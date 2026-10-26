use crate::persistent_engine;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

static REQUEST_ID: AtomicU64 = AtomicU64::new(1);

#[derive(Debug, Serialize, Deserialize)]
pub struct EngineError {
    code: String,
    message: String,
}

impl EngineError {
    fn new(code: &str, message: impl Into<String>) -> Self {
        Self {
            code: code.into(),
            message: message.into(),
        }
    }
}

fn request_with_control(
    method: &str,
    params: Value,
    control: Option<(&AtomicBool, &std::path::Path)>,
) -> Result<Value, EngineError> {
    if control.is_some_and(|(cancelled, _)| cancelled.load(Ordering::Relaxed)) {
        return Err(EngineError::new("CANCELLED", "Engine request cancelled"));
    }

    let id = format!(
        "{}-{}",
        std::process::id(),
        REQUEST_ID.fetch_add(1, Ordering::Relaxed)
    );
    let payload = json!({
        "version": 1,
        "id": id,
        "method": method,
        "params": params,
    });
    let timeout = if method == "audio.prepare" {
        Duration::from_secs(3605)
    } else {
        Duration::from_secs(35)
    };
    let (cancelled, cancel_file) = control
        .map(|(flag, path)| (Some(flag), Some(path)))
        .unwrap_or((None, None));

    let response = persistent_engine::request(
        &payload,
        cancelled,
        if method == "audio.prepare" { cancel_file } else { None },
        timeout,
    )
    .map_err(|message| match message.as_str() {
        "CANCELLED" => EngineError::new("CANCELLED", "Engine request cancelled"),
        "ENGINE_TIMEOUT" => EngineError::new("ENGINE_TIMEOUT", "The engine request timed out"),
        _ if message.contains("not installed") => EngineError::new("ENGINE_NOT_INSTALLED", message),
        _ => EngineError::new("ENGINE_IO_ERROR", message),
    })?;

    if response.get("version") != Some(&json!(1)) || response.get("id") != Some(&json!(id)) {
        return Err(EngineError::new(
            "ENGINE_PROTOCOL_ERROR",
            "Engine response version or request ID does not match",
        ));
    }
    if let Some(error) = response.get("error") {
        return Err(serde_json::from_value(error.clone()).map_err(|_| {
            EngineError::new("ENGINE_PROTOCOL_ERROR", "Engine returned an invalid error")
        })?);
    }
    response
        .get("result")
        .cloned()
        .ok_or_else(|| EngineError::new("ENGINE_PROTOCOL_ERROR", "Engine response has no result"))
}

#[cfg(test)]
fn request(method: &str, params: Value) -> Result<Value, EngineError> {
    request_with_control(method, params, None)
}

#[derive(Default)]
pub struct EngineJobs(Mutex<HashMap<String, JobToken>>, AtomicBool, AtomicBool);

impl EngineJobs {
    fn register(&self, id: &str, cancelled: Arc<AtomicBool>) -> Result<(), EngineError> {
        let mut active = self
            .0
            .lock()
            .map_err(|_| EngineError::new("JOB_STATE_ERROR", "Could not access engine jobs"))?;
        if self.1.load(Ordering::SeqCst) {
            return Err(EngineError::new("APP_CLOSING", "Catty is closing"));
        }
        active.insert(
            id.into(),
            JobToken {
                cancelled,
                pending_until: None,
            },
        );
        Ok(())
    }

    pub fn begin_shutdown(&self) -> bool {
        if self.1.swap(true, Ordering::SeqCst) {
            return false;
        }
        if let Ok(active) = self.0.lock() {
            for token in active.values() {
                token.cancelled.store(true, Ordering::Relaxed);
            }
        }
        true
    }

    pub fn drain(&self) {
        let start = Instant::now();
        loop {
            let running = self
                .0
                .lock()
                .map(|active| active.values().any(|token| token.pending_until.is_none()))
                .unwrap_or(false);
            if !running || start.elapsed() > Duration::from_secs(4) {
                break;
            }
            std::thread::sleep(Duration::from_millis(20));
        }
        persistent_engine::shutdown();
        self.2.store(true, Ordering::SeqCst);
    }

    pub fn shutdown_finished(&self) -> bool {
        self.2.load(Ordering::SeqCst)
    }
}

struct JobToken {
    cancelled: Arc<AtomicBool>,
    pending_until: Option<Instant>,
}

fn prune_jobs(active: &mut HashMap<String, JobToken>) {
    active.retain(|_, token| {
        token
            .pending_until
            .is_none_or(|until| until > Instant::now())
    });
}

fn validate_job_id(id: &str) -> Result<(), EngineError> {
    if id.len() != 36
        || !id
            .bytes()
            .all(|byte| byte.is_ascii_hexdigit() || byte == b'-')
    {
        return Err(EngineError::new(
            "INVALID_JOB_ID",
            "Expected a UUID job identifier",
        ));
    }
    Ok(())
}

#[tauri::command]
pub async fn engine_request(
    method: String,
    params: Value,
    jobs: tauri::State<'_, EngineJobs>,
) -> Result<Value, EngineError> {
    if !matches!(method.as_str(), "health" | "system.hello" | "media.probe") {
        return Err(EngineError::new(
            "UNKNOWN_METHOD",
            "This engine operation is not available",
        ));
    }

    let id = format!("rpc-{}", REQUEST_ID.fetch_add(1, Ordering::Relaxed));
    let cancelled = Arc::new(AtomicBool::new(false));
    jobs.register(&id, cancelled.clone())?;
    let result = tauri::async_runtime::spawn_blocking(move || {
        request_with_control(
            &method,
            params,
            Some((
                &cancelled,
                &std::env::temp_dir().join("catty-unused-cancel"),
            )),
        )
    })
    .await;
    if let Ok(mut active) = jobs.0.lock() {
        active.remove(&id);
    }
    result.map_err(|error| EngineError::new("ENGINE_TASK_FAILED", error.to_string()))?
}

#[tauri::command]
pub async fn prepare_audio(
    job_id: String,
    source: String,
    episode_id: String,
    project_directory: String,
    existing_asset: Option<Value>,
    jobs: tauri::State<'_, EngineJobs>,
) -> Result<Value, EngineError> {
    validate_job_id(&job_id)?;
    let cancelled = Arc::new(AtomicBool::new(false));
    {
        let mut active = jobs
            .0
            .lock()
            .map_err(|_| EngineError::new("JOB_STATE_ERROR", "Could not access engine jobs"))?;
        if jobs.1.load(Ordering::SeqCst) {
            return Err(EngineError::new("APP_CLOSING", "Catty is closing"));
        }
        prune_jobs(&mut active);
        if let Some(previous) = active.get(&job_id) {
            if previous.pending_until.is_some() {
                active.remove(&job_id);
                return Err(EngineError::new("CANCELLED", "Audio preparation cancelled"));
            }
            return Err(EngineError::new(
                "DUPLICATE_JOB",
                "This job is already running",
            ));
        }
        if active.len() >= 16 {
            return Err(EngineError::new(
                "JOB_LIMIT",
                "Too many engine jobs are running",
            ));
        }
        active.insert(
            job_id.clone(),
            JobToken {
                cancelled: cancelled.clone(),
                pending_until: None,
            },
        );
    }

    let job_id_for_cleanup = job_id.clone();
    let result = tauri::async_runtime::spawn_blocking(move || {
        let directory = std::env::temp_dir().join("catty-engine-jobs").join(&job_id);
        std::fs::create_dir_all(&directory)
            .map_err(|error| EngineError::new("JOB_IO_ERROR", error.to_string()))?;
        let cancel_file = directory.join("cancel");
        let result = request_with_control(
            "audio.prepare",
            json!({
                "source": source,
                "episode_id": episode_id,
                "project_directory": project_directory,
                "existing_asset": existing_asset,
                "cancel_file": cancel_file,
            }),
            Some((&cancelled, &cancel_file)),
        );
        let _ = std::fs::remove_file(&cancel_file);
        let _ = std::fs::remove_dir(&directory);
        result
    })
    .await
    .map_err(|error| EngineError::new("ENGINE_TASK_FAILED", error.to_string()));

    if let Ok(mut active) = jobs.0.lock() {
        active.remove(&job_id_for_cleanup);
    }
    result?
}

#[tauri::command]
pub fn cancel_audio(
    job_id: String,
    jobs: tauri::State<'_, EngineJobs>,
) -> Result<(), EngineError> {
    validate_job_id(&job_id)?;
    let mut active = jobs
        .0
        .lock()
        .map_err(|_| EngineError::new("JOB_STATE_ERROR", "Could not access engine jobs"))?;
    prune_jobs(&mut active);
    if active.len() >= 16 && !active.contains_key(&job_id) {
        return Err(EngineError::new("JOB_LIMIT", "Too many engine jobs"));
    }
    active
        .entry(job_id)
        .or_insert_with(|| JobToken {
            cancelled: Arc::new(AtomicBool::new(false)),
            pending_until: Some(Instant::now() + Duration::from_secs(30)),
        })
        .cancelled
        .store(true, Ordering::Relaxed);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shutdown_cancels_registered_jobs_and_rejects_new_work() {
        let jobs = EngineJobs::default();
        let probe = Arc::new(AtomicBool::new(false));
        let audio = Arc::new(AtomicBool::new(false));
        jobs.register("probe", probe.clone()).unwrap();
        jobs.register("audio", audio.clone()).unwrap();
        assert!(jobs.begin_shutdown());
        assert!(probe.load(Ordering::Relaxed));
        assert!(audio.load(Ordering::Relaxed));
        assert!(!jobs.begin_shutdown());
        assert_eq!(
            jobs.register("late", Arc::new(AtomicBool::new(false)))
                .unwrap_err()
                .code,
            "APP_CLOSING"
        );
    }

    #[test]
    fn persistent_engine_handles_multiple_requests() {
        let hello = request("system.hello", json!({})).expect("engine hello");
        assert_eq!(hello["name"], "catty-engine");
        assert_eq!(hello["protocol_version"], 1);
        let health = request("health", json!({})).expect("engine health");
        assert_eq!(health["name"], "catty-engine");
    }

    #[test]
    fn engine_reports_missing_media() {
        let error = request(
            "media.probe",
            json!({"path": "/__catty_missing_media__.mp4"}),
        )
        .unwrap_err();
        assert_eq!(error.code, "MEDIA_PROBE_FAILED");
    }
}

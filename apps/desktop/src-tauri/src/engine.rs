use crate::processes;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::io::Write;
use std::path::PathBuf;
use std::process::{Command, Stdio};
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

#[cfg(test)]
fn request(method: &str, params: Value) -> Result<Value, EngineError> {
    request_with_control(method, params, None)
}

fn request_with_control(
    method: &str,
    params: Value,
    control: Option<(&AtomicBool, &std::path::Path)>,
) -> Result<Value, EngineError> {
    if control.is_some_and(|(cancelled, _)| cancelled.load(Ordering::Relaxed)) {
        return Err(EngineError::new("CANCELLED", "Audio preparation cancelled"));
    }
    let timeout = if method == "audio.prepare" { 3605 } else { 35 };
    let directory = std::env::var_os("CATTY_ENGINE_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../engine"));
    let python = std::env::var_os("CATTY_ENGINE_PYTHON")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            directory.join(if cfg!(windows) {
                ".venv/Scripts/python.exe"
            } else {
                ".venv/bin/python"
            })
        });
    if !python.is_file() {
        return Err(EngineError::new("ENGINE_NOT_INSTALLED", "Python engine is not installed. Run `uv sync` in the engine directory, then restart Catty."));
    }
    let id = format!(
        "{}-{}",
        std::process::id(),
        REQUEST_ID.fetch_add(1, Ordering::Relaxed)
    );
    let payload = json!({ "version": 1, "id": id, "method": method, "params": params });
    let mut command = Command::new(python);
    processes::isolate(&mut command);
    let mut child = command
        .args(["-m", "catty_engine", "--rpc"])
        .current_dir(&directory)
        .env("PYTHONPATH", directory.join("src"))
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|error| EngineError::new("ENGINE_START_FAILED", error.to_string()))?;
    let written = child
        .stdin
        .take()
        .ok_or_else(|| EngineError::new("ENGINE_IO_ERROR", "Engine stdin is unavailable"))
        .and_then(|mut stdin| {
            stdin
                .write_all(payload.to_string().as_bytes())
                .map_err(|error| EngineError::new("ENGINE_IO_ERROR", error.to_string()))
        });
    if let Err(error) = written {
        processes::terminate(&mut child);
        return Err(error);
    }
    let started = Instant::now();
    let mut cancellation_started = None;
    loop {
        if let Some((cancelled, path)) = control {
            if cancelled.load(Ordering::Relaxed) {
                if method == "audio.prepare" {
                    let _ = std::fs::write(path, b"cancel");
                }
                let since = cancellation_started.get_or_insert_with(Instant::now);
                if method != "audio.prepare" || since.elapsed() > Duration::from_secs(2) {
                    processes::terminate(&mut child);
                    return Err(EngineError::new("CANCELLED", "Engine request cancelled"));
                }
            }
        }
        match child.try_wait() {
            Ok(Some(_)) => break,
            Ok(None) if started.elapsed() < Duration::from_secs(timeout) => {
                std::thread::sleep(Duration::from_millis(20))
            }
            Ok(None) => {
                processes::terminate(&mut child);
                return Err(EngineError::new(
                    "ENGINE_TIMEOUT",
                    "The engine request timed out.",
                ));
            }
            Err(error) => {
                processes::terminate(&mut child);
                return Err(EngineError::new("ENGINE_IO_ERROR", error.to_string()));
            }
        }
    }
    let output = child
        .wait_with_output()
        .map_err(|error| EngineError::new("ENGINE_IO_ERROR", error.to_string()))?;
    if !output.status.success() {
        return Err(EngineError::new(
            "ENGINE_EXITED",
            format!(
                "Engine exited unsuccessfully: {}",
                String::from_utf8_lossy(&output.stderr).trim()
            ),
        ));
    }
    let response: Value = serde_json::from_slice(&output.stdout)
        .map_err(|error| EngineError::new("ENGINE_PROTOCOL_ERROR", error.to_string()))?;
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

#[tauri::command]
pub async fn engine_request(
    method: String,
    params: Value,
    jobs: tauri::State<'_, EngineJobs>,
) -> Result<Value, EngineError> {
    if !matches!(method.as_str(), "health" | "media.probe") {
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
            if !running {
                break;
            }
            if start.elapsed() > Duration::from_secs(4) {
                break;
            }
            std::thread::sleep(Duration::from_millis(20));
        }
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
            .map_or(true, |until| until > Instant::now())
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
        std::fs::create_dir_all(&directory).map_err(|error| EngineError::new("JOB_IO_ERROR", error.to_string()))?;
        let cancel_file = directory.join("cancel");
        let result = request_with_control("audio.prepare", json!({ "source": source, "episode_id": episode_id, "project_directory": project_directory, "existing_asset": existing_asset, "cancel_file": cancel_file }), Some((&cancelled, &cancel_file)));
        let _ = std::fs::remove_file(&cancel_file); let _ = std::fs::remove_dir(&directory);
        result
    }).await.map_err(|error| EngineError::new("ENGINE_TASK_FAILED", error.to_string()));
    // Completion (including errors) always releases the cancellation token.
    if let Ok(mut active) = jobs.0.lock() {
        active.remove(&job_id_for_cleanup);
    }
    result?
}

#[tauri::command]
pub fn cancel_audio(job_id: String, jobs: tauri::State<'_, EngineJobs>) -> Result<(), EngineError> {
    validate_job_id(&job_id)?;
    let mut active = jobs
        .0
        .lock()
        .map_err(|_| EngineError::new("JOB_STATE_ERROR", "Could not access engine jobs"))?;
    prune_jobs(&mut active);
    if active.len() >= 16 && !active.contains_key(&job_id) {
        return Err(EngineError::new("JOB_LIMIT", "Too many engine jobs"));
    }
    // Remember cancellation if it reaches Tauri just before the start command.
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
        assert!(!jobs.begin_shutdown(), "shutdown is idempotent");
        assert_eq!(
            jobs.register("late", Arc::new(AtomicBool::new(false)))
                .unwrap_err()
                .code,
            "APP_CLOSING"
        );
        jobs.0.lock().unwrap().clear();
        jobs.drain();
        assert!(jobs.shutdown_finished());
    }
    #[test]
    fn engine_health_round_trip() {
        let result = request("health", json!({})).expect("engine health");
        assert_eq!(result["name"], "catty-engine");
    }
    fn audio_fixture(path: &std::path::Path) {
        let mut wav = Vec::new();
        wav.extend_from_slice(b"RIFF");
        wav.extend_from_slice(&1636u32.to_le_bytes());
        wav.extend_from_slice(b"WAVEfmt ");
        wav.extend_from_slice(&16u32.to_le_bytes());
        wav.extend_from_slice(&1u16.to_le_bytes());
        wav.extend_from_slice(&1u16.to_le_bytes());
        wav.extend_from_slice(&8000u32.to_le_bytes());
        wav.extend_from_slice(&16000u32.to_le_bytes());
        wav.extend_from_slice(&2u16.to_le_bytes());
        wav.extend_from_slice(&16u16.to_le_bytes());
        wav.extend_from_slice(b"data");
        wav.extend_from_slice(&1600u32.to_le_bytes());
        wav.resize(1644, 0);
        std::fs::write(path, wav).expect("write media fixture");
    }
    #[test]
    fn engine_probes_real_audio() {
        let path =
            std::env::temp_dir().join(format!("catty-engine-probe-{}.wav", std::process::id()));
        audio_fixture(&path);
        let result = request("media.probe", json!({"path": path}));
        let _ = std::fs::remove_file(&path);
        let result = result.expect("probe real audio through Python and FFprobe");
        assert_eq!(result["sample_rate"], 8000);
        assert_eq!(result["channels"], 1);
        assert_eq!(result["duration"], 0.1);
    }
    #[test]
    fn engine_prepares_and_caches_speech_audio() {
        let directory =
            std::env::temp_dir().join(format!("catty-audio-integration-{}", std::process::id()));
        std::fs::create_dir_all(&directory).unwrap();
        let source = directory.join("source.wav");
        audio_fixture(&source);
        let params = json!({ "source": source, "project_directory": directory.join("project"), "episode_id": "00000000-0000-4000-8000-000000000001" });
        let result = (|| -> Result<(), EngineError> {
            let asset = request("audio.prepare", params.clone())?;
            assert_eq!(asset["sample_rate"], 16000);
            assert_eq!(asset["channels"], 1);
            let probe = request("media.probe", json!({"path": asset["path"]}))?;
            assert_eq!(probe["sample_rate"], 16000);
            assert_eq!(probe["channels"], 1);
            let mut cached = params;
            cached["existing_asset"] = asset.clone();
            assert_eq!(request("audio.prepare", cached)?, asset);
            Ok(())
        })();
        let _ = std::fs::remove_dir_all(directory);
        result.expect("prepare speech WAV through Rust, Python, and FFmpeg");
    }
    #[test]
    fn engine_audio_honors_pre_cancelled_token() {
        let cancelled = AtomicBool::new(true);
        let path = std::env::temp_dir().join("catty-test-cancel");
        let error = request_with_control("audio.prepare", json!({}), Some((&cancelled, &path)))
            .unwrap_err();
        assert_eq!(error.code, "CANCELLED");
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

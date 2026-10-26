use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::io::Write;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};
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

fn request(method: &str, params: Value) -> Result<Value, EngineError> {
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
    let mut child = Command::new(python)
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
        let _ = child.kill();
        let _ = child.wait();
        return Err(error);
    }
    let started = Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(_)) => break,
            Ok(None) if started.elapsed() < Duration::from_secs(35) => {
                std::thread::sleep(Duration::from_millis(20))
            }
            Ok(None) => {
                let _ = child.kill();
                let _ = child.wait();
                return Err(EngineError::new(
                    "ENGINE_TIMEOUT",
                    "The engine request timed out.",
                ));
            }
            Err(error) => {
                let _ = child.kill();
                let _ = child.wait();
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
pub async fn engine_request(method: String, params: Value) -> Result<Value, EngineError> {
    if !matches!(method.as_str(), "health" | "media.probe") {
        return Err(EngineError::new(
            "UNKNOWN_METHOD",
            "This engine operation is not available",
        ));
    }
    tauri::async_runtime::spawn_blocking(move || request(&method, params))
        .await
        .map_err(|error| EngineError::new("ENGINE_TASK_FAILED", error.to_string()))?
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn engine_health_round_trip() {
        let result = request("health", json!({})).expect("engine health");
        assert_eq!(result["name"], "catty-engine");
    }
    #[test]
    fn engine_probes_real_audio() {
        let path =
            std::env::temp_dir().join(format!("catty-engine-probe-{}.wav", std::process::id()));
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
        std::fs::write(&path, wav).expect("write media fixture");
        let result = request("media.probe", json!({"path": path}));
        let _ = std::fs::remove_file(&path);
        let result = result.expect("probe real audio through Python and FFprobe");
        assert_eq!(result["sample_rate"], 8000);
        assert_eq!(result["channels"], 1);
        assert_eq!(result["duration"], 0.1);
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

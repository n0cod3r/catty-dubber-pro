use serde_json::Value;
use std::sync::OnceLock;
use tauri::{AppHandle, Emitter};

static APP: OnceLock<AppHandle> = OnceLock::new();
pub fn initialize(app: AppHandle) {
    let _ = APP.set(app);
}

fn progress_event(line: &str) -> Option<(&'static str, Value)> {
    let value: Value = serde_json::from_str(line).ok()?;
    let event = match value["catty_progress"].as_str()? {
        "translation" => "catty:translation-progress",
        "transcription" => "catty:transcription-progress",
        "tts" => "catty:tts-progress",
        _ => return None,
    };
    let payload = &value["payload"];
    if !payload["operation_id"].is_string()
        || !payload["episode_id"].is_string()
        || !payload["phase"].is_string()
    {
        return None;
    }
    Some((event, payload.clone()))
}

pub fn forward(line: &str) -> bool {
    if let Some((event, payload)) = progress_event(line) {
        if let Some(app) = APP.get() {
            let _ = app.emit(event, payload);
        }
        return true;
    }
    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn forwards_only_correlated_progress_without_touching_rpc_or_logs() {
        assert!(progress_event(r#"{"catty_progress":"translation","payload":{"operation_id":"job1","episode_id":"ep1","phase":"saved","completed":1}}"#).is_some());
        assert!(progress_event(r#"{"catty_progress":"transcription","payload":{"operation_id":"job1","episode_id":"ep1","phase":"asr"}}"#).is_some());
        assert!(progress_event(r#"{"catty_progress":"tts","payload":{"operation_id":"job1","episode_id":"ep1","phase":"saved","completed":1}}"#).is_some());
        assert!(progress_event(r#"{"catty_log":true,"message":"test"}"#).is_none());
        assert!(progress_event(r#"{"version":1,"result":{}}"#).is_none());
        assert!(progress_event(r#"{"catty_progress":"tts","payload":{}}"#).is_none());
    }
}

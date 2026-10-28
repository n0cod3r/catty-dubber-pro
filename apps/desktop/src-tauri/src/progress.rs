use serde_json::Value;
use std::sync::OnceLock;
use tauri::{AppHandle, Emitter};

static APP: OnceLock<AppHandle> = OnceLock::new();
pub fn initialize(app: AppHandle) {
    let _ = APP.set(app);
}

fn translation_payload(line: &str) -> Option<Value> {
    let value: Value = serde_json::from_str(line).ok()?;
    if value["catty_progress"] != "translation" {
        return None;
    }
    let payload = &value["payload"];
    if !payload["operation_id"].is_string()
        || !payload["episode_id"].is_string()
        || !payload["phase"].is_string()
    {
        return None;
    }
    Some(payload.clone())
}

pub fn forward(line: &str) -> bool {
    if let Some(payload) = translation_payload(line) {
        if let Some(app) = APP.get() {
            let _ = app.emit("catty:translation-progress", payload);
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
        assert!(translation_payload(r#"{"catty_progress":"translation","payload":{"operation_id":"job1","episode_id":"ep1","phase":"saved","completed":1}}"#).is_some());
        assert!(translation_payload(r#"{"catty_log":true,"message":"test"}"#).is_none());
        assert!(translation_payload(r#"{"version":1,"result":{}}"#).is_none());
        assert!(translation_payload(r#"{"catty_progress":"translation","payload":{}}"#).is_none());
    }
}

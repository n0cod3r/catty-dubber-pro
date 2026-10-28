use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::sync::{Mutex, OnceLock};
use std::time::{SystemTime, UNIX_EPOCH};

const LIMIT: usize = 2000;
#[derive(Clone, Serialize, Deserialize)]
pub struct LogEntry {
    id: u64,
    timestamp: u64,
    source: String,
    level: String,
    message: String,
}
#[derive(Default)]
struct Buffer {
    next: u64,
    entries: VecDeque<LogEntry>,
}
static LOGS: OnceLock<Mutex<Buffer>> = OnceLock::new();
fn buffer() -> &'static Mutex<Buffer> {
    LOGS.get_or_init(|| Mutex::new(Buffer::default()))
}

fn redact(message: &str) -> String {
    static SECRETS: OnceLock<regex::Regex> = OnceLock::new();
    static BEARER: OnceLock<regex::Regex> = OnceLock::new();
    let bearer = BEARER.get_or_init(|| regex::Regex::new(r#"(?i)(bearer\s+)[^\s"']+"#).unwrap());
    let secrets = SECRETS.get_or_init(|| regex::Regex::new(r#"(?i)((?:api[_-]?key|access[_-]?token|authorization|password|secret)["']?\s*[:=]\s*["']?)[^\s,"'}]+"#).unwrap());
    let message = bearer.replace_all(message, "${1}[REDACTED]");
    secrets.replace_all(&message, "${1}[REDACTED]").into_owned()
}

pub fn record(source: &str, level: &str, message: &str) {
    if let Ok(mut logs) = buffer().lock() {
        logs.next += 1;
        let entry = LogEntry {
            id: logs.next,
            timestamp: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_millis() as u64,
            source: source.into(),
            level: level.into(),
            message: redact(message).chars().take(8192).collect(),
        };
        logs.entries.push_back(entry);
        while logs.entries.len() > LIMIT {
            logs.entries.pop_front();
        }
    }
}

pub fn python_line(line: &str) {
    if let Ok(value) = serde_json::from_str::<serde_json::Value>(line) {
        if value["catty_log"] == true {
            let logger = value["logger"].as_str().unwrap_or("engine");
            let request = value["request_id"].as_str().unwrap_or("-");
            record(
                "python",
                value["level"].as_str().unwrap_or("INFO"),
                &format!(
                    "[{logger}] [{request}] {}",
                    value["message"].as_str().unwrap_or("")
                ),
            );
            return;
        }
    }
    // Third-party progress output and tracebacks are retained alongside structured logs.
    record("python", "INFO", line);
}

#[tauri::command]
pub fn app_logs(after: Option<u64>) -> Vec<LogEntry> {
    buffer()
        .lock()
        .map(|logs| {
            logs.entries
                .iter()
                .filter(|entry| entry.id > after.unwrap_or(0))
                .cloned()
                .collect()
        })
        .unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn bounded_history_preserves_monotonic_cursor_and_python_messages() {
        for _ in 0..2100 {
            record("rust", "INFO", "test");
        }
        let entries = app_logs(None);
        assert_eq!(entries.len(), LIMIT);
        let cursor = entries.last().unwrap().id;
        python_line(
            r#"{"catty_log":true,"logger":"speech","request_id":"r1","level":"ERROR","message":"failed"}"#,
        );
        let new = app_logs(Some(cursor));
        let python = new
            .iter()
            .find(|entry| entry.message.contains("[r1] failed"))
            .unwrap();
        assert_eq!(python.level, "ERROR");
        assert!(!redact("api_key=private Authorization: Bearer token").contains("private"));
        assert!(!redact("api_key=private Authorization: Bearer token").contains("token"));
    }
}

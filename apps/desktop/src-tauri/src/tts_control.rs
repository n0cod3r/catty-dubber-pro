use std::path::PathBuf;

fn validate_operation_id(id: &str) -> Result<(), String> {
    if id.len() != 36 || !id.bytes().all(|byte| byte.is_ascii_hexdigit() || byte == b'-') {
        return Err("Expected a UUID operation identifier".into());
    }
    Ok(())
}

fn job_dir(operation_id: &str) -> PathBuf {
    std::env::temp_dir().join("catty-tts-jobs").join(operation_id)
}

#[tauri::command]
pub fn prepare_tts_cancel(operation_id: String) -> Result<String, String> {
    validate_operation_id(&operation_id)?;
    let directory = job_dir(&operation_id);
    std::fs::create_dir_all(&directory).map_err(|error| error.to_string())?;
    let cancel = directory.join("cancel");
    let _ = std::fs::remove_file(&cancel);
    Ok(cancel.to_string_lossy().into_owned())
}

#[tauri::command]
pub fn cancel_tts(operation_id: String) -> Result<(), String> {
    validate_operation_id(&operation_id)?;
    let directory = job_dir(&operation_id);
    std::fs::create_dir_all(&directory).map_err(|error| error.to_string())?;
    std::fs::write(directory.join("cancel"), b"cancel").map_err(|error| error.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_invalid_operation_id() {
        assert!(prepare_tts_cancel("bad".into()).is_err());
    }
}

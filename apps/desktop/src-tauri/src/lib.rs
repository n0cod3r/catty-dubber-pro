mod engine;

#[tauri::command]
fn app_status() -> &'static str {
    "Catty Dubber Pro desktop shell is ready"
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(engine::EngineJobs::default())
        .invoke_handler(tauri::generate_handler![
            app_status,
            engine::engine_request,
            engine::prepare_audio,
            engine::cancel_audio
        ])
        .run(tauri::generate_context!())
        .expect("error while running Catty Dubber Pro");
}

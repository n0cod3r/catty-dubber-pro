mod engine;
mod persistent_engine;
mod processes;

use tauri::{Emitter, Manager};

#[tauri::command]
fn app_status() -> &'static str {
    "Catty Dubber Pro desktop shell is ready"
}

fn shutdown(app: tauri::AppHandle) {
    if !app.state::<engine::EngineJobs>().begin_shutdown() {
        return;
    }
    let _ = app.emit("catty:shutting-down", ());
    tauri::async_runtime::spawn_blocking(move || {
        app.state::<engine::EngineJobs>().drain();
        app.exit(0);
    });
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(engine::EngineJobs::default())
        .setup(|app| {
            if let Some(window) = app.get_webview_window("main") {
                window.maximize()?;
                window.show()?;
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            app_status,
            engine::engine_request,
            engine::prepare_audio,
            engine::cancel_audio
        ])
        .on_window_event(|window, event| {
            if window.label() != "main" {
                return;
            }
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                if !window.state::<engine::EngineJobs>().shutdown_finished() {
                    api.prevent_close();
                    shutdown(window.app_handle().clone());
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building Catty Dubber Pro");
    app.run(|app, event| {
        if let tauri::RunEvent::ExitRequested { api, .. } = event {
            if !app.state::<engine::EngineJobs>().shutdown_finished() {
                api.prevent_exit();
                shutdown(app.clone());
            }
        }
    });
}

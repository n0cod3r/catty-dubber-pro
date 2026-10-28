mod engine;
mod logs;
mod persistent_engine;
mod processes;
mod progress;

use tauri::{Emitter, Manager};

#[tauri::command]
fn app_status() -> &'static str {
    "Catty Dubber Pro desktop shell is ready"
}

/// Projects can live on external drives or outside the static asset scope.
/// Allow the chosen media/project paths for the asset protocol at runtime.
#[tauri::command]
fn allow_asset_path(app: tauri::AppHandle, path: String) -> Result<(), String> {
    let path = std::path::PathBuf::from(&path);
    if !path.is_absolute() {
        return Err("Media path must be absolute".into());
    }
    let scope = app.asset_protocol_scope();
    let result = if path.is_file() {
        scope.allow_file(&path)
    } else {
        scope.allow_directory(&path, true)
    };
    result.map_err(|error| format!("Could not allow media path: {error}"))
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
            progress::initialize(app.handle().clone());
            logs::record("rust", "INFO", "Catty desktop started");
            if let Some(window) = app.get_webview_window("main") {
                window.maximize()?;
                window.show()?;
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            app_status,
            allow_asset_path,
            logs::app_logs,
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

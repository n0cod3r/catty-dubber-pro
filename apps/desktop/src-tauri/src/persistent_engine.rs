use crate::processes;
use serde_json::Value;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{self, Receiver, TryRecvError};
use std::sync::{Mutex, OnceLock};
use std::time::{Duration, Instant};

static ENGINE: OnceLock<Mutex<Option<EngineProcess>>> = OnceLock::new();

fn runtime() -> &'static Mutex<Option<EngineProcess>> {
    ENGINE.get_or_init(|| Mutex::new(None))
}

struct EngineProcess {
    child: Child,
    stdin: ChildStdin,
    responses: Receiver<String>,
}

impl EngineProcess {
    fn start() -> Result<Self, String> {
        let directory = engine_directory();
        let python = engine_python(&directory);
        if !python.is_file() {
            return Err(
                "Python engine is not installed. Run `uv sync` in the engine directory, then restart Catty."
                    .into(),
            );
        }

        let mut command = Command::new(python);
        processes::isolate(&mut command);
        let mut child = command
            .args(["-m", "catty_engine", "--server"])
            .current_dir(&directory)
            .env("PYTHONPATH", directory.join("src"))
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|error| error.to_string())?;

        let stdin = child.stdin.take().ok_or("Engine stdin is unavailable")?;
        let stdout = child.stdout.take().ok_or("Engine stdout is unavailable")?;
        let stderr = child.stderr.take().ok_or("Engine stderr is unavailable")?;
        let (sender, responses) = mpsc::channel();

        std::thread::spawn(move || {
            for line in BufReader::new(stdout).lines() {
                match line {
                    Ok(line) => {
                        if sender.send(line).is_err() {
                            break;
                        }
                    }
                    Err(_) => break,
                }
            }
        });
        std::thread::spawn(move || {
            for line in BufReader::new(stderr).lines().map_while(Result::ok) {
                eprintln!("[catty-engine] {line}");
            }
        });

        Ok(Self {
            child,
            stdin,
            responses,
        })
    }

    fn send(
        &mut self,
        payload: &Value,
        cancelled: Option<&AtomicBool>,
        cancel_file: Option<&Path>,
        timeout: Duration,
    ) -> Result<Value, String> {
        writeln!(self.stdin, "{payload}").map_err(|error| error.to_string())?;
        self.stdin.flush().map_err(|error| error.to_string())?;

        let started = Instant::now();
        let mut cancellation_started = None;
        loop {
            if cancelled.is_some_and(|flag| flag.load(Ordering::Relaxed)) {
                if let Some(path) = cancel_file {
                    let _ = std::fs::write(path, b"cancel");
                }
                let since = cancellation_started.get_or_insert_with(Instant::now);
                if cancel_file.is_none() || since.elapsed() > Duration::from_secs(2) {
                    return Err("CANCELLED".into());
                }
            }

            match self.responses.try_recv() {
                Ok(line) => {
                    return serde_json::from_str(&line).map_err(|error| error.to_string());
                }
                Err(TryRecvError::Disconnected) => {
                    return Err("Engine response channel closed".into());
                }
                Err(TryRecvError::Empty) => {}
            }

            match self.child.try_wait() {
                Ok(Some(status)) => return Err(format!("Engine exited with {status}")),
                Ok(None) => {}
                Err(error) => return Err(error.to_string()),
            }

            if started.elapsed() >= timeout {
                return Err("ENGINE_TIMEOUT".into());
            }
            std::thread::sleep(Duration::from_millis(20));
        }
    }

    fn stop(&mut self) {
        let payload = serde_json::json!({
            "version": 1,
            "id": "shutdown",
            "method": "system.shutdown",
            "params": {}
        });
        let _ = writeln!(self.stdin, "{payload}");
        let _ = self.stdin.flush();

        let started = Instant::now();
        while started.elapsed() < Duration::from_secs(2) {
            match self.child.try_wait() {
                Ok(Some(_)) => return,
                Ok(None) => std::thread::sleep(Duration::from_millis(20)),
                Err(_) => break,
            }
        }
        processes::terminate(&mut self.child);
    }
}

fn engine_directory() -> PathBuf {
    std::env::var_os("CATTY_ENGINE_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../engine"))
}

fn engine_python(directory: &Path) -> PathBuf {
    std::env::var_os("CATTY_ENGINE_PYTHON")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            directory.join(if cfg!(windows) {
                ".venv/Scripts/python.exe"
            } else {
                ".venv/bin/python"
            })
        })
}

pub fn request(
    payload: &Value,
    cancelled: Option<&AtomicBool>,
    cancel_file: Option<&Path>,
    timeout: Duration,
) -> Result<Value, String> {
    let mut guard = runtime()
        .lock()
        .map_err(|_| "Could not lock Python engine runtime".to_string())?;

    if guard.is_none() {
        *guard = Some(EngineProcess::start()?);
    }

    let result = guard
        .as_mut()
        .expect("engine was initialized")
        .send(payload, cancelled, cancel_file, timeout);

    let restart_engine = matches!(
        result.as_ref().err().map(String::as_str),
        Some("CANCELLED" | "ENGINE_TIMEOUT")
    );
    if restart_engine {
        if let Some(mut engine) = guard.take() {
            processes::terminate(&mut engine.child);
        }
    }
    result
}

pub fn shutdown() {
    if let Ok(mut guard) = runtime().lock() {
        if let Some(mut engine) = guard.take() {
            engine.stop();
        }
    }
}

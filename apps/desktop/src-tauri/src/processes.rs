use std::process::{Child, Command};

// Each engine request owns a process group so aborting Python also aborts
// ffprobe/FFmpeg descendants, including on window close and timeout.
pub fn isolate(command: &mut Command) {
    #[cfg(unix)]
    {
        use std::os::unix::process::CommandExt;
        command.process_group(0);
    }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }
}

pub fn terminate(child: &mut Child) {
    #[cfg(unix)]
    // SAFETY: the process-group ID is that of our isolated child. Negative
    // PIDs target only that group; SIGKILL ensures no descendant survives exit.
    unsafe {
        libc::kill(-(child.id() as i32), libc::SIGKILL);
    }
    #[cfg(windows)]
    {
        let _ = Command::new("taskkill")
            .args(["/PID", &child.id().to_string(), "/T", "/F"])
            .output();
    }
    let _ = child.kill();
    let _ = child.wait();
}

#[cfg(all(test, unix))]
mod tests {
    use super::*;
    use std::io::{BufRead, BufReader};

    #[test]
    fn terminating_engine_group_stops_descendants() {
        let mut command = Command::new("sh");
        command
            .args(["-c", "sleep 30 & echo $!; wait"])
            .stdout(std::process::Stdio::piped());
        isolate(&mut command);
        let mut parent = command.spawn().unwrap();
        let mut line = String::new();
        BufReader::new(parent.stdout.take().unwrap())
            .read_line(&mut line)
            .unwrap();
        let descendant = line.trim().parse::<u32>().unwrap();
        terminate(&mut parent);
        assert!(parent.try_wait().unwrap().is_some());
        let start = std::time::Instant::now();
        loop {
            let output = Command::new("ps")
                .args(["-o", "stat=", "-p", &descendant.to_string()])
                .output()
                .unwrap();
            let status = String::from_utf8_lossy(&output.stdout);
            if status.trim().is_empty() || status.trim_start().starts_with('Z') {
                break;
            }
            assert!(
                start.elapsed() < std::time::Duration::from_secs(2),
                "engine descendant is still running: {status}"
            );
            std::thread::sleep(std::time::Duration::from_millis(20));
        }
    }
}

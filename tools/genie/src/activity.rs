use crate::protocol::Activity;
use std::io::{self, IsTerminal, Write};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{self, SyncSender, TrySendError};
use std::time::{Duration, Instant};

struct Frame {
    label: String,
    seconds: u64,
    completed: u64,
    index: usize,
}

enum Output {
    Frame(Frame),
    Diagnostic(Vec<u8>),
    Clear,
    Finish {
        text: Option<String>,
        diagnostic: Option<String>,
    },
}

fn terminal_columns() -> usize {
    let mut size = std::mem::MaybeUninit::<libc::winsize>::zeroed();
    // ioctl initializes winsize on success; stderr is borrowed, never closed here.
    if unsafe { libc::ioctl(libc::STDERR_FILENO, libc::TIOCGWINSZ, size.as_mut_ptr()) } == 0 {
        usize::from(unsafe { size.assume_init() }.ws_col)
    } else {
        0 // Unknown width: do not risk wrapping.
    }
}

fn status_line(frame: &Frame, columns: usize) -> String {
    let spinner = ["|", "/", "-", "\\"][frame.index % 4];
    let suffix = format!(
        " | {}s | {} completed calls",
        frame.seconds, frame.completed
    );
    let width = columns.saturating_sub(1);
    let mut label = frame.label.clone();
    if width > suffix.len() + 2 {
        label.truncate(width - suffix.len() - 2);
    }
    let mut text = format!("{spinner} {label}{suffix}");
    // Everything here is ASCII; leave the last cell unused to avoid auto-wrap.
    text.truncate(width);
    text
}

struct Renderer {
    enabled: bool,
    visible: bool,
    diagnostic_line_open: bool,
}

impl Renderer {
    fn new(quiet: bool) -> Self {
        Self {
            enabled: !quiet
                && io::stderr().is_terminal()
                && std::env::var_os("TERM").is_none_or(|term| term != "dumb"),
            visible: false,
            diagnostic_line_open: false,
        }
    }

    fn clear(&mut self) -> io::Result<()> {
        if self.visible {
            self.visible = false;
            let mut stderr = io::stderr().lock();
            stderr.write_all(b"\r\x1b[2K")?;
            stderr.flush()?;
        }
        Ok(())
    }

    fn diagnostic(&mut self, bytes: &[u8]) -> io::Result<()> {
        self.clear()?;
        let mut stderr = io::stderr().lock();
        stderr.write_all(bytes)?;
        stderr.flush()?;
        // Do not paint over a diagnostic which has not finished its line.
        if let Some(last) = bytes.last() {
            self.diagnostic_line_open = *last != b'\n';
        }
        Ok(())
    }

    fn output(&mut self, output: Output, cancelled: &AtomicBool) -> io::Result<bool> {
        match output {
            Output::Frame(frame) => {
                if self.enabled && !self.diagnostic_line_open {
                    let text = status_line(&frame, terminal_columns());
                    if !text.is_empty() || self.visible {
                        let mut stderr = io::stderr().lock();
                        write!(stderr, "\r\x1b[2K{text}")?;
                        stderr.flush()?;
                        self.visible = !text.is_empty();
                    }
                }
            }
            Output::Diagnostic(bytes) => self.diagnostic(&bytes)?,
            Output::Clear => {
                self.enabled = false;
                self.clear()?;
            }
            Output::Finish { text, diagnostic } => {
                self.clear()?;
                if !cancelled.load(Ordering::Acquire)
                    && let Some(message) = diagnostic
                {
                    self.diagnostic(format!("g: {message}\n").as_bytes())?;
                }
                if !cancelled.load(Ordering::Acquire)
                    && let Some(text) = text
                {
                    let result = {
                        let mut stdout = io::stdout().lock();
                        stdout
                            .write_all(text.as_bytes())
                            .and_then(|()| stdout.flush())
                    };
                    if let Err(error) = result {
                        let _ = self.diagnostic(b"g: could not write final response to stdout\n");
                        return Err(error);
                    }
                }
                return Ok(true);
            }
        }
        Ok(false)
    }
}

// One writer owns all terminal writes and final publication. A stalled inherited
// sink must not block signal handling/reaping, or change shared fd flags. At most
// one queued chunk, one pending chunk and one executing chunk exist (16 KiB each).
// Normal completion waits for acknowledgement; cancellation never joins a stalled
// writer. Process exit stops it after the owned Pi child has been cleaned up.
pub struct OutputWriter {
    sender: SyncSender<Output>,
    pending: Option<Output>,
    clear_requested: bool,
    finish_requested: Option<Output>,
    closing: bool,
    done: Arc<AtomicBool>,
    failed: Arc<AtomicBool>,
    cancelled: Arc<AtomicBool>,
    started: Instant,
    last_paint: Option<Instant>,
    frame: usize,
}

impl OutputWriter {
    pub fn new(quiet: bool) -> io::Result<Self> {
        let (sender, receiver) = mpsc::sync_channel(1);
        let done = Arc::new(AtomicBool::new(false));
        let failed = Arc::new(AtomicBool::new(false));
        let worker_done = done.clone();
        let worker_failed = failed.clone();
        let cancelled = Arc::new(AtomicBool::new(false));
        let worker_cancelled = cancelled.clone();
        std::thread::Builder::new()
            .name("genie-output".into())
            .spawn(move || {
                let mut renderer = Renderer::new(quiet);
                for output in receiver {
                    match renderer.output(output, &worker_cancelled) {
                        Ok(false) => {}
                        Ok(true) => break,
                        Err(_) => {
                            worker_failed.store(true, Ordering::Release);
                            break;
                        }
                    }
                }
                worker_done.store(true, Ordering::Release);
            })?;
        Ok(Self {
            sender,
            pending: None,
            clear_requested: false,
            finish_requested: None,
            closing: false,
            done,
            failed,
            cancelled,
            started: Instant::now(),
            last_paint: None,
            frame: 0,
        })
    }

    fn send(&mut self, output: Output) {
        match self.sender.try_send(output) {
            Ok(()) => {}
            Err(TrySendError::Full(output)) => self.pending = Some(output),
            Err(TrySendError::Disconnected(_)) => {}
        }
    }

    pub fn pump(&mut self) {
        if let Some(output) = self.pending.take() {
            self.send(output);
        }
        if self.pending.is_none() && self.clear_requested {
            self.clear_requested = false;
            self.send(Output::Clear);
        }
        if self.pending.is_none()
            && let Some(output) = self.finish_requested.take()
        {
            self.send(output);
        }
    }

    pub fn can_read_diagnostic(&self) -> bool {
        self.pending.is_none()
    }

    pub fn diagnostic(&mut self, bytes: &[u8]) {
        self.send(Output::Diagnostic(bytes.to_vec()));
    }

    pub fn paint(&mut self, activity: &Activity) {
        if self.closing
            || self.pending.is_some()
            || self
                .last_paint
                .is_some_and(|last| last.elapsed() < Duration::from_millis(100))
        {
            return;
        }
        let label = match activity.active.values().next() {
            Some(tool) => format!("Running {tool}"),
            None if activity.started => "Working".into(),
            None => "Starting Pi".into(),
        };
        // Frames are disposable under backpressure; diagnostic bytes are not.
        let _ = self.sender.try_send(Output::Frame(Frame {
            label,
            seconds: self.started.elapsed().as_secs(),
            completed: activity.completed,
            index: self.frame,
        }));
        self.frame = self.frame.wrapping_add(1);
        self.last_paint = Some(Instant::now());
    }

    pub fn stop(&mut self) {
        self.closing = true;
        self.clear_requested = true;
    }

    pub fn cancel(&mut self) {
        self.cancelled.store(true, Ordering::Release);
        self.stop();
    }

    pub fn finish(&mut self, text: Option<String>, diagnostic: Option<String>) {
        self.closing = true;
        self.finish_requested = Some(Output::Finish { text, diagnostic });
        self.pump();
    }

    pub fn done(&self) -> bool {
        self.done.load(Ordering::Acquire)
    }
    pub fn failed(&self) -> bool {
        self.failed.load(Ordering::Acquire)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lines_fit_narrow_and_resized_terminals() {
        let frame = Frame {
            label: "Starting Pi".into(),
            seconds: 123,
            completed: 0,
            index: 3,
        };
        assert!(status_line(&frame, 80).contains("Starting Pi"));
        for columns in [80, 24, 8, 2, 1, 0, 120] {
            let line = status_line(&frame, columns);
            assert!(line.is_ascii());
            assert!(line.len() <= columns.saturating_sub(1));
            assert!(!line.contains(['\n', '\r', '\x1b']));
        }
    }
}

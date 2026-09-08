use crate::activity::OutputWriter;
use crate::protocol::{Activity, JsonLines};
use signal_hook::consts::{SIGHUP, SIGINT, SIGKILL, SIGTERM};
use std::io::{self, Read, Write};
use std::os::fd::AsRawFd;
use std::os::unix::process::{CommandExt, ExitStatusExt};
use std::process::{Child, Command, Stdio};
use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::{Duration, Instant};

const CLEANUP_GRACE: Duration = Duration::from_secs(2);
const CLEANUP_DRAIN: Duration = Duration::from_millis(500);
const PIPE_IDLE: Duration = Duration::from_secs(2);

struct Signals {
    pending: Arc<AtomicUsize>,
    ids: Vec<signal_hook::SigId>,
    previous: Vec<(i32, libc::sigaction)>,
}

impl Signals {
    fn new() -> io::Result<Self> {
        let mut signals = Self {
            pending: Arc::new(AtomicUsize::new(0)),
            ids: Vec::new(),
            previous: Vec::new(),
        };
        for signal in [SIGINT, SIGTERM, SIGHUP] {
            let mut previous = std::mem::MaybeUninit::<libc::sigaction>::uninit();
            // Capture before registration, including inherited SIG_IGN. Keep it
            // even if registration fails so partial construction also restores it.
            if unsafe { libc::sigaction(signal, std::ptr::null(), previous.as_mut_ptr()) } != 0 {
                return Err(io::Error::last_os_error());
            }
            signals
                .previous
                .push((signal, unsafe { previous.assume_init() }));
            signals.ids.push(signal_hook::flag::register_usize(
                signal,
                signals.pending.clone(),
                signal as usize,
            )?);
        }
        Ok(signals)
    }
}

impl Drop for Signals {
    fn drop(&mut self) {
        // unregister alone leaves the registry handler installed and effectively
        // ignores these signals. Restore first, avoiding an unhandled interval.
        // Genie owns these registrations once per process; no later reuse occurs.
        for (signal, previous) in self.previous.iter().rev() {
            unsafe {
                libc::sigaction(*signal, previous, std::ptr::null_mut());
            }
        }
        for id in self.ids.drain(..) {
            signal_hook::low_level::unregister(id);
        }
        // An early launch/setup error may leave a cancellation flag unserviced.
        // Deliver it under the restored disposition, including inherited ignore.
        let pending = self.pending.swap(0, Ordering::SeqCst) as i32;
        if pending != 0 {
            unsafe {
                libc::raise(pending);
            }
        }
    }
}

struct OwnedChild {
    child: Child,
    reaped: bool,
}

impl OwnedChild {
    fn signal(&self, signal: i32, group: bool) {
        if !self.reaped {
            let pid = self.child.id() as i32;
            // process_group(0) gives this child its own group. Never signal our
            // foreground group. Reaped PIDs must not be reused as kill targets.
            unsafe {
                if group {
                    libc::kill(-pid, signal);
                }
                // Also target the unreaped direct child in case it changed groups.
                libc::kill(pid, signal);
            }
        }
    }
}

impl Drop for OwnedChild {
    fn drop(&mut self) {
        if !self.reaped {
            self.signal(SIGKILL, true);
            let _ = self.child.wait();
        }
    }
}

fn nonblocking(pipe: &impl AsRawFd) -> io::Result<()> {
    let fd = pipe.as_raw_fd();
    // These are private child pipe read ends, not inherited output descriptors.
    let flags = unsafe { libc::fcntl(fd, libc::F_GETFL) };
    if flags < 0 || unsafe { libc::fcntl(fd, libc::F_SETFL, flags | libc::O_NONBLOCK) } < 0 {
        return Err(io::Error::last_os_error());
    }
    Ok(())
}

pub fn run(prompt: &str, quiet: bool, selection: &crate::Selection) -> u8 {
    let signals = match Signals::new() {
        Ok(signals) => signals,
        Err(_) => {
            diagnostic("could not install cancellation handlers");
            return 1;
        }
    };
    // No system/session/trust flags. Omitted selections retain Pi defaults.
    let mut command = Command::new("pi");
    command.args(["--mode", "json"]);
    if let Some(model) = &selection.model {
        command.args(["--model", model]);
    }
    if let Some(thinking) = &selection.thinking {
        // Pi gives explicit --thinking precedence over a model :thinking suffix.
        command.args(["--thinking", thinking]);
    }
    let child = command
        .args(["--", prompt])
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .process_group(0)
        .spawn();
    let mut owned = match child {
        Ok(child) => OwnedChild {
            child,
            reaped: false,
        },
        Err(error) => {
            drop(signals);
            match error.kind() {
                io::ErrorKind::NotFound => diagnostic(
                    "could not find or start 'pi' on PATH; install Pi and authenticate it",
                ),
                io::ErrorKind::PermissionDenied => {
                    diagnostic("cannot execute 'pi'; check its executable permissions on PATH")
                }
                _ => diagnostic("could not execute 'pi'"),
            };
            return 1;
        }
    };
    let mut stdout = owned.child.stdout.take().expect("piped child stdout");
    let mut stderr = owned.child.stderr.take().expect("piped child stderr");
    if nonblocking(&stdout)
        .and_then(|()| nonblocking(&stderr))
        .is_err()
    {
        // Setup failed before any writer starts. Reap before reporting the error,
        // and restore normal signals so a blocked diagnostic remains cancellable.
        drop(owned);
        drop(signals);
        diagnostic("could not configure Pi output pipes");
        return 1;
    }
    let mut writer = match OutputWriter::new(quiet) {
        Ok(writer) => writer,
        Err(_) => {
            drop(owned);
            drop(signals);
            diagnostic("could not start output writer");
            return 1;
        }
    };
    let mut activity = Activity::default();
    let mut lines = JsonLines::default();
    let mut failure = None;
    writer.paint(&activity);
    let mut completion = None;
    let mut stdout_done = false;
    let mut stderr_done = false;
    let mut status = None;
    let mut last_data = Instant::now();
    let mut shutdown = None;
    let mut forced = false;
    let mut cancelled = None;
    let mut buffer = [0u8; 16384];

    loop {
        let signal = signals.pending.swap(0, Ordering::SeqCst) as i32;
        if signal != 0 {
            if cancelled.is_some() {
                owned.signal(SIGKILL, true);
                forced = true;
                shutdown = Some(Instant::now() - CLEANUP_GRACE);
            } else {
                cancelled = Some(signal);
                // Pi INT lacks detached-tool cleanup; TERM runs that handler.
                owned.signal(if signal == SIGINT { SIGTERM } else { signal }, false);
                shutdown = Some(Instant::now());
            }
            writer.cancel();
        }
        writer.pump();
        if writer.failed() {
            failure.get_or_insert("could not write output");
        }
        if status.is_none() {
            match owned.child.try_wait() {
                Ok(Some(exit)) => {
                    owned.reaped = true;
                    status = Some(exit);
                    last_data = Instant::now();
                }
                Ok(None) => {}
                Err(_) => {
                    failure.get_or_insert("could not wait for Pi");
                }
            }
        }
        if !stdout_done {
            match stdout.read(&mut buffer) {
                Ok(0) => {
                    stdout_done = true;
                    if failure.is_none()
                        && cancelled.is_none()
                        && let Err(error) = lines.eof(&mut activity)
                    {
                        failure = Some(error);
                    }
                }
                Ok(n) => {
                    last_data = Instant::now();
                    if failure.is_none()
                        && cancelled.is_none()
                        && let Err(error) = lines.push(&buffer[..n], &mut activity)
                    {
                        failure = Some(error);
                    }
                }
                Err(error)
                    if matches!(
                        error.kind(),
                        io::ErrorKind::WouldBlock | io::ErrorKind::Interrupted
                    ) => {}
                Err(_) => {
                    stdout_done = true;
                    failure.get_or_insert("could not read Pi JSON stream");
                }
            }
        }
        if !stderr_done && writer.can_read_diagnostic() {
            match stderr.read(&mut buffer) {
                Ok(0) => stderr_done = true,
                Ok(n) => {
                    last_data = Instant::now();
                    if !writer.failed() {
                        writer.diagnostic(&buffer[..n]);
                    }
                }
                Err(error)
                    if matches!(
                        error.kind(),
                        io::ErrorKind::WouldBlock | io::ErrorKind::Interrupted
                    ) => {}
                Err(_) => {
                    stderr_done = true;
                    failure.get_or_insert("could not read Pi stderr");
                }
            }
        }
        if failure.is_none() && cancelled.is_none() {
            writer.paint(&activity);
        }
        if failure.is_some() && shutdown.is_none() {
            writer.stop();
            owned.signal(SIGTERM, false);
            shutdown = Some(Instant::now());
        }
        if let Some(start) = shutdown {
            if !forced && start.elapsed() >= CLEANUP_GRACE {
                owned.signal(SIGKILL, true);
                forced = true;
            }
            if start.elapsed() >= CLEANUP_GRACE + CLEANUP_DRAIN {
                // Close retained pipe ends rather than waiting for untracked
                // descendants forever. Drop reaps the owned child if necessary.
                break;
            }
        }
        if status.is_some()
            && (!stdout_done || !stderr_done)
            && writer.can_read_diagnostic()
            && last_data.elapsed() >= PIPE_IDLE
        {
            failure.get_or_insert("Pi output pipes stayed open after exit");
            stdout_done = true;
            stderr_done = true;
        }
        if let Some(exit) = status
            && stdout_done
            && stderr_done
            && completion.is_none()
        {
            let mut code =
                exit.code()
                    .unwrap_or_else(|| 128 + exit.signal().unwrap_or(1)) as u8;
            let mut text = None;
            let mut message = failure.map(str::to_owned);
            if cancelled.is_none() && exit.success() {
                if failure.is_some() {
                    code = 1;
                } else {
                    match activity.finish() {
                        Ok(final_message) => {
                            text = Some(final_message.text.clone());
                            if final_message.truncated {
                                message = Some("Pi response was truncated (length limit)".into());
                            }
                        }
                        Err(error) => {
                            code = 1;
                            message = Some(error.to_owned());
                        }
                    }
                }
            }
            completion = Some(code);
            writer.finish(text, message);
        }
        if completion.is_some() && writer.done() {
            break;
        }
        let mut polls = [
            libc::pollfd {
                fd: if stdout_done { -1 } else { stdout.as_raw_fd() },
                events: libc::POLLIN,
                revents: 0,
            },
            libc::pollfd {
                fd: if stderr_done || !writer.can_read_diagnostic() {
                    -1
                } else {
                    stderr.as_raw_fd()
                },
                events: libc::POLLIN,
                revents: 0,
            },
        ];
        // Bounded wakeups also service signals, animation, reaping and deadlines.
        if unsafe { libc::poll(polls.as_mut_ptr(), polls.len() as libc::nfds_t, 20) } < 0
            && io::Error::last_os_error().kind() != io::ErrorKind::Interrupted
        {
            failure.get_or_insert("could not poll Pi output pipes");
        }
    }
    if let Some(signal) = cancelled {
        return (128 + signal) as u8;
    }
    let code = completion
        .or_else(|| {
            status.map(|exit| {
                exit.code()
                    .unwrap_or_else(|| 128 + exit.signal().unwrap_or(1)) as u8
            })
        })
        .unwrap_or(1);
    if code == 0 && (failure.is_some() || !writer.done() || writer.failed()) {
        1
    } else {
        code
    }
}

pub fn diagnostic(message: &str) -> bool {
    writeln!(io::stderr().lock(), "g: {message}").is_ok()
}

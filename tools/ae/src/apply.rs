//! Execute an approved plan, reporting progress as events.
//!
//! Every step re-checks the filesystem first, so a path that changed after the
//! plan was shown is skipped rather than overwritten.

use crate::paths::{Roots, link_target, occupied};
use crate::plan::{Op, Plan};
use crate::state::Existing;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc;
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

#[derive(Clone, Debug)]
pub enum Outcome {
    Done(Option<String>),
    Skipped(String),
    Failed(String),
}

impl Outcome {
    pub fn is_failure(&self) -> bool {
        matches!(self, Outcome::Failed(_))
    }
}

#[derive(Clone, Debug)]
pub enum Event {
    Started(usize),
    /// Fraction complete when known, plus a short status line.
    Progress(usize, Option<f64>, String),
    Finished(usize, Outcome, Duration),
    /// Steps not run because the user cancelled.
    Cancelled(Vec<usize>),
}

pub struct Context {
    pub roots: Roots,
    pub log_dir: PathBuf,
}

/// Run `plan` in order, calling `emit` for every event. Returns per-step outcomes.
pub fn run(plan: &Plan, context: &Context, cancel: &Arc<AtomicBool>, mut emit: impl FnMut(Event)) {
    let order = plan.apply_order();
    for (position, &index) in order.iter().enumerate() {
        if cancel.load(Ordering::SeqCst) {
            emit(Event::Cancelled(order[position..].to_vec()));
            return;
        }
        emit(Event::Started(index));
        let started = Instant::now();
        let outcome = match &plan.steps[index].op {
            Op::Link { source, dest } => link(source, dest, context, None),
            Op::Replace { source, dest, existing } => link(source, dest, context, Some(existing)),
            Op::Relink { source, dest, .. } => relink(source, dest, &context.roots),
            Op::Unlink { dest, .. } => unlink(dest, &context.roots),
            Op::Subagents { script, agent_dir, .. } => subagents(script, agent_dir),
            Op::CargoInstall { dir, locked, packages, .. } => {
                let name = &plan.steps[index].name;
                cargo_install(dir, *locked, *packages, name, context, cancel, &mut |fraction, line| {
                    emit(Event::Progress(index, fraction, line))
                })
            }
        };
        emit(Event::Finished(index, outcome, started.elapsed()));
    }
}

fn link(source: &Path, dest: &Path, context: &Context, replacing: Option<&Existing>) -> Outcome {
    if !occupied(source) {
        return Outcome::Failed(format!("source is missing: {}", source.display()));
    }
    if let Some(parent) = dest.parent()
        && let Err(error) = std::fs::create_dir_all(parent)
    {
        return Outcome::Failed(format!("could not create {}: {error}", parent.display()));
    }
    let current = link_target(dest);
    if current.as_deref().is_some_and(|target| context.roots.to_canonical(target) == context.roots.to_canonical(source)) {
        return Outcome::Skipped("already linked".into());
    }
    let mut detail = None;
    match (replacing, occupied(dest)) {
        (_, false) => {}
        (None, true) => return Outcome::Skipped("something appeared here after the plan was made; left untouched".into()),
        (Some(expected), true) => {
            let now = describe(dest);
            if now != *expected {
                return Outcome::Skipped("changed after the plan was made; left untouched".into());
            }
            match expected {
                Existing::Symlink(_) => {
                    // Remove the conflicting link itself; its target is untouched.
                    if let Err(error) = std::fs::remove_file(dest) {
                        return Outcome::Failed(format!("could not remove the existing link: {error}"));
                    }
                    detail = Some("replaced the existing link".to_string());
                }
                Existing::File | Existing::Directory => {
                    let backup = backup_path(dest);
                    if let Err(error) = std::fs::rename(dest, &backup) {
                        return Outcome::Failed(format!("could not back up: {error}"));
                    }
                    detail = Some(format!("backed up to {}", backup.display()));
                }
            }
        }
    }
    let _ = &context.log_dir;
    match std::os::unix::fs::symlink(source, dest) {
        Ok(()) => Outcome::Done(detail),
        Err(error) => Outcome::Failed(format!("could not link: {error}")),
    }
}

fn describe(path: &Path) -> Existing {
    if let Some(target) = link_target(path) {
        return Existing::Symlink(target);
    }
    if path.is_dir() { Existing::Directory } else { Existing::File }
}

fn relink(source: &Path, dest: &Path, roots: &Roots) -> Outcome {
    match link_target(dest) {
        Some(target) if roots.contains(&target) => {
            if let Err(error) = std::fs::remove_file(dest) {
                return Outcome::Failed(format!("could not remove the old link: {error}"));
            }
            match std::os::unix::fs::symlink(source, dest) {
                Ok(()) => Outcome::Done(None),
                Err(error) => Outcome::Failed(format!("could not link: {error}")),
            }
        }
        _ => Outcome::Skipped("no longer a link into this checkout; left untouched".into()),
    }
}

fn unlink(dest: &Path, roots: &Roots) -> Outcome {
    match link_target(dest) {
        Some(target) if roots.contains(&target) => match std::fs::remove_file(dest) {
            Ok(()) => Outcome::Done(None),
            Err(error) => Outcome::Failed(format!("could not remove: {error}")),
        },
        Some(_) => Outcome::Skipped("now points outside this checkout; left untouched".into()),
        None if occupied(dest) => Outcome::Skipped("no longer a link; left untouched".into()),
        None => Outcome::Skipped("already gone".into()),
    }
}

fn subagents(script: &Path, agent_dir: &Path) -> Outcome {
    let output = Command::new("python3").arg(script).arg("--agent-dir").arg(agent_dir).arg("--apply").stdin(Stdio::null()).output();
    match output {
        Ok(output) if output.status.success() => {
            let text = String::from_utf8_lossy(&output.stdout);
            let detail: Vec<&str> = text.lines().filter(|line| line.starts_with("Backed up")).collect();
            Outcome::Done((!detail.is_empty()).then(|| detail.join("; ")))
        }
        Ok(output) => {
            let text = String::from_utf8_lossy(&output.stderr).trim().to_string();
            Outcome::Failed(if text.is_empty() { "install.py --apply failed".into() } else { text })
        }
        Err(error) => Outcome::Failed(format!("could not run python3: {error}")),
    }
}

fn cargo_install(
    dir: &Path,
    locked: bool,
    packages: usize,
    name: &str,
    context: &Context,
    cancel: &Arc<AtomicBool>,
    progress: &mut dyn FnMut(Option<f64>, String),
) -> Outcome {
    let mut command = Command::new("cargo");
    command.arg("install").arg("--path").arg(dir).arg("--force");
    if locked {
        command.arg("--locked");
    }
    command.env("CARGO_TERM_COLOR", "never").env("CARGO_TERM_PROGRESS_WHEN", "never");
    command.stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::piped());
    let mut child = match command.spawn() {
        Ok(child) => child,
        Err(error) => return Outcome::Failed(format!("could not run cargo: {error}")),
    };
    let _ = std::fs::create_dir_all(&context.log_dir);
    let log_path = context.log_dir.join(format!("{name}-{}.log", timestamp()));
    let mut log = std::fs::File::create(&log_path).ok();

    let (tx, rx) = mpsc::channel::<String>();
    for stream in [
        child.stdout.take().map(|s| Box::new(s) as Box<dyn std::io::Read + Send>),
        child.stderr.take().map(|s| Box::new(s) as Box<dyn std::io::Read + Send>),
    ]
    .into_iter()
    .flatten()
    {
        let tx = tx.clone();
        thread::spawn(move || {
            for line in BufReader::new(stream).lines().map_while(Result::ok) {
                if tx.send(line).is_err() {
                    break;
                }
            }
        });
    }
    drop(tx);

    let mut compiled = 0usize;
    let mut last_error: Option<String> = None;
    progress(Some(0.0), "Resolving dependencies".into());
    loop {
        match rx.recv_timeout(Duration::from_millis(100)) {
            Ok(line) => {
                if let Some(log) = log.as_mut() {
                    let _ = writeln!(log, "{line}");
                }
                let trimmed = line.trim();
                if trimmed.starts_with("Compiling") {
                    compiled += 1;
                }
                if trimmed.starts_with("error") {
                    last_error.get_or_insert_with(|| trimmed.to_string());
                }
                if ["Compiling", "Updating", "Downloading", "Downloaded", "Finished", "Installing", "Replacing", "Locking"]
                    .iter()
                    .any(|word| trimmed.starts_with(word))
                {
                    let fraction = if packages > 0 { Some((compiled as f64 / packages as f64).min(0.99)) } else { None };
                    progress(fraction, trimmed.to_string());
                }
            }
            Err(mpsc::RecvTimeoutError::Timeout) => {
                if cancel.load(Ordering::SeqCst) {
                    let _ = child.kill();
                }
            }
            Err(mpsc::RecvTimeoutError::Disconnected) => break,
        }
    }
    let status = child.wait();
    let log_note = format!("log: {}", log_path.display());
    match status {
        Ok(status) if status.success() => {
            progress(Some(1.0), "Installed".into());
            Outcome::Done(None)
        }
        _ if cancel.load(Ordering::SeqCst) => Outcome::Skipped("cancelled; the previous binary is unchanged".into()),
        Ok(status) => Outcome::Failed(format!(
            "{} (exit {}); {log_note}",
            last_error.unwrap_or_else(|| "cargo install failed".into()),
            status.code().map(|c| c.to_string()).unwrap_or_else(|| "signal".into())
        )),
        Err(error) => Outcome::Failed(format!("cargo did not finish: {error}; {log_note}")),
    }
}

fn backup_path(dest: &Path) -> PathBuf {
    let name = dest.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default();
    let candidate = dest.with_file_name(format!("{name}.backup.{}", timestamp()));
    if occupied(&candidate) {
        return dest.with_file_name(format!("{name}.backup.{}.{}", timestamp(), std::process::id()));
    }
    candidate
}

/// UTC `YYYYmmddHHMMSS`, without a date library.
pub fn timestamp() -> String {
    let secs = SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs() as i64).unwrap_or(0);
    let (days, rest) = (secs.div_euclid(86_400), secs.rem_euclid(86_400));
    // Howard Hinnant's civil-from-days.
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let day = doy - (153 * mp + 2) / 5 + 1;
    let month = if mp < 10 { mp + 3 } else { mp - 9 };
    let year = yoe + era * 400 + i64::from(month <= 2);
    format!("{year:04}{month:02}{day:02}{:02}{:02}{:02}", rest / 3600, rest % 3600 / 60, rest % 60)
}

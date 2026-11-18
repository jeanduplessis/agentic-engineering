//! Plain-terminal rendering for status, plans, and results.

use crate::apply::Outcome;
use crate::doctor::{Issue, Level, Probe, join};
use crate::plan::{Op, Plan, Reason, Section};
use crate::repo::PiKind;
use crate::state::{Entry, Snapshot, SubagentState};
use std::collections::BTreeMap;
use std::time::Duration;

#[derive(Clone, Copy)]
pub struct Paint {
    pub color: bool,
}

macro_rules! style {
    ($name:ident, $code:expr) => {
        pub fn $name(&self, text: impl AsRef<str>) -> String {
            self.wrap($code, text.as_ref())
        }
    };
}

impl Paint {
    fn wrap(&self, code: &str, text: &str) -> String {
        if self.color && !text.is_empty() { format!("\x1b[{code}m{text}\x1b[0m") } else { text.to_string() }
    }
    style!(bold, "1");
    style!(dim, "2");
    style!(green, "32");
    style!(red, "31");
    style!(yellow, "33");
    style!(cyan, "36");
    style!(accent, "1;35");
}

pub const GLYPH_ON: &str = "●";
pub const GLYPH_OFF: &str = "·";
pub const GLYPH_FOREIGN: &str = "◆";

fn terminal_width() -> usize {
    use std::io::IsTerminal;
    if std::io::stdout().is_terminal()
        && let Ok((columns, _)) = ratatui::crossterm::terminal::size()
    {
        return columns as usize;
    }
    std::env::var("COLUMNS").ok().and_then(|c| c.parse().ok()).unwrap_or(100)
}

fn pad(text: &str, width: usize) -> String {
    let len = text.chars().count();
    if len >= width { text.to_string() } else { format!("{text}{}", " ".repeat(width - len)) }
}

pub fn header(snap: &Snapshot, paint: Paint) -> String {
    let mut out = format!("{}  {}  {}\n", paint.accent("Æ"), paint.bold("Agentic Engineering"), paint.dim(snap.env.tilde(&snap.repo.root)));
    if let Some(orchestrator) = &snap.env.orchestrator {
        let version = orchestrator.version.as_deref().map(|v| format!(" {v}")).unwrap_or_default();
        out.push_str(&format!(
            "   {}\n",
            paint.dim(format!(
                "{}{version} orchestrates · harness names from {}",
                orchestrator.name,
                snap.env.tilde(&orchestrator.settings)
            ))
        ));
    }
    out
}

pub fn status(snap: &Snapshot, issues: &[Issue], paint: Paint) -> String {
    let env = &snap.env;
    let mut out = header(snap, paint);
    out.push('\n');
    out.push_str(&format!("{}\n", paint.bold("Harnesses")));
    let name_width = env.harnesses.iter().map(|h| h.name.chars().count()).max().unwrap_or(4) + 2;
    for (h, harness) in env.harnesses.iter().enumerate() {
        let mut note = Vec::new();
        if harness.disabled {
            note.push("off in T3 Code".to_string());
        }
        let shared_by: Vec<String> = snap
            .locations
            .iter()
            .filter(|l| l.path == *harness.own_skills() && l.readers.len() > 1)
            .flat_map(|l| l.readers.iter().filter(|&&r| r != h).map(|&r| env.harnesses[r].name.clone()))
            .collect();
        if !shared_by.is_empty() {
            note.push(format!("its skills also load in {}", join(&shared_by)));
        }
        let line = format!(
            "  {} {}{}{}{}",
            pad(&harness.label, 4),
            pad(&harness.name, name_width),
            pad(harness.version.as_deref().unwrap_or(if harness.detected { "found" } else { "" }), 12),
            pad(&env.tilde(&harness.home), 22),
            note.join(" · ")
        );
        if harness.detected {
            out.push_str(&format!("{}\n", line.trim_end()));
        } else {
            out.push_str(&format!("{}\n", paint.dim(format!("{}  not found", line.trim_end()))));
        }
    }
    if let Some(shared) = snap.locations.iter().find(|l| l.path == env.shared_skills) {
        let names: Vec<String> = shared.readers.iter().map(|&h| env.harnesses[h].name.clone()).collect();
        if !names.is_empty() {
            out.push_str(&format!("       {}\n", paint.dim(format!("{} is shared by {}", env.tilde(&shared.path), join(&names)))));
        }
    }

    out.push('\n');
    let columns: Vec<usize> = snap.active.iter().copied().collect();
    let skill_width = snap.repo.skills.iter().map(|s| s.name.chars().count()).max().unwrap_or(5).max(6) + 2;
    let tag_width = 11;
    let mut heading = format!("{}{}", pad("Skills", skill_width + 2), " ".repeat(tag_width));
    for &h in &columns {
        heading.push_str(&pad(&env.harnesses[h].label, 4));
    }
    out.push_str(&format!("{}\n", paint.bold(heading.trim_end())));
    if snap.repo.skills.is_empty() {
        out.push_str(&format!("  {}\n", paint.dim("No skills in this checkout.")));
    }
    for (s, skill) in snap.repo.skills.iter().enumerate() {
        let visible = snap.visible(s);
        let foreign = snap.foreign(s);
        let mut row = format!("  {}{}", pad(&skill.name, skill_width), paint.dim(pad(&skill.tags.join(" "), tag_width)));
        for &h in &columns {
            let cell = if visible.contains(&h) {
                paint.green(GLYPH_ON)
            } else if foreign.contains(&h) {
                paint.yellow(GLYPH_FOREIGN)
            } else {
                paint.dim(GLYPH_OFF)
            };
            row.push_str(&cell);
            row.push_str("   ");
        }
        out.push_str(&format!("{}\n", row.trim_end()));
    }
    if !columns.is_empty() && !snap.repo.skills.is_empty() {
        out.push_str(&format!(
            "  {}\n",
            paint.dim(format!("{GLYPH_ON} from this checkout   {GLYPH_FOREIGN} a different copy   {GLYPH_OFF} not installed"))
        ));
    }

    if !snap.repo.claude.is_empty() && !snap.claude_homes.is_empty() {
        out.push('\n');
        out.push_str(&format!("{}\n", paint.bold("Claude Code")));
        let id_width = snap.repo.claude.iter().map(|c| c.id.chars().count()).max().unwrap_or(4) + 2;
        let name_width = snap.claude_homes.iter().map(|&h| env.harnesses[h].name.chars().count()).max().unwrap_or(4) + 2;
        for (i, item) in snap.repo.claude.iter().enumerate() {
            for (k, &h) in snap.claude_homes.iter().enumerate() {
                let state = match &snap.claude[i][k] {
                    Entry::Linked if item.style.is_none() || snap.style_active(i, k) => format!("{} linked", paint.green(GLYPH_ON)),
                    Entry::Linked => format!("{} linked, not selected in settings.json", paint.green(GLYPH_ON)),
                    Entry::Foreign { what } => format!("{} {} is in the way", paint.yellow(GLYPH_FOREIGN), what.describe()),
                    _ => format!("{} not linked", paint.dim(GLYPH_OFF)),
                };
                let id = if k == 0 { item.id.as_str() } else { "" };
                out.push_str(&format!("  {}{}{state}\n", pad(id, id_width), pad(&env.harnesses[h].name, name_width)));
            }
        }
    }

    if let Some(pi_dir) = &snap.pi_dir
        && !snap.repo.pi.is_empty()
    {
        out.push('\n');
        out.push_str(&format!("{}  {}\n", paint.bold("Pi"), paint.dim(env.tilde(pi_dir))));
        let mut groups: BTreeMap<&str, Vec<(String, usize)>> = BTreeMap::new();
        for (i, item) in snap.repo.pi.iter().enumerate() {
            let installed = match item.kind {
                PiKind::Subagents => snap.subagents.as_ref().map(|s| s.state == SubagentState::Installed),
                _ => Some(snap.pi[i] == Entry::Linked),
            };
            let short = item.id.rsplit_once('/').map(|(_, name)| name).unwrap_or(&item.id).to_string();
            let glyph = match (installed, &snap.pi[i]) {
                (Some(true), _) => paint.green(GLYPH_ON),
                (_, Entry::Foreign { .. }) => paint.yellow(GLYPH_FOREIGN),
                _ => paint.dim(GLYPH_OFF),
            };
            let width = short.chars().count() + 2;
            groups.entry(item.kind.group()).or_default().push((format!("{glyph} {short}"), width));
        }
        let limit = terminal_width().saturating_sub(2).max(40);
        for (group, items) in groups {
            let mut line = format!("  {}", pad(group, 13));
            let mut used = 15;
            for (index, (text, width)) in items.iter().enumerate() {
                if index > 0 && used + 2 + width > limit {
                    out.push_str(&format!("{line}\n"));
                    line = " ".repeat(15);
                    used = 15;
                } else if index > 0 {
                    line.push_str("  ");
                    used += 2;
                }
                line.push_str(text);
                used += width;
            }
            out.push_str(&format!("{line}\n"));
        }
    }

    if !snap.repo.tools.is_empty() {
        out.push('\n');
        out.push_str(&format!("{}\n", paint.bold("Tools")));
        let width = snap.repo.tools.iter().map(|t| t.name.chars().count()).max().unwrap_or(4) + 2;
        for (t, tool) in snap.repo.tools.iter().enumerate() {
            let version = tool.version.clone().unwrap_or_default();
            let state = match &snap.tools[t] {
                Some(installed) if installed.from_this_checkout && installed.version == version => {
                    format!("{} installed", paint.green(GLYPH_ON))
                }
                Some(installed) if installed.from_this_checkout => {
                    format!("{} {} installed, update available", paint.yellow("◐"), installed.version)
                }
                Some(installed) => format!("{} {} installed from {}", paint.yellow(GLYPH_FOREIGN), installed.version, installed.source),
                None => format!("{} not installed", paint.dim(GLYPH_OFF)),
            };
            let bins = if tool.bins == [tool.name.clone()] { String::new() } else { format!("  ({})", tool.bins.join(", ")) };
            out.push_str(&format!("  {}{}{state}{}\n", pad(&tool.name, width), pad(&version, 10), paint.dim(bins)));
        }
    }

    out.push('\n');
    out.push_str(&issues_text(issues, paint));
    out
}

pub fn issues_text(issues: &[Issue], paint: Paint) -> String {
    if issues.is_empty() {
        return format!("{} {}\n", paint.green("✓"), "No problems found.");
    }
    let mut out = format!("{}\n", paint.bold("Problems"));
    for issue in issues {
        let mark = match issue.level {
            Level::Warning => paint.yellow("!"),
            Level::Info => paint.cyan("i"),
        };
        let fix = issue.fix.as_ref().map(|fix| format!("  {}", paint.dim(format!("→ {fix}")))).unwrap_or_default();
        out.push_str(&format!("  {mark} {}{fix}\n", issue.message));
    }
    out
}

pub fn probes_text(probes: &[Probe], paint: Paint) -> String {
    let mut out = String::new();
    for probe in probes {
        match (&probe.loaded, &probe.error) {
            (Some(loaded), _) if probe.mismatches.is_empty() => out.push_str(&format!(
                "  {} {} loads what Æ expects ({} skills, checked with `{}`)\n",
                paint.green("✓"),
                probe.harness,
                loaded.len(),
                probe.command
            )),
            (Some(_), _) => {
                for mismatch in &probe.mismatches {
                    out.push_str(&format!("  {} {mismatch}\n", paint.red("✗")));
                }
            }
            (None, error) => {
                out.push_str(&format!("  {} could not ask {}: {}\n", paint.yellow("!"), probe.harness, error.clone().unwrap_or_default()))
            }
        }
    }
    out
}

pub fn op_glyph(op: &Op) -> &'static str {
    match op {
        Op::Link { .. } => "+",
        Op::Replace { .. } => "!",
        Op::Relink { .. } => "~",
        Op::Unlink { .. } => "−",
        Op::Subagents { .. } => "⇄",
        Op::CargoInstall { from: Some(_), .. } => "↻",
        Op::CargoInstall { .. } => "+",
    }
}

pub fn describe_step(snap: &Snapshot, op: &Op) -> String {
    let env = &snap.env;
    match op {
        Op::Link { dest, .. } => format!("link {}", env.tilde(dest)),
        Op::Replace { dest, existing, .. } => format!(
            "{} is {}; {}",
            env.tilde(dest),
            existing.describe(),
            match existing {
                crate::state::Existing::Symlink(_) => "the link will be replaced",
                _ => "it will be backed up, then linked",
            }
        ),
        Op::Relink { dest, previous, .. } => format!("repoint {} (was {})", env.tilde(dest), env.tilde(previous)),
        Op::Unlink { dest, reason } => format!(
            "remove {}{}",
            env.tilde(dest),
            match reason {
                Reason::Deselected => "",
                Reason::Stale => " (its source is gone)",
                Reason::Redundant => " (already loaded from another folder)",
            }
        ),
        Op::Subagents { agent_dir, .. } => format!("merge reviewer and model policy into {}", env.tilde(agent_dir)),
        Op::CargoInstall { dir, locked, from, to, .. } => {
            let change = match (from, to) {
                (Some(from), Some(to)) if from != to => format!("{from} → {to}, "),
                (Some(_), _) => "reinstall, ".into(),
                _ => String::new(),
            };
            format!("{change}cargo install --path {} --force{}", env.tilde(dir), if *locked { " --locked" } else { "" })
        }
    }
}

pub fn plan_text(snap: &Snapshot, plan: &Plan, paint: Paint) -> String {
    let mut out = String::new();
    for section in [Section::Skills, Section::Claude, Section::Pi, Section::Tools, Section::Tidy] {
        let steps: Vec<_> = plan.steps.iter().filter(|step| step.section == section).collect();
        if steps.is_empty() {
            continue;
        }
        out.push_str(&format!("{}\n", paint.bold(section.title())));
        for step in steps {
            let glyph = op_glyph(&step.op);
            let glyph = match &step.op {
                Op::Unlink { .. } => paint.red(glyph),
                Op::Replace { .. } => paint.yellow(glyph),
                _ => paint.green(glyph),
            };
            let readers = if step.readers.is_empty() || section == Section::Pi {
                String::new()
            } else {
                format!("  {}", paint.cyan(step.readers.join(" · ")))
            };
            let skipped = if step.needs_approval && !step.approved { paint.yellow("  [skipped unless approved]") } else { String::new() };
            out.push_str(&format!("  {glyph} {}{readers}{skipped}\n", paint.bold(&step.name)));
            out.push_str(&format!("      {}\n", paint.dim(describe_step(snap, &step.op))));
            if let Op::Subagents { preview, .. } = &step.op {
                for line in preview {
                    out.push_str(&format!("      {}\n", paint.dim(line)));
                }
            }
        }
    }
    out
}

pub fn summary_line(plan: &Plan, paint: Paint) -> String {
    let approved = plan.approved_count();
    let pending = plan.pending_conflicts();
    let mut parts = vec![format!("{approved} change{}", if approved == 1 { "" } else { "s" })];
    if pending > 0 {
        parts.push(paint.yellow(format!("{pending} conflict{} skipped", if pending == 1 { "" } else { "s" })));
    }
    parts.join(" · ")
}

pub fn outcome_line(snap: &Snapshot, plan: &Plan, index: usize, outcome: &Outcome, elapsed: Duration, paint: Paint) -> String {
    let step = &plan.steps[index];
    let what = describe_step(snap, &step.op);
    let time = if elapsed >= Duration::from_secs(1) { paint.dim(format!("  {:.1}s", elapsed.as_secs_f64())) } else { String::new() };
    match outcome {
        Outcome::Done(detail) => format!(
            "  {} {}  {}{}{time}",
            paint.green("✓"),
            paint.bold(&step.name),
            paint.dim(&what),
            detail.as_ref().map(|d| format!(" · {d}")).unwrap_or_default()
        ),
        Outcome::Skipped(why) => format!("  {} {}  {}", paint.yellow("–"), paint.bold(&step.name), paint.dim(why)),
        Outcome::Failed(why) => format!("  {} {}  {}", paint.red("✗"), paint.bold(&step.name), paint.red(why)),
    }
}

/// Which harnesses need a restart to pick up changes.
pub fn restart_hint(plan: &Plan) -> Option<String> {
    let mut names: Vec<String> = Vec::new();
    for (_, step) in plan.approved() {
        if matches!(step.section, Section::Skills | Section::Claude | Section::Pi | Section::Tidy) {
            for reader in &step.readers {
                if !names.contains(reader) {
                    names.push(reader.clone());
                }
            }
        }
    }
    (!names.is_empty()).then(|| format!("Start a new session in {} (or a new T3 Code thread) to load the changes.", join(&names)))
}

/// How to turn on each output style the plan links but settings.json does not
/// select. Æ never edits settings.json itself.
pub fn activation_hints(snap: &Snapshot, plan: &Plan) -> Vec<String> {
    let mut out = Vec::new();
    for (_, step) in plan.approved() {
        let (Op::Link { dest, .. } | Op::Replace { dest, .. } | Op::Relink { dest, .. }) = &step.op else { continue };
        if step.section != Section::Claude {
            continue;
        }
        let Some(i) = snap.repo.claude.iter().position(|item| item.id == step.name) else { continue };
        let Some(style) = &snap.repo.claude[i].style else { continue };
        for (k, &h) in snap.claude_homes.iter().enumerate() {
            let harness = &snap.env.harnesses[h];
            if *dest == harness.home.join(&snap.repo.claude[i].target) && !snap.style_active(i, k) {
                out.push(style_hint(snap, h, style));
            }
        }
    }
    out
}

pub fn style_hint(snap: &Snapshot, h: usize, style: &str) -> String {
    let harness = &snap.env.harnesses[h];
    format!("To use it in {}, set \"outputStyle\": \"{style}\" in {}.", harness.name, snap.env.tilde(&harness.home.join("settings.json")))
}

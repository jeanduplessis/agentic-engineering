//! The interactive installer: browse → review → apply → done.

mod theme;
mod view;

use crate::apply::{self, Event as ApplyEvent, Outcome};
use crate::doctor::{self, Issue};
use crate::harness::Environment;
use crate::output::{self, Paint};
use crate::plan::{self, Desired, Options, Plan};
use crate::repo::PiKind;
use crate::state::{Entry, Snapshot, SubagentState};
use anyhow::Result;
use ratatui::crossterm::event::{self, Event, KeyCode, KeyEvent, KeyEventKind, KeyModifiers};
use std::collections::{BTreeMap, BTreeSet};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{self, Receiver};
use std::thread;
use std::time::{Duration, Instant};
pub use theme::Theme;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Tab {
    Skills,
    Pi,
    Tools,
}

impl Tab {
    const ALL: [Tab; 3] = [Tab::Skills, Tab::Pi, Tab::Tools];
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Screen {
    Browse,
    Review,
    Applying,
    Done,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Tone {
    Info,
    Warn,
    Good,
}

#[derive(Clone, Debug)]
pub enum StepStatus {
    Pending,
    Running { started: Instant, fraction: Option<f64>, line: String },
    Finished { outcome: Outcome, elapsed: Duration },
    NotRun,
}

pub struct Applying {
    pub statuses: Vec<StepStatus>,
    pub order: Vec<usize>,
    pub started: Instant,
    pub finished: Option<Duration>,
    pub cancel: Arc<AtomicBool>,
    rx: Receiver<ApplyEvent>,
}

pub struct App {
    pub snap: Snapshot,
    pub issues: Vec<Issue>,
    pub theme: Theme,
    pub tab: Tab,
    pub screen: Screen,
    pub columns: Vec<usize>,
    pub row: usize,
    pub col: usize,
    pub filter: String,
    pub filtering: bool,
    pub skills: BTreeMap<usize, BTreeSet<usize>>,
    pub pi_row: usize,
    pub pi: BTreeMap<usize, bool>,
    pub subagents: bool,
    pub tool_row: usize,
    pub tools: BTreeSet<usize>,
    pub prune: bool,
    pub message: Option<(String, Tone)>,
    pub plan: Plan,
    pub plan_row: usize,
    pub applying: Option<Applying>,
    pub help: bool,
    pub confirm_quit: bool,
    pub tick: usize,
    pub probing: bool,
    pub log: Vec<String>,
    pub quit: bool,
    versions: Option<Receiver<Environment>>,
}

impl App {
    pub fn new(snap: Snapshot, theme: Theme) -> App {
        let issues = doctor::issues(&snap);
        let columns = snap.active.iter().copied().collect();
        App {
            snap,
            issues,
            theme,
            tab: Tab::Skills,
            screen: Screen::Browse,
            columns,
            row: 0,
            col: 0,
            filter: String::new(),
            filtering: false,
            skills: BTreeMap::new(),
            pi_row: 0,
            pi: BTreeMap::new(),
            subagents: false,
            tool_row: 0,
            tools: BTreeSet::new(),
            prune: false,
            message: None,
            plan: Plan::default(),
            plan_row: 0,
            applying: None,
            help: false,
            confirm_quit: false,
            tick: 0,
            probing: false,
            log: Vec::new(),
            quit: false,
            versions: None,
        }
    }

    /// Fill in harness versions in the background so the first frame is instant.
    pub fn probe_versions(&mut self) {
        let mut env = self.snap.env.clone();
        let (tx, rx) = mpsc::channel();
        thread::spawn(move || {
            env.probe_versions(Duration::from_secs(3));
            let _ = tx.send(env);
        });
        self.versions = Some(rx);
        self.probing = true;
    }

    /// Skill rows matching the filter.
    pub fn rows(&self) -> Vec<usize> {
        let needle = self.filter.to_lowercase();
        (0..self.snap.repo.skills.len())
            .filter(|&s| {
                let skill = &self.snap.repo.skills[s];
                needle.is_empty() || skill.name.to_lowercase().contains(&needle) || skill.description.to_lowercase().contains(&needle)
            })
            .collect()
    }

    /// The harnesses that will load skill `s` after applying.
    pub fn wanted(&self, s: usize) -> BTreeSet<usize> {
        self.skills.get(&s).cloned().unwrap_or_else(|| self.snap.visible(s))
    }

    pub fn desired(&self) -> Desired {
        Desired {
            skills: self.skills.clone(),
            pi: self.pi.clone(),
            subagents: self.subagents,
            tools: self.tools.clone(),
            prune: self.prune,
        }
    }

    pub fn pending(&self) -> usize {
        self.skills.len() + self.pi.len() + usize::from(self.subagents) + self.tools.len() + usize::from(self.prune)
    }

    pub fn pending_plan(&self) -> Plan {
        plan::build(&self.snap, &self.desired(), Options::default())
    }

    fn say(&mut self, text: impl Into<String>, tone: Tone) {
        self.message = Some((text.into(), tone));
    }

    fn set_wanted(&mut self, s: usize, wanted: BTreeSet<usize>) {
        if wanted == self.snap.visible(s) {
            self.skills.remove(&s);
        } else {
            self.skills.insert(s, wanted);
        }
    }

    /// Toggle one harness for one skill, honoring shared folders.
    pub fn toggle_cell(&mut self, s: usize, h: usize) {
        let mut wanted = self.wanted(s);
        let harness = self.snap.env.harnesses[h].name.clone();
        let skill = self.snap.repo.skills[s].name.clone();
        if wanted.contains(&h) {
            let forced = plan::forced_by(&self.snap, &wanted, h);
            if let Some(&cause) = forced.first() {
                let owner = &self.snap.env.harnesses[cause];
                self.say(
                    format!(
                        "{harness} also loads {} from {}. Turn {skill} off for {} first.",
                        owner.name,
                        self.snap.env.tilde(owner.own_skills()),
                        owner.name
                    ),
                    Tone::Warn,
                );
                return;
            }
            wanted.remove(&h);
        } else {
            wanted.insert(h);
            let closed = plan::closure(&self.snap, &wanted);
            let extra: Vec<String> = closed.difference(&wanted).map(|&g| self.snap.env.harnesses[g].name.clone()).collect();
            if !extra.is_empty() {
                self.say(
                    format!(
                        "{} also load{} skills from {}, so {} {skill} too.",
                        doctor::join(&extra),
                        if extra.len() == 1 { "s" } else { "" },
                        self.snap.env.tilde(self.snap.env.harnesses[h].own_skills()),
                        if extra.len() == 1 { "it gets" } else { "they get" },
                    ),
                    Tone::Info,
                );
            } else {
                self.message = None;
            }
            wanted = closed;
        }
        self.set_wanted(s, wanted);
    }

    pub fn toggle_row(&mut self, s: usize) {
        let wanted = self.wanted(s);
        let all: BTreeSet<usize> = self.columns.iter().copied().collect();
        if all.is_subset(&wanted) {
            let keep: BTreeSet<usize> = wanted.difference(&all).copied().collect();
            self.set_wanted(s, keep);
        } else {
            let closed = plan::closure(&self.snap, &wanted.union(&all).copied().collect());
            self.set_wanted(s, closed);
        }
        self.message = None;
    }

    pub fn toggle_column(&mut self, h: usize) {
        let rows = self.rows();
        let every = rows.iter().all(|&s| self.wanted(s).contains(&h));
        let mut blocked = 0;
        for s in rows {
            let mut wanted = self.wanted(s);
            if every {
                if !plan::forced_by(&self.snap, &wanted, h).is_empty() {
                    blocked += 1;
                    continue;
                }
                wanted.remove(&h);
            } else {
                wanted.insert(h);
                wanted = plan::closure(&self.snap, &wanted);
            }
            self.set_wanted(s, wanted);
        }
        let name = self.snap.env.harnesses[h].name.clone();
        if blocked > 0 {
            self.say(format!("{blocked} skill(s) stay on for {name} because another harness shares its folder."), Tone::Warn);
        } else {
            self.say(format!("{} every listed skill for {name}.", if every { "Removed" } else { "Added" }), Tone::Info);
        }
    }

    pub fn toggle_pi(&mut self, i: usize) {
        let item = &self.snap.repo.pi[i];
        if item.kind == PiKind::Subagents {
            match self.snap.subagents.as_ref().map(|s| s.state.clone()) {
                Some(SubagentState::Installed) => {
                    self.say("Subagents merges Pi settings, so Æ will not undo it. See harness/pi/subagents/README.md.", Tone::Warn)
                }
                Some(SubagentState::NeedsChanges) => {
                    self.subagents = !self.subagents;
                    self.message = None;
                }
                Some(SubagentState::Invalid) => {
                    self.say("Pi settings did not pass the subagents preflight; fix settings.json first (see ae doctor).", Tone::Warn)
                }
                _ => self.say("python3 is needed for the subagents component.", Tone::Warn),
            }
            return;
        }
        let installed = self.snap.pi[i] == Entry::Linked;
        match self.pi.get(&i) {
            Some(_) => {
                self.pi.remove(&i);
            }
            None => {
                self.pi.insert(i, !installed);
            }
        }
        self.message = None;
    }

    pub fn toggle_tool(&mut self, t: usize) {
        if !self.tools.remove(&t) {
            self.tools.insert(t);
        }
    }

    pub fn start_review(&mut self) {
        if self.pending() == 0 {
            self.say("Nothing selected yet. Space toggles the highlighted item.", Tone::Info);
            return;
        }
        self.plan = self.pending_plan();
        if let Some(error) = self.plan.errors.first().cloned() {
            self.say(error, Tone::Warn);
            return;
        }
        if self.plan.steps.is_empty() {
            self.say("Everything selected is already in place.", Tone::Good);
            return;
        }
        self.plan_row = 0;
        self.screen = Screen::Review;
        self.message = None;
    }

    pub fn start_apply(&mut self) {
        if self.plan.approved_count() == 0 {
            self.say("Every step is skipped. Approve a conflict with space, or press esc.", Tone::Warn);
            return;
        }
        let plan = self.plan.clone();
        let order = plan.apply_order();
        let context = apply::Context { roots: self.snap.roots.clone(), log_dir: std::env::temp_dir().join("ae-logs") };
        let cancel = Arc::new(AtomicBool::new(false));
        let (tx, rx) = mpsc::channel();
        let worker_cancel = cancel.clone();
        thread::spawn(move || {
            apply::run(&plan, &context, &worker_cancel, |event| {
                let _ = tx.send(event);
            });
        });
        self.applying = Some(Applying {
            statuses: vec![StepStatus::Pending; self.plan.steps.len()],
            order,
            started: Instant::now(),
            finished: None,
            cancel,
            rx,
        });
        self.screen = Screen::Applying;
    }

    fn drain(&mut self) {
        if let Some(rx) = &self.versions
            && let Ok(env) = rx.try_recv()
        {
            for (harness, probed) in self.snap.env.harnesses.iter_mut().zip(env.harnesses) {
                harness.version = probed.version;
            }
            if let (Some(mine), Some(theirs)) = (self.snap.env.orchestrator.as_mut(), env.orchestrator) {
                mine.version = theirs.version;
            }
            self.probing = false;
            self.versions = None;
        }
        let Some(applying) = self.applying.as_mut() else { return };
        let mut done = false;
        while let Ok(event) = applying.rx.try_recv() {
            match event {
                ApplyEvent::Started(i) => {
                    applying.statuses[i] = StepStatus::Running { started: Instant::now(), fraction: None, line: String::new() }
                }
                ApplyEvent::Progress(i, fraction, text) => {
                    if let StepStatus::Running { fraction: f, line, .. } = &mut applying.statuses[i] {
                        if fraction.is_some() {
                            *f = fraction;
                        }
                        *line = text;
                    }
                }
                ApplyEvent::Finished(i, outcome, elapsed) => {
                    applying.statuses[i] = StepStatus::Finished { outcome, elapsed };
                    if applying.order.last() == Some(&i) {
                        done = true;
                    }
                }
                ApplyEvent::Cancelled(rest) => {
                    for i in rest {
                        applying.statuses[i] = StepStatus::NotRun;
                    }
                    done = true;
                }
            }
        }
        if done {
            applying.finished = Some(applying.started.elapsed());
            self.screen = Screen::Done;
            let paint = Paint { color: self.theme.color };
            for &i in &applying.order {
                if let StepStatus::Finished { outcome, elapsed } = &applying.statuses[i] {
                    self.log.push(output::outcome_line(&self.snap, &self.plan, i, outcome, *elapsed, paint));
                }
            }
            if let Some(hint) = output::restart_hint(&self.plan) {
                self.log.push(paint.dim(hint));
            }
        }
    }

    /// Re-scan after applying so another round starts from the real state.
    fn refresh(&mut self) {
        let env = self.snap.env.clone();
        let repo = crate::repo::Repo::discover(&self.snap.repo.root);
        let mut fresh = Snapshot::take(repo, env.clone(), &BTreeSet::new());
        fresh.env = env;
        self.snap = fresh;
        self.issues = doctor::issues(&self.snap);
        self.skills.clear();
        self.pi.clear();
        self.subagents = false;
        self.tools.clear();
        self.prune = false;
        self.applying = None;
        self.screen = Screen::Browse;
    }

    pub fn handle_key(&mut self, key: KeyEvent) {
        if key.kind != KeyEventKind::Press {
            return;
        }
        let ctrl_c = key.modifiers.contains(KeyModifiers::CONTROL) && key.code == KeyCode::Char('c');
        if self.help {
            self.help = false;
            return;
        }
        match self.screen {
            Screen::Applying => {
                if ctrl_c || key.code == KeyCode::Esc {
                    if let Some(applying) = &self.applying {
                        applying.cancel.store(true, Ordering::SeqCst);
                    }
                    self.say("Stopping after the current step…", Tone::Warn);
                }
                return;
            }
            Screen::Done => {
                match key.code {
                    KeyCode::Enter => {
                        let ok = self.applying.as_ref().is_some_and(|a| {
                            a.statuses.iter().all(|s| !matches!(s, StepStatus::Finished { outcome: Outcome::Failed(_), .. }))
                        });
                        self.refresh();
                        self.say(
                            if ok {
                                "Applied. Pick more changes, or press q to quit."
                            } else {
                                "Some steps failed; the list shows the current state."
                            },
                            if ok { Tone::Good } else { Tone::Warn },
                        );
                    }
                    KeyCode::Char('q') | KeyCode::Esc => self.quit = true,
                    _ if ctrl_c => self.quit = true,
                    _ => {}
                }
                return;
            }
            Screen::Review => {
                match key.code {
                    KeyCode::Esc | KeyCode::Backspace | KeyCode::Char('q') => {
                        self.screen = Screen::Browse;
                    }
                    _ if ctrl_c => self.quit = true,
                    KeyCode::Up | KeyCode::Char('k') => self.plan_row = self.plan_row.saturating_sub(1),
                    KeyCode::Down | KeyCode::Char('j') => self.plan_row = (self.plan_row + 1).min(self.plan.steps.len().saturating_sub(1)),
                    KeyCode::Char(' ') => {
                        if let Some(step) = self.plan.steps.get_mut(self.plan_row) {
                            if step.needs_approval {
                                step.approved = !step.approved;
                            } else {
                                self.message =
                                    Some(("Only conflicts can be skipped here; go back to change the selection.".into(), Tone::Info));
                            }
                        }
                    }
                    KeyCode::Enter | KeyCode::Char('y') => self.start_apply(),
                    _ => {}
                }
                return;
            }
            Screen::Browse => {}
        }

        if self.confirm_quit {
            self.confirm_quit = false;
            if matches!(key.code, KeyCode::Char('y') | KeyCode::Char('Y')) || ctrl_c {
                self.quit = true;
            }
            return;
        }
        if self.filtering {
            match key.code {
                KeyCode::Esc => {
                    self.filtering = false;
                    self.filter.clear();
                }
                KeyCode::Enter => self.filtering = false,
                KeyCode::Backspace => {
                    self.filter.pop();
                }
                KeyCode::Char(c) if !key.modifiers.contains(KeyModifiers::CONTROL) => self.filter.push(c),
                _ if ctrl_c => self.quit = true,
                _ => {}
            }
            self.row = 0;
            return;
        }
        let shift = key.modifiers.contains(KeyModifiers::SHIFT);
        match key.code {
            _ if ctrl_c => self.request_quit(),
            KeyCode::Char('q') | KeyCode::Esc => self.request_quit(),
            KeyCode::Char('?') => self.help = true,
            KeyCode::Tab => self.cycle_tab(1),
            KeyCode::BackTab => self.cycle_tab(-1),
            KeyCode::Char('1') => self.tab = Tab::Skills,
            KeyCode::Char('2') => self.tab = Tab::Pi,
            KeyCode::Char('3') => self.tab = Tab::Tools,
            KeyCode::Enter => self.start_review(),
            KeyCode::Char('p') => {
                let tidy = !self.snap.stale.is_empty() || !plan::redundant(&self.snap).is_empty();
                if tidy {
                    self.prune = !self.prune;
                    self.say(if self.prune { "Stale and redundant links will be removed." } else { "Tidy-up cancelled." }, Tone::Info);
                } else {
                    self.say("Nothing to tidy: no stale or redundant links.", Tone::Good);
                }
            }
            KeyCode::Char('R') => {
                self.skills.clear();
                self.pi.clear();
                self.subagents = false;
                self.tools.clear();
                self.prune = false;
                self.say("Cleared every pending change.", Tone::Info);
            }
            _ => match self.tab {
                Tab::Skills => self.skills_key(key.code, shift),
                Tab::Pi => self.list_key(key.code, true),
                Tab::Tools => self.list_key(key.code, false),
            },
        }
    }

    fn request_quit(&mut self) {
        if self.pending() > 0 {
            self.confirm_quit = true;
        } else {
            self.quit = true;
        }
    }

    fn cycle_tab(&mut self, step: isize) {
        let index = Tab::ALL.iter().position(|t| *t == self.tab).unwrap_or(0) as isize;
        self.tab = Tab::ALL[(index + step).rem_euclid(Tab::ALL.len() as isize) as usize];
        self.message = None;
    }

    fn skills_key(&mut self, code: KeyCode, _shift: bool) {
        let rows = self.rows();
        let row_count = rows.len();
        match code {
            KeyCode::Up | KeyCode::Char('k') => self.row = self.row.saturating_sub(1),
            KeyCode::Down | KeyCode::Char('j') => self.row = (self.row + 1).min(row_count.saturating_sub(1)),
            KeyCode::Left | KeyCode::Char('h') => self.col = self.col.saturating_sub(1),
            KeyCode::Right | KeyCode::Char('l') => self.col = (self.col + 1).min(self.columns.len().saturating_sub(1)),
            KeyCode::Home | KeyCode::Char('g') => self.row = 0,
            KeyCode::End | KeyCode::Char('G') => self.row = row_count.saturating_sub(1),
            KeyCode::Char('/') => {
                self.filtering = true;
                self.filter.clear();
            }
            KeyCode::Char(' ') | KeyCode::Char('x') => {
                if let (Some(&s), Some(&h)) = (rows.get(self.row), self.columns.get(self.col)) {
                    self.toggle_cell(s, h);
                }
            }
            KeyCode::Char('a') => {
                if let Some(&s) = rows.get(self.row) {
                    self.toggle_row(s);
                }
            }
            KeyCode::Char('A') => {
                if let Some(&h) = self.columns.get(self.col) {
                    self.toggle_column(h);
                }
            }
            KeyCode::Char('r') => {
                if let Some(&s) = rows.get(self.row) {
                    self.skills.remove(&s);
                }
            }
            _ => {}
        }
    }

    fn list_key(&mut self, code: KeyCode, pi: bool) {
        let len = if pi { self.snap.repo.pi.len() } else { self.snap.repo.tools.len() };
        let cursor = if pi { &mut self.pi_row } else { &mut self.tool_row };
        match code {
            KeyCode::Up | KeyCode::Char('k') => *cursor = cursor.saturating_sub(1),
            KeyCode::Down | KeyCode::Char('j') => *cursor = (*cursor + 1).min(len.saturating_sub(1)),
            KeyCode::Home | KeyCode::Char('g') => *cursor = 0,
            KeyCode::End | KeyCode::Char('G') => *cursor = len.saturating_sub(1),
            KeyCode::Char(' ') | KeyCode::Char('x') => {
                let index = *cursor;
                if index < len {
                    if pi { self.toggle_pi(index) } else { self.toggle_tool(index) }
                }
            }
            KeyCode::Char('a') if !pi => {
                if self.tools.len() == len {
                    self.tools.clear();
                } else {
                    self.tools = (0..len).collect();
                }
            }
            _ => {}
        }
    }
}

/// Run the full-screen installer, then print what happened to the scrollback.
pub fn run(snap: Snapshot) -> Result<u8> {
    let theme = Theme::detect();
    let mut app = App::new(snap, theme);
    app.probe_versions();
    let mut terminal = ratatui::init();
    let result = (|| -> Result<()> {
        while !app.quit {
            app.drain();
            terminal.draw(|frame| view::draw(frame, &app))?;
            if event::poll(Duration::from_millis(80))?
                && let Event::Key(key) = event::read()?
            {
                app.handle_key(key);
            }
            app.tick = app.tick.wrapping_add(1);
        }
        Ok(())
    })();
    ratatui::restore();
    result?;
    if app.log.is_empty() {
        println!("Æ closed. Nothing changed.");
        return Ok(0);
    }
    for line in &app.log {
        println!("{line}");
    }
    let failed = app.log.iter().any(|line| line.contains('✗'));
    Ok(u8::from(failed))
}

#[cfg(test)]
mod tests;

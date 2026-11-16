//! Turn a desired state into an ordered, reviewable plan.
//!
//! Skills are chosen per harness, but links live in folders that several
//! harnesses share. The solver picks the folders whose readers cover exactly
//! the chosen harnesses, preferring (in order): keeping existing links, loading
//! each skill once per harness, avoiding conflicts, fewer links, fewer changes,
//! and a harness's own folder over a shared one.

use crate::state::{Entry, Existing, Snapshot, SubagentState};
use serde::Serialize;
use std::collections::{BTreeMap, BTreeSet};
use std::path::PathBuf;

#[derive(Clone, Debug, Default)]
pub struct Desired {
    /// Desired harness set for each skill row that changed.
    pub skills: BTreeMap<usize, BTreeSet<usize>>,
    /// Desired installed state for each Pi item that changed (not subagents).
    pub pi: BTreeMap<usize, bool>,
    pub subagents: bool,
    pub tools: BTreeSet<usize>,
    pub prune: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum Section {
    Skills,
    Pi,
    Tools,
    Tidy,
}

impl Section {
    pub fn title(self) -> &'static str {
        match self {
            Section::Skills => "Skills",
            Section::Pi => "Pi",
            Section::Tools => "Tools",
            Section::Tidy => "Tidy",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum Reason {
    Deselected,
    Stale,
    Redundant,
}

#[derive(Clone, Debug, Serialize)]
#[serde(tag = "op", rename_all = "kebab-case")]
pub enum Op {
    Link {
        source: PathBuf,
        dest: PathBuf,
    },
    /// Replace something the user owns; files and directories are backed up.
    Replace {
        source: PathBuf,
        dest: PathBuf,
        existing: Existing,
    },
    /// Repoint a link that already points into this checkout.
    Relink {
        source: PathBuf,
        dest: PathBuf,
        previous: PathBuf,
    },
    Unlink {
        dest: PathBuf,
        reason: Reason,
    },
    Subagents {
        script: PathBuf,
        agent_dir: PathBuf,
        preview: Vec<String>,
    },
    CargoInstall {
        dir: PathBuf,
        locked: bool,
        packages: usize,
        from: Option<String>,
        to: Option<String>,
    },
}

impl Op {
    /// Apply order: removals, then links, then the settings merge, then builds.
    pub fn priority(&self) -> u8 {
        match self {
            Op::Unlink { .. } => 0,
            Op::Link { .. } | Op::Replace { .. } | Op::Relink { .. } => 1,
            Op::Subagents { .. } => 2,
            Op::CargoInstall { .. } => 3,
        }
    }

    pub fn dest(&self) -> Option<&PathBuf> {
        match self {
            Op::Link { dest, .. } | Op::Replace { dest, .. } | Op::Relink { dest, .. } | Op::Unlink { dest, .. } => Some(dest),
            _ => None,
        }
    }
}

#[derive(Clone, Debug, Serialize)]
pub struct Step {
    pub section: Section,
    /// The skill, Pi item, or tool name.
    pub name: String,
    /// Harnesses affected, for display.
    pub readers: Vec<String>,
    pub op: Op,
    pub needs_approval: bool,
    pub approved: bool,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct Plan {
    pub steps: Vec<Step>,
    /// Problems that block the whole plan.
    pub errors: Vec<String>,
}

impl Plan {
    pub fn approved(&self) -> impl Iterator<Item = (usize, &Step)> {
        self.steps.iter().enumerate().filter(|(_, step)| step.approved)
    }

    pub fn approved_count(&self) -> usize {
        self.steps.iter().filter(|step| step.approved).count()
    }

    pub fn pending_conflicts(&self) -> usize {
        self.steps.iter().filter(|step| step.needs_approval && !step.approved).count()
    }

    pub fn approve_conflicts(&mut self, approve: bool) {
        for step in self.steps.iter_mut().filter(|step| step.needs_approval) {
            step.approved = approve;
        }
    }

    /// Indices of approved steps in the order they must run.
    pub fn apply_order(&self) -> Vec<usize> {
        let mut order: Vec<usize> = self.approved().map(|(index, _)| index).collect();
        order.sort_by_key(|&index| (self.steps[index].op.priority(), index));
        order
    }
}

/// Add every harness that cannot get the skill without also giving it to
/// others: Claude Code's `~/.claude/skills` is also loaded by Grok and Kilo.
pub fn closure(snap: &Snapshot, wanted: &BTreeSet<usize>) -> BTreeSet<usize> {
    let mut set: BTreeSet<usize> = wanted.intersection(&snap.active).copied().collect();
    loop {
        let before = set.len();
        for h in set.clone() {
            let usable = snap.env.harnesses[h]
                .skill_dirs
                .iter()
                .any(|dir| location(snap, dir).is_some_and(|l| snap.locations[l].readers.is_subset(&set)));
            if !usable && let Some(l) = location(snap, snap.env.harnesses[h].own_skills()) {
                set.extend(snap.locations[l].readers.iter().copied());
            }
        }
        if set.len() == before {
            return set;
        }
    }
}

/// Harnesses that force `h` on when they have the skill.
pub fn forced_by(snap: &Snapshot, set: &BTreeSet<usize>, h: usize) -> Vec<usize> {
    let mut without = set.clone();
    without.remove(&h);
    if !closure(snap, &without).contains(&h) {
        return Vec::new();
    }
    without
        .into_iter()
        .filter(|&g| {
            snap.env.harnesses[g].skill_dirs.iter().all(|dir| location(snap, dir).is_some_and(|l| snap.locations[l].readers.contains(&h)))
        })
        .collect()
}

pub fn location(snap: &Snapshot, dir: &std::path::Path) -> Option<usize> {
    snap.locations.iter().position(|location| location.path == dir)
}

/// The set of locations that should hold skill `s` so exactly `wanted` load it.
/// Lexicographic: removals, overlap, conflicts, folder count, adds, unowned folders.
type Cost = (usize, usize, usize, usize, usize, usize);

pub fn solve(snap: &Snapshot, s: usize, wanted: &BTreeSet<usize>) -> BTreeSet<usize> {
    if wanted.is_empty() {
        return BTreeSet::new();
    }
    let current = snap.linked_locations(s);
    let candidates: Vec<usize> = (0..snap.locations.len())
        .filter(|&l| {
            let readers = &snap.locations[l].readers;
            !readers.is_empty() && readers.is_subset(wanted)
        })
        .collect();
    // A folder no chosen harness calls its own (the shared folder, or
    // ~/.claude/skills when only Grok or Kilo read it) loses ties.
    let unowned = |l: usize| !snap.locations[l].readers.iter().any(|&h| snap.env.harnesses[h].own_skills() == snap.locations[l].path);
    let mut best: Option<(Cost, BTreeSet<usize>)> = None;
    let limit = candidates.len().min(16);
    for mask in 1u32..(1 << limit) {
        let chosen: BTreeSet<usize> = (0..limit).filter(|bit| mask & (1 << bit) != 0).map(|bit| candidates[bit]).collect();
        let mut covered = BTreeSet::new();
        let mut loads = 0;
        for &l in &chosen {
            covered.extend(snap.locations[l].readers.iter().copied());
            loads += snap.locations[l].readers.len();
        }
        if covered != *wanted {
            continue;
        }
        // A copy the user owns that stays in place is loaded too: routing
        // around it would leave a harness with two skills of the same name.
        for l in 0..snap.locations.len() {
            if !chosen.contains(&l) && matches!(snap.skills[s][l], Entry::Foreign { .. }) {
                loads += snap.locations[l].readers.intersection(wanted).count();
            }
        }
        let removals = current.difference(&chosen).count();
        let conflicts = chosen.iter().filter(|&&l| matches!(snap.skills[s][l], Entry::Foreign { .. })).count();
        let overlap = loads - wanted.len();
        let adds = chosen.difference(&current).count();
        let cost = (removals, overlap, conflicts, chosen.len(), adds, chosen.iter().filter(|&&l| unowned(l)).count());
        if best.as_ref().is_none_or(|(best_cost, _)| cost < *best_cost) {
            best = Some((cost, chosen));
        }
    }
    best.map(|(_, chosen)| chosen).unwrap_or_default()
}

#[derive(Clone, Copy, Debug, Default)]
pub struct Options {
    /// Back up and replace conflicting files without asking.
    pub replace: bool,
}

pub fn build(snap: &Snapshot, desired: &Desired, options: Options) -> Plan {
    let mut plan = Plan::default();
    let mut claimed: BTreeSet<PathBuf> = BTreeSet::new();
    let mut push = |plan: &mut Plan, step: Step| {
        if let Some(dest) = step.op.dest()
            && !claimed.insert(dest.clone())
        {
            return;
        }
        plan.steps.push(step);
    };

    for (&s, wanted) in &desired.skills {
        let skill = &snap.repo.skills[s];
        let wanted = closure(snap, wanted);
        let target = solve(snap, s, &wanted);
        let current = snap.linked_locations(s);
        for &l in current.difference(&target) {
            let step = Step {
                section: Section::Skills,
                name: skill.name.clone(),
                readers: snap.location_names(l),
                op: Op::Unlink { dest: snap.locations[l].path.join(&skill.name), reason: Reason::Deselected },
                needs_approval: false,
                approved: true,
            };
            push(&mut plan, step);
        }
        for &l in target.difference(&current) {
            let dest = snap.locations[l].path.join(&skill.name);
            let source = skill.dir.clone();
            let (op, needs_approval) = match &snap.skills[s][l] {
                Entry::Foreign { what } => (Op::Replace { source, dest, existing: what.clone() }, true),
                Entry::OtherAeLink { target } => (Op::Relink { source, dest, previous: target.clone() }, false),
                _ => (Op::Link { source, dest }, false),
            };
            let step = Step {
                section: Section::Skills,
                name: skill.name.clone(),
                readers: snap.location_names(l),
                op,
                approved: !needs_approval || options.replace,
                needs_approval,
            };
            push(&mut plan, step);
        }
    }

    if let Some(pi_dir) = &snap.pi_dir {
        for (&i, &want) in &desired.pi {
            let item = &snap.repo.pi[i];
            let dest = pi_dir.join(&item.target);
            let source = item.source.clone();
            let (op, needs_approval) = match (&snap.pi[i], want) {
                (Entry::Missing, true) => (Op::Link { source, dest }, false),
                (Entry::Foreign { what }, true) => (Op::Replace { source, dest, existing: what.clone() }, true),
                (Entry::OtherAeLink { target }, true) => (Op::Relink { source, dest, previous: target.clone() }, false),
                (Entry::Linked, false) => (Op::Unlink { dest, reason: Reason::Deselected }, false),
                _ => continue,
            };
            let step = Step {
                section: Section::Pi,
                name: item.id.clone(),
                readers: vec!["Pi".into()],
                op,
                approved: !needs_approval || options.replace,
                needs_approval,
            };
            push(&mut plan, step);
        }
        if desired.subagents {
            match (&snap.subagents, snap.repo.pi.iter().find(|item| item.kind == crate::repo::PiKind::Subagents)) {
                (Some(state), Some(item)) => match state.state {
                    SubagentState::Installed => {}
                    SubagentState::NeedsChanges => push(
                        &mut plan,
                        Step {
                            section: Section::Pi,
                            name: "subagents".into(),
                            readers: vec!["Pi".into()],
                            op: Op::Subagents {
                                script: item.source.join("install.py"),
                                agent_dir: pi_dir.clone(),
                                preview: state.preview.clone(),
                            },
                            needs_approval: false,
                            approved: true,
                        },
                    ),
                    SubagentState::Invalid => plan.errors.push(format!(
                        "Subagent policy preflight failed for {}. {}",
                        snap.env.tilde(pi_dir),
                        state.message.clone().unwrap_or_default()
                    )),
                    SubagentState::Unavailable => plan.errors.push("python3 is required for the subagents component.".into()),
                },
                _ => plan.errors.push("This checkout has no Pi subagents component.".into()),
            }
        }
    }

    for &t in &desired.tools {
        let tool = &snap.repo.tools[t];
        let installed = snap.tools[t].as_ref();
        push(
            &mut plan,
            Step {
                section: Section::Tools,
                name: tool.name.clone(),
                readers: tool.bins.clone(),
                op: Op::CargoInstall {
                    dir: tool.dir.clone(),
                    locked: tool.locked,
                    packages: tool.packages,
                    from: installed.map(|i| i.version.clone()),
                    to: tool.version.clone(),
                },
                needs_approval: false,
                approved: true,
            },
        );
    }

    if desired.prune {
        for stale in &snap.stale {
            let name = stale.path.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default();
            push(
                &mut plan,
                Step {
                    section: Section::Tidy,
                    name,
                    readers: readers_of_dir(snap, &stale.path),
                    op: Op::Unlink { dest: stale.path.clone(), reason: Reason::Stale },
                    needs_approval: false,
                    approved: true,
                },
            );
        }
        for (s, l) in redundant(snap) {
            if desired.skills.contains_key(&s) {
                continue;
            }
            let skill = &snap.repo.skills[s];
            push(
                &mut plan,
                Step {
                    section: Section::Tidy,
                    name: skill.name.clone(),
                    readers: snap.location_names(l),
                    op: Op::Unlink { dest: snap.locations[l].path.join(&skill.name), reason: Reason::Redundant },
                    needs_approval: false,
                    approved: true,
                },
            );
        }
    }
    plan
}

fn readers_of_dir(snap: &Snapshot, path: &std::path::Path) -> Vec<String> {
    path.parent().and_then(|parent| location(snap, parent)).map(|l| snap.location_names(l)).unwrap_or_else(|| vec!["Pi".into()])
}

/// AE links whose every reader also loads the skill through another AE link.
/// Removing one never changes what any harness loads.
pub fn redundant(snap: &Snapshot) -> Vec<(usize, usize)> {
    let mut out = Vec::new();
    for s in 0..snap.repo.skills.len() {
        let mut counts = snap.link_counts(s);
        for l in snap.linked_locations(s) {
            let readers = &snap.locations[l].readers;
            if !readers.is_empty() && readers.iter().all(|h| counts.get(h).copied().unwrap_or(0) > 1) {
                for h in readers {
                    *counts.get_mut(h).unwrap() -= 1;
                }
                out.push((s, l));
            }
        }
    }
    out
}

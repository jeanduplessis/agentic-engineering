//! A read-only snapshot of what is installed where.

use crate::harness::Environment;
use crate::paths::{Roots, link_target, occupied};
use crate::repo::{PiKind, Repo};
use serde::Serialize;
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};
use std::process::Command;

/// What occupies one install path.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "state", rename_all = "kebab-case")]
pub enum Entry {
    Missing,
    /// A symlink to the expected source in this checkout.
    Linked,
    /// A symlink into this checkout, but to a different or missing source.
    OtherAeLink {
        target: PathBuf,
    },
    /// Anything the user owns: a file, a directory, or a symlink elsewhere.
    Foreign {
        what: Existing,
    },
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "kind", content = "target", rename_all = "kebab-case")]
pub enum Existing {
    File,
    Directory,
    Symlink(PathBuf),
}

impl Existing {
    pub fn describe(&self) -> String {
        match self {
            Existing::File => "a file".into(),
            Existing::Directory => "a directory".into(),
            Existing::Symlink(target) => format!("a link to {}", target.display()),
        }
    }
}

pub fn inspect(dest: &Path, expected: &Path, roots: &Roots) -> Entry {
    if let Some(target) = link_target(dest) {
        if roots.to_canonical(&target) == roots.to_canonical(expected) || target == expected {
            return Entry::Linked;
        }
        if roots.contains(&target) {
            return Entry::OtherAeLink { target };
        }
        return Entry::Foreign { what: Existing::Symlink(target) };
    }
    if !occupied(dest) {
        return Entry::Missing;
    }
    Entry::Foreign { what: if dest.is_dir() { Existing::Directory } else { Existing::File } }
}

/// A skill folder and the active harnesses that load it.
#[derive(Clone, Debug, Serialize)]
pub struct Location {
    pub path: PathBuf,
    pub readers: BTreeSet<usize>,
}

#[derive(Clone, Debug, Serialize)]
pub struct StaleLink {
    pub path: PathBuf,
    pub target: PathBuf,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum SubagentState {
    Installed,
    NeedsChanges,
    /// `install.py --check` refused the target (malformed or symlinked settings).
    Invalid,
    /// python3 is not on PATH.
    Unavailable,
}

#[derive(Clone, Debug, Serialize)]
pub struct Subagents {
    pub state: SubagentState,
    /// The LINK/MERGE preview lines from `install.py --check`.
    pub preview: Vec<String>,
    pub message: Option<String>,
}

#[derive(Clone, Debug, Serialize)]
pub struct InstalledTool {
    pub version: String,
    pub source: String,
    pub from_this_checkout: bool,
}

#[derive(Clone, Debug, Serialize)]
pub struct Snapshot {
    pub repo: Repo,
    pub env: Environment,
    pub roots_canonical: PathBuf,
    /// Indices of harnesses AE may target (detected, or explicitly requested).
    pub active: BTreeSet<usize>,
    pub locations: Vec<Location>,
    /// `skills[s][l]`: what occupies `locations[l]/<skill s>`.
    pub skills: Vec<Vec<Entry>>,
    pub stale: Vec<StaleLink>,
    pub pi_dir: Option<PathBuf>,
    pub pi: Vec<Entry>,
    pub subagents: Option<Subagents>,
    pub tools: Vec<Option<InstalledTool>>,
    #[serde(skip)]
    pub roots: Roots,
}

impl Snapshot {
    /// Scan the filesystem. `force_active` adds harnesses that were requested
    /// explicitly even though they were not detected.
    pub fn take(repo: Repo, env: Environment, force_active: &BTreeSet<usize>) -> Snapshot {
        let roots = Roots::new(&repo.root);
        let active: BTreeSet<usize> = env
            .harnesses
            .iter()
            .enumerate()
            .filter(|(index, harness)| harness.detected || force_active.contains(index))
            .map(|(index, _)| index)
            .collect();

        let mut paths: Vec<PathBuf> = Vec::new();
        for &index in &active {
            for dir in &env.harnesses[index].skill_dirs {
                if !paths.contains(dir) {
                    paths.push(dir.clone());
                }
            }
        }
        let locations: Vec<Location> = paths
            .into_iter()
            .map(|path| {
                let readers = active.iter().copied().filter(|&h| env.harnesses[h].skill_dirs.contains(&path)).collect();
                Location { path, readers }
            })
            .collect();

        let skills = repo
            .skills
            .iter()
            .map(|skill| locations.iter().map(|location| inspect(&location.path.join(&skill.name), &skill.dir, &roots)).collect())
            .collect();

        let pi_index = env.harnesses.iter().position(|h| h.kind == crate::harness::Kind::Pi);
        let pi_dir = pi_index.map(|index| env.harnesses[index].home.clone());
        let pi = repo
            .pi
            .iter()
            .map(|item| match (&pi_dir, item.kind) {
                (_, PiKind::Subagents) | (None, _) => Entry::Missing,
                (Some(dir), _) => inspect(&dir.join(&item.target), &item.source, &roots),
            })
            .collect();

        let subagents = match (&pi_dir, repo.pi.iter().find(|item| item.kind == PiKind::Subagents)) {
            (Some(dir), Some(item)) => Some(check_subagents(&item.source, dir)),
            _ => None,
        };

        let mut scan_dirs: Vec<PathBuf> = locations.iter().map(|l| l.path.clone()).collect();
        if let Some(dir) = &pi_dir {
            for sub in ["", "prompts", "extensions", "skills", "agents"] {
                scan_dirs.push(dir.join(sub));
            }
        }
        let stale = find_stale(&scan_dirs, &roots);
        let tools = installed_tools(&repo, &env.cargo_home, &roots);

        Snapshot {
            roots_canonical: roots.canonical.clone(),
            repo,
            env,
            active,
            locations,
            skills,
            stale,
            pi_dir,
            pi,
            subagents,
            tools,
            roots,
        }
    }

    /// Harnesses that load AE's copy of skill `s` (through any location).
    pub fn visible(&self, s: usize) -> BTreeSet<usize> {
        self.harnesses_where(s, |entry| *entry == Entry::Linked)
    }

    /// Harnesses that load some other skill with the same name.
    pub fn foreign(&self, s: usize) -> BTreeSet<usize> {
        self.harnesses_where(s, |entry| matches!(entry, Entry::Foreign { .. } | Entry::OtherAeLink { .. }))
    }

    fn harnesses_where(&self, s: usize, predicate: impl Fn(&Entry) -> bool) -> BTreeSet<usize> {
        let mut out = BTreeSet::new();
        for (l, entry) in self.skills[s].iter().enumerate() {
            if predicate(entry) {
                out.extend(self.locations[l].readers.iter().copied());
            }
        }
        out
    }

    /// Locations holding AE's link for skill `s`.
    pub fn linked_locations(&self, s: usize) -> BTreeSet<usize> {
        (0..self.locations.len()).filter(|&l| self.skills[s][l] == Entry::Linked).collect()
    }

    /// How many AE links each harness loads skill `s` through.
    pub fn link_counts(&self, s: usize) -> BTreeMap<usize, usize> {
        let mut counts = BTreeMap::new();
        for l in self.linked_locations(s) {
            for &h in &self.locations[l].readers {
                *counts.entry(h).or_insert(0) += 1;
            }
        }
        counts
    }

    pub fn location_names(&self, l: usize) -> Vec<String> {
        self.locations[l].readers.iter().map(|&h| self.env.harnesses[h].name.clone()).collect()
    }
}

/// Symlinks into this checkout whose source no longer exists.
fn find_stale(dirs: &[PathBuf], roots: &Roots) -> Vec<StaleLink> {
    let mut out = Vec::new();
    let mut seen = BTreeSet::new();
    for dir in dirs {
        let Ok(read) = std::fs::read_dir(dir) else { continue };
        let mut paths: Vec<PathBuf> = read.filter_map(Result::ok).map(|entry| entry.path()).collect();
        paths.sort();
        for path in paths {
            let Some(target) = link_target(&path) else { continue };
            if roots.contains(&target) && !occupied(&target) && seen.insert(path.clone()) {
                out.push(StaleLink { path, target });
            }
        }
    }
    out
}

fn check_subagents(source: &Path, agent_dir: &Path) -> Subagents {
    let script = source.join("install.py");
    let output =
        Command::new("python3").arg(&script).arg("--agent-dir").arg(agent_dir).arg("--check").stdin(std::process::Stdio::null()).output();
    let Ok(output) = output else {
        return Subagents {
            state: SubagentState::Unavailable,
            preview: Vec::new(),
            message: Some("python3 is required for the subagents component".into()),
        };
    };
    let stdout = String::from_utf8_lossy(&output.stdout);
    let preview: Vec<String> = stdout.lines().map(str::to_string).filter(|line| !line.is_empty()).collect();
    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
    let state = match output.status.code() {
        Some(0) => SubagentState::Installed,
        Some(1) => SubagentState::NeedsChanges,
        _ => SubagentState::Invalid,
    };
    Subagents { state, preview, message: (!stderr.is_empty()).then_some(stderr) }
}

/// Read cargo's install ledger rather than running `cargo install --list`.
fn installed_tools(repo: &Repo, cargo_home: &Path, roots: &Roots) -> Vec<Option<InstalledTool>> {
    let ledger: serde_json::Value = std::fs::read_to_string(cargo_home.join(".crates2.json"))
        .ok()
        .and_then(|text| serde_json::from_str(&text).ok())
        .unwrap_or(serde_json::Value::Null);
    let installs = ledger.get("installs").and_then(|v| v.as_object());
    repo.tools
        .iter()
        .map(|tool| {
            let installs = installs?;
            installs.keys().find_map(|key| {
                // "gs 1.1.0 (path+file:///Users/me/repo/tools/gs)"
                let mut parts = key.splitn(3, ' ');
                let (name, version, source) = (parts.next()?, parts.next()?, parts.next().unwrap_or(""));
                if name != tool.name {
                    return None;
                }
                let source = source.trim_matches(|c| c == '(' || c == ')').to_string();
                let path = source.strip_prefix("path+file://").map(PathBuf::from);
                let from_this_checkout =
                    path.is_some_and(|path| roots.to_canonical(&path) == roots.to_canonical(&tool.dir) || path == tool.dir);
                Some(InstalledTool { version: version.to_string(), source, from_this_checkout })
            })
        })
        .collect()
}

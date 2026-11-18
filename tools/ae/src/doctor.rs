//! Health checks: filesystem issues, plus asking harnesses what they load.

use crate::harness::{Kind, run_bounded_in};
use crate::plan::redundant;
use crate::state::{Entry, Snapshot, SubagentState};
use serde::Serialize;
use std::collections::{BTreeMap, BTreeSet};
use std::sync::mpsc;
use std::thread;
use std::time::Duration;

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Level {
    Warning,
    Info,
}

#[derive(Clone, Debug, Serialize)]
pub struct Issue {
    pub level: Level,
    pub message: String,
    pub fix: Option<String>,
}

/// Problems visible from the filesystem alone. Cheap enough for every screen.
pub fn issues(snap: &Snapshot) -> Vec<Issue> {
    let mut out = Vec::new();
    for stale in &snap.stale {
        out.push(Issue {
            level: Level::Warning,
            message: format!("{} points to {}, which no longer exists", snap.env.tilde(&stale.path), snap.env.tilde(&stale.target)),
            fix: Some("ae prune".into()),
        });
    }
    for (s, l) in redundant(snap) {
        let skill = &snap.repo.skills[s].name;
        out.push(Issue {
            level: Level::Info,
            message: format!(
                "{} is redundant: {} already load{} {skill} from another folder",
                snap.env.tilde(&snap.locations[l].path.join(skill)),
                join(&snap.location_names(l)),
                if snap.locations[l].readers.len() == 1 { "s" } else { "" },
            ),
            fix: Some("ae prune".into()),
        });
    }
    for (s, skill) in snap.repo.skills.iter().enumerate() {
        for (l, entry) in snap.skills[s].iter().enumerate() {
            if let Entry::Foreign { what } = entry {
                let names = snap.location_names(l);
                if names.is_empty() {
                    continue;
                }
                out.push(Issue {
                    level: Level::Info,
                    message: format!(
                        "{} is {} not managed by Æ; {} load{} that copy of {}",
                        snap.env.tilde(&snap.locations[l].path.join(&skill.name)),
                        what.describe(),
                        join(&names),
                        if names.len() == 1 { "s" } else { "" },
                        skill.name
                    ),
                    fix: None,
                });
            }
        }
    }
    for (i, item) in snap.repo.claude.iter().enumerate() {
        for (k, &h) in snap.claude_homes.iter().enumerate() {
            let harness = &snap.env.harnesses[h];
            let path = snap.env.tilde(&harness.home.join(&item.target));
            match &snap.claude[i][k] {
                Entry::Linked => {
                    if let Some(style) = &item.style
                        && !snap.style_active(i, k)
                    {
                        out.push(Issue {
                            level: Level::Info,
                            message: format!("{} has the {style} output style, but its settings.json does not select it", harness.name),
                            fix: Some(crate::output::style_hint(snap, h, style)),
                        });
                    }
                }
                Entry::Foreign { what } => {
                    out.push(Issue { level: Level::Info, message: format!("{path} is {} not managed by Æ", what.describe()), fix: None })
                }
                _ => {}
            }
        }
    }
    if let Some(subagents) = &snap.subagents
        && subagents.state == SubagentState::Invalid
    {
        out.push(Issue {
            level: Level::Warning,
            message: format!(
                "Pi subagent policy cannot be checked: {}",
                subagents.message.clone().unwrap_or_else(|| "install.py --check failed".into())
            ),
            fix: None,
        });
    }
    for (t, tool) in snap.repo.tools.iter().enumerate() {
        if let (Some(installed), Some(version)) = (&snap.tools[t], &tool.version)
            && installed.from_this_checkout
            && installed.version != *version
        {
            out.push(Issue {
                level: Level::Info,
                message: format!("{} {} is installed; this checkout has {version}", tool.name, installed.version),
                fix: Some(format!("ae add --tool {}", tool.name)),
            });
        }
    }
    out.sort_by_key(|issue| issue.level);
    out
}

#[derive(Clone, Debug, Serialize)]
pub struct Probe {
    pub harness: String,
    pub command: String,
    /// `None` when the harness could not be asked.
    pub loaded: Option<BTreeSet<String>>,
    pub error: Option<String>,
    pub mismatches: Vec<String>,
}

/// Ask Grok, Kilo, and Codex which skills they load, in parallel, from an
/// empty directory so project skills do not interfere.
pub fn probe(snap: &Snapshot, timeout: Duration) -> Vec<Probe> {
    let scratch = std::env::temp_dir().join(format!("ae-doctor-{}", std::process::id()));
    let _ = std::fs::create_dir_all(&scratch);
    let (tx, rx) = mpsc::channel();
    let mut count = 0;
    for &h in &snap.active {
        let harness = &snap.env.harnesses[h];
        let Some(binary) = harness.binary.clone() else { continue };
        let args: &'static [&'static str] = match harness.kind {
            Kind::Grok => &["inspect", "--json"],
            Kind::Kilo => &["debug", "skill"],
            Kind::Codex => &["debug", "prompt-input"],
            _ => continue,
        };
        count += 1;
        let (tx, scratch, kind) = (tx.clone(), scratch.clone(), harness.kind);
        thread::spawn(move || {
            let output = run_bounded_in(&binary, args, timeout, Some(&scratch));
            let _ = tx.send((h, args.join(" "), output.map(|text| parse(kind, &text))));
        });
    }
    drop(tx);
    let mut results: BTreeMap<usize, Probe> = BTreeMap::new();
    for _ in 0..count {
        let Ok((h, args, parsed)) = rx.recv_timeout(timeout + Duration::from_secs(2)) else { break };
        let harness = &snap.env.harnesses[h];
        let command = format!("{} {args}", harness.kind.binary());
        let (loaded, error) = match parsed {
            Some(Some(names)) => (Some(names), None),
            Some(None) => (None, Some("output was not in the expected format".to_string())),
            None => (None, Some(format!("did not answer within {}s", timeout.as_secs()))),
        };
        let mut mismatches = Vec::new();
        if let Some(names) = &loaded {
            for (s, skill) in snap.repo.skills.iter().enumerate() {
                let expected = snap.visible(s).contains(&h);
                let foreign = snap.foreign(s).contains(&h);
                let actual = names.contains(&skill.name);
                if expected && !actual {
                    mismatches.push(format!("expected {} to load {}, but it does not", harness.name, skill.name));
                } else if !expected && !foreign && actual {
                    mismatches.push(format!("{} loads a {} that Æ did not install", harness.name, skill.name));
                }
            }
        }
        results.insert(h, Probe { harness: harness.name.clone(), command, loaded, error, mismatches });
    }
    let _ = std::fs::remove_dir_all(&scratch);
    results.into_values().collect()
}

fn parse(kind: Kind, text: &str) -> Option<BTreeSet<String>> {
    match kind {
        Kind::Grok => {
            let json: serde_json::Value = serde_json::from_str(text.trim()).ok()?;
            let skills = json.get("skills")?.as_array()?;
            Some(skills.iter().filter_map(|s| s.get("name")?.as_str().map(str::to_string)).collect())
        }
        Kind::Kilo => {
            let start = text.find(['[', '{'])?;
            let json: serde_json::Value = serde_json::from_str(text[start..].trim()).ok()?;
            let mut names = BTreeSet::new();
            collect_named(&json, &mut names);
            Some(names)
        }
        Kind::Codex => {
            let json: serde_json::Value = serde_json::from_str(text.trim()).ok()?;
            let mut strings = Vec::new();
            collect_strings(&json, &mut strings);
            // The heading also appears in prose; the catalog is the one followed by list items.
            const HEADING: &str = "### Available skills\n";
            let body = strings
                .iter()
                .find_map(|s| s.match_indices(HEADING).map(|(at, _)| &s[at + HEADING.len()..]).find(|rest| rest.starts_with("- ")))?;
            Some(
                body.lines()
                    .take_while(|line| !line.starts_with("###"))
                    .filter_map(|line| line.strip_prefix("- ")?.split_once(':').map(|(name, _)| name.trim().to_string()))
                    .collect(),
            )
        }
        _ => None,
    }
}

fn collect_named(value: &serde_json::Value, names: &mut BTreeSet<String>) {
    match value {
        serde_json::Value::Array(items) => items.iter().for_each(|item| collect_named(item, names)),
        serde_json::Value::Object(map) => {
            if let (Some(name), true) = (map.get("name").and_then(|v| v.as_str()), map.contains_key("location")) {
                names.insert(name.to_string());
            }
            map.values().for_each(|item| collect_named(item, names));
        }
        _ => {}
    }
}

fn collect_strings(value: &serde_json::Value, out: &mut Vec<String>) {
    match value {
        serde_json::Value::String(text) => out.push(text.clone()),
        serde_json::Value::Array(items) => items.iter().for_each(|item| collect_strings(item, out)),
        serde_json::Value::Object(map) => map.values().for_each(|item| collect_strings(item, out)),
        _ => {}
    }
}

pub fn join(names: &[String]) -> String {
    match names.len() {
        0 => String::new(),
        1 => names[0].clone(),
        _ => format!("{} and {}", names[..names.len() - 1].join(", "), names[names.len() - 1]),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_each_harness_format() {
        let grok = r#"{"skills": [{"name": "context", "source": {"type": "user"}}]}"#;
        assert_eq!(parse(Kind::Grok, grok).unwrap(), BTreeSet::from(["context".to_string()]));
        let kilo = "log line\n[{\"name\": \"premortem\", \"location\": \"/h/.agents/skills/premortem/SKILL.md\"}]";
        assert_eq!(parse(Kind::Kilo, kilo).unwrap(), BTreeSet::from(["premortem".to_string()]));
        let codex = serde_json::json!([
            {"content": [{"text": "Skills are listed under \"### Available skills\".\n\nEach entry has a name."}]},
            {"content": [{"text": "intro\n### Available skills\n- context: Create CONTEXT.md (r1/context/SKILL.md)\n- wat: Explain (r0/wat/SKILL.md)\n### Next\n- not-a-skill: x"}]}
        ]);
        assert_eq!(parse(Kind::Codex, &codex.to_string()).unwrap(), BTreeSet::from(["context".to_string(), "wat".to_string()]));
    }
}

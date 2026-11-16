//! Detect coding harnesses and model where each one loads user skills from.
//!
//! The discovery model was checked against each harness's own introspection
//! (`grok inspect --json`, `kilo debug skill`, `codex debug prompt-input`, Pi's
//! skills documentation) rather than its README: Grok 1.0.70, for example, also
//! loads `~/.agents/skills`, which its README omits.

use crate::paths::{expand_tilde, tilde};
use serde::Serialize;
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::mpsc;
use std::thread;
use std::time::{Duration, Instant};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Kind {
    Claude,
    Codex,
    Grok,
    Pi,
    Kilo,
}

impl Kind {
    pub fn binary(self) -> &'static str {
        match self {
            Kind::Claude => "claude",
            Kind::Codex => "codex",
            Kind::Grok => "grok",
            Kind::Pi => "pi",
            Kind::Kilo => "kilo",
        }
    }
}

#[derive(Clone, Debug, Serialize)]
pub struct Harness {
    /// Stable selector, e.g. `claude-personal`.
    pub id: String,
    /// Display name, taken from T3 Code when it defines one.
    pub name: String,
    /// Short matrix column label.
    pub label: String,
    pub kind: Kind,
    pub home: PathBuf,
    /// Where the home came from: `T3 Code`, an environment variable, or `default`.
    pub origin: String,
    pub binary: Option<PathBuf>,
    pub detected: bool,
    /// T3 Code has this provider instance switched off.
    pub disabled: bool,
    /// User skill folders this harness loads, own folder first.
    pub skill_dirs: Vec<PathBuf>,
    pub version: Option<String>,
}

impl Harness {
    pub fn own_skills(&self) -> &Path {
        &self.skill_dirs[0]
    }
}

#[derive(Clone, Debug, Serialize)]
pub struct Orchestrator {
    pub name: String,
    pub settings: PathBuf,
    pub binary: Option<PathBuf>,
    pub version: Option<String>,
}

#[derive(Clone, Debug, Serialize)]
pub struct Environment {
    pub home: PathBuf,
    /// `~/.agents/skills`, the cross-harness Agent Skills folder.
    pub shared_skills: PathBuf,
    /// `~/.claude/skills`, which Grok and Kilo load for Claude Code compatibility.
    pub claude_compat: PathBuf,
    pub cargo_home: PathBuf,
    pub orchestrator: Option<Orchestrator>,
    pub harnesses: Vec<Harness>,
}

/// The process environment, captured so tests can supply their own.
#[derive(Clone, Debug, Default)]
pub struct Vars(pub HashMap<String, String>);

impl Vars {
    pub fn from_process() -> Self {
        Vars(std::env::vars().collect())
    }

    pub fn get(&self, key: &str) -> Option<&str> {
        self.0.get(key).map(String::as_str).filter(|value| !value.is_empty())
    }

    pub fn which(&self, program: &str) -> Option<PathBuf> {
        use std::os::unix::fs::PermissionsExt;
        self.get("PATH")?.split(':').filter(|dir| !dir.is_empty()).find_map(|dir| {
            let candidate = Path::new(dir).join(program);
            let meta = std::fs::metadata(&candidate).ok()?;
            (meta.is_file() && meta.permissions().mode() & 0o111 != 0).then_some(candidate)
        })
    }
}

impl Environment {
    pub fn detect(vars: &Vars) -> Environment {
        let home = PathBuf::from(vars.get("HOME").unwrap_or("/"));
        let shared_skills = home.join(".agents/skills");
        let claude_compat = home.join(".claude/skills");
        let cargo_home = vars.get("CARGO_HOME").map(PathBuf::from).unwrap_or_else(|| home.join(".cargo"));
        let t3_settings = home.join(".t3/userdata/settings.json");
        let t3: Option<serde_json::Value> = std::fs::read_to_string(&t3_settings).ok().and_then(|text| serde_json::from_str(&text).ok());
        let instances: Vec<(String, serde_json::Value)> = t3
            .as_ref()
            .and_then(|json| json.get("providerInstances"))
            .and_then(|value| value.as_object())
            .map(|map| map.iter().map(|(id, value)| (id.clone(), value.clone())).collect())
            .unwrap_or_default();
        let t3_instance = |driver: &str| -> Vec<&(String, serde_json::Value)> {
            instances.iter().filter(|(_, value)| value.get("driver").and_then(|v| v.as_str()) == Some(driver)).collect()
        };
        let display_name = |value: &serde_json::Value| value.get("displayName").and_then(|v| v.as_str()).map(str::to_string);
        let disabled = |value: &serde_json::Value| value.get("enabled").and_then(|v| v.as_bool()) == Some(false);

        let mut harnesses = Vec::new();
        let claude_binary = vars.which("claude");
        let claude_instances = t3_instance("claudeAgent");
        if claude_instances.is_empty() {
            let default_home = home.join(".claude");
            harnesses.push(claude("Claude Code", default_home.clone(), "default", false, &claude_binary));
            if let Some(dir) = vars.get("CLAUDE_CONFIG_DIR").map(|dir| expand_tilde(dir, &home))
                && dir != default_home
            {
                harnesses.push(claude("Claude Code (CLAUDE_CONFIG_DIR)", dir, "CLAUDE_CONFIG_DIR", false, &claude_binary));
            }
        } else {
            for (_, value) in claude_instances {
                let home_path = value
                    .get("config")
                    .and_then(|config| config.get("homePath"))
                    .and_then(|v| v.as_str())
                    .map(|raw| expand_tilde(raw, &home))
                    .unwrap_or_else(|| home.join(".claude"));
                let name = display_name(value).unwrap_or_else(|| "Claude Code".into());
                harnesses.push(claude(&name, home_path, "T3 Code", disabled(value), &claude_binary));
            }
        }

        let simple = |kind: Kind, default_name: &str, env_home: Option<(&str, PathBuf)>, fallback: PathBuf, driver: &str| {
            let (origin, home_dir) = match env_home {
                Some((var, dir)) => (var.to_string(), dir),
                None => ("default".to_string(), fallback),
            };
            let t3 = t3_instance(driver);
            let name = t3.first().and_then(|(_, value)| display_name(value)).unwrap_or_else(|| default_name.to_string());
            let binary = vars.which(kind.binary());
            let mut skill_dirs = vec![home_dir.join("skills"), shared_skills.clone()];
            if matches!(kind, Kind::Grok | Kind::Kilo) {
                skill_dirs.push(claude_compat.clone());
            }
            Harness {
                id: slug(default_name),
                label: String::new(),
                detected: binary.is_some() || home_dir.is_dir(),
                disabled: t3.first().is_some_and(|(_, value)| disabled(value)),
                name,
                kind,
                home: home_dir,
                origin,
                binary,
                skill_dirs,
                version: None,
            }
        };
        let env_dir = |var: &'static str| vars.get(var).map(|dir| (var, expand_tilde(dir, &home)));
        harnesses.push(simple(Kind::Codex, "Codex", env_dir("CODEX_HOME"), home.join(".codex"), "codex"));
        harnesses.push(simple(Kind::Grok, "Grok", env_dir("GROK_HOME"), home.join(".grok"), "grok"));
        let pi_dir = env_dir("PI_CODING_AGENT_DIR").or_else(|| env_dir("PI_AGENT_DIR"));
        harnesses.push(simple(Kind::Pi, "Pi", pi_dir, home.join(".pi/agent"), "pi"));
        let kilo_dir = env_dir("KILO_CONFIG_DIR")
            .or_else(|| vars.get("XDG_CONFIG_HOME").map(|dir| ("XDG_CONFIG_HOME", PathBuf::from(dir).join("kilo"))));
        harnesses.push(simple(Kind::Kilo, "Kilo", kilo_dir, home.join(".config/kilo"), "kilo"));

        assign_labels(&mut harnesses);
        let orchestrator =
            t3.map(|_| Orchestrator { name: "T3 Code".into(), settings: t3_settings, binary: vars.which("t3"), version: None });
        Environment { home, shared_skills, claude_compat, cargo_home, orchestrator, harnesses }
    }

    #[cfg(test)]
    pub fn harness(&self, id: &str) -> Option<usize> {
        self.harnesses.iter().position(|harness| harness.id == id)
    }

    pub fn tilde(&self, path: &Path) -> String {
        tilde(path, &self.home)
    }

    /// Ask each detected binary for its version, in parallel and bounded.
    pub fn probe_versions(&mut self, timeout: Duration) {
        let mut jobs: Vec<(Option<usize>, PathBuf)> = Vec::new();
        for (index, harness) in self.harnesses.iter().enumerate() {
            if let Some(binary) = &harness.binary {
                jobs.push((Some(index), binary.clone()));
            }
        }
        if let Some(binary) = self.orchestrator.as_ref().and_then(|o| o.binary.clone()) {
            jobs.push((None, binary));
        }
        let mut unique: Vec<PathBuf> = jobs.iter().map(|(_, binary)| binary.clone()).collect();
        unique.sort();
        unique.dedup();
        let (tx, rx) = mpsc::channel();
        for binary in unique {
            let tx = tx.clone();
            thread::spawn(move || {
                let version = run_bounded(&binary, &["--version"], timeout).and_then(|out| parse_version(&out));
                let _ = tx.send((binary, version));
            });
        }
        drop(tx);
        let deadline = Instant::now() + timeout + Duration::from_millis(250);
        let mut versions: HashMap<PathBuf, Option<String>> = HashMap::new();
        while let Ok((binary, version)) = rx.recv_timeout(deadline.saturating_duration_since(Instant::now())) {
            versions.insert(binary, version);
        }
        for (index, binary) in jobs {
            let version = versions.get(&binary).cloned().flatten();
            match index {
                Some(index) => self.harnesses[index].version = version,
                None => {
                    if let Some(orchestrator) = self.orchestrator.as_mut() {
                        orchestrator.version = version;
                    }
                }
            }
        }
    }
}

fn claude(name: &str, home: PathBuf, origin: &str, disabled: bool, binary: &Option<PathBuf>) -> Harness {
    Harness {
        id: slug(name),
        name: name.to_string(),
        label: String::new(),
        kind: Kind::Claude,
        detected: home.is_dir() || (origin == "default" && binary.is_some()),
        skill_dirs: vec![home.join("skills")],
        home,
        origin: origin.to_string(),
        binary: binary.clone(),
        disabled,
        version: None,
    }
}

/// `Claude Personal` → `claude-personal`.
pub fn slug(name: &str) -> String {
    let mut out = String::new();
    for c in name.chars() {
        if c.is_ascii_alphanumeric() {
            out.push(c.to_ascii_lowercase());
        } else if !out.ends_with('-') && !out.is_empty() {
            out.push('-');
        }
    }
    out.trim_end_matches('-').to_string()
}

fn assign_labels(harnesses: &mut [Harness]) {
    let mut used: Vec<String> = Vec::new();
    for harness in harnesses.iter_mut() {
        let base = match harness.kind {
            Kind::Claude => {
                let rest = harness.name.trim_start_matches("Claude").trim();
                let initial = rest.chars().find(|c| c.is_alphanumeric()).map(|c| c.to_ascii_uppercase());
                match initial {
                    Some(c) if !rest.starts_with('(') => format!("C{c}"),
                    _ => "CC".to_string(),
                }
            }
            Kind::Codex => "Cdx".into(),
            Kind::Grok => "Grk".into(),
            Kind::Pi => "Pi".into(),
            Kind::Kilo => "Klo".into(),
        };
        let mut label = base.clone();
        let mut n = 2;
        while used.contains(&label) {
            label = format!("{base}{n}");
            n += 1;
        }
        used.push(label.clone());
        harness.label = label;
    }
}

/// Run a program with a hard timeout and return its combined output.
pub fn run_bounded(program: &Path, args: &[&str], timeout: Duration) -> Option<String> {
    run_bounded_in(program, args, timeout, None)
}

pub fn run_bounded_in(program: &Path, args: &[&str], timeout: Duration, cwd: Option<&Path>) -> Option<String> {
    let mut command = Command::new(program);
    command.args(args).stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::piped());
    command.env("NO_COLOR", "1");
    if let Some(cwd) = cwd {
        command.current_dir(cwd);
    }
    let mut child = command.spawn().ok()?;
    let mut stdout = child.stdout.take()?;
    let mut stderr = child.stderr.take()?;
    let out = thread::spawn(move || {
        let mut buffer = String::new();
        let _ = std::io::Read::read_to_string(&mut stdout, &mut buffer);
        buffer
    });
    let err = thread::spawn(move || {
        let mut buffer = String::new();
        let _ = std::io::Read::read_to_string(&mut stderr, &mut buffer);
        buffer
    });
    let started = Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(_)) => break,
            Ok(None) if started.elapsed() < timeout => thread::sleep(Duration::from_millis(15)),
            _ => {
                let _ = child.kill();
                let _ = child.wait();
                return None;
            }
        }
    }
    let mut text = out.join().unwrap_or_default();
    text.push_str(&err.join().unwrap_or_default());
    Some(text)
}

/// The first `x.y.z`-style token in a `--version` banner.
pub fn parse_version(text: &str) -> Option<String> {
    text.split(|c: char| c.is_whitespace() || c == '(' || c == ')' || c == ',')
        .map(|token| token.trim_start_matches('v'))
        .find(|token| {
            let mut parts = token.split('.');
            parts.next().is_some_and(|p| !p.is_empty() && p.chars().all(|c| c.is_ascii_digit()))
                && parts.next().is_some_and(|p| p.chars().next().is_some_and(|c| c.is_ascii_digit()))
        })
        .map(str::to_string)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn vars(pairs: &[(&str, &str)]) -> Vars {
        Vars(pairs.iter().map(|(k, v)| (k.to_string(), v.to_string())).collect())
    }

    #[test]
    fn versions_parse_from_common_banners() {
        assert_eq!(parse_version("2.1.318 (Claude Code)").as_deref(), Some("2.1.318"));
        assert_eq!(parse_version("codex-cli 0.166.0").as_deref(), Some("0.166.0"));
        assert_eq!(parse_version("grok 1.0.70 (f50904eaee6c) [stable]").as_deref(), Some("1.0.70"));
        assert_eq!(parse_version("t3 v0.1.8-nightly.20261104.4165").as_deref(), Some("0.1.8-nightly.20261104.4165"));
        assert_eq!(parse_version("no version here"), None);
    }

    #[test]
    fn t3_instances_name_claude_homes_and_grok_reads_shared_and_claude_folders() {
        let dir = tempfile::tempdir().unwrap();
        let home = dir.path();
        std::fs::create_dir_all(home.join(".t3/userdata")).unwrap();
        std::fs::create_dir_all(home.join(".claude_personal")).unwrap();
        std::fs::write(
            home.join(".t3/userdata/settings.json"),
            r#"{"providerInstances": {
                "claudeAgent": {"driver": "claudeAgent", "displayName": "Claude Work", "config": {}},
                "claudeAgent_claude_personal": {"driver": "claudeAgent", "displayName": "Claude Personal",
                    "enabled": true, "config": {"homePath": "~/.claude_personal"}},
                "grok": {"driver": "grok", "displayName": "Grok", "enabled": true}}}"#,
        )
        .unwrap();
        let env = Environment::detect(&vars(&[("HOME", home.to_str().unwrap()), ("PATH", "")]));
        let ids: Vec<&str> = env.harnesses.iter().map(|h| h.id.as_str()).collect();
        assert_eq!(ids, ["claude-work", "claude-personal", "codex", "grok", "pi", "kilo"]);
        let labels: Vec<&str> = env.harnesses.iter().map(|h| h.label.as_str()).collect();
        assert_eq!(labels, ["CW", "CP", "Cdx", "Grk", "Pi", "Klo"]);
        let personal = &env.harnesses[1];
        assert_eq!(personal.home, home.join(".claude_personal"));
        assert!(personal.detected);
        assert!(!env.harnesses[0].detected, "missing ~/.claude and no binary");
        let grok = &env.harnesses[3];
        assert_eq!(grok.skill_dirs, [home.join(".grok/skills"), home.join(".agents/skills"), home.join(".claude/skills")]);
        assert_eq!(env.harnesses[2].skill_dirs, [home.join(".codex/skills"), home.join(".agents/skills")]);
    }

    #[test]
    fn environment_overrides_set_harness_homes() {
        let env = Environment::detect(&vars(&[
            ("HOME", "/h"),
            ("CODEX_HOME", "/c"),
            ("GROK_HOME", "~/g"),
            ("PI_AGENT_DIR", "/p"),
            ("XDG_CONFIG_HOME", "/x"),
            ("CLAUDE_CONFIG_DIR", "/h/.claude_alt"),
        ]));
        let homes: Vec<String> = env.harnesses.iter().map(|h| h.home.display().to_string()).collect();
        assert_eq!(homes, ["/h/.claude", "/h/.claude_alt", "/c", "/h/g", "/p", "/x/kilo"]);
        assert_eq!(env.harnesses[1].label, "CC2");
    }
}

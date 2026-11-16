//! Discover what this checkout can install: skills, Pi resources, and tools.

use serde::Serialize;
use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Clone, Debug, Serialize)]
pub struct Skill {
    pub name: String,
    pub dir: PathBuf,
    pub description: String,
    /// Short labels such as "T3 Code" or "/command only".
    pub tags: Vec<String>,
}

#[derive(Clone, Debug, Serialize)]
pub struct Tool {
    pub name: String,
    pub dir: PathBuf,
    pub version: Option<String>,
    pub description: Option<String>,
    pub bins: Vec<String>,
    pub locked: bool,
    /// Packages in Cargo.lock: an upper bound for build progress.
    pub packages: usize,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum PiKind {
    Policy,
    Command,
    Extension,
    Skill,
    Directory,
    File,
    Subagents,
}

impl PiKind {
    pub fn group(self) -> &'static str {
        match self {
            PiKind::Policy | PiKind::File => "Files",
            PiKind::Command => "Commands",
            PiKind::Extension => "Extensions",
            PiKind::Skill => "Pi skills",
            PiKind::Directory => "Directories",
            PiKind::Subagents => "Subagents",
        }
    }
}

#[derive(Clone, Debug, Serialize)]
pub struct PiItem {
    /// Selector used on the command line, e.g. `commands/flesh-out.md`.
    pub id: String,
    pub kind: PiKind,
    pub source: PathBuf,
    /// Destination relative to the Pi agent directory.
    pub target: PathBuf,
    pub description: Option<String>,
}

#[derive(Clone, Debug, Serialize)]
pub struct Repo {
    pub root: PathBuf,
    pub skills: Vec<Skill>,
    pub tools: Vec<Tool>,
    pub pi: Vec<PiItem>,
}

impl Repo {
    pub fn discover(root: &Path) -> Repo {
        Repo {
            root: root.to_path_buf(),
            skills: discover_skills(&root.join("skills")),
            tools: discover_tools(&root.join("tools")),
            pi: discover_pi(&root.join("harness/pi")),
        }
    }
}

/// Sorted, non-hidden entries of a directory.
fn entries(dir: &Path) -> Vec<PathBuf> {
    let mut found: Vec<PathBuf> = fs::read_dir(dir)
        .map(|read| {
            read.filter_map(Result::ok)
                .map(|entry| entry.path())
                .filter(|path| !path.file_name().is_some_and(|name| name.to_string_lossy().starts_with('.')))
                .collect()
        })
        .unwrap_or_default();
    found.sort();
    found
}

fn file_name(path: &Path) -> String {
    path.file_name().map(|name| name.to_string_lossy().into_owned()).unwrap_or_default()
}

fn discover_skills(dir: &Path) -> Vec<Skill> {
    entries(dir)
        .into_iter()
        .filter(|path| path.is_dir() && path.join("SKILL.md").is_file())
        .map(|path| {
            let text = fs::read_to_string(path.join("SKILL.md")).unwrap_or_default();
            let fields = frontmatter(&text);
            let description = fields.get("description").cloned().unwrap_or_default();
            let mut tags = Vec::new();
            if description.contains("T3 Code") {
                tags.push("T3 Code".to_string());
            }
            if fields.get("disable-model-invocation").is_some_and(|value| value == "true") {
                tags.push("/command".to_string());
            }
            if fields.get("user-invocable").is_some_and(|value| value == "false") {
                tags.push("auto".to_string());
            }
            Skill { name: file_name(&path), dir: path, description, tags }
        })
        .collect()
}

fn discover_tools(dir: &Path) -> Vec<Tool> {
    entries(dir)
        .into_iter()
        .filter(|path| path.is_dir() && path.join("Cargo.toml").is_file())
        .map(|path| {
            let manifest: toml::Table =
                fs::read_to_string(path.join("Cargo.toml")).ok().and_then(|text| text.parse().ok()).unwrap_or_default();
            let package = manifest.get("package").and_then(|value| value.as_table());
            let text = |key: &str| package.and_then(|p| p.get(key)).and_then(|v| v.as_str()).map(str::to_string);
            let name = text("name").unwrap_or_else(|| file_name(&path));
            let mut bins: Vec<String> = manifest
                .get("bin")
                .and_then(|value| value.as_array())
                .map(|bins| bins.iter().filter_map(|bin| bin.get("name").and_then(|v| v.as_str()).map(str::to_string)).collect())
                .unwrap_or_default();
            if bins.is_empty() {
                bins.push(name.clone());
            }
            let lock = fs::read_to_string(path.join("Cargo.lock")).ok();
            Tool {
                version: text("version"),
                description: text("description"),
                bins,
                locked: lock.is_some(),
                packages: lock.map(|lock| lock.matches("[[package]]").count()).unwrap_or(0),
                name,
                dir: path,
            }
        })
        .collect()
}

/// Pi discovers extensions as a directory exposing index.ts/index.js or a
/// package.json manifest.
fn is_extension(path: &Path) -> bool {
    path.is_dir() && (path.join("index.ts").is_file() || path.join("index.js").is_file() || path.join("package.json").is_file())
}

fn discover_pi(dir: &Path) -> Vec<PiItem> {
    let mut items = Vec::new();
    for component in entries(dir) {
        let name = file_name(&component);
        let nested = |kind: PiKind, target_dir: &str, eligible: &dyn Fn(&Path) -> bool| -> Vec<PiItem> {
            entries(&component)
                .into_iter()
                .filter(|path| eligible(path))
                .map(|path| {
                    let item = file_name(&path);
                    PiItem {
                        id: format!("{name}/{item}"),
                        kind,
                        description: describe(&path),
                        target: Path::new(target_dir).join(&item),
                        source: path,
                    }
                })
                .collect()
        };
        match name.as_str() {
            "subagents" if component.is_dir() => items.push(PiItem {
                id: name.clone(),
                kind: PiKind::Subagents,
                target: PathBuf::from("agents/reviewer.md"),
                description: Some("Owned reviewer agent plus strict same-model subagent policy".into()),
                source: component,
            }),
            // Pi calls the repository's command templates "prompts".
            "commands" if component.is_dir() => items.extend(nested(PiKind::Command, "prompts", &|_| true)),
            "extensions" if component.is_dir() => items.extend(nested(PiKind::Extension, "extensions", &is_extension)),
            "skills" if component.is_dir() => items.extend(nested(PiKind::Skill, "skills", &|_| true)),
            _ => items.push(PiItem {
                id: name.clone(),
                kind: if name == "APPEND_SYSTEM.md" {
                    PiKind::Policy
                } else if component.is_dir() {
                    PiKind::Directory
                } else {
                    PiKind::File
                },
                description: describe(&component),
                target: PathBuf::from(&name),
                source: component,
            }),
        }
    }
    items
}

/// A one-line description from frontmatter, package.json, or a README.
fn describe(path: &Path) -> Option<String> {
    let read = |file: &Path| fs::read_to_string(file).ok();
    if path.is_file() {
        let text = read(path)?;
        return frontmatter(&text).get("description").cloned().or_else(|| first_paragraph(&text));
    }
    if let Some(text) = read(&path.join("SKILL.md"))
        && let Some(description) = frontmatter(&text).get("description")
    {
        return Some(description.clone());
    }
    if let Some(description) = read(&path.join("package.json"))
        .and_then(|text| serde_json::from_str::<serde_json::Value>(&text).ok())
        .and_then(|json| json.get("description").and_then(|v| v.as_str()).map(str::to_string))
    {
        return Some(description);
    }
    ["README.md", "SPEC.md"].iter().find_map(|name| read(&path.join(name)).and_then(|text| first_paragraph(&text)))
}

fn first_paragraph(text: &str) -> Option<String> {
    let body = strip_frontmatter(text);
    let line = body
        .lines()
        .map(str::trim)
        .find(|line| !line.is_empty() && !line.starts_with('#') && !line.starts_with("```") && !line.starts_with('>'))?;
    Some(plain(line.trim_start_matches(['-', '*', ' '])))
}

/// Markdown to plain text for one-line summaries: `[text](url)` keeps the
/// text, and code and emphasis markers are dropped.
fn plain(line: &str) -> String {
    let mut out = String::with_capacity(line.len());
    let mut rest = line;
    while let Some(open) = rest.find('[') {
        let Some(close) = rest[open..].find("](").map(|i| open + i) else { break };
        let Some(end) = rest[close..].find(')').map(|i| close + i) else { break };
        out.push_str(&rest[..open]);
        out.push_str(&rest[open + 1..close]);
        rest = &rest[end + 1..];
    }
    out.push_str(rest);
    out.replace(['`', '*'], "")
}

fn strip_frontmatter(text: &str) -> &str {
    if let Some(rest) = text.strip_prefix("---\n")
        && let Some(end) = rest.find("\n---")
    {
        return &rest[end + 4..];
    }
    text
}

/// Parse the small YAML subset used by skill and command frontmatter:
/// top-level `key: value`, quoted values, and `|`/`>` block scalars. Values are
/// flattened to one line for display.
pub fn frontmatter(text: &str) -> BTreeMap<String, String> {
    let mut fields = BTreeMap::new();
    let mut lines = text.lines();
    if lines.next().map(str::trim_end) != Some("---") {
        return fields;
    }
    let body: Vec<&str> = lines.take_while(|line| line.trim_end() != "---").collect();
    let mut index = 0;
    while index < body.len() {
        let line = body[index];
        index += 1;
        if line.starts_with([' ', '\t']) || line.trim().is_empty() || line.trim_start().starts_with('#') {
            continue;
        }
        let Some((key, value)) = line.split_once(':') else { continue };
        let key = key.trim().to_string();
        let value = value.trim();
        let mut collected = Vec::new();
        if value.is_empty() || value.starts_with('|') || value.starts_with('>') {
            while index < body.len() && (body[index].starts_with([' ', '\t']) || body[index].trim().is_empty()) {
                collected.push(body[index].trim());
                index += 1;
            }
            if value.is_empty() {
                // A nested mapping such as `metadata:`; not a scalar.
                continue;
            }
        } else {
            collected.push(unquote(value));
        }
        let joined = collected.into_iter().filter(|part| !part.is_empty()).collect::<Vec<_>>().join(" ");
        fields.insert(key, joined);
    }
    fields
}

fn unquote(value: &str) -> &str {
    let bytes = value.as_bytes();
    if bytes.len() >= 2 && (bytes[0] == b'"' || bytes[0] == b'\'') && bytes[bytes.len() - 1] == bytes[0] {
        return &value[1..value.len() - 1];
    }
    value
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn frontmatter_handles_plain_quoted_and_block_values() {
        let text = "---\nname: one\nuser-invocable: false\nmetadata:\n  version: \"4\"\ndescription: |\n  First line\n  second line.\nlicense: \"MIT\"\n---\nBody\n";
        let fields = frontmatter(text);
        assert_eq!(fields["name"], "one");
        assert_eq!(fields["description"], "First line second line.");
        assert_eq!(plain("Runs [jg (jevgrep)](https://x.dev) via `code_search` **fast**"), "Runs jg (jevgrep) via code_search fast");
        assert_eq!(fields["license"], "MIT");
        assert_eq!(fields["user-invocable"], "false");
        assert!(!fields.contains_key("metadata"));
    }

    #[test]
    fn missing_frontmatter_is_empty() {
        assert!(frontmatter("# Title\n").is_empty());
    }
}

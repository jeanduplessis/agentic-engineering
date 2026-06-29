use std::{
    collections::BTreeMap,
    ffi::OsString,
    fs,
    path::{Path, PathBuf},
};

use anyhow::{Context, Result};
use path_clean::PathClean;
use serde::{Deserialize, Serialize};

pub const CONFIG_FILE_NAME: &str = ".gw.yml";
pub const CURRENT_VERSION: &str = "1.0";
pub const DEFAULT_BASE_DIR: &str = "../worktrees";

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(default)]
pub struct Config {
    pub version: String,
    pub defaults: Defaults,
    pub hooks: Hooks,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            version: CURRENT_VERSION.to_owned(),
            defaults: Defaults::default(),
            hooks: Hooks::default(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(default)]
pub struct Defaults {
    pub base_dir: PathBuf,
}

impl Default for Defaults {
    fn default() -> Self {
        Self {
            base_dir: DEFAULT_BASE_DIR.into(),
        }
    }
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(default)]
pub struct Hooks {
    pub post_create: Vec<Hook>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum Hook {
    Copy {
        from: PathBuf,
        to: PathBuf,
    },
    Symlink {
        from: PathBuf,
        to: PathBuf,
    },
    Command {
        command: String,
        #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
        env: BTreeMap<String, String>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        work_dir: Option<PathBuf>,
    },
}

impl Config {
    pub fn load(repo_root: impl AsRef<Path>) -> Result<Self> {
        let path = repo_root.as_ref().join(CONFIG_FILE_NAME);
        let contents = match fs::read(&path) {
            Ok(contents) => contents,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
                return Ok(Self::default());
            }
            Err(error) => {
                return Err(error).with_context(|| format!("failed to read {}", path.display()));
            }
        };

        serde_yaml::from_slice::<Option<Self>>(&contents)
            .context("failed to parse configuration")
            .map(Option::unwrap_or_default)
    }

    pub fn base_dir(&self, repo_root: impl AsRef<Path>) -> PathBuf {
        let repo_root = repo_root.as_ref();
        let base_dir = if self.defaults.base_dir.is_absolute() {
            self.defaults.base_dir.clone()
        } else {
            let absolute_root = if repo_root.is_absolute() {
                repo_root.to_path_buf()
            } else {
                std::env::current_dir()
                    .expect("current directory must be available")
                    .join(repo_root)
            };
            absolute_root.join(&self.defaults.base_dir)
        };
        normalize_absolute(base_dir)
    }
}

fn normalize_absolute(path: PathBuf) -> PathBuf {
    let cleaned = path.clean();
    let mut existing = cleaned.as_path();
    let mut missing = Vec::<OsString>::new();

    while !existing.exists() {
        let Some(name) = existing.file_name() else {
            return cleaned;
        };
        missing.push(name.to_os_string());
        let Some(parent) = existing.parent() else {
            return cleaned;
        };
        existing = parent;
    }

    let mut normalized = existing
        .canonicalize()
        .unwrap_or_else(|_| existing.to_path_buf());
    for component in missing.into_iter().rev() {
        normalized.push(component);
    }
    normalized.clean()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn defaults_apply_to_missing_config_and_fields() {
        let repo = tempfile::tempdir().unwrap();
        assert_eq!(Config::load(repo.path()).unwrap(), Config::default());

        fs::write(repo.path().join(CONFIG_FILE_NAME), "{}").unwrap();
        assert_eq!(Config::load(repo.path()).unwrap(), Config::default());
    }

    #[test]
    fn deserializes_tagged_yaml_hooks() {
        let config: Config = serde_yaml::from_str(
            r#"
hooks:
  post_create:
    - type: copy
      from: .env.example
      to: .env
    - type: symlink
      from: ../shared
      to: shared
    - type: command
      command: cargo test
      env:
        RUST_BACKTRACE: "1"
      work_dir: crates/core
"#,
        )
        .unwrap();

        assert_eq!(config.hooks.post_create.len(), 3);
        assert!(matches!(
            &config.hooks.post_create[0],
            Hook::Copy { from, to } if from == Path::new(".env.example") && to == Path::new(".env")
        ));
        assert!(matches!(
            &config.hooks.post_create[1],
            Hook::Symlink { from, to } if from == Path::new("../shared") && to == Path::new("shared")
        ));
        assert!(matches!(
            &config.hooks.post_create[2],
            Hook::Command { command, env, work_dir }
                if command == "cargo test"
                    && env.get("RUST_BACKTRACE").map(String::as_str) == Some("1")
                    && work_dir.as_deref() == Some(Path::new("crates/core"))
        ));
    }

    #[test]
    fn resolves_clean_absolute_paths() {
        let repo = tempfile::tempdir().unwrap();
        let config = Config {
            defaults: Defaults {
                base_dir: "./nested/../trees".into(),
            },
            ..Config::default()
        };

        let canonical_repo = repo.path().canonicalize().unwrap();
        assert_eq!(config.base_dir(repo.path()), canonical_repo.join("trees"));
    }
}

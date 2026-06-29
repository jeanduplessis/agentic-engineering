use std::path::{Path, PathBuf};

use anyhow::{Result, bail};
use path_clean::PathClean;

/// A worktree reported by `git worktree list --porcelain`.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Worktree {
    pub path: PathBuf,
    pub head: Option<String>,
    pub branch: Option<String>,
    pub detached: bool,
    pub locked: bool,
    pub prunable: bool,
}

impl Worktree {
    /// Returns whether this worktree is the repository's main worktree.
    pub fn is_main(&self, main_root: impl AsRef<Path>) -> bool {
        self.path.clean() == main_root.as_ref().clean()
    }

    /// Returns whether this worktree is managed by gw.
    pub fn is_managed(&self, main_root: impl AsRef<Path>, base_dir: impl AsRef<Path>) -> bool {
        let main_root = main_root.as_ref().clean();
        if self.path.clean() == main_root {
            return true;
        }

        self.path.clean().starts_with(base_dir.as_ref().clean())
    }

    /// Returns the name used to identify this worktree in user-facing output.
    pub fn display_name(&self, main_root: impl AsRef<Path>, base_dir: impl AsRef<Path>) -> String {
        let main_root = main_root.as_ref().clean();
        let path = self.path.clean();

        if path == main_root {
            return "@".to_owned();
        }

        path.strip_prefix(base_dir.as_ref().clean()).map_or_else(
            |_| self.path.to_string_lossy().into_owned(),
            |relative| relative.to_string_lossy().into_owned(),
        )
    }
}

#[derive(Default)]
struct WorktreeBuilder {
    path: Option<PathBuf>,
    head: Option<String>,
    branch: Option<String>,
    detached: bool,
    locked: bool,
    prunable: bool,
}

impl WorktreeBuilder {
    fn is_empty(&self) -> bool {
        self.path.is_none()
            && self.head.is_none()
            && self.branch.is_none()
            && !self.detached
            && !self.locked
            && !self.prunable
    }

    fn finish(self) -> Result<Option<Worktree>> {
        if self.is_empty() {
            return Ok(None);
        }

        let Some(path) = self.path else {
            bail!("worktree record is missing a path");
        };

        Ok(Some(Worktree {
            path,
            head: self.head,
            branch: self.branch,
            detached: self.detached,
            locked: self.locked,
            prunable: self.prunable,
        }))
    }
}

/// Parses output from `git worktree list --porcelain`.
pub fn parse_worktrees(output: &str) -> Result<Vec<Worktree>> {
    let mut worktrees = Vec::new();
    let mut current = WorktreeBuilder::default();

    for line in output.lines() {
        if line.is_empty() {
            if let Some(worktree) = std::mem::take(&mut current).finish()? {
                worktrees.push(worktree);
            }
            continue;
        }

        let (field, value) = line.split_once(' ').unwrap_or((line, ""));
        match field {
            "worktree" => {
                if current.path.is_some()
                    && let Some(worktree) = std::mem::take(&mut current).finish()?
                {
                    worktrees.push(worktree);
                }
                current.path = Some(PathBuf::from(value));
            }
            "HEAD" => current.head = Some(value.to_owned()),
            "branch" => {
                current.branch = Some(
                    value
                        .strip_prefix("refs/heads/")
                        .unwrap_or(value)
                        .to_owned(),
                );
            }
            "detached" => current.detached = true,
            "locked" => current.locked = true,
            "prunable" => current.prunable = true,
            _ => {}
        }
    }

    if let Some(worktree) = current.finish()? {
        worktrees.push(worktree);
    }

    Ok(worktrees)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_porcelain_records_and_strips_local_branch_prefix() {
        let output = "worktree /repos/project\nHEAD abc123\nbranch refs/heads/main\n\n\
                      worktree /repos/worktrees/feature with spaces\nHEAD def456\nbranch refs/heads/feature/test\nlocked maintenance reason\nprunable gitdir file points to non-existent location\n\n\
                      worktree /repos/worktrees/detached\nHEAD fedcba\ndetached\n";

        let worktrees = parse_worktrees(output).unwrap();

        assert_eq!(
            worktrees,
            vec![
                Worktree {
                    path: PathBuf::from("/repos/project"),
                    head: Some("abc123".to_owned()),
                    branch: Some("main".to_owned()),
                    detached: false,
                    locked: false,
                    prunable: false,
                },
                Worktree {
                    path: PathBuf::from("/repos/worktrees/feature with spaces"),
                    head: Some("def456".to_owned()),
                    branch: Some("feature/test".to_owned()),
                    detached: false,
                    locked: true,
                    prunable: true,
                },
                Worktree {
                    path: PathBuf::from("/repos/worktrees/detached"),
                    head: Some("fedcba".to_owned()),
                    branch: None,
                    detached: true,
                    locked: false,
                    prunable: false,
                },
            ]
        );
    }

    #[test]
    fn tolerates_unknown_fields_and_extra_blank_lines() {
        let output = "\nworktree /repos/project\nHEAD abc123\nbare\nfuture-field value\n\n\n";

        let worktrees = parse_worktrees(output).unwrap();

        assert_eq!(worktrees.len(), 1);
        assert_eq!(worktrees[0].path, PathBuf::from("/repos/project"));
    }

    #[test]
    fn finalizes_last_record_without_trailing_blank_line() {
        let worktrees = parse_worktrees("worktree /repos/project\nHEAD abc123").unwrap();

        assert_eq!(worktrees.len(), 1);
        assert_eq!(worktrees[0].head.as_deref(), Some("abc123"));
    }

    #[test]
    fn rejects_record_without_worktree_path() {
        let error = parse_worktrees("HEAD abc123\n").unwrap_err();

        assert_eq!(error.to_string(), "worktree record is missing a path");
    }

    #[test]
    fn identifies_main_and_managed_worktrees() {
        let main = worktree("/repos/project");
        let managed = worktree("/repos/worktrees/feature/auth");
        let unmanaged = worktree("/tmp/other");

        assert!(main.is_main("/repos/project"));
        assert!(main.is_managed("/repos/project", "/repos/worktrees"));
        assert!(!managed.is_main("/repos/project"));
        assert!(managed.is_managed("/repos/project", "/repos/worktrees"));
        assert!(!unmanaged.is_managed("/repos/project", "/repos/worktrees"));
    }

    #[test]
    fn displays_main_managed_and_unmanaged_names() {
        let main = worktree("/repos/project");
        let managed = worktree("/repos/project/.worktrees/feature/auth");
        let unmanaged = worktree("/tmp/other");

        assert_eq!(
            main.display_name("/repos/project", "/repos/project/.worktrees"),
            "@"
        );
        assert_eq!(
            managed.display_name("/repos/project", "/repos/project/.worktrees"),
            "feature/auth"
        );
        assert_eq!(
            unmanaged.display_name("/repos/project", "/repos/project/.worktrees"),
            "/tmp/other"
        );
    }

    #[test]
    fn cleans_paths_before_classifying_and_displaying_them() {
        let managed = worktree("/repos/project/../worktrees/feature/auth");

        assert!(managed.is_managed("/repos/project", "/repos/worktrees"));
        assert_eq!(
            managed.display_name("/repos/project", "/repos/worktrees"),
            "feature/auth"
        );
    }

    fn worktree(path: &str) -> Worktree {
        Worktree {
            path: PathBuf::from(path),
            head: None,
            branch: None,
            detached: false,
            locked: false,
            prunable: false,
        }
    }
}

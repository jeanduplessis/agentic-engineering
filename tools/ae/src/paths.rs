//! Path helpers: tilde display, lexical normalization, and symlink targets.

use std::path::{Component, Path, PathBuf};

/// Expand a leading `~` or `~/` against `home`.
pub fn expand_tilde(raw: &str, home: &Path) -> PathBuf {
    if raw == "~" {
        return home.to_path_buf();
    }
    if let Some(rest) = raw.strip_prefix("~/") {
        return home.join(rest);
    }
    PathBuf::from(raw)
}

/// Show a path relative to `home` as `~/…` for compact, familiar output.
pub fn tilde(path: &Path, home: &Path) -> String {
    if let Ok(rest) = path.strip_prefix(home) {
        if rest.as_os_str().is_empty() {
            return "~".to_string();
        }
        return format!("~/{}", rest.display());
    }
    path.display().to_string()
}

/// Remove `.` and resolve `..` without touching the filesystem.
pub fn normalize(path: &Path) -> PathBuf {
    let mut out = PathBuf::new();
    for component in path.components() {
        match component {
            Component::CurDir => {}
            Component::ParentDir => {
                if !out.pop() {
                    out.push("..");
                }
            }
            other => out.push(other.as_os_str()),
        }
    }
    out
}

/// The absolute, lexically normalized target of a symlink, or `None` when
/// `link` is not a symlink.
pub fn link_target(link: &Path) -> Option<PathBuf> {
    let target = std::fs::read_link(link).ok()?;
    let absolute = if target.is_absolute() { target } else { link.parent().unwrap_or_else(|| Path::new("/")).join(target) };
    Some(normalize(&absolute))
}

/// True when `path` exists as anything, including a dangling symlink.
pub fn occupied(path: &Path) -> bool {
    std::fs::symlink_metadata(path).is_ok()
}

/// Canonicalize when possible; otherwise normalize lexically.
pub fn canonical(path: &Path) -> PathBuf {
    std::fs::canonicalize(path).unwrap_or_else(|_| normalize(path))
}

/// The two spellings of a checkout root that a link may use.
#[derive(Clone, Debug)]
pub struct Roots {
    pub given: PathBuf,
    pub canonical: PathBuf,
}

impl Roots {
    pub fn new(root: &Path) -> Self {
        Self { given: normalize(root), canonical: canonical(root) }
    }

    /// True when `target` points inside this checkout.
    pub fn contains(&self, target: &Path) -> bool {
        target.starts_with(&self.given) || target.starts_with(&self.canonical) || canonical(target).starts_with(&self.canonical)
    }

    /// Map a target inside the checkout to the canonical spelling.
    pub fn to_canonical(&self, target: &Path) -> PathBuf {
        if let Ok(rest) = target.strip_prefix(&self.given) {
            return self.canonical.join(rest);
        }
        target.to_path_buf()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tilde_round_trips() {
        let home = Path::new("/Users/me");
        assert_eq!(tilde(Path::new("/Users/me/.claude"), home), "~/.claude");
        assert_eq!(tilde(home, home), "~");
        assert_eq!(tilde(Path::new("/opt/x"), home), "/opt/x");
        assert_eq!(expand_tilde("~/.claude_personal", home), PathBuf::from("/Users/me/.claude_personal"));
    }

    #[test]
    fn normalize_resolves_parents() {
        assert_eq!(normalize(Path::new("/a/b/../c/./d")), PathBuf::from("/a/c/d"));
    }
}

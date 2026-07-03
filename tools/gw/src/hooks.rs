use std::fs::{self, Metadata};
use std::os::unix::fs::{PermissionsExt, symlink};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

use anyhow::{Context, Result, bail};
use path_clean::PathClean;

use crate::config::{Config, Hook};

/// Runs configured post-create hooks in declaration order.
pub fn run_post_create(config: &Config, repo_root: &Path, worktree_path: &Path) -> Result<()> {
    for (index, hook) in config.hooks.post_create.iter().enumerate() {
        run_hook(hook, repo_root, worktree_path)
            .with_context(|| format!("post-create hook {} failed", index + 1))?;
    }
    Ok(())
}

fn run_hook(hook: &Hook, repo_root: &Path, worktree_path: &Path) -> Result<()> {
    match hook {
        Hook::Copy { from, to, optional } => {
            let source = resolve_source(repo_root, from);
            let destination = resolve_destination(worktree_path, to)?;
            copy_path(&source, &destination, worktree_path, *optional)
        }
        Hook::Symlink { from, to, optional } => {
            let source = resolve_source(repo_root, from);
            let destination = resolve_destination(worktree_path, to)?;
            create_symlink(&source, &destination, *optional)
        }
        Hook::Command {
            command,
            env,
            work_dir,
        } => {
            let work_dir = match work_dir {
                Some(path) => resolve_work_dir(worktree_path, path)?,
                None => worktree_path.to_path_buf(),
            };
            let status = Command::new("/bin/sh")
                .args(["-c", command])
                .current_dir(&work_dir)
                .envs(env)
                .env("GIT_GW_WORKTREE_PATH", worktree_path)
                .env("GIT_GW_REPO_ROOT", repo_root)
                .stdin(Stdio::inherit())
                .stdout(Stdio::inherit())
                .stderr(Stdio::inherit())
                .status()
                .with_context(|| format!("failed to run command hook in {}", work_dir.display()))?;
            if !status.success() {
                bail!("command hook exited with {status}");
            }
            Ok(())
        }
    }
}

fn resolve_source(repo_root: &Path, source: &Path) -> PathBuf {
    if source.is_absolute() {
        source.clean()
    } else {
        repo_root.join(source).clean()
    }
}

fn resolve_destination(worktree_path: &Path, destination: &Path) -> Result<PathBuf> {
    resolve_relative_contained(worktree_path, destination, "destination")
}

fn resolve_work_dir(worktree_path: &Path, work_dir: &Path) -> Result<PathBuf> {
    resolve_relative_contained(worktree_path, work_dir, "work_dir")
}

fn resolve_relative_contained(base: &Path, path: &Path, kind: &str) -> Result<PathBuf> {
    let base = base.clean();
    let resolved = if path.is_absolute() {
        path.clean()
    } else {
        base.join(path).clean()
    };
    if !resolved.starts_with(&base) {
        bail!(
            "{kind} {} escapes worktree {}",
            path.display(),
            base.display()
        );
    }

    let canonical_base = fs::canonicalize(&base)
        .with_context(|| format!("failed to resolve worktree {}", base.display()))?;
    let mut existing_ancestor = resolved.clone();
    loop {
        match fs::canonicalize(&existing_ancestor) {
            Ok(canonical_ancestor) => {
                if !canonical_ancestor.starts_with(&canonical_base) {
                    bail!(
                        "relative {kind} {} escapes worktree {} through a symlink",
                        path.display(),
                        base.display()
                    );
                }
                break;
            }
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
                if !existing_ancestor.pop() {
                    return Err(error).with_context(|| {
                        format!("failed to resolve relative {kind} {}", path.display())
                    });
                }
            }
            Err(error) => {
                return Err(error).with_context(|| {
                    format!("failed to resolve relative {kind} {}", path.display())
                });
            }
        }
    }

    Ok(resolved)
}

fn create_symlink(source: &Path, destination: &Path, optional: bool) -> Result<()> {
    if source_metadata(source, "symlink", optional)?.is_none() {
        return Ok(());
    }
    create_parent(destination)?;
    symlink(source, destination).with_context(|| {
        format!(
            "failed to create symlink {} -> {}",
            destination.display(),
            source.display()
        )
    })
}

fn copy_path(
    source: &Path,
    destination: &Path,
    worktree_path: &Path,
    optional: bool,
) -> Result<()> {
    resolve_destination(worktree_path, destination)?;
    let Some(metadata) = source_metadata(source, "copy", optional)? else {
        return Ok(());
    };
    if metadata.is_dir() {
        copy_directory(
            source,
            destination,
            worktree_path,
            metadata.permissions().mode(),
        )
    } else if metadata.is_file() {
        copy_file(source, destination, metadata.permissions().mode())
    } else {
        bail!("unsupported copy source type: {}", source.display());
    }
}

fn source_metadata(source: &Path, hook_type: &str, optional: bool) -> Result<Option<Metadata>> {
    match fs::metadata(source) {
        Ok(metadata) => Ok(Some(metadata)),
        Err(error) if optional && error.kind() == std::io::ErrorKind::NotFound => Ok(None),
        Err(error) => Err(error)
            .with_context(|| format!("failed to inspect {hook_type} source {}", source.display())),
    }
}

fn copy_directory(
    source: &Path,
    destination: &Path,
    worktree_path: &Path,
    mode: u32,
) -> Result<()> {
    create_parent(destination)?;
    match fs::create_dir(destination) {
        Ok(()) => {}
        Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => {
            let metadata = fs::metadata(destination).with_context(|| {
                format!("failed to inspect destination {}", destination.display())
            })?;
            if !metadata.is_dir() {
                return Err(error).with_context(|| {
                    format!("failed to create directory {}", destination.display())
                });
            }
        }
        Err(error) => {
            return Err(error)
                .with_context(|| format!("failed to create directory {}", destination.display()));
        }
    }

    for entry in fs::read_dir(source)
        .with_context(|| format!("failed to read directory {}", source.display()))?
    {
        let entry =
            entry.with_context(|| format!("failed to read entry in {}", source.display()))?;
        copy_path(
            &entry.path(),
            &destination.join(entry.file_name()),
            worktree_path,
            false,
        )?;
    }

    fs::set_permissions(destination, fs::Permissions::from_mode(mode)).with_context(|| {
        format!(
            "failed to preserve permissions on directory {}",
            destination.display()
        )
    })
}

fn copy_file(source: &Path, destination: &Path, mode: u32) -> Result<()> {
    create_parent(destination)?;
    fs::copy(source, destination).with_context(|| {
        format!(
            "failed to copy {} to {}",
            source.display(),
            destination.display()
        )
    })?;
    fs::set_permissions(destination, fs::Permissions::from_mode(mode)).with_context(|| {
        format!(
            "failed to preserve permissions on file {}",
            destination.display()
        )
    })
}

fn create_parent(path: &Path) -> Result<()> {
    let parent = path
        .parent()
        .with_context(|| format!("path has no parent: {}", path.display()))?;
    fs::create_dir_all(parent)
        .with_context(|| format!("failed to create directory {}", parent.display()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn relative_destination_must_stay_in_worktree() {
        let worktree = tempfile::tempdir().unwrap();

        assert_eq!(
            resolve_destination(worktree.path(), Path::new("config/app.yml")).unwrap(),
            worktree.path().join("config/app.yml")
        );
        assert!(resolve_destination(worktree.path(), Path::new("../outside")).is_err());
        assert!(resolve_destination(worktree.path(), Path::new("/tmp/outside")).is_err());
        assert!(resolve_work_dir(worktree.path(), Path::new("nested/../../outside")).is_err());
    }

    #[test]
    fn relative_destination_cannot_escape_through_symlink() {
        let worktree = tempfile::tempdir().unwrap();
        let outside = tempfile::tempdir().unwrap();
        symlink(outside.path(), worktree.path().join("escape")).unwrap();

        assert!(resolve_destination(worktree.path(), Path::new("escape/file")).is_err());
    }

    #[test]
    fn recursive_copy_cannot_escape_through_existing_destination_symlink() {
        let source_root = tempfile::tempdir().unwrap();
        let worktree = tempfile::tempdir().unwrap();
        let outside = tempfile::tempdir().unwrap();
        let source = source_root.path().join("source");
        fs::create_dir_all(source.join("nested")).unwrap();
        fs::write(source.join("nested/file"), "content").unwrap();
        fs::create_dir(worktree.path().join("destination")).unwrap();
        symlink(outside.path(), worktree.path().join("destination/nested")).unwrap();

        assert!(
            copy_path(
                &source,
                &worktree.path().join("destination"),
                worktree.path(),
                false
            )
            .is_err()
        );
        assert!(!outside.path().join("file").exists());
    }

    #[test]
    fn recursively_copies_files_and_preserves_permissions() {
        let source_root = tempfile::tempdir().unwrap();
        let destination_root = tempfile::tempdir().unwrap();
        let source = source_root.path().join("source");
        let nested = source.join("nested");
        fs::create_dir_all(&nested).unwrap();
        fs::write(nested.join("script"), "content").unwrap();
        fs::set_permissions(&source, fs::Permissions::from_mode(0o750)).unwrap();
        fs::set_permissions(nested.join("script"), fs::Permissions::from_mode(0o740)).unwrap();

        let destination = destination_root.path().join("destination");
        copy_path(&source, &destination, destination_root.path(), false).unwrap();

        assert_eq!(
            fs::read_to_string(destination.join("nested/script")).unwrap(),
            "content"
        );
        assert_eq!(
            fs::metadata(&destination).unwrap().permissions().mode() & 0o777,
            0o750
        );
        assert_eq!(
            fs::metadata(destination.join("nested/script"))
                .unwrap()
                .permissions()
                .mode()
                & 0o777,
            0o740
        );
    }

    #[test]
    fn optional_missing_copy_source_is_skipped() {
        let source_root = tempfile::tempdir().unwrap();
        let destination_root = tempfile::tempdir().unwrap();
        let destination = destination_root.path().join("destination");

        copy_path(
            &source_root.path().join("missing"),
            &destination,
            destination_root.path(),
            true,
        )
        .unwrap();

        assert!(!destination.exists());
    }

    #[test]
    fn missing_copy_source_still_fails_by_default() {
        let source_root = tempfile::tempdir().unwrap();
        let destination_root = tempfile::tempdir().unwrap();

        let error = copy_path(
            &source_root.path().join("missing"),
            &destination_root.path().join("destination"),
            destination_root.path(),
            false,
        )
        .unwrap_err();

        assert!(error.to_string().contains("failed to inspect copy source"));
    }
}

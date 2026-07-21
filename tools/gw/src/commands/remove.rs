use std::ffi::OsString;
use std::path::Path;

use anyhow::{Context, Result, bail};
use path_clean::PathClean;

use crate::cli::RemoveArgs;
use crate::config::Config;
use crate::git::{self, Repository};
use crate::worktree::Worktree;

pub fn run(args: &RemoveArgs) -> Result<()> {
    let repo = Repository::discover(
        std::env::current_dir().context("failed to access current directory")?,
    )?;
    let config = Config::load(&repo.main_root)?;
    let base_dir = config.base_dir(&repo.main_root);
    let worktrees = repo.worktrees();
    let targets = args
        .names
        .iter()
        .map(|name| find_target(worktrees, &repo, &base_dir, name))
        .collect::<Result<Vec<_>>>()?;

    for target in &targets {
        if is_current(&repo.cwd, &target.path) {
            bail!(
                "cannot remove worktree '{}' because it is currently active",
                target.display_name(&repo.main_root, &base_dir)
            );
        }
    }

    for target in targets {
        let display_name = target.display_name(&repo.main_root, &base_dir);
        let branch = target.branch.clone();
        remove_worktree(&repo, &target.path, args.force)?;
        println!(
            "Removed worktree '{display_name}' at {}",
            target.path.display()
        );

        if args.with_branch
            && let Some(branch) = branch
        {
            delete_branch(&repo, &branch, args.force_branch)?;
            println!("Removed branch '{branch}'");
        }
    }

    Ok(())
}

fn find_target<'a>(
    worktrees: &'a [Worktree],
    repo: &Repository,
    base_dir: &Path,
    name: &str,
) -> Result<&'a Worktree> {
    let direct = worktrees
        .iter()
        .filter(|worktree| {
            worktree.display_name(&repo.main_root, base_dir) == name
                || worktree.branch.as_deref() == Some(name)
        })
        .collect::<Vec<_>>();
    let matches = if direct.is_empty() {
        worktrees
            .iter()
            .filter(|worktree| {
                worktree
                    .path
                    .file_name()
                    .is_some_and(|basename| basename == name)
            })
            .collect::<Vec<_>>()
    } else {
        direct
    };

    if matches
        .iter()
        .any(|worktree| worktree.is_main(&repo.main_root))
    {
        bail!("cannot remove the main worktree");
    }
    let managed = matches
        .iter()
        .copied()
        .filter(|worktree| worktree.is_managed(&repo.main_root, base_dir))
        .collect::<Vec<_>>();
    match managed.as_slice() {
        [target] => Ok(target),
        [] if matches.is_empty() => bail!("worktree '{name}' not found"),
        [] => bail!("worktree '{name}' is not managed by gw"),
        _ => bail!("worktree name '{name}' is ambiguous"),
    }
}

fn remove_worktree(repo: &Repository, path: &Path, force: bool) -> Result<()> {
    let mut args = vec![OsString::from("worktree"), OsString::from("remove")];
    if force {
        args.push(OsString::from("--force"));
    }
    args.push(OsString::from("--"));
    args.push(path.as_os_str().to_owned());
    git::run(&repo.main_root, args)
        .with_context(|| format!("failed to remove worktree {}", path.display()))?;
    Ok(())
}

fn delete_branch(repo: &Repository, branch: &str, force: bool) -> Result<()> {
    let flag = if force { "-D" } else { "-d" };
    git::run(&repo.main_root, ["branch", flag, "--", branch])
        .with_context(|| format!("failed to remove branch '{branch}'"))?;
    Ok(())
}

fn is_current(cwd: &Path, worktree: &Path) -> bool {
    let cwd = cwd
        .canonicalize()
        .unwrap_or_else(|_| cwd.to_path_buf().clean());
    let worktree = worktree
        .canonicalize()
        .unwrap_or_else(|_| worktree.to_path_buf().clean());
    cwd.starts_with(worktree)
}

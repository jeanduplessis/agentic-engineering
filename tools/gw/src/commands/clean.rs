use std::collections::HashSet;
use std::ffi::OsString;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, bail};
use path_clean::PathClean;

use crate::config::Config;
use crate::git::{self, Repository};
use crate::worktree::Worktree;

pub fn run() -> Result<()> {
    let repo = Repository::discover(
        std::env::current_dir().context("failed to access current directory")?,
    )?;
    let config = Config::load(&repo.main_root)?;
    let worktrees = repo.worktrees();
    let base_branch = base_branch(&repo, worktrees)?;
    let merged = merged_branches(&repo, &base_branch)?;
    let base_dir = config.base_dir(&repo.main_root);

    let mut removed = 0;
    for worktree in worktrees.iter().filter(|worktree| {
        !worktree.is_main(&repo.main_root)
            && worktree.is_managed(&repo.main_root, &base_dir)
            && worktree
                .branch
                .as_ref()
                .is_some_and(|branch| branch != &base_branch && merged.contains(branch))
    }) {
        let name = worktree.display_name(&repo.main_root, &base_dir);
        if is_current(&repo.cwd, &worktree.path) {
            eprintln!("Warning: skipping worktree '{name}' because it is currently active");
            continue;
        }

        if let Err(error) = remove_worktree(&repo, &worktree.path) {
            eprintln!("Warning: failed to remove worktree '{name}': {error:#}");
            continue;
        }
        println!("Removed worktree '{name}' at {}", worktree.path.display());
        removed += 1;

        let branch = worktree
            .branch
            .as_deref()
            .expect("filtered worktree has branch");
        match delete_branch(&repo, branch) {
            Ok(()) => println!("Removed branch '{branch}'"),
            Err(error) => eprintln!("Warning: failed to remove branch '{branch}': {error:#}"),
        }
    }

    if removed == 0 {
        println!("No merged worktrees found");
    }
    Ok(())
}

fn base_branch(repo: &Repository, worktrees: &[Worktree]) -> Result<String> {
    if let Ok(origin_head) = git::run(
        &repo.main_root,
        [
            "symbolic-ref",
            "--quiet",
            "--short",
            "refs/remotes/origin/HEAD",
        ],
    ) && let Some(branch) = origin_head.strip_prefix("origin/")
        && !branch.is_empty()
    {
        return Ok(branch.to_owned());
    }

    for branch in ["main", "master"] {
        if repo.branch_exists(branch)? {
            return Ok(branch.to_owned());
        }
    }

    if let Some(branch) = worktrees
        .iter()
        .find(|worktree| worktree.is_main(&repo.main_root))
        .and_then(|worktree| worktree.branch.clone())
    {
        return Ok(branch);
    }
    bail!("could not determine base branch")
}

fn merged_branches(repo: &Repository, base_branch: &str) -> Result<HashSet<String>> {
    let output = git::run(
        &repo.main_root,
        [
            "for-each-ref",
            "--format=%(refname:short)",
            "--merged",
            base_branch,
            "refs/heads",
        ],
    )
    .with_context(|| format!("failed to list branches merged into '{base_branch}'"))?;
    Ok(output
        .lines()
        .map(str::trim)
        .filter(|branch| !branch.is_empty())
        .map(ToOwned::to_owned)
        .collect())
}

fn remove_worktree(repo: &Repository, path: &Path) -> Result<()> {
    let args = [
        OsString::from("worktree"),
        OsString::from("remove"),
        OsString::from("--"),
        path.as_os_str().to_owned(),
    ];
    git::run(&repo.main_root, args)
        .with_context(|| format!("failed to remove worktree {}", path.display()))?;
    Ok(())
}

fn delete_branch(repo: &Repository, branch: &str) -> Result<()> {
    git::run(&repo.main_root, ["branch", "-d", "--", branch])
        .with_context(|| format!("failed to remove branch '{branch}'"))?;
    Ok(())
}

fn is_current(cwd: &Path, worktree: &Path) -> bool {
    let cwd = cwd
        .canonicalize()
        .unwrap_or_else(|_| PathBuf::from(cwd).clean());
    let worktree = worktree
        .canonicalize()
        .unwrap_or_else(|_| PathBuf::from(worktree).clean());
    cwd.starts_with(worktree)
}

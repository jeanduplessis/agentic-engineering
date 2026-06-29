use std::ffi::OsStr;
use std::path::{Path, PathBuf};
use std::process::{Command, ExitStatus, Stdio};

use anyhow::{Context, Result, bail};

use crate::worktree::{Worktree, parse_worktrees};

#[derive(Debug)]
pub struct GitOutput {
    pub status: ExitStatus,
    pub stdout: String,
    pub stderr: String,
}

impl GitOutput {
    pub fn success(&self) -> bool {
        self.status.success()
    }
}

#[derive(Debug, Clone)]
pub struct Repository {
    pub cwd: PathBuf,
    pub main_root: PathBuf,
    worktrees: Vec<Worktree>,
}

impl Repository {
    pub fn discover(cwd: impl AsRef<Path>) -> Result<Self> {
        let cwd = cwd
            .as_ref()
            .canonicalize()
            .with_context(|| format!("failed to resolve {}", cwd.as_ref().display()))?;
        let worktrees = parse_worktrees(
            &run(&cwd, ["worktree", "list", "--porcelain"])
                .with_context(|| format!("{} is not inside a Git repository", cwd.display()))?,
        )?;
        let main_root = worktrees
            .first()
            .map(|worktree| worktree.path.clone())
            .context("Git repository has no main worktree")?;
        Ok(Self {
            cwd,
            main_root,
            worktrees,
        })
    }

    pub fn worktrees(&self) -> &[Worktree] {
        &self.worktrees
    }

    pub fn branch_exists(&self, branch: &str) -> Result<bool> {
        Ok(output(
            &self.main_root,
            [
                "show-ref",
                "--verify",
                "--quiet",
                &format!("refs/heads/{branch}"),
            ],
        )?
        .success())
    }

    pub fn validate_branch_name(&self, branch: &str) -> Result<()> {
        if output(&self.main_root, ["check-ref-format", "--branch", branch])?.success() {
            return Ok(());
        }
        bail!("invalid branch name: {branch}")
    }

    pub fn remote_matches(&self, branch: &str) -> Result<Vec<String>> {
        let pattern = format!("refs/remotes/*/{branch}");
        let stdout = run(
            &self.main_root,
            ["for-each-ref", "--format=%(refname:short)", &pattern],
        )?;
        let mut matches = stdout
            .lines()
            .map(str::trim)
            .filter(|line| !line.is_empty() && !line.ends_with("/HEAD"))
            .map(ToOwned::to_owned)
            .collect::<Vec<_>>();
        matches.sort();
        matches.dedup();
        Ok(matches)
    }
}

pub fn branches(cwd: &Path) -> Result<Vec<String>> {
    let stdout = run(
        cwd,
        [
            "for-each-ref",
            "--format=%(refname)",
            "refs/heads",
            "refs/remotes",
        ],
    )?;
    let mut branches = stdout
        .lines()
        .filter_map(normalize_completion_branch)
        .collect::<Vec<_>>();
    branches.sort();
    branches.dedup();
    Ok(branches)
}

fn normalize_completion_branch(reference: &str) -> Option<String> {
    if let Some(branch) = reference.strip_prefix("refs/heads/") {
        return Some(branch.to_owned());
    }
    let remote_branch = reference.strip_prefix("refs/remotes/")?;
    let (_, branch) = remote_branch.split_once('/')?;
    if branch == "HEAD" {
        return None;
    }
    Some(branch.to_owned())
}

pub fn output<I, S>(cwd: &Path, args: I) -> Result<GitOutput>
where
    I: IntoIterator<Item = S>,
    S: AsRef<OsStr>,
{
    let args = args.into_iter().collect::<Vec<_>>();
    let result = Command::new("git")
        .args(&args)
        .current_dir(cwd)
        .output()
        .with_context(|| format!("failed to run git in {}", cwd.display()))?;
    Ok(GitOutput {
        status: result.status,
        stdout: String::from_utf8_lossy(&result.stdout).trim().to_owned(),
        stderr: String::from_utf8_lossy(&result.stderr).trim().to_owned(),
    })
}

pub fn run<I, S>(cwd: &Path, args: I) -> Result<String>
where
    I: IntoIterator<Item = S>,
    S: AsRef<OsStr>,
{
    let result = output(cwd, args)?;
    if !result.success() {
        bail!("git command failed: {}", result.stderr);
    }
    Ok(result.stdout)
}

pub fn run_inherit<I, S>(cwd: &Path, args: I) -> Result<()>
where
    I: IntoIterator<Item = S>,
    S: AsRef<OsStr>,
{
    let status = Command::new("git")
        .args(args)
        .current_dir(cwd)
        .stdin(Stdio::inherit())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .status()
        .with_context(|| format!("failed to run git in {}", cwd.display()))?;
    if !status.success() {
        bail!("git command exited with {status}");
    }
    Ok(())
}

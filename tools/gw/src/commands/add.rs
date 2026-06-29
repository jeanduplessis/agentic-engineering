use std::env;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, bail};
use path_clean::PathClean;

use crate::cli::AddArgs;
use crate::config::Config;
use crate::git::{Repository, run_inherit};
use crate::hooks;

/// Creates a managed worktree and runs its post-create hooks.
pub fn run(args: &AddArgs) -> Result<()> {
    let cwd = env::current_dir().context("failed to access current directory")?;
    let repository = Repository::discover(&cwd)?;
    let config = Config::load(&repository.main_root)?;
    let request = AddRequest::resolve(args, &repository)?;
    let destination = destination_path(&config, &repository.main_root, &request.branch)?;

    create_worktree(&repository.main_root, &destination, &request)?;

    if let Err(error) = hooks::run_post_create(&config, &repository.main_root, &destination) {
        eprintln!("Warning: post-create hooks failed: {error:#}");
    }

    println!("{}", destination.display());
    Ok(())
}

#[derive(Debug, Eq, PartialEq)]
struct AddRequest {
    branch: String,
    start_point: Option<String>,
    tracking_remote: Option<String>,
    create: bool,
}

impl AddRequest {
    fn resolve(args: &AddArgs, repository: &Repository) -> Result<Self> {
        if let Some(branch) = args.new_branch.as_deref() {
            validate_worktree_name(branch)?;
            repository.validate_branch_name(branch)?;
            return Ok(Self {
                branch: branch.to_owned(),
                start_point: args.target.clone(),
                tracking_remote: None,
                create: true,
            });
        }

        let branch = args.target.as_deref().context(
            "branch name required: gw add <branch> | gw add -b <new-branch> [start-point]",
        )?;
        validate_worktree_name(branch)?;
        repository.validate_branch_name(branch)?;

        if repository.branch_exists(branch)? {
            return Ok(Self {
                branch: branch.to_owned(),
                start_point: None,
                tracking_remote: None,
                create: false,
            });
        }

        let remote_matches = repository.remote_matches(branch)?;
        match remote_matches.as_slice() {
            [] => Ok(Self {
                branch: branch.to_owned(),
                start_point: None,
                tracking_remote: None,
                create: true,
            }),
            [remote] => Ok(Self {
                branch: branch.to_owned(),
                start_point: None,
                tracking_remote: Some(remote.clone()),
                create: true,
            }),
            matches => bail!(
                "branch '{branch}' matches multiple remote branches: {}",
                matches.join(", ")
            ),
        }
    }
}

fn destination_path(config: &Config, repo_root: &Path, branch: &str) -> Result<PathBuf> {
    let base_dir = config.base_dir(repo_root);
    let destination = base_dir.join(branch).clean();
    if !destination.starts_with(&base_dir) || destination == base_dir {
        bail!(
            "branch name '{branch}' resolves outside configured worktree directory {}",
            base_dir.display()
        );
    }
    Ok(destination)
}

fn validate_worktree_name(branch: &str) -> Result<()> {
    if matches!(branch, "@" | "root") {
        bail!("branch name '{branch}' is reserved by gw");
    }
    Ok(())
}

fn create_worktree(repo_root: &Path, destination: &Path, request: &AddRequest) -> Result<()> {
    let destination = destination.as_os_str();

    match (
        &request.create,
        &request.tracking_remote,
        &request.start_point,
    ) {
        (false, _, _) => run_inherit(
            repo_root,
            [
                "worktree".as_ref(),
                "add".as_ref(),
                destination,
                request.branch.as_ref(),
            ],
        ),
        (true, Some(remote), _) => run_inherit(
            repo_root,
            [
                "worktree".as_ref(),
                "add".as_ref(),
                "-b".as_ref(),
                request.branch.as_ref(),
                "--track".as_ref(),
                destination,
                remote.as_ref(),
            ],
        ),
        (true, None, Some(start_point)) => run_inherit(
            repo_root,
            [
                "worktree".as_ref(),
                "add".as_ref(),
                "-b".as_ref(),
                request.branch.as_ref(),
                destination,
                start_point.as_ref(),
            ],
        ),
        (true, None, None) => run_inherit(
            repo_root,
            [
                "worktree".as_ref(),
                "add".as_ref(),
                "-b".as_ref(),
                request.branch.as_ref(),
                destination,
            ],
        ),
    }
    .with_context(|| {
        format!(
            "failed to create worktree for branch '{}' at {}",
            request.branch,
            destination.to_string_lossy()
        )
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn destination_must_remain_in_configured_base_directory() {
        let repo = tempfile::tempdir().unwrap();
        let config = Config::default();

        assert!(destination_path(&config, repo.path(), "feature/auth").is_ok());
        assert!(destination_path(&config, repo.path(), "../outside").is_err());
    }
}

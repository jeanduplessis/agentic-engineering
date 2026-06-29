use std::{env, path::Path};

use anyhow::Result;

use crate::{cli::ListArgs, config::Config, git::Repository, worktree::Worktree};

const SHORT_HEAD_LEN: usize = 8;

pub fn run(args: ListArgs) -> Result<()> {
    let repo = Repository::discover(env::current_dir()?)?;
    let config = Config::load(&repo.main_root)?;
    let base_dir = config.base_dir(&repo.main_root);
    let worktrees = repo.worktrees();

    if args.quiet {
        for worktree in worktrees {
            println!("{}", worktree.display_name(&repo.main_root, &base_dir));
        }
        return Ok(());
    }

    let rows = worktrees
        .iter()
        .map(|worktree| row(worktree, &repo, &base_dir))
        .collect::<Vec<_>>();

    if args.compact {
        println!("NAME\tSTATUS\tBRANCH\tHEAD");
        for row in rows {
            println!("{}\t{}\t{}\t{}", row.name, row.status, row.state, row.head);
        }
        return Ok(());
    }

    let name_width = rows
        .iter()
        .map(|row| row.name.len())
        .chain(["NAME".len()])
        .max()
        .unwrap_or_default();
    let status_width = rows
        .iter()
        .map(|row| row.status.len())
        .chain(["STATUS".len()])
        .max()
        .unwrap_or_default();
    let state_width = rows
        .iter()
        .map(|row| row.state.len())
        .chain(["BRANCH".len()])
        .max()
        .unwrap_or_default();

    println!(
        "{:<name_width$}  {:<status_width$}  {:<state_width$}  HEAD",
        "NAME", "STATUS", "BRANCH"
    );
    for row in rows {
        println!(
            "{:<name_width$}  {:<status_width$}  {:<state_width$}  {}",
            row.name, row.status, row.state, row.head
        );
    }

    Ok(())
}

struct Row {
    name: String,
    status: &'static str,
    state: String,
    head: String,
}

fn row(worktree: &Worktree, repo: &Repository, base_dir: &Path) -> Row {
    Row {
        name: worktree.display_name(&repo.main_root, base_dir),
        status: if worktree.is_managed(&repo.main_root, base_dir) {
            "managed"
        } else {
            "unmanaged"
        },
        state: if worktree.detached {
            "(detached HEAD)".to_owned()
        } else {
            worktree
                .branch
                .clone()
                .unwrap_or_else(|| "(no branch)".to_owned())
        },
        head: worktree
            .head
            .as_deref()
            .unwrap_or("-")
            .chars()
            .take(SHORT_HEAD_LEN)
            .collect(),
    }
}

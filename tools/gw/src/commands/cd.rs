use std::{env, path::Path};

use anyhow::{Result, bail};
use path_clean::PathClean;

use crate::{cli::CdArgs, config::Config, git::Repository, worktree::Worktree};

pub fn run(args: CdArgs) -> Result<()> {
    let repo = Repository::discover(env::current_dir()?)?;
    let config = Config::load(&repo.main_root)?;
    let base_dir = config.base_dir(&repo.main_root);
    let name = args.name.as_deref().unwrap_or("@");
    let worktrees = repo.worktrees();

    let target = resolve(name, worktrees, &repo.main_root, &base_dir)?
        .ok_or_else(|| anyhow::anyhow!("managed worktree not found: {name}"))?;
    println!("{}", target.path.clean().display());
    Ok(())
}

fn resolve<'a>(
    name: &str,
    worktrees: &'a [Worktree],
    main_root: &Path,
    base_dir: &Path,
) -> Result<Option<&'a Worktree>> {
    if name.is_empty() {
        return Ok(None);
    }

    if matches!(name, "@" | "root") {
        return Ok(worktrees
            .iter()
            .find(|worktree| worktree.is_main(main_root)));
    }

    let managed = worktrees
        .iter()
        .filter(|worktree| worktree.is_managed(main_root, base_dir))
        .collect::<Vec<_>>();
    let direct = managed
        .iter()
        .copied()
        .filter(|worktree| {
            worktree.display_name(main_root, base_dir) == name
                || worktree.branch.as_deref() == Some(name)
        })
        .collect::<Vec<_>>();
    if let Some(target) = unique_match(name, &direct)? {
        return Ok(Some(target));
    }

    let basename = managed
        .iter()
        .copied()
        .filter(|worktree| worktree.path.file_name().is_some_and(|base| base == name))
        .collect::<Vec<_>>();
    unique_match(name, &basename)
}

fn unique_match<'a>(name: &str, matches: &[&'a Worktree]) -> Result<Option<&'a Worktree>> {
    match matches {
        [] => Ok(None),
        [target] => Ok(Some(target)),
        _ => bail!("worktree name '{name}' is ambiguous"),
    }
}

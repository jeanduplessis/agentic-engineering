use std::env;

use anyhow::Result;

use crate::cli::CompleteArgs;
use crate::config::Config;
use crate::git::{self, Repository};

const ROOT_COMMANDS: &[&str] = &[
    "add",
    "list",
    "ls",
    "remove",
    "rm",
    "clean",
    "init",
    "cd",
    "completion",
    "hook",
    "shell-init",
];

pub fn run(args: &CompleteArgs) -> Result<()> {
    for candidate in candidates(&args.words)? {
        println!("{candidate}");
    }
    Ok(())
}

fn candidates(words: &[String]) -> Result<Vec<String>> {
    if words.is_empty() {
        return Ok(ROOT_COMMANDS
            .iter()
            .map(|value| (*value).to_owned())
            .collect());
    }

    let command = words[0].as_str();
    if words.len() == 1 && !ROOT_COMMANDS.contains(&command) {
        return Ok(filter(ROOT_COMMANDS.iter().copied(), command));
    }

    let current = words
        .get(1..)
        .and_then(|rest| rest.last())
        .map_or("", String::as_str);
    let values = match command {
        "add" => complete_add(current)?,
        "cd" => complete_worktrees(current, true)?,
        "remove" | "rm" => complete_worktrees(current, false)?,
        "list" | "ls" => filter(["--compact", "-c", "--quiet", "-q"], current),
        "completion" | "hook" | "shell-init" => filter(["zsh"], current),
        _ => Vec::new(),
    };
    Ok(values)
}

fn complete_add(current: &str) -> Result<Vec<String>> {
    if current.starts_with('-') {
        return Ok(filter(["--branch", "-b", "--cd"], current));
    }
    let cwd = env::current_dir()?;
    Ok(filter(
        git::branches(&cwd)?.iter().map(String::as_str),
        current,
    ))
}

fn complete_worktrees(current: &str, include_main: bool) -> Result<Vec<String>> {
    let repository = Repository::discover(env::current_dir()?)?;
    let config = Config::load(&repository.main_root)?;
    let base_dir = config.base_dir(&repository.main_root);
    let names = repository
        .worktrees()
        .iter()
        .filter(|worktree| {
            worktree.is_managed(&repository.main_root, &base_dir)
                && (include_main || !worktree.is_main(&repository.main_root))
        })
        .map(|worktree| worktree.display_name(&repository.main_root, &base_dir))
        .collect::<Vec<_>>();
    Ok(filter(names.iter().map(String::as_str), current))
}

fn filter<'a>(values: impl IntoIterator<Item = &'a str>, current: &str) -> Vec<String> {
    values
        .into_iter()
        .filter(|value| value.starts_with(current))
        .map(ToOwned::to_owned)
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn completes_root_commands_by_prefix() {
        assert_eq!(candidates(&["sh".to_owned()]).unwrap(), vec!["shell-init"]);
    }

    #[test]
    fn completes_zsh_only_shell_commands() {
        assert_eq!(candidates(&["completion".to_owned()]).unwrap(), vec!["zsh"]);
    }

    #[test]
    fn completes_add_flags_by_prefix() {
        assert_eq!(
            candidates(&["add".to_owned(), "--".to_owned()]).unwrap(),
            vec!["--branch", "--cd"]
        );
    }
}

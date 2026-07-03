use std::ffi::OsStr;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};

use tempfile::TempDir;

struct TestRepo {
    _temp: TempDir,
    root: PathBuf,
    repo: PathBuf,
}

impl TestRepo {
    fn new() -> Self {
        let temp = tempfile::tempdir().expect("create temporary directory");
        let root = temp.path().to_path_buf();
        let repo = root.join("repo");
        fs::create_dir(&repo).expect("create repository directory");

        git_success(&repo, ["init", "-b", "main"]);
        git_success(&repo, ["config", "user.name", "GW Integration Tests"]);
        git_success(&repo, ["config", "user.email", "gw-tests@example.com"]);
        git_success(&repo, ["config", "commit.gpgSign", "false"]);
        git_success(&repo, ["config", "core.hooksPath", "/dev/null"]);
        fs::write(repo.join("README.md"), "initial\n").expect("write initial file");
        git_success(&repo, ["add", "README.md"]);
        git_success(&repo, ["commit", "-m", "initial"]);

        Self {
            _temp: temp,
            root,
            repo,
        }
    }

    fn worktree(&self, name: &str) -> PathBuf {
        self.root.join("worktrees").join(name)
    }
}

#[test]
fn no_args_and_help_print_usage() {
    let temp = tempfile::tempdir().expect("create temporary directory");

    let no_args = gw_success(temp.path(), [] as [&str; 0]);
    let no_args_stdout = stdout(&no_args);
    assert!(no_args_stdout.contains("Personal Git worktree manager"));
    assert!(no_args_stdout.contains("Usage: gw [COMMAND]"));

    let help = gw_success(temp.path(), ["--help"]);
    let help_stdout = stdout(&help);
    assert!(help_stdout.contains("Personal Git worktree manager"));
    assert!(help_stdout.contains("Usage: gw [COMMAND]"));
    assert!(help_stdout.contains("Commands:"));
}

#[test]
fn init_from_nested_directory_writes_config_only_at_main_root() {
    let test_repo = TestRepo::new();
    let nested = test_repo.repo.join("nested/deeper");
    fs::create_dir_all(&nested).expect("create nested directory");

    gw_success(&nested, ["init"]);

    assert!(test_repo.repo.join(".gw.yml").is_file());
    assert!(!test_repo.repo.join("nested/.gw.yml").exists());
    assert!(!nested.join(".gw.yml").exists());
}

#[test]
fn add_list_and_cd_address_managed_worktree_by_branch_name() {
    let test_repo = TestRepo::new();
    let worktree = test_repo.worktree("feature/test");

    gw_success(&test_repo.repo, ["add", "feature/test"]);
    assert!(worktree.is_dir());

    let list = gw_success(&test_repo.repo, ["list", "--quiet"]);
    assert_eq!(
        stdout(&list).lines().collect::<Vec<_>>(),
        ["@", "feature/test"]
    );

    let cd = gw_success(&test_repo.repo, ["cd", "feature/test"]);
    assert_eq!(
        stdout(&cd).trim(),
        worktree.canonicalize().unwrap().display().to_string()
    );
}

#[test]
fn cd_rejects_ambiguous_basename() {
    let test_repo = TestRepo::new();
    gw_success(&test_repo.repo, ["add", "feature/shared"]);
    gw_success(&test_repo.repo, ["add", "bugfix/shared"]);

    let ambiguous = gw_output(&test_repo.repo, ["cd", "shared"]);

    assert!(!ambiguous.status.success());
    assert!(String::from_utf8_lossy(&ambiguous.stderr).contains("ambiguous"));
    assert!(
        gw_success(&test_repo.repo, ["cd", "feature/shared"])
            .status
            .success()
    );
}

#[test]
fn add_works_from_linked_worktree() {
    let test_repo = TestRepo::new();
    gw_success(&test_repo.repo, ["add", "feature/first"]);

    gw_success(
        &test_repo.worktree("feature/first"),
        ["add", "feature/second"],
    );

    assert!(test_repo.worktree("feature/second").is_dir());
}

#[test]
fn absolute_base_dir_is_managed_consistently() {
    let test_repo = TestRepo::new();
    let base_dir = test_repo.root.join("absolute-worktrees");
    fs::write(
        test_repo.repo.join(".gw.yml"),
        format!(
            "version: \"1.0\"\ndefaults:\n  base_dir: {}\n",
            base_dir.display()
        ),
    )
    .expect("write gw configuration");

    gw_success(&test_repo.repo, ["add", "feature/absolute"]);

    let list = gw_success(&test_repo.repo, ["list", "--quiet"]);
    assert!(stdout(&list).lines().any(|line| line == "feature/absolute"));
    assert_eq!(
        stdout(&gw_success(&test_repo.repo, ["cd", "feature/absolute"])).trim(),
        base_dir
            .canonicalize()
            .expect("canonicalize absolute base directory")
            .join("feature/absolute")
            .display()
            .to_string()
    );
}

#[test]
fn add_tracks_unique_remote_branch() {
    let test_repo = TestRepo::new();
    let remote = test_repo.root.join("remote.git");
    let remote_str = remote.to_str().expect("temporary path is UTF-8");
    git_success(&test_repo.root, ["init", "--bare", remote_str]);
    git_success(&test_repo.repo, ["remote", "add", "upstream", remote_str]);
    git_success(&test_repo.repo, ["push", "upstream", "main"]);
    git_success(&test_repo.repo, ["branch", "feature/remote"]);
    git_success(&test_repo.repo, ["push", "upstream", "feature/remote"]);
    git_success(&test_repo.repo, ["branch", "-D", "feature/remote"]);

    let completion = gw_success(&test_repo.repo, ["__complete", "add", "feature/"]);
    assert_eq!(stdout(&completion).trim(), "feature/remote");
    gw_success(&test_repo.repo, ["add", "feature/remote"]);

    assert!(test_repo.worktree("feature/remote").is_dir());
    assert_eq!(
        stdout(&git_success(
            &test_repo.repo,
            ["config", "branch.feature/remote.remote"]
        ))
        .trim(),
        "upstream"
    );
}

#[test]
fn add_rejects_invalid_branch_name() {
    let test_repo = TestRepo::new();

    let output = gw_output(&test_repo.repo, ["add", "-b", "branch..name"]);

    assert!(!output.status.success());
    assert!(String::from_utf8_lossy(&output.stderr).contains("invalid branch name"));

    let reserved = gw_output(&test_repo.repo, ["add", "@"]);
    assert!(!reserved.status.success());
    assert!(String::from_utf8_lossy(&reserved.stderr).contains("reserved by gw"));
}

#[test]
fn remove_rejects_main_and_current_worktrees() {
    let test_repo = TestRepo::new();
    let main_output = gw_output(&test_repo.repo, ["remove", "@"]);
    assert!(!main_output.status.success());
    assert!(test_repo.repo.is_dir());

    let worktree = test_repo.worktree("feature/current");
    gw_success(&test_repo.repo, ["add", "feature/current"]);
    let current_output = gw_output(&worktree, ["remove", "feature/current"]);
    assert!(!current_output.status.success());
    assert!(worktree.is_dir());
}

#[test]
fn zsh_shell_init_enables_cd_hook() {
    let test_repo = TestRepo::new();
    let worktree = test_repo.worktree("feature/zsh");
    gw_success(&test_repo.repo, ["add", "feature/zsh"]);
    let binary_dir = Path::new(env!("CARGO_BIN_EXE_gw"))
        .parent()
        .expect("binary has parent directory");
    let path = format!(
        "{}:{}",
        binary_dir.display(),
        std::env::var("PATH").unwrap_or_default()
    );

    let mut command = Command::new("zsh");
    command
        .args([
            "-fc",
            "autoload -Uz compinit; compinit; eval \"$(gw shell-init zsh)\"; gw cd feature/zsh; pwd",
        ])
        .current_dir(&test_repo.repo)
        .env("PATH", path);
    isolated_environment(&mut command);
    let output = assert_success(command.output().expect("run zsh"), "zsh");

    assert_eq!(
        stdout(&output).trim(),
        worktree.canonicalize().unwrap().display().to_string()
    );
}

#[test]
fn zsh_shell_init_enables_add_cd_hook() {
    let test_repo = TestRepo::new();
    let worktree = test_repo.worktree("feature/add-cd");
    let binary_dir = Path::new(env!("CARGO_BIN_EXE_gw"))
        .parent()
        .expect("binary has parent directory");
    let path = format!(
        "{}:{}",
        binary_dir.display(),
        std::env::var("PATH").unwrap_or_default()
    );

    let mut command = Command::new("zsh");
    command
        .args([
            "-fc",
            "autoload -Uz compinit; compinit; eval \"$(gw shell-init zsh)\"; gw add --cd feature/add-cd >/dev/null; pwd",
        ])
        .current_dir(&test_repo.repo)
        .env("PATH", path);
    isolated_environment(&mut command);
    let output = assert_success(command.output().expect("run zsh"), "zsh");

    assert_eq!(
        stdout(&output).trim(),
        worktree.canonicalize().unwrap().display().to_string()
    );
}

#[test]
fn remove_with_branch_removes_worktree_and_branch() {
    let test_repo = TestRepo::new();
    let worktree = test_repo.worktree("feature/test");
    gw_success(&test_repo.repo, ["add", "feature/test"]);

    gw_success(&test_repo.repo, ["remove", "--with-branch", "feature/test"]);

    assert!(!worktree.exists());
    assert!(!branch_exists(&test_repo.repo, "feature/test"));
}

#[test]
fn add_runs_post_create_copy_and_command_hooks() {
    let test_repo = TestRepo::new();
    fs::write(test_repo.repo.join(".env.example"), "FROM_TEMPLATE=yes\n")
        .expect("write copy source");
    fs::create_dir(test_repo.repo.join("shared")).expect("create symlink source");
    fs::write(test_repo.repo.join("shared/value.txt"), "shared\n").expect("write symlink source");
    fs::write(
        test_repo.repo.join(".gw.yml"),
        r#"version: "1.0"
defaults:
  base_dir: ../worktrees
hooks:
  post_create:
    - type: copy
      from: .env.example
      to: config/.env
    - type: symlink
      from: shared
      to: shared
    - type: command
      command: 'printf "%s" "$HOOK_VALUE" > hook-result.txt'
      env:
        HOOK_VALUE: command-ran
"#,
    )
    .expect("write gw configuration");

    gw_success(&test_repo.repo, ["add", "feature/hooks"]);

    let worktree = test_repo.worktree("feature/hooks");
    assert_eq!(
        fs::read_to_string(worktree.join("config/.env")).unwrap(),
        "FROM_TEMPLATE=yes\n"
    );
    assert!(
        fs::symlink_metadata(worktree.join("shared"))
            .unwrap()
            .file_type()
            .is_symlink()
    );
    assert_eq!(
        fs::read_to_string(worktree.join("shared/value.txt")).unwrap(),
        "shared\n"
    );
    assert_eq!(
        fs::read_to_string(worktree.join("hook-result.txt")).unwrap(),
        "command-ran"
    );
}

#[test]
fn optional_missing_post_create_source_is_skipped_and_later_hooks_run() {
    let test_repo = TestRepo::new();
    fs::write(test_repo.repo.join(".env.local"), "LOCAL=yes\n").expect("write copy source");
    fs::write(
        test_repo.repo.join(".gw.yml"),
        r#"version: "1.0"
defaults:
  base_dir: ../worktrees
hooks:
  post_create:
    - type: copy
      from: .env
      to: .env
      optional: true
    - type: copy
      from: .env.local
      to: .env.local
    - type: command
      command: 'printf "continued" > hook-result.txt'
"#,
    )
    .expect("write gw configuration");

    let output = gw_success(&test_repo.repo, ["add", "feature/optional-hooks"]);

    let worktree = test_repo.worktree("feature/optional-hooks");
    assert!(!worktree.join(".env").exists());
    assert_eq!(
        fs::read_to_string(worktree.join(".env.local")).unwrap(),
        "LOCAL=yes\n"
    );
    assert_eq!(
        fs::read_to_string(worktree.join("hook-result.txt")).unwrap(),
        "continued"
    );
    assert!(!stderr(&output).contains("post-create hooks failed"));
}

#[test]
fn clean_removes_merged_managed_worktree_but_keeps_unmerged_one() {
    let test_repo = TestRepo::new();
    let merged = test_repo.worktree("merged/test");
    let unmerged = test_repo.worktree("unmerged/test");
    gw_success(&test_repo.repo, ["add", "merged/test"]);
    gw_success(&test_repo.repo, ["add", "unmerged/test"]);

    fs::write(unmerged.join("unmerged.txt"), "branch-only change\n")
        .expect("write unmerged branch file");
    git_success(&unmerged, ["add", "unmerged.txt"]);
    git_success(&unmerged, ["commit", "-m", "unmerged change"]);

    gw_success(&test_repo.repo, ["clean"]);

    assert!(!merged.exists());
    assert!(!branch_exists(&test_repo.repo, "merged/test"));
    assert!(unmerged.is_dir());
    assert!(branch_exists(&test_repo.repo, "unmerged/test"));
}

fn gw_success<I, S>(cwd: &Path, args: I) -> Output
where
    I: IntoIterator<Item = S>,
    S: AsRef<OsStr>,
{
    assert_success(gw_output(cwd, args), "gw")
}

fn gw_output<I, S>(cwd: &Path, args: I) -> Output
where
    I: IntoIterator<Item = S>,
    S: AsRef<OsStr>,
{
    let mut command = Command::new(env!("CARGO_BIN_EXE_gw"));
    command.args(args).current_dir(cwd);
    isolated_environment(&mut command);
    command.output().expect("run gw")
}

fn git_success<I, S>(cwd: &Path, args: I) -> Output
where
    I: IntoIterator<Item = S>,
    S: AsRef<OsStr>,
{
    assert_success(git_output(cwd, args), "git")
}

fn git_output<I, S>(cwd: &Path, args: I) -> Output
where
    I: IntoIterator<Item = S>,
    S: AsRef<OsStr>,
{
    let mut command = Command::new("git");
    command.args(args).current_dir(cwd);
    isolated_environment(&mut command);
    command.output().expect("run git")
}

fn branch_exists(repo: &Path, branch: &str) -> bool {
    git_output(
        repo,
        [
            "show-ref",
            "--verify",
            "--quiet",
            &format!("refs/heads/{branch}"),
        ],
    )
    .status
    .success()
}

fn isolated_environment(command: &mut Command) {
    command
        .env("GIT_CONFIG_GLOBAL", "/dev/null")
        .env("GIT_CONFIG_NOSYSTEM", "1")
        .env("LC_ALL", "C");
}

fn assert_success(output: Output, program: &str) -> Output {
    assert!(
        output.status.success(),
        "{program} failed with {}\nstdout:\n{}\nstderr:\n{}",
        output.status,
        stdout(&output),
        String::from_utf8_lossy(&output.stderr)
    );
    output
}

fn stdout(output: &Output) -> String {
    String::from_utf8_lossy(&output.stdout).into_owned()
}

fn stderr(output: &Output) -> String {
    String::from_utf8_lossy(&output.stderr).into_owned()
}

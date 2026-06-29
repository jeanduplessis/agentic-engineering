use std::fs;
use std::path::Path;
use std::process::Command as StdCommand;

use assert_cmd::Command;
use tempfile::TempDir;

fn init_repo() -> TempDir {
    let dir = TempDir::new().expect("temp dir");
    git(dir.path(), &["init", "-b", "main"]);
    git(dir.path(), &["config", "user.email", "test@example.com"]);
    git(dir.path(), &["config", "user.name", "Test User"]);
    dir
}

fn git(dir: &Path, args: &[&str]) -> String {
    let output = StdCommand::new("git")
        .arg("-C")
        .arg(dir)
        .args(args)
        .output()
        .unwrap_or_else(|error| panic!("failed to run git {args:?}: {error}"));
    assert!(
        output.status.success(),
        "git {args:?} failed\nstdout:\n{}\nstderr:\n{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    String::from_utf8(output.stdout).expect("git stdout utf8")
}

fn git_with_config(dir: &Path, args: &[&str]) -> String {
    let output = StdCommand::new("git")
        .arg("-C")
        .arg(dir)
        .args(["-c", "protocol.file.allow=always"])
        .args(args)
        .output()
        .unwrap_or_else(|error| panic!("failed to run git {args:?}: {error}"));
    assert!(
        output.status.success(),
        "git {args:?} failed\nstdout:\n{}\nstderr:\n{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    String::from_utf8(output.stdout).expect("git stdout utf8")
}

fn write(path: impl AsRef<Path>, content: impl AsRef<[u8]>) {
    let path = path.as_ref();
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).expect("create parent dir");
    }
    fs::write(path, content).expect("write file");
}

fn commit_all(dir: &Path, message: &str) {
    git(dir, &["add", "-A"]);
    git(dir, &["commit", "-m", message]);
}

fn expected_latest_commit_line(dir: &Path, subject: &str) -> String {
    let short_hash = git(dir, &["rev-parse", "--short", "HEAD"]);
    format!("Commit: {} {subject}", short_hash.trim())
}

fn gs_output(dir: &Path, args: &[&str]) -> String {
    let output = Command::cargo_bin("gs")
        .expect("gs binary")
        .args(args)
        .current_dir(dir)
        .output()
        .expect("run gs");
    assert!(
        output.status.success(),
        "gs failed\nstdout:\n{}\nstderr:\n{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stderr), "");
    String::from_utf8(output.stdout).expect("stdout utf8")
}

#[test]
fn clean_repository_output_and_outside_repository_error_are_user_visible() {
    let repo = init_repo();
    write(repo.path().join("README.md"), "# project\n");
    commit_all(repo.path(), "initial\n\nbody details");
    let commit = expected_latest_commit_line(repo.path(), "initial");

    Command::cargo_bin("gs")
        .expect("gs binary")
        .arg("--color=never")
        .current_dir(repo.path())
        .assert()
        .success()
        .stdout(format!(
            " ───────────────────────\n Branch: main ↑0 ↓0\n {commit}\n ───────────────────────\n ✓ working tree clean\n"
        ))
        .stderr("");

    let outside = TempDir::new().expect("outside temp dir");
    Command::cargo_bin("gs")
        .expect("gs binary")
        .current_dir(outside.path())
        .assert()
        .failure()
        .code(1)
        .stdout("")
        .stderr("gs: not a git repository\n");
}

#[test]
fn untracked_text_files_are_root_relative_sorted_counted_and_ignore_ignored_files() {
    let repo = init_repo();
    write(repo.path().join(".gitignore"), "ignored.log\n");
    commit_all(repo.path(), "ignore rules");

    write(repo.path().join("zeta.txt"), "z1\nz2\n");
    write(repo.path().join("src/alpha.txt"), "a1\na2\na3");
    write(repo.path().join("ignored.log"), "noise\n");
    fs::create_dir_all(repo.path().join("src/nested")).expect("subdir");

    let commit = expected_latest_commit_line(repo.path(), "ignore rules");
    let output = gs_output(&repo.path().join("src/nested"), &["--color=never"]);
    assert_eq!(
        output,
        format!(
            " ────────────────────────────\n Branch: main       ↑0 ↓0\n {commit}\n ────────────────────────────\n Untracked (2)\n   ? src/alpha.txt  +3/-0\n   ? zeta.txt       +2/-0\n"
        )
    );
}

#[test]
fn unstaged_tracked_modifications_and_deletions_render_in_tracked_section() {
    let repo = init_repo();
    write(repo.path().join("delete.txt"), "gone\n");
    write(repo.path().join("modify.txt"), "old\nkeep\n");
    commit_all(repo.path(), "initial");

    fs::remove_file(repo.path().join("delete.txt")).expect("delete file");
    write(repo.path().join("modify.txt"), "new\nkeep\nadded\n");

    let commit = expected_latest_commit_line(repo.path(), "initial");
    let output = gs_output(repo.path(), &["--color=never"]);
    assert_eq!(
        output,
        format!(
            " ───────────────────────\n Branch: main    ↑0 ↓0\n {commit}\n ───────────────────────\n Tracked (2)\n   D delete.txt  +0/-1\n   M modify.txt  +2/-1\n"
        )
    );
}

#[test]
fn staged_add_modify_delete_use_index_stats_separate_from_worktree_stats() {
    let repo = init_repo();
    write(repo.path().join("delete.txt"), "remove me\n");
    write(repo.path().join("modify.txt"), "old\nkeep\n");
    commit_all(repo.path(), "initial");

    write(repo.path().join("added.txt"), "one\ntwo\n");
    fs::remove_file(repo.path().join("delete.txt")).expect("delete file");
    write(repo.path().join("modify.txt"), "new\nkeep\n");
    git(repo.path(), &["add", "-A"]);
    write(repo.path().join("modify.txt"), "new\nkeep\nunstaged\n");

    let commit = expected_latest_commit_line(repo.path(), "initial");
    let output = gs_output(repo.path(), &["--color=never"]);
    assert_eq!(
        output,
        format!(
            " ───────────────────────\n Branch: main    ↑0 ↓0\n {commit}\n ───────────────────────\n Staged (3)\n   A added.txt   +2/-0\n   D delete.txt  +0/-1\n   M modify.txt  +1/-1\n\n Tracked (1)\n   M modify.txt  +1/-0\n"
        )
    );
}

#[test]
fn partially_staged_file_renders_once_per_section_with_separate_stats() {
    let repo = init_repo();
    write(repo.path().join("partial.txt"), "a\nb\nc\n");
    commit_all(repo.path(), "initial");

    write(repo.path().join("partial.txt"), "a\nb staged\nc\n");
    git(repo.path(), &["add", "partial.txt"]);
    write(
        repo.path().join("partial.txt"),
        "a\nb staged\nc\nunstaged\n",
    );

    let commit = expected_latest_commit_line(repo.path(), "initial");
    let output = gs_output(repo.path(), &["--color=never"]);
    assert_eq!(
        output,
        format!(
            " ───────────────────────\n Branch: main     ↑0 ↓0\n {commit}\n ───────────────────────\n Staged (1)\n   M partial.txt  +1/-1\n\n Tracked (1)\n   M partial.txt  +1/-0\n"
        )
    );
}

#[test]
fn staged_renames_render_old_to_new_and_sort_by_destination_path() {
    let repo = init_repo();
    write(repo.path().join("aaa-old.txt"), "same\ncontent\n");
    commit_all(repo.path(), "initial");

    git(repo.path(), &["mv", "aaa-old.txt", "zzz-new.txt"]);
    write(repo.path().join("mmm.txt"), "middle\n");
    git(repo.path(), &["add", "mmm.txt"]);

    let commit = expected_latest_commit_line(repo.path(), "initial");
    let output = gs_output(repo.path(), &["--color=never"]);
    assert_eq!(
        output,
        format!(
            " ─────────────────────────────────────\n Branch: main                    ↑0 ↓0\n {commit}\n ─────────────────────────────────────\n Staged (2)\n   A mmm.txt                     +1/-0\n   R aaa-old.txt -> zzz-new.txt  +0/-0\n"
        )
    );
}

#[test]
fn binary_files_render_unknown_stats() {
    let repo = init_repo();
    write(repo.path().join("tracked.bin"), [0, 1, 2, 3]);
    commit_all(repo.path(), "initial");

    write(repo.path().join("tracked.bin"), [0, 1, 9, 3]);
    write(repo.path().join("new.bin"), [0, 159, 146, 150]);

    let commit = expected_latest_commit_line(repo.path(), "initial");
    let output = gs_output(repo.path(), &["--color=never"]);
    assert_eq!(
        output,
        format!(
            " ───────────────────────\n Branch: main     ↑0 ↓0\n {commit}\n ───────────────────────\n Tracked (1)\n   M tracked.bin  +?/-?\n\n Untracked (1)\n   ? new.bin      +?/-?\n"
        )
    );
}

#[test]
fn branch_header_renders_upstream_divergence_and_detached_head() {
    let repo = init_repo();
    write(repo.path().join("file.txt"), "initial\n");
    commit_all(repo.path(), "initial");

    let remote = TempDir::new().expect("remote temp dir");
    git(remote.path(), &["init", "--bare"]);
    git(
        repo.path(),
        &["remote", "add", "origin", remote.path().to_str().unwrap()],
    );
    git(repo.path(), &["push", "-u", "origin", "main"]);

    write(repo.path().join("local.txt"), "local\n");
    commit_all(repo.path(), "local ahead");

    let other = TempDir::new().expect("other temp dir");
    git_with_config(
        other.path(),
        &["clone", remote.path().to_str().unwrap(), "clone"],
    );
    let other_clone = other.path().join("clone");
    git(&other_clone, &["config", "user.email", "other@example.com"]);
    git(&other_clone, &["config", "user.name", "Other User"]);
    write(other_clone.join("remote.txt"), "remote\n");
    commit_all(&other_clone, "remote behind");
    git(&other_clone, &["push", "origin", "main"]);

    git(repo.path(), &["fetch", "origin"]);
    let commit = expected_latest_commit_line(repo.path(), "local ahead");
    let output = gs_output(repo.path(), &["--color=never"]);
    assert_eq!(
        output,
        format!(
            " ───────────────────────────\n Branch: main ↑1 ↓1\n {commit}\n ───────────────────────────\n ✓ working tree clean\n"
        )
    );

    let short = git(repo.path(), &["rev-parse", "--short", "HEAD"])
        .trim()
        .to_string();
    git(repo.path(), &["checkout", "--detach", "HEAD"]);
    let output = gs_output(repo.path(), &["--color=never"]);
    assert_eq!(
        output,
        format!(
            " ───────────────────────────\n detached @ {short}\n {commit}\n ───────────────────────────\n ✓ working tree clean\n"
        )
    );
}

#[test]
fn color_modes_control_ansi_output() {
    let repo = init_repo();
    write(repo.path().join("new.txt"), "hello\n");

    let plain = gs_output(repo.path(), &["--color=never"]);
    assert!(!plain.contains("\x1b["));
    assert!(!plain.contains("Commit:"));

    let forced = gs_output(repo.path(), &["--color=always"]);
    assert!(forced.contains(" Branch: \x1b[38;5;2mmain\x1b[0m"));
    assert!(forced.contains("\x1b[38;5;2m↑0\x1b[0m \x1b[38;5;1m↓0\x1b[0m"));
    assert!(forced.contains(" Untracked (1)\n"));
    assert!(forced.contains("\x1b[38;5;245m? new.txt\x1b[0m"));
    assert!(forced.contains("\x1b[38;5;2m+1\x1b[0m\x1b[38;5;244m/\x1b[0m\x1b[38;5;1m-0\x1b[0m"));

    let auto = gs_output(repo.path(), &["--color=auto"]);
    assert!(!auto.contains("\x1b["));
}

#[test]
fn submodule_path_level_changes_are_unknown_and_internal_changes_are_excluded() {
    let child = init_repo();
    write(child.path().join("inside.txt"), "inside\n");
    commit_all(child.path(), "child initial");

    let parent = init_repo();
    git_with_config(
        parent.path(),
        &[
            "submodule",
            "add",
            child.path().to_str().unwrap(),
            "vendor/sub",
        ],
    );

    let output = gs_output(parent.path(), &["--color=never"]);
    assert!(output.contains("Staged (2)"));
    assert!(output.contains("  A vendor/sub"), "{output}");
    assert!(output.contains("+?/-?"), "{output}");

    commit_all(parent.path(), "add submodule");
    let commit = expected_latest_commit_line(parent.path(), "add submodule");
    let submodule_path = parent.path().join("vendor/sub");
    write(submodule_path.join("inside.txt"), "dirty internal change\n");
    let output = gs_output(parent.path(), &["--color=never"]);
    assert_eq!(
        output,
        format!(
            " ─────────────────────────────\n Branch: main ↑0 ↓0\n {commit}\n ─────────────────────────────\n ✓ working tree clean\n"
        )
    );

    git(
        &submodule_path,
        &["config", "user.email", "sub@example.com"],
    );
    git(&submodule_path, &["config", "user.name", "Submodule User"]);
    commit_all(&submodule_path, "move submodule head");
    let output = gs_output(parent.path(), &["--color=never"]);
    assert_eq!(
        output,
        format!(
            " ─────────────────────────────\n Branch: main    ↑0 ↓0\n {commit}\n ─────────────────────────────\n Tracked (1)\n   M vendor/sub  +?/-?\n"
        )
    );
}

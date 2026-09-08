use std::ffi::OsString;
use std::fs;
use std::io;
use std::os::unix::ffi::OsStringExt;
use std::os::unix::fs::PermissionsExt;
use std::path::PathBuf;
use std::process::{Child, Command, Output, Stdio};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::thread;
use std::time::{Duration, Instant};

static NEXT_ID: AtomicUsize = AtomicUsize::new(0);

// Only shell builtins: PATH contains no system executables or real Pi.
const FAKE_PI: &str = r#"#!/bin/sh
printf '%s\000' "$@" > "$GENIE_TEST_DIR/args"
pwd -P > "$GENIE_TEST_DIR/cwd"
printf '%s\000' "$HOME" "$PI_CODING_AGENT_DIR" "$GENIE_TEST_INHERITED" > "$GENIE_TEST_DIR/env"
printf '%s' "$$" > "$GENIE_TEST_DIR/pid"
if IFS= read -r line; then
    printf 'unexpected stdin: %s\n' "$line" >&2
    exit 99
fi
printf 'eof' > "$GENIE_TEST_DIR/stdin"
if [ -n "$GENIE_TEST_STDOUT" ]; then
    printf '%s' "$GENIE_TEST_STDOUT"
else
    printf '%s\n' '{"type":"message_end","message":{"role":"assistant","stopReason":"stop","content":[]}}'
fi
printf '%s' "$GENIE_TEST_STDERR" >&2
if [ "$GENIE_TEST_BINARY" = yes ]; then
    printf '\376\000' >&2
fi
if [ "$GENIE_TEST_SIGNAL" = yes ]; then
    kill -TERM "$$"
fi
exit "${GENIE_TEST_STATUS:-0}"
"#;

struct Fixture {
    root: PathBuf,
}

impl Fixture {
    fn new() -> Self {
        let root = loop {
            let id = NEXT_ID.fetch_add(1, Ordering::Relaxed);
            let path = std::env::temp_dir().join(format!("genie-test-{}-{id}", std::process::id()));
            match fs::create_dir(&path) {
                Ok(()) => break fs::canonicalize(path).unwrap(),
                Err(error) if error.kind() == io::ErrorKind::AlreadyExists => continue,
                Err(error) => panic!("cannot create test directory: {error}"),
            }
        };
        for directory in ["bin", "home", "pi-state", "working directory"] {
            fs::create_dir(root.join(directory)).unwrap();
        }
        Self { root }
    }

    fn install_fake_pi(&self, mode: u32) {
        let path = self.root.join("bin/pi");
        fs::write(&path, FAKE_PI).unwrap();
        fs::set_permissions(path, fs::Permissions::from_mode(mode)).unwrap();
    }

    fn command(&self) -> Command {
        let mut command = Command::new(env!("CARGO_BIN_EXE_g"));
        command
            .env_clear()
            .env("PATH", self.root.join("bin"))
            .env("HOME", self.root.join("home"))
            .env("PI_CODING_AGENT_DIR", self.root.join("pi-state"))
            .env("PI_AGENT_DIR", self.root.join("pi-state"))
            .env("GENIE_TEST_DIR", &self.root)
            .env("GENIE_TEST_INHERITED", "inherited value with spaces 🧞")
            .current_dir(self.root.join("working directory"))
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        command
    }

    fn run(&self, args: &[&str]) -> Output {
        wait_for_output(self.command().args(args).spawn().unwrap())
    }

    fn pi_args(&self) -> Vec<String> {
        fs::read(self.root.join("args"))
            .unwrap()
            .strip_suffix(&[0])
            .unwrap()
            .split(|byte| *byte == 0)
            .map(|bytes| String::from_utf8(bytes.to_vec()).unwrap())
            .collect()
    }

    fn assert_request(&self, message: &str) {
        self.assert_selection(message, &[]);
    }

    fn assert_selection(&self, message: &str, options: &[&str]) {
        let args = self.pi_args();
        // Exact argv excludes unrequested overrides, session flags, and passthrough.
        let mut expected = vec!["--mode", "json"];
        expected.extend_from_slice(options);
        expected.push("--");
        assert_eq!(args.len(), expected.len() + 1);
        assert_eq!(&args[..expected.len()], expected);
        let prompt = args.last().unwrap();
        let (guidance, request) = prompt.split_once("\n\nUser request:\n").unwrap();
        assert!(!guidance.is_empty());
        assert!(!prompt.starts_with(['@', '/', '-']));
        assert_eq!(request, message);
    }

    fn assert_pi_not_started(&self) {
        assert!(!self.root.join("args").exists());
    }
}

impl Drop for Fixture {
    fn drop(&mut self) {
        fs::remove_dir_all(&self.root).unwrap();
    }
}

fn wait_for_output(mut child: Child) -> Output {
    // Leave the pipe open: inheriting stdin would block fake Pi's read. Bound all
    // subprocess tests so a regression fails instead of hanging the test suite.
    let _open_stdin = child.stdin.take();
    let deadline = Instant::now() + Duration::from_secs(5);
    loop {
        if child.try_wait().unwrap().is_some() {
            return child.wait_with_output().unwrap();
        }
        if Instant::now() >= deadline {
            child.kill().unwrap();
            let output = child.wait_with_output().unwrap();
            panic!("CLI did not exit within 5 seconds: {output:?}");
        }
        thread::sleep(Duration::from_millis(5));
    }
}

#[test]
fn multiword_request_uses_one_prompt_and_no_pi_overrides() {
    let fixture = Fixture::new();
    fixture.install_fake_pi(0o700);
    let output = fixture.run(&["find", "the", "login", "form"]);
    assert!(output.status.success());
    assert!(output.stdout.is_empty());
    assert!(output.stderr.is_empty());
    fixture.assert_request("find the login form");
}

#[test]
fn quoted_multiline_unicode_and_metacharacters_are_preserved_without_a_shell() {
    let fixture = Fixture::new();
    fixture.install_fake_pi(0o700);
    let words = [
        "  keep  spaces  ",
        "'single' and \"double\" quotes",
        "line one\nline two\t🧞 café 日本語",
        "$(touch injected); `touch injected`; * ? $HOME > injected && echo nope | cat",
        "",
    ];
    assert!(fixture.run(&words).status.success());
    fixture.assert_request(&words.join(" "));
    assert!(
        fs::read_dir(fixture.root.join("working directory"))
            .unwrap()
            .next()
            .is_none()
    );
}

#[test]
fn leading_pi_syntax_is_literal_request_text() {
    for message in [
        "@notes.md",
        "/review",
        "--model=other",
        "--help",
        "-V",
        "--",
    ] {
        let fixture = Fixture::new();
        fixture.install_fake_pi(0o700);
        assert!(fixture.run(&["--", message]).status.success());
        fixture.assert_request(message);
    }
    for message in ["@notes.md", "/review"] {
        let fixture = Fixture::new();
        fixture.install_fake_pi(0o700);
        assert!(fixture.run(&[message]).status.success());
        fixture.assert_request(message);
    }
}

#[test]
fn options_after_first_message_word_remain_literal() {
    let fixture = Fixture::new();
    fixture.install_fake_pi(0o700);
    let words = [
        "explain",
        "--help",
        "-h",
        "--version",
        "-V",
        "--",
        "--model=x",
        "--model",
        "provider/id",
        "--thinking",
        "not-a-level",
        "--quiet",
        "-q",
    ];
    assert!(fixture.run(&words).status.success());
    fixture.assert_request(&words.join(" "));
}

#[test]
fn quiet_is_wrapper_only_before_the_literal_boundary() {
    let fixture = Fixture::new();
    fixture.install_fake_pi(0o700);
    assert!(
        fixture
            .run(&["--quiet", "-q", "find", "--quiet"])
            .status
            .success()
    );
    fixture.assert_request("find --quiet");
    assert!(fixture.run(&["-q", "--", "--quiet"]).status.success());
    fixture.assert_request("--quiet");
}

#[test]
fn cwd_and_environment_are_inherited() {
    let fixture = Fixture::new();
    fixture.install_fake_pi(0o700);
    assert!(
        fixture
            .run(&["inspect", "this", "directory"])
            .status
            .success()
    );
    assert_eq!(
        fs::read_to_string(fixture.root.join("cwd")).unwrap(),
        format!("{}\n", fixture.root.join("working directory").display())
    );
    assert_eq!(
        fs::read(fixture.root.join("env")).unwrap(),
        format!(
            "{}\0{}\0inherited value with spaces 🧞\0",
            fixture.root.join("home").display(),
            fixture.root.join("pi-state").display()
        )
        .into_bytes()
    );
}

#[test]
fn stdin_is_eof_even_when_callers_pipe_stays_open() {
    let fixture = Fixture::new();
    fixture.install_fake_pi(0o700);
    assert!(fixture.run(&["find", "files"]).status.success());
    assert_eq!(fs::read(fixture.root.join("stdin")).unwrap(), b"eof");
}

#[test]
fn piped_content_is_not_read_or_added_to_request() {
    use std::io::Write;

    let fixture = Fixture::new();
    fixture.install_fake_pi(0o700);
    let mut child = fixture.command().args(["find", "files"]).spawn().unwrap();
    // A closed reader can race this write because the wrapper ignores stdin.
    if let Err(error) = child.stdin.as_mut().unwrap().write_all(b"not a request\n") {
        assert_eq!(error.kind(), io::ErrorKind::BrokenPipe);
    }
    assert!(wait_for_output(child).status.success());
    fixture.assert_request("find files");
    assert_eq!(fs::read(fixture.root.join("stdin")).unwrap(), b"eof");
}

#[test]
fn nonzero_pi_status_suppresses_final_stdout_and_preserves_stderr_bytes() {
    let fixture = Fixture::new();
    fixture.install_fake_pi(0o700);
    let output = wait_for_output(
        fixture
            .command()
            .arg("inspect")
            .env("GENIE_TEST_STDOUT", r#"{"type":"message_end","message":{"role":"assistant","stopReason":"stop","content":[{"type":"text","text":"result"}]}}"#)
            .env("GENIE_TEST_STDERR", "Pi diagnostic\n")
            .env("GENIE_TEST_BINARY", "yes")
            .env("GENIE_TEST_STATUS", "37")
            .spawn()
            .unwrap(),
    );
    assert_eq!(output.status.code(), Some(37));
    assert!(output.stdout.is_empty());
    assert_eq!(output.stderr, b"Pi diagnostic\n\xfe\x00");
}

#[test]
fn supervised_pi_has_separate_identity_and_conventional_signal_status() {
    let fixture = Fixture::new();
    fixture.install_fake_pi(0o700);
    let child = fixture
        .command()
        .arg("inspect")
        .env("GENIE_TEST_SIGNAL", "yes")
        .spawn()
        .unwrap();
    let pid = child.id();
    let output = wait_for_output(child);
    assert_eq!(output.status.code(), Some(143));
    assert_ne!(
        fs::read_to_string(fixture.root.join("pid")).unwrap(),
        pid.to_string()
    );
}

#[test]
fn help_and_version_do_not_start_pi_or_require_it() {
    for install in [false, true] {
        let fixture = Fixture::new();
        if install {
            fixture.install_fake_pi(0o700);
        }
        for flag in ["--help", "-h", "--version", "-V"] {
            let output = fixture.run(&[flag]);
            assert!(output.status.success());
            assert!(output.stderr.is_empty());
            let stdout = String::from_utf8(output.stdout).unwrap();
            if flag == "--help" || flag == "-h" {
                assert!(stdout.contains("Usage: g"));
            } else {
                assert_eq!(stdout, format!("g {}\n", env!("CARGO_PKG_VERSION")));
            }
            fixture.assert_pi_not_started();
        }
    }
}

#[test]
fn empty_or_whitespace_requests_are_usage_errors_without_pi() {
    let fixture = Fixture::new();
    fixture.install_fake_pi(0o700);
    for args in [
        vec![],
        vec![""],
        vec![" ", "\n\t\u{2003}"],
        vec!["--"],
        vec!["--", "", "  "],
    ] {
        let output = fixture.run(&args);
        assert_eq!(output.status.code(), Some(2));
        assert!(output.stdout.is_empty());
        assert!(String::from_utf8(output.stderr).unwrap().contains("Usage:"));
        fixture.assert_pi_not_started();
    }
}

#[test]
fn leading_unknown_options_are_usage_errors_not_pi_flags() {
    let fixture = Fixture::new();
    fixture.install_fake_pi(0o700);
    for flag in [
        "--model=x",
        "--thinking=high",
        "--continue",
        "--approve",
        "-x",
    ] {
        let output = fixture.run(&[flag, "value"]);
        assert_eq!(output.status.code(), Some(2));
        assert!(output.stdout.is_empty());
        assert!(String::from_utf8(output.stderr).unwrap().contains("g --"));
        fixture.assert_pi_not_started();
    }
}

#[test]
fn non_unicode_request_is_a_usage_error_not_a_panic() {
    let fixture = Fixture::new();
    fixture.install_fake_pi(0o700);
    let output = wait_for_output(
        fixture
            .command()
            .arg(OsString::from_vec(vec![0xff]))
            .spawn()
            .unwrap(),
    );
    assert_eq!(output.status.code(), Some(2));
    assert!(output.stdout.is_empty());
    assert!(
        String::from_utf8(output.stderr)
            .unwrap()
            .contains("Unicode")
    );
    fixture.assert_pi_not_started();
}

#[test]
fn missing_pi_reports_a_clear_launch_error() {
    let fixture = Fixture::new();
    let output = fixture.run(&["inspect"]);
    assert_eq!(output.status.code(), Some(1));
    assert!(output.stdout.is_empty());
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(stderr.contains("'pi'"));
    assert!(stderr.contains("PATH"));
    assert!(stderr.contains("install"));
}

#[test]
fn non_executable_pi_reports_permissions_error() {
    let fixture = Fixture::new();
    fixture.install_fake_pi(0o600);
    let output = fixture.run(&["inspect"]);
    assert_eq!(output.status.code(), Some(1));
    assert!(output.stdout.is_empty());
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(stderr.contains("'pi'"));
    assert!(stderr.contains("permissions"));
    fixture.assert_pi_not_started();
}

#[test]
fn model_and_thinking_precedence_is_independent_and_defaults_are_omitted() {
    for mask in 0..16 {
        let fixture = Fixture::new();
        fixture.install_fake_pi(0o700);
        let mut command = fixture.command();
        let mut expected = Vec::new();
        if mask & 1 != 0 {
            command.args(["--model", "cli/provider/model:high"]);
        }
        if mask & 2 != 0 {
            command.args(["--thinking", "low"]);
        }
        if mask & 4 != 0 {
            command.env("GENIE_MODEL", "env/provider/model:max");
            expected.extend(["--model", "env/provider/model:max"]);
        } else if mask & 1 != 0 {
            expected.extend(["--model", "cli/provider/model:high"]);
        }
        if mask & 8 != 0 {
            command.env("GENIE_THINKING", "off");
            expected.extend(["--thinking", "off"]);
        } else if mask & 2 != 0 {
            expected.extend(["--thinking", "low"]);
        }
        let output = wait_for_output(command.args(["-q", "--", "@inspect"]).spawn().unwrap());
        assert!(output.status.success(), "mask {mask}: {output:?}");
        assert!(output.stdout.is_empty());
        assert!(output.stderr.is_empty());
        fixture.assert_selection("@inspect", &expected);
    }
}

#[test]
fn blank_environment_is_absent_without_trimming_model_values() {
    for blank in ["", " \n\t\u{2003}"] {
        for options in [
            vec![],
            vec!["--model", "  provider/id:custom  ", "--thinking", "max"],
        ] {
            let fixture = Fixture::new();
            fixture.install_fake_pi(0o700);
            let output = wait_for_output(
                fixture
                    .command()
                    .env("GENIE_MODEL", blank)
                    .env("GENIE_THINKING", blank)
                    .args(&options)
                    .arg("inspect")
                    .spawn()
                    .unwrap(),
            );
            assert!(output.status.success());
            fixture.assert_selection("inspect", &options);
        }
    }
    let fixture = Fixture::new();
    fixture.install_fake_pi(0o700);
    let model = "  provider/nested/id:custom 🧞 $(touch injected); *  ";
    let output = wait_for_output(
        fixture
            .command()
            .env("GENIE_MODEL", model)
            .arg("inspect")
            .spawn()
            .unwrap(),
    );
    assert!(output.status.success());
    fixture.assert_selection("inspect", &["--model", model]);
    assert!(!fixture.root.join("working directory/injected").exists());
}

#[test]
fn all_thinking_levels_and_last_repeated_options_are_forwarded() {
    for level in ["off", "minimal", "low", "medium", "high", "xhigh", "max"] {
        let fixture = Fixture::new();
        fixture.install_fake_pi(0o700);
        let output = fixture.run(&[
            "--model",
            "old",
            "--thinking",
            "high",
            "--model",
            "provider/id:low",
            "--thinking",
            level,
            "inspect",
        ]);
        assert!(output.status.success());
        fixture.assert_selection(
            "inspect",
            &["--model", "provider/id:low", "--thinking", level],
        );
    }
}

#[test]
fn selection_options_after_double_dash_are_literal_even_if_invalid() {
    let fixture = Fixture::new();
    fixture.install_fake_pi(0o700);
    assert!(
        fixture
            .run(&[
                "--model",
                "provider/id",
                "--",
                "--thinking",
                "INVALID",
                "--model",
                ""
            ])
            .status
            .success()
    );
    fixture.assert_selection("--thinking INVALID --model ", &["--model", "provider/id"]);
}

#[test]
fn invalid_cli_configuration_never_launches_pi_even_with_environment_overrides() {
    let fixture = Fixture::new();
    fixture.install_fake_pi(0o700);
    for args in [
        vec!["--model"],
        vec!["--thinking"],
        vec!["--model", "", "inspect"],
        vec!["--model", " \n\t\u{2003}", "inspect"],
        vec!["--thinking", "", "inspect"],
        vec!["--thinking", " \n\t", "inspect"],
        vec!["--thinking", "PRIVATE\x1b[31m", "inspect"],
        vec!["--thinking", "HIGH", "inspect"],
        vec!["--thinking", " high ", "inspect"],
        vec!["--thinking", "PRIVATE", "--thinking", "low", "inspect"],
        vec!["--model", "--thinking", "high", "inspect"],
        vec!["--thinking", "--model", "provider/id", "inspect"],
        vec!["--model", "--", "inspect"],
        vec!["--thinking", "-q", "inspect"],
    ] {
        let output = wait_for_output(
            fixture
                .command()
                .env("GENIE_MODEL", "env/id")
                .env("GENIE_THINKING", "max")
                .args(&args)
                .spawn()
                .unwrap(),
        );
        assert_eq!(output.status.code(), Some(2), "{args:?}");
        assert!(output.stdout.is_empty());
        let stderr = String::from_utf8(output.stderr).unwrap();
        assert!(stderr.contains("g:"));
        assert!(!stderr.contains("PRIVATE"));
        assert!(!stderr.contains('\x1b'));
        fixture.assert_pi_not_started();
    }
}

#[test]
fn invalid_environment_thinking_never_launches_pi() {
    let fixture = Fixture::new();
    fixture.install_fake_pi(0o700);
    for value in ["PRIVATE\x1b[31m", "HIGH", " high "] {
        let output = wait_for_output(
            fixture
                .command()
                .env("GENIE_THINKING", value)
                .args(["--thinking", "low", "inspect"])
                .spawn()
                .unwrap(),
        );
        assert_eq!(output.status.code(), Some(2));
        assert!(output.stdout.is_empty());
        let stderr = String::from_utf8(output.stderr).unwrap();
        assert!(stderr.contains("thinking level must be"));
        assert!(!stderr.contains(value));
        fixture.assert_pi_not_started();
    }
}

#[test]
fn non_unicode_configuration_is_rejected_without_echoing_values() {
    let fixture = Fixture::new();
    fixture.install_fake_pi(0o700);
    let invalid = OsString::from_vec(b"PRIVATE\xff".to_vec());
    for flag in ["--model", "--thinking"] {
        let output = wait_for_output(
            fixture
                .command()
                .arg(flag)
                .arg(&invalid)
                .arg("inspect")
                .env("GENIE_MODEL", "env/id")
                .env("GENIE_THINKING", "low")
                .spawn()
                .unwrap(),
        );
        assert_eq!(output.status.code(), Some(2));
        assert!(output.stdout.is_empty());
        let stderr = String::from_utf8(output.stderr).unwrap();
        assert!(stderr.contains("Unicode"));
        assert!(!stderr.contains("PRIVATE"));
        fixture.assert_pi_not_started();
    }
    for name in ["GENIE_MODEL", "GENIE_THINKING"] {
        let output = wait_for_output(
            fixture
                .command()
                .env(name, &invalid)
                .args(["--model", "cli/id", "--thinking", "low", "inspect"])
                .spawn()
                .unwrap(),
        );
        assert_eq!(output.status.code(), Some(2));
        assert!(output.stdout.is_empty());
        let stderr = String::from_utf8(output.stderr).unwrap();
        assert!(stderr.contains("Unicode"));
        assert!(!stderr.contains("PRIVATE"));
        fixture.assert_pi_not_started();
    }
}

#[test]
fn help_and_version_ignore_invalid_selection_environment() {
    let fixture = Fixture::new();
    fixture.install_fake_pi(0o700);
    for value in [OsString::from("PRIVATE"), OsString::from_vec(vec![0xff])] {
        for flag in ["--help", "-h", "--version", "-V"] {
            let output = wait_for_output(
                fixture
                    .command()
                    .env("GENIE_MODEL", &value)
                    .env("GENIE_THINKING", &value)
                    .args(["--model", "cli/id", flag, "--thinking", "INVALID"])
                    .spawn()
                    .unwrap(),
            );
            assert!(output.status.success());
            assert!(!output.stdout.is_empty());
            assert!(output.stderr.is_empty());
            fixture.assert_pi_not_started();
        }
    }
}

mod activity;
mod protocol;
mod supervisor;

use std::env;
use std::ffi::OsString;
use std::io::{self, Write};
use std::process::ExitCode;

const HELP: &str = "g — execute a natural-language request with installed Pi

Usage: g [-q|--quiet] [--model <model>] [--thinking <level>] [--] <message words...>
       g --help | --version

Options (before the first message word):
  -q, --quiet      Hide activity only; keep results and diagnostics
  --model <model>  Select a Pi model pattern or provider/id
  --thinking <level>
                  Set reasoning: off, minimal, low, medium, high, xhigh, max
  -h, --help       Show this help without running Pi
  -V, --version    Show the version without running Pi
  --              Treat all remaining arguments as message text

GENIE_MODEL and GENIE_THINKING override the corresponding option independently.
Unset, empty, or whitespace-only environment values are absent. Otherwise values
must be Unicode; thinking must be one of the levels above. No selection means Pi's
defaults (no corresponding flag). Explicit thinking overrides a model :thinking suffix.
Repeated options use the last value. Every supplied option value must be valid,
non-blank, and not start with '-'; environment overrides do not hide option errors.
Message words are joined with spaces. Quote shell metacharacters and multiline text.
Explicit requests execute immediately, with no additional confirmation gate or sandbox.
Pi keeps its normal instructions, configuration, trust, and new-session persistence.
Requires Pi JSON mode (--mode json). Stdin is ignored. Only final assistant text goes
to stdout after Pi exits and its output drains. Pi diagnostics remain on stderr.
TTY stderr shows elapsed seconds and completed tool calls (including failed calls),
not task success or percent complete. No activity with --quiet, TERM=dumb, or a pipe.
Pi nonzero status is preserved; protocol/final-response failures are nonzero too.
Final length-limited text prints with a warning. Zero does not prove task success.
INT/TERM/HUP cancel with status 130/143/129 after bounded cleanup. INT requests Pi
TERM cleanup; forced shutdown cannot guarantee cleanup of all detached descendants.
";

const GUIDANCE: &str = "Execute the user's explicit request rather than giving commands for them to run. \
Stay within the requested authority and preserve unrelated changes. \
If the request is ambiguous or work is blocked, stop and report it; do not guess or attempt destructive recovery. \
Verify the result before claiming success. Return only a concise final result: \
a brief confirmation for completed actions, paths for file searches, or a clear blocker when incomplete.";

#[derive(Debug)]
enum Input {
    Help,
    Version,
    Message {
        message: String,
        quiet: bool,
        selection: Selection,
    },
}

#[derive(Debug, Default)]
struct Selection {
    model: Option<String>,
    thinking: Option<String>,
}

fn validate_thinking(level: &str) -> Result<(), &'static str> {
    match level {
        "off" | "minimal" | "low" | "medium" | "high" | "xhigh" | "max" => Ok(()),
        _ => Err("thinking level must be off, minimal, low, medium, high, xhigh, or max"),
    }
}

fn environment_value(value: Option<OsString>) -> Result<Option<String>, &'static str> {
    let value = value
        .map(|value| value.into_string())
        .transpose()
        .map_err(|_| "model and thinking configuration must be Unicode")?;
    Ok(value.filter(|value| !value.trim().is_empty()))
}

impl Selection {
    fn with_environment(self) -> Result<Self, &'static str> {
        let model = environment_value(env::var_os("GENIE_MODEL"))?;
        let thinking = environment_value(env::var_os("GENIE_THINKING"))?;
        if let Some(level) = &thinking {
            validate_thinking(level)?;
        }
        Ok(Self {
            model: model.or(self.model),
            thinking: thinking.or(self.thinking),
        })
    }
}

fn parse_input(mut args: impl Iterator<Item = OsString>) -> Result<Input, &'static str> {
    let mut words = Vec::new();
    let mut quiet = false;
    let mut literal = false;
    let mut selection = Selection::default();
    while let Some(arg) = args.next() {
        let word = arg.into_string().map_err(|_| "request must be Unicode")?;
        if !literal {
            match word.as_str() {
                "--help" | "-h" => return Ok(Input::Help),
                "--version" | "-V" => return Ok(Input::Version),
                "--quiet" | "-q" => {
                    quiet = true;
                    continue;
                }
                "--model" | "--thinking" => {
                    let value = args
                        .next()
                        .ok_or("--model and --thinking require a value")?
                        .into_string()
                        .map_err(|_| "model and thinking configuration must be Unicode")?;
                    if value.trim().is_empty() || value.starts_with('-') {
                        return Err(
                            "--model and --thinking require a non-blank value, not an option",
                        );
                    }
                    if word == "--thinking" {
                        validate_thinking(&value)?;
                        selection.thinking = Some(value);
                    } else {
                        selection.model = Some(value);
                    }
                    continue;
                }
                "--" => {
                    literal = true;
                    continue;
                }
                word if word.starts_with('-') => {
                    return Err("unknown option; use 'g -- <message>' for text beginning with '-'");
                }
                _ => literal = true,
            }
        }
        words.push(word);
    }
    let message = words.join(" ");
    if message.trim().is_empty() {
        return Err("a non-empty request is required");
    }
    Ok(Input::Message {
        message,
        quiet,
        selection,
    })
}

fn print_output(text: &str) -> ExitCode {
    if io::stdout().lock().write_all(text.as_bytes()).is_ok() {
        ExitCode::SUCCESS
    } else {
        ExitCode::FAILURE
    }
}

fn main() -> ExitCode {
    let (message, quiet, selection) = match parse_input(env::args_os().skip(1)) {
        Ok(Input::Help) => return print_output(HELP),
        Ok(Input::Version) => return print_output(&format!("g {}\n", env!("CARGO_PKG_VERSION"))),
        Ok(Input::Message {
            message,
            quiet,
            selection,
        }) => (message, quiet, selection),
        Err(error) => {
            supervisor::diagnostic(&format!(
                "{error}\nUsage: g [-q|--quiet] [--model <model>] [--thinking <level>] [--] <message words...>\nTry 'g --help' for help."
            ));
            return ExitCode::from(2);
        }
    };
    let selection = match selection.with_environment() {
        Ok(selection) => selection,
        Err(error) => {
            supervisor::diagnostic(error);
            return ExitCode::from(2);
        }
    };
    // System-prompt flags can suppress Pi's normal APPEND_SYSTEM.md discovery.
    // Keep guidance in the user prompt and prefix the request to avoid Pi syntax.
    let prompt = format!("{GUIDANCE}\n\nUser request:\n{message}");
    ExitCode::from(supervisor::run(&prompt, quiet, &selection))
}

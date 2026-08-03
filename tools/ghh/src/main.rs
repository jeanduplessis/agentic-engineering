use std::fmt;
use std::io;
use std::process::{Command, ExitCode, Stdio};
use std::time::Duration;

use clap::{Parser, Subcommand};
use indicatif::{MultiProgress, ProgressBar, ProgressStyle};

#[derive(Debug, Parser)]
#[command(
    name = "ghh",
    version,
    about = "A GitHub CLI helper for managing pull requests"
)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Debug, Subcommand)]
enum Commands {
    /// Approve one or more pull requests
    Stamp {
        /// GitHub organization that owns the repository
        #[arg(long)]
        org: String,

        /// Repository name
        #[arg(long)]
        repo: String,

        /// Comma-separated pull request numbers
        #[arg(long = "pr", value_parser = parse_prs)]
        prs: PrNumbers,
    },
}

#[derive(Clone, Debug)]
struct PrNumbers(Vec<u64>);

fn parse_prs(value: &str) -> Result<PrNumbers, String> {
    if value.trim().is_empty() {
        return Err("at least one pull request number is required".into());
    }

    value
        .split(',')
        .map(|part| {
            let part = part.trim();
            let number = part
                .parse::<u64>()
                .map_err(|_| format!("'{part}' is not a valid pull request number"))?;

            if number == 0 {
                Err("pull request numbers must be greater than zero".into())
            } else {
                Ok(number)
            }
        })
        .collect::<Result<Vec<_>, _>>()
        .map(PrNumbers)
}

#[derive(Debug)]
enum StampError {
    GhNotFound,
    GhFailed { pr: u64, code: Option<i32> },
    Io(io::Error),
}

impl fmt::Display for StampError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::GhNotFound => write!(
                formatter,
                "GitHub CLI ('gh') was not found; install it and run 'gh auth login'"
            ),
            Self::GhFailed {
                pr,
                code: Some(code),
            } => {
                write!(
                    formatter,
                    "failed to approve PR #{pr} (gh exited with status {code})"
                )
            }
            Self::GhFailed { pr, code: None } => {
                write!(formatter, "failed to approve PR #{pr} (gh was terminated)")
            }
            Self::Io(error) => write!(formatter, "could not run gh: {error}"),
        }
    }
}

fn stamp(org: &str, repo: &str, prs: &[u64]) -> Result<(), StampError> {
    let repository = format!("{org}/{repo}");
    let progress = MultiProgress::new();
    let overall = progress.add(ProgressBar::new(prs.len() as u64));
    overall.set_style(
        ProgressStyle::with_template("{bar:32.cyan/dim} {pos}/{len} {msg}")
            .expect("valid progress style")
            .progress_chars("━━╾"),
    );
    overall.set_message("PRs approved");

    for pr in prs {
        let current = progress.add(ProgressBar::new_spinner());
        current.set_style(
            ProgressStyle::with_template("{spinner:.cyan} {msg}")
                .expect("valid spinner style")
                .tick_chars("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏✓"),
        );
        current.enable_steady_tick(Duration::from_millis(80));
        current.set_message(format!("Approving {repository}#{pr}"));

        let output = Command::new("gh")
            .args([
                "pr",
                "review",
                &pr.to_string(),
                "--repo",
                &repository,
                "--approve",
            ])
            .stdin(Stdio::inherit())
            .output()
            .map_err(|error| {
                current.finish_and_clear();
                overall.abandon();
                if error.kind() == io::ErrorKind::NotFound {
                    StampError::GhNotFound
                } else {
                    StampError::Io(error)
                }
            })?;

        if !output.status.success() {
            current.abandon_with_message(format!("✗ Failed {repository}#{pr}"));
            overall.abandon_with_message("approval stopped");
            if !output.stderr.is_empty() {
                progress
                    .println(String::from_utf8_lossy(&output.stderr).trim_end())
                    .ok();
            }
            return Err(StampError::GhFailed {
                pr: *pr,
                code: output.status.code(),
            });
        }

        current.finish_with_message(format!("Approved {repository}#{pr}"));
        overall.inc(1);
    }

    overall.finish_with_message(format!("Approved {} PRs in {repository}", prs.len()));
    Ok(())
}

fn run(cli: Cli) -> Result<(), StampError> {
    match cli.command {
        Commands::Stamp { org, repo, prs } => stamp(&org, &repo, &prs.0),
    }
}

fn main() -> ExitCode {
    match run(Cli::parse()) {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("error: {error}");
            ExitCode::FAILURE
        }
    }
}

#[cfg(test)]
mod tests {
    use super::parse_prs;

    #[test]
    fn parses_one_pr() {
        assert_eq!(parse_prs("1234").unwrap().0, vec![1234]);
    }

    #[test]
    fn parses_multiple_prs() {
        assert_eq!(parse_prs("1234, 4567").unwrap().0, vec![1234, 4567]);
    }

    #[test]
    fn rejects_empty_input() {
        assert!(parse_prs("").is_err());
    }

    #[test]
    fn rejects_invalid_prs() {
        assert!(parse_prs("1234,nope").is_err());
        assert!(parse_prs("1234,,4567").is_err());
        assert!(parse_prs("0").is_err());
    }
}

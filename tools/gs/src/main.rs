use std::io::IsTerminal;
use std::process::ExitCode;

use clap::Parser;
use gs::{ColorMode, InspectError, enhanced_status_view, render};

#[derive(Debug, Parser)]
#[command(name = "gs", version, about = "Print an enhanced Git status view")]
struct Args {
    #[arg(long, value_enum, default_value_t = ColorMode::Auto)]
    color: ColorMode,
}

fn main() -> ExitCode {
    let args = Args::parse();
    let cwd = match std::env::current_dir() {
        Ok(cwd) => cwd,
        Err(error) => {
            eprintln!("gs: {error}");
            return ExitCode::from(1);
        }
    };

    match enhanced_status_view(&cwd) {
        Ok(view) => {
            print!(
                "{}",
                render(&view, args.color, std::io::stdout().is_terminal())
            );
            ExitCode::SUCCESS
        }
        Err(InspectError::NotGitRepository) => {
            eprintln!("gs: not a git repository");
            ExitCode::from(1)
        }
        Err(error) => {
            eprintln!("gs: {error}");
            ExitCode::from(1)
        }
    }
}

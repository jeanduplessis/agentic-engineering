use std::process::ExitCode;

use anyhow::Result;
use clap::{CommandFactory, Parser};
use gw::cli::{Cli, Command};
use gw::{commands, shell};

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("Error: {error:#}");
            ExitCode::FAILURE
        }
    }
}

fn run() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Some(Command::Add(args)) => commands::add::run(&args),
        Some(Command::List(args)) => commands::list::run(args),
        Some(Command::Remove(args)) => commands::remove::run(&args),
        Some(Command::Clean) => commands::clean::run(),
        Some(Command::Init) => commands::init::run(),
        Some(Command::Cd(args)) => commands::cd::run(args),
        Some(Command::Completion(_)) => {
            println!("{}", shell::zsh_completion());
            Ok(())
        }
        Some(Command::Hook(_)) => {
            println!("{}", shell::zsh_hook());
            Ok(())
        }
        Some(Command::ShellInit(_)) => {
            println!("{}", shell::zsh_shell_init());
            Ok(())
        }
        Some(Command::Complete(args)) => commands::complete::run(&args),
        None => {
            Cli::command().print_help()?;
            println!();
            Ok(())
        }
    }
}

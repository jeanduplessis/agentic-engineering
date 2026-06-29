use clap::{Args, Parser, Subcommand, ValueEnum};

#[derive(Debug, Parser)]
#[command(name = "gw", version, about = "Personal Git worktree manager")]
pub struct Cli {
    #[command(subcommand)]
    pub command: Option<Command>,
}

#[derive(Debug, Subcommand)]
pub enum Command {
    /// Create a worktree.
    Add(AddArgs),
    /// Print planned add target path.
    #[command(name = "__add-target", hide = true)]
    AddTarget(AddArgs),
    /// List worktrees.
    #[command(alias = "ls")]
    List(ListArgs),
    /// Remove a managed worktree.
    #[command(alias = "rm")]
    Remove(RemoveArgs),
    /// Remove managed worktrees whose branches are merged.
    Clean,
    /// Create .gw.yml in the main repository root.
    Init,
    /// Print a managed worktree path.
    Cd(CdArgs),
    /// Generate zsh completion.
    Completion(ShellArgs),
    /// Generate zsh cd hook.
    Hook(ShellArgs),
    /// Generate zsh completion and cd hook.
    ShellInit(ShellArgs),
    /// Return dynamic completion candidates.
    #[command(name = "__complete", hide = true)]
    Complete(CompleteArgs),
}

#[derive(Debug, Args)]
pub struct AddArgs {
    /// Enter the new worktree after creation when shell integration is active.
    #[arg(long)]
    pub cd: bool,
    /// Create a new branch, optionally from START_POINT.
    #[arg(short = 'b', long = "branch", value_name = "NEW_BRANCH")]
    pub new_branch: Option<String>,
    /// Existing branch, or START_POINT when -b is used.
    #[arg(value_name = "BRANCH_OR_START_POINT")]
    pub target: Option<String>,
}

#[derive(Debug, Args)]
pub struct ListArgs {
    /// Minimize output width.
    #[arg(short, long)]
    pub compact: bool,
    /// Print worktree names only.
    #[arg(short, long)]
    pub quiet: bool,
}

#[derive(Debug, Args)]
pub struct RemoveArgs {
    pub name: String,
    /// Force removal of a dirty or locked worktree.
    #[arg(short, long)]
    pub force: bool,
    /// Delete the associated branch after removal.
    #[arg(long)]
    pub with_branch: bool,
    /// Force branch deletion. Requires --with-branch.
    #[arg(long, requires = "with_branch")]
    pub force_branch: bool,
}

#[derive(Debug, Args)]
pub struct CdArgs {
    pub name: Option<String>,
}

#[derive(Debug, Clone, Copy, ValueEnum)]
pub enum Shell {
    Zsh,
}

#[derive(Debug, Args)]
pub struct ShellArgs {
    #[arg(value_enum)]
    pub shell: Shell,
}

#[derive(Debug, Args)]
pub struct CompleteArgs {
    #[arg(trailing_var_arg = true, allow_hyphen_values = true)]
    pub words: Vec<String>,
}

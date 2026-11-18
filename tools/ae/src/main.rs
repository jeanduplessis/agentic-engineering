//! Æ — install Agentic Engineering skills and resources into every coding harness.

mod apply;
mod doctor;
mod harness;
mod output;
mod paths;
mod plan;
mod repo;
mod state;
mod ui;

use anyhow::{Context as _, Result, bail};
use clap::{Args, CommandFactory, Parser, Subcommand};
use harness::{Environment, Vars};
use output::Paint;
use plan::{Desired, Options, Plan};
use state::Snapshot;
use std::collections::BTreeSet;
use std::io::{BufRead, IsTerminal, Write};
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::sync::Arc;
use std::sync::atomic::AtomicBool;
use std::time::{Duration, Instant};

const EXAMPLES: &str = "\
Examples:
  ae                                    open the interactive installer
  ae status                             what each harness loads, and any problems
  ae add -s council-review -H all       give a skill to every detected harness
  ae add -s premortem,wat -H claude-personal,codex
  ae remove -s premortem -H codex       stop Codex loading a skill
  ae add -p APPEND_SYSTEM.md -p extensions/prompt-stash
  ae add -c output-style                link the output style into every Claude Code home
  ae add -t gs,gw                       build and install tools with cargo
  ae doctor                             verify by asking Grok, Kilo, and Codex
  ae prune -n                           preview removal of stale or redundant links

Harness ids come from `ae status` (for example claude-work, claude-personal, codex, grok, pi, kilo).
Every change is shown as a plan first. Æ only creates or removes symlinks into this checkout;
anything else in the way is backed up, and only after you approve it.";

#[derive(Parser)]
#[command(
    name = "ae",
    version,
    about = "Æ — install Agentic Engineering skills and resources into every coding harness",
    after_help = EXAMPLES
)]
struct Cli {
    /// Checkout to install from (defaults to the one ae was built from)
    #[arg(long, global = true, env = "AE_REPO", value_name = "PATH")]
    repo: Option<PathBuf>,
    /// Print machine-readable JSON
    #[arg(long, global = true)]
    json: bool,
    /// Disable colors (also honors NO_COLOR)
    #[arg(long, global = true)]
    no_color: bool,
    #[command(subcommand)]
    command: Option<Cmd>,
}

#[derive(Subcommand)]
enum Cmd {
    /// Open the interactive installer (the default in a terminal)
    Ui,
    /// Show detected harnesses, what each one loads, and any problems
    Status,
    /// Check links and ask Grok, Kilo, and Codex which skills they actually load
    Doctor {
        /// Skip asking the harnesses; check the filesystem only
        #[arg(long, env = "AE_NO_PROBE", value_parser = clap::builder::FalseyValueParser::new())]
        no_probe: bool,
    },
    /// Install skills for harnesses, Claude Code resources, Pi resources, or tools
    Add {
        #[command(flatten)]
        selection: Selection,
        /// Tools to build and install with cargo (or `all`)
        #[arg(short, long = "tool", value_delimiter = ',', value_name = "NAME")]
        tools: Vec<String>,
        /// Back up and replace anything in the way without asking
        #[arg(long)]
        replace: bool,
        #[command(flatten)]
        apply: ApplyFlags,
    },
    /// Remove links into this checkout for skills, Claude Code resources, or Pi resources
    Remove {
        #[command(flatten)]
        selection: Selection,
        #[command(flatten)]
        apply: ApplyFlags,
    },
    /// Remove stale links and links that duplicate another folder
    Prune {
        #[command(flatten)]
        apply: ApplyFlags,
    },
    /// Print a shell completion script
    Completions { shell: clap_complete::Shell },
}

#[derive(Args, Default)]
struct Selection {
    /// Skills to change (names, or `all`)
    #[arg(short, long = "skill", value_delimiter = ',', value_name = "NAME")]
    skills: Vec<String>,
    /// Harnesses to change them for (ids such as claude-personal, or `all`)
    #[arg(short = 'H', long = "harness", value_delimiter = ',', value_name = "ID")]
    harnesses: Vec<String>,
    /// Claude Code resources (output-style, or `all`); every Claude Code home unless --harness names some
    #[arg(short, long = "claude", value_delimiter = ',', value_name = "ITEM")]
    claude: Vec<String>,
    /// Pi resources (APPEND_SYSTEM.md, docs, subagents, commands/<file>, extensions/<name>, `<group>/all`, or `all`)
    #[arg(short, long = "pi", value_delimiter = ',', value_name = "ITEM")]
    pi: Vec<String>,
}

#[derive(Args, Default)]
struct ApplyFlags {
    /// Show the plan without changing anything
    #[arg(short = 'n', long)]
    dry_run: bool,
    /// Apply without asking for confirmation
    #[arg(short, long)]
    yes: bool,
}

fn main() -> ExitCode {
    let cli = Cli::parse();
    match run(cli) {
        Ok(code) => ExitCode::from(code),
        Err(error) => {
            eprintln!("ae: {error:#}");
            ExitCode::from(2)
        }
    }
}

fn run(cli: Cli) -> Result<u8> {
    let paint = Paint { color: !cli.no_color && std::env::var_os("NO_COLOR").is_none() && std::io::stdout().is_terminal() && !cli.json };
    if let Some(Cmd::Completions { shell }) = &cli.command {
        clap_complete::generate(*shell, &mut Cli::command(), "ae", &mut std::io::stdout());
        return Ok(0);
    }
    let root = resolve_repo(cli.repo.as_deref())?;
    let vars = Vars::from_process();
    let interactive = std::io::stdin().is_terminal() && std::io::stdout().is_terminal();
    match cli.command {
        None if interactive && !cli.json => ui::run(load(&root, &vars, &BTreeSet::new(), true)),
        Some(Cmd::Ui) => {
            if !interactive {
                bail!("the interactive installer needs a terminal; use `ae status` or `ae add --help`");
            }
            ui::run(load(&root, &vars, &BTreeSet::new(), true))
        }
        None | Some(Cmd::Status) => {
            let snap = load(&root, &vars, &BTreeSet::new(), true);
            let issues = doctor::issues(&snap);
            if cli.json {
                println!("{}", serde_json::to_string_pretty(&status_json(&snap, &issues))?);
            } else {
                print!("{}", output::status(&snap, &issues, paint));
                if cli.command.is_none() {
                    println!("\n{}", paint.dim("Run ae in a terminal for the interactive installer, or see ae --help for commands."));
                }
            }
            Ok(0)
        }
        Some(Cmd::Doctor { no_probe }) => {
            let snap = load(&root, &vars, &BTreeSet::new(), !no_probe);
            let issues = doctor::issues(&snap);
            let probes = if no_probe {
                Vec::new()
            } else {
                let spinner = (!cli.json && std::io::stderr().is_terminal()).then(|| {
                    let bar = indicatif::ProgressBar::new_spinner();
                    bar.set_message("Asking Grok, Kilo, and Codex which skills they load…");
                    bar.enable_steady_tick(Duration::from_millis(80));
                    bar
                });
                let probes = doctor::probe(&snap, Duration::from_secs(45));
                if let Some(bar) = spinner {
                    bar.finish_and_clear();
                }
                probes
            };
            let failed = issues.iter().any(|i| i.level <= doctor::Level::Warning) || probes.iter().any(|p| !p.mismatches.is_empty());
            if cli.json {
                println!("{}", serde_json::to_string_pretty(&serde_json::json!({ "issues": issues, "probes": probes }))?);
            } else {
                print!("{}", output::header(&snap, paint));
                println!();
                print!("{}", output::issues_text(&issues, paint));
                if !probes.is_empty() {
                    println!("\n{}", paint.bold("What the harnesses report"));
                    print!("{}", output::probes_text(&probes, paint));
                }
            }
            Ok(u8::from(failed))
        }
        Some(Cmd::Add { selection, tools, replace, apply }) => {
            change(&root, &vars, &selection, &tools, true, false, replace, &apply, cli.json, paint)
        }
        Some(Cmd::Remove { selection, apply }) => change(&root, &vars, &selection, &[], false, false, false, &apply, cli.json, paint),
        Some(Cmd::Prune { apply }) => change(&root, &vars, &Selection::default(), &[], false, true, false, &apply, cli.json, paint),
        Some(Cmd::Completions { .. }) => unreachable!(),
    }
}

/// `--repo`, then `AE_REPO`, then the checkout this binary was built from.
fn resolve_repo(explicit: Option<&Path>) -> Result<PathBuf> {
    if let Some(path) = explicit {
        return std::fs::canonicalize(path).with_context(|| format!("checkout not found: {}", path.display()));
    }
    let built = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    if built.join("skills").is_dir() || built.join("harness").is_dir() {
        return Ok(paths::canonical(&built));
    }
    bail!("cannot find the Agentic Engineering checkout; pass --repo <path> or set AE_REPO")
}

fn load(root: &Path, vars: &Vars, force: &BTreeSet<usize>, probe: bool) -> Snapshot {
    let repo = repo::Repo::discover(root);
    let mut env = Environment::detect(vars);
    if probe && vars.get("AE_NO_PROBE").is_none_or(|v| v == "0") {
        env.probe_versions(Duration::from_secs(3));
    }
    Snapshot::take(repo, env, force)
}

#[allow(clippy::too_many_arguments)]
fn change(
    root: &Path,
    vars: &Vars,
    selection: &Selection,
    tools: &[String],
    adding: bool,
    prune: bool,
    replace: bool,
    flags: &ApplyFlags,
    json: bool,
    paint: Paint,
) -> Result<u8> {
    if json && !flags.dry_run && !flags.yes {
        bail!("--json needs --dry-run or --yes, because it cannot ask for confirmation");
    }
    let probe_env = Environment::detect(vars);
    let probe_repo = repo::Repo::discover(root);
    let harnesses = resolve_harnesses(&probe_env, &selection.harnesses)?;
    let skills = resolve_names("skill", &selection.skills, probe_repo.skills.iter().map(|s| s.name.as_str()))?;
    let tools = resolve_names("tool", tools, probe_repo.tools.iter().map(|t| t.name.as_str()))?;
    let pi = resolve_pi(&probe_repo, &selection.pi)?;
    let claude = resolve_names("Claude Code resource", &selection.claude, probe_repo.claude.iter().map(|c| c.id.as_str()))?;
    if !skills.is_empty() && harnesses.is_empty() {
        bail!("choose which harnesses get the skills with --harness <id>, or --harness all (see `ae status` for ids)");
    }
    if skills.is_empty() && claude.is_empty() && !harnesses.is_empty() {
        bail!("choose skills with --skill <name> or Claude Code resources with --claude <item>");
    }
    let requested = !selection.skills.is_empty() || !selection.claude.is_empty() || !selection.pi.is_empty() || !tools.is_empty();
    if !prune && !requested && selection.harnesses.is_empty() {
        bail!(
            "nothing selected; pass --skill and --harness, --claude, --pi{}, or run ae for the interactive installer",
            if adding { ", --tool" } else { "" }
        );
    }
    let explicit: BTreeSet<usize> = if selection.harnesses.iter().any(|h| !h.eq_ignore_ascii_case("all")) {
        harnesses.iter().copied().collect()
    } else {
        Default::default()
    };
    let snap = load(root, vars, &explicit, false);
    for &h in &explicit {
        if !snap.env.harnesses[h].detected && !json {
            eprintln!(
                "{} {} was not found; linking anyway into {}",
                paint.yellow("!"),
                snap.env.harnesses[h].name,
                snap.env.tilde(snap.env.harnesses[h].own_skills())
            );
        }
    }
    let targets: BTreeSet<usize> = if selection.harnesses.iter().any(|h| h.eq_ignore_ascii_case("all")) {
        snap.active.clone()
    } else {
        harnesses.iter().copied().collect()
    };

    let claude_targets: Vec<usize> = if selection.harnesses.is_empty() {
        snap.claude_homes.clone()
    } else {
        targets.iter().copied().filter(|&h| snap.env.harnesses[h].kind == harness::Kind::Claude).collect()
    };
    if !claude.is_empty() && claude_targets.is_empty() {
        bail!("no Claude Code home to change; name one with --harness <id> (see `ae status` for ids)");
    }

    let mut desired = Desired { prune, ..Desired::default() };
    for &i in &claude {
        for &h in &claude_targets {
            desired.claude.insert((i, h), adding);
        }
    }
    for &s in &skills {
        let mut wanted = snap.visible(s);
        if adding {
            wanted.extend(targets.iter().copied());
        } else {
            for &h in &targets {
                let forced = plan::forced_by(&snap, &wanted, h);
                if !forced.is_empty() {
                    let names: Vec<String> = forced.iter().map(|&g| snap.env.harnesses[g].name.clone()).collect();
                    bail!(
                        "{} loads skills from {}, so it keeps {} while {} has it; remove it there too",
                        snap.env.harnesses[h].name,
                        snap.env.tilde(snap.env.harnesses[forced[0]].own_skills()),
                        snap.repo.skills[s].name,
                        doctor::join(&names)
                    );
                }
                wanted.remove(&h);
            }
        }
        desired.skills.insert(s, wanted);
    }
    for &i in &pi {
        if snap.repo.pi[i].kind == repo::PiKind::Subagents {
            if adding {
                desired.subagents = true;
            } else {
                bail!("subagents merges Pi settings and cannot be removed automatically; see harness/pi/subagents/README.md");
            }
        } else {
            desired.pi.insert(i, adding);
        }
    }
    desired.tools = tools.into_iter().collect();

    let mut plan = plan::build(&snap, &desired, Options { replace });
    if !plan.errors.is_empty() {
        for error in &plan.errors {
            eprintln!("{} {error}", paint.red("✗"));
        }
        eprintln!("Nothing changed.");
        return Ok(1);
    }
    if plan.steps.is_empty() {
        if json {
            println!("{}", serde_json::to_string_pretty(&serde_json::json!({ "plan": plan, "results": [] }))?);
        } else {
            println!("{} Nothing to do — everything selected is already in place.", paint.green("✓"));
        }
        return Ok(0);
    }
    if !json {
        print!("{}", output::plan_text(&snap, &plan, paint));
    }
    if flags.dry_run {
        if json {
            println!("{}", serde_json::to_string_pretty(&serde_json::json!({ "plan": plan }))?);
        } else {
            println!("\n{}  {}", output::summary_line(&plan, paint), paint.dim("(dry run: nothing changed)"));
        }
        return Ok(0);
    }
    let conflicts = plan.pending_conflicts();
    if conflicts > 0 && !flags.yes {
        match ask(&format!("Back up and replace the {conflicts} item{} in the way?", if conflicts == 1 { "" } else { "s" })) {
            Some(answer) => plan.approve_conflicts(answer),
            None => {
                println!("Cancelled. Nothing changed.");
                return Ok(0);
            }
        }
    }
    if plan.approved_count() == 0 {
        println!("Nothing to apply; {} skipped.", output::summary_line(&plan, paint));
        return Ok(1);
    }
    if !flags.yes {
        let prompt = format!("Apply {}?", output::summary_line(&plan, Paint { color: false }));
        if ask(&prompt) != Some(true) {
            println!("Cancelled. Nothing changed.");
            return Ok(0);
        }
    }
    let failed = execute(&snap, &plan, json, paint)?;
    Ok(u8::from(failed || plan.pending_conflicts() > 0))
}

/// Ask a yes/no question on stdin. `None` means no input (EOF).
fn ask(question: &str) -> Option<bool> {
    print!("{question} [y/N] ");
    let _ = std::io::stdout().flush();
    let mut line = String::new();
    match std::io::stdin().lock().read_line(&mut line) {
        Ok(0) | Err(_) => {
            println!();
            None
        }
        Ok(_) => Some(matches!(line.trim(), "y" | "Y" | "yes" | "Yes" | "YES")),
    }
}

fn execute(snap: &Snapshot, plan: &Plan, json: bool, paint: Paint) -> Result<bool> {
    let context = apply::Context { roots: snap.roots.clone(), log_dir: std::env::temp_dir().join("ae-logs") };
    let cancel = Arc::new(AtomicBool::new(false));
    let started = Instant::now();
    let fancy = !json && std::io::stderr().is_terminal();
    let mut bar: Option<indicatif::ProgressBar> = None;
    let mut results = Vec::new();
    let mut failed = false;
    if !json {
        println!();
    }
    apply::run(plan, &context, &cancel, |event| match event {
        apply::Event::Started(index) => {
            if fancy && matches!(plan.steps[index].op, plan::Op::CargoInstall { .. }) {
                let progress = indicatif::ProgressBar::new(1000);
                progress.set_style(
                    indicatif::ProgressStyle::with_template(
                        "  {spinner:.magenta} {prefix:.bold} [{bar:24.magenta/dim}] {elapsed:>4} {wide_msg:.dim}",
                    )
                    .unwrap()
                    .progress_chars("━╸─"),
                );
                progress.set_prefix(plan.steps[index].name.clone());
                progress.enable_steady_tick(Duration::from_millis(80));
                bar = Some(progress);
            }
        }
        apply::Event::Progress(_, fraction, line) => {
            if let Some(progress) = &bar {
                if let Some(fraction) = fraction {
                    progress.set_position((fraction * 1000.0) as u64);
                }
                progress.set_message(line);
            }
        }
        apply::Event::Finished(index, outcome, elapsed) => {
            if let Some(progress) = bar.take() {
                progress.finish_and_clear();
            }
            failed |= outcome.is_failure();
            if json {
                results.push(serde_json::json!({
                    "name": plan.steps[index].name,
                    "outcome": match &outcome {
                        apply::Outcome::Done(_) => "done",
                        apply::Outcome::Skipped(_) => "skipped",
                        apply::Outcome::Failed(_) => "failed",
                    },
                    "detail": match &outcome {
                        apply::Outcome::Done(detail) => detail.clone(),
                        apply::Outcome::Skipped(why) | apply::Outcome::Failed(why) => Some(why.clone()),
                    },
                }));
            } else {
                println!("{}", output::outcome_line(snap, plan, index, &outcome, elapsed, paint));
            }
        }
        apply::Event::Cancelled(_) => {}
    });
    if json {
        println!("{}", serde_json::to_string_pretty(&serde_json::json!({ "plan": plan, "results": results }))?);
    } else {
        let elapsed = started.elapsed().as_secs_f64();
        if failed {
            println!("\n{} Finished with errors in {elapsed:.1}s. Review the lines marked ✗ above.", paint.red("✗"));
        } else {
            println!("\n{} Done in {elapsed:.1}s.", paint.green("✓"));
        }
        if let Some(hint) = output::restart_hint(plan) {
            println!("{}", paint.dim(hint));
        }
        for hint in output::activation_hints(snap, plan) {
            println!("{}", paint.yellow(hint));
        }
    }
    Ok(failed)
}

fn suggest<'a>(input: &str, options: impl Iterator<Item = &'a str>) -> Option<&'a str> {
    let distance = |a: &str, b: &str| -> usize {
        let b: Vec<char> = b.chars().collect();
        let mut row: Vec<usize> = (0..=b.len()).collect();
        for (i, ca) in a.chars().enumerate() {
            let mut previous = row[0];
            row[0] = i + 1;
            for (j, cb) in b.iter().enumerate() {
                let current = row[j + 1];
                row[j + 1] = (previous + usize::from(ca != *cb)).min(row[j] + 1).min(current + 1);
                previous = current;
            }
        }
        row[b.len()]
    };
    options
        .map(|option| (distance(input, option), option))
        .filter(|(d, option)| *d <= 3.max(option.len() / 3))
        .min_by_key(|(d, _)| *d)
        .map(|(_, option)| option)
}

fn resolve_names<'a>(kind: &str, wanted: &[String], options: impl Iterator<Item = &'a str> + Clone) -> Result<Vec<usize>> {
    let all: Vec<&str> = options.clone().collect();
    let mut out = Vec::new();
    for name in wanted.iter().map(|n| n.trim()).filter(|n| !n.is_empty()) {
        if name.eq_ignore_ascii_case("all") {
            return Ok((0..all.len()).collect());
        }
        match all.iter().position(|option| *option == name) {
            Some(index) if !out.contains(&index) => out.push(index),
            Some(_) => {}
            None => {
                let hint = suggest(name, all.iter().copied()).map(|s| format!(" Did you mean `{s}`?")).unwrap_or_default();
                bail!("unknown {kind} `{name}`.{hint} Available: {}", all.join(", "));
            }
        }
    }
    Ok(out)
}

fn resolve_harnesses(env: &Environment, wanted: &[String]) -> Result<Vec<usize>> {
    let mut out = Vec::new();
    for raw in wanted.iter().map(|n| n.trim()).filter(|n| !n.is_empty()) {
        if raw.eq_ignore_ascii_case("all") {
            return Ok(env.harnesses.iter().enumerate().filter(|(_, h)| h.detected).map(|(i, _)| i).collect());
        }
        let lower = raw.to_ascii_lowercase();
        let matches: Vec<usize> = env
            .harnesses
            .iter()
            .enumerate()
            .filter(|(_, h)| h.id == lower || h.label.eq_ignore_ascii_case(raw) || harness::slug(&h.name) == harness::slug(raw))
            .map(|(i, _)| i)
            .collect();
        let matches = if matches.is_empty() {
            env.harnesses.iter().enumerate().filter(|(_, h)| format!("{:?}", h.kind).eq_ignore_ascii_case(raw)).map(|(i, _)| i).collect()
        } else {
            matches
        };
        match matches.as_slice() {
            [one] => {
                if !out.contains(one) {
                    out.push(*one)
                }
            }
            [] => {
                let ids: Vec<&str> = env.harnesses.iter().map(|h| h.id.as_str()).collect();
                let hint = suggest(&lower, ids.iter().copied()).map(|s| format!(" Did you mean `{s}`?")).unwrap_or_default();
                bail!("unknown harness `{raw}`.{hint} Available: {}", ids.join(", "));
            }
            many => {
                let ids: Vec<&str> = many.iter().map(|&i| env.harnesses[i].id.as_str()).collect();
                bail!("`{raw}` matches several harnesses; choose one of {}", ids.join(", "));
            }
        }
    }
    Ok(out)
}

fn resolve_pi(repo: &repo::Repo, wanted: &[String]) -> Result<Vec<usize>> {
    let mut out: Vec<usize> = Vec::new();
    let add = |index: usize, out: &mut Vec<usize>| {
        if !out.contains(&index) {
            out.push(index)
        }
    };
    for raw in wanted.iter().map(|n| n.trim()).filter(|n| !n.is_empty()) {
        if raw.eq_ignore_ascii_case("all") {
            (0..repo.pi.len()).for_each(|i| add(i, &mut out));
            continue;
        }
        if let Some(group) = raw.strip_suffix("/all") {
            let found: Vec<usize> =
                repo.pi.iter().enumerate().filter(|(_, item)| item.id.starts_with(&format!("{group}/"))).map(|(i, _)| i).collect();
            if found.is_empty() {
                bail!("no Pi {group} in this checkout");
            }
            found.into_iter().for_each(|i| add(i, &mut out));
            continue;
        }
        match repo.pi.iter().position(|item| item.id == raw) {
            Some(index) => add(index, &mut out),
            None => {
                let ids: Vec<&str> = repo.pi.iter().map(|item| item.id.as_str()).collect();
                let hint = suggest(raw, ids.iter().copied()).map(|s| format!(" Did you mean `{s}`?")).unwrap_or_default();
                let groups = if ["commands", "extensions", "skills"].contains(&raw) {
                    format!(" Choose items like `{raw}/<name>`, or `{raw}/all`.")
                } else {
                    String::new()
                };
                bail!("unknown Pi item `{raw}`.{hint}{groups}");
            }
        }
    }
    Ok(out)
}

fn status_json(snap: &Snapshot, issues: &[doctor::Issue]) -> serde_json::Value {
    let id = |h: &usize| snap.env.harnesses[*h].id.clone();
    serde_json::json!({
        "repo": snap.repo.root,
        "orchestrator": snap.env.orchestrator,
        "harnesses": snap.env.harnesses,
        "locations": snap.locations.iter().map(|l| serde_json::json!({
            "path": l.path,
            "readers": l.readers.iter().map(id).collect::<Vec<_>>(),
        })).collect::<Vec<_>>(),
        "skills": snap.repo.skills.iter().enumerate().map(|(s, skill)| serde_json::json!({
            "name": skill.name,
            "description": skill.description,
            "tags": skill.tags,
            "loaded_by": snap.visible(s).iter().map(id).collect::<Vec<_>>(),
            "other_copy_in": snap.foreign(s).iter().map(id).collect::<Vec<_>>(),
            "links": snap.linked_locations(s).iter().map(|&l| snap.locations[l].path.join(&skill.name)).collect::<Vec<_>>(),
        })).collect::<Vec<_>>(),
        "pi": {
            "dir": snap.pi_dir,
            "items": snap.repo.pi.iter().enumerate().map(|(i, item)| serde_json::json!({
                "id": item.id,
                "kind": item.kind,
                "target": item.target,
                "state": if item.kind == repo::PiKind::Subagents {
                    serde_json::to_value(snap.subagents.as_ref().map(|s| &s.state)).unwrap_or_default()
                } else {
                    serde_json::to_value(&snap.pi[i]).unwrap_or_default()
                },
            })).collect::<Vec<_>>(),
        },
        "claude": snap.repo.claude.iter().enumerate().map(|(i, item)| serde_json::json!({
            "id": item.id,
            "target": item.target,
            "style": item.style,
            "homes": snap.claude_homes.iter().enumerate().map(|(k, &h)| serde_json::json!({
                "harness": snap.env.harnesses[h].id,
                "path": snap.env.harnesses[h].home.join(&item.target),
                "state": snap.claude[i][k],
                "active": snap.style_active(i, k),
            })).collect::<Vec<_>>(),
        })).collect::<Vec<_>>(),
        "tools": snap.repo.tools.iter().enumerate().map(|(t, tool)| serde_json::json!({
            "name": tool.name,
            "version": tool.version,
            "bins": tool.bins,
            "installed": snap.tools[t],
        })).collect::<Vec<_>>(),
        "issues": issues,
    })
}

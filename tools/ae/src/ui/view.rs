//! Rendering. Every function draws from `&App`; nothing here mutates state.

use super::theme::SPINNER;
use super::{App, Screen, StepStatus, Tab, Tone};
use crate::apply::Outcome;
use crate::doctor::{Level, join};
use crate::output::describe_step;
use crate::plan::{self, Op, Section};
use crate::repo::PiKind;
use crate::state::{Entry, Existing, SubagentState};
use ratatui::Frame;
use ratatui::layout::{Alignment, Constraint, Layout, Rect};
use ratatui::style::{Modifier, Style};
use ratatui::text::{Line, Span, Text};
use ratatui::widgets::{Block, BorderType, Cell, Clear, Gauge, Paragraph, Row, Table, TableState, Wrap};

const MIN_WIDTH: u16 = 50;
const MIN_HEIGHT: u16 = 14;

pub fn draw(frame: &mut Frame, app: &App) {
    let area = frame.area();
    if area.width < MIN_WIDTH || area.height < MIN_HEIGHT {
        let text = format!("Æ needs a terminal of at least {MIN_WIDTH}×{MIN_HEIGHT}.\nThis one is {}×{}.", area.width, area.height);
        frame.render_widget(Paragraph::new(text).alignment(Alignment::Center).wrap(Wrap { trim: true }), area);
        return;
    }
    let [header, tabs, body, message, footer] =
        Layout::vertical([Constraint::Length(1), Constraint::Length(1), Constraint::Min(6), Constraint::Length(1), Constraint::Length(1)])
            .areas(area);
    draw_header(frame, app, header);
    draw_tabs(frame, app, tabs);
    match app.screen {
        Screen::Browse => match app.tab {
            Tab::Skills => draw_skills(frame, app, body),
            Tab::Pi => draw_pi(frame, app, body),
            Tab::Tools => draw_tools(frame, app, body),
        },
        Screen::Review => draw_review(frame, app, body),
        Screen::Applying | Screen::Done => draw_applying(frame, app, body),
    }
    draw_message(frame, app, message);
    draw_footer(frame, app, footer);
    if app.help {
        draw_help(frame, app, area);
    }
}

fn draw_header(frame: &mut Frame, app: &App, area: Rect) {
    let t = &app.theme;
    let env = &app.snap.env;
    let width = area.width as usize;
    let brand = [
        Span::styled(" Æ ", t.accent().add_modifier(Modifier::BOLD | Modifier::REVERSED)),
        Span::raw("  "),
        Span::styled("Agentic Engineering", t.bold()),
    ];
    let path = format!("  {}", env.tilde(&app.snap.repo.root));
    let orchestrator = env.orchestrator.as_ref().map(|o| {
        let version = match (&o.version, app.probing) {
            (Some(v), _) => format!(" {v}"),
            (None, true) => format!(" {}", SPINNER[app.tick % SPINNER.len()]),
            _ => String::new(),
        };
        (format!("orchestrated by {}{version} ", o.name), format!("{}{version} ", o.name), format!("{} ", o.name))
    });
    // Drop detail from the right, then the path, until everything fits with a gap.
    let brand_width: usize = brand.iter().map(|s| s.content.chars().count()).sum();
    let rights: Vec<String> = match orchestrator {
        Some((long, medium, short)) => vec![long, medium, short],
        None => vec![String::new()],
    };
    let fits = |left: usize, right: &str| left + 2 + right.chars().count() <= width;
    let (show_path, right) = rights
        .iter()
        .find(|r| fits(brand_width + path.chars().count(), r))
        .map(|r| (true, r.clone()))
        .or_else(|| rights.iter().find(|r| fits(brand_width, r)).map(|r| (false, r.clone())))
        .unwrap_or((false, String::new()));
    let mut spans = brand.to_vec();
    if show_path {
        spans.push(Span::styled(path, t.muted()));
    }
    let used: usize = spans.iter().map(|s| s.content.chars().count()).sum();
    spans.push(Span::raw(" ".repeat(width.saturating_sub(used + right.chars().count()))));
    spans.push(Span::styled(right, t.muted()));
    frame.render_widget(Paragraph::new(Line::from(spans)), area);
}

/// Shortens `text` to `width` characters, ending in an ellipsis when cut.
fn fit(text: &str, width: usize) -> String {
    if text.chars().count() <= width {
        return text.to_string();
    }
    if width == 0 {
        return String::new();
    }
    let mut out: String = text.chars().take(width - 1).collect();
    out.truncate(out.trim_end().len());
    out.push('…');
    out
}

/// Width left for a table's last column inside a bordered block, after the
/// fixed columns and ratatui's default one-cell column spacing.
fn last_column(area: Rect, fixed: &[u16]) -> usize {
    let used: u16 = fixed.iter().sum::<u16>() + fixed.len() as u16;
    area.width.saturating_sub(2 + used) as usize
}

fn draw_tabs(frame: &mut Frame, app: &App, area: Rect) {
    let t = &app.theme;
    let count_skills = app.snap.repo.skills.len();
    let count_pi = app.snap.repo.pi.len();
    let count_tools = app.snap.repo.tools.len();
    let pending = |tab: Tab| match tab {
        Tab::Skills => app.skills.len(),
        Tab::Pi => app.pi.len() + usize::from(app.subagents),
        Tab::Tools => app.tools.len(),
    };
    let mut spans = vec![Span::raw(" ")];
    for (key, tab, name, count) in
        [("1", Tab::Skills, "Skills", count_skills), ("2", Tab::Pi, "Pi", count_pi), ("3", Tab::Tools, "Tools", count_tools)]
    {
        let active = app.tab == tab && app.screen == Screen::Browse;
        let style = if active { t.accent().add_modifier(Modifier::BOLD | Modifier::UNDERLINED) } else { t.text() };
        spans.push(Span::styled(format!("{key} "), t.muted()));
        spans.push(Span::styled(name, style));
        spans.push(Span::styled(format!(" {count}"), t.muted()));
        let p = pending(tab);
        if p > 0 {
            spans.push(Span::styled(format!(" ●{p}"), t.peach()));
        }
        spans.push(Span::raw("    "));
    }
    let problems = app.issues.iter().filter(|i| i.level <= Level::Warning).count();
    let right = match (app.screen, problems, app.prune) {
        (Screen::Review, ..) => "Review the plan".to_string(),
        (Screen::Applying, ..) => "Applying".to_string(),
        (Screen::Done, ..) => "Finished".to_string(),
        (_, _, true) => "tidy-up queued".to_string(),
        (_, 0, _) => String::new(),
        (_, n, _) => format!("{n} problem{} · p tidies", if n == 1 { "" } else { "s" }),
    };
    let used: usize = spans.iter().map(|s| s.content.chars().count()).sum();
    let gap = (area.width as usize).saturating_sub(used + right.chars().count() + 1);
    spans.push(Span::raw(" ".repeat(gap)));
    spans.push(Span::styled(right, if problems > 0 && !app.prune { t.yellow() } else { t.muted() }));
    frame.render_widget(Paragraph::new(Line::from(spans)), area);
}

fn panel<'a>(app: &App, title: &'a str, focused: bool) -> Block<'a> {
    let t = &app.theme;
    Block::bordered()
        .border_type(BorderType::Rounded)
        .border_style(if focused { t.focus_border() } else { t.border() })
        .title(Line::from(vec![Span::raw(" "), Span::styled(title, t.bold()), Span::raw(" ")]))
}

/// The glyph and style for one skill × harness cell.
fn cell(app: &App, s: usize, h: usize) -> (&'static str, Style) {
    let t = &app.theme;
    let wanted = app.wanted(s);
    let now = app.snap.visible(s).contains(&h);
    let foreign = app.snap.foreign(s).contains(&h);
    let will = wanted.contains(&h);
    match (now, will) {
        (true, true) => ("●", t.green()),
        (false, true) => {
            if !plan::forced_by(&app.snap, &wanted, h).is_empty() {
                ("◐", t.peach())
            } else if conflict_for(app, s, h).is_some() {
                ("!", t.yellow().add_modifier(Modifier::BOLD))
            } else {
                ("+", t.green().add_modifier(Modifier::BOLD))
            }
        }
        (true, false) => ("−", t.red().add_modifier(Modifier::BOLD)),
        (false, false) if foreign => ("◆", t.yellow()),
        (false, false) => ("·", t.muted()),
    }
}

/// The location harness `h` would load skill `s` from after applying.
fn planned_location(app: &App, s: usize, h: usize) -> Option<usize> {
    let wanted = plan::closure(&app.snap, &app.wanted(s));
    plan::solve(&app.snap, s, &wanted).into_iter().find(|&l| app.snap.locations[l].readers.contains(&h))
}

fn conflict_for(app: &App, s: usize, h: usize) -> Option<(usize, Existing)> {
    let l = planned_location(app, s, h)?;
    match &app.snap.skills[s][l] {
        Entry::Foreign { what } => Some((l, what.clone())),
        _ => None,
    }
}

fn draw_skills(frame: &mut Frame, app: &App, area: Rect) {
    let t = &app.theme;
    let wide = area.width >= 112;
    let [main, side] =
        if wide { Layout::horizontal([Constraint::Min(60), Constraint::Length(46)]).areas(area) } else { [area, Rect::default()] };
    let detail_height = 6;
    let [matrix_area, detail_area] = Layout::vertical([Constraint::Min(4), Constraint::Length(detail_height)]).areas(main);

    let rows = app.rows();
    // The name column takes what the marker, tag and harness columns leave.
    let others = 2 + 9 + 5 * app.columns.len() as u16 + app.columns.len() as u16 + 2;
    let room = matrix_area.width.saturating_sub(2 + others).max(8);
    let name_width = (app.snap.repo.skills.iter().map(|s| s.name.chars().count()).max().unwrap_or(5).clamp(8, 32) as u16 + 1).min(room);
    let mut widths = vec![Constraint::Length(2), Constraint::Length(name_width), Constraint::Length(9)];
    widths.extend(app.columns.iter().map(|_| Constraint::Length(5)));
    let mut header = vec![Cell::from(""), Cell::from("Skill"), Cell::from("")];
    for (c, &h) in app.columns.iter().enumerate() {
        let harness = &app.snap.env.harnesses[h];
        let style = if c == app.col { t.accent().add_modifier(Modifier::BOLD) } else { t.muted() };
        header.push(Cell::from(Line::from(Span::styled(harness.label.clone(), style)).alignment(Alignment::Center)));
    }
    let body: Vec<Row> = rows
        .iter()
        .enumerate()
        .map(|(r, &s)| {
            let skill = &app.snap.repo.skills[s];
            let dirty = app.skills.contains_key(&s);
            let marker = if dirty { Span::styled("●", t.peach()) } else { Span::raw(" ") };
            let mut cells = vec![
                Cell::from(Line::from(vec![Span::raw(" "), marker])),
                Cell::from(Span::styled(fit(&skill.name, name_width as usize - 1), if r == app.row { t.bold() } else { t.text() })),
                Cell::from(Span::styled(short_tags(&skill.tags), t.blue())),
            ];
            for (c, &h) in app.columns.iter().enumerate() {
                let (glyph, mut style) = cell(app, s, h);
                if r == app.row && c == app.col {
                    style = style.patch(t.cursor());
                }
                cells.push(Cell::from(Line::from(Span::styled(format!(" {glyph} "), style)).alignment(Alignment::Center)));
            }
            Row::new(cells)
        })
        .collect();
    let title = if app.filtering || !app.filter.is_empty() {
        format!("Skills · filter: {}{}", app.filter, if app.filtering { "▏" } else { "" })
    } else {
        "Skills × harnesses".to_string()
    };
    let block = panel(app, &title, true);
    if rows.is_empty() {
        let text =
            if app.snap.repo.skills.is_empty() { "This checkout has no skills." } else { "No skills match the filter. Esc clears it." };
        frame.render_widget(Paragraph::new(Span::styled(text, t.muted())).block(block), matrix_area);
    } else if app.columns.is_empty() {
        frame.render_widget(
            Paragraph::new("No harnesses were detected. Install Claude Code, Codex, Grok, Pi, or Kilo, then run ae again.")
                .wrap(Wrap { trim: true })
                .block(block),
            matrix_area,
        );
    } else {
        let table = Table::new(body, widths)
            .header(Row::new(header).style(t.bold()).bottom_margin(0))
            .row_highlight_style(t.row_highlight())
            .block(block);
        let mut state = TableState::default().with_selected(Some(app.row.min(rows.len() - 1)));
        frame.render_stateful_widget(table, matrix_area, &mut state);
    }

    draw_skill_detail(frame, app, detail_area, &rows);
    if wide {
        draw_harness_panel(frame, app, side);
    }
}

fn short_tags(tags: &[String]) -> String {
    tags.iter()
        .map(|tag| match tag.as_str() {
            "T3 Code" => "T3",
            "/command" => "/cmd",
            "auto" => "auto",
            other => other,
        })
        .collect::<Vec<_>>()
        .join(" ")
}

fn draw_skill_detail(frame: &mut Frame, app: &App, area: Rect, rows: &[usize]) {
    let t = &app.theme;
    let block = panel(app, "Details", false);
    let (Some(&s), Some(&h)) = (rows.get(app.row), app.columns.get(app.col)) else {
        frame.render_widget(block, area);
        return;
    };
    let skill = &app.snap.repo.skills[s];
    let harness = &app.snap.env.harnesses[h];
    let env = &app.snap.env;
    let wanted = app.wanted(s);
    let now = app.snap.visible(s).contains(&h);
    let will = wanted.contains(&h);
    let source_of = |h: usize| -> Option<String> {
        app.snap
            .linked_locations(s)
            .into_iter()
            .find(|&l| app.snap.locations[l].readers.contains(&h))
            .map(|l| env.tilde(&app.snap.locations[l].path))
    };
    let status: Line = match (now, will) {
        (true, true) => Line::from(vec![
            Span::styled("● ", t.green()),
            Span::raw(format!("{} loads this from ", harness.name)),
            Span::styled(source_of(h).unwrap_or_default(), t.teal()),
        ]),
        (false, true) => {
            let forced = plan::forced_by(&app.snap, &wanted, h);
            if let Some(&cause) = forced.first() {
                let owner = &env.harnesses[cause];
                Line::from(vec![
                    Span::styled("◐ ", t.peach()),
                    Span::raw(format!("{} gets it too: it also loads {}'s ", harness.name, owner.name)),
                    Span::styled(env.tilde(owner.own_skills()), t.teal()),
                ])
            } else if let Some((l, existing)) = conflict_for(app, s, h) {
                Line::from(vec![
                    Span::styled("! ", t.yellow()),
                    Span::styled(env.tilde(&app.snap.locations[l].path.join(&skill.name)), t.teal()),
                    Span::raw(format!(" is {}; you will be asked before it is backed up", existing.describe())),
                ])
            } else {
                let target = planned_location(app, s, h).map(|l| env.tilde(&app.snap.locations[l].path)).unwrap_or_default();
                Line::from(vec![
                    Span::styled("+ ", t.green()),
                    Span::raw(format!("{} will load it from ", harness.name)),
                    Span::styled(target, t.teal()),
                ])
            }
        }
        (true, false) => Line::from(vec![
            Span::styled("− ", t.red()),
            Span::raw(format!("{} will stop loading it (removes the link in ", harness.name)),
            Span::styled(source_of(h).unwrap_or_default(), t.teal()),
            Span::raw(")"),
        ]),
        (false, false) => {
            if app.snap.foreign(s).contains(&h) {
                Line::from(vec![
                    Span::styled("◆ ", t.yellow()),
                    Span::raw(format!("{} loads a different {} that Æ does not manage", harness.name, skill.name)),
                ])
            } else {
                Line::from(vec![
                    Span::styled("· ", t.muted()),
                    Span::raw(format!("Not installed for {}. ", harness.name)),
                    Span::styled("space", t.bold()),
                    Span::raw(" adds it, "),
                    Span::styled("a", t.bold()),
                    Span::raw(" adds it everywhere."),
                ])
            }
        }
    };
    let mut title = vec![Span::styled(skill.name.clone(), t.bold())];
    for tag in &skill.tags {
        title.push(Span::raw("  "));
        title.push(Span::styled(
            match tag.as_str() {
                "T3 Code" => "needs T3 Code".to_string(),
                "/command" => "runs only when invoked".to_string(),
                "auto" => "loaded automatically".to_string(),
                other => other.to_string(),
            },
            t.blue(),
        ));
    }
    let text = Text::from(vec![Line::from(title), Line::from(Span::styled(skill.description.clone(), t.muted())), status]);
    frame.render_widget(Paragraph::new(text).wrap(Wrap { trim: true }).block(block), area);
}

fn draw_harness_panel(frame: &mut Frame, app: &App, area: Rect) {
    let t = &app.theme;
    let env = &app.snap.env;
    let focused = app.columns.get(app.col).copied();
    let mut lines: Vec<Line> = Vec::new();
    for (h, harness) in env.harnesses.iter().enumerate() {
        let is_focus = Some(h) == focused;
        let dot = if !harness.detected {
            Span::styled("○ ", t.muted())
        } else if harness.disabled {
            Span::styled("◌ ", t.yellow())
        } else {
            Span::styled("● ", t.green())
        };
        let version = match (&harness.version, app.probing && harness.binary.is_some()) {
            (Some(v), _) => v.clone(),
            (None, true) => SPINNER[app.tick % SPINNER.len()].to_string(),
            _ => String::new(),
        };
        let name_style = if is_focus {
            t.accent().add_modifier(Modifier::BOLD)
        } else if harness.detected {
            t.text()
        } else {
            t.muted()
        };
        lines.push(Line::from(vec![
            dot,
            Span::styled(format!("{:<4}", harness.label), t.muted()),
            Span::styled(format!("{:<18}", harness.name), name_style),
            Span::styled(version, t.muted()),
        ]));
        let detail = if harness.detected { env.tilde(&harness.home) } else { "not found".to_string() };
        lines.push(Line::from(vec![Span::raw("      "), Span::styled(detail, t.muted())]));
        if is_focus && harness.detected {
            for dir in &harness.skill_dirs {
                let shared: Vec<String> = app
                    .snap
                    .locations
                    .iter()
                    .find(|l| l.path == *dir)
                    .map(|l| l.readers.iter().filter(|&&r| r != h).map(|&r| env.harnesses[r].label.clone()).collect())
                    .unwrap_or_default();
                let mut spans = vec![Span::raw("      "), Span::styled("↳ ", t.accent()), Span::styled(env.tilde(dir), t.teal())];
                if !shared.is_empty() {
                    spans.push(Span::styled(format!("  +{}", shared.join(" ")), t.muted()));
                }
                lines.push(Line::from(spans));
            }
        }
    }
    lines.push(Line::raw(""));
    lines.push(Line::from(Span::styled("Legend", t.bold())));
    for (glyph, style, text) in [
        ("●", t.green(), "loads this checkout's copy"),
        ("+", t.green(), "will be added"),
        ("−", t.red(), "will be removed"),
        ("◐", t.peach(), "comes along via a shared folder"),
        ("◆", t.yellow(), "a different copy, not managed"),
        ("!", t.yellow(), "something is in the way"),
    ] {
        lines.push(Line::from(vec![Span::styled(format!(" {glyph} "), style), Span::styled(text, t.muted())]));
    }
    frame.render_widget(Paragraph::new(lines).block(panel(app, "Harnesses", false)), area);
}

fn pi_glyph(app: &App, i: usize) -> (&'static str, Style) {
    let t = &app.theme;
    let item = &app.snap.repo.pi[i];
    if item.kind == PiKind::Subagents {
        return match app.snap.subagents.as_ref().map(|s| &s.state) {
            Some(SubagentState::Installed) => ("●", t.green()),
            Some(SubagentState::NeedsChanges) if app.subagents => ("+", t.green().add_modifier(Modifier::BOLD)),
            Some(SubagentState::NeedsChanges) => ("·", t.muted()),
            Some(SubagentState::Invalid) => ("✗", t.red()),
            _ => ("?", t.muted()),
        };
    }
    let entry = &app.snap.pi[i];
    match (entry, app.pi.get(&i)) {
        (Entry::Linked, Some(false)) => ("−", t.red().add_modifier(Modifier::BOLD)),
        (Entry::Linked, _) => ("●", t.green()),
        (Entry::Foreign { .. }, Some(true)) => ("!", t.yellow().add_modifier(Modifier::BOLD)),
        (Entry::Foreign { .. }, _) => ("◆", t.yellow()),
        (_, Some(true)) => ("+", t.green().add_modifier(Modifier::BOLD)),
        _ => ("·", t.muted()),
    }
}

const PI_COLUMNS: [u16; 3] = [12, 3, 28];
const TOOL_COLUMNS: [u16; 5] = [3, 8, 8, 18, 6];

fn draw_pi(frame: &mut Frame, app: &App, area: Rect) {
    let t = &app.theme;
    let [list, detail] = Layout::vertical([Constraint::Min(4), Constraint::Length(5)]).areas(area);
    let Some(pi_dir) = &app.snap.pi_dir else {
        frame.render_widget(Paragraph::new("Pi was not detected.").block(panel(app, "Pi", true)), area);
        return;
    };
    if app.snap.repo.pi.is_empty() {
        frame.render_widget(
            Paragraph::new(Span::styled("This checkout has no harness/pi resources.", t.muted())).block(panel(app, "Pi", true)),
            area,
        );
        return;
    }
    let about = last_column(list, &PI_COLUMNS);
    let mut last_group = "";
    let rows: Vec<Row> = app
        .snap
        .repo
        .pi
        .iter()
        .enumerate()
        .map(|(i, item)| {
            let group = item.kind.group();
            let group_cell = if group != last_group {
                last_group = group;
                Span::styled(group, t.muted())
            } else {
                Span::raw("")
            };
            let (glyph, style) = pi_glyph(app, i);
            let name = item.id.rsplit_once('/').map(|(_, n)| n).unwrap_or(&item.id).to_string();
            Row::new(vec![
                Cell::from(group_cell),
                Cell::from(Span::styled(format!(" {glyph} "), style)),
                Cell::from(Span::styled(name, if i == app.pi_row { t.bold() } else { t.text() })),
                Cell::from(Span::styled(fit(item.description.as_deref().unwrap_or(""), about), t.muted())),
            ])
        })
        .collect();
    let title = format!("Pi resources → {}", app.snap.env.tilde(pi_dir));
    let table = Table::new(rows, PI_COLUMNS.iter().map(|&w| Constraint::Length(w)).chain([Constraint::Min(10)]))
        .row_highlight_style(t.cursor())
        .block(panel(app, &title, true));
    let mut state = TableState::default().with_selected(Some(app.pi_row));
    frame.render_stateful_widget(table, list, &mut state);

    let item = &app.snap.repo.pi[app.pi_row.min(app.snap.repo.pi.len() - 1)];
    let env = &app.snap.env;
    let mut lines = vec![Line::from(vec![
        Span::styled(item.id.clone(), t.bold()),
        Span::raw("  "),
        Span::styled(env.tilde(&pi_dir.join(&item.target)), t.teal()),
    ])];
    if item.kind == PiKind::Subagents {
        if let Some(sub) = &app.snap.subagents {
            for line in sub.preview.iter().take(2) {
                lines.push(Line::from(Span::styled(line.clone(), t.muted())));
            }
            if let Some(message) = &sub.message {
                lines.push(Line::from(Span::styled(message.clone(), t.yellow())));
            }
        }
    } else if let Entry::Foreign { what } = &app.snap.pi[app.pi_row] {
        lines.push(Line::from(Span::styled(
            format!("Currently {}; adding it backs that up first, after you approve.", what.describe()),
            t.yellow(),
        )));
    } else if let Some(description) = &item.description {
        lines.push(Line::from(Span::styled(description.clone(), t.muted())));
    }
    frame.render_widget(Paragraph::new(lines).wrap(Wrap { trim: true }).block(panel(app, "Details", false)), detail);
}

fn draw_tools(frame: &mut Frame, app: &App, area: Rect) {
    let t = &app.theme;
    if app.snap.repo.tools.is_empty() {
        frame.render_widget(Paragraph::new(Span::styled("This checkout has no tools.", t.muted())).block(panel(app, "Tools", true)), area);
        return;
    }
    let about = last_column(area, &TOOL_COLUMNS);
    let rows: Vec<Row> = app
        .snap
        .repo
        .tools
        .iter()
        .enumerate()
        .map(|(i, tool)| {
            let version = tool.version.clone().unwrap_or_default();
            let installed = app.snap.tools[i].as_ref();
            let queued = app.tools.contains(&i);
            let (glyph, style, state) = match installed {
                Some(inst) if inst.from_this_checkout && inst.version == version => {
                    if queued {
                        ("↻", t.green(), "reinstall".to_string())
                    } else {
                        ("●", t.green(), "installed".to_string())
                    }
                }
                Some(inst) if inst.from_this_checkout => {
                    if queued {
                        ("↻", t.green(), format!("{} → {version}", inst.version))
                    } else {
                        ("◐", t.peach(), format!("{} installed", inst.version))
                    }
                }
                Some(inst) => (if queued { "!" } else { "◆" }, t.yellow(), format!("{} from elsewhere", inst.version)),
                None => {
                    if queued {
                        ("+", t.green(), "install".to_string())
                    } else {
                        ("·", t.muted(), "not installed".to_string())
                    }
                }
            };
            let style = if queued { style.add_modifier(Modifier::BOLD) } else { style };
            Row::new(vec![
                Cell::from(Span::styled(format!(" {glyph} "), style)),
                Cell::from(Span::styled(tool.name.clone(), t.bold())),
                Cell::from(Span::styled(version, t.muted())),
                Cell::from(Span::styled(state, style)),
                Cell::from(Span::styled(tool.bins.join(" "), t.teal())),
                Cell::from(Span::styled(fit(tool.description.as_deref().unwrap_or(""), about), t.muted())),
            ])
        })
        .collect();
    let table = Table::new(rows, TOOL_COLUMNS.iter().map(|&w| Constraint::Length(w)).chain([Constraint::Min(10)]))
        .header(Row::new(vec!["", "Tool", "Version", "State", "Bin", "About"]).style(t.bold()))
        .row_highlight_style(t.cursor())
        .block(panel(app, "Tools · built with cargo install --path", true));
    let mut state = TableState::default().with_selected(Some(app.tool_row));
    frame.render_stateful_widget(table, area, &mut state);
}

fn draw_review(frame: &mut Frame, app: &App, area: Rect) {
    let t = &app.theme;
    let plan = &app.plan;
    let mut lines: Vec<Line> = Vec::new();
    let mut selected_line = 0;
    let summary = {
        let approved = plan.approved_count();
        let skipped = plan.pending_conflicts();
        let mut spans = vec![Span::styled(format!("{approved} change{}", if approved == 1 { "" } else { "s" }), t.bold())];
        if skipped > 0 {
            spans.push(Span::styled(format!(" · {skipped} conflict{} skipped", if skipped == 1 { "" } else { "s" }), t.yellow()));
        }
        spans.push(Span::styled("  ·  only symlinks into this checkout are created or removed", t.muted()));
        Line::from(spans)
    };
    lines.push(summary);
    for section in [Section::Skills, Section::Pi, Section::Tools, Section::Tidy] {
        let steps: Vec<usize> = (0..plan.steps.len()).filter(|&i| plan.steps[i].section == section).collect();
        if steps.is_empty() {
            continue;
        }
        lines.push(Line::raw(""));
        lines.push(Line::from(Span::styled(section.title(), t.accent().add_modifier(Modifier::BOLD))));
        for i in steps {
            let step = &plan.steps[i];
            if i == app.plan_row {
                selected_line = lines.len();
            }
            let (glyph, style) = match &step.op {
                Op::Unlink { .. } => ("−", t.red()),
                Op::Replace { .. } => ("!", t.yellow()),
                Op::Relink { .. } => ("~", t.blue()),
                Op::Subagents { .. } => ("⇄", t.green()),
                Op::CargoInstall { from: Some(_), .. } => ("↻", t.green()),
                _ => ("+", t.green()),
            };
            let cursor = if i == app.plan_row { Span::styled("▸ ", t.accent()) } else { Span::raw("  ") };
            let mut spans = vec![cursor];
            if step.needs_approval {
                spans.push(Span::styled(if step.approved { "[✓] " } else { "[ ] " }, t.yellow()));
            }
            spans.push(Span::styled(format!("{glyph} "), style.add_modifier(Modifier::BOLD)));
            spans.push(Span::styled(step.name.clone(), t.bold()));
            if !step.readers.is_empty() && section != Section::Pi {
                spans.push(Span::styled(format!("   {}", step.readers.join(" · ")), t.teal()));
            }
            let row_style = if i == app.plan_row { t.row_highlight() } else { Style::default() };
            lines.push(Line::from(spans).style(row_style));
            lines.push(Line::from(Span::styled(format!("      {}", describe_step(&app.snap, &step.op)), t.muted())).style(row_style));
            if let Op::Subagents { preview, .. } = &step.op {
                for line in preview {
                    lines.push(Line::from(Span::styled(format!("      {line}"), t.muted())));
                }
            }
        }
    }
    let inner_height = area.height.saturating_sub(2) as usize;
    let scroll = selected_line.saturating_sub(inner_height.saturating_sub(4)) as u16;
    frame.render_widget(Paragraph::new(lines).scroll((scroll, 0)).block(panel(app, "Review the plan", true)), area);
}

fn draw_applying(frame: &mut Frame, app: &App, area: Rect) {
    let t = &app.theme;
    let Some(applying) = &app.applying else { return };
    let [gauge_area, list_area] = Layout::vertical([Constraint::Length(3), Constraint::Min(3)]).areas(area);
    let total = applying.order.len().max(1);
    let finished = applying.order.iter().filter(|&&i| matches!(applying.statuses[i], StepStatus::Finished { .. })).count();
    let running_fraction = applying
        .order
        .iter()
        .find_map(|&i| match &applying.statuses[i] {
            StepStatus::Running { fraction, .. } => Some(fraction.unwrap_or(0.0)),
            _ => None,
        })
        .unwrap_or(0.0);
    let ratio = if applying.finished.is_some() { 1.0 } else { ((finished as f64 + running_fraction) / total as f64).min(1.0) };
    let elapsed = applying.finished.unwrap_or_else(|| applying.started.elapsed());
    let failures = applying.statuses.iter().filter(|s| matches!(s, StepStatus::Finished { outcome: Outcome::Failed(_), .. })).count();
    let label = match applying.finished {
        Some(_) if failures > 0 => {
            format!("Finished with {failures} error{} in {:.1}s", if failures == 1 { "" } else { "s" }, elapsed.as_secs_f64())
        }
        Some(_) => format!("All {total} done in {:.1}s", elapsed.as_secs_f64()),
        None => format!("{finished} of {total} · {:.1}s", elapsed.as_secs_f64()),
    };
    let gauge_style = if failures > 0 {
        t.red()
    } else if applying.finished.is_some() {
        t.green()
    } else {
        t.accent()
    };
    frame.render_widget(
        Gauge::default()
            .block(panel(app, if applying.finished.is_some() { "Done" } else { "Applying" }, true))
            .gauge_style(gauge_style)
            .ratio(ratio)
            .label(Span::styled(label, t.bold())),
        gauge_area,
    );

    let mut lines: Vec<Line> = Vec::new();
    let mut focus = 0;
    for &i in &applying.order {
        let step = &app.plan.steps[i];
        let what = describe_step(&app.snap, &step.op);
        match &applying.statuses[i] {
            StepStatus::Pending => lines.push(Line::from(vec![
                Span::styled("  ○ ", t.muted()),
                Span::styled(step.name.clone(), t.muted()),
                Span::styled(format!("  {what}"), t.muted()),
            ])),
            StepStatus::NotRun => lines.push(Line::from(vec![
                Span::styled("  – ", t.yellow()),
                Span::styled(step.name.clone(), t.muted()),
                Span::styled("  not run (stopped)", t.yellow()),
            ])),
            StepStatus::Running { started, fraction, line } => {
                focus = lines.len();
                lines.push(Line::from(vec![
                    Span::styled(format!("  {} ", SPINNER[app.tick % SPINNER.len()]), t.accent()),
                    Span::styled(step.name.clone(), t.bold()),
                    Span::styled(format!("  {what}"), t.muted()),
                    Span::styled(format!("  {:.0}s", started.elapsed().as_secs_f64()), t.muted()),
                ]));
                if matches!(step.op, Op::CargoInstall { .. }) {
                    let width = 28usize;
                    let filled = ((fraction.unwrap_or(0.0) * width as f64).round() as usize).min(width);
                    lines.push(Line::from(vec![
                        Span::raw("    "),
                        Span::styled("━".repeat(filled), t.accent()),
                        Span::styled("─".repeat(width - filled), t.border()),
                        Span::styled(format!("  {line}"), t.muted()),
                    ]));
                }
            }
            StepStatus::Finished { outcome, elapsed } => {
                let time = if elapsed.as_secs_f64() >= 1.0 { format!("  {:.1}s", elapsed.as_secs_f64()) } else { String::new() };
                let (glyph, style, note) = match outcome {
                    Outcome::Done(detail) => ("✓", t.green(), detail.clone().map(|d| format!(" · {d}")).unwrap_or_default()),
                    Outcome::Skipped(why) => ("–", t.yellow(), format!(" · {why}")),
                    Outcome::Failed(why) => ("✗", t.red(), format!(" · {why}")),
                };
                lines.push(Line::from(vec![
                    Span::styled(format!("  {glyph} "), style.add_modifier(Modifier::BOLD)),
                    Span::styled(step.name.clone(), t.bold()),
                    Span::styled(format!("  {what}"), t.muted()),
                    Span::styled(note, if matches!(outcome, Outcome::Done(_)) { t.muted() } else { style }),
                    Span::styled(time, t.muted()),
                ]));
            }
        }
    }
    if applying.finished.is_some()
        && let Some(hint) = crate::output::restart_hint(&app.plan)
    {
        lines.push(Line::raw(""));
        lines.push(Line::from(Span::styled(format!("  {hint}"), t.teal())));
    }
    let inner = list_area.height.saturating_sub(2) as usize;
    let scroll = focus.saturating_sub(inner.saturating_sub(3)) as u16;
    frame.render_widget(Paragraph::new(lines).scroll((scroll, 0)).wrap(Wrap { trim: false }).block(panel(app, "Steps", false)), list_area);
}

fn draw_message(frame: &mut Frame, app: &App, area: Rect) {
    let t = &app.theme;
    let line = if app.confirm_quit {
        Line::from(vec![
            Span::styled(" ? ", t.yellow().add_modifier(Modifier::BOLD)),
            Span::raw(format!("Discard {} pending change{} and quit? ", app.pending(), if app.pending() == 1 { "" } else { "s" })),
            Span::styled("y", t.bold()),
            Span::raw("/"),
            Span::styled("N", t.bold()),
        ])
    } else if let Some((text, tone)) = &app.message {
        let (mark, style) = match tone {
            Tone::Info => (" i ", t.blue()),
            Tone::Warn => (" ! ", t.yellow()),
            Tone::Good => (" ✓ ", t.green()),
        };
        Line::from(vec![Span::styled(mark, style.add_modifier(Modifier::BOLD)), Span::raw(text.clone())])
    } else if app.screen == Screen::Browse && app.pending() > 0 {
        Line::from(vec![
            Span::styled(" ● ", t.peach()),
            Span::raw(format!("{} pending · ", app.pending())),
            Span::styled("enter", t.bold()),
            Span::raw(" to review the plan · "),
            Span::styled("R", t.bold()),
            Span::raw(" clears all"),
        ])
    } else {
        Line::raw("")
    };
    frame.render_widget(Paragraph::new(line), area);
}

fn draw_footer(frame: &mut Frame, app: &App, area: Rect) {
    let t = &app.theme;
    let keys: &[(&str, &str)] = match (app.screen, app.tab) {
        (Screen::Browse, _) if app.filtering => &[("type", "filter"), ("enter", "keep"), ("esc", "clear")],
        (Screen::Browse, Tab::Skills) => &[
            ("↑↓←→", "move"),
            ("space", "toggle"),
            ("a", "row"),
            ("A", "column"),
            ("/", "filter"),
            ("tab", "Pi · Tools"),
            ("enter", "review"),
            ("?", "help"),
            ("q", "quit"),
        ],
        (Screen::Browse, Tab::Tools) => &[
            ("↑↓", "move"),
            ("space", "install/update"),
            ("a", "all"),
            ("tab", "switch"),
            ("enter", "review"),
            ("?", "help"),
            ("q", "quit"),
        ],
        (Screen::Browse, Tab::Pi) => {
            &[("↑↓", "move"), ("space", "toggle"), ("tab", "switch"), ("enter", "review"), ("?", "help"), ("q", "quit")]
        }
        (Screen::Review, _) => &[("↑↓", "move"), ("space", "approve/skip conflict"), ("enter", "apply"), ("esc", "back")],
        (Screen::Applying, _) => &[("ctrl-c", "stop after this step")],
        (Screen::Done, _) => &[("enter", "make more changes"), ("q", "quit")],
    };
    // On narrow terminals, drop optional hints from the right; the ways to
    // review, get help, go back and quit always stay.
    let mut keys = keys.to_vec();
    let width = |keys: &[(&str, &str)]| 1 + keys.iter().map(|(k, w)| k.chars().count() + w.chars().count() + 4).sum::<usize>();
    while width(&keys) > area.width as usize + 3 {
        let Some(drop) = keys.iter().rposition(|(k, _)| !matches!(*k, "enter" | "?" | "q" | "esc")) else { break };
        keys.remove(drop);
    }
    let mut spans = vec![Span::raw(" ")];
    for (key, what) in &keys {
        spans.push(Span::styled(*key, t.accent().add_modifier(Modifier::BOLD)));
        spans.push(Span::styled(format!(" {what}   "), t.muted()));
    }
    frame.render_widget(Paragraph::new(Line::from(spans)), area);
}

fn draw_help(frame: &mut Frame, app: &App, area: Rect) {
    let t = &app.theme;
    let width = area.width.min(74);
    let height = area.height.min(24);
    let popup = Rect { x: area.x + (area.width - width) / 2, y: area.y + (area.height - height) / 2, width, height };
    let key = |k: &str, v: &str| {
        Line::from(vec![Span::styled(format!("  {k:<12}"), t.accent().add_modifier(Modifier::BOLD)), Span::raw(v.to_string())])
    };
    let shared: Vec<String> = app
        .snap
        .locations
        .iter()
        .filter(|l| l.readers.len() > 1)
        .map(|l| {
            let names: Vec<String> = l.readers.iter().map(|&h| app.snap.env.harnesses[h].name.clone()).collect();
            format!("{} → {}", app.snap.env.tilde(&l.path), join(&names))
        })
        .collect();
    let mut lines = vec![
        Line::from(Span::styled("Keys", t.bold())),
        key("↑ ↓ ← →", "move (or h j k l)"),
        key("space", "toggle the highlighted skill, Pi item, or tool"),
        key("a / A", "toggle the whole row / the whole column"),
        key("/", "filter skills by name or description"),
        key("tab, 1 2 3", "switch between Skills, Pi, and Tools"),
        key("p", "remove stale and redundant links"),
        key("r / R", "reset this row / every pending change"),
        key("enter", "review the plan; nothing changes before you confirm"),
        key("q", "quit"),
        Line::raw(""),
        Line::from(Span::styled("Shared folders", t.bold())),
    ];
    for entry in shared {
        lines.push(Line::from(Span::styled(format!("  {entry}"), t.muted())));
    }
    lines.push(Line::raw(""));
    lines.push(Line::from(Span::styled(
        "Æ only creates or removes symlinks into this checkout. Anything else in the way is backed up, and only after you approve it.",
        t.muted(),
    )));
    frame.render_widget(Clear, popup);
    frame.render_widget(Paragraph::new(lines).wrap(Wrap { trim: true }).block(panel(app, "Help · any key closes", true)), popup);
}

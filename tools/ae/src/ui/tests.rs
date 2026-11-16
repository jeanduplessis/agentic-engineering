use super::*;
use crate::harness::{Environment, Vars};
use crate::repo::Repo;
use ratatui::Terminal;
use ratatui::backend::TestBackend;
use ratatui::crossterm::event::{KeyCode, KeyEvent, KeyModifiers};
use std::path::Path;

struct Fixture {
    _dir: tempfile::TempDir,
    root: std::path::PathBuf,
    home: std::path::PathBuf,
}

fn fixture() -> Fixture {
    let dir = tempfile::tempdir().unwrap();
    let base = std::fs::canonicalize(dir.path()).unwrap();
    let root = base.join("repo");
    let home = base.join("home");
    for skill in ["alpha", "beta"] {
        let path = root.join("skills").join(skill);
        std::fs::create_dir_all(&path).unwrap();
        std::fs::write(path.join("SKILL.md"), format!("---\nname: {skill}\ndescription: The {skill} skill.\n---\nBody\n")).unwrap();
    }
    for harness in [".claude", ".claude_personal", ".codex", ".grok"] {
        std::fs::create_dir_all(home.join(harness)).unwrap();
    }
    std::fs::create_dir_all(home.join(".t3/userdata")).unwrap();
    std::fs::write(
        home.join(".t3/userdata/settings.json"),
        r#"{"providerInstances": {
            "claudeAgent": {"driver": "claudeAgent", "displayName": "Claude Work"},
            "claudeAgent_claude_personal": {"driver": "claudeAgent", "displayName": "Claude Personal",
                "config": {"homePath": "~/.claude_personal"}}}}"#,
    )
    .unwrap();
    Fixture { _dir: dir, root, home }
}

fn app(fixture: &Fixture) -> App {
    let vars = Vars([("HOME".to_string(), fixture.home.display().to_string()), ("PATH".to_string(), String::new())].into());
    let env = Environment::detect(&vars);
    let snap = Snapshot::take(Repo::discover(&fixture.root), env, &BTreeSet::new());
    App::new(snap, Theme::plain())
}

fn press(app: &mut App, code: KeyCode) {
    app.handle_key(KeyEvent::new(code, KeyModifiers::NONE));
}

fn screen(app: &App, width: u16, height: u16) -> String {
    let mut terminal = Terminal::new(TestBackend::new(width, height)).unwrap();
    terminal.draw(|frame| view::draw(frame, app)).unwrap();
    let buffer = terminal.backend().buffer().clone();
    let mut out = String::new();
    for y in 0..buffer.area.height {
        for x in 0..buffer.area.width {
            out.push_str(buffer[(x, y)].symbol());
        }
        out.push('\n');
    }
    out
}

fn harness(app: &App, id: &str) -> usize {
    app.snap.env.harness(id).unwrap()
}

#[test]
fn first_frame_shows_matrix_harnesses_and_hints() {
    let fixture = fixture();
    let app = app(&fixture);
    let text = screen(&app, 140, 30);
    assert!(text.contains("Skills × harnesses"), "{text}");
    assert!(text.contains("alpha") && text.contains("beta"));
    assert!(text.contains("Claude Personal") && text.contains("Grok"));
    assert!(text.contains("CW") && text.contains("Cdx"));
    assert!(text.contains("enter review"));
}

#[test]
fn small_terminals_get_a_clear_message() {
    let fixture = fixture();
    let app = app(&fixture);
    assert!(screen(&app, 40, 10).contains("needs a terminal of at least"));
}

#[test]
fn claude_work_brings_grok_along_and_grok_cannot_be_removed_alone() {
    let fixture = fixture();
    let mut app = app(&fixture);
    let (work, grok) = (harness(&app, "claude-work"), harness(&app, "grok"));
    app.col = app.columns.iter().position(|&h| h == work).unwrap();
    press(&mut app, KeyCode::Char(' '));
    assert_eq!(app.wanted(0), BTreeSet::from([work, grok]));
    assert!(app.message.as_ref().unwrap().0.contains("Grok"));
    app.col = app.columns.iter().position(|&h| h == grok).unwrap();
    press(&mut app, KeyCode::Char(' '));
    assert_eq!(app.wanted(0), BTreeSet::from([work, grok]), "Grok stays while Claude Work has it");
    assert_eq!(app.message.as_ref().unwrap().1, Tone::Warn);
    let text = screen(&app, 140, 30);
    assert!(text.contains("◐"), "Grok's cell shows it comes along:\n{text}");
}

#[test]
fn review_then_apply_links_and_reports() {
    let fixture = fixture();
    let mut app = app(&fixture);
    let personal = harness(&app, "claude-personal");
    app.col = app.columns.iter().position(|&h| h == personal).unwrap();
    press(&mut app, KeyCode::Char(' '));
    press(&mut app, KeyCode::Enter);
    assert_eq!(app.screen, Screen::Review);
    let text = screen(&app, 120, 30);
    assert!(text.contains("Review the plan") && text.contains("1 change"), "{text}");
    press(&mut app, KeyCode::Enter);
    assert_eq!(app.screen, Screen::Applying);
    for _ in 0..200 {
        app.drain();
        if app.screen == Screen::Done {
            break;
        }
        std::thread::sleep(Duration::from_millis(5));
    }
    assert_eq!(app.screen, Screen::Done);
    let link = fixture.home.join(".claude_personal/skills/alpha");
    assert_eq!(std::fs::read_link(&link).unwrap(), fixture.root.join("skills/alpha"));
    assert!(screen(&app, 120, 30).contains("All 1 done"));
    press(&mut app, KeyCode::Enter);
    assert_eq!(app.screen, Screen::Browse);
    assert!(app.snap.visible(0).contains(&personal), "refreshed after apply");
}

#[test]
fn filter_narrows_rows_and_quit_asks_when_changes_are_pending() {
    let fixture = fixture();
    let mut app = app(&fixture);
    press(&mut app, KeyCode::Char('/'));
    for c in "bet".chars() {
        press(&mut app, KeyCode::Char(c));
    }
    assert_eq!(app.rows(), vec![1]);
    press(&mut app, KeyCode::Esc);
    assert_eq!(app.rows().len(), 2);
    press(&mut app, KeyCode::Char('a'));
    assert!(app.pending() > 0);
    press(&mut app, KeyCode::Char('q'));
    assert!(app.confirm_quit && !app.quit);
    press(&mut app, KeyCode::Char('n'));
    assert!(!app.quit);
    press(&mut app, KeyCode::Char('q'));
    press(&mut app, KeyCode::Char('y'));
    assert!(app.quit);
}

#[test]
fn row_toggle_uses_fewest_folders_without_double_loading() {
    let fixture = fixture();
    let mut app = app(&fixture);
    press(&mut app, KeyCode::Char('a'));
    let plan = app.pending_plan();
    let dests: BTreeSet<String> =
        plan.steps.iter().filter_map(|s| s.op.dest()).map(|d| d.strip_prefix(&fixture.home).unwrap().display().to_string()).collect();
    // Claude Work's folder also serves Grok; Codex gets its own so nothing loads twice.
    assert_eq!(
        dests,
        BTreeSet::from([
            ".claude/skills/alpha".to_string(),
            ".claude_personal/skills/alpha".to_string(),
            ".codex/skills/alpha".to_string(),
        ])
    );
    let _ = Path::new("");
}

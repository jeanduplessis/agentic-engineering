use std::cell::RefCell;
use std::collections::HashMap;
use std::fs;
use std::path::Path;

use git2::{
    Delta, Diff, DiffDelta, DiffFindOptions, DiffLine, DiffOptions, FileMode, Oid, Repository,
    Status, StatusOptions, SubmoduleIgnore,
};
use thiserror::Error;

use crate::model::{
    BranchHeader, Entry, EntryStats, LatestCommit, Section, SectionKind, StatusSymbol, StatusView,
};

#[derive(Debug, Error)]
pub enum InspectError {
    #[error("not a git repository")]
    NotGitRepository,
    #[error("{0}")]
    Git(#[from] git2::Error),
    #[error("{0}")]
    Io(#[from] std::io::Error),
    #[error("repository has no working directory")]
    BareRepository,
}

pub fn inspect_repository(cwd: &Path) -> Result<StatusView, InspectError> {
    let repo = Repository::discover(cwd).map_err(|error| {
        if error.code() == git2::ErrorCode::NotFound {
            InspectError::NotGitRepository
        } else {
            InspectError::Git(error)
        }
    })?;

    let header = branch_header(&repo)?;
    let latest_commit = latest_commit(&repo)?;
    let staged = diff_entries(&repo, SectionKind::Staged)?;
    let tracked = diff_entries(&repo, SectionKind::Tracked)?;
    let untracked = untracked_entries(&repo)?;

    let sections = vec![
        Section::new(SectionKind::Staged, staged),
        Section::new(SectionKind::Tracked, tracked),
        Section::new(SectionKind::Untracked, untracked),
    ];

    Ok(StatusView {
        header,
        latest_commit,
        sections,
    })
}

fn latest_commit(repo: &Repository) -> Result<Option<LatestCommit>, InspectError> {
    let head = match repo.head() {
        Ok(head) => head,
        Err(error) if error.code() == git2::ErrorCode::UnbornBranch => return Ok(None),
        Err(error) if error.code() == git2::ErrorCode::NotFound => return Ok(None),
        Err(error) => return Err(InspectError::Git(error)),
    };
    let commit = head.peel_to_commit()?;
    let subject = commit
        .message_bytes()
        .split(|byte| *byte == b'\n')
        .next()
        .map(String::from_utf8_lossy)
        .unwrap_or_default()
        .into_owned();

    Ok(Some(LatestCommit {
        short_hash: short_oid(repo, commit.id())?,
        subject,
    }))
}

fn branch_header(repo: &Repository) -> Result<BranchHeader, InspectError> {
    match repo.head() {
        Ok(head) if head.is_branch() => {
            let name = head.shorthand().unwrap_or("HEAD").to_string();
            let (ahead, behind) = upstream_divergence(repo, &name, head.target())?;
            Ok(BranchHeader::Branch {
                name,
                ahead,
                behind,
            })
        }
        Ok(head) => {
            let oid = head
                .target()
                .or_else(|| head.peel_to_commit().ok().map(|commit| commit.id()))
                .unwrap_or_else(Oid::zero);
            Ok(BranchHeader::Detached {
                short_sha: short_oid(repo, oid)?,
            })
        }
        Err(error) if error.code() == git2::ErrorCode::UnbornBranch => {
            let name = repo
                .find_reference("HEAD")
                .ok()
                .and_then(|reference| reference.symbolic_target().map(str::to_string))
                .and_then(|target| target.strip_prefix("refs/heads/").map(str::to_string))
                .unwrap_or_else(|| "HEAD".to_string());
            Ok(BranchHeader::Branch {
                name,
                ahead: 0,
                behind: 0,
            })
        }
        Err(error) => Err(InspectError::Git(error)),
    }
}

fn upstream_divergence(
    repo: &Repository,
    branch_name: &str,
    local_oid: Option<Oid>,
) -> Result<(usize, usize), InspectError> {
    let Some(local_oid) = local_oid else {
        return Ok((0, 0));
    };

    let Ok(branch) = repo.find_branch(branch_name, git2::BranchType::Local) else {
        return Ok((0, 0));
    };
    let Ok(upstream) = branch.upstream() else {
        return Ok((0, 0));
    };
    let Some(upstream_oid) = upstream.get().target() else {
        return Ok((0, 0));
    };

    Ok(repo.graph_ahead_behind(local_oid, upstream_oid)?)
}

fn short_oid(repo: &Repository, oid: Oid) -> Result<String, InspectError> {
    Ok(repo
        .find_object(oid, None)?
        .short_id()?
        .as_str()
        .unwrap_or("0000000")
        .to_string())
}

fn diff_entries(repo: &Repository, section_kind: SectionKind) -> Result<Vec<Entry>, InspectError> {
    let index = repo.index()?;
    let mut opts = DiffOptions::new();
    opts.include_typechange(true)
        .recurse_untracked_dirs(true)
        .ignore_submodules(true);

    let mut diff = match section_kind {
        SectionKind::Staged => {
            let head_tree = head_tree(repo)?;
            repo.diff_tree_to_index(head_tree.as_ref(), Some(&index), Some(&mut opts))?
        }
        SectionKind::Tracked => {
            opts.include_untracked(false);
            repo.diff_index_to_workdir(Some(&index), Some(&mut opts))?
        }
        SectionKind::Untracked => unreachable!("untracked entries do not come from tracked diffs"),
    };

    let mut find = DiffFindOptions::new();
    find.renames(true).rename_threshold(50);
    diff.find_similar(Some(&mut find))?;

    let mut entries = entries_from_diff(repo, &diff)?;
    if section_kind == SectionKind::Tracked {
        entries.extend(submodule_workdir_entries(repo, &entries)?);
    }
    Ok(entries)
}

fn head_tree(repo: &Repository) -> Result<Option<git2::Tree<'_>>, InspectError> {
    match repo.head() {
        Ok(head) => Ok(Some(head.peel_to_tree()?)),
        Err(error) if error.code() == git2::ErrorCode::UnbornBranch => Ok(None),
        Err(error) if error.code() == git2::ErrorCode::NotFound => Ok(None),
        Err(error) => Err(InspectError::Git(error)),
    }
}

#[derive(Debug)]
struct DiffEntryBuilder {
    symbol: StatusSymbol,
    display_path: String,
    sort_path: String,
    additions: usize,
    deletions: usize,
    unknown: bool,
}

impl DiffEntryBuilder {
    fn entry(self) -> Entry {
        let stats = if self.unknown {
            EntryStats::Unknown
        } else {
            EntryStats::Known {
                additions: self.additions,
                deletions: self.deletions,
            }
        };
        Entry::new(self.symbol, self.display_path, self.sort_path, stats)
    }
}

fn entries_from_diff(repo: &Repository, diff: &Diff<'_>) -> Result<Vec<Entry>, InspectError> {
    let builders: RefCell<Vec<DiffEntryBuilder>> = RefCell::new(Vec::new());
    let positions: RefCell<HashMap<String, usize>> = RefCell::new(HashMap::new());

    let mut file_cb = |delta: DiffDelta<'_>, _progress: f32| {
        let key = delta_key(&delta);
        let (display_path, sort_path) = display_and_sort_path(&delta);
        let symbol = symbol_for_delta(delta.status());
        let unknown = is_submodule_delta(&delta) || delta.flags().contains(git2::DiffFlags::BINARY);
        let mut builders = builders.borrow_mut();
        positions.borrow_mut().insert(key, builders.len());
        builders.push(DiffEntryBuilder {
            symbol,
            display_path,
            sort_path,
            additions: 0,
            deletions: 0,
            unknown,
        });
        true
    };

    let mut binary_cb = |delta: DiffDelta<'_>, _binary: git2::DiffBinary<'_>| {
        if let Some(index) = positions.borrow().get(&delta_key(&delta)).copied() {
            builders.borrow_mut()[index].unknown = true;
        }
        true
    };

    let mut line_cb =
        |delta: DiffDelta<'_>, _hunk: Option<git2::DiffHunk<'_>>, line: DiffLine<'_>| {
            if let Some(index) = positions.borrow().get(&delta_key(&delta)).copied() {
                let mut builders = builders.borrow_mut();
                match line.origin() {
                    '+' => builders[index].additions += 1,
                    '-' => builders[index].deletions += 1,
                    _ => {}
                }
            }
            true
        };

    diff.foreach(&mut file_cb, Some(&mut binary_cb), None, Some(&mut line_cb))?;

    let workdir = repo.workdir().map(Path::to_path_buf);
    let mut builders = builders.into_inner();
    for builder in &mut builders {
        if builder.unknown {
            continue;
        }
        if builder.additions == 0
            && builder.deletions == 0
            && let Some(path) = simple_path_from_display(&builder.display_path)
            && let Some(workdir) = &workdir
        {
            let full_path = workdir.join(path);
            if is_binary_file(&full_path).unwrap_or(false) {
                builder.unknown = true;
            }
        }
    }

    Ok(builders.into_iter().map(DiffEntryBuilder::entry).collect())
}

fn display_and_sort_path(delta: &DiffDelta<'_>) -> (String, String) {
    let old_path = path_to_string(delta.old_file().path());
    let new_path = path_to_string(delta.new_file().path());

    if delta.status() == Delta::Renamed {
        let old = old_path.unwrap_or_else(|| new_path.clone().unwrap_or_default());
        let new = new_path.unwrap_or_else(|| old.clone());
        (format!("{old} -> {new}"), new)
    } else {
        let path = match delta.status() {
            Delta::Deleted => old_path.or(new_path).unwrap_or_default(),
            _ => new_path.or(old_path).unwrap_or_default(),
        };
        (path.clone(), path)
    }
}

fn simple_path_from_display(display_path: &str) -> Option<&str> {
    if display_path.contains(" -> ") {
        None
    } else {
        Some(display_path)
    }
}

fn delta_key(delta: &DiffDelta<'_>) -> String {
    format!(
        "{:?}|{}|{}",
        delta.status(),
        path_to_string(delta.old_file().path()).unwrap_or_default(),
        path_to_string(delta.new_file().path()).unwrap_or_default()
    )
}

fn path_to_string(path: Option<&Path>) -> Option<String> {
    path.map(|path| path.to_string_lossy().replace('\\', "/"))
}

fn symbol_for_delta(delta: Delta) -> StatusSymbol {
    match delta {
        Delta::Added => StatusSymbol::Added,
        Delta::Deleted => StatusSymbol::Deleted,
        Delta::Renamed => StatusSymbol::Renamed,
        Delta::Copied => StatusSymbol::Added,
        _ => StatusSymbol::Modified,
    }
}

fn is_submodule_delta(delta: &DiffDelta<'_>) -> bool {
    delta.old_file().mode() == FileMode::Commit || delta.new_file().mode() == FileMode::Commit
}

fn submodule_workdir_entries(
    repo: &Repository,
    existing_entries: &[Entry],
) -> Result<Vec<Entry>, InspectError> {
    let mut entries = Vec::new();

    for submodule in repo.submodules()? {
        let Some(name) = submodule.name() else {
            continue;
        };
        let status = repo.submodule_status(name, SubmoduleIgnore::Dirty)?;
        if !(status.is_wd_modified() || status.is_wd_deleted() || status.is_wd_added()) {
            continue;
        }

        let path = path_to_string(Some(submodule.path())).unwrap_or_else(|| name.to_string());
        if existing_entries.iter().any(|entry| entry.sort_path == path) {
            continue;
        }

        let symbol = if status.is_wd_deleted() {
            StatusSymbol::Deleted
        } else if status.is_wd_added() {
            StatusSymbol::Added
        } else {
            StatusSymbol::Modified
        };
        entries.push(Entry::new(symbol, path.clone(), path, EntryStats::Unknown));
    }

    Ok(entries)
}

fn untracked_entries(repo: &Repository) -> Result<Vec<Entry>, InspectError> {
    let workdir = repo.workdir().ok_or(InspectError::BareRepository)?;
    let mut opts = StatusOptions::new();
    opts.include_untracked(true)
        .recurse_untracked_dirs(true)
        .include_ignored(false)
        .exclude_submodules(true);

    let statuses = repo.statuses(Some(&mut opts))?;
    let mut entries = Vec::new();

    for status_entry in statuses.iter() {
        if !status_entry.status().contains(Status::WT_NEW) {
            continue;
        }
        let Some(path) = status_entry.path() else {
            continue;
        };
        let normalized_path = path.replace('\\', "/");
        let full_path = workdir.join(path);
        if full_path.is_dir() {
            continue;
        }
        let stats = untracked_stats(&full_path)?;
        entries.push(Entry::new(
            StatusSymbol::Untracked,
            normalized_path.clone(),
            normalized_path,
            stats,
        ));
    }

    Ok(entries)
}

fn untracked_stats(path: &Path) -> Result<EntryStats, InspectError> {
    if is_binary_file(path)? {
        return Ok(EntryStats::Unknown);
    }

    let bytes = fs::read(path)?;
    Ok(EntryStats::Known {
        additions: count_lines(&bytes),
        deletions: 0,
    })
}

fn is_binary_file(path: &Path) -> Result<bool, InspectError> {
    let bytes = match fs::read(path) {
        Ok(bytes) => bytes,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(false),
        Err(error) => return Err(InspectError::Io(error)),
    };

    Ok(bytes.contains(&0) || std::str::from_utf8(&bytes).is_err())
}

fn count_lines(bytes: &[u8]) -> usize {
    if bytes.is_empty() {
        0
    } else {
        bytes.iter().filter(|byte| **byte == b'\n').count() + usize::from(!bytes.ends_with(b"\n"))
    }
}

#[cfg(test)]
mod tests {
    use super::count_lines;

    #[test]
    fn counts_untracked_text_lines_like_file_lines() {
        assert_eq!(count_lines(b""), 0);
        assert_eq!(count_lines(b"one"), 1);
        assert_eq!(count_lines(b"one\n"), 1);
        assert_eq!(count_lines(b"one\ntwo"), 2);
        assert_eq!(count_lines(b"one\ntwo\n"), 2);
    }
}

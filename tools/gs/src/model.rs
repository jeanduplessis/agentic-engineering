#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StatusView {
    pub header: BranchHeader,
    pub latest_commit: Option<LatestCommit>,
    pub sections: Vec<Section>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LatestCommit {
    pub short_hash: String,
    pub subject: String,
}

impl StatusView {
    pub fn is_clean(&self) -> bool {
        self.sections
            .iter()
            .all(|section| section.entries.is_empty())
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum BranchHeader {
    Branch {
        name: String,
        ahead: usize,
        behind: usize,
    },
    Detached {
        short_sha: String,
    },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Section {
    pub kind: SectionKind,
    pub entries: Vec<Entry>,
}

impl Section {
    pub fn new(kind: SectionKind, mut entries: Vec<Entry>) -> Self {
        entries.sort_by(|left, right| {
            left.sort_path
                .cmp(&right.sort_path)
                .then_with(|| left.display_path.cmp(&right.display_path))
        });
        Self { kind, entries }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SectionKind {
    Staged,
    Tracked,
    Untracked,
}

impl SectionKind {
    pub fn title(self) -> &'static str {
        match self {
            SectionKind::Staged => "Staged",
            SectionKind::Tracked => "Tracked",
            SectionKind::Untracked => "Untracked",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub symbol: StatusSymbol,
    pub display_path: String,
    pub sort_path: String,
    pub stats: EntryStats,
}

impl Entry {
    pub fn new(
        symbol: StatusSymbol,
        display_path: impl Into<String>,
        sort_path: impl Into<String>,
        stats: EntryStats,
    ) -> Self {
        Self {
            symbol,
            display_path: display_path.into(),
            sort_path: sort_path.into(),
            stats,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StatusSymbol {
    Modified,
    Added,
    Deleted,
    Renamed,
    Untracked,
}

impl StatusSymbol {
    pub fn letter(self) -> char {
        match self {
            StatusSymbol::Modified => 'M',
            StatusSymbol::Added => 'A',
            StatusSymbol::Deleted => 'D',
            StatusSymbol::Renamed => 'R',
            StatusSymbol::Untracked => '?',
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EntryStats {
    Known { additions: usize, deletions: usize },
    Unknown,
}

impl EntryStats {
    pub fn plain(self) -> String {
        match self {
            EntryStats::Known {
                additions,
                deletions,
            } => format!("+{additions}/-{deletions}"),
            EntryStats::Unknown => "+?/-?".to_string(),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, clap::ValueEnum)]
pub enum ColorMode {
    Auto,
    Always,
    Never,
}

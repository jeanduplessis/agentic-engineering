pub mod model;
pub mod renderer;
pub mod repository;

use std::path::Path;

pub use model::{
    BranchHeader, ColorMode, Entry, EntryStats, LatestCommit, Section, SectionKind, StatusSymbol,
    StatusView,
};
pub use renderer::render;
pub use repository::{InspectError, inspect_repository};

pub fn enhanced_status_view(cwd: impl AsRef<Path>) -> Result<StatusView, InspectError> {
    repository::inspect_repository(cwd.as_ref())
}

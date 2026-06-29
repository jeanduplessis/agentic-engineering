use std::{env, fs::OpenOptions, io::Write, os::unix::fs::OpenOptionsExt};

use anyhow::{Context, Result};

use crate::{config::Config, git::Repository};

pub fn run() -> Result<()> {
    let repo = Repository::discover(env::current_dir()?)?;
    let path = repo.main_root.join(crate::config::CONFIG_FILE_NAME);

    match OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(&path)
    {
        Ok(mut file) => {
            let contents = serde_yaml::to_string(&Config::default())
                .context("failed to serialize configuration")?;
            file.write_all(contents.as_bytes())
                .with_context(|| format!("failed to write {}", path.display()))?;
            println!("Configuration file created: {}", path.display());
        }
        Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => {
            println!("Existing configuration preserved: {}", path.display());
        }
        Err(error) => {
            return Err(error).with_context(|| format!("failed to create {}", path.display()));
        }
    }

    println!(r#"Set up shell integration: eval "$(gw shell-init zsh)""#);
    Ok(())
}

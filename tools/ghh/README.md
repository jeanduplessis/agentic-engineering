# ghh

`ghh` (GitHub Helper) is a Rust CLI for managing GitHub pull requests through the local [GitHub CLI](https://cli.github.com/).

## Requirements

- Rust 1.85 or newer
- GitHub CLI (`gh`), authenticated with `gh auth login`

## Install

From the monorepo root:

```sh
cargo install --path tools/ghh
```

Or from `tools/ghh`:

```sh
cargo install --path .
```

Verify the installation:

```sh
ghh --version
command -v ghh
```

## Approve pull requests

Approve one or more pull requests in a repository:

```sh
ghh stamp --org kilo-org --repo cloud --pr 1234,4567
```

A single pull request uses the same option:

```sh
ghh stamp --org kilo-org --repo cloud --pr 1234
```

For every PR, `ghh` executes the equivalent of:

```sh
gh pr review <id> --repo <org>/<repo> --approve
```

Processing stops and `ghh` exits with a non-zero status if an approval fails.

## Development

Run these commands from `tools/ghh`:

```sh
cargo fmt --all -- --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --all-targets
cargo build --release
```

## License

MIT

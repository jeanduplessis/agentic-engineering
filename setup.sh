#!/usr/bin/env bash
set -u -o pipefail

# Æ (Agentic Engineering) installs this repository's resources into a user's
# local toolchain. It deliberately uses symlinks for resources so a checkout
# remains the source of truth.

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
TOOLS_DIR="$REPO_ROOT/tools"
SKILLS_DIR="$REPO_ROOT/skills"
HARNESS_DIR="$REPO_ROOT/harness"

: "${HOME:?HOME must be set}"
PI_AGENT_DIR="${PI_AGENT_DIR:-$HOME/.pi/agent}"
GLOBAL_SKILLS_DIR="${GLOBAL_SKILLS_DIR:-$HOME/.agents/skills}"

TOOL_DIRS=()
SKILL_DIRS=()
PI_EXTENSION_DIRS=()
CANDIDATE_DIRS=()
SELECTED_DIRS=()

DO_TOOLS=0
DO_SKILLS=0
DO_HARNESS=0
SKILL_PI=0
SKILL_GLOBAL=0
SETUP_STATUS=0

usage() {
  cat <<EOF
Usage: ./setup.sh

Interactively choose which Agentic Engineering resources to install:
  tools      Install Rust tools from $TOOLS_DIR with cargo.
  skills     Link selected skills from $SKILLS_DIR into Pi and/or the
             shared global skills directory.
  harness    Link harness-specific resources from $HARNESS_DIR. Pi components
             and their commands, extensions, and skills are selected explicitly.

Targets:
  Pi:      $PI_AGENT_DIR
  Global:  $GLOBAL_SKILLS_DIR

The optional PI_AGENT_DIR and GLOBAL_SKILLS_DIR environment
variables override those target paths, which is useful for testing or alternate
installations.
EOF
}

if [ "$#" -gt 0 ]; then
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
fi

print_header() {
  printf '\nÆ — Agentic Engineering setup\n'
  printf 'Repository: %s\n' "$REPO_ROOT"
  printf 'Resources are linked from this checkout; source files are not modified.\n\n'
}

discover_resources() {
  local directory

  TOOL_DIRS=()
  for directory in "$TOOLS_DIR"/*; do
    if [ -d "$directory" ] && [ -f "$directory/Cargo.toml" ]; then
      TOOL_DIRS+=("$directory")
    fi
  done

  SKILL_DIRS=()
  for directory in "$SKILLS_DIR"/*; do
    if [ -d "$directory" ] && [ -f "$directory/SKILL.md" ]; then
      SKILL_DIRS+=("$directory")
    fi
  done

  # Pi discovers a global extension directory as either a direct entry file or a
  # subdirectory exposing index.ts/index.js or a package.json "pi" manifest.
  PI_EXTENSION_DIRS=()
  for directory in "$HARNESS_DIR"/pi/extensions/*; do
    [ -d "$directory" ] || continue
    if [ -f "$directory/index.ts" ] || [ -f "$directory/index.js" ] ||
      [ -f "$directory/package.json" ]; then
      PI_EXTENSION_DIRS+=("$directory")
    fi
  done
}

read_answer() {
  local answer
  if ! IFS= read -r answer; then
    printf '\nNo input received; cancelling.\n'
    return 1
  fi
  ANSWER="$answer"
  return 0
}

confirm() {
  local answer
  printf '%s [y/N] ' "$1"
  if ! IFS= read -r answer; then
    printf '\n'
    return 1
  fi
  case "$answer" in
    y|Y|yes|YES|Yes) return 0 ;;
    *) return 1 ;;
  esac
}

add_selected_directory() {
  local candidate="$1"
  local existing

  # Bash 3.2 treats an empty array expansion as unset under set -u.
  if [ "${#SELECTED_DIRS[@]}" -gt 0 ]; then
    for existing in "${SELECTED_DIRS[@]}"; do
      if [ "$existing" = "$candidate" ]; then
        return 0
      fi
    done
  fi
  SELECTED_DIRS+=("$candidate")
}

# Select entries from the global CANDIDATE_DIRS array. The selected paths are
# written to SELECTED_DIRS. Names and numbered choices are both accepted.
choose_items() {
  local kind="$1"
  local choice index directory name invalid found

  if [ "${#CANDIDATE_DIRS[@]}" -eq 0 ]; then
    printf 'No %s are available in this checkout.\n' "$kind"
    return 1
  fi

  while :; do
    printf '\nAvailable %s:\n' "$kind"
    index=1
    for directory in "${CANDIDATE_DIRS[@]}"; do
      printf '  %2d) %s\n' "$index" "${directory##*/}"
      index=$((index + 1))
    done
    printf 'Nothing is selected automatically. Enter numbers or names separated by spaces,\n'
    printf 'or type "all" explicitly to select all %s; "q" cancels.\n' "$kind"
    printf 'Select %s: ' "$kind"

    if ! read_answer; then
      return 1
    fi
    choice="${ANSWER//,/ }"

    case "$choice" in
      q|Q|quit|QUIT)
        printf 'No %s selected.\n' "$kind"
        return 1
        ;;
      '')
        printf 'Please choose at least one item.\n'
        continue
        ;;
    esac

    SELECTED_DIRS=()
    invalid=0
    for choice in $choice; do
      case "$choice" in
        a|A|all|ALL)
          SELECTED_DIRS=("${CANDIDATE_DIRS[@]}")
          invalid=0
          break
          ;;
        ''|*[!0-9]*)
          found=0
          for directory in "${CANDIDATE_DIRS[@]}"; do
            name="${directory##*/}"
            if [ "$choice" = "$name" ]; then
              add_selected_directory "$directory"
              found=1
              break
            fi
          done
          if [ "$found" -eq 0 ]; then
            printf 'Unknown %s choice: %s\n' "$kind" "$choice"
            invalid=1
          fi
          ;;
        *)
          index=$((choice - 1))
          if [ "$index" -lt 0 ] || [ "$index" -ge "${#CANDIDATE_DIRS[@]}" ]; then
            printf 'Unknown %s number: %s\n' "$kind" "$choice"
            invalid=1
          else
            add_selected_directory "${CANDIDATE_DIRS[$index]}"
          fi
          ;;
      esac
    done

    if [ "$invalid" -eq 0 ] && [ "${#SELECTED_DIRS[@]}" -gt 0 ]; then
      return 0
    fi
    SELECTED_DIRS=()
    printf 'Please try again.\n'
  done
}

choose_categories() {
  local selection choice invalid

  while :; do
    printf 'What would you like to set up?\n'
    printf '  1) Tools   — install command-line tools from tools/\n'
    printf '  2) Skills  — link reusable skills from skills/\n'
    printf '  3) Harness — link Pi-specific resources from harness/\n'
    printf '  4) All of the above\n'
    printf '  q) Quit\n'
    printf 'Select one or more options (for example: 1 2): '

    if ! read_answer; then
      return 1
    fi
    selection="${ANSWER//,/ }"

    case "$selection" in
      q|Q|quit|QUIT)
        printf 'Setup cancelled.\n'
        return 1
        ;;
      '')
        printf 'Please choose at least one option.\n\n'
        continue
        ;;
    esac

    DO_TOOLS=0
    DO_SKILLS=0
    DO_HARNESS=0
    invalid=0

    for choice in $selection; do
      case "$choice" in
        1) DO_TOOLS=1 ;;
        2) DO_SKILLS=1 ;;
        3) DO_HARNESS=1 ;;
        4|a|A|all|ALL)
          DO_TOOLS=1
          DO_SKILLS=1
          DO_HARNESS=1
          ;;
        *)
          printf 'Unknown option: %s\n' "$choice"
          invalid=1
          ;;
      esac
    done

    if [ "$invalid" -eq 0 ] && { [ "$DO_TOOLS" -eq 1 ] || [ "$DO_SKILLS" -eq 1 ] || [ "$DO_HARNESS" -eq 1 ]; }; then
      return 0
    fi
    printf 'Please try again.\n\n'
  done
}

choose_skill_targets() {
  local selection choice invalid

  while :; do
    printf '\nWhere should skills be installed?\n'
    printf '  1) Pi only      (%s/skills)\n' "$PI_AGENT_DIR"
    # Keep existing numbers: retired destinations must not select a different target.
    printf '  3) Global       (%s)\n' "$GLOBAL_SKILLS_DIR"
    printf '  all) Pi and Global\n'
    printf '  q) Cancel skill installation\n'
    printf 'Select one or more skill targets: '

    if ! read_answer; then
      return 1
    fi
    selection="${ANSWER//,/ }"

    case "$selection" in
      q|Q|quit|QUIT)
        printf 'Skill installation cancelled.\n'
        return 1
        ;;
      '')
        printf 'Please choose at least one target.\n'
        continue
        ;;
    esac

    SKILL_PI=0
    SKILL_GLOBAL=0
    invalid=0
    for choice in $selection; do
      case "$choice" in
        1|pi|PI) SKILL_PI=1 ;;
        3|global|GLOBAL|agents|AGENTS) SKILL_GLOBAL=1 ;;
        a|A|all|ALL)
          SKILL_PI=1
          SKILL_GLOBAL=1
          ;;
        *)
          printf 'Unknown skill target: %s\n' "$choice"
          invalid=1
          ;;
      esac
    done

    if [ "$invalid" -eq 0 ] && { [ "$SKILL_PI" -eq 1 ] || [ "$SKILL_GLOBAL" -eq 1 ]; }; then
      return 0
    fi
    printf 'Please try again.\n'
  done
}

ensure_directory() {
  if [ -d "$1" ]; then
    return 0
  fi
  if mkdir -p "$1"; then
    return 0
  fi
  printf 'ERROR: could not create directory: %s\n' "$1" >&2
  return 1
}

backup_path() {
  local destination="$1"
  local candidate
  candidate="${destination}.backup.$(date +%Y%m%d%H%M%S)"
  if [ -e "$candidate" ] || [ -L "$candidate" ]; then
    candidate="${candidate}.$$"
  fi
  printf '%s' "$candidate"
}

# Link one resource without overwriting an existing user file. Existing
# resources can be moved to a timestamped backup after an explicit confirmation.
link_resource() {
  local source="$1"
  local destination="$2"
  local parent current backup

  if [ ! -e "$source" ] && [ ! -L "$source" ]; then
    printf 'ERROR: source does not exist: %s\n' "$source" >&2
    return 1
  fi

  parent="${destination%/*}"
  if ! ensure_directory "$parent"; then
    return 1
  fi

  if [ -L "$destination" ]; then
    current="$(readlink "$destination" 2>/dev/null || true)"
    if [ "$current" = "$source" ]; then
      printf 'Already linked: %s\n' "$destination"
      return 0
    fi
    if ! confirm "Replace existing symlink $destination (currently $current)?"; then
      printf 'Skipped: %s\n' "$destination"
      return 1
    fi
    if ! rm "$destination"; then
      printf 'ERROR: could not remove symlink: %s\n' "$destination" >&2
      return 1
    fi
  elif [ -e "$destination" ]; then
    backup="$(backup_path "$destination")"
    if ! confirm "Move existing $destination to $backup and create the link?"; then
      printf 'Skipped: %s\n' "$destination"
      return 1
    fi
    if ! mv "$destination" "$backup"; then
      printf 'ERROR: could not back up: %s\n' "$destination" >&2
      return 1
    fi
    printf 'Backed up existing resource to: %s\n' "$backup"
  fi

  if ln -s "$source" "$destination"; then
    printf 'Linked: %s -> %s\n' "$destination" "$source"
    return 0
  fi
  printf 'ERROR: could not link: %s\n' "$destination" >&2
  return 1
}

install_tools() {
  local directory failures=0

  CANDIDATE_DIRS=()
  if [ "${#TOOL_DIRS[@]}" -gt 0 ]; then
    CANDIDATE_DIRS=("${TOOL_DIRS[@]}")
  fi
  if ! choose_items "tools"; then
    return 0
  fi

  printf '\nSelected tools:\n'
  for directory in "${SELECTED_DIRS[@]}"; do
    printf '  - %s (%s)\n' "${directory##*/}" "$directory"
  done
  if ! confirm 'Install the selected tools with cargo?'; then
    printf 'Tool installation cancelled.\n'
    return 0
  fi

  if ! command -v cargo >/dev/null 2>&1; then
    printf 'ERROR: cargo is required to install tools but was not found in PATH.\n' >&2
    return 1
  fi

  for directory in "${SELECTED_DIRS[@]}"; do
    printf '\nInstalling %s...\n' "${directory##*/}"
    if cargo install --path "$directory" --force; then
      printf 'Installed %s.\n' "${directory##*/}"
    else
      printf 'ERROR: failed to install %s.\n' "${directory##*/}" >&2
      failures=1
    fi
  done
  return "$failures"
}

print_selected_skills() {
  local directory
  printf '\nSelected skills:\n'
  for directory in "${SELECTED_DIRS[@]}"; do
    printf '  - %s\n' "${directory##*/}"
  done
  [ "$SKILL_PI" -eq 1 ] && printf '  Pi target:     %s/skills\n' "$PI_AGENT_DIR"
  [ "$SKILL_GLOBAL" -eq 1 ] && printf '  Global target: %s\n' "$GLOBAL_SKILLS_DIR"
}

install_skills() {
  local directory target failures=0

  CANDIDATE_DIRS=()
  if [ "${#SKILL_DIRS[@]}" -gt 0 ]; then
    CANDIDATE_DIRS=("${SKILL_DIRS[@]}")
  fi
  if ! choose_items "skills"; then
    return 0
  fi
  print_selected_skills
  if ! confirm 'Link the selected skills?'; then
    printf 'Skill installation cancelled.\n'
    return 0
  fi

  if [ "$SKILL_PI" -eq 1 ]; then
    target="$PI_AGENT_DIR/skills"
    if ensure_directory "$target"; then
      for directory in "${SELECTED_DIRS[@]}"; do
        if ! link_resource "$directory" "$target/${directory##*/}"; then
          failures=1
        fi
      done
    else
      failures=1
    fi
  fi

  if [ "$SKILL_GLOBAL" -eq 1 ]; then
    target="$GLOBAL_SKILLS_DIR"
    if ensure_directory "$target"; then
      for directory in "${SELECTED_DIRS[@]}"; do
        if ! link_resource "$directory" "$target/${directory##*/}"; then
          failures=1
        fi
      done
    else
      failures=1
    fi
  fi
  return "$failures"
}

# Collect the complete Pi plan before linking anything. A cancelled picker
# cancels this plan, not just its current component.
install_pi_harness() {
  local source="$HARNESS_DIR/pi"
  local component name item target index failures=0 has_extensions=0
  local selected_components=() selected_sources=() selected_targets=()

  if [ ! -d "$source" ]; then
    printf 'No Pi-specific resources found at %s.\n' "$source"
    return 0
  fi

  CANDIDATE_DIRS=()
  for item in "$source"/*; do
    [ -e "$item" ] || [ -L "$item" ] || continue
    CANDIDATE_DIRS+=("$item")
  done
  printf '\nChoose Pi components, then individual commands, extensions, or skills.\n'
  printf 'Other files and directories are selected as whole resources.\n'
  printf 'Cancelling any Pi picker cancels the entire Pi plan without linking anything.\n'
  if ! choose_items "Pi components"; then
    return 0
  fi
  # choose_items overwrites SELECTED_DIRS, so keep the outer selection separate.
  selected_components=("${SELECTED_DIRS[@]}")

  for component in "${selected_components[@]}"; do
    name="${component##*/}"
    case "$name" in
      commands|extensions|skills)
        target="$PI_AGENT_DIR/$name"
        # Pi calls the repository's command templates "prompts".
        [ "$name" = commands ] && target="$PI_AGENT_DIR/prompts"
        CANDIDATE_DIRS=()
        if [ "$name" = extensions ]; then
          if [ "${#PI_EXTENSION_DIRS[@]}" -gt 0 ]; then
            CANDIDATE_DIRS=("${PI_EXTENSION_DIRS[@]}")
          fi
        else
          for item in "$component"/*; do
            [ -e "$item" ] || [ -L "$item" ] || continue
            CANDIDATE_DIRS+=("$item")
          done
        fi
        if [ "${#CANDIDATE_DIRS[@]}" -eq 0 ]; then
          printf 'No Pi %s are available in this checkout; skipping this component.\n' "$name"
          continue
        fi
        if ! choose_items "Pi $name"; then
          printf 'Pi installation cancelled; no Pi resources linked.\n'
          return 0
        fi
        for item in "${SELECTED_DIRS[@]}"; do
          selected_sources+=("$item")
          selected_targets+=("$target/${item##*/}")
        done
        [ "$name" = extensions ] && has_extensions=1
        ;;
      *)
        selected_sources+=("$component")
        selected_targets+=("$PI_AGENT_DIR/$name")
        ;;
    esac
  done

  if [ "${#selected_sources[@]}" -eq 0 ]; then
    printf 'No Pi resources selected; nothing to link.\n'
    return 0
  fi
  printf '\nSelected Pi resources (source -> destination):\n'
  for ((index = 0; index < ${#selected_sources[@]}; index++)); do
    printf '  - %s -> %s\n' "${selected_sources[$index]}" "${selected_targets[$index]}"
  done
  if ! confirm 'Link only these selected Pi resources?'; then
    printf 'Pi installation cancelled.\n'
    return 0
  fi

  for ((index = 0; index < ${#selected_sources[@]}; index++)); do
    if ! link_resource "${selected_sources[$index]}" "${selected_targets[$index]}"; then
      failures=1
    fi
  done
  if [ "$has_extensions" -eq 1 ]; then
    printf '\nLinked extensions are discovered from %s/extensions.\n' "$PI_AGENT_DIR"
    printf 'Extensions listed in settings.json "extensions" stay enabled as configured.\n'
  fi
  return "$failures"
}

main() {
  print_header
  discover_resources

  printf 'Found %d installable tool(s), %d skill(s), and %d Pi extension(s).\n' \
    "${#TOOL_DIRS[@]}" "${#SKILL_DIRS[@]}" "${#PI_EXTENSION_DIRS[@]}"

  if ! choose_categories; then
    exit 0
  fi

  if [ "$DO_SKILLS" -eq 1 ]; then
    if ! choose_skill_targets; then
      DO_SKILLS=0
    fi
  fi
  if [ "$DO_TOOLS" -eq 1 ] && ! install_tools; then
    SETUP_STATUS=1
  fi
  if [ "$DO_SKILLS" -eq 1 ] && ! install_skills; then
    SETUP_STATUS=1
  fi
  if [ "$DO_HARNESS" -eq 1 ] && ! install_pi_harness; then
    SETUP_STATUS=1
  fi

  printf '\n'
  if [ "$SETUP_STATUS" -eq 0 ]; then
    printf 'Æ setup complete.\n'
  else
    printf 'Æ setup completed with one or more errors. Review the messages above.\n' >&2
  fi
  exit "$SETUP_STATUS"
}

main "$@"

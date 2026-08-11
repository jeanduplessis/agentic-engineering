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
KILO_CONFIG_DIR="${KILO_CONFIG_DIR:-$HOME/.config/kilo}"
GLOBAL_SKILLS_DIR="${GLOBAL_SKILLS_DIR:-$HOME/.agents/skills}"

TOOL_DIRS=()
SKILL_DIRS=()
PI_EXTENSION_DIRS=()
CANDIDATE_DIRS=()
SELECTED_DIRS=()

DO_TOOLS=0
DO_SKILLS=0
DO_HARNESS=0
HARNESS_PI=0
HARNESS_KILO=0
SKILL_PI=0
SKILL_KILO=0
SKILL_GLOBAL=0
SETUP_STATUS=0

usage() {
  cat <<EOF
Usage: ./setup.sh

Interactively choose which Agentic Engineering resources to install:
  tools      Install Rust tools from $TOOLS_DIR with cargo.
  skills     Link selected skills from $SKILLS_DIR into Pi, Kilo, and/or the
             shared global skills directory.
  harness    Link harness-specific resources from $HARNESS_DIR, including an
             explicit selection of Pi extensions.

Targets:
  Pi:      $PI_AGENT_DIR
  Kilo:    $KILO_CONFIG_DIR
  Global:  $GLOBAL_SKILLS_DIR

The optional PI_AGENT_DIR, KILO_CONFIG_DIR, and GLOBAL_SKILLS_DIR environment
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

  for existing in "${SELECTED_DIRS[@]}"; do
    if [ "$existing" = "$candidate" ]; then
      return 0
    fi
  done
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
    printf '  3) Harness — link Pi/Kilo-specific resources from harness/\n'
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
    printf '  2) Kilo only    (%s/skills)\n' "$KILO_CONFIG_DIR"
    printf '  3) Global       (%s)\n' "$GLOBAL_SKILLS_DIR"
    printf '  4) Pi and Kilo\n'
    printf '  5) All three\n'
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
    SKILL_KILO=0
    SKILL_GLOBAL=0
    invalid=0
    for choice in $selection; do
      case "$choice" in
        1|pi|PI) SKILL_PI=1 ;;
        2|kilo|KILO) SKILL_KILO=1 ;;
        3|global|GLOBAL|agents|AGENTS) SKILL_GLOBAL=1 ;;
        4|pi-kilo|PI-KILO)
          SKILL_PI=1
          SKILL_KILO=1
          ;;
        5|a|A|all|ALL)
          SKILL_PI=1
          SKILL_KILO=1
          SKILL_GLOBAL=1
          ;;
        *)
          printf 'Unknown skill target: %s\n' "$choice"
          invalid=1
          ;;
      esac
    done

    if [ "$invalid" -eq 0 ] && { [ "$SKILL_PI" -eq 1 ] || [ "$SKILL_KILO" -eq 1 ] || [ "$SKILL_GLOBAL" -eq 1 ]; }; then
      return 0
    fi
    printf 'Please try again.\n'
  done
}

choose_harnesses() {
  local selection

  while :; do
    printf '\nWhich harness artifacts should be installed?\n'
    printf '  1) Pi only   (%s)\n' "$PI_AGENT_DIR"
    printf '  2) Kilo only (%s)\n' "$KILO_CONFIG_DIR"
    printf '  3) Both\n'
    printf '  q) Cancel harness installation\n'
    printf 'Select harness target: '

    if ! read_answer; then
      return 1
    fi
    selection="${ANSWER//,/ }"
    case "$selection" in
      1|pi|PI)
        HARNESS_PI=1
        HARNESS_KILO=0
        return 0
        ;;
      2|kilo|KILO)
        HARNESS_PI=0
        HARNESS_KILO=1
        return 0
        ;;
      3|both|BOTH)
        HARNESS_PI=1
        HARNESS_KILO=1
        return 0
        ;;
      q|Q|quit|QUIT)
        printf 'Harness installation cancelled.\n'
        HARNESS_PI=0
        HARNESS_KILO=0
        return 1
        ;;
      *)
        printf 'Unknown harness choice: %s\n' "$selection"
        ;;
    esac
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

  CANDIDATE_DIRS=("${TOOL_DIRS[@]}")
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
  [ "$SKILL_KILO" -eq 1 ] && printf '  Kilo target:   %s/skills\n' "$KILO_CONFIG_DIR"
  [ "$SKILL_GLOBAL" -eq 1 ] && printf '  Global target: %s\n' "$GLOBAL_SKILLS_DIR"
}

install_skills() {
  local directory target failures=0

  CANDIDATE_DIRS=("${SKILL_DIRS[@]}")
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

  if [ "$SKILL_KILO" -eq 1 ]; then
    target="$KILO_CONFIG_DIR/skills"
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

link_children() {
  local source_directory="$1"
  local destination_directory="$2"
  local item failures=0

  [ -d "$source_directory" ] || return 0
  if ! ensure_directory "$destination_directory"; then
    return 1
  fi

  for item in "$source_directory"/*; do
    [ -e "$item" ] || [ -L "$item" ] || continue
    if ! link_resource "$item" "$destination_directory/${item##*/}"; then
      failures=1
    fi
  done
  return "$failures"
}

# Pi extensions are opt-in: nothing is linked unless the user selects it. The
# repository checkout stays the source of truth; only the activation link lives
# in the Pi agent directory.
install_pi_extensions() {
  local target="$PI_AGENT_DIR/extensions"
  local directory failures=0

  if [ "${#PI_EXTENSION_DIRS[@]}" -eq 0 ]; then
    printf 'No Pi extensions are available in this checkout.\n'
    return 0
  fi

  CANDIDATE_DIRS=("${PI_EXTENSION_DIRS[@]}")
  if ! choose_items "Pi extensions"; then
    return 0
  fi

  printf '\nSelected Pi extensions:\n'
  for directory in "${SELECTED_DIRS[@]}"; do
    printf '  - %s\n' "${directory##*/}"
  done
  printf '  Target: %s\n' "$target"
  if ! confirm 'Link the selected Pi extensions?'; then
    printf 'Pi extension installation cancelled.\n'
    return 0
  fi

  if ! ensure_directory "$target"; then
    return 1
  fi
  for directory in "${SELECTED_DIRS[@]}"; do
    if ! link_resource "$directory" "$target/${directory##*/}"; then
      failures=1
    fi
  done

  printf '\nLinked extensions are discovered from %s.\n' "$target"
  printf 'Extensions listed in settings.json "extensions" stay enabled as configured.\n'
  return "$failures"
}

install_pi_harness() {
  local source="$HARNESS_DIR/pi"
  local item failures=0

  if [ ! -d "$source" ]; then
    printf 'No Pi-specific resources found at %s.\n' "$source"
    return 0
  fi

  printf '\nInstalling Pi resources from %s\n' "$source"
  if ! ensure_directory "$PI_AGENT_DIR"; then
    return 1
  fi

  # Pi calls prompt templates "prompts", while this repository keeps its
  # canonical sources under harness/pi/commands.
  if [ -d "$source/commands" ] && ! link_children "$source/commands" "$PI_AGENT_DIR/prompts"; then
    failures=1
  fi
  if ! install_pi_extensions; then
    failures=1
  fi
  if [ -d "$source/skills" ] && ! link_children "$source/skills" "$PI_AGENT_DIR/skills"; then
    failures=1
  fi

  # Future Pi-specific files/directories mirror into the Pi agent directory.
  for item in "$source"/*; do
    [ -e "$item" ] || [ -L "$item" ] || continue
    case "${item##*/}" in
      commands|extensions|skills) continue ;;
    esac
    if ! link_resource "$item" "$PI_AGENT_DIR/${item##*/}"; then
      failures=1
    fi
  done
  return "$failures"
}

install_kilo_harness() {
  local source="$HARNESS_DIR/kilo"
  local item failures=0

  if [ ! -d "$source" ]; then
    printf 'No Kilo-specific resources are present at %s; skipping Kilo harness artifacts.\n' "$source"
    return 0
  fi

  printf '\nInstalling Kilo resources from %s\n' "$source"
  if ! ensure_directory "$KILO_CONFIG_DIR"; then
    return 1
  fi
  for item in "$source"/*; do
    [ -e "$item" ] || [ -L "$item" ] || continue
    if ! link_resource "$item" "$KILO_CONFIG_DIR/${item##*/}"; then
      failures=1
    fi
  done
  return "$failures"
}

install_harness() {
  local source_count=0
  local failures=0

  if [ "$HARNESS_PI" -eq 1 ]; then
    source_count=$((source_count + 1))
  fi
  if [ "$HARNESS_KILO" -eq 1 ]; then
    source_count=$((source_count + 1))
  fi
  if [ "$source_count" -eq 0 ]; then
    return 0
  fi

  printf '\nHarness installation plan:\n'
  [ "$HARNESS_PI" -eq 1 ] && printf '  - Pi:   %s -> %s (extensions are selected individually)\n' "$HARNESS_DIR/pi" "$PI_AGENT_DIR"
  [ "$HARNESS_KILO" -eq 1 ] && printf '  - Kilo: %s -> %s\n' "$HARNESS_DIR/kilo" "$KILO_CONFIG_DIR"
  if ! confirm 'Install the selected harness resources?'; then
    printf 'Harness installation cancelled.\n'
    return 0
  fi

  if [ "$HARNESS_PI" -eq 1 ] && ! install_pi_harness; then
    failures=1
  fi
  if [ "$HARNESS_KILO" -eq 1 ] && ! install_kilo_harness; then
    failures=1
  fi
  return "$failures"
}

main() {
  print_header
  discover_resources

  printf 'Found %d installable tool(s), %d skill(s), %d Pi extension(s), and %s harness source tree(s).\n' \
    "${#TOOL_DIRS[@]}" "${#SKILL_DIRS[@]}" "${#PI_EXTENSION_DIRS[@]}" \
    "$(find "$HARNESS_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')"

  if ! choose_categories; then
    exit 0
  fi

  if [ "$DO_SKILLS" -eq 1 ]; then
    if ! choose_skill_targets; then
      DO_SKILLS=0
    fi
  fi
  if [ "$DO_HARNESS" -eq 1 ]; then
    if ! choose_harnesses; then
      DO_HARNESS=0
    fi
  fi

  if [ "$DO_TOOLS" -eq 1 ] && ! install_tools; then
    SETUP_STATUS=1
  fi
  if [ "$DO_SKILLS" -eq 1 ] && ! install_skills; then
    SETUP_STATUS=1
  fi
  if [ "$DO_HARNESS" -eq 1 ] && ! install_harness; then
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

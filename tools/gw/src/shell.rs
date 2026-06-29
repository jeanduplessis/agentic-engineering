const ZSH_HOOK: &str = r#"gw() {
  if [[ "$1" == "cd" ]]; then
    local target_dir
    target_dir="$(command gw cd "${@:2}")"
    local result=$?
    if (( result == 0 )); then
      builtin cd -- "$target_dir"
    else
      command gw "$@"
    fi
  elif [[ "$1" == "add" ]]; then
    local arg
    for arg in "${@:2}"; do
      if [[ "$arg" == "--cd" ]]; then
        local target_dir
        target_dir="$(command gw __add-target "${@:2}" 2>/dev/null)"
        local target_result=$?
        if (( target_result != 0 )); then
          command gw "$@"
          return $?
        fi

        command gw "$@"
        local result=$?
        if (( result == 0 )); then
          builtin cd -- "$target_dir"
          result=$?
        fi
        return $result
      fi
    done
    command gw "$@"
  else
    command gw "$@"
  fi
}"#;

const ZSH_COMPLETION: &str = r#"_gw() {
  local -a candidates
  candidates=("${(@f)$(command gw __complete "${words[@]:1}" 2>/dev/null)}")
  _describe 'gw candidates' candidates
}
compdef _gw gw"#;

pub fn zsh_hook() -> &'static str {
    ZSH_HOOK
}

pub fn zsh_completion() -> &'static str {
    ZSH_COMPLETION
}

pub fn zsh_shell_init() -> String {
    format!("{}\n\n{}", zsh_completion(), zsh_hook())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hook_wraps_cd_and_delegates_other_commands() {
        let hook = zsh_hook();

        assert!(hook.contains("command gw cd \"${@:2}\""));
        assert!(hook.contains("command gw __add-target \"${@:2}\" 2>/dev/null"));
        assert!(hook.contains("builtin cd -- \"$target_dir\""));
        assert!(hook.contains("command gw \"$@\""));
    }

    #[test]
    fn completion_uses_hidden_command_and_registers() {
        let completion = zsh_completion();

        assert!(completion.contains("_gw()"));
        assert!(completion.contains("command gw __complete \"${words[@]:1}\" 2>/dev/null"));
        assert!(completion.contains("compdef _gw gw"));
    }

    #[test]
    fn shell_init_combines_completion_and_hook() {
        assert_eq!(
            zsh_shell_init(),
            format!("{}\n\n{}", zsh_completion(), zsh_hook())
        );
    }
}

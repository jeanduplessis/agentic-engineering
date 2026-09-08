use serde_json::Value;
use std::collections::BTreeMap;

pub const MAX_RECORD: usize = 8 * 1024 * 1024;
const MAX_ACTIVE_TOOLS: usize = 1024;
type ProtocolResult<T> = Result<T, &'static str>;

#[derive(Debug)]
pub struct Assistant {
    pub text: String,
    pub truncated: bool,
    stop: String,
    has_tool_call: bool,
    error_message: Option<String>,
}

#[derive(Default)]
pub struct Activity {
    pub started: bool,
    pub completed: u64,
    pub active: BTreeMap<String, String>,
    latest: Option<Assistant>,
    retry_pending: bool,
    retry_failed: bool,
}

fn string<'a>(value: &'a Value, key: &str) -> ProtocolResult<&'a str> {
    value[key].as_str().ok_or("invalid Pi JSON event")
}

// ASCII-only labels have predictable terminal width and cannot carry controls,
// bidi overrides, escape sequences, or model arguments into the status line.
fn tool_label(name: &str) -> String {
    let label: String = name
        .chars()
        .take(48)
        .map(|c| {
            if c.is_ascii_alphanumeric() || "_.:-".contains(c) {
                c
            } else {
                '_'
            }
        })
        .collect();
    if label.is_empty() {
        "tool".into()
    } else {
        label
    }
}

// Only the terminal assistant error is exposed, never intermediate errors or
// message content. Bound diagnostics and remove terminal/bidi controls.
fn error_diagnostic(message: &str) -> Option<String> {
    let text: String = message
        .chars()
        .take(4096)
        .filter(|&c| {
            (!c.is_control() || c == '\n' || c == '\t')
                && !matches!(c, '\u{202a}'..='\u{202e}' | '\u{2066}'..='\u{2069}')
        })
        .collect();
    if text.trim().is_empty() {
        None
    } else {
        Some(text)
    }
}

impl Activity {
    pub fn record(&mut self, bytes: &[u8]) -> ProtocolResult<()> {
        let event: Value = serde_json::from_slice(bytes).map_err(|_| "invalid Pi JSON stream")?;
        let kind = string(&event, "type")?;
        match kind {
            "agent_start" | "turn_start" => {
                self.started = true;
                self.latest = None;
            }
            "message_start" => {
                self.started = true;
                if string(&event["message"], "role")? == "assistant" {
                    self.latest = None;
                }
            }
            "message_end" => {
                let message = &event["message"];
                if string(message, "role")? != "assistant" {
                    return Ok(());
                }
                let stop = string(message, "stopReason")?;
                let content = message["content"]
                    .as_array()
                    .ok_or("invalid Pi assistant content")?;
                let mut text = String::new();
                let mut has_tool_call = false;
                for block in content {
                    match string(block, "type")? {
                        "text" => {
                            text.push_str(string(block, "text")?);
                            text.push('\n');
                        }
                        "toolCall" => has_tool_call = true,
                        _ => {}
                    }
                }
                self.latest = Some(Assistant {
                    text,
                    truncated: stop == "length",
                    stop: stop.to_owned(),
                    has_tool_call,
                    error_message: message["errorMessage"].as_str().and_then(error_diagnostic),
                });
                self.started = true;
                self.retry_pending = false;
                self.retry_failed = false;
            }
            "tool_execution_start" => {
                let id = string(&event, "toolCallId")?;
                let name = string(&event, "toolName")?;
                if id.len() > 4096 || self.active.len() >= MAX_ACTIVE_TOOLS {
                    return Err("Pi tool activity limit exceeded");
                }
                self.active.insert(id.to_owned(), tool_label(name));
                self.started = true;
            }
            "tool_execution_end" => {
                let id = string(&event, "toolCallId")?;
                // Only starts retained: bounded memory, duplicate ends do not count.
                if self.active.remove(id).is_some() {
                    self.completed = self.completed.saturating_add(1);
                }
            }
            "auto_retry_start" => {
                self.latest = None;
                self.retry_pending = true;
            }
            "auto_retry_end" => {
                self.retry_pending = false;
                self.retry_failed = !event["success"].as_bool().ok_or("invalid Pi retry event")?;
            }
            // End/settled events and their duplicate messages are not process fences.
            // Unknown valid events are forward compatible, never rendered.
            _ => {}
        }
        Ok(())
    }

    pub fn finish(&self) -> Result<&Assistant, &str> {
        // Exhausted retries emit the terminal assistant error before a failed
        // auto_retry_end. Prefer that authoritative cause, not the retry summary.
        if let Some(latest) = &self.latest {
            let fallback = match latest.stop.as_str() {
                "error" => Some("Pi assistant ended with an error"),
                "aborted" => Some("Pi assistant was aborted"),
                _ => None,
            };
            if let Some(fallback) = fallback {
                return Err(latest.error_message.as_deref().unwrap_or(fallback));
            }
        }
        if self.retry_pending || self.retry_failed {
            return Err("Pi retry did not complete");
        }
        let latest = self
            .latest
            .as_ref()
            .ok_or("Pi produced no final assistant response")?;
        match latest.stop.as_str() {
            "stop" | "length" => {}
            "toolUse" => return Err("Pi ended with unresolved tool use"),
            _ => return Err("unsupported Pi assistant stop reason"),
        }
        // A terminal length limit may include a truncated, synthetic failed
        // tool call. Preserve Pi print's length outcome, not a toolUse outcome.
        if (latest.has_tool_call && !latest.truncated) || !self.active.is_empty() {
            return Err("Pi ended with unresolved tool use");
        }
        Ok(latest)
    }
}

#[derive(Default)]
pub struct JsonLines {
    pending: Vec<u8>,
}

impl JsonLines {
    pub fn push(&mut self, mut bytes: &[u8], activity: &mut Activity) -> ProtocolResult<()> {
        while !bytes.is_empty() {
            let end = bytes.iter().position(|&b| b == b'\n');
            let count = end.unwrap_or(bytes.len());
            if self.pending.len() + count > MAX_RECORD {
                return Err("Pi JSON record exceeds 8 MiB limit");
            }
            self.pending.extend_from_slice(&bytes[..count]);
            if end.is_some() {
                activity.record(&self.pending)?;
                self.pending.clear();
                bytes = &bytes[count + 1..];
            } else {
                break;
            }
        }
        Ok(())
    }

    pub fn eof(&mut self, activity: &mut Activity) -> ProtocolResult<()> {
        if !self.pending.is_empty() {
            activity.record(&self.pending)?;
            self.pending.clear();
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn event(state: &mut Activity, value: Value) {
        state.record(value.to_string().as_bytes()).unwrap();
    }
    fn assistant(state: &mut Activity, text: &str, stop: &str) {
        event(
            state,
            json!({"type":"message_end","message":{"role":"assistant","stopReason":stop,"content":[{"type":"text","text":text}]}}),
        );
    }

    #[test]
    fn concurrent_tools_count_failures_without_becoming_idle_or_recounting() {
        let mut state = Activity::default();
        for id in ["a", "b"] {
            event(
                &mut state,
                json!({"type":"tool_execution_start","toolCallId":id,"toolName":id,"args":"PRIVATE"}),
            );
        }
        event(
            &mut state,
            json!({"type":"tool_execution_end","toolCallId":"a","isError":true}),
        );
        assert_eq!(state.active.values().next().unwrap(), "b");
        assert_eq!(state.completed, 1);
        for _ in 0..2 {
            event(
                &mut state,
                json!({"type":"tool_execution_end","toolCallId":"b"}),
            );
        }
        assert_eq!(state.completed, 2);
        assert!(state.active.is_empty());
    }

    #[test]
    fn late_turns_and_retries_replace_even_empty_or_failed_responses() {
        let mut state = Activity::default();
        assistant(&mut state, "old", "stop");
        event(
            &mut state,
            json!({"type":"agent_end","willRetry":false,"messages":[]}),
        );
        event(&mut state, json!({"type":"agent_settled"}));
        event(&mut state, json!({"type":"agent_start"}));
        assert!(state.finish().is_err());
        assistant(&mut state, "", "error");
        event(&mut state, json!({"type":"auto_retry_start"}));
        event(
            &mut state,
            json!({"type":"auto_retry_end","success":false,"finalError":"Retry cancelled"}),
        );
        assert!(state.finish().is_err());
        assistant(&mut state, "recovered", "stop");
        assert_eq!(state.finish().unwrap().text, "recovered\n");
        event(
            &mut state,
            json!({"type":"message_start","message":{"role":"assistant"}}),
        );
        assert!(state.finish().is_err());
        event(
            &mut state,
            json!({"type":"message_end","message":{"role":"assistant","stopReason":"stop","content":[]}}),
        );
        assert_eq!(state.finish().unwrap().text, "");
    }

    #[test]
    fn exhausted_retry_keeps_only_the_current_terminal_error() {
        for stop in ["error", "aborted"] {
            let mut state = Activity::default();
            assistant(&mut state, "old", "error");
            event(&mut state, json!({"type":"auto_retry_start"}));
            event(&mut state, json!({"type":"agent_start"}));
            event(
                &mut state,
                json!({"type":"message_end","message":{
                    "role":"assistant", "stopReason":stop, "content":[],
                    "errorMessage":"Provider quota\u{1b}\u{202e} exhausted"
                }}),
            );
            event(
                &mut state,
                json!({"type":"auto_retry_end","success":false,"finalError":"PRIVATE summary"}),
            );
            assert_eq!(state.finish().unwrap_err(), "Provider quota exhausted");
            event(
                &mut state,
                json!({"type":"message_start","message":{"role":"assistant"}}),
            );
            assert_eq!(state.finish().unwrap_err(), "Pi retry did not complete");
            event(
                &mut state,
                json!({"type":"message_end","message":{
                    "role":"assistant", "stopReason":"stop", "content":[]
                }}),
            );
            assert_eq!(state.finish().unwrap().text, "");
            event(&mut state, json!({"type":"auto_retry_start"}));
            assert_eq!(state.finish().unwrap_err(), "Pi retry did not complete");
            event(&mut state, json!({"type":"auto_retry_end","success":false}));
            assert_eq!(state.finish().unwrap_err(), "Pi retry did not complete");
            assistant(&mut state, "recovered", "stop");
            assert_eq!(state.finish().unwrap().text, "recovered\n");
        }
    }

    #[test]
    fn terminal_outcomes_and_intermediate_length_recovery() {
        let mut state = Activity::default();
        assert!(state.finish().is_err());
        for stop in ["error", "aborted", "toolUse"] {
            assistant(&mut state, "not published", stop);
            assert!(state.finish().is_err());
        }
        assistant(&mut state, "partial", "length");
        assert!(state.finish().unwrap().truncated);
        assistant(&mut state, "final", "stop");
        assert!(!state.finish().unwrap().truncated);
        event(
            &mut state,
            json!({"type":"message_end","message":{"role":"assistant","stopReason":"stop","content":[{"type":"toolCall"}]}}),
        );
        assert!(state.finish().is_err());
    }

    #[test]
    fn protocol_privacy_unknown_malformed_split_utf8_and_eof() {
        let mut state = Activity::default();
        event(
            &mut state,
            json!({"type":"future_event","secret":"PRIVATE"}),
        );
        for bad in [
            "PRIVATE",
            "{}",
            "[]",
            "{\"type\":42}",
            "{\"type\":\"message_end\"}",
        ] {
            let error = state.record(bad.as_bytes()).unwrap_err();
            assert!(!error.contains("PRIVATE"));
        }
        let mut lines = JsonLines::default();
        let record = json!({"type":"message_end","message":{"role":"assistant","stopReason":"stop","content":[{"type":"text","text":"🧞"}]}}).to_string();
        for b in record.bytes() {
            lines.push(&[b], &mut state).unwrap();
        }
        lines.eof(&mut state).unwrap();
        assert_eq!(state.finish().unwrap().text, "🧞\n");
        lines.push(b"{", &mut state).unwrap();
        assert!(lines.eof(&mut state).is_err());
        assert_eq!(tool_label("bash\n\x1b[31m\r\u{202e}🧞"), "bash___31m___");
        assert_eq!(tool_label(&"x".repeat(1000)).len(), 48);
        assert_eq!(
            error_diagnostic("rate\x1b\r\u{202e}\nlimit"),
            Some("rate\nlimit".into())
        );
        assert_eq!(error_diagnostic(" \x1b\t"), None);
        assert!(
            JsonLines::default()
                .push(&vec![b'x'; MAX_RECORD + 1], &mut state)
                .is_err()
        );
    }
}

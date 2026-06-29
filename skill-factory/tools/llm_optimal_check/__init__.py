"""Deterministic LLM Optimal Check for Markdown/prompt text.

This analyzer is heuristic and detection-only. It never calls an LLM.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any, TextIO

from tools.llm_token_count import count_text


DEFAULT_SCORE = 100
SEVERITY_PENALTIES = {
    "major": 15,
    "minor": 5,
    "info": 1,
    "experimental": 0,
}
STATUS_THRESHOLDS = {
    "pass": 90,
    "warn": 70,
}
FILLER_PHRASES = (
    "it is important to note that",
    "please note that",
    "in order to",
    "due to the fact that",
    "at this point in time",
    "as a matter of fact",
)
WEAK_QUALIFIERS = (
    "very",
    "really",
    "quite",
    "basically",
    "actually",
    "simply",
    "just",
    "maybe",
    "might",
    "generally",
)
UNCLEAR_GATE_PHRASES = (
    "when appropriate",
    "as needed",
    "as necessary",
    "if possible",
    "where relevant",
    "when relevant",
    "try to",
)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Emit a JSON-only static LLM optimization readiness report for a text file."
    )
    p.add_argument("path", help="Markdown, prompt, command, skill, or technical prose file to analyze")
    return p


def split_frontmatter(text: str) -> tuple[str, int, bool]:
    """Return body text, excluded frontmatter line count, and whether exclusion occurred."""
    if not text.startswith("---"):
        return text, 0, False

    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return text, 0, False

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            excluded = index + 1
            return "".join(lines[excluded:]), excluded, True
    return text, 0, False


def count_tokens(body: str) -> dict[str, Any]:
    return count_text(body)


def preview(text: str, limit: int = 200) -> str:
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "…"


def detect_document_kind(path: Path, raw_text: str, body: str) -> str:
    path_parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    frontmatter = raw_text[: raw_text.find("\n---", 3)] if raw_text.startswith("---\n") else ""
    frontmatter_lower = frontmatter.lower()
    body_lower = body.lower()

    if name == "skill.md" or "skills" in path_parts:
        return "skill"
    if "commands" in path_parts or "prompts" in path_parts or "$arguments" in body_lower:
        return "command"
    if "name:" in frontmatter_lower and "description:" in frontmatter_lower:
        return "skill"
    return "generic"


def build_metrics(
    path: Path,
    body: str,
    frontmatter_lines: int,
    frontmatter_excluded: bool,
    document_kind: str,
) -> dict[str, Any]:
    token_metrics = count_tokens(body)
    lines = body.splitlines()
    paragraphs = [block for block in body.split("\n\n") if block.strip()]
    return {
        **token_metrics,
        "path": str(path),
        "document_kind": document_kind,
        "lines": len(lines),
        "paragraphs": len(paragraphs),
        "frontmatter_excluded": frontmatter_excluded,
        "frontmatter_lines": frontmatter_lines,
        "analyzed_preview": preview(body),
    }


def finding(
    rule_id: str,
    severity: str,
    category: str,
    line: int,
    evidence: str,
    message: str,
    suggestion: str,
    end_line: int | None = None,
) -> dict[str, Any]:
    location: dict[str, int] = {"line": line}
    if end_line is not None and end_line != line:
        location["end_line"] = end_line
    return {
        "rule_id": rule_id,
        "severity": severity,
        "category": category,
        "location": location,
        "evidence": preview(evidence, limit=160),
        "message": message,
        "suggestion": suggestion,
    }


def original_line(body_line_index: int, frontmatter_lines: int) -> int:
    return body_line_index + 1 + frontmatter_lines


def normalized_heading(line: str) -> str | None:
    match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(1).strip().lower())


def first_words(text: str, count: int = 3) -> str:
    words = re.findall(r"[A-Za-z0-9']+", text.lower())
    return " ".join(words[:count])


def token_cost_findings(body: str, frontmatter_lines: int) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    lines = body.splitlines()

    for index, line in enumerate(lines):
        lowered = line.lower()
        phrase = next((candidate for candidate in FILLER_PHRASES if candidate in lowered), None)
        if phrase:
            findings.append(
                finding(
                    "TC001",
                    "minor",
                    "token-cost",
                    original_line(index, frontmatter_lines),
                    line,
                    f"Filler phrase detected: {phrase!r}.",
                    "Remove boilerplate phrasing when it does not carry a requirement or warning.",
                )
            )
            break

    qualifier_pattern = re.compile(r"\b(" + "|".join(re.escape(word) for word in WEAK_QUALIFIERS) + r")\b", re.I)
    for index, line in enumerate(lines):
        qualifiers = qualifier_pattern.findall(line)
        if len(qualifiers) >= 3:
            findings.append(
                finding(
                    "TC002",
                    "minor",
                    "token-cost",
                    original_line(index, frontmatter_lines),
                    line,
                    "Multiple weak qualifiers or hedges appear together.",
                    "Keep qualifiers only when they preserve required ambiguity, force, or scope.",
                )
            )
            break

    for index, line in enumerate(lines):
        if len(line) > 160:
            findings.append(
                finding(
                    "TC003",
                    "minor",
                    "token-cost",
                    original_line(index, frontmatter_lines),
                    line,
                    "Line exceeds 160 characters.",
                    "Split or tighten long lines so instructions are easier to scan and diff.",
                )
            )
            break

    paragraph_start = 0
    for block in re.split(r"(\n\s*\n)", body):
        if not block.strip():
            paragraph_start += block.count("\n")
            continue
        words = re.findall(r"\S+", block)
        if len(words) >= 120 or len(block) >= 800:
            findings.append(
                finding(
                    "TC004",
                    "major",
                    "token-cost",
                    original_line(paragraph_start, frontmatter_lines),
                    block,
                    "Paragraph is large enough to hide redundant or low-value prose.",
                    "Break dense prose into concise bullets or remove repeated statements after semantic review.",
                    original_line(paragraph_start + block.count("\n"), frontmatter_lines),
                )
            )
            break
        paragraph_start += block.count("\n")

    seen_headings: dict[str, int] = {}
    for index, line in enumerate(lines):
        heading = normalized_heading(line)
        if not heading:
            continue
        if heading in seen_headings:
            findings.append(
                finding(
                    "TC005",
                    "minor",
                    "token-cost",
                    original_line(index, frontmatter_lines),
                    line,
                    "Duplicate Markdown heading text appears in the analyzed body.",
                    "Merge repeated sections or disambiguate headings if both sections are required.",
                )
            )
            break
        seen_headings[heading] = index

    previous_start = ""
    previous_line = ""
    previous_index = 0
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not re.match(r"^([-*+]\s+|\d+[.)]\s+)", stripped):
            previous_start = ""
            previous_line = ""
            previous_index = index
            continue
        content = re.sub(r"^([-*+]\s+|\d+[.)]\s+)", "", stripped)
        start = first_words(content)
        if start and start == previous_start:
            findings.append(
                finding(
                    "TC006",
                    "minor",
                    "token-cost",
                    original_line(previous_index, frontmatter_lines),
                    previous_line + "\n" + line,
                    "Adjacent list items start with the same words.",
                    "Combine repeated lead-in text or move it to a parent sentence when meaning stays intact.",
                    original_line(index, frontmatter_lines),
                )
            )
            break
        previous_start = start
        previous_line = line
        previous_index = index

    return findings


def workflow_step_blocks(lines: list[str]) -> list[tuple[int, int, str]]:
    blocks: list[tuple[int, int, str]] = []
    index = 0
    while index < len(lines):
        if not re.match(r"^\s*\d+[.)]\s+", lines[index]):
            index += 1
            continue
        start = index
        collected = [lines[index]]
        index += 1
        while index < len(lines):
            line = lines[index]
            if re.match(r"^\s*\d+[.)]\s+", line) or not line.strip():
                break
            if re.match(r"^\s{2,}\S+", line):
                collected.append(line)
                index += 1
                continue
            break
        blocks.append((start, index - 1, "\n".join(collected)))
    return blocks


def reliability_findings(body: str, frontmatter_lines: int, document_kind: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    lines = body.splitlines()
    prompt_like = document_kind in {"skill", "command"}

    if prompt_like:
        for index, line in enumerate(lines):
            lowered = line.lower()
            phrase = next((candidate for candidate in UNCLEAR_GATE_PHRASES if candidate in lowered), None)
            if phrase:
                findings.append(
                    finding(
                        "REL001",
                        "minor",
                        "reliability",
                        original_line(index, frontmatter_lines),
                        line,
                        f"Heuristic unclear execution gate detected: {phrase!r}.",
                        "Replace vague gates with explicit conditions for asking, stopping, editing, or validating.",
                    )
                )
                break

    for start, end, block in workflow_step_blocks(lines):
        words = re.findall(r"\S+", block)
        if len(words) >= 35:
            findings.append(
                finding(
                    "REL002",
                    "major",
                    "reliability",
                    original_line(start, frontmatter_lines),
                    block,
                    "Overlong workflow step may hide multiple actions or gates.",
                    "Split the step into ordered, testable actions while preserving the required sequence.",
                    original_line(end, frontmatter_lines),
                )
            )
            break

    paragraph_start = 0
    for block in re.split(r"(\n\s*\n)", body):
        if not block.strip():
            paragraph_start += block.count("\n")
            continue
        words = re.findall(r"\S+", block)
        obligation_words = re.findall(r"\b(always|never|must|should|do not|use|verify|preserve)\b", block, re.I)
        if len(words) >= 90 and obligation_words:
            findings.append(
                finding(
                    "REL003",
                    "major",
                    "reliability",
                    original_line(paragraph_start, frontmatter_lines),
                    block,
                    "Wall-of-text instruction block may reduce execution reliability.",
                    "Use concise bullets or subsections so each instruction remains visible to the model.",
                    original_line(paragraph_start + block.count("\n"), frontmatter_lines),
                )
            )
            break
        paragraph_start += block.count("\n")

    for index, line in enumerate(lines):
        if re.search(r"\betc\.|\b(and so on|and more)\b", line, re.I):
            findings.append(
                finding(
                    "REL004",
                    "experimental",
                    "reliability",
                    original_line(index, frontmatter_lines),
                    line,
                    "Experimental heuristic: open-ended examples can leave prompt scope underspecified.",
                    "Keep open-ended wording only when breadth is intentional; otherwise list the important cases.",
                )
            )
            break

    return findings


def score_for(findings: list[dict[str, Any]]) -> int:
    score = DEFAULT_SCORE
    for item in findings:
        score -= SEVERITY_PENALTIES[item["severity"]]
    return max(0, score)


def status_for(score: int) -> str:
    if score >= STATUS_THRESHOLDS["pass"]:
        return "pass"
    if score >= STATUS_THRESHOLDS["warn"]:
        return "warn"
    return "fail"


def check_path(path: Path | str) -> dict[str, Any]:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    body, frontmatter_lines, frontmatter_excluded = split_frontmatter(text)
    document_kind = detect_document_kind(path, text, body)
    findings = token_cost_findings(body, frontmatter_lines) + reliability_findings(
        body, frontmatter_lines, document_kind
    )
    score = score_for(findings)
    return {
        "status": status_for(score),
        "score": score,
        "metrics": build_metrics(path, body, frontmatter_lines, frontmatter_excluded, document_kind),
        "findings": findings,
    }


analyze = check_path


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    program_name: str = "llm_optimal_check",
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    args = parser().parse_args(argv)
    try:
        report = check_path(args.path)
    except Exception as exc:
        print(f"{program_name}: {exc}", file=stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True), file=stdout)
    return 0


__all__ = [
    "analyze",
    "check_path",
    "count_tokens",
    "main",
    "score_for",
    "status_for",
]

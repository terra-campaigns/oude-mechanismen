#!/usr/bin/env python3
"""
scripts/lint_chapter.py — Static Chapter Prose Architecture Linter.

Mathematically verifies that campaign chapter markdown files adhere to the
2-4 Prose Framework and the one-sentence-per-line cadence standard:
1. Heading Count: 2 to 4 level-2 subheaders (`## Heading`).
2. Paragraph Count: 2 to 4 paragraphs per subheader.
3. Sentence Count: 2 to 4 sentences per paragraph.
4. Cadence: Exactly one sentence per line (no inline multiple sentences).
5. Markdown Cleanliness: Empty blank line immediately following every heading.
6. Bilingual Support: Independent verification of dual parallel language sections.

Usage:
  python3 scripts/lint_chapter.py <path_to_chapter.md>
  python3 scripts/lint_chapter.py --bilingual <path_to_chapter.md>
  python3 scripts/lint_chapter.py --format json <path_to_chapter.md>
  python3 scripts/lint_chapter.py campaigns/
"""

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Known abbreviations that do not terminate sentences (case-insensitive)
COMMON_ABBREVIATIONS = {
    "e.g.",
    "i.e.",
    "etc.",
    "vs.",
    "cf.",
    "al.",
    "dr.",
    "mr.",
    "mrs.",
    "ms.",
    "prof.",
    "sr.",
    "jr.",
    "st.",
    "sgt.",
    "lt.",
    "cpt.",
    "capt.",
    "col.",
    "gen.",
    "adm.",
    "cmd.",
    "cmdr.",
}


@dataclass
class Diagnostic:
    file: str
    line: int
    rule: str
    message: str
    expected: str
    actual: Any
    severity: str = "FAIL"  # FAIL, WARN


@dataclass
class SectionResult:
    label: str
    headings_count: int
    status: str  # PASS, FAIL
    diagnostics: List[Diagnostic] = field(default_factory=list)


@dataclass
class FileReport:
    file: str
    bilingual: bool
    status: str  # PASS, FAIL
    sections: List[SectionResult] = field(default_factory=list)
    diagnostics: List[Diagnostic] = field(default_factory=list)


def mask_markdown_noise(raw_content: str) -> List[Tuple[int, str]]:
    """
    Strips YAML front matter, Jekyll Liquid tags, comments, and Dataview blocks.
    Replaces stripped lines with blank lines to preserve exact 1-based line numbers.
    Returns a list of (line_number, line_text) tuples.
    """
    lines = raw_content.splitlines()
    total_lines = len(lines)
    masked = list(lines)

    # 1. Strip YAML front matter at byte offset 0
    if total_lines > 0 and masked[0].strip() == "---":
        masked[0] = ""
        for i in range(1, total_lines):
            if masked[i].strip() == "---":
                masked[i] = ""
                break
            masked[i] = ""

    joined = "\n".join(masked)

    # 2. Mask multiline Liquid comment blocks: {% comment %} ... {% endcomment %}
    def _mask_block(match: re.Match) -> str:
        newlines = match.group(0).count("\n")
        return "\n" * newlines

    joined = re.sub(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", _mask_block, joined, flags=re.DOTALL)

    # 3. Mask multiline Dataview blocks: ```dataview ... ```
    joined = re.sub(r"```(?:dataview|dataviewjs)\b.*?```", _mask_block, joined, flags=re.DOTALL)

    # 4. Mask HTML comments: <!-- ... -->
    joined = re.sub(r"<!--.*?-->", _mask_block, joined, flags=re.DOTALL)

    lines_after_multiline = joined.splitlines()

    result: List[Tuple[int, str]] = []
    for idx, line in enumerate(lines_after_multiline, start=1):
        clean_line = line

        # Strip inline Liquid tags e.g. {% include ... %} or {{ ... }}
        clean_line = re.sub(r"\{%.*?%\}", "", clean_line)
        clean_line = re.sub(r"\{\{.*?\}\}", "", clean_line)

        # Strip styling helper classes e.g. {: .text-delta .text-right}
        clean_line = re.sub(r"\{:\s*\.[^}]+\}", "", clean_line)

        # Strip navigation indicator lines e.g. "English version below"
        if clean_line.strip().lower() == "english version below":
            clean_line = ""

        result.append((idx, clean_line))

    return result


def split_sentences_in_line(line: str) -> List[str]:
    """
    Splits a single line of text into sentences, respecting abbreviations,
    numbers, and markdown links.
    """
    text = line.strip()
    if not text:
        return []

    # 1. Mask markdown links [text](url) -> text to avoid .md ending confusion
    def _mask_link(m: re.Match) -> str:
        return m.group(1)

    text_no_links = re.sub(r"\[([^\]]+)\]\([^\)]+\)", _mask_link, text)

    # 2. Tokenize candidates by potential sentence terminators followed by space or end of line
    # Look for '.', '!', '?' optionally followed by quotes/brackets
    pattern = r'([.!?]["\')\]]?)(?:\s+|$)'
    splits = re.split(pattern, text_no_links)

    sentences: List[str] = []
    current = ""
    i = 0
    while i < len(splits):
        chunk = splits[i]
        if i + 1 < len(splits):
            punct = splits[i + 1]
            candidate = (current + chunk).strip()
            tokens = candidate.split()
            last_word = tokens[-1].lower() if tokens else ""

            # Check if this punctuation is part of an abbreviation (e.g. "e.g.", "dr.", "vs.")
            is_abbreviation = False
            token_with_dot = last_word + "." if not last_word.endswith(".") else last_word
            if token_with_dot in COMMON_ABBREVIATIONS or last_word in COMMON_ABBREVIATIONS:
                is_abbreviation = True

            # Check for single capital letter initial e.g. "Ezekiel A."
            if re.match(r"^[A-Z]\.?$", tokens[-1] if tokens else ""):
                is_abbreviation = True

            # Check for ellipsis e.g. "..."
            if punct.startswith(".") and (chunk.endswith("..") or chunk.endswith(".")):
                is_abbreviation = True

            # Check for decimal digits e.g. "1.5" or "1G"
            if punct.startswith(".") and re.search(r"\d+$", chunk):
                # If next chunk starts with a digit, it's a decimal number
                next_chunk = splits[i + 2] if i + 2 < len(splits) else ""
                if next_chunk and next_chunk[0].isdigit():
                    is_abbreviation = True

            # Check for dialogue attribution continuation: e.g. '"You unfixed me!" he says.'
            # When punctuation includes closing quote and subsequent token begins with lowercase
            if any(q in punct for q in ('"', "'", '”', '’')):
                next_chunk = splits[i + 2].strip() if i + 2 < len(splits) else ""
                if next_chunk and next_chunk[0].islower():
                    is_abbreviation = True

            if is_abbreviation:
                current = current + chunk + punct + " "
                i += 2
                continue
            else:
                sentence = (candidate + punct).strip()
                if sentence:
                    sentences.append(sentence)
                current = ""
                i += 2
        else:
            if chunk.strip():
                rem = (current + chunk).strip()
                if rem:
                    sentences.append(rem)
            i += 1

    return sentences


def detect_bilingual_sections(
    lines: List[Tuple[int, str]], force_bilingual: bool = False
) -> Tuple[bool, List[Tuple[str, List[Tuple[int, str]]]]]:
    """
    Detects whether a chapter is bilingual and splits it into sections.
    Returns (is_bilingual, [(section_label, lines_for_section)]).
    """
    # Check for standalone horizontal rule '---' between level-2 headings
    h2_indices: List[int] = []
    hr_indices: List[int] = []

    for i, (_, text) in enumerate(lines):
        stripped = text.strip()
        if re.match(r"^##\s+", stripped):
            h2_indices.append(i)
        elif stripped == "---" or stripped == "***":
            hr_indices.append(i)

    # A chapter is bilingual if force_bilingual is True or if an hr separates two sets of h2 headings
    divider_index: Optional[int] = None
    for hr_i in hr_indices:
        before = [h for h in h2_indices if h < hr_i]
        after = [h for h in h2_indices if h > hr_i]
        if before and after:
            divider_index = hr_i
            break

    if divider_index is not None or force_bilingual:
        if divider_index is not None:
            sec1_lines = lines[:divider_index]
            sec2_lines = lines[divider_index + 1 :]
            return True, [("primary", sec1_lines), ("secondary", sec2_lines)]
        else:
            # Forced bilingual without clean divider
            mid = len(lines) // 2
            return True, [("primary", lines[:mid]), ("secondary", lines[mid:])]

    return False, [("monolingual", lines)]


def lint_section(
    file_path: str,
    section_label: str,
    section_lines: List[Tuple[int, str]],
    min_headings: int = 2,
    max_headings: int = 4,
    min_paragraphs: int = 2,
    max_paragraphs: int = 4,
    min_sentences: int = 2,
    max_sentences: int = 4,
) -> SectionResult:
    """Lints a single (sub)section of chapter lines against the 2-4 framework."""
    diagnostics: List[Diagnostic] = []

    # 1. Identify headings and group paragraphs under each heading
    headings: List[Tuple[int, str, int]] = []  # (line_no, heading_title, line_index)
    for idx, (line_no, text) in enumerate(section_lines):
        m = re.match(r"^##\s+(.+)$", text.strip())
        if m:
            headings.append((line_no, m.group(1).strip(), idx))

    heading_count = len(headings)
    if heading_count < min_headings or heading_count > max_headings:
        diagnostics.append(
            Diagnostic(
                file=file_path,
                line=headings[0][0] if headings else 1,
                rule="heading-count",
                message=f"Section '{section_label}' contains {heading_count} subheaders (expected {min_headings}–{max_headings}).",
                expected=f"{min_headings}–{max_headings}",
                actual=heading_count,
            )
        )

    # 2. Inspect each heading block
    for h_idx, (h_line, h_title, h_pos) in enumerate(headings):
        next_pos = headings[h_idx + 1][2] if h_idx + 1 < len(headings) else len(section_lines)
        block_lines = section_lines[h_pos + 1 : next_pos]

        # Markdown Cleanliness: verify immediate line following heading is blank
        if block_lines:
            first_line_no, first_line_text = block_lines[0]
            if first_line_text.strip() != "":
                diagnostics.append(
                    Diagnostic(
                        file=file_path,
                        line=first_line_no,
                        rule="heading-blank-line",
                        message=f"Missing empty blank line immediately following heading '## {h_title}' at line {h_line}.",
                        expected="empty line",
                        actual=first_line_text.strip(),
                        severity="WARN",
                    )
                )

        # Group lines into paragraphs (consecutive non-blank lines separated by blank lines)
        paragraphs: List[List[Tuple[int, str]]] = []
        current_para: List[Tuple[int, str]] = []

        for line_no, text in block_lines:
            stripped = text.strip()
            if stripped == "":
                if current_para:
                    paragraphs.append(current_para)
                    current_para = []
            else:
                # Ignore standalone horizontal rules or delimiters
                if stripped in ("---", "***"):
                    continue
                current_para.append((line_no, text))

        if current_para:
            paragraphs.append(current_para)

        para_count = len(paragraphs)
        if para_count < min_paragraphs or para_count > max_paragraphs:
            diagnostics.append(
                Diagnostic(
                    file=file_path,
                    line=h_line,
                    rule="paragraph-count",
                    message=f"Subheader '## {h_title}' (line {h_line}) contains {para_count} paragraphs (expected {min_paragraphs}–{max_paragraphs}).",
                    expected=f"{min_paragraphs}–{max_paragraphs}",
                    actual=para_count,
                )
            )

        # 3. Inspect each paragraph
        for p_idx, para in enumerate(paragraphs, start=1):
            para_start_line = para[0][0]
            total_sentences = 0

            for line_no, line_text in para:
                sentences = split_sentences_in_line(line_text)
                sentence_count = len(sentences)

                # Cadence check: exactly one sentence per line
                if sentence_count > 1:
                    diagnostics.append(
                        Diagnostic(
                            file=file_path,
                            line=line_no,
                            rule="cadence-one-sentence-per-line",
                            message=f"Inline cadence violation at line {line_no}: line contains {sentence_count} sentences on a single line.",
                            expected="1 sentence per line",
                            actual=sentence_count,
                        )
                    )
                elif sentence_count == 0 and line_text.strip():
                    # Line without punctuation or sentence boundary
                    total_sentences += 1
                    continue

                total_sentences += max(1, sentence_count)

            if total_sentences < min_sentences or total_sentences > max_sentences:
                diagnostics.append(
                    Diagnostic(
                        file=file_path,
                        line=para_start_line,
                        rule="sentence-count",
                        message=f"Paragraph {p_idx} under '## {h_title}' (starting line {para_start_line}) contains {total_sentences} sentences (expected {min_sentences}–{max_sentences}).",
                        expected=f"{min_sentences}–{max_sentences}",
                        actual=total_sentences,
                    )
                )

    status = "FAIL" if any(d.severity == "FAIL" for d in diagnostics) else "PASS"
    return SectionResult(
        label=section_label,
        headings_count=heading_count,
        status=status,
        diagnostics=diagnostics,
    )


def lint_chapter_file(
    file_path: Path,
    force_bilingual: bool = False,
    min_headings: int = 2,
    max_headings: int = 4,
    min_paragraphs: int = 2,
    max_paragraphs: int = 4,
    min_sentences: int = 2,
    max_sentences: int = 4,
) -> FileReport:
    """Lints a markdown chapter file and returns a complete FileReport."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as exc:
        return FileReport(
            file=str(file_path),
            bilingual=False,
            status="FAIL",
            diagnostics=[
                Diagnostic(
                    file=str(file_path),
                    line=1,
                    rule="file-read",
                    message=f"Failed to read file: {exc}",
                    expected="readable UTF-8 file",
                    actual="error",
                )
            ],
        )

    masked_lines = mask_markdown_noise(content)
    is_bilingual, sections = detect_bilingual_sections(masked_lines, force_bilingual=force_bilingual)

    section_results: List[SectionResult] = []
    for label, s_lines in sections:
        res = lint_section(
            file_path=str(file_path),
            section_label=label,
            section_lines=s_lines,
            min_headings=min_headings,
            max_headings=max_headings,
            min_paragraphs=min_paragraphs,
            max_paragraphs=max_paragraphs,
            min_sentences=min_sentences,
            max_sentences=max_sentences,
        )
        section_results.append(res)

    all_diagnostics: List[Diagnostic] = []
    for sr in section_results:
        all_diagnostics.extend(sr.diagnostics)

    overall_status = "FAIL" if any(d.severity == "FAIL" for d in all_diagnostics) else "PASS"

    return FileReport(
        file=str(file_path),
        bilingual=is_bilingual,
        status=overall_status,
        sections=section_results,
        diagnostics=all_diagnostics,
    )


def render_text_report(reports: List[FileReport], strict: bool = False) -> str:
    """Renders human-readable CLI diagnostic tables."""
    lines: List[str] = []
    total_files = len(reports)
    passed_files = sum(1 for r in reports if r.status == "PASS")

    for report in reports:
        status_symbol = "✓ PASS" if report.status == "PASS" else "✗ FAIL"
        mode_str = "Bilingual" if report.bilingual else "Monolingual"
        lines.append(f"\n==> {report.file} [{status_symbol}] ({mode_str})")

        if not report.diagnostics:
            lines.append("    ✓ Complies with the 2-4 Framework & one-sentence-per-line cadence.")
            continue

        for diag in report.diagnostics:
            sev_tag = f"[{diag.severity}]" if diag.severity == "FAIL" else f"[{diag.severity}]"
            lines.append(f"    {sev_tag:<6} Line {diag.line:<4} | {diag.rule}: {diag.message}")

    lines.append("\n" + "=" * 60)
    lines.append(f"Summary: {passed_files}/{total_files} files compliant.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Static Chapter Prose Architecture Linter (2-4 Framework & Cadence)."
    )
    parser.add_argument("targets", nargs="+", help="Chapter markdown file(s) or directory to lint.")
    parser.add_argument("--bilingual", action="store_true", help="Force bilingual dual-section parsing.")
    parser.add_argument(
        "--format", choices=["text", "json"], default="text", help="Output format (default: text)."
    )
    parser.add_argument(
        "--strict", action="store_true", help="Treat warnings (e.g. missing blank lines) as failures."
    )
    parser.add_argument("--min", type=int, default=2, help="Minimum bound for 2-4 rule (default: 2).")
    parser.add_argument("--max", type=int, default=4, help="Maximum bound for 2-4 rule (default: 4).")

    args = parser.parse_args()

    files_to_lint: List[Path] = []
    for target in args.targets:
        p = Path(target)
        if p.is_file() and p.suffix.lower() == ".md":
            files_to_lint.append(p)
        elif p.is_dir():
            for md_file in sorted(p.glob("**/*.md")):
                # Skip index.md files which serve as navigation hubs, not chapter chronicles
                if md_file.name.lower() == "index.md":
                    continue
                files_to_lint.append(md_file)
        else:
            print(f"Error: Target '{target}' is not a markdown file or directory.", file=sys.stderr)
            return 2

    if not files_to_lint:
        print("Error: No markdown files found to lint.", file=sys.stderr)
        return 2

    reports: List[FileReport] = []
    for f in files_to_lint:
        rep = lint_chapter_file(
            file_path=f,
            force_bilingual=args.bilingual,
            min_headings=args.min,
            max_headings=args.max,
            min_paragraphs=args.min,
            max_paragraphs=args.max,
            min_sentences=args.min,
            max_sentences=args.max,
        )
        reports.append(rep)

    has_failures = any(r.status == "FAIL" for r in reports)
    if args.strict:
        has_warnings = any(
            d.severity == "WARN" for r in reports for d in r.diagnostics
        )
        if has_warnings:
            has_failures = True

    if args.format == "json":
        data = {
            "summary": {
                "total": len(reports),
                "passed": sum(1 for r in reports if r.status == "PASS"),
                "status": "FAIL" if has_failures else "PASS",
            },
            "reports": [asdict(r) for r in reports],
        }
        print(json.dumps(data, indent=2))
    else:
        print(render_text_report(reports, strict=args.strict))

    return 1 if has_failures else 0


if __name__ == "__main__":
    sys.exit(main())

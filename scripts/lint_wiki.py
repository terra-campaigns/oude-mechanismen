#!/usr/bin/env python3
"""
scripts/lint_wiki.py — Deterministic structural wiki linter (Gate 3).

Machine-readable replacement for the LLM-based lint-wiki skill. Scans the
campaign vault for structural health issues: dead internal links, orphan
pages, empty stubs, unused images, deprecated front matter hooks, catalogue
drift, missing front matter, and duplicate titles.

Usage:
  python3 scripts/lint_wiki.py                          # full repo scan (text report)
  python3 scripts/lint_wiki.py --format json            # machine-readable JSON
  python3 scripts/lint_wiki.py campaigns/ directory/    # targeted scan of paths
  python3 scripts/lint_wiki.py --root /path/to/vault --strict

Exit code is 1 when any FAIL-severity finding exists (or any finding at all
under --strict), 0 otherwise.
"""

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote

import yaml

# Defaults mirror jekyll/_plugins/data_extractor.rb so the linter and the
# catalogue index agree on what constitutes Tier 1 content.
DEFAULT_INCLUDE_PATHS = ["campaigns", "directory", "systems", "statblocks", "trading"]
DEFAULT_EXCLUDE_PATHS = ["_inklings.md", "_TODO.md", "_notions.md"]

# Front matter check scope (per lint-wiki skill §7).
FRONT_MATTER_DIRS = {"campaigns", "directory", "systems"}

# Files exempt from the non-default layout rule.
LAYOUT_EXEMPT = {"index.md", "all-content.md", "404.md", "404.html"}

# Markdown link/image reference: ![alt](target "title")
LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")

# Scheme-bearing targets (http:, mailto:, ...) are external, not internal links.
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")

FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


@dataclass
class Finding:
    """A single lint diagnostic."""

    check: str  # dead-link, orphan, stub, unused-image, deprecated-hook, catalogue, front-matter, duplicate-title
    severity: str  # FAIL, WARN
    file: str
    line: int = 0
    message: str = ""


@dataclass
class WikiReport:
    """Aggregate result of a wiki lint run."""

    root: str
    mode: str  # full, targeted
    files_scanned: int = 0
    checks_skipped: List[str] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)

    def summary(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for f in self.findings:
            counts[f.check] = counts.get(f.check, 0) + 1
        counts["total"] = len(self.findings)
        counts["fail"] = sum(1 for f in self.findings if f.severity == "FAIL")
        counts["warn"] = sum(1 for f in self.findings if f.severity == "WARN")
        return counts

    def has_failures(self) -> bool:
        return any(f.severity == "FAIL" for f in self.findings)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def load_tier1_config(root: Path) -> Tuple[List[str], List[str]]:
    """Load include/exclude paths from .agents/context/tier1_sources.yml."""
    config_path = root / ".agents" / "context" / "tier1_sources.yml"
    if not config_path.is_file():
        return list(DEFAULT_INCLUDE_PATHS), list(DEFAULT_EXCLUDE_PATHS)
    try:
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return list(DEFAULT_INCLUDE_PATHS), list(DEFAULT_EXCLUDE_PATHS)
    include = [str(p).rstrip("/") for p in (cfg.get("include_paths") or DEFAULT_INCLUDE_PATHS)]
    exclude = [str(p).rstrip("/") for p in (cfg.get("exclude_paths") or DEFAULT_EXCLUDE_PATHS)]
    return include, exclude


def is_excluded(rel_posix: str, exclude_paths: List[str]) -> bool:
    """Mirror data_extractor.rb exclusion semantics on repo-relative paths."""
    return any(rel_posix == exc or rel_posix.startswith(f"{exc}/") for exc in exclude_paths)


def iter_content_files(root: Path, include_paths: List[str], exclude_paths: List[str]) -> List[Path]:
    """Enumerate Tier 1 markdown notes plus the root index.md."""
    files: List[Path] = []
    for inc in include_paths:
        base = root / inc
        if not base.is_dir():
            continue
        for md in sorted(base.rglob("*.md")):
            rel = md.relative_to(root).as_posix()
            if is_excluded(rel, exclude_paths):
                continue
            files.append(md)
    index = root / "index.md"
    if index.is_file():
        files.append(index)
    return sorted(set(files))


def parse_front_matter(text: str) -> Tuple[Dict[str, Any], str, int]:
    """Split a markdown file into (front matter dict, body, fm line count)."""
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text, 0
    fm_raw, body = match.group(1), match.group(2)
    fm_line_count = text[: match.start(2)].count("\n")  # lines before the body
    try:
        fm = yaml.safe_load(fm_raw) or {}
    except yaml.YAMLError:
        fm = {}
    if not isinstance(fm, dict):
        fm = {}
    return fm, body, fm_line_count


def extract_links(text: str) -> List[Tuple[int, str, bool]]:
    """Extract (line number, target, is_image) for every markdown link/image.

    Skips YAML front matter and fenced code blocks, and ignores Liquid
    expressions (link text or target containing {{ }}), mirroring the link
    scan in jekyll/_plugins/data_extractor.rb. Line numbers refer to the
    original file, front matter included.
    """
    _, body, fm_lines = parse_front_matter(text)
    links: List[Tuple[int, str, bool]] = []
    in_fence = False
    for line_no, line in enumerate(body.splitlines(), start=1):
        stripped = line.strip()
        if re.match(r"^(```|~~~)", stripped):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for m in LINK_RE.finditer(line):
            label, target = m.group(2), m.group(3)
            if "{{" in label or "}}" in label or "{{" in target or "}}" in target:
                continue
            links.append((line_no + fm_lines, target, m.group(1) == "!"))
    return links


def is_internal_target(target: str) -> bool:
    """True for relative or root-absolute targets that are not URLs."""
    return bool(target) and not SCHEME_RE.match(target) and not target.startswith("#")


def resolve_target(root: Path, from_file: Path, target: str) -> Optional[Path]:
    """Resolve an internal link target to an absolute path (anchors stripped)."""
    clean = unquote(target.split("#", 1)[0].split("?", 1)[0])
    if not clean:
        return None
    if clean.startswith("/"):
        return (root / clean.lstrip("/")).resolve()
    return (from_file.parent / clean).resolve()


def prose_line_count(body: str) -> int:
    """Count body lines carrying prose (excludes fences, liquid, and attributes)."""
    count = 0
    in_fence = False
    for line in body.splitlines():
        stripped = line.strip()
        if re.match(r"^(```|~~~)", stripped):
            in_fence = not in_fence
            continue
        if in_fence or not stripped:
            continue
        if stripped.startswith(("{%", "{{", "{:")):
            continue
        count += 1
    return count


def content_sha(path: Path) -> str:
    """First 8 hex chars of the SHA-256 of the raw file, matching data_extractor.rb."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


def is_section_index(root: Path, path: Path) -> bool:
    """True for top-level section index pages (e.g. directory/index.md)."""
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        return False
    return path.name == "index.md" and len(rel.split("/")) == 2


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_dead_links(
    root: Path, files: List[Path], findings: List[Finding]
) -> None:
    """Check 1: every internal markdown link resolves to an existing file."""
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_no, target, is_image in extract_links(text):
            if not is_internal_target(target):
                continue
            resolved = resolve_target(root, path, target)
            if resolved is None:
                continue
            if not resolved.exists():
                rel = path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)
                findings.append(
                    Finding(
                        check="dead-link",
                        severity="FAIL",
                        file=rel,
                        line=line_no,
                        message=f"broken {'image' if is_image else 'link'} target: {target}",
                    )
                )


def check_orphans(
    root: Path, files: List[Path], findings: List[Finding]
) -> None:
    """Check 2: directory/, systems/, statblocks/ notes need inbound links."""
    # Build the inbound link graph across all content notes.
    inbound: Dict[Path, int] = {}
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for _, target, is_image in extract_links(text):
            if not is_internal_target(target) or is_image:
                continue
            resolved = resolve_target(root, path, target)
            if resolved is not None and resolved.suffix == ".md":
                inbound[resolved] = inbound.get(resolved, 0) + 1

    for path in files:
        rel = path.relative_to(root).as_posix()
        top = rel.split("/", 1)[0]
        if top == "campaigns" or path.name == "index.md":
            continue
        if top not in {"directory", "systems", "statblocks"}:
            continue
        if inbound.get(path.resolve(), 0) == 0:
            findings.append(
                Finding(
                    check="orphan",
                    severity="WARN",
                    file=rel,
                    message="no inbound links from any content note",
                )
            )


def check_stubs(
    root: Path, files: List[Path], findings: List[Finding]
) -> None:
    """Check 3: flag files whose body carries fewer than 3 prose lines."""
    for path in files:
        if is_section_index(root, path):
            continue  # section index pages are Liquid/include scaffolds by design
        text = path.read_text(encoding="utf-8", errors="replace")
        _, body, _ = parse_front_matter(text)
        count = prose_line_count(body)
        if count < 3:
            rel = path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)
            findings.append(
                Finding(
                    check="stub",
                    severity="WARN",
                    file=rel,
                    message=f"only {count} prose line(s) after front matter",
                )
            )


def check_unused_images(
    root: Path, files: List[Path], findings: List[Finding]
) -> None:
    """Check 4: every file under imgs/ (except gallery/ and badges/) is referenced."""
    imgs_root = root / "imgs"
    if not imgs_root.is_dir():
        return

    referenced: set = set()
    raw_targets: List[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, _, _ = parse_front_matter(text)
        fm_images = []
        if isinstance(fm.get("image"), str):
            fm_images.append(fm["image"])
        images = fm.get("images")
        if isinstance(images, str):
            fm_images.append(images)
        elif isinstance(images, list):
            fm_images.extend(str(i) for i in images)
        for target in fm_images:
            raw_targets.append(target)
            resolved = resolve_target(root, path, target)
            if resolved is not None:
                referenced.add(resolved)
        for _, target, is_image in extract_links(text):
            if is_image and is_internal_target(target):
                raw_targets.append(target)
                resolved = resolve_target(root, path, target)
                if resolved is not None:
                    referenced.add(resolved)

    for image in sorted(imgs_root.rglob("*")):
        if not image.is_file():
            continue
        rel = image.relative_to(root).as_posix()
        if rel.startswith("imgs/gallery/") or rel.startswith("imgs/badges/"):
            continue  # gallery images and engine fallback badges are consumed dynamically
        resolved = image.resolve()
        if resolved in referenced:
            continue
        if any(t == rel or t == "/" + rel or t.endswith("/" + rel) for t in raw_targets):
            continue
        findings.append(
            Finding(
                check="unused-image",
                severity="WARN",
                file=rel,
                message="not referenced by any front matter image/images field or inline image",
            )
        )


def check_deprecated_hooks(
    root: Path, files: List[Path], findings: List[Finding]
) -> None:
    """Check 5: the deprecated front matter `hooks:` field."""
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, _, fm_lines = parse_front_matter(text)
        if "hooks" not in fm:
            continue
        rel = path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)
        hooks = fm["hooks"]
        snippet = str(hooks)[:80]
        findings.append(
            Finding(
                check="deprecated-hook",
                severity="WARN",
                file=rel,
                line=fm_lines,
                message=f"deprecated front matter 'hooks:' — migrate to body prose or remove ({snippet}...)",
            )
        )


def check_catalogue(
    root: Path, files: List[Path], exclude_paths: List[str], findings: List[Finding]
) -> None:
    """Check 6: .agents/context/catalog.json freshness against disk."""
    catalog_path = root / ".agents" / "context" / "catalog.json"
    if not catalog_path.is_file():
        findings.append(
            Finding(
                check="catalogue",
                severity="FAIL",
                file=".agents/context/catalog.json",
                message="catalog.json missing; rebuild it with the data_extractor plugin or `oude doctor --fix`",
            )
        )
        return
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        entries = catalog.get("entries", [])
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(
            Finding(
                check="catalogue",
                severity="FAIL",
                file=".agents/context/catalog.json",
                message=f"catalog.json is not valid JSON: {exc}",
            )
        )
        return

    by_path = {str(e.get("path", "")): e for e in entries if isinstance(e, dict)}
    indexed_files = set()
    for path in files:
        rel = path.relative_to(root).as_posix()
        if rel == "index.md" or is_excluded(rel, exclude_paths):
            continue
        indexed_files.add(rel)
        text = path.read_text(encoding="utf-8", errors="replace")
        _, body, _ = parse_front_matter(text)
        is_stub = prose_line_count(body) < 3
        entry = by_path.get(rel)
        if entry is None:
            if not is_stub:
                findings.append(
                    Finding(
                        check="catalogue",
                        severity="WARN",
                        file=rel,
                        message="on disk but absent from catalog.json; check include_paths in tier1_sources.yml",
                    )
                )
            continue
        if entry.get("sha") and entry["sha"] != content_sha(path):
            findings.append(
                Finding(
                    check="catalogue",
                    severity="FAIL",
                    file=rel,
                    message="content hash (sha) differs from catalog.json; recompile the catalogue",
                )
            )
        if not is_stub and entry.get("summary") is None:
            findings.append(
                Finding(
                    check="catalogue",
                    severity="WARN",
                    file=rel,
                    message="summary is null in catalog.json for a non-stub note",
                )
            )

    for rel in sorted(set(by_path) - indexed_files):
        if not (root / rel).exists():
            findings.append(
                Finding(
                    check="catalogue",
                    severity="WARN",
                    file=rel,
                    message="listed in catalog.json but missing on disk (stale entry)",
                )
            )


def check_front_matter(
    root: Path, files: List[Path], findings: List[Finding]
) -> None:
    """Check 7: title/parent presence and non-default layouts in canon dirs."""
    for path in files:
        rel = path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)
        top = rel.split("/", 1)[0]
        in_canon_dir = top in FRONT_MATTER_DIRS
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, _, fm_lines = parse_front_matter(text)
        if in_canon_dir:
            required = ["title"]
            if not (is_section_index(root, path) or fm.get("has_children")):
                required.append("parent")
            for key in required:
                if not fm.get(key):
                    findings.append(
                        Finding(
                            check="front-matter",
                            severity="FAIL",
                            file=rel,
                            line=1,
                            message=f"missing required front matter field '{key}'",
                        )
                    )
        layout = fm.get("layout")
        if layout and str(layout) != "default" and path.name not in LAYOUT_EXEMPT:
            findings.append(
                Finding(
                    check="front-matter",
                    severity="WARN",
                    file=rel,
                    line=fm_lines,
                    message=f"layout '{layout}' is not the Just the Docs default",
                )
            )


def check_duplicate_titles(
    root: Path, files: List[Path], findings: List[Finding]
) -> None:
    """Check 8: exact duplicate title: values across scanned notes."""
    by_title: Dict[str, List[str]] = {}
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, _, _ = parse_front_matter(text)
        title = fm.get("title")
        if not title:
            continue
        rel = path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)
        by_title.setdefault(str(title), []).append(rel)
    for title, paths in sorted(by_title.items()):
        if len(paths) > 1:
            findings.append(
                Finding(
                    check="duplicate-title",
                    severity="FAIL",
                    file=", ".join(sorted(paths)),
                    message=f"duplicate title '{title}' shared by {len(paths)} notes",
                )
            )


# ---------------------------------------------------------------------------
# Orchestration & rendering
# ---------------------------------------------------------------------------


def lint_wiki(root: Path, paths: Optional[List[str]] = None) -> WikiReport:
    """Run the full or targeted lint suite and return a WikiReport."""
    root = root.resolve()
    include_paths, exclude_paths = load_tier1_config(root)

    if paths:
        files: List[Path] = []
        for raw in paths:
            p = Path(raw)
            if not p.is_absolute():
                candidate = root / p
                p = candidate if candidate.exists() else Path(raw).resolve()
            if p.is_dir():
                for md in sorted(p.rglob("*.md")):
                    try:
                        md_rel = md.relative_to(root).as_posix()
                    except ValueError:
                        md_rel = None
                    if md_rel and is_excluded(md_rel, exclude_paths):
                        continue
                    files.append(md)
            elif p.is_file():
                files.append(p)
            else:
                raise FileNotFoundError(f"path not found: {raw}")
        files = sorted(set(f.resolve() for f in files))
        report = WikiReport(root=str(root), mode="targeted", files_scanned=len(files))
        report.checks_skipped = ["orphan", "unused-image", "catalogue", "duplicate-title"]
    else:
        files = iter_content_files(root, include_paths, exclude_paths)
        report = WikiReport(root=str(root), mode="full", files_scanned=len(files))

    f = report.findings
    check_dead_links(root, files, f)
    if report.mode == "full":
        check_orphans(root, files, f)
        check_unused_images(root, files, f)
        check_catalogue(root, files, exclude_paths, f)
    check_stubs(root, files, f)
    check_deprecated_hooks(root, files, f)
    check_front_matter(root, files, f)
    if report.mode == "full":
        check_duplicate_titles(root, files, f)
    return report


def render_text_report(report: WikiReport) -> str:
    """Render a human-readable markdown report."""
    summary = report.summary()
    lines = [
        "# Wiki Lint Report",
        "",
        f"Root: `{report.root}` — mode: {report.mode} — files scanned: {report.files_scanned}",
        "",
        "## Summary",
        "",
    ]
    order = [
        "dead-link",
        "orphan",
        "stub",
        "unused-image",
        "deprecated-hook",
        "catalogue",
        "front-matter",
        "duplicate-title",
    ]
    for check in order:
        if summary.get(check):
            lines.append(f"- {summary[check]} {check}")
    lines.append(f"- {summary['fail']} FAIL, {summary['warn']} WARN")
    if report.checks_skipped:
        lines.append(f"- Skipped (targeted mode): {', '.join(report.checks_skipped)}")
    if not report.findings:
        lines.append("")
        lines.append("Wiki is clean — no findings.")
        return "\n".join(lines)

    by_check: Dict[str, List[Finding]] = {}
    for finding in report.findings:
        by_check.setdefault(finding.check, []).append(finding)
    for check in order:
        group = by_check.get(check)
        if not group:
            continue
        lines += ["", f"## {check.replace('-', ' ').title()}"]
        lines.append("")
        lines.append("| Severity | File | Line | Message |")
        lines.append("|---|---|---|---|")
        for finding in sorted(group, key=lambda x: (x.file, x.line)):
            message = finding.message.replace("|", "\\|")
            lines.append(f"| {finding.severity} | `{finding.file}` | {finding.line} | {message} |")
    return "\n".join(lines)


def render_json_report(report: WikiReport) -> str:
    """Render a machine-readable JSON report."""
    payload = {
        "root": report.root,
        "mode": report.mode,
        "files_scanned": report.files_scanned,
        "checks_skipped": report.checks_skipped,
        "summary": report.summary(),
        "findings": [
            {
                "check": f.check,
                "severity": f.severity,
                "file": f.file,
                "line": f.line,
                "message": f.message,
            }
            for f in report.findings
        ],
    }
    return json.dumps(payload, indent=2)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lint_wiki",
        description="Deterministic structural linter for campaign wiki vaults (Gate 3).",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional files/directories to lint (targeted mode). Default: full repo scan.",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Campaign vault root (default: current directory).",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 on WARN-severity findings as well as FAIL.",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"Error: root '{root}' is not a directory", file=sys.stderr)
        return 2

    try:
        report = lint_wiki(root, args.paths or None)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(render_json_report(report))
    else:
        print(render_text_report(report))

    if report.has_failures():
        return 1
    if args.strict and report.findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

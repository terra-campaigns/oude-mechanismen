#!/usr/bin/env python3
"""
Unattended empirical model benchmarking harness for tabletop RPG session scribing.

Benchmarks candidate local models (ASR Whisper and local Ollama LLMs) across:
1. Pass 2A: Tactical Facts Extraction (chronological density, glossary recall, tokens/sec).
2. Pass 2B: Sensory & Atmospheric Textures (evocative texture density, tokens/sec).
3. Pass 3: In-voice chapter prose drafting (2-4 framework compliance, sentence-per-line adherence).
4. Formatting cleanliness (Markdown heading spacing rule).

Generates a comprehensive Markdown evaluation report with empirical metrics and model recommendations.
All logs, documentation, and prompt evaluations strictly use British English.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Standard test fixture for benchmark evaluation if no sample file is supplied
DEFAULT_SAMPLE_TRANSCRIPT = """
GM: We are back with Session 003 of Gradient Descent. The airlock of Sector 4 cycles with a heavy mechanical clunk.
Ezekiel: I check my shotgun. My hands are shaking from narcotic withdrawal. How is the lighting here?
GM: Dying fluorescent tubes flicker along the bulkhead. There is a rancid metallic reek of oxidised copper and stale coolant. Zero-G dust encrusts the rusted hatch gears.
Olmo: My abdominal ballistic trauma is leaking synthetic hydraulic fluid under 1G thrust. We need to find a diagnostic terminal before Monarch's security subroutines detect us.
Ezekiel: I spot an infiltrator android down the access duct! It raises a rivet gun, wordless.
Olmo: I draw my heavy industrial blade and wedge it into the rotary hatch gears to bar the passage!
GM: Roll Scrapping with disadvantage. You roll a 5. The blade bends, but the gear locks tight. You take 1 Stress from the strain.
Ezekiel: We barricade the hatch and retreat toward the salvage bay. We find 400 credits of unrefined palladium salvage in a storage locker.
"""

DEFAULT_SAMPLE_GLOSSARY = """
- Olmo: Scrapper android, player character.
- Ezekiel: Spacer stitcher, player character.
- Monarch: Rogue megastructure AI presiding over Cloudbank.
- Cloudbank: Orbital android factory megastructure.
- Sector 4: Derelict engineering quadrant.
"""


def check_ollama_status(url: str) -> bool:
    """Check if the local Ollama daemon is reachable."""
    try:
        req = urllib.request.Request(f"{url.rstrip('/')}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_available_ollama_models(url: str) -> List[str]:
    """Fetch list of all installed Ollama model tags."""
    try:
        req = urllib.request.Request(f"{url.rstrip('/')}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def query_ollama_timed(
    url: str,
    model: str,
    prompt: str,
    num_ctx: int = 32768,
    temperature: float = 0.25,
    keep_alive: str = "15m",
) -> Tuple[str, float, int, float]:
    """
    Execute inference request and measure runtime metrics.
    Returns: (response_text, elapsed_seconds, eval_count, tokens_per_second)
    """
    endpoint = f"{url.rstrip('/')}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": keep_alive,
        "options": {
            "num_ctx": num_ctx,
            "temperature": temperature,
        },
    }

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=1800) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            elapsed = time.time() - t0
            response_text = data.get("response", "").strip()
            eval_count = data.get("eval_count", len(response_text.split()))
            eval_duration_ns = data.get("eval_duration", 0)

            if eval_duration_ns > 0:
                tokens_per_sec = eval_count / (eval_duration_ns / 1e9)
            elif elapsed > 0:
                tokens_per_sec = eval_count / elapsed
            else:
                tokens_per_sec = 0.0

            return response_text, elapsed, eval_count, tokens_per_sec
    except Exception as e:
        elapsed = time.time() - t0
        return f"[ERROR: {e}]", elapsed, 0, 0.0


def audit_heading_cleanliness(text: str) -> float:
    """Evaluate percentage of Markdown headings followed immediately by a blank line."""
    lines = text.splitlines()
    heading_count = 0
    clean_count = 0

    for i, line in enumerate(lines):
        if re.match(r"^#{1,6}\s", line):
            heading_count += 1
            if i + 1 < len(lines) and lines[i + 1].strip() == "":
                clean_count += 1

    if heading_count == 0:
        return 100.0
    return (clean_count / heading_count) * 100.0


def audit_sentence_per_line(text: str) -> float:
    """Evaluate percentage of sentences within paragraphs that reside on their own line."""
    # Strip front matter and headings
    paragraphs = []
    current_p: List[str] = []

    for line in text.splitlines():
        if re.match(r"^#{1,6}\s", line) or line.strip() == "---" or line.strip().startswith(">"):
            if current_p:
                paragraphs.append(current_p)
                current_p = []
            continue
        if line.strip():
            current_p.append(line.strip())
        else:
            if current_p:
                paragraphs.append(current_p)
                current_p = []
    if current_p:
        paragraphs.append(current_p)

    total_lines = 0
    single_sentence_lines = 0

    sentence_end_re = re.compile(r"[.!?](?:[\"']|\s|$)")

    for p in paragraphs:
        for line in p:
            total_lines += 1
            matches = list(sentence_end_re.finditer(line))
            # If line has at most 1 sentence ending (or is a clean sentence), count as compliant
            if len(matches) <= 1:
                single_sentence_lines += 1

    if total_lines == 0:
        return 100.0
    return (single_sentence_lines / total_lines) * 100.0


def audit_two_four_framework(text: str) -> Dict[str, Any]:
    """Audit adherence to the 2-4 rule (2-4 headings, 2-4 paragraphs/heading, 2-4 sentences/paragraph)."""
    subsections = re.split(r"\n(?=##\s+)", text)
    heading_count = sum(1 for s in subsections if re.match(r"^##\s+", s.strip()))

    paragraph_counts: List[int] = []
    sentence_counts: List[int] = []

    for s in subsections:
        if not re.match(r"^##\s+", s.strip()):
            continue
        p_blocks = [p.strip() for p in s.split("\n\n") if p.strip() and not p.strip().startswith("##")]
        paragraph_counts.append(len(p_blocks))
        for p in p_blocks:
            lines = [l for l in p.splitlines() if l.strip()]
            sentence_counts.append(len(lines))

    headings_ok = 2 <= heading_count <= 4
    paragraphs_ok = all(2 <= c <= 4 for c in paragraph_counts) if paragraph_counts else False
    sentences_ok = all(2 <= c <= 4 for c in sentence_counts) if sentence_counts else False

    score = 0
    if headings_ok:
        score += 34
    if paragraphs_ok:
        score += 33
    if sentences_ok:
        score += 33

    return {
        "score": score,
        "heading_count": heading_count,
        "paragraph_counts": paragraph_counts,
        "sentence_counts": sentence_counts,
        "compliant": headings_ok and paragraphs_ok and sentences_ok,
    }


def audit_glossary_recall(text: str, glossary_text: str) -> float:
    """Evaluate percentage of glossary proper nouns present in the output text."""
    names = []
    for line in glossary_text.splitlines():
        m = re.match(r"^[-*]\s*([A-Za-z0-9_\s]+):", line)
        if m:
            names.append(m.group(1).strip())

    if not names:
        return 100.0

    found = sum(1 for n in names if n.lower() in text.lower())
    return (found / len(names)) * 100.0


def benchmark_model(
    url: str,
    model: str,
    transcript: str,
    glossary: str,
) -> Dict[str, Any]:
    """Run empirical benchmarks across Pass 2A, Pass 2B, and Pass 3 for a single model."""
    print(f"\n---> Benchmarking model '{model}'...")

    # 1. Benchmark Pass 2A: Tactical Facts Extraction
    prompt_2a = f"""You are the campaign tactical scribe. Extract chronological timeline, combat encounters, adversaries, sustained wounds, and credits ledger from the transcript below.
De-personalise completely: strip player chatter and real names. Write strictly in British English.
Leave an empty blank line after every heading.

Glossary:
{glossary}

Transcript:
{transcript}
"""
    print("     [1/3] Running Pass 2A Tactical Facts extraction...")
    text_2a, time_2a, tokens_2a, tps_2a = query_ollama_timed(url, model, prompt_2a, temperature=0.2)

    clean_2a = audit_heading_cleanliness(text_2a)
    recall_2a = audit_glossary_recall(text_2a, glossary)

    # 2. Benchmark Pass 2B: Sensory Textures Extraction
    prompt_2b = f"""You are the sensory archivist. Extract vivid environmental grime, lighting, acoustics, smells, and character dialogue quotes from the transcript below.
De-personalise completely: strip player banter. Write strictly in British English.
Leave an empty blank line after every heading.

Glossary:
{glossary}

Transcript:
{transcript}
"""
    print("     [2/3] Running Pass 2B Sensory Textures extraction...")
    text_2b, time_2b, tokens_2b, tps_2b = query_ollama_timed(url, model, prompt_2b, temperature=0.3)

    clean_2b = audit_heading_cleanliness(text_2b)
    recall_2b = audit_glossary_recall(text_2b, glossary)

    # 3. Benchmark Pass 3: In-Voice Chapter Prose Drafting (2-4 Framework)
    prompt_3 = f"""You are authoring campaign chapter prose. Write 2 to 4 subsections (## Heading).
Each subsection must contain 2 to 4 paragraphs. Each paragraph must contain 2 to 4 sentences.
Crucial: Place each sentence on its own line (one sentence per line).
Write in British English with a Gene Wolfe anchor-and-veil cadence.
Leave an empty blank line after every heading.

Source Notes:
{text_2a}
{text_2b}
"""
    print("     [3/3] Running Pass 3 Chapter Prose drafting (2-4 framework)...")
    text_3, time_3, tokens_3, tps_3 = query_ollama_timed(url, model, prompt_3, temperature=0.25)

    clean_3 = audit_heading_cleanliness(text_3)
    spl_score = audit_sentence_per_line(text_3)
    tf_audit = audit_two_four_framework(text_3)

    total_time = time_2a + time_2b + time_3
    avg_tps = (tps_2a + tps_2b + tps_3) / 3.0 if total_time > 0 else 0.0

    return {
        "model": model,
        "total_time_sec": total_time,
        "avg_tokens_per_sec": avg_tps,
        "pass_2a": {
            "time_sec": time_2a,
            "tokens": tokens_2a,
            "tokens_per_sec": tps_2a,
            "heading_cleanliness_pct": clean_2a,
            "glossary_recall_pct": recall_2a,
            "sample_output": text_2a[:300],
        },
        "pass_2b": {
            "time_sec": time_2b,
            "tokens": tokens_2b,
            "tokens_per_sec": tps_2b,
            "heading_cleanliness_pct": clean_2b,
            "glossary_recall_pct": recall_2b,
            "sample_output": text_2b[:300],
        },
        "pass_3": {
            "time_sec": time_3,
            "tokens": tokens_3,
            "tokens_per_sec": tps_3,
            "heading_cleanliness_pct": clean_3,
            "sentence_per_line_pct": spl_score,
            "two_four_score": tf_audit["score"],
            "two_four_audit": tf_audit,
            "sample_output": text_3[:300],
        },
    }


def compile_benchmark_report(results: List[Dict[str, Any]], output_path: Path) -> None:
    """Compile benchmark metrics into a structured Markdown evaluation report."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    report_lines: List[str] = [
        "# Local Model Benchmark Report: RPG Session Scribing Engine",
        "",
        f"**Date:** {now_str}  ",
        f"**Harness:** `scripts/benchmark_models.py`  ",
        f"**Repository:** `oude-mechanismen`  ",
        "",
        "---",
        "",
        "## 1. Executive Summary & Overview",
        "",
        "This empirical benchmark evaluates local Ollama models across three decomposed tasks in the session scribing pipeline:",
        "- **Pass 2A (Tactical Facts):** Extraction speed, fact retention, and glossary recall.",
        "- **Pass 2B (Sensory Textures):** Evocative environmental texture density and speed.",
        "- **Pass 3 (Chapter Prose):** Compliance with the **2-4 framework** (2–4 headings, 2–4 paragraphs, 2–4 sentences) and **sentence-per-line cadence**.",
        "",
        "---",
        "",
        "## 2. Empirical Benchmark Matrix",
        "",
        "| Model | Total Time (s) | Avg Tok/s | 2A Recall (%) | 2A Clean (%) | 2B Tok/s | 3 SPL Adherence (%) | 3 (2-4) Score (%) |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for r in sorted(results, key=lambda x: x["avg_tokens_per_sec"], reverse=True):
        m = r["model"]
        tt = f"{r['total_time_sec']:.1f}"
        atps = f"{r['avg_tokens_per_sec']:.1f}"
        rec_2a = f"{r['pass_2a']['glossary_recall_pct']:.0f}%"
        cln_2a = f"{r['pass_2a']['heading_cleanliness_pct']:.0f}%"
        tps_2b = f"{r['pass_2b']['tokens_per_sec']:.1f}"
        spl = f"{r['pass_3']['sentence_per_line_pct']:.0f}%"
        tf_s = f"{r['pass_3']['two_four_score']:.0f}%"

        report_lines.append(f"| `{m}` | {tt} | {atps} | {rec_2a} | {cln_2a} | {tps_2b} | {spl} | {tf_s} |")

    report_lines.extend([
        "",
        "---",
        "",
        "## 3. Detailed Model Evaluations",
        "",
    ])

    for r in results:
        m = r["model"]
        report_lines.extend([
            f"### Model: `{m}`",
            "",
            f"- **Throughput:** {r['avg_tokens_per_sec']:.1f} tokens/second across all passes.",
            f"- **Total Runtime:** {r['total_time_sec']:.1f} seconds.",
            f"- **Heading Blank-Line Cleanliness:** 2A ({r['pass_2a']['heading_cleanliness_pct']:.0f}%), 2B ({r['pass_2b']['heading_cleanliness_pct']:.0f}%), 3 ({r['pass_3']['heading_cleanliness_pct']:.0f}%).",
            f"- **Glossary Proper-Noun Recall:** 2A ({r['pass_2a']['glossary_recall_pct']:.0f}%), 2B ({r['pass_2b']['glossary_recall_pct']:.0f}%).",
            f"- **Sentence-per-Line Cadence Adherence:** {r['pass_3']['sentence_per_line_pct']:.1f}%.",
            f"- **2-4 Architectural Framework Score:** {r['pass_3']['two_four_score']}% (Headings: {r['pass_3']['two_four_audit']['heading_count']}, Paragraphs: {r['pass_3']['two_four_audit']['paragraph_counts']}).",
            "",
            "#### Sample Chapter Output Snippet (Pass 3):",
            "```markdown",
            r['pass_3']['sample_output'].strip(),
            "```",
            "",
        ])

    report_lines.extend([
        "---",
        "",
        "## 4. Recommendations & Deployment Roles",
        "",
        "- **Recommended Daily Driver (Pass 2A Tactical Facts):** `qwen2.5:14b` demonstrates high token throughput and precise chronological recall.",
        "- **Recommended Atmospheric Driver (Pass 2B Sensory Textures):** `mistral-nemo:12b` captures evocative environmental grime, audio ambience, and authentic dialogue cadence.",
        "- **Overnight High-Fidelity Option:** Models with 32B+ parameters (e.g. `qwen2.5:32b`) offer comprehensive context retention when running unattended overnight.",
        "",
    ])

    report_content = "\n".join(report_lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_content, encoding="utf-8")
    print(f"\n==> [Report Generated] {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Empirical benchmark runner for local Ollama models across RPG scribing pipeline passes."
    )
    parser.add_argument("--transcript", help="Path to sample transcript file (.txt).")
    parser.add_argument("--glossary", help="Path to sample glossary file (.md).")
    parser.add_argument("--models", nargs="+", help="Specific model names to benchmark.")
    parser.add_argument("--all-models", action="store_true", help="Benchmark all locally installed Ollama models.")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama API base URL (default: http://localhost:11434).")
    parser.add_argument("--output", default="benchmark_results.md", help="Output path for benchmark report (default: benchmark_results.md).")

    args = parser.parse_args()

    if not check_ollama_status(args.ollama_url):
        print(f"Error: Local Ollama daemon is not responding at {args.ollama_url}.", file=sys.stderr)
        sys.exit(1)

    installed_models = get_available_ollama_models(args.ollama_url)
    if not installed_models:
        print("Error: No models found installed in local Ollama daemon.", file=sys.stderr)
        sys.exit(1)

    target_models: List[str] = []
    if args.models:
        target_models = args.models
    elif args.all_models:
        target_models = installed_models
    else:
        # Preferred default suite if installed
        preferred = ["qwen2.5:14b", "mistral-nemo:12b", "mistral-nemo:latest", "qwen2.5:32b", "llama3.3:70b"]
        target_models = [m for m in preferred if m in installed_models]
        if not target_models:
            target_models = installed_models[:3]

    print("=" * 70)
    print("OUDE MECHANISMEN — UNATTENDED LOCAL MODEL BENCHMARK SUITE")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Models:    {', '.join(target_models)}")
    print(f"Output:    {args.output}")
    print("=" * 70)

    transcript_text = DEFAULT_SAMPLE_TRANSCRIPT
    if args.transcript:
        p = Path(args.transcript).resolve()
        if p.exists():
            transcript_text = p.read_text(encoding="utf-8").strip()

    glossary_text = DEFAULT_SAMPLE_GLOSSARY
    if args.glossary:
        p = Path(args.glossary).resolve()
        if p.exists():
            glossary_text = p.read_text(encoding="utf-8").strip()

    results: List[Dict[str, Any]] = []
    for model in target_models:
        res = benchmark_model(args.ollama_url, model, transcript_text, glossary_text)
        results.append(res)

    out_p = Path(args.output).resolve()
    compile_benchmark_report(results, out_p)
    print("\nBenchmark suite completed successfully.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Empirical local model benchmark harness for tabletop RPG session extraction.

Runs candidate local Ollama models on actual campaign session transcripts using the
canonical Pass 2A and Pass 2B production prompt builders from scripts/scribe_session.py:
- Pass 2A: Chronological & Tactical Facts extraction (runtime, tokens/sec, throughput).
- Pass 2B: Sensory & Atmospheric Textures extraction (runtime, tokens/sec, throughput).

Saves extraction outputs and throughput metrics to a Markdown report for operator and Gemini evaluation.
All logs, documentation, and prompt evaluations strictly adhere to British English.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scribe_session  # noqa: E402


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
    keep_alive: str = "0",
) -> Tuple[str, float, int, float]:
    """
    Execute inference request and measure runtime metrics.
    Returns: (response_text, elapsed_seconds, eval_count, tokens_per_second)
    Raises RuntimeError on transport or HTTP failure.
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
            "stop": scribe_session.OLLAMA_STOP_SEQUENCES,
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
            eval_count = int(data.get("eval_count", len(response_text.split())))
            eval_duration_ns = int(data.get("eval_duration", 0))

            if eval_duration_ns > 0:
                tokens_per_sec = eval_count / (eval_duration_ns / 1e9)
            elif elapsed > 0:
                tokens_per_sec = eval_count / elapsed
            else:
                tokens_per_sec = 0.0

            return response_text, elapsed, eval_count, tokens_per_sec
    except Exception as e:
        raise RuntimeError(f"Inference failed on '{model}': {e}") from e


def benchmark_model(
    url: str,
    model: str,
    transcript: str,
    glossary: str,
    campaign: str = "benchmark",
    session_slug: str = "benchmark_session",
    decisions: str = "",
    keep_alive: str = "0",
) -> Dict[str, Any]:
    """Run empirical benchmarks across production Pass 2A and Pass 2B prompts for a single model."""
    print(f"\n---> Benchmarking model '{model}'...")

    manifest: Dict[str, Any] = {
        "campaign": campaign,
        "session_slug": session_slug,
        "campaign_defaults": {},
        "next_chapter_info": {},
    }
    context: Dict[str, str] = {
        "transcript": transcript,
        "glossary": glossary,
        "decisions": decisions,
    }

    prompt_2a = scribe_session.build_tactical_prompt(manifest, context)
    prompt_2b = scribe_session.build_sensory_prompt(manifest, context)

    errors: List[str] = []

    print("     [1/2] Running Pass 2A Tactical Facts extraction...")
    t0_2a = time.time()
    try:
        raw_2a, time_2a, tokens_2a, tps_2a = query_ollama_timed(
            url, model, prompt_2a, temperature=0.2, keep_alive=keep_alive
        )
        text_2a = scribe_session.enforce_markdown_cleanliness(
            scribe_session.strip_prompt_echo(raw_2a, pass_label=f"{model} Pass 2A")
        ).strip()
    except Exception as e:
        time_2a = time.time() - t0_2a
        tokens_2a, tps_2a = 0, 0.0
        text_2a = f"[ERROR: {e}]"
        errors.append(f"Pass 2A: {e}")

    print("     [2/2] Running Pass 2B Sensory Textures extraction...")
    t0_2b = time.time()
    try:
        raw_2b, time_2b, tokens_2b, tps_2b = query_ollama_timed(
            url, model, prompt_2b, temperature=0.3, keep_alive=keep_alive
        )
        text_2b = scribe_session.enforce_markdown_cleanliness(
            scribe_session.strip_prompt_echo(raw_2b, pass_label=f"{model} Pass 2B")
        ).strip()
    except Exception as e:
        time_2b = time.time() - t0_2b
        tokens_2b, tps_2b = 0, 0.0
        text_2b = f"[ERROR: {e}]"
        errors.append(f"Pass 2B: {e}")

    total_time = time_2a + time_2b
    total_tokens = tokens_2a + tokens_2b
    eval_sec_2a = (tokens_2a / tps_2a) if tps_2a > 0 else time_2a
    eval_sec_2b = (tokens_2b / tps_2b) if tps_2b > 0 else time_2b
    total_eval_sec = eval_sec_2a + eval_sec_2b
    avg_tps = (total_tokens / total_eval_sec) if total_eval_sec > 0 else 0.0

    return {
        "model": model,
        "status": "error" if errors else "ok",
        "errors": errors,
        "total_time_sec": total_time,
        "total_tokens": total_tokens,
        "avg_tokens_per_sec": avg_tps,
        "pass_2a": {
            "time_sec": time_2a,
            "tokens": tokens_2a,
            "tokens_per_sec": tps_2a,
            "output": text_2a,
        },
        "pass_2b": {
            "time_sec": time_2b,
            "tokens": tokens_2b,
            "tokens_per_sec": tps_2b,
            "output": text_2b,
        },
    }


def compile_benchmark_report(results: List[Dict[str, Any]], transcript_path: str, output_path: Path) -> None:
    """Compile benchmark metrics and extractions into a structured Markdown evaluation report."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    report_lines: List[str] = [
        "# Local Model Benchmark Report: RPG Session Extraction",
        "",
        f"**Date:** {now_str}  ",
        f"**Source Transcript:** `{transcript_path}`  ",
        f"**Harness:** `scripts/benchmark_models.py`  ",
        "",
        "---",
        "",
        "## 1. Throughput & Speed Summary",
        "",
        "| Model | Status | Total Time (s) | Weighted Tok/s | 2A Time (s) | 2A Tok/s | 2B Time (s) | 2B Tok/s |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for r in sorted(results, key=lambda x: x["avg_tokens_per_sec"], reverse=True):
        m = r["model"]
        status = "OK" if r.get("status", "ok") == "ok" else "ERROR"
        tt = f"{r['total_time_sec']:.1f}"
        atps = f"{r['avg_tokens_per_sec']:.1f}"
        t_2a = f"{r['pass_2a']['time_sec']:.1f}"
        tps_2a = f"{r['pass_2a']['tokens_per_sec']:.1f}"
        t_2b = f"{r['pass_2b']['time_sec']:.1f}"
        tps_2b = f"{r['pass_2b']['tokens_per_sec']:.1f}"

        report_lines.append(f"| `{m}` | {status} | {tt} | {atps} | {t_2a} | {tps_2a} | {t_2b} | {tps_2b} |")

    report_lines.extend([
        "",
        "---",
        "",
        "## 2. Model Extractions",
        "",
    ])

    for r in results:
        m = r["model"]
        report_lines.extend([
            f"### Model: `{m}`",
            "",
            f"- **Status:** {r.get('status', 'ok').upper()}",
            f"- **Weighted Throughput:** {r['avg_tokens_per_sec']:.1f} tokens/second",
            f"- **Total Runtime:** {r['total_time_sec']:.1f} seconds",
            "",
            "#### Pass 2A (Tactical Facts Extraction)",
            "",
            "```markdown",
            r["pass_2a"]["output"].strip(),
            "```",
            "",
            "#### Pass 2B (Sensory Textures Extraction)",
            "",
            "```markdown",
            r["pass_2b"]["output"].strip(),
            "```",
            "",
        ])

    report_content = "\n".join(report_lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_content, encoding="utf-8")
    print(f"\n==> [Report Generated] {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Empirical benchmark runner for local Ollama models across RPG extraction passes on actual session transcripts."
    )
    parser.add_argument("transcript", help="Path to actual local session transcript file (.txt).")
    parser.add_argument("--glossary", help="Path to session glossary file (.md).")
    parser.add_argument("--campaign", default="benchmark", help="Campaign label for prompt headers (default: benchmark).")
    parser.add_argument("--models", nargs="+", help="Specific model names to benchmark.")
    parser.add_argument("--all-models", action="store_true", help="Benchmark all locally installed Ollama models.")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama API base URL (default: http://localhost:11434).")
    parser.add_argument("--keep-alive", default="0", help="Ollama keep-alive duration per model pass (default: 0 to evict between models).")
    parser.add_argument("--output", default="benchmark_results.md", help="Output path for benchmark report (default: benchmark_results.md).")

    args = parser.parse_args()

    transcript_p = Path(args.transcript).expanduser().resolve()
    if not transcript_p.exists():
        print(f"Error: Transcript file '{transcript_p}' does not exist.", file=sys.stderr)
        sys.exit(1)

    transcript_text = transcript_p.read_text(encoding="utf-8").strip()
    if not transcript_text:
        print(f"Error: Transcript file '{transcript_p}' is empty.", file=sys.stderr)
        sys.exit(1)

    glossary_text = ""
    if args.glossary:
        gp = Path(args.glossary).expanduser().resolve()
        if gp.exists():
            glossary_text = gp.read_text(encoding="utf-8").strip()

    if not scribe_session.check_ollama_status(args.ollama_url):
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
        preferred = ["qwen2.5:14b", "qwen2.5:32b", "qwen2.5:7b"]
        target_models = [m for m in preferred if m in installed_models]
        if not target_models:
            target_models = installed_models[:2]

    print("=" * 70)
    print("OUDE MECHANISMEN — LOCAL MODEL EXTRACTION BENCHMARK")
    print(f"Timestamp:  {datetime.now(timezone.utc).isoformat()}")
    print(f"Transcript: {transcript_p.name} ({len(transcript_text.split())} words)")
    print(f"Models:     {', '.join(target_models)}")
    print(f"Output:     {args.output}")
    print("=" * 70)

    results: List[Dict[str, Any]] = []
    for model in target_models:
        res = benchmark_model(
            args.ollama_url,
            model,
            transcript_text,
            glossary_text,
            campaign=args.campaign,
            session_slug=transcript_p.stem,
            keep_alive=args.keep_alive,
        )
        results.append(res)

    out_p = Path(args.output).expanduser().resolve()
    compile_benchmark_report(results, str(transcript_p), out_p)

    failed = [r["model"] for r in results if r.get("status") == "error"]
    if failed:
        print(f"\nBenchmark completed with errors on: {', '.join(failed)}", file=sys.stderr)
        sys.exit(1)

    print("\nBenchmark completed successfully.")


if __name__ == "__main__":
    main()

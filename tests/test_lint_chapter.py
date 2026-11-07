#!/usr/bin/env python3
"""
tests/test_lint_chapter.py — Unit and integration tests for scripts/lint_chapter.py.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lint_chapter


class TestLintChapter(unittest.TestCase):
    """Test suite covering the 2-4 framework, cadence, and noise masking."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_file(self, filename: str, content: str) -> Path:
        p = self.test_dir / filename
        p.write_text(content, encoding="utf-8")
        return p

    def test_compliant_monolingual(self):
        """Verify compliant monolingual chapter passes all checks with zero errors."""
        content = """---
layout: default
type: session
title: Compliant Chapter
---

## First Section

First sentence of first paragraph.
Second sentence of first paragraph.

First sentence of second paragraph.
Second sentence of second paragraph.
Third sentence of second paragraph.

## Second Section

Alpha sentence of first paragraph.
Beta sentence of first paragraph.

Gamma sentence of second paragraph.
Delta sentence of second paragraph.
"""
        file_path = self._write_file("compliant.md", content)
        report = lint_chapter.lint_chapter_file(file_path)

        self.assertEqual(report.status, "PASS")
        self.assertFalse(report.bilingual)
        self.assertEqual(len(report.sections), 1)
        self.assertEqual(report.sections[0].headings_count, 2)
        self.assertEqual(len(report.diagnostics), 0)

    def test_compliant_bilingual(self):
        """Verify dual-section bilingual chapter passes with independent section audits."""
        content = """---
layout: default
type: session
title: Dual Language Chapter
---

English version below
{: .text-delta .text-right}

## Primeiro Subtítulo

Primeira frase do primeiro parágrafo.
Segunda frase do primeiro parágrafo.

Primeira frase do segundo parágrafo.
Segunda frase do segundo parágrafo.

## Segundo Subtítulo

Terceira frase do primeiro parágrafo.
Quarta frase do primeiro parágrafo.

Quinta frase do segundo parágrafo.
Sexta frase do segundo parágrafo.

---

## First Subheader

First sentence of first paragraph.
Second sentence of first paragraph.

First sentence of second paragraph.
Second sentence of second paragraph.

## Second Subheader

Alpha sentence of first paragraph.
Beta sentence of first paragraph.

Gamma sentence of second paragraph.
Delta sentence of second paragraph.
"""
        file_path = self._write_file("bilingual.md", content)
        report = lint_chapter.lint_chapter_file(file_path)

        self.assertEqual(report.status, "PASS")
        self.assertTrue(report.bilingual)
        self.assertEqual(len(report.sections), 2)
        self.assertEqual(report.sections[0].headings_count, 2)
        self.assertEqual(report.sections[1].headings_count, 2)
        self.assertEqual(len(report.diagnostics), 0)

    def test_heading_count_violations(self):
        """Verify heading violations (<2 or >4) are accurately flagged."""
        # Single heading (too few)
        too_few = """---
title: Too Few
---

## Lone Subheader

Sentence one here.
Sentence two here.

Sentence three here.
Sentence four here.
"""
        rep_few = lint_chapter.lint_chapter_file(self._write_file("few_headings.md", too_few))
        self.assertEqual(rep_few.status, "FAIL")
        diag_few = [d for d in rep_few.diagnostics if d.rule == "heading-count"]
        self.assertEqual(len(diag_few), 1)
        self.assertEqual(diag_few[0].actual, 1)

        # 5 headings (too many)
        too_many = """---
title: Too Many
---

## H1
S1.
S2.

S3.
S4.

## H2
S1.
S2.

S3.
S4.

## H3
S1.
S2.

S3.
S4.

## H4
S1.
S2.

S3.
S4.

## H5
S1.
S2.

S3.
S4.
"""
        rep_many = lint_chapter.lint_chapter_file(self._write_file("many_headings.md", too_many))
        self.assertEqual(rep_many.status, "FAIL")
        diag_many = [d for d in rep_many.diagnostics if d.rule == "heading-count"]
        self.assertEqual(len(diag_many), 1)
        self.assertEqual(diag_many[0].actual, 5)

    def test_paragraph_count_violations(self):
        """Verify paragraph violations under a subheader (<2 or >4) are flagged."""
        content = """---
title: Bad Paragraph Count
---

## Heading One

Only one paragraph in this entire section.
Which violates the 2-4 rule.

## Heading Two

P1 sentence one.
P1 sentence two.

P2 sentence one.
P2 sentence two.

P3 sentence one.
P3 sentence two.

P4 sentence one.
P4 sentence two.

P5 sentence one.
P5 sentence two.
"""
        report = lint_chapter.lint_chapter_file(self._write_file("bad_paras.md", content))
        self.assertEqual(report.status, "FAIL")
        para_diags = [d for d in report.diagnostics if d.rule == "paragraph-count"]
        self.assertEqual(len(para_diags), 2)
        # First heading had 1 paragraph, second heading had 5
        self.assertEqual(para_diags[0].actual, 1)
        self.assertEqual(para_diags[1].actual, 5)

    def test_sentence_count_and_inline_cadence_violations(self):
        """Verify sentence counts (<2 or >4) and inline multiple sentences are flagged."""
        content = """---
title: Cadence Violations
---

## Heading One

Sentence one here.
Sentence two here.

Sentence three here.
Sentence four here.

## Heading Two

Single sentence paragraph fails sentence count.

This line has sentence one. This same line has sentence two.
This is sentence three.
"""
        report = lint_chapter.lint_chapter_file(self._write_file("bad_cadence.md", content))
        self.assertEqual(report.status, "FAIL")

        # Sentence count violation in paragraph 1 of Heading Two (only 1 sentence)
        sent_diags = [d for d in report.diagnostics if d.rule == "sentence-count"]
        self.assertTrue(any(d.actual == 1 for d in sent_diags))

        # Inline cadence violation in paragraph 2 of Heading Two (2 sentences on 1 line)
        cadence_diags = [d for d in report.diagnostics if d.rule == "cadence-one-sentence-per-line"]
        self.assertEqual(len(cadence_diags), 1)
        self.assertEqual(cadence_diags[0].actual, 2)

    def test_noise_masking_preserves_line_numbers(self):
        """Verify YAML, comments, and Dataview are masked while preserving line indices."""
        content = """---
layout: default
type: session
title: Line Preserving Chapter
---
{% include header_chapter.md %}
{% comment %}
```dataview
LIST FROM [[]]
```
- [index](../../directory/index.md)
{% endcomment %}
<!-- HTML comment block -->

## Heading One

First sentence of first paragraph.
Second sentence of first paragraph.

First sentence of second paragraph.
Second sentence of second paragraph.

## Heading Two

Alpha sentence of first paragraph.
Beta sentence of first paragraph.

Gamma sentence of second paragraph.
Delta sentence of second paragraph.
"""
        raw_lines = content.splitlines()
        masked = lint_chapter.mask_markdown_noise(content)
        self.assertEqual(len(masked), len(raw_lines))

        # Find the line number of "## Heading One" in raw vs masked
        raw_h1_line = next(i for i, line in enumerate(raw_lines, 1) if "## Heading One" in line)
        masked_h1_line = next(line_no for line_no, text in masked if "## Heading One" in text)
        self.assertEqual(raw_h1_line, masked_h1_line)

        # Linter should pass cleanly on this file
        file_path = self._write_file("line_check.md", content)
        report = lint_chapter.lint_chapter_file(file_path)
        self.assertEqual(report.status, "PASS")

    def test_abbreviation_disambiguation(self):
        """Verify abbreviations (e.g., Dr., vs.) and markdown links don't trigger false breaks."""
        line = "Dr. [Silus](../../directory/Fomalhaut/Cloudbank/Silus.md) meets with Lt. Vance e.g. at 1.5G."
        sentences = lint_chapter.split_sentences_in_line(line)
        self.assertEqual(len(sentences), 1)
        self.assertEqual(sentences[0], "Dr. Silus meets with Lt. Vance e.g. at 1.5G.")

    def test_dialogue_attribution_single_sentence(self):
        """Verify dialogue with lowercase speech tags ('You unfixed me!' he says.) is 1 sentence."""
        line = '"You unfixed me!" he says.'
        sentences = lint_chapter.split_sentences_in_line(line)
        self.assertEqual(len(sentences), 1)
        self.assertEqual(sentences[0], '"You unfixed me!" he says.')

    def test_markdown_cleanliness_warning(self):
        """Verify heading without immediate blank line triggers a cleanliness warning."""
        content = """---
title: Missing Blank Line
---

## Heading One
First sentence directly under heading without blank line.
Second sentence here.

Third sentence here.
Fourth sentence here.

## Heading Two

First sentence here.
Second sentence here.

Third sentence here.
Fourth sentence here.
"""
        report = lint_chapter.lint_chapter_file(self._write_file("no_blank.md", content))
        warns = [d for d in report.diagnostics if d.rule == "heading-blank-line"]
        self.assertEqual(len(warns), 1)
        self.assertEqual(warns[0].severity, "WARN")
        # In non-strict mode, warnings don't fail overall status
        self.assertEqual(report.status, "PASS")

    def test_json_output_serialization(self):
        """Verify FileReport correctly serializes to dictionary / JSON."""
        content = """---
title: JSON Test
---

## Heading One

S1.
S2.

S3.
S4.

## Heading Two

S1.
S2.

S3.
S4.
"""
        report = lint_chapter.lint_chapter_file(self._write_file("json_test.md", content))
        data = lint_chapter.asdict(report)
        json_str = json.dumps(data)
        loaded = json.loads(json_str)
        self.assertEqual(loaded["status"], "PASS")
        self.assertEqual(len(loaded["sections"]), 1)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""
tests/test_link_graph.py — Unit tests for scripts/link_graph.py.

Verifies candidate term extraction, co-occurrence graph construction, and
link-graph prioritisation ordering used by chunked scribe-session extraction.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import link_graph  # noqa: E402


class TestLinkGraph(unittest.TestCase):
    def test_extract_candidate_terms_filters_stopwords_and_dedupes(self):
        terms = link_graph.extract_candidate_terms("The Cat sat. Kael Vorn arrived with Kael Vorn again.")
        self.assertIn("Kael Vorn", terms)
        self.assertNotIn("The", terms)
        self.assertEqual(terms.count("Kael Vorn"), 1)

    def test_build_link_graph_weights_cooccurrence(self):
        chunks = [
            "Kael met Monarch at Fomalhaut.",
            "Monarch spoke with Kael about Fomalhaut.",
        ]
        graph = link_graph.build_link_graph(chunks)
        # Kael and Monarch co-occur in both chunks -> weight 2
        self.assertEqual(graph["Kael"]["Monarch"], 2)
        self.assertEqual(graph["Monarch"]["Kael"], 2)

    def test_prioritise_terms_ranks_by_weighted_degree(self):
        chunks = [
            "Kael met Monarch at Fomalhaut.",
            "Monarch spoke with Kael about Fomalhaut.",
            "Kael argued with Vex alone.",
        ]
        graph = link_graph.build_link_graph(chunks)
        ranked = link_graph.prioritise_terms(graph)
        self.assertEqual(ranked[0][0], "Kael")
        self.assertGreaterEqual(ranked[0][1], ranked[-1][1])


if __name__ == "__main__":
    unittest.main()

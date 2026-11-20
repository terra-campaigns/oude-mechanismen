#!/usr/bin/env python3
"""
scripts/link_graph.py — Link-graph analysis for session extraction chunks.

Builds a term co-occurrence graph over transcript chunks and scores terms by
weighted degree centrality, so glossary generation can prioritise high-impact
proper nouns. Pure functions only; no I/O, no model calls.
All output strictly adheres to British English.
"""

import re
from collections import defaultdict
from typing import Dict, List, Tuple

# Capitalised single or multi-word terms (proper-noun candidates).
TERM_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b")

# Sentence-initial common words that are capitalised but never proper nouns.
STOPWORDS = {
    "The", "A", "An", "This", "That", "These", "Those", "He", "She", "It",
    "They", "We", "I", "You", "In", "On", "At", "As", "But", "And", "Or",
    "Not", "No", "Yes", "Then", "When", "While", "After", "Before",
    "There", "Here", "What", "Which", "Who", "How", "If", "So", "His", "Her",
    "Their", "Our", "Your", "My", "Its", "Session", "Chapter",
}


def extract_candidate_terms(text: str) -> List[str]:
    """Extract distinct capitalised proper-noun candidate terms from text."""
    terms = [t.strip() for t in TERM_RE.findall(text)]
    seen = set()
    ordered: List[str] = []
    for t in terms:
        if t in STOPWORDS or len(t) < 3:
            continue
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    return ordered


def build_link_graph(chunks: List[str]) -> Dict[str, Dict[str, int]]:
    """
    Build a weighted term co-occurrence graph: an edge between two terms with
    weight equal to the number of chunks in which they co-occur.
    """
    graph: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for chunk in chunks:
        terms = sorted(set(extract_candidate_terms(chunk)))
        for i, a in enumerate(terms):
            for b in terms[i + 1:]:
                graph[a][b] += 1
                graph[b][a] += 1
    return {term: dict(neighbours) for term, neighbours in graph.items()}


def term_scores(graph: Dict[str, Dict[str, int]]) -> Dict[str, int]:
    """Weighted degree centrality per term."""
    return {term: sum(neighbours.values()) for term, neighbours in graph.items()}


def prioritise_terms(
    graph: Dict[str, Dict[str, int]],
    top_n: int = 20,
) -> List[Tuple[str, int]]:
    """
    Rank all graph terms by weighted degree, descending (ties alphabetical).
    Returns a list of (term, score) truncated to top_n.
    """
    scores = term_scores(graph)
    ranked = [(t, s) for t, s in scores.items()]
    ranked.sort(key=lambda item: (-item[1], item[0]))
    return ranked[:top_n]

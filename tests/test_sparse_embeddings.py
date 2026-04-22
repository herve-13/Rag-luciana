from __future__ import annotations

from chatfriends_retrieval.core import sparse_embeddings as se


def test_build_readable_terms_handles_french_accents_and_apostrophes():
    terms = se._build_readable_terms("Matteo étudie l'ingénierie informatique.")
    assert [item["term"] for item in terms] == ["matteo", "étudie", "ingénierie", "informatique"]


def test_build_readable_terms_handles_spanish_unicode():
    terms = se._build_readable_terms("La informática médica en España")
    labels = [item["term"] for item in terms]
    assert "informática" in labels
    assert "médica" in labels
    assert "españa" in labels


def test_build_readable_terms_handles_italian_hyphen_and_apostrophe():
    terms = se._build_readable_terms("L'amore italo-francese di Luciana")
    assert [item["term"] for item in terms] == ["amore", "italo", "francese", "luciana"]


def test_build_readable_terms_handles_english_plain_text():
    terms = se._build_readable_terms("Long term memory and context retrieval")
    assert [item["term"] for item in terms] == ["long", "term", "memory", "context", "retrieval"]


def test_build_readable_terms_filters_noise_fragments():
    terms = se._build_readable_terms("type d ingenierie etudie par Matteo")
    assert [item["term"] for item in terms] == ["ingenierie", "etudie", "matteo"]


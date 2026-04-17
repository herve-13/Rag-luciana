from __future__ import annotations

import pytest
from pydantic import ValidationError

from rag_luciana.api.schemas import IngestRequest, QueryRequest


def test_ingest_request_rejects_global_scope():
    with pytest.raises(ValidationError):
        IngestRequest(
            character_id="luciana",
            scope="global",
            user_id="u1",
            doc_id="d1",
            data={"retrieval_text": "x"},
        )


def test_query_request_requires_private_scope():
    with pytest.raises(ValidationError):
        QueryRequest(
            character_id="luciana",
            user_id="u1",
            query="hello",
            scope="both",
        )


def test_query_request_accepts_sparse_query_terms():
    req = QueryRequest(
        assistant_id="luciana",
        user_id="u1",
        query="qui est ton pere",
        scope="private",
        sparse_query={"terms": [{"term": "pere", "weight": 1.0}]},
    )
    assert req.sparse_query is not None
    assert len(req.sparse_query.terms) == 1
    assert req.sparse_query.terms[0].term == "pere"
    assert req.tenant_id == "herve"
    assert req.assistant_id == "luciana"
    assert req.character_id == "luciana"


def test_ingest_request_accepts_assistant_id_alias():
    req = IngestRequest(
        assistant_id="luciana",
        scope="private",
        user_id="u1",
        doc_id="d1",
        data={"retrieval_text": "x"},
    )

    assert req.tenant_id == "herve"
    assert req.assistant_id == "luciana"
    assert req.character_id == "luciana"


def test_query_request_rejects_mismatched_assistant_and_character_ids():
    with pytest.raises(ValidationError):
        QueryRequest(
            assistant_id="marina",
            character_id="luciana",
            user_id="u1",
            query="hello",
            scope="private",
        )

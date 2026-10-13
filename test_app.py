"""Tests for the transcript redaction service.

None of these tests load or download the Hugging Face model. A FakeRedactor
returns fixed entities and runs them through the real redaction logic
(redactor.redact_text), so the threshold, email rule, type filtering, and
overlap handling are all exercised without transformers.

Run from the project root:  python -m pytest -v
"""
import logging
import pathlib
import sys

import pytest

# Make app.py and redactor.py importable no matter where pytest is launched.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "my-app"))

from app import create_app  # noqa: E402
from redactor import DEFAULT_MIN_SCORE, MODEL_NAME, redact_text  # noqa: E402

SAMPLE = (
    "I met Dr. Maria Lopez at Riverside Clinic in Denver. "
    "Email me at maria@example.com."
)


def make_entity(text, phrase, type_, score):
    """Build a model-style entity for `phrase`, located inside `text`."""
    start = text.index(phrase)
    return {"type": type_, "start": start, "end": start + len(phrase), "score": score}


SAMPLE_ENTITIES = [
    make_entity(SAMPLE, "Maria Lopez", "PER", 0.998),
    make_entity(SAMPLE, "Riverside Clinic", "ORG", 0.975),
    make_entity(SAMPLE, "Denver", "LOC", 0.999),
]


class FakeRedactor:
    """Stands in for redactor.Redactor: fixed entities, no model."""

    model_name = MODEL_NAME

    def __init__(self, entities, min_score=DEFAULT_MIN_SCORE):
        self.entities = entities
        self.min_score = min_score

    def redact(self, text, types=None, min_score=None):
        if min_score is None:
            min_score = self.min_score
        result = redact_text(text, self.entities, types, min_score)
        result["model"] = self.model_name
        return result


def make_client(entities=SAMPLE_ENTITIES):
    app = create_app(redactor=FakeRedactor(entities))
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def client():
    return make_client()


# ---------------------------------------------------------------- routes

def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["model"] == MODEL_NAME


def test_index_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Transcript Redaction Service" in response.data


def test_successful_redaction(client):
    response = client.post("/api/redact", json={"text": SAMPLE})
    assert response.status_code == 200
    body = response.get_json()

    assert body["redacted_text"] == (
        "I met Dr. [PER] at [ORG] in [LOC]. Email me at [EMAIL]."
    )
    assert body["model"] == MODEL_NAME
    assert [e["type"] for e in body["entities"]] == ["PER", "ORG", "LOC", "EMAIL"]

    first = body["entities"][0]
    assert first["text"] == "Maria Lopez"
    assert SAMPLE[first["start"]:first["end"]] == "Maria Lopez"
    assert isinstance(first["score"], float)


def test_types_filter_only_redacts_requested_types(client):
    response = client.post("/api/redact", json={"text": SAMPLE, "types": ["PER"]})
    assert response.status_code == 200
    redacted = response.get_json()["redacted_text"]

    assert "[PER]" in redacted
    assert "Riverside Clinic" in redacted  # ORG not requested
    assert "Denver" in redacted            # LOC not requested


def test_emails_redacted_even_with_empty_types(client):
    response = client.post("/api/redact", json={"text": SAMPLE, "types": []})
    assert response.status_code == 200
    body = response.get_json()

    assert "maria@example.com" not in body["redacted_text"]
    assert "[EMAIL]" in body["redacted_text"]
    assert "Maria Lopez" in body["redacted_text"]  # names left alone
    assert [e["type"] for e in body["entities"]] == ["EMAIL"]


def test_low_score_entities_are_not_redacted():
    text = "Talk to Alex in Boston."
    entities = [
        make_entity(text, "Alex", "PER", 0.95),
        make_entity(text, "Boston", "LOC", 0.50),  # below the 0.80 threshold
    ]
    client = make_client(entities)

    response = client.post("/api/redact", json={"text": text})
    assert response.status_code == 200
    body = response.get_json()

    assert body["redacted_text"] == "Talk to [PER] in Boston."
    assert [e["type"] for e in body["entities"]] == ["PER"]


# ----------------------------------------------------------- validation

@pytest.mark.parametrize(
    "types",
    [["PER", "FOO"], ["email"], "PER", [1, 2], {"PER": True}],
)
def test_invalid_types_return_400(client, types):
    response = client.post("/api/redact", json={"text": SAMPLE, "types": types})
    assert response.status_code == 400
    assert "error" in response.get_json()


@pytest.mark.parametrize(
    "payload",
    [
        {"text": ""},            # empty
        {"text": "a" * 10001},   # one over the limit
        {},                      # text missing
        {"text": None},          # wrong type
        {"text": 12345},         # wrong type
    ],
)
def test_bad_text_returns_400(client, payload):
    response = client.post("/api/redact", json=payload)
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_non_json_body_returns_400(client):
    response = client.post(
        "/api/redact", data="just some text", content_type="text/plain"
    )
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_json_array_body_returns_400(client):
    response = client.post("/api/redact", json=["not", "an", "object"])
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_score_threshold_lives_in_app_config():
    app = create_app(redactor=FakeRedactor(SAMPLE_ENTITIES))
    assert app.config["MIN_SCORE"] == 0.80
    assert app.config["MAX_TEXT_LENGTH"] == 10000


def test_text_at_exact_limit_is_accepted(client):
    response = client.post("/api/redact", json={"text": "a" * 10000})
    assert response.status_code == 200


# ------------------------------------------------------------- 404 / privacy

def test_unknown_api_url_returns_json_404(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.is_json
    assert "error" in response.get_json()


def test_submitted_text_is_never_logged(client, caplog):
    with caplog.at_level(logging.DEBUG):
        client.post("/api/redact", json={"text": SAMPLE})
    assert "Maria Lopez" not in caplog.text
    assert "maria@example.com" not in caplog.text


# ------------------------------------------- redaction logic (no Flask at all)

def test_email_wins_over_entity_overlapping_it():
    # The model may tag "maria" inside an email address as a person.
    text = "Write to maria@example.com today."
    entities = [make_entity(text, "maria", "PER", 0.99)]

    result = redact_text(text, entities)

    assert result["redacted_text"] == "Write to [EMAIL] today."
    assert [e["type"] for e in result["entities"]] == ["EMAIL"]


def test_multiple_entities_keep_positions_correct():
    # Replacements change the text length, so they must be applied back to front.
    text = "Ana met Bob in Rome."
    entities = [
        make_entity(text, "Ana", "PER", 0.99),
        make_entity(text, "Bob", "PER", 0.99),
        make_entity(text, "Rome", "LOC", 0.99),
    ]

    result = redact_text(text, entities)

    assert result["redacted_text"] == "[PER] met [PER] in [LOC]."

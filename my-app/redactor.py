import re

MODEL_NAME = "dslim/bert-base-NER"
NER_TYPES = ("PER", "LOC", "ORG", "MISC")
DEFAULT_MIN_SCORE = 0.80

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

def validate_types(types):
    """Return the set of NER types to redact.

    None -> all four types. Anything that isn't a list of known types
    raises ValueError, which app.py turns into a 400 response.
    An empty list is allowed and means "emails only".
    """
    if types is None:
        return set(NER_TYPES)
    if not isinstance(types, (list, tuple)) or not all(isinstance(t, str) for t in types):
        raise ValueError("types must be a list of strings")
    unknown = sorted(set(types) - set(NER_TYPES))
    if unknown:
        raise ValueError(
            f"unknown types: {', '.join(unknown)}; allowed: {', '.join(NER_TYPES)}"
        )
    return set(types)


def find_emails(text):
    """Email matches in the same shape as model entities."""
    return [
        {"type": "EMAIL", "start": m.start(), "end": m.end(), "score": 1.0}
        for m in EMAIL_RE.finditer(text)
    ]


def _overlaps(a, b):
    return a["start"] < b["end"] and b["start"] < a["end"]


def resolve_overlaps(emails, ner):
    """Drop entities that overlap one already kept.

    Emails win (the model may tag "maria" inside maria@example.com as PER),
    then higher-scoring NER entities win over lower ones.
    """
    kept = []
    for ent in emails + sorted(ner, key=lambda e: e["score"], reverse=True):
        if not any(_overlaps(ent, k) for k in kept):
            kept.append(ent)
    return sorted(kept, key=lambda e: e["start"])


def apply_redactions(text, entities):
    """Replace each span with [TYPE], working from the end of the text
    backwards so earlier start/end positions stay valid."""
    for ent in sorted(entities, key=lambda e: e["start"], reverse=True):
        text = text[: ent["start"]] + f"[{ent['type']}]" + text[ent["end"]:]
    return text


def redact_text(text, raw_entities, types=None, min_score=DEFAULT_MIN_SCORE):
    """Core logic: filter model entities, add emails, redact.

    `raw_entities` are dicts with type/start/end/score, as returned by
    Redactor.find_entities().
    """
    wanted = validate_types(types)
    ner = [
        e for e in raw_entities
        if e["type"] in wanted and e["score"] >= min_score
    ]
    kept = resolve_overlaps(find_emails(text), ner)

    return {
        "redacted_text": apply_redactions(text, kept),
        "entities": [
            {
                "type": e["type"],
                "text": text[e["start"]:e["end"]],  
                "start": e["start"],
                "end": e["end"],
                "score": round(float(e["score"]), 3),
            }
            for e in kept
        ],
    }

class Redactor:
    """
    Loads the NER model once and redacts text with it.
    """

    model_name = MODEL_NAME  

    def __init__(
        self,
        model_name=MODEL_NAME,
        stride=128,
        min_score=DEFAULT_MIN_SCORE,
    ):
        from transformers import pipeline

        self.model_name = model_name
        self.min_score = min_score

        self._ner = pipeline(
            "ner",
            model=model_name,
            aggregation_strategy="simple",
            stride=stride,
        )

    def find_entities(self, text):
        """Run the model and normalize its output to plain Python types."""
        results = []
        for r in self._ner(text):
            if r.get("start") is None or r.get("end") is None:
                continue
            results.append({
                "type": r["entity_group"],
                "start": int(r["start"]),
                "end": int(r["end"]),
                "score": float(r["score"]), 
            })
        return results

    def redact(self, text, types=None, min_score=None):
        if min_score is None:
            min_score = self.min_score

        result = redact_text(
            text,
            self.find_entities(text),
            types,
            min_score,
        )
        result["model"] = self.model_name
        return result

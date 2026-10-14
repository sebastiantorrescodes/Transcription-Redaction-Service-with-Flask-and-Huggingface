# Transcription-Redaction-Service-with-Flask-and-Huggingface

A small Flask service that de-identifies interview transcripts before they are shared. It uses the Hugging Face NER model [`dslim/bert-base-NER`](https://huggingface.co/dslim/bert-base-NER) to find people (PER), places (LOC), organizations (ORG) and other names (MISC), and replaces each one with its type, such as `[PER]`. Email addresses are always replaced with `[EMAIL]`.

```
I met Dr. Maria Lopez at Riverside Clinic in Denver. Email me at maria@example.com.
I met Dr. [PER] at [ORG] in [LOC]. Email me at [EMAIL].
```

The output is a first pass, not a guarantee. A person should still review every redacted transcript. The service never saves or logs the submitted text.

## Files

- `my-app/redactor.py`: loads the model and does the redaction (no Flask code)
- `my-app/app.py`: the Flask app and routes
- `my-app/templates/index.html`: the web page
- `test_app.py`: tests (they use a fake model, so nothing is downloaded)
- `client_example.py`: example script that calls the API

## Setup

```
cd my-app
python -m venv .venv
.venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## Run code

```
cd my-app
.venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
flask run
```

Then open http://127.0.0.1:5000. The first start downloads the model (about 400 MB), so it can take a few minutes before the server is ready.

## Use the API from other tools

Any tool that can send an HTTP POST can use the service. With the server running, from the project root:

```
python client_example.py                       # redact a built-in sample
python client_example.py transcript.txt        # redact a text file
python client_example.py transcript.txt --types PER LOC
```

Or with curl:

```
curl -X POST http://127.0.0.1:5000/api/redact -H "Content-Type: application/json" -d "{\"text\": \"I met Maria Lopez in Denver.\"}"
```

`text` must be 1 to 10,000 characters. `types` is optional and can be any of `PER`, `LOC`, `ORG`, `MISC`. If you leave it out, all four are redacted. Email addresses are always redacted.

## Run tests

From the project root, with the virtual environment active:

```
python -m pytest -v
```

## Limitations

This service only finds person, place, organization and "other" names, plus email addresses in standard `name@domain.com` form. It does not find dates, ages, phone numbers, street addresses, ID numbers, job titles ("the head nurse"), or relationships ("my brother-in-law"), and it will miss emails written out as "maria at example dot com". It often misses names that are lowercase, misspelled, nicknames, or unusual, and it does poorly on non-English text. Any name the model is less than 80% sure about is left in the text on purpose. It also cannot tell when ordinary details add up to identify someone, for example "the only Korean teacher at the high school in my town". For these reasons, the output is only a first pass. A person who knows the study must read every redacted transcript in full and fix what was missed before it is shared outside the lab.

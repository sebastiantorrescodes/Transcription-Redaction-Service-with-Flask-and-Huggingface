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

## Run tests

From the project root, with the virtual environment active:

```
python -m pytest -v
```

"""Example non-browser client for the Transcript Redaction Service.

Sends a transcript to the running service's /api/redact endpoint and prints
the redacted text and the list of removed items. Any tool that can send an
HTTP POST (R, JavaScript, curl, ...) can do the same.

Start the server first (python app.py), then:

    python client_example.py                          # redact a built-in sample
    python client_example.py transcript.txt           # redact a text file
    python client_example.py transcript.txt --types PER LOC
    python client_example.py --types                  # emails only
    python client_example.py --url http://other-host:5000
"""
import argparse
import sys

import requests

SAMPLE_TEXT = (
    "I met Dr. Maria Lopez at Riverside Clinic in Denver. "
    "Email me at maria@example.com."
)


def main():
    parser = argparse.ArgumentParser(description="Redact a transcript via the API.")
    parser.add_argument("file", nargs="?", help="text file to redact (default: sample)")
    parser.add_argument(
        "--types",
        nargs="*",
        choices=["PER", "LOC", "ORG", "MISC"],
        help="categories to redact (default: all). Give none for emails only.",
    )
    parser.add_argument("--url", default="http://127.0.0.1:5000", help="server address")
    args = parser.parse_args()

    if args.file:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    else:
        text = SAMPLE_TEXT

    payload = {"text": text}
    if args.types is not None:
        payload["types"] = args.types

    try:
        response = requests.post(f"{args.url}/api/redact", json=payload, timeout=120)
    except requests.exceptions.RequestException as exc:
        sys.exit(f"Could not reach the server at {args.url}: {exc}")

    try:
        data = response.json()
    except ValueError:
        sys.exit(f"Unexpected response (HTTP {response.status_code}): {response.text[:200]}")

    if not response.ok:
        sys.exit(f"Error (HTTP {response.status_code}): {data.get('error', data)}")

    print("REDACTED TEXT")
    print(data["redacted_text"])
    print()
    print(f"REMOVED ({len(data['entities'])} items, model: {data['model']})")
    for ent in data["entities"]:
        print(f"  {ent['type']:<6} {ent['text']!r}  ({ent['score'] * 100:.1f}%)")
    print()
    print("A human must still review the transcript before it is shared.")


if __name__ == "__main__":
    main()

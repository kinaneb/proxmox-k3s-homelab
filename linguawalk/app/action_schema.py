"""Export the public LinguaWalk contract for a Custom GPT Action."""

from __future__ import annotations

import argparse
import copy
import ipaddress
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from app import app


ACTION_OPERATIONS = {
    "/profile": {
        "get": (
            "getLearnerProfile",
            "Get learner profile",
            "Read the learner's baseline, CEFR levels, strengths, weaknesses, learning-method preferences, and current item counts.",
        ),
    },
    "/progress": {
        "get": (
            "getLearningProgress",
            "Get learning progress",
            "Read lifetime session and event totals, current vocabulary and grammar state, and the latest weekly and monthly summaries.",
        ),
    },
    "/learning/targets": {
        "get": (
            "getLearningTargets",
            "Get due learning targets",
            "Get vocabulary and grammar items currently due for natural review, including priorities, reasons, and recommended methods.",
        ),
    },
    "/session/start": {
        "post": (
            "startSession",
            "Start a learning session",
            "Create a LinguaWalk session and return its server-owned ID together with the learner profile, due targets, and maintenance state.",
        ),
    },
    "/vocabulary/event": {
        "post": (
            "recordVocabularyEvent",
            "Record a vocabulary event",
            "Record one observed vocabulary learning event for the active session and return the updated vocabulary item state.",
        ),
    },
    "/grammar/event": {
        "post": (
            "recordGrammarEvent",
            "Record a grammar event",
            "Record one observed grammar learning event for the active session and return the updated grammar item state.",
        ),
    },
    "/session/end": {
        "post": (
            "endSession",
            "End a learning session",
            "Close a LinguaWalk session with its subjects, summary, and learner notes, then return stored closure and event counts.",
        ),
    },
}


def validate_public_server_url(value: str) -> str:
    """Return a normalized public HTTPS base URL or raise ValueError."""
    parsed = urlsplit(value)
    if parsed.scheme != "https":
        raise ValueError("the Action server URL must use https")
    if not parsed.hostname:
        raise ValueError("the Action server URL must include a hostname")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("the Action server URL cannot contain credentials, a query, or a fragment")
    if parsed.port not in (None, 443):
        raise ValueError("the Action server URL must use public HTTPS port 443")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(
        (".localhost", ".local", ".home.arpa", ".example", ".invalid", ".test")
    ):
        raise ValueError("the Action server URL must use a public DNS hostname")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        if "." not in hostname:
            raise ValueError("the Action server URL must use a fully qualified public hostname")
    else:
        if not address.is_global:
            raise ValueError("the Action server URL cannot use a private or reserved IP address")

    path = parsed.path.rstrip("/")
    return urlunsplit(("https", parsed.netloc, path, "", ""))


def build_action_schema(server_url: str) -> dict:
    """Build the minimal GPT Action schema from FastAPI's generated contract."""
    normalized_url = validate_public_server_url(server_url)
    source = copy.deepcopy(app.openapi())
    paths: dict = {}

    for path, methods in ACTION_OPERATIONS.items():
        paths[path] = {}
        for method, (operation_id, summary, description) in methods.items():
            operation = source["paths"][path][method]
            operation["operationId"] = operation_id
            operation["summary"] = summary
            operation["description"] = description
            operation["security"] = [{"bearerAuth": []}]
            if method != "get":
                # These writes are the expected, low-impact purpose of this
                # single-user Action. Users can still decline or revoke access.
                operation["x-openai-isConsequential"] = False
            paths[path][method] = operation

    source["info"] = {
        "title": "LinguaWalk Learning Memory API",
        "version": source["info"]["version"],
        "description": (
            "Stores and retrieves one learner's LinguaWalk sessions, observed "
            "vocabulary and grammar events, adaptive targets, profile, and progress."
        ),
    }
    source["servers"] = [{"url": normalized_url}]
    source["paths"] = paths
    source.setdefault("components", {}).setdefault("securitySchemes", {})[
        "bearerAuth"
    ] = {
        "type": "http",
        "scheme": "bearer",
        "description": "LinguaWalk API key configured as Bearer authentication in the GPT editor.",
    }
    return source


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a minimal OpenAPI document for the LinguaWalk GPT Action."
    )
    parser.add_argument("--server-url", required=True, help="Public HTTPS base URL")
    parser.add_argument(
        "--output",
        type=Path,
        help="Output JSON path; omit to write to standard output",
    )
    args = parser.parse_args()

    try:
        schema = build_action_schema(args.server_url)
    except ValueError as exc:
        parser.error(str(exc))

    rendered = json.dumps(schema, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()

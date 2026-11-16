# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""CLA gate without pull_request_target (ARCHITECTURE section 9).

check: used by the "cla" job on pull_request. Passes for exempt accounts (the owner and
       bots) and for logins recorded in signatures/cla.json on the cla-signatures branch.
sign:  used by the issue_comment workflow, which never checks out pull request code.
       Records the commenter when the comment is the signing phrase.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SIGN_PHRASE = "I have read the CLA Document and I hereby sign the CLA"
CLA_URL = "https://github.com/mohnishbasha/stokeai-trading-supertrends/blob/develop/CLA.md"


def is_signature(body: str) -> bool:
    """True when a comment is exactly the signing phrase (case and trailing period ignored)."""
    normalized = re.sub(r"\s+", " ", body).strip().rstrip(".").lower()
    return normalized == SIGN_PHRASE.lower()


def _read(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"signedContributors": []}
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        msg = f"{path}: expected a JSON object"
        raise TypeError(msg)
    data.setdefault("signedContributors", [])
    return data


def _signed(data: dict[str, Any], login: str) -> bool:
    return any(str(c.get("name", "")).lower() == login.lower() for c in data["signedContributors"])


def check(author: str, signatures: Path, exempt: set[str]) -> int:
    if author.lower() in exempt:
        print(f"ok {author} is exempt from the CLA")  # noqa: T201
        return 0
    if _signed(_read(signatures), author):
        print(f"ok {author} has signed the CLA")  # noqa: T201
        return 0
    print(  # noqa: T201
        f"x {author} has not signed the CLA. Read {CLA_URL}, then comment on the pull request "
        f'with exactly: "{SIGN_PHRASE}"'
    )
    return 1


def sign(args: argparse.Namespace) -> int:
    """Record args.author when args.body is the signing phrase."""
    author, body, signatures = args.author, args.body, args.signatures
    if not is_signature(body):
        print("ok comment is not the signing phrase; nothing recorded")  # noqa: T201
        return 0
    data = _read(signatures)
    if _signed(data, author):
        print(f"ok {author} already signed")  # noqa: T201
        return 0
    data["signedContributors"].append(
        {
            "name": author,
            "id": args.author_id,
            "comment_id": args.comment_id,
            "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "pullRequestNo": args.pr,
        }
    )
    signatures.parent.mkdir(parents=True, exist_ok=True)
    signatures.write_text(json.dumps(data, indent=2) + "\n")
    print(f"ok recorded CLA signature for {author}")  # noqa: T201
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("check")
    c.add_argument("--author", required=True)
    c.add_argument("--signatures", type=Path, required=True)
    c.add_argument("--exempt", default="")
    s = sub.add_parser("sign")
    s.add_argument("--author", required=True)
    s.add_argument("--author-id", type=int, required=True)
    s.add_argument("--pr", type=int, required=True)
    s.add_argument("--comment-id", type=int, required=True)
    s.add_argument("--signatures", type=Path, required=True)
    s.add_argument("--body", default=SIGN_PHRASE, help="the comment text")
    args = parser.parse_args(argv)
    if args.command == "check":
        exempt = {e.strip().lower() for e in args.exempt.split(",") if e.strip()}
        return check(args.author, args.signatures, exempt)
    return sign(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

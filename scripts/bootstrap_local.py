"""Create a local ignored environment file without exposing generated secrets."""

from __future__ import annotations

import argparse
import secrets
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="replace an existing local .env")
    args = parser.parse_args()

    if ENV_PATH.exists() and not args.force:
        print(".env already exists; leaving it unchanged")
        return 0

    token = secrets.token_urlsafe(48)
    workspace_id = uuid4()
    content = "\n".join(
        (
            "# Generated local M2 settings. Never commit this file.",
            "OPINTEL_APP_ENV=development",
            "OPINTEL_DATABASE_URL=sqlite:///./local-data/m0.db",
            "OPINTEL_FIXTURE_ROOT=fixtures/public-web",
            f"OPINTEL_AUTH_TOKEN={token}",
            "OPINTEL_AUTH_SUBJECT=local-operator",
            "OPINTEL_AUTH_ROLES=admin,operator,reviewer,viewer",
            f"OPINTEL_WORKSPACE_ID={workspace_id}",
            "OPINTEL_ALLOWED_ORIGINS=http://127.0.0.1:3000,http://localhost:3000",
            "OPINTEL_API_HOST=127.0.0.1",
            "OPINTEL_API_PORT=8000",
            "OPINTEL_WORKER_POLL_SECONDS=0.25",
            "OPINTEL_WORKER_LEASE_SECONDS=30",
            "OPINTEL_RESEARCH_LIVE_ENABLED=false",
            "OPINTEL_RESEARCH_BROWSER_ENABLED=false",
            "",
        )
    )
    ENV_PATH.write_text(content, encoding="utf-8", newline="\n")
    print("Created ignored .env with a generated local token and workspace ID.")
    print("Open .env locally to copy the token into the diagnostic UI; it was not printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

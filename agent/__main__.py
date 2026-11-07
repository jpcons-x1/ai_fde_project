"""Work claims with the UnderCover Agent.

uv run -m agent CLM-1001   works one claim
uv run -m agent            works every waiting claim in turn
"""

import sys
from uuid import uuid4

from agent.main import request, run


def main(claim_ids: list[str]) -> None:
    if not claim_ids:
        claims = request("GET", "/api/claims").json()
        claim_ids = [c["claim_id"] for c in claims if c["status"] == "waiting"]
    for claim_id in claim_ids:
        print(f"{claim_id}: {run(claim_id, str(uuid4()))}")


if __name__ == "__main__":
    main(sys.argv[1:])

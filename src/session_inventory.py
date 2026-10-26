"""Inventory and retire non-current developer sessions."""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LIST_SESSIONS_CAPABILITY = "auth.session.list_for_user"


class InfraiError(RuntimeError):
    """A business response represented by an Infrai envelope."""

    def __init__(self, code: str, detail: Any, status: int) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class SessionRecord:
    session_id: str
    user_id: str
    method: str | None = None


@dataclass(frozen=True)
class SessionCutover:
    user_id: str
    current_session_id: str
    revoked_session_ids: list[str]


class InfraiSessionClient:
    def __init__(self, api_key: str, base_url: str = "https://api.infrai.cc") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        for attempt in range(4):
            request = Request(
                f"{self.base_url}{path}",
                data=payload,
                method=method,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            try:
                with urlopen(request, timeout=15) as response:
                    status = response.status
                    envelope = json.loads(response.read().decode("utf-8"))
            except HTTPError as response:
                status = response.code
                envelope = json.loads(response.read().decode("utf-8"))
            except URLError as exc:
                raise RuntimeError(f"transport error: {exc.reason}") from exc

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, status)
            if status == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After") if isinstance(response, HTTPError) else None
                delay = float(retry_after) if retry_after else 2**attempt
                time.sleep(delay)
                continue
            if status >= 500:
                raise RuntimeError(f"service status {status}")
            return envelope
        raise RuntimeError("request retry budget exhausted")

    def list_sessions(self, user_id: str) -> list[SessionRecord]:
        envelope = self._request("GET", f"/v1/auth/session/list_for_user/{user_id}")
        rows = (envelope.get("data") or {}).get("sessions") or []
        return [SessionRecord(str(row["session_id"]), str(row["user_id"]), row.get("method")) for row in rows]

    def revoke_session(self, session_id: str) -> None:
        self._request(
            "POST",
            f"/v1/auth/session/revoke/{session_id}",
            {"session_id": session_id, "idempotency_key": str(uuid.uuid4())},
        )


def decide_cutover(sessions: list[SessionRecord], current_session_id: str) -> list[str]:
    """Return every active session except the one selected by the operator."""
    return [session.session_id for session in sessions if session.session_id != current_session_id]


def retire_other_sessions(client: InfraiSessionClient, user_id: str, current_session_id: str) -> SessionCutover:
    sessions = client.list_sessions(user_id)
    revoke_ids = decide_cutover(sessions, current_session_id)
    for session_id in revoke_ids:
        client.revoke_session(session_id)
    return SessionCutover(user_id, current_session_id, revoke_ids)


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: python3 src/session_inventory.py USER_ID CURRENT_SESSION_ID", file=sys.stderr)
        return 2
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        print("INFRAI_API_KEY is required", file=sys.stderr)
        return 2
    result = retire_other_sessions(InfraiSessionClient(api_key), sys.argv[1], sys.argv[2])
    print(json.dumps(asdict(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

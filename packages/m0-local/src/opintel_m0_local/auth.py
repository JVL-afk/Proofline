"""Development-only bearer authentication adapter."""

from __future__ import annotations

import secrets
from uuid import UUID

from opintel_m0.domain import Principal, Role


class LocalTokenAuthenticator:
    def __init__(
        self,
        expected_token: str,
        subject: str,
        workspace_id: UUID,
        roles: frozenset[str] | None = None,
    ) -> None:
        if len(expected_token) < 32:
            raise ValueError("local authentication token must contain at least 32 characters")
        self._expected_token = expected_token
        selected = roles or frozenset({Role.OPERATOR.value, Role.VIEWER.value})
        try:
            domain_roles = frozenset(Role(item) for item in selected)
        except ValueError as error:
            raise ValueError("local authentication contains an unsupported role") from error
        self._principal = Principal(
            subject=subject,
            workspace_id=workspace_id,
            roles=domain_roles,
        )

    def authenticate(self, token: str) -> Principal | None:
        if not token or not secrets.compare_digest(token, self._expected_token):
            return None
        return self._principal

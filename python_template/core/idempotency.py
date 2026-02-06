from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from python_template.core.exceptions import ValidationError


@dataclass(frozen=True)
class IdempotencyRecord:
    request_hash: str
    status_code: int
    payload: dict[str, Any]


class IdempotencyStore:
    def __init__(self):
        self._records: dict[str, IdempotencyRecord] = {}

    def _record_key(self, scope: str, idempotency_key: str) -> str:
        return f"{scope}:{idempotency_key}"

    def fetch(self, scope: str, idempotency_key: str) -> IdempotencyRecord | None:
        return self._records.get(self._record_key(scope, idempotency_key))

    def fetch_or_validate(
        self,
        scope: str,
        idempotency_key: str,
        request_hash: str,
    ) -> IdempotencyRecord | None:
        record = self.fetch(scope=scope, idempotency_key=idempotency_key)
        if record is None:
            return None
        if record.request_hash != request_hash:
            raise ValidationError(
                "idempotency_key already used with a different payload",
                code="IDEMPOTENCY_KEY_REUSED",
            )
        return record

    def save(
        self,
        scope: str,
        idempotency_key: str,
        request_hash: str,
        status_code: int,
        payload: dict[str, Any],
    ) -> None:
        record = IdempotencyRecord(
            request_hash=request_hash,
            status_code=status_code,
            payload=payload,
        )
        self._records[self._record_key(scope, idempotency_key)] = record

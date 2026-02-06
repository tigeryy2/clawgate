from __future__ import annotations

import uuid
from datetime import UTC, datetime

from python_template.core.exceptions import NotFoundError, ValidationError
from python_template.core.models import ApprovalTicket


class ApprovalStore:
    def __init__(self):
        self._tickets: dict[str, ApprovalTicket] = {}
        self._updated_at: dict[str, datetime] = {}

    def create_ticket(
        self,
        summary: str,
        proposed_effect: dict,
        capability_id: str,
        fingerprint: str,
    ) -> ApprovalTicket:
        ticket_id = f"appr_{uuid.uuid4().hex[:12]}"
        ticket = ApprovalTicket(
            id=ticket_id,
            status="pending",
            summary=summary,
            proposed_effect=proposed_effect,
            fingerprint=fingerprint,
            capability_id=capability_id,
        )
        self._tickets[ticket_id] = ticket
        self._updated_at[ticket_id] = datetime.now(UTC)
        return ticket

    def get(self, ticket_id: str) -> ApprovalTicket:
        ticket = self._tickets.get(ticket_id)
        if ticket is None:
            raise NotFoundError(f"approval ticket '{ticket_id}' not found")
        return ticket

    def set_status(self, ticket_id: str, status: str) -> ApprovalTicket:
        if status not in {"approved", "denied"}:
            raise ValidationError("status must be 'approved' or 'denied'")
        ticket = self.get(ticket_id)
        if ticket.status == status:
            return ticket
        if ticket.status != "pending":
            raise ValidationError(
                f"ticket '{ticket_id}' already finalized as '{ticket.status}'",
                code="APPROVAL_ALREADY_FINALIZED",
            )
        updated = ticket.model_copy(update={"status": status})
        self._tickets[ticket_id] = updated
        self._updated_at[ticket_id] = datetime.now(UTC)
        return updated

    def find_for_fingerprint(
        self,
        capability_id: str,
        fingerprint: str,
        statuses: set[str],
    ) -> ApprovalTicket | None:
        for ticket in self._tickets.values():
            if ticket.capability_id != capability_id:
                continue
            if ticket.fingerprint != fingerprint:
                continue
            if ticket.status not in statuses:
                continue
            return ticket
        return None

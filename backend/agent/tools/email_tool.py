"""Agent-facing email tools."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.models.email import EmailDraft, EmailSummary, SendResult
from backend.services.email_service import EmailService


async def draft_email(session: Session, to: str, subject: str, body_instruction: str) -> EmailDraft:
    """Create an email draft without sending it."""

    return await EmailService(session).draft_email(to, subject, body_instruction)


async def send_email(session: Session, draft_id: str, confirmed: bool) -> SendResult:
    """Send a previously drafted email after confirmation."""

    return await EmailService(session).send_email(draft_id, confirmed)


async def read_recent_emails(session: Session, n: int = 10) -> list[EmailSummary]:
    """Return draft-backed email summaries for the current V1 implementation."""

    drafts = await EmailService(session).list_drafts()
    return [
        EmailSummary(
            subject=draft.subject,
            from_addr="draft-system",
            snippet=draft.body[:120],
            received_at=draft.created_at,
        )
        for draft in drafts[:n]
    ]

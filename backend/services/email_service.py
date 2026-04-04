"""Email application service."""

from __future__ import annotations

from datetime import datetime, timezone

import aiosmtplib
from email.message import EmailMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db.repositories import EmailDraftRepository
from backend.db.models import EmailDraftRecord
from backend.models.email import EmailDraft, SendResult


class UnconfirmedSendError(ValueError):
    """Raised when a send action is attempted without confirmation."""


def _to_draft(record: EmailDraftRecord) -> EmailDraft:
    return EmailDraft(
        id=record.id,
        to=record.to_addr,
        subject=record.subject,
        body=record.body,
        created_at=record.created_at,
        status=record.status,
    )


class EmailService:
    """Draft and send emails with explicit confirmation."""

    def __init__(self, session: Session):
        self.session = session
        self.settings = get_settings()
        self.repository = EmailDraftRepository(session)

    async def draft_email(self, to: str, subject: str, body_instruction: str) -> EmailDraft:
        body = f"Dear recipient,\n\n{body_instruction}\n\nBest regards,\nSUSTech Student"
        record = self.repository.create(to_addr=to, subject=subject, body=body)
        return _to_draft(record)

    async def list_drafts(self) -> list[EmailDraft]:
        result = self.session.execute(select(EmailDraftRecord).order_by(EmailDraftRecord.created_at.desc()))
        return [_to_draft(record) for record in result.scalars()]

    async def send_email(self, draft_id: str, confirmed: bool) -> SendResult:
        if not confirmed:
            raise UnconfirmedSendError("Email sending requires explicit user confirmation.")

        draft = self.repository.get(draft_id)
        if not draft:
            return SendResult(draft_id=draft_id, status="blocked", detail="Draft not found.")
        if draft.status == "sent":
            return SendResult(draft_id=draft_id, status="sent", detail="Draft was already sent.")

        message = EmailMessage()
        message["From"] = self.settings.smtp_user
        message["To"] = draft.to_addr
        message["Subject"] = draft.subject
        message.set_content(draft.body)

        await aiosmtplib.send(
            message,
            hostname=self.settings.smtp_host,
            port=self.settings.smtp_port,
            start_tls=True,
            username=self.settings.smtp_user,
            password=self.settings.smtp_password,
        )
        self.repository.update_status(
            draft_id,
            status="sent",
            sent_at=datetime.now(timezone.utc),
        )
        return SendResult(draft_id=draft_id, status="sent", detail="Email sent.")

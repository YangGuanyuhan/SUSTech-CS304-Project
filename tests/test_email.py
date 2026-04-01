import pytest

from backend.services.email_service import EmailService, UnconfirmedSendError


async def test_unconfirmed_email_never_sends(db_session, mocker):
    service = EmailService(db_session)
    draft = await service.draft_email("teacher@example.com", "Question", "Need an extension.")
    sender = mocker.patch("backend.services.email_service.aiosmtplib.send")

    with pytest.raises(UnconfirmedSendError):
        await service.send_email(draft.id, confirmed=False)

    sender.assert_not_called()


async def test_confirmed_email_sends(db_session, mocker):
    service = EmailService(db_session)
    draft = await service.draft_email("teacher@example.com", "Question", "Need an extension.")
    sender = mocker.patch("backend.services.email_service.aiosmtplib.send")

    result = await service.send_email(draft.id, confirmed=True)
    assert result.status == "sent"
    sender.assert_called_once()

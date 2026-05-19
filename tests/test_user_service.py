from __future__ import annotations

import pytest

from backend.services.user_service import AuthenticationError, UserService


def test_default_user_login_and_profile_update(db_session):
    service = UserService(db_session)
    service.ensure_default_user()

    result = service.login("local", "studyai")
    assert result.profile.username == "local"

    updated = service.update_profile(result.token, display_name="张同学")
    assert updated.display_name == "张同学"


def test_login_rejects_wrong_password(db_session):
    service = UserService(db_session)
    service.ensure_default_user()

    with pytest.raises(AuthenticationError):
        service.login("local", "wrong")


def test_logout_invalidates_token(db_session):
    service = UserService(db_session)
    service.ensure_default_user()
    result = service.login("local", "studyai")

    service.logout(result.token)

    with pytest.raises(AuthenticationError):
        service.profile_for_token(result.token)

"""Local user authentication and profile management."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from backend.db.repositories import UserProfileRepository
from backend.models.user import LoginResult, UserProfile

DEFAULT_USERNAME = "local"
DEFAULT_PASSWORD = "studyai"
AVATAR_DIR = Path("data/avatars")
MAX_AVATAR_BYTES = 2 * 1024 * 1024
ALLOWED_AVATAR_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

_ACTIVE_TOKENS: dict[str, str] = {}


class AuthenticationError(ValueError):
    """Raised when local authentication fails."""


class AvatarUploadError(ValueError):
    """Raised when an avatar upload is invalid."""


def _hash_password(password: str, salt: str | None = None) -> str:
    actual_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), actual_salt.encode(), 120_000)
    return f"pbkdf2_sha256${actual_salt}${digest.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, salt, expected = stored_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    candidate = _hash_password(password, salt).split("$", 2)[2]
    return hmac.compare_digest(candidate, expected)


def _avatar_url(avatar_path: str | None) -> str | None:
    if not avatar_path:
        return None
    return f"/api/user/avatar/{Path(avatar_path).name}"


def _to_profile(record) -> UserProfile:
    return UserProfile(
        id=record.id,
        username=record.username,
        display_name=record.display_name,
        avatar_url=_avatar_url(record.avatar_path),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


class UserService:
    """Service for the local default user."""

    def __init__(self, session: Session):
        self.session = session
        self.repository = UserProfileRepository(session)

    def ensure_default_user(self):
        record = self.repository.get_by_username(DEFAULT_USERNAME)
        if record is not None:
            return record
        return self.repository.create(
            username=DEFAULT_USERNAME,
            display_name="用户",
            password_hash=_hash_password(DEFAULT_PASSWORD),
        )

    def login(self, username: str, password: str) -> LoginResult:
        record = self.repository.get_by_username(username.strip())
        if record is None or not _verify_password(password, record.password_hash):
            raise AuthenticationError("用户名或密码错误")
        token = secrets.token_urlsafe(32)
        _ACTIVE_TOKENS[token] = record.id
        return LoginResult(token=token, profile=_to_profile(record))

    def logout(self, token: str) -> None:
        _ACTIVE_TOKENS.pop(token, None)

    def profile_for_token(self, token: str) -> UserProfile:
        user_id = _ACTIVE_TOKENS.get(token)
        if not user_id:
            raise AuthenticationError("登录已失效")
        record = self.repository.get(user_id)
        if record is None:
            _ACTIVE_TOKENS.pop(token, None)
            raise AuthenticationError("用户不存在")
        return _to_profile(record)

    def update_profile(self, token: str, *, display_name: str) -> UserProfile:
        user_id = _ACTIVE_TOKENS.get(token)
        if not user_id:
            raise AuthenticationError("登录已失效")
        cleaned = display_name.strip()
        if not cleaned:
            raise ValueError("昵称不能为空")
        if len(cleaned) > 100:
            raise ValueError("昵称不能超过 100 个字符")
        record = self.repository.update_profile(user_id, display_name=cleaned)
        if record is None:
            raise AuthenticationError("用户不存在")
        return _to_profile(record)

    async def save_avatar(self, token: str, upload: UploadFile) -> UserProfile:
        user_id = _ACTIVE_TOKENS.get(token)
        if not user_id:
            raise AuthenticationError("登录已失效")

        suffix = ALLOWED_AVATAR_TYPES.get(upload.content_type or "")
        if suffix is None:
            raise AvatarUploadError("头像必须是 JPEG、PNG、WEBP 或 GIF 图片")

        content = await upload.read()
        if not content:
            raise AvatarUploadError("头像文件不能为空")
        if len(content) > MAX_AVATAR_BYTES:
            raise AvatarUploadError("头像不能超过 2MB")

        AVATAR_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"{user_id}-{uuid4().hex}{suffix}"
        path = AVATAR_DIR / filename
        path.write_bytes(content)

        record = self.repository.update_profile(user_id, avatar_path=str(path))
        if record is None:
            raise AuthenticationError("用户不存在")
        return _to_profile(record)

    @staticmethod
    def avatar_path(filename: str) -> Path:
        safe_name = Path(filename).name
        path = AVATAR_DIR / safe_name
        if not path.is_file():
            raise FileNotFoundError(filename)
        return path

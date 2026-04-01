"""Local encrypted secret storage for development profiles."""

from __future__ import annotations

from pathlib import Path

from cryptography.fernet import Fernet


class SecretStore:
    """Encrypt small secrets at rest using a local machine key file."""

    def __init__(self, key_path: str = "data/profile-secrets.key") -> None:
        self.key_path = Path(key_path)
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        if self.key_path.exists():
            self._fernet = Fernet(self.key_path.read_bytes())
        else:
            key = Fernet.generate_key()
            self.key_path.write_bytes(key)
            self.key_path.chmod(0o600)
            self._fernet = Fernet(key)

    def encrypt(self, secret: str) -> str:
        return self._fernet.encrypt(secret.encode("utf-8")).decode("utf-8")

    def decrypt(self, token: str) -> str:
        return self._fernet.decrypt(token.encode("utf-8")).decode("utf-8")


secret_store = SecretStore()

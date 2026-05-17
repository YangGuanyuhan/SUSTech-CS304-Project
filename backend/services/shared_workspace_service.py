"""Shared workspace path handling for Docker-safe local file access."""

from __future__ import annotations

from pathlib import Path

from backend.config import get_settings


class SharedWorkspaceError(ValueError):
    """Raised when a requested path escapes the shared workspace."""


class SharedWorkspaceService:
    """Resolve and validate paths under the configured shared workspace root."""

    def __init__(self, root: str | None = None):
        self._configured_root = root

    def root(self) -> Path:
        raw_root = self._configured_root or get_settings().shared_workspace_dir
        root = Path(raw_root).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        return root.resolve(strict=True)

    def resolve_workspace_root(self, workspace_root: str | None = None) -> Path:
        root = self.root()
        if not workspace_root or not str(workspace_root).strip():
            return root
        candidate = self.resolve_path(workspace_root, base=root)
        if not candidate.is_dir():
            raise SharedWorkspaceError(f"Workspace directory `{workspace_root}` is not a directory.")
        return candidate

    def resolve_path(self, requested_path: str | None, *, base: Path | None = None) -> Path:
        root = self.root()
        current_base = base.resolve(strict=True) if base else root
        self.ensure_inside(current_base)
        text = str(requested_path or ".").strip() or "."
        raw = Path(text).expanduser()
        candidate = raw.resolve() if raw.is_absolute() else (current_base / raw).resolve()
        self.ensure_inside(candidate)
        return candidate

    def ensure_inside(self, path: Path) -> None:
        root = self.root()
        try:
            path.resolve().relative_to(root)
        except ValueError as exc:
            raise SharedWorkspaceError("Requested path is outside the shared workspace.") from exc

    def relative_path(self, path: Path) -> str:
        root = self.root()
        try:
            relative = path.resolve().relative_to(root)
        except ValueError as exc:
            raise SharedWorkspaceError("Requested path is outside the shared workspace.") from exc
        return "." if str(relative) == "." else relative.as_posix()

    def directory_payload(self, path: str | None = None) -> dict[str, object]:
        current = self.resolve_path(path)
        if not current.exists():
            raise SharedWorkspaceError(f"Directory not found: {path or self.root()}")
        if not current.is_dir():
            raise SharedWorkspaceError(f"Path is not a directory: {self.relative_path(current)}")

        entries: list[dict[str, str]] = []
        try:
            for child in current.iterdir():
                try:
                    resolved = child.resolve(strict=True)
                except OSError:
                    continue
                try:
                    self.ensure_inside(resolved)
                except SharedWorkspaceError:
                    continue
                if resolved.is_dir():
                    entries.append(
                        {
                            "name": child.name,
                            "path": str(resolved),
                            "relative_path": self.relative_path(resolved),
                        }
                    )
        except PermissionError as exc:
            raise SharedWorkspaceError(
                f"Permission denied: {self.relative_path(current)}"
            ) from exc

        entries.sort(key=lambda item: item["name"].lower())
        root = self.root()
        parent = current.parent if current != root else None
        return {
            "root": str(root),
            "path": str(current),
            "relative_path": self.relative_path(current),
            "display_path": self.relative_path(current),
            "parent": str(parent) if parent else None,
            "shortcuts": [{"name": "Shared", "path": str(root)}],
            "roots": [],
            "entries": entries,
        }

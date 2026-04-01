"""Agent-facing file manager tools."""

from __future__ import annotations

from backend.models.task import FileSummary, Quiz, RenamePreview, RenameResult
from backend.services.file_service import FileService


def batch_rename(directory: str, pattern: str, dry_run: bool = True) -> RenamePreview | RenameResult:
    """Preview or execute a batch rename operation.

    Args:
        directory: Target directory containing files.
        pattern: Python format string using index, stem, and suffix.
        dry_run: When True, only return a preview.

    Returns:
        A preview when dry_run=True or the plan is invalid, otherwise the execution result.
    """

    return FileService().batch_rename(directory, pattern, dry_run)


def summarize_file(file_path: str) -> FileSummary:
    """Summarize a local file into key study notes."""

    return FileService().summarize_file(file_path)


def generate_quiz(file_path: str, n_questions: int = 5) -> Quiz:
    """Generate a quiz from a local file."""

    return FileService().generate_quiz(file_path, n_questions)

"""File management service."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

try:
    from markitdown import MarkItDown
except ImportError:  # pragma: no cover - optional at test time
    MarkItDown = None

from backend.models.task import (
    FileSummary,
    Quiz,
    QuizQuestion,
    RenameOperation,
    RenamePreview,
    RenameResult,
)


INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')


class FileService:
    """Local file automation service."""

    def batch_rename(self, directory: str, pattern: str, dry_run: bool = True) -> RenamePreview | RenameResult:
        base = Path(directory)
        files = sorted(path for path in base.iterdir() if path.is_file())
        operations: list[RenameOperation] = []
        generated_names: set[str] = set()

        for index, file_path in enumerate(files, start=1):
            new_name = pattern.format(index=index, stem=file_path.stem, suffix=file_path.suffix.lstrip("."))
            conflict = False
            reason = None
            if INVALID_FILENAME_CHARS.search(new_name):
                conflict = True
                reason = "Filename contains invalid characters."
            elif new_name in generated_names:
                conflict = True
                reason = "Renaming rule generates duplicate filenames."
            generated_names.add(new_name)
            operations.append(
                RenameOperation(
                    original_name=file_path.name,
                    new_name=new_name,
                    conflict=conflict,
                    reason=reason,
                )
            )

        valid = all(not operation.conflict for operation in operations)
        if dry_run or not valid:
            return RenamePreview(directory=directory, operations=operations, valid=valid)

        renamed_count = 0
        for operation in operations:
            source = base / operation.original_name
            target = base / operation.new_name
            source.rename(target)
            renamed_count += 1
        return RenameResult(directory=directory, renamed_count=renamed_count, operations=operations)

    def summarize_file(self, file_path: str) -> FileSummary:
        path = Path(file_path)
        text = path.read_text(encoding="utf-8", errors="ignore")
        if MarkItDown is not None and path.suffix.lower() != ".md":
            try:
                result = MarkItDown().convert(file_path)
                text = result.text_content or text
            except Exception:
                pass
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        summary = " ".join(lines[:3])[:400] if lines else "No content available."
        return FileSummary(file_path=file_path, summary=summary, key_points=lines[:5])

    def generate_quiz(self, file_path: str, n_questions: int = 5) -> Quiz:
        summary = self.summarize_file(file_path)
        questions = []
        key_points = summary.key_points or [summary.summary]
        for index in range(n_questions):
            focus = key_points[index % len(key_points)]
            questions.append(
                QuizQuestion(
                    question=f"What is the best summary of point {index + 1} from the source material?",
                    options=[
                        focus,
                        "This point is not discussed.",
                        "The source only contains images.",
                        "The source rejects this idea entirely.",
                    ],
                    answer=focus,
                    explanation="The correct answer is taken directly from the extracted source summary.",
                )
            )
        return Quiz(source_file=file_path, questions=questions, generated_at=datetime.now(timezone.utc))

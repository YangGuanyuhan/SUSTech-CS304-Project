"""Discovery and safe reading for agent skills."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class SkillMetadata(BaseModel):
    name: str
    description: str
    path: str
    scope: str
    enabled: bool = True
    allow_implicit_invocation: bool = True
    has_openai_metadata: bool = False
    error: str | None = None


class SkillReadResult(BaseModel):
    metadata: SkillMetadata
    content: str
    truncated: bool = False


class SkillServiceError(ValueError):
    """Raised when a skill request is invalid or unsafe."""


class SkillService:
    """Discover Codex-style skills and read their files safely."""

    MAX_SKILL_CONTENT_CHARS = 50_000

    def __init__(self, workspace_root: str | None = None):
        self.workspace_root = Path(workspace_root).expanduser().resolve() if workspace_root else None

    def discover(self) -> list[SkillMetadata]:
        skills: list[SkillMetadata] = []
        seen: set[tuple[str, str]] = set()
        for root, scope in self._candidate_skill_roots():
            if not root.exists() or not root.is_dir():
                continue
            for skill_dir in sorted(item for item in root.iterdir() if item.is_dir()):
                metadata = self._read_metadata(skill_dir, scope)
                key = (metadata.name, metadata.path)
                if key not in seen:
                    skills.append(metadata)
                    seen.add(key)
        return skills

    def build_metadata_prompt(self, max_chars: int = 8000) -> str:
        skills = [skill for skill in self.discover() if skill.enabled]
        if not skills:
            return "No agent skills are currently available."

        lines = [
            "Available agent skills:",
            "Use a skill when the user explicitly mentions `$skill-name` or when the task matches the description. "
            "Call read_skill before following a skill's full instructions.",
        ]
        omitted = 0
        for skill in skills:
            suffix = " implicit=false" if not skill.allow_implicit_invocation else ""
            line = (
                f"- ${skill.name}: {skill.description} "
                f"(scope={skill.scope}, path={skill.path}{suffix})"
            )
            if len("\n".join([*lines, line])) > max_chars:
                omitted += 1
                continue
            lines.append(line)
        if omitted:
            lines.append(f"... {omitted} additional skills omitted by context budget.")
        return "\n".join(lines)

    def read_skill(self, name: str, max_chars: int | None = None) -> SkillReadResult:
        metadata = self._find_skill(name)
        return self._read_skill_file(metadata, "SKILL.md", max_chars=max_chars)

    def read_resource(
        self,
        name: str,
        relative_path: str,
        *,
        max_chars: int | None = None,
    ) -> SkillReadResult:
        metadata = self._find_skill(name)
        return self._read_skill_file(metadata, relative_path, max_chars=max_chars)

    def _candidate_skill_roots(self) -> list[tuple[Path, str]]:
        roots: list[tuple[Path, str]] = []
        for base in self._repo_chain(Path.cwd()):
            roots.append((base / ".agents" / "skills", "repo"))
        if self.workspace_root:
            for base in self._repo_chain(self.workspace_root):
                roots.append((base / ".agents" / "skills", "workspace"))
        home = Path(os.environ.get("HOME", "~")).expanduser()
        roots.append((home / ".agents" / "skills", "user"))

        deduped: list[tuple[Path, str]] = []
        seen: set[Path] = set()
        for root, scope in roots:
            resolved = root.expanduser().resolve()
            if resolved not in seen:
                deduped.append((resolved, scope))
                seen.add(resolved)
        return deduped

    def _repo_chain(self, start: Path) -> list[Path]:
        resolved = start.expanduser().resolve()
        if resolved.is_file():
            resolved = resolved.parent
        chain = [resolved]
        current = resolved
        while current.parent != current:
            current = current.parent
            chain.append(current)
            if (current / ".git").exists():
                break
        return chain

    def _read_metadata(self, skill_dir: Path, scope: str) -> SkillMetadata:
        skill_file = skill_dir / "SKILL.md"
        path = skill_file.as_posix()
        if not skill_file.is_file():
            return SkillMetadata(
                name=skill_dir.name,
                description="",
                path=path,
                scope=scope,
                enabled=False,
                error="Missing SKILL.md",
            )
        try:
            frontmatter = self._parse_frontmatter(skill_file)
            name = str(frontmatter.get("name") or "").strip()
            description = str(frontmatter.get("description") or "").strip()
            if not name or not description:
                raise SkillServiceError("SKILL.md frontmatter must include name and description.")
            allow_implicit = self._allow_implicit_invocation(skill_dir)
            return SkillMetadata(
                name=name,
                description=description,
                path=path,
                scope=scope,
                allow_implicit_invocation=allow_implicit,
                has_openai_metadata=(skill_dir / "agents" / "openai.yaml").is_file(),
            )
        except Exception as exc:
            return SkillMetadata(
                name=skill_dir.name,
                description="",
                path=path,
                scope=scope,
                enabled=False,
                error=str(exc),
            )

    def _find_skill(self, name: str) -> SkillMetadata:
        normalized = name.strip().removeprefix("$")
        for skill in self.discover():
            if skill.name == normalized and skill.enabled:
                return skill
        raise SkillServiceError(f"Skill `{name}` was not found.")

    def _read_skill_file(
        self,
        metadata: SkillMetadata,
        relative_path: str,
        *,
        max_chars: int | None,
    ) -> SkillReadResult:
        skill_file = Path(metadata.path).resolve()
        skill_dir = skill_file.parent
        target = (skill_dir / relative_path).resolve()
        try:
            target.relative_to(skill_dir)
        except ValueError as exc:
            raise SkillServiceError("Requested skill resource is outside the skill directory.") from exc
        if not target.is_file():
            raise SkillServiceError(f"Skill resource `{relative_path}` was not found.")
        limit = max_chars or self.MAX_SKILL_CONTENT_CHARS
        content = target.read_text(encoding="utf-8", errors="ignore")
        return SkillReadResult(
            metadata=metadata,
            content=content[:limit],
            truncated=len(content) > limit,
        )

    def _parse_frontmatter(self, skill_file: Path) -> dict[str, Any]:
        text = skill_file.read_text(encoding="utf-8", errors="ignore")
        if not text.startswith("---\n"):
            raise SkillServiceError("SKILL.md must start with YAML frontmatter.")
        try:
            _, raw_yaml, _ = text.split("---", 2)
        except ValueError as exc:
            raise SkillServiceError("SKILL.md frontmatter is not closed.") from exc
        parsed = yaml.safe_load(raw_yaml) or {}
        if not isinstance(parsed, dict):
            raise SkillServiceError("SKILL.md frontmatter must be a YAML mapping.")
        return parsed

    def _allow_implicit_invocation(self, skill_dir: Path) -> bool:
        metadata_file = skill_dir / "agents" / "openai.yaml"
        if not metadata_file.is_file():
            return True
        try:
            parsed = yaml.safe_load(metadata_file.read_text(encoding="utf-8")) or {}
        except Exception:
            return True
        policy = parsed.get("policy") if isinstance(parsed, dict) else None
        if not isinstance(policy, dict):
            return True
        return bool(policy.get("allow_implicit_invocation", True))

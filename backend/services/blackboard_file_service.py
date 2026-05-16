"""Blackboard file management service - async file tree and download."""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass, field

try:
    import aiofiles
    import aiohttp
except ImportError:
    aiohttp = None
    aiofiles = None


@dataclass
class BBFile:
    """Represents a downloadable file in Blackboard."""

    id: str
    file_name: str
    download_url: str
    parent_content: BBContent | None = None


@dataclass
class BBContent:
    """Represents a Blackboard content node (course, folder, document, file)."""

    id: str
    title: str
    type: str  # x-bb-course / x-bb-folder / x-bb-document / x-bb-file
    course_id: str
    has_children: bool = False
    children: list[BBContent] = field(default_factory=list)
    attachments: list[BBFile] = field(default_factory=list)
    parent_node: BBContent | None = None
    is_loaded: bool = False
    _load_event: object = field(default=None, repr=False, compare=False)

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "course_id": self.course_id,
            "has_children": self.has_children,
            "is_loaded": self.is_loaded,
            "children": [c.to_dict() for c in self.children],
            "attachments": [
                {
                    "id": a.id,
                    "file_name": a.file_name,
                    "download_url": a.download_url,
                }
                for a in self.attachments
            ],
        }


class BBFileManager:
    """Async Blackboard file manager with concurrent downloads."""

    BASE_URL = "https://bb.sustech.edu.cn/learn/api/public/v1"

    def __init__(self, cookies: dict, download_root: str = "./BB_Files"):
        if aiohttp is None or aiofiles is None:
            raise RuntimeError(
                "aiohttp and aiofiles are required. Install with: pip install aiohttp aiofiles"
            )

        self.cookies = cookies
        self.download_root = download_root
        self._session: aiohttp.ClientSession | None = None
        self._dl_sem = asyncio.Semaphore(10)  # Max 10 concurrent downloads
        self._api_sem = asyncio.Semaphore(20)  # Max 20 concurrent API requests
        os.makedirs(self.download_root, exist_ok=True)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(limit=50, limit_per_host=25)
            self._session = aiohttp.ClientSession(
                cookies=self.cookies,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                connector=connector,
            )
        return self._session

    async def close(self):
        """Close aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    @staticmethod
    def sanitize_path(name: str) -> str:
        """Sanitize filename/dirname."""
        return re.sub(r'[\\/:*?"<>|]', "_", str(name)).strip()

    def get_full_path(self, node: BBContent) -> str:
        """Get full filesystem path for a content node."""
        segments: list[str] = []
        curr: BBContent | None = node
        while curr:
            segments.insert(0, self.sanitize_path(curr.title))
            curr = curr.parent_node
        return os.path.join(self.download_root, *segments)

    async def _get_json(self, url: str) -> dict:
        """Make async HTTP GET request and return JSON."""
        session = await self._get_session()
        async with self._api_sem:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                r.raise_for_status()
                return await r.json()

    async def fetch_all_courses(self) -> list[BBContent]:
        """Fetch list of all courses for current user."""
        try:
            data = await self._get_json(f"{self.BASE_URL}/users/me/courses?expand=course")
            nodes = []
            for item in data.get("results", []):
                c_id = item.get("courseId")
                c_name = item.get("course", {}).get("name", "Unknown Course")
                nodes.append(
                    BBContent(
                        id=c_id,
                        title=c_name,
                        type="x-bb-course",
                        course_id=c_id,
                        has_children=True,
                    )
                )
            return nodes
        except Exception as e:
            print(f"[ERR] Failed to fetch courses: {e}")
            return []

    async def fetch_node_children(self, node: BBContent):
        """
        Fetch children and attachments for a node.
        Idempotent: if already loaded, returns immediately.
        Concurrent calls wait for first load to complete.
        """
        # Create Event on first call
        if node._load_event is None:
            node._load_event = asyncio.Event()
        elif node.is_loaded:
            return
        else:
            # Other coroutines are loading, wait for completion
            await node._load_event.wait()
            return

        try:
            # Blackboard can report children under document/lesson-like nodes too,
            # so follow has_children instead of only folder nodes.
            if node.type == "x-bb-course" or node.has_children:
                if node.type == "x-bb-course":
                    url = f"{self.BASE_URL}/courses/{node.course_id}/contents"
                else:
                    url = f"{self.BASE_URL}/courses/{node.course_id}/contents/{node.id}/children"
                try:
                    data = await self._get_json(url)
                    for item in data.get("results", []):
                        handler = item.get("contentHandler", {}).get("id", "")
                        ctype = handler.rsplit("/", 1)[-1] if handler else "unknown"
                        child = BBContent(
                            id=item["id"],
                            title=item["title"],
                            type=ctype,
                            course_id=node.course_id,
                            has_children=item.get("hasChildren", False),
                            parent_node=node,
                        )
                        node.children.append(child)
                except Exception as e:
                    print(f"[WARN] Failed to fetch children ({node.title}): {e}")

            # Fetch attachments for content-like nodes. Lessons and some unknown
            # handler types can still expose attachments. Folders usually return
            # 400 and are skipped to avoid unnecessary probes.
            if node.type not in {"x-bb-course", "x-bb-folder"}:
                attach_url = (
                    f"{self.BASE_URL}/courses/{node.course_id}/contents/{node.id}/attachments"
                )
                try:
                    data = await self._get_json(attach_url)
                    for a in data.get("results", []):
                        f = BBFile(
                            id=a["id"],
                            file_name=a["fileName"],
                            download_url=(
                                f"{self.BASE_URL}/courses/{node.course_id}"
                                f"/contents/{node.id}/attachments/{a['id']}/download"
                            ),
                            parent_content=node,
                        )
                        node.attachments.append(f)
                except aiohttp.ClientResponseError as e:
                    # Some nodes report attachment-capable handler but expose no attachment API.
                    if e.status != 400:
                        print(f"[WARN] Failed to fetch attachments ({node.title}): {e}")
                except Exception as e:
                    print(f"[WARN] Failed to fetch attachments ({node.title}): {e}")

        finally:
            node.is_loaded = True
            node._load_event.set()

    async def download_recursive(self, node: BBContent) -> dict:
        """
        Recursively download node and all its children.
        Returns download statistics.
        """
        await self.fetch_node_children(node)

        tasks = []
        stats = {"files_downloaded": 0, "files_skipped": 0, "errors": 0}

        # Download attachments for current node
        if node.attachments:
            target_dir = self.get_full_path(node)
            os.makedirs(target_dir, exist_ok=True)
            for attach in node.attachments:
                save_path = os.path.join(target_dir, self.sanitize_path(attach.file_name))
                tasks.append(self._execute_download(attach.download_url, save_path))

        # Recursively handle children
        for child in node.children:
            tasks.append(self.download_recursive(child))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, dict):
                    stats["files_downloaded"] += result.get("files_downloaded", 0)
                    stats["files_skipped"] += result.get("files_skipped", 0)
                    stats["errors"] += result.get("errors", 0)
                elif isinstance(result, Exception):
                    stats["errors"] += 1

        return stats

    async def download_single(self, f: BBFile) -> dict:
        """Download a single file."""
        target_dir = self.get_full_path(f.parent_content)
        os.makedirs(target_dir, exist_ok=True)
        save_path = os.path.join(target_dir, self.sanitize_path(f.file_name))
        return await self._execute_download(f.download_url, save_path)

    async def _execute_download(self, url: str, save_path: str) -> dict:
        """Execute actual file download with temporary file handling."""
        if os.path.exists(save_path):
            return {"files_downloaded": 0, "files_skipped": 1, "errors": 0}

        tmp_path = save_path + ".tmp"
        session = await self._get_session()
        async with self._dl_sem:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=120)) as r:
                    r.raise_for_status()
                    async with aiofiles.open(tmp_path, "wb") as fp:
                        async for chunk in r.content.iter_chunked(256 * 1024):
                            await fp.write(chunk)
                os.replace(tmp_path, save_path)
                print(f"[OK] {os.path.basename(save_path)}")
                return {"files_downloaded": 1, "files_skipped": 0, "errors": 0}
            except Exception as e:
                print(f"[ERR] {e} | {save_path}")
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                return {"files_downloaded": 0, "files_skipped": 0, "errors": 1}


# Singleton instance for service use
_bb_file_manager: BBFileManager | None = None


def get_bb_file_manager(cookies: dict) -> BBFileManager:
    """Get or create Blackboard file manager instance."""
    global _bb_file_manager
    if _bb_file_manager is None:
        _bb_file_manager = BBFileManager(cookies)
    return _bb_file_manager

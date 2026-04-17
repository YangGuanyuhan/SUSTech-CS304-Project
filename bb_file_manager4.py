"""
Blackboard 极速下载器 —— 异步版
依赖: pip install aiohttp aiofiles beautifulsoup4
"""

import asyncio
import os
import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from dataclasses import dataclass, field
from typing import List, Optional

import aiohttp
import aiofiles
from bs4 import BeautifulSoup

# ─────────────────────────────────────────
# 1. 数据结构
# ─────────────────────────────────────────

@dataclass
class BBFile:
    id: str
    file_name: str
    download_url: str
    parent_content: "BBContent" = None


@dataclass
class BBContent:
    id: str
    title: str
    type: str           # x-bb-course / x-bb-folder / x-bb-document / x-bb-file
    course_id: str
    has_children: bool = False
    children: List["BBContent"] = field(default_factory=list)
    attachments: List[BBFile] = field(default_factory=list)
    parent_node: Optional["BBContent"] = None
    is_loaded: bool = False
    _load_event: object = field(default=None, repr=False, compare=False)


# ─────────────────────────────────────────
# 2. 异步管理器
# ─────────────────────────────────────────

class BBManager:
    BASE_URL = "https://bb.sustech.edu.cn/learn/api/public/v1"

    def __init__(self, cookies: dict, download_root: str = "./BB_Files"):
        self.cookies = cookies          # 从同步登录拿到的 cookie dict
        self.download_root = download_root
        self._session: Optional[aiohttp.ClientSession] = None
        self._dl_sem = asyncio.Semaphore(10)   # 最多 10 并发下载
        self._api_sem = asyncio.Semaphore(20)  # 最多 20 并发 API 请求
        os.makedirs(self.download_root, exist_ok=True)

    # ── session 管理 ──────────────────────

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(limit=50, limit_per_host=25)
            self._session = aiohttp.ClientSession(
                cookies=self.cookies,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                connector=connector,
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    # ── 工具 ──────────────────────────────

    @staticmethod
    def sanitize_path(name: str) -> str:
        return re.sub(r'[\\/:*?"<>|]', "_", str(name)).strip()

    def get_full_path(self, node: BBContent) -> str:
        segments: list[str] = []
        curr: Optional[BBContent] = node
        while curr:
            segments.insert(0, self.sanitize_path(curr.title))
            curr = curr.parent_node
        return os.path.join(self.download_root, *segments)

    # ── API 请求 ──────────────────────────

    async def _get_json(self, url: str) -> dict:
        session = await self._get_session()
        async with self._api_sem:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                r.raise_for_status()
                return await r.json()

    async def fetch_all_courses(self) -> List[BBContent]:
        try:
            data = await self._get_json(f"{self.BASE_URL}/users/me/courses?expand=course")
            nodes = []
            for item in data.get("results", []):
                c_id = item.get("courseId")
                c_name = item.get("course", {}).get("name", "Unknown Course")
                nodes.append(
                    BBContent(id=c_id, title=c_name, type="x-bb-course",
                              course_id=c_id, has_children=True)
                )
            return nodes
        except Exception as e:
            print(f"[ERR] 获取课程列表失败: {e}")
            return []

    async def fetch_node_children(self, node: BBContent):
        """
        幂等：若已加载则直接返回；并发调用时等待首次加载完成。
        用 asyncio.Event 替代线程锁，纯异步安全。
        """
        # 首次调用时创建 Event
        if node._load_event is None:
            node._load_event = asyncio.Event()
        elif node.is_loaded:
            return
        else:
            # 其他协程正在加载，等待完成
            await node._load_event.wait()
            return

        try:
            # ── 子内容 ──
            if node.type in ("x-bb-course", "x-bb-folder"):
                if node.type == "x-bb-course":
                    url = f"{self.BASE_URL}/courses/{node.course_id}/contents"
                else:
                    url = (f"{self.BASE_URL}/courses/{node.course_id}"
                           f"/contents/{node.id}/children")
                try:
                    data = await self._get_json(url)
                    for item in data.get("results", []):
                        handler = item.get("contentHandler", {}).get("id", "")
                        ctype = handler.split("/")[-1] if "/" in handler else "unknown"
                        child = BBContent(
                            id=item["id"], title=item["title"], type=ctype,
                            course_id=node.course_id,
                            has_children=item.get("hasChildren", False),
                            parent_node=node,
                        )
                        node.children.append(child)
                except Exception as e:
                    print(f"[WARN] 拉取子项失败 ({node.title}): {e}")

            # ── 附件 ──
            if node.type in ("x-bb-document", "x-bb-file", "x-bb-assignment", "x-bb-lesson"):
                attach_url = (f"{self.BASE_URL}/courses/{node.course_id}"
                              f"/contents/{node.id}/attachments")
                try:
                    data = await self._get_json(attach_url)
                    for a in data.get("results", []):
                        f = BBFile(
                            id=a["id"], file_name=a["fileName"],
                            download_url=(
                                f"{self.BASE_URL}/courses/{node.course_id}"
                                f"/contents/{node.id}/attachments/{a['id']}/download"
                            ),
                            parent_content=node,
                        )
                        node.attachments.append(f)
                except Exception as e:
                    print(f"[WARN] 拉取附件失败 ({node.title}): {e}")

        finally:
            node.is_loaded = True
            node._load_event.set()

    # ── 下载 ─────────────────────────────

    async def download_recursive(self, node: BBContent):
        """递归下载节点及其所有子节点，全程异步并发。"""
        await self.fetch_node_children(node)

        tasks = []

        # 下载当前节点的附件
        if node.attachments:
            target_dir = self.get_full_path(node)
            os.makedirs(target_dir, exist_ok=True)
            for attach in node.attachments:
                save_path = os.path.join(target_dir, self.sanitize_path(attach.file_name))
                tasks.append(self._execute_download(attach.download_url, save_path))

        # 递归子节点
        for child in node.children:
            tasks.append(self.download_recursive(child))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def download_single(self, f: BBFile):
        """下载单个附件（GUI 双击 BBFile 时使用）。"""
        target_dir = self.get_full_path(f.parent_content)
        os.makedirs(target_dir, exist_ok=True)
        save_path = os.path.join(target_dir, self.sanitize_path(f.file_name))
        await self._execute_download(f.download_url, save_path)

    async def _execute_download(self, url: str, save_path: str):
        if os.path.exists(save_path):
            return
        tmp_path = save_path + ".tmp"
        session = await self._get_session()
        async with self._dl_sem:
            try:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=120)
                ) as r:
                    r.raise_for_status()
                    async with aiofiles.open(tmp_path, "wb") as fp:
                        async for chunk in r.content.iter_chunked(256 * 1024):
                            await fp.write(chunk)
                os.replace(tmp_path, save_path)
                print(f"[OK] {os.path.basename(save_path)}")
            except Exception as e:
                print(f"[ERR] {e} | {save_path}")
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)


# ─────────────────────────────────────────
# 3. 异步事件循环桥接器
# ─────────────────────────────────────────

class AsyncBridge:
    """
    在后台线程中运行独立的 asyncio 事件循环，
    供 tkinter 主线程安全地提交协程。
    """

    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def submit(self, coro, done_callback=None):
        """把协程提交到后台 loop，可选完成回调（在后台线程执行）。"""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        if done_callback:
            future.add_done_callback(lambda f: done_callback(f))
        return future

    def stop(self):
        self._loop.call_soon_threadsafe(self._loop.stop)


# ─────────────────────────────────────────
# 4. GUI
# ─────────────────────────────────────────

class BBBrowserGUI:
    def __init__(self, manager: BBManager, bridge: AsyncBridge):
        self.manager = manager
        self.bridge = bridge

        self.root = tk.Tk()
        self.root.title("Blackboard 极速下载器（异步版）")
        self.root.geometry("1100x750")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.status_var = tk.StringVar(value="正在加载课程列表…")
        tk.Label(self.root, textvariable=self.status_var,
                 anchor="w", relief=tk.SUNKEN, bd=1).pack(side=tk.BOTTOM, fill=tk.X)

        self.tree = ttk.Treeview(self.root)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.tree.heading("#0", text="资源目录（展开即加载 | 双击下载）", anchor="w")

        self.node_map: dict = {}
        self._expanding: set = set()

        self.tree.bind("<<TreeviewOpen>>", self._on_expand)
        self.tree.bind("<Double-1>", self._on_double_click)

    # ── 启动 ──────────────────────────────

    def start(self):
        self.bridge.submit(
            self.manager.fetch_all_courses(),
            done_callback=lambda f: self.root.after(0, lambda: self._render_courses(f.result()))
        )
        self.root.mainloop()

    # ── 关闭 ──────────────────────────────

    def _on_close(self):
        self.bridge.submit(self.manager.close())
        self.root.after(200, self.root.destroy)
        self.bridge.stop()

    # ── 渲染课程列表 ─────────────────────

    def _render_courses(self, courses: List[BBContent]):
        for c in courses:
            iid = self.tree.insert("", "end", text=f"🎓 {c.title}", open=False)
            self.node_map[iid] = c
            self.tree.insert(iid, "end", text="⏳ 加载中…")
        self.status_var.set(f"共 {len(courses)} 门课程，展开即可加载内容。")

    # ── 展开节点 ──────────────────────────

    def _on_expand(self, _event):
        iid = self.tree.focus()
        node = self.node_map.get(iid)
        if not isinstance(node, BBContent):
            return
        if node.is_loaded or iid in self._expanding:
            return

        self._expanding.add(iid)
        self.status_var.set(f"正在加载：{node.title}…")

        self.bridge.submit(
            self.manager.fetch_node_children(node),
            done_callback=lambda _: self.root.after(0, lambda: self._render_children(iid, node))
        )

    def _render_children(self, iid: str, node: BBContent):
        for child_ui in self.tree.get_children(iid):
            self.tree.delete(child_ui)

        for child in node.children:
            icon = "📁" if child.type == "x-bb-folder" else "📄"
            sub_iid = self.tree.insert(iid, "end", text=f"{icon} {child.title}")
            self.node_map[sub_iid] = child
            if child.has_children or child.type in ("x-bb-document", "x-bb-file"):
                self.tree.insert(sub_iid, "end", text="⏳ 加载中…")

        for f in node.attachments:
            f_iid = self.tree.insert(iid, "end", text=f"📎 {f.file_name}")
            self.node_map[f_iid] = f

        self._expanding.discard(iid)
        count = len(node.children) + len(node.attachments)
        self.status_var.set(f"已加载：{node.title}（{count} 项）")

    # ── 双击下载 ──────────────────────────

    def _on_double_click(self, _event):
        selection = self.tree.selection()
        if not selection:
            return
        iid = selection[0]
        obj = self.node_map.get(iid)

        if isinstance(obj, BBContent):
            self.status_var.set(f"后台下载中：{obj.title}…")
            self.bridge.submit(self.manager.download_recursive(obj))
            messagebox.showinfo("下载已开始",
                                f"正在后台异步递归下载「{obj.title}」，\n请查看终端输出了解进度。")

        elif isinstance(obj, BBFile):
            self.bridge.submit(self.manager.download_single(obj))
            messagebox.showinfo("已加入队列", f"「{obj.file_name}」已加入下载队列。")


# ─────────────────────────────────────────
# 5. 异步登录
# ─────────────────────────────────────────

async def login_async(username: str, password: str) -> Optional[dict]:
    """
    用 aiohttp 完成 CAS 登录，返回 cookie dict 供后续 BBManager 复用。
    实际只需执行一次，在入口处用 asyncio.run() 驱动。
    """
    timeout = aiohttp.ClientTimeout(total=15)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    # aiohttp 默认不跟随跨域重定向时保留 cookie，
    # 用 allow_redirects=False 手动处理以确保 CAS ticket 正确传递。
    connector = aiohttp.TCPConnector(ssl=False)  # 校园网自签证书常见，可按需改为 True
    async with aiohttp.ClientSession(
        headers=headers, connector=connector,
        cookie_jar=aiohttp.CookieJar()
    ) as session:
        try:
            # Step 1: 访问 BB 首页，可能被重定向到 CAS
            async with session.get(
                "https://bb.sustech.edu.cn/", timeout=timeout
            ) as res:
                final_url = str(res.url)
                html = await res.text()

            # Step 2: 若落在 CAS，解析 execution 并 POST 凭据
            if "cas.sustech.edu.cn" in final_url:
                soup = BeautifulSoup(html, "html.parser")
                execution_tag = soup.find("input", {"name": "execution"})
                if not execution_tag:
                    print("[ERR] 未找到 CAS execution 字段，页面结构可能已变化。")
                    return None
                execution = execution_tag["value"]

                async with session.post(
                    final_url,
                    data={
                        "username": username,
                        "password": password,
                        "execution": execution,
                        "_eventId": "submit",
                    },
                    timeout=timeout,
                ) as res:
                    final_url = str(res.url)

            # Step 3: 校验是否已离开 CAS（即登录成功）
            if "cas.sustech.edu.cn" in final_url:
                return None

            # 提取所有 cookie 返回给调用方
            cookies = {
                c.key: c.value
                for c in session.cookie_jar
            }
            return cookies

        except Exception as e:
            print(f"[ERR] 登录网络错误: {e}")
            return None


# ─────────────────────────────────────────
# 6. 入口
# ─────────────────────────────────────────

if __name__ == "__main__":
    u = input("BB Username: ")
    p = input("BB Password: ")

    print("正在登录…")
    # 登录只需跑一次，用 asyncio.run() 在主线程同步等待结果，
    # 之后 tkinter 接管主线程，异步任务交给 AsyncBridge 的后台 loop。
    cookies = asyncio.run(login_async(u, p))
    if not cookies:
        print("登录失败，请检查账号或网络。")
        raise SystemExit(1)

    print("登录成功，启动界面…")
    bridge = AsyncBridge()
    manager = BBManager(cookies=cookies)
    gui = BBBrowserGUI(manager=manager, bridge=bridge)
    gui.start()
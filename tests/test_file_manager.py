from backend.services.blackboard_file_service import BBContent, BBFileManager
from backend.services.file_service import FileService


def test_batch_rename_detects_conflicts(tmp_path):
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")

    result = FileService().batch_rename(str(tmp_path), "same.txt", dry_run=True)
    assert result.valid is False
    assert any(operation.conflict for operation in result.operations)


def test_batch_rename_executes(tmp_path):
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    result = FileService().batch_rename(str(tmp_path), "renamed-{index}.txt", dry_run=False)
    assert result.renamed_count == 1
    assert (tmp_path / "renamed-1.txt").exists()


async def test_blackboard_manager_loads_children_below_document_nodes(monkeypatch):
    manager = BBFileManager({})

    async def fake_get_json(url: str):
        if url.endswith("/contents/doc9/children"):
            return {
                "results": [
                    {
                        "id": "file-node",
                        "title": "Lab 9 handout",
                        "contentHandler": {"id": "resource/x-bb-file"},
                        "hasChildren": False,
                    }
                ]
            }
        if url.endswith("/contents/doc9/attachments"):
            return {"results": []}
        if url.endswith("/contents/file-node/attachments"):
            return {"results": [{"id": "att-1", "fileName": "handout.pdf"}]}
        raise AssertionError(f"unexpected Blackboard URL: {url}")

    monkeypatch.setattr(manager, "_get_json", fake_get_json)

    node = BBContent(
        id="doc9",
        title="Lab 9",
        type="x-bb-document",
        course_id="_101_1",
        has_children=True,
    )

    await manager.fetch_node_children(node)
    await manager.fetch_node_children(node.children[0])

    assert node.children[0].type == "x-bb-file"
    assert node.children[0].attachments[0].file_name == "handout.pdf"

    await manager.close()


async def test_blackboard_manager_loads_lesson_attachments(monkeypatch):
    manager = BBFileManager({})

    async def fake_get_json(url: str):
        if url.endswith("/contents/lesson9/attachments"):
            return {"results": [{"id": "att-lesson", "fileName": "lesson.zip"}]}
        raise AssertionError(f"unexpected Blackboard URL: {url}")

    monkeypatch.setattr(manager, "_get_json", fake_get_json)

    node = BBContent(
        id="lesson9",
        title="Lab 9 lesson",
        type="x-bb-lesson",
        course_id="_101_1",
        has_children=False,
    )

    await manager.fetch_node_children(node)

    assert node.attachments[0].id == "att-lesson"
    assert node.attachments[0].file_name == "lesson.zip"

    await manager.close()

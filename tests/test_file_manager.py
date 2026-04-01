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

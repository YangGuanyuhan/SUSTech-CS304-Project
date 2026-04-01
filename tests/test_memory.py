from backend.services.memory_service import MemoryService


async def test_save_and_query_memory(db_session):
    service = MemoryService(db_session)
    saved = await service.save_memory("assignment", {"course": "CS305"}, "blackboard", ["deadline"])
    assert saved.key == "assignment"

    relevant = await service.get_relevant_memories("deadline blackboard")
    assert len(relevant) == 1
    assert relevant[0].id == saved.id


async def test_delete_memories_by_query(db_session):
    service = MemoryService(db_session)
    await service.save_memory("os-lab", {"status": "todo"}, "task", ["lab"])
    deleted = await service.delete_memories_by_query("delete lab")
    assert deleted == 1

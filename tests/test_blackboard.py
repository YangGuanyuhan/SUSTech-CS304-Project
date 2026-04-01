from backend.services.blackboard_service import BlackboardService, MockBlackboardProvider


async def test_blackboard_courses_are_returned(db_session):
    service = BlackboardService(db_session, MockBlackboardProvider())
    result = await service.get_all_courses()
    assert result.is_cached is False
    assert len(result.data) >= 1


async def test_blackboard_uses_cache_on_failure(db_session):
    service = BlackboardService(db_session, MockBlackboardProvider())
    await service.get_all_courses()

    class FailingProvider(MockBlackboardProvider):
        async def get_all_courses(self):
            raise RuntimeError("down")

    failing = BlackboardService(db_session, FailingProvider())
    result = await failing.get_all_courses()
    assert result.is_cached is True
    assert result.warning is not None

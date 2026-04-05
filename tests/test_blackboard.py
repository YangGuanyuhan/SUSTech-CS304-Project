from backend.services.blackboard_service import BlackboardService, DemoBlackboardProvider


async def test_blackboard_courses_are_returned(db_session, monkeypatch):
    from backend.services import blackboard_service

    class Settings:
        blackboard_base_url = "https://bb.sustech.edu.cn/learn/api/public/v1"
        blackboard_student_id = "123456"
        blackboard_cas_password = "secret"

    class FakeCoursesResponse:
        status_code = 200
        ok = True

        def json(self):
            return {
                "results": [
                    {
                        "courseId": "_101_1",
                        "course": {"courseId": "CS304-2026", "name": "Software Engineering"},
                    },
                    {
                        "courseId": "_102_1",
                        "course": {"courseId": "CS305-2026", "name": "Operating Systems"},
                    },
                ]
            }

    class FakeSession:
        def __init__(self):
            self.headers = {}

        def get(self, *_args, **_kwargs):
            return FakeCoursesResponse()

    monkeypatch.setattr(blackboard_service, "get_settings", lambda: Settings())
    provider = DemoBlackboardProvider()
    provider._cas_session = FakeSession()

    service = BlackboardService(db_session, provider)
    result = await service.get_all_courses()

    assert result.is_cached is False
    assert len(result.data) == 2
    assert result.data[0].course_id == "_101_1"
    assert result.data[0].blackboard_course_id == "CS304-2026"
    assert result.data[0].name == "Software Engineering"


async def test_blackboard_uses_cache_on_failure(db_session):
    service = BlackboardService(db_session, DemoBlackboardProvider())
    await service.get_all_courses()

    class FailingProvider(DemoBlackboardProvider):
        async def get_all_courses(self):
            raise RuntimeError("down")

    failing = BlackboardService(db_session, FailingProvider())
    result = await failing.get_all_courses()
    assert result.is_cached is True
    assert result.warning is not None


async def test_bypass_cas_login_returns_false_without_credentials(monkeypatch):
    from backend.services import blackboard_service

    class Settings:
        blackboard_student_id = None
        blackboard_cas_password = None

    monkeypatch.setattr(blackboard_service, "get_settings", lambda: Settings())
    provider = DemoBlackboardProvider()

    result = await provider.bypass_cas_login()

    assert result is False


async def test_bypass_cas_login_returns_false_on_timeout(monkeypatch):
    from backend.services import blackboard_service

    class Settings:
        blackboard_student_id = "123456"
        blackboard_cas_password = "secret"

    class TimeoutSession:
        def __init__(self):
            self.headers = {}

        def get(self, *_args, **_kwargs):
            raise blackboard_service.requests.Timeout()

    monkeypatch.setattr(blackboard_service, "get_settings", lambda: Settings())
    monkeypatch.setattr(blackboard_service.requests, "Session", TimeoutSession)
    provider = DemoBlackboardProvider()

    result = await provider.bypass_cas_login()

    assert result is False


async def test_bypass_cas_login_returns_true_on_success(monkeypatch):
    from backend.services import blackboard_service

    class Settings:
        blackboard_student_id = "123456"
        blackboard_cas_password = "secret"

    class FakeResponse:
        def __init__(self, url: str, text: str = ""):
            self.url = url
            self.text = text

    class SuccessSession:
        def __init__(self):
            self.headers = {}

        def get(self, *_args, **_kwargs):
            return FakeResponse(
                "https://cas.sustech.edu.cn/cas/login",
                '<input name="execution" value="e1s1"/>',
            )

        def post(self, *_args, **_kwargs):
            return FakeResponse("https://bb.sustech.edu.cn/webapps/portal/execute/tabs/tabAction")

    monkeypatch.setattr(blackboard_service, "get_settings", lambda: Settings())
    monkeypatch.setattr(blackboard_service.requests, "Session", SuccessSession)
    provider = DemoBlackboardProvider()

    result = await provider.bypass_cas_login()

    assert result is True
    assert provider._cas_session is not None

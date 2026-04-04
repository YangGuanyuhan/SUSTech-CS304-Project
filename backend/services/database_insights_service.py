"""Database-level summary service used by API and debugging UI."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.db.repositories import DatabaseAnalyticsRepository
from backend.models.database import DatabaseOverview


class DatabaseInsightsService:
    """Expose operational database insights in a frontend-friendly shape."""

    def __init__(self, session: Session):
        self.repository = DatabaseAnalyticsRepository(session)

    async def get_overview(self) -> DatabaseOverview:
        return DatabaseOverview.model_validate(self.repository.overview())

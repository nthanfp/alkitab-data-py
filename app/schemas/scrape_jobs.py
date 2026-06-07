from datetime import datetime

from pydantic import BaseModel


class ScrapeJobRead(BaseModel):
    id: int
    book_id: int
    chapter_no: int
    status: str
    verses_count: int | None
    error: str | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class ScrapeJobList(BaseModel):
    data: list[ScrapeJobRead]

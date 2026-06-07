from pydantic import BaseModel


class ScrapeChapterRequest(BaseModel):
    book_abbr: str
    chapter: int


class ScrapeResponse(BaseModel):
    status: str
    message: str
    chapter_id: int | None = None

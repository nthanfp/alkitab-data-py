from pydantic import BaseModel


class ChapterRead(BaseModel):
    id: int
    book_id: int
    chapter_no: int
    title: str | None
    source_url: str | None

    model_config = {"from_attributes": True}


class ChapterList(BaseModel):
    data: list[ChapterRead]

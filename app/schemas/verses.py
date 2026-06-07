from pydantic import BaseModel


class VerseRead(BaseModel):
    id: int
    chapter_id: int
    verse_no: int
    title: str | None
    text: str | None

    model_config = {"from_attributes": True}


class VerseList(BaseModel):
    data: list[VerseRead]

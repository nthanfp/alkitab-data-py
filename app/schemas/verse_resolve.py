from pydantic import BaseModel


class ResolveResult(BaseModel):
    book_id: int
    book_abbr: str
    book_name: str
    chapter: int
    start_verse: int
    end_verse: int | None
    text: str | None

    model_config = {"from_attributes": True}


class ResolveVerseRequest(BaseModel):
    text: str


class ResolveVerseResponse(BaseModel):
    query: str
    results: list[ResolveResult]

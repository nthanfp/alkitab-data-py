from pydantic import BaseModel


class VerseSearchResult(BaseModel):
    id: int
    verse_no: int
    text: str | None
    book_id: int
    book_abbr: str
    book_name: str
    chapter_no: int


class VerseSearchResults(BaseModel):
    data: list[VerseSearchResult]
    total: int
    query: str

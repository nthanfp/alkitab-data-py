from pydantic import BaseModel, field_validator


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

    @field_validator("text", mode="before")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        if v:
            v = v.replace("\r\n", " ").replace("\n", " ")
            v = " ".join(v.split())
        return v


class ResolveVerseResponse(BaseModel):
    query: str
    results: list[ResolveResult]

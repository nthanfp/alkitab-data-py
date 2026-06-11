from pydantic import BaseModel, field_validator


class GenerateImageRequest(BaseModel):
    text: str

    @field_validator("text", mode="before")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        if v:
            v = v.replace("\r\n", " ").replace("\n", " ")
            v = " ".join(v.split())
        return v


class GenerateImageResponse(BaseModel):
    status: str
    verse_reference: str
    book: str
    chapter: int
    verse: int
    image_path: str

from pydantic import BaseModel


class GenerateImageRequest(BaseModel):
    text: str


class GenerateImageResponse(BaseModel):
    status: str
    verse_reference: str
    book: str
    chapter: int
    verse: int
    image_path: str

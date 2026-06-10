from pydantic import BaseModel


class ImageTextRequest(BaseModel):
    book: str
    chapter: int
    verse: int
    output: str


class ImageTextResponse(BaseModel):
    status: str
    message: str
    output_path: str

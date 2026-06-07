from pydantic import BaseModel


class BookRead(BaseModel):
    id: int
    abbr: str
    name: str
    chapter_count: int
    order_no: int

    model_config = {"from_attributes": True}


class BookList(BaseModel):
    data: list[BookRead]

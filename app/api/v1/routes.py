from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.books import Book
from app.models.chapters import Chapter
from app.models.verses import Verse
from app.schemas.books import BookList, BookRead
from app.schemas.chapters import ChapterList, ChapterRead
from app.schemas.verses import VerseList, VerseRead
from app.schemas.scrape import ScrapeChapterRequest, ScrapeResponse
from app.services.scraper import scrape_chapter

router = APIRouter()


@router.get("/ping")
async def ping():
    return {"message": "pong"}


@router.get("/books", response_model=BookList)
async def list_books(db: Session = Depends(get_db)):
    books = db.query(Book).order_by(Book.order_no).all()
    return BookList(data=books)


@router.get("/books/{book_id}", response_model=BookRead)
async def get_book(book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@router.get("/books/{book_id}/chapters", response_model=ChapterList)
async def list_book_chapters(book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    chapters = db.query(Chapter).filter(Chapter.book_id == book_id).order_by(Chapter.chapter_no).all()
    return ChapterList(data=chapters)


@router.get("/chapters/{chapter_id}/verses", response_model=VerseList)
async def list_chapter_verses(chapter_id: int, db: Session = Depends(get_db)):
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    verses = db.query(Verse).filter(Verse.chapter_id == chapter_id).order_by(Verse.verse_no).all()
    return VerseList(data=verses)


@router.post("/scrape/chapter", response_model=ScrapeResponse)
async def scrape_single_chapter(req: ScrapeChapterRequest, db: Session = Depends(get_db)):
    try:
        chapter_obj = await scrape_chapter(db, req.book_abbr, req.chapter)
        return ScrapeResponse(
            status="ok",
            message=f"Scraped {req.book_abbr} {req.chapter}",
            chapter_id=chapter_obj.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scrape failed: {e}")


@router.post("/scrape/book/{book_id}", response_model=ScrapeResponse)
async def scrape_all_book_chapters(book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    scraped = 0
    for ch in range(1, book.chapter_count + 1):
        try:
            await scrape_chapter(db, book.abbr, ch)
            scraped += 1
        except Exception:
            continue

    return ScrapeResponse(
        status="ok",
        message=f"Scraped {book.name} ({scraped}/{book.chapter_count} chapters)",
    )

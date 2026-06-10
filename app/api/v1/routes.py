from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.books import Book
from app.models.chapters import Chapter
from app.models.verses import Verse
from app.models.scrape_jobs import ScrapeJob
from app.schemas.books import BookList, BookRead
from app.schemas.chapters import ChapterList, ChapterRead
from app.schemas.verses import VerseList, VerseRead
from app.schemas.scrape import ScrapeChapterRequest, ScrapeResponse
from app.schemas.scrape_jobs import ScrapeJobList
from app.schemas.search import VerseSearchResult, VerseSearchResults
from app.schemas.verse_resolve import ResolveVerseRequest, ResolveVerseResponse
from app.services.scraper import scrape_chapter
from app.services.verse_resolver import resolve_verse

router = APIRouter()


@router.get("/ping", tags=["Health"])
async def ping():
    """Health check endpoint."""
    return {"message": "pong"}


@router.get("/search/books", tags=["Search"], summary="Cari kitab Alkitab")
async def search_books(q: str = "", db: Session = Depends(get_db)):
    """Cari kitab berdasarkan nama atau singkatan."""
    if not q:
        return {"data": []}
    qs = f"%{q}%"
    books = (
        db.query(Book)
        .filter(Book.name.ilike(qs) | Book.abbr.ilike(qs))
        .order_by(Book.order_no)
        .all()
    )
    return {"data": books, "total": len(books), "query": q}


@router.get("/search/verses", response_model=VerseSearchResults, tags=["Search"], summary="Cari ayat Alkitab")
async def search_verses(q: str = "", limit: int = 50, db: Session = Depends(get_db)):
    """Cari ayat berdasarkan teks (partial match)."""
    if not q:
        return VerseSearchResults(data=[], total=0, query=q)
    qs = f"%{q}%"
    results = (
        db.query(Verse, Chapter, Book)
        .select_from(Verse)
        .join(Chapter, Verse.chapter_id == Chapter.id)
        .join(Book, Chapter.book_id == Book.id)
        .filter(Verse.text.ilike(qs))
        .order_by(Book.order_no, Chapter.chapter_no, Verse.verse_no)
        .limit(limit)
        .all()
    )
    data = [
        VerseSearchResult(
            id=v.id,
            verse_no=v.verse_no,
            text=v.text,
            book_id=b.id,
            book_abbr=b.abbr,
            book_name=b.name,
            chapter_no=ch.chapter_no,
        )
        for v, ch, b in results
    ]
    return VerseSearchResults(data=data, total=len(data), query=q)


@router.get("/scrape-jobs", response_model=ScrapeJobList, tags=["Scrape"], summary="Riwayat scrape")
async def list_scrape_jobs(db: Session = Depends(get_db)):
    """Lihat riwayat scraping job."""
    jobs = db.query(ScrapeJob).order_by(ScrapeJob.created_at.desc()).all()
    return ScrapeJobList(data=jobs)


@router.get("/books", response_model=BookList, tags=["Books"], summary="Daftar kitab")
async def list_books(db: Session = Depends(get_db)):
    """Daftar semua 66 kitab Alkitab."""
    books = db.query(Book).order_by(Book.order_no).all()
    return BookList(data=books)


@router.get("/books/{book_id}", response_model=BookRead, tags=["Books"], summary="Detail kitab")
async def get_book(book_id: int, db: Session = Depends(get_db)):
    """Detail kitab berdasarkan ID."""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@router.get("/books/{book_id}/chapters", response_model=ChapterList, tags=["Books"], summary="Daftar pasal")
async def list_book_chapters(book_id: int, db: Session = Depends(get_db)):
    """Daftar semua pasal dalam kitab."""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    chapters = db.query(Chapter).filter(Chapter.book_id == book_id).order_by(Chapter.chapter_no).all()
    return ChapterList(data=chapters)


@router.get("/chapters/{chapter_id}/verses", response_model=VerseList, tags=["Chapters"], summary="Daftar ayat")
async def list_chapter_verses(chapter_id: int, db: Session = Depends(get_db)):
    """Daftar semua ayat dalam pasal."""
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    verses = db.query(Verse).filter(Verse.chapter_id == chapter_id).order_by(Verse.verse_no).all()
    return VerseList(data=verses)


@router.post("/scrape/chapter", response_model=ScrapeResponse, tags=["Scrape"], summary="Scrape 1 pasal")
async def scrape_single_chapter(req: ScrapeChapterRequest, db: Session = Depends(get_db)):
    """Scrape 1 pasal dari alkitab.sabda.org."""
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


@router.post("/scrape/book/{book_id}", response_model=ScrapeResponse, tags=["Scrape"], summary="Scrape seluruh pasal")
async def scrape_all_book_chapters(book_id: int, db: Session = Depends(get_db)):
    """Scrape semua pasal dalam kitab."""
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


@router.post("/resolve-verse", response_model=ResolveVerseResponse, tags=["Resolve"], summary="Resolve referensi ayat")
async def resolve(req: ResolveVerseRequest, db: Session = Depends(get_db)):
    """Resolve teks ayat ke referensi Alkitab (book, chapter, verse) menggunakan LLM BLIP-Text.

    Contoh input:
    - "Yesaya 54:10"
    - "Sebab biarpun gunung-gunung beranjak... Yesaya 54:10"
    """
    results = await resolve_verse(req.text, db)
    return ResolveVerseResponse(query=req.text, results=results)

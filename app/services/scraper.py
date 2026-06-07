from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from urllib.parse import quote

import httpx
from sqlalchemy.orm import Session

from app.models.books import Book
from app.models.chapters import Chapter
from app.models.scrape_jobs import ScrapeJob
from app.models.verses import Verse

BASE_URL = "https://alkitab.sabda.org/api/passage.php"


async def scrape_chapter(db: Session, book_abbr: str, chapter: int) -> Chapter:
    book = db.query(Book).filter(Book.abbr == book_abbr).first()
    if not book:
        raise ValueError(f"Book '{book_abbr}' not found")

    job = ScrapeJob(book_id=book.id, chapter_no=chapter, status="running")
    db.add(job)
    db.flush()

    try:
        passage = f"{book.name.lower()} {chapter}"
        url = f"{BASE_URL}?passage={quote(passage)}"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        root = ET.fromstring(resp.text)

        existing = db.query(Chapter).filter(
            Chapter.book_id == book.id,
            Chapter.chapter_no == chapter,
        ).first()

        if existing:
            chapter_obj = existing
            db.query(Verse).filter(Verse.chapter_id == chapter_obj.id).delete()
        else:
            chapter_obj = Chapter(book_id=book.id, chapter_no=chapter, source_url=url)
            db.add(chapter_obj)
            db.flush()

        chapter_el = root.find(".//chapter")
        if chapter_el is not None:
            title_el = chapter_el.find("title")
            if title_el is not None and title_el.text:
                chapter_obj.title = title_el.text.strip()

        verses_count = 0
        for verse_el in root.findall(".//verse"):
            num_el = verse_el.find("number")
            text_el = verse_el.find("text")
            title_el = verse_el.find("title")

            if num_el is None or text_el is None:
                continue

            verse_no = int(num_el.text)
            verse_text = text_el.text or ""
            verse_title = title_el.text.strip() if title_el is not None and title_el.text else None

            db.add(Verse(
                chapter_id=chapter_obj.id,
                verse_no=verse_no,
                title=verse_title,
                text=verse_text.strip(),
            ))
            verses_count += 1

        job.status = "success"
        job.verses_count = verses_count
        db.commit()
        db.refresh(chapter_obj)
        return chapter_obj
    except Exception as exc:
        db.rollback()
        failed_job = ScrapeJob(book_id=book.id, chapter_no=chapter, status="failed", error=str(exc))
        db.add(failed_job)
        db.commit()
        raise

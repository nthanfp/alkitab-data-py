from sqlalchemy.orm import Session

from app.models.books import Book
from app.models.chapters import Chapter
from app.models.verses import Verse
from app.services.llm import extract_references


async def resolve_verse(text: str, db: Session) -> list[dict]:
    refs = await extract_references(text)

    results = []
    for ref in refs[:3]:
        book_name = ref.get("book", "")
        chapter_no = ref.get("chapter")
        verse_no = ref.get("verse")
        end_verse = ref.get("end_verse")

        if not book_name or chapter_no is None or verse_no is None:
            continue

        if end_verse and end_verse > verse_no:
            rows = (
                db.query(Verse, Chapter, Book)
                .select_from(Verse)
                .join(Chapter, Verse.chapter_id == Chapter.id)
                .join(Book, Chapter.book_id == Book.id)
                .filter(
                    Book.name.ilike(book_name),
                    Chapter.chapter_no == chapter_no,
                    Verse.verse_no >= verse_no,
                    Verse.verse_no <= end_verse,
                )
                .order_by(Verse.verse_no)
                .all()
            )
            if rows:
                v, ch, b = rows[0]
                combined_text = "\n".join(r[0].text or "" for r in rows)
                results.append({
                    "book_id": b.id,
                    "book_abbr": b.abbr,
                    "book_name": b.name,
                    "chapter": ch.chapter_no,
                    "start_verse": verse_no,
                    "end_verse": end_verse,
                    "text": combined_text,
                })
        else:
            row = (
                db.query(Verse, Chapter, Book)
                .select_from(Verse)
                .join(Chapter, Verse.chapter_id == Chapter.id)
                .join(Book, Chapter.book_id == Book.id)
                .filter(
                    Book.name.ilike(book_name),
                    Chapter.chapter_no == chapter_no,
                    Verse.verse_no == verse_no,
                )
                .first()
            )
            if row:
                v, ch, b = row
                results.append({
                    "book_id": b.id,
                    "book_abbr": b.abbr,
                    "book_name": b.name,
                    "chapter": ch.chapter_no,
                    "start_verse": v.verse_no,
                    "end_verse": None,
                    "text": v.text,
                })

    if not results:
        snippet = text[:80].strip()
        rows = (
            db.query(Verse, Chapter, Book)
            .select_from(Verse)
            .join(Chapter, Verse.chapter_id == Chapter.id)
            .join(Book, Chapter.book_id == Book.id)
            .filter(Verse.text.ilike(f"%{snippet}%"))
            .order_by(Book.order_no, Chapter.chapter_no, Verse.verse_no)
            .limit(3)
            .all()
        )
        for v, ch, b in rows:
            results.append({
                "book_id": b.id,
                "book_abbr": b.abbr,
                "book_name": b.name,
                "chapter": ch.chapter_no,
                "verse": v.verse_no,
                "text": v.text,
            })

    return results

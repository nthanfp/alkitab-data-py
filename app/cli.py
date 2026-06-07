import asyncio

import typer
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.books import Book
from app.services.scraper import scrape_chapter

app = typer.Typer(help="Alkitab scraper CLI")
scrape_app = typer.Typer(help="Scrape commands")
app.add_typer(scrape_app, name="scrape")


async def _scrape_all(db: Session):
    books = db.query(Book).order_by(Book.order_no).all()
    total = 0
    for book in books:
        for chapter_no in range(1, book.chapter_count + 1):
            await scrape_chapter(db, book.abbr, chapter_no)
            total += 1
            typer.echo(f"OK {book.abbr} {chapter_no}")
    return total


@scrape_app.command("all")
def scrape_all():
    db = SessionLocal()
    try:
        total = asyncio.run(_scrape_all(db))
        typer.echo(f"Done {total} chapters")
    finally:
        db.close()


@scrape_app.command("book")
def scrape_book(book_id: int = typer.Option(..., "--id")):
    db = SessionLocal()
    try:
        book = db.query(Book).filter(Book.id == book_id).first()
        if not book:
            raise typer.BadParameter("Book not found")

        async def _scrape():
            total = 0
            for chapter_no in range(1, book.chapter_count + 1):
                await scrape_chapter(db, book.abbr, chapter_no)
                total += 1
                typer.echo(f"OK {book.abbr} {chapter_no}")
            return total

        total = asyncio.run(_scrape())
        typer.echo(f"Done {book.name} {total} chapters")
    finally:
        db.close()


@scrape_app.command("chapter")
def scrape_single(book_abbr: str = typer.Option(..., "--book-abbr"), chapter: int = typer.Option(..., "--chapter")):
    async def _scrape():
        db = SessionLocal()
        try:
            await scrape_chapter(db, book_abbr, chapter)
            typer.echo(f"OK {book_abbr} {chapter}")
        finally:
            db.close()

    asyncio.run(_scrape())


if __name__ == "__main__":
    app()

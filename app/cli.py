import asyncio
from typing import Optional

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, engine
from app.models.books import Book
from app.services.scraper import fetch_chapter_xml, save_chapter, scrape_chapter

app = typer.Typer(help="Alkitab scraper CLI")
scrape_app = typer.Typer(help="Scrape commands")
app.add_typer(scrape_app, name="scrape")

DEFAULT_CONCURRENT = 5


def _enable_wal():
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        conn.exec_driver_sql("PRAGMA busy_timeout=5000")
        conn.commit()


def _get_chapters(db: Session, book_id: Optional[int] = None) -> list[tuple[str, int, str]]:
    if book_id:
        books = db.query(Book).filter(Book.id == book_id).all()
    else:
        books = db.query(Book).order_by(Book.order_no).all()

    chapters = []
    for book in books:
        for ch in range(1, book.chapter_count + 1):
            chapters.append((book.abbr, ch, book.name))
    return chapters


async def _run_concurrent(jobs: list[tuple[str, int, str]], concurrent: int, desc: str):
    _enable_wal()
    db_lock = asyncio.Lock()
    queue: asyncio.Queue = asyncio.Queue()
    total = len(jobs)

    async def worker(abbr, chapter, book_name):
        try:
            url, root = await fetch_chapter_xml(book_name, chapter)
            async with db_lock:
                db = SessionLocal()
                try:
                    save_chapter(db, abbr, chapter, url, root)
                    await queue.put(("ok", abbr, chapter, None))
                finally:
                    db.close()
        except Exception as e:
            await queue.put(("fail", abbr, chapter, str(e)))

    async def consumer(progress, task_id):
        done = 0
        while done < total:
            status, abbr, chapter, error = await queue.get()
            done += 1
            if status == "ok":
                progress.update(task_id, advance=1, description=f"{desc} {done}/{total}")
            else:
                progress.update(task_id, advance=1, description=f"[red]FAIL {abbr} {chapter} ({done}/{total})")

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        task_id = progress.add_task(f"{desc} 0/{total}", total=total)
        consumer_task = asyncio.create_task(consumer(progress, task_id))
        semaphore = asyncio.Semaphore(concurrent)

        async def limited(abbr, chapter, book_name):
            async with semaphore:
                await worker(abbr, chapter, book_name)

        await asyncio.gather(*[limited(a, c, n) for a, c, n in jobs])
        await consumer_task


@scrape_app.command("all")
def scrape_all(concurrent: int = typer.Option(DEFAULT_CONCURRENT, "--concurrent", "-c")):
    db = SessionLocal()
    try:
        jobs = _get_chapters(db)
    finally:
        db.close()

    typer.echo(f"Scraping {len(jobs)} chapters (concurrent={concurrent})")
    asyncio.run(_run_concurrent(jobs, concurrent, "All books"))
    typer.echo("Done.")


@scrape_app.command("book")
def scrape_book(book_id: int = typer.Option(..., "--id"), concurrent: int = typer.Option(DEFAULT_CONCURRENT, "--concurrent", "-c")):
    db = SessionLocal()
    try:
        book = db.query(Book).filter(Book.id == book_id).first()
        if not book:
            raise typer.BadParameter("Book not found")
        jobs = _get_chapters(db, book_id)
    finally:
        db.close()

    typer.echo(f"Scraping {book.name} ({len(jobs)} chapters, concurrent={concurrent})")
    asyncio.run(_run_concurrent(jobs, concurrent, book.name))
    typer.echo("Done.")


@scrape_app.command("chapter")
def scrape_single(
    book_abbr: str = typer.Option(..., "--book-abbr"),
    chapter: int = typer.Option(..., "--chapter"),
):
    async def _run():
        db = SessionLocal()
        try:
            await scrape_chapter(db, book_abbr, chapter)
            typer.echo(f"OK {book_abbr} {chapter}")
        finally:
            db.close()

    asyncio.run(_run())


if __name__ == "__main__":
    app()

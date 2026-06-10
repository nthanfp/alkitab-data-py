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


image_app = typer.Typer(help="Image editing commands")
app.add_typer(image_app, name="image")


@image_app.command("add-text")
def image_add_text(
    output: str = typer.Option(..., "--output", "-o", help="Output image path"),
):
    """Add text overlay to Teens Verse template."""
    from pathlib import Path
    from PIL import Image, ImageDraw, ImageFont

    try:
        assets = Path(__file__).parent / "assets"
        template_path = assets / "images" / "Teens_Verse_Template.png"
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        output_file = Path(output)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        img = Image.open(template_path).convert("RGB")
        draw = ImageDraw.Draw(img, "RGBA")

        bold_font_path = assets / "fonts" / "glacial-indifference.bold.otf"
        regular_font_path = assets / "fonts" / "glacial-indifference.regular.otf"

        try:
            bold_font = ImageFont.truetype(str(regular_font_path), 50)
        except (FileNotFoundError, OSError):
            bold_font = ImageFont.load_default()

        try:
            regular_font = ImageFont.truetype(str(regular_font_path), 44)
        except (FileNotFoundError, OSError):
            regular_font = ImageFont.load_default()

        title = "Kejadian 1:1"
        bbox = draw.textbbox((0, 0), title, font=bold_font)
        title_w = bbox[2] - bbox[0]
        title_h = bbox[3] - bbox[1]

        verse_text = "Pada mulanya Allah menciptakan langit dan bumi."
        max_width = 610
        words = verse_text.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = current_line + " " + word if current_line else word
            tw = draw.textbbox((0, 0), test_line, font=regular_font)[2]
            if tw <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        line_spacing = regular_font.getbbox("A")[3] - regular_font.getbbox("A")[1] + 20
        verse_h = len(lines) * line_spacing

        title_box_h = title_h + 15 + 4 + 10
        gap_between = 40
        total_h = title_box_h + gap_between + verse_h

        start_y = (img.height - total_h) // 2

        x_title = img.width // 2 - title_w // 2
        y_title = start_y

        draw.text((x_title, y_title), title, fill="black", font=bold_font)

        underline_y = y_title + title_h + 15
        draw.line([(x_title, underline_y), (x_title + title_w, underline_y)], fill="black", width=4)

        y_verse = underline_y + 10 + gap_between

        for line in lines:
            lw = draw.textbbox((0, 0), line, font=regular_font)[2]
            x_verse = img.width // 2 - lw // 2
            draw.text((x_verse, y_verse), line, fill="black", font=regular_font)
            y_verse += line_spacing

        img.save(output_file)
        typer.echo(f"Saved: {output_file}")
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()

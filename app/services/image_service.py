from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from app.models.books import Book
from app.models.chapters import Chapter
from app.models.verses import Verse


async def generate_verse_image(db: Session, book: str, chapter: int, verse: int, end_verse: int | None = None, output_path: str = "output/verse.png") -> str:
    """Generate verse image with title and verse text overlay.
    
    Args:
        db: Database session
        book: Book name (Indonesian)
        chapter: Chapter number
        verse: Start verse number
        end_verse: End verse number (optional, for range)
        output_path: Output image path
    """
    
    book_obj = db.query(Book).filter(Book.name.ilike(book)).first()
    if not book_obj:
        raise ValueError(f"Book '{book}' not found")
    
    chapter_obj = db.query(Chapter).filter(
        Chapter.book_id == book_obj.id,
        Chapter.chapter_no == chapter
    ).first()
    if not chapter_obj:
        raise ValueError(f"Chapter {chapter} not found in {book}")
    
    # Ambil range ayat
    if end_verse and end_verse > verse:
        verse_objs = db.query(Verse).filter(
            Verse.chapter_id == chapter_obj.id,
            Verse.verse_no >= verse,
            Verse.verse_no <= end_verse
        ).order_by(Verse.verse_no).all()
        title = f"{book_obj.name} {chapter}:{verse}-{end_verse}"
    else:
        verse_obj = db.query(Verse).filter(
            Verse.chapter_id == chapter_obj.id,
            Verse.verse_no == verse
        ).first()
        if not verse_obj:
            raise ValueError(f"Verse {verse} not found in {book} {chapter}")
        verse_objs = [verse_obj]
        title = f"{book_obj.name} {chapter}:{verse}"
    
    # Combine teks semua ayat
    verse_text = "\n".join(v.text or "" for v in verse_objs)
    
    assets = Path(__file__).parent.parent / "assets"
    template_path = assets / "images" / "Teens_Verse_Template.png"
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    
    output_file = Path(output_path)
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
    
    # Hitung title dimensi
    bbox = draw.textbbox((0, 0), title, font=bold_font)
    title_w = bbox[2] - bbox[0]
    title_h = bbox[3] - bbox[1]
    
    # Hitung verse lines
    max_width = 610
    words = verse_text.replace("\n", " \n ").split()
    lines = []
    current_line = ""
    for word in words:
        if word == "\n":
            lines.append(current_line)
            current_line = ""
            continue
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
    
    # Hitung total height
    title_box_h = title_h + 15 + 4 + 10
    verse_lines_h = len(lines) * line_spacing
    total_h = title_box_h + verse_lines_h
    
    # Vertical center
    y_title = (img.height - total_h) // 2
    x_title = img.width // 2 - title_w // 2
    underline_y = y_title + title_h + 15
    
    # Draw
    draw.text((x_title, y_title), title, fill="black", font=bold_font)
    draw.line([(x_title, underline_y), (x_title + title_w, underline_y)], fill="black", width=4)
    
    y_verse = underline_y + 10 + 20
    for line in lines:
        lw = draw.textbbox((0, 0), line, font=regular_font)[2]
        x_verse = img.width // 2 - lw // 2
        draw.text((x_verse, y_verse), line, fill="black", font=regular_font)
        y_verse += line_spacing
    
    img.save(output_file)
    return str(output_file)

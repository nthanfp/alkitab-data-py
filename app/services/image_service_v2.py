from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from app.models.books import Book
from app.models.chapters import Chapter
from app.models.verses import Verse

ASSETS = Path(__file__).parent.parent / "assets"
IMAGES = ASSETS / "images"
FONTS = ASSETS / "fonts"


async def generate_verse_image_v2(
    db: Session,
    book: str,
    chapter: int,
    verse: int,
    end_verse: int | None = None,
    output_path: str = "output/verse_v2.png",
) -> str:
    """Generate verse image using V2 template.
    
    Template: Teens_Verse_Template_V2.png
    Title: left-aligned at x=145, y=770
    Verse: left-aligned at x=145, y=870, extends downward
    Font: Montserrat-Bold.ttf
    Color: #373e12
    """

    # DB lookup
    book_obj = db.query(Book).filter(Book.name.ilike(book)).first()
    if not book_obj:
        raise ValueError(f"Book '{book}' not found")

    chapter_obj = db.query(Chapter).filter(
        Chapter.book_id == book_obj.id,
        Chapter.chapter_no == chapter,
    ).first()
    if not chapter_obj:
        raise ValueError(f"Chapter {chapter} not found in {book}")

    # Ambil ayat
    if end_verse and end_verse > verse:
        verse_objs = db.query(Verse).filter(
            Verse.chapter_id == chapter_obj.id,
            Verse.verse_no >= verse,
            Verse.verse_no <= end_verse,
        ).order_by(Verse.verse_no).all()
        title = f"{book_obj.name} {chapter}:{verse}-{end_verse}"
    else:
        verse_obj = db.query(Verse).filter(
            Verse.chapter_id == chapter_obj.id,
            Verse.verse_no == verse,
        ).first()
        if not verse_obj:
            raise ValueError(f"Verse {verse} not found in {book} {chapter}")
        verse_objs = [verse_obj]
        title = f"{book_obj.name} {chapter}:{verse}"

    verse_text = "\n".join(v.text or "" for v in verse_objs)

    # Load template
    template_path = IMAGES / "Teens_Verse_Template_V2.png"
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    img = Image.open(template_path).convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")

    # Load fonts
    bold_font_path = FONTS / "Montserrat-Bold.ttf"
    regular_font_path = FONTS / "Montserrat-Regular.ttf"
    try:
        title_font = ImageFont.truetype(str(bold_font_path), 64)
    except (FileNotFoundError, OSError):
        title_font = ImageFont.load_default()

    try:
        verse_font = ImageFont.truetype(str(regular_font_path), 42)
    except (FileNotFoundError, OSError):
        verse_font = ImageFont.load_default()

    color = "#373e12"
    x = 145
    zone_top = 670
    zone_bottom = 1440
    zone_height = zone_bottom - zone_top
    title_gap = 80

    # Word wrap
    max_width = img.width - 145 - 100
    words = verse_text.replace("\n", " \n ").split()
    lines = []
    current_line = ""
    for word in words:
        if word == "\n":
            lines.append(current_line)
            current_line = ""
            continue
        test_line = current_line + " " + word if current_line else word
        tw = draw.textbbox((0, 0), test_line, font=verse_font)[2]
        if tw <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)

    # Hitung total height
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    title_h = title_bbox[3] - title_bbox[1]

    line_spacing = int(42 * 1.3)
    verse_h = len(lines) * line_spacing

    total_h = title_h + title_gap + verse_h

    # Vertical center dalam zone 670-1440
    start_y = zone_top + (zone_height - total_h) // 2

    # Draw title
    draw.text((x, start_y), title, fill=color, font=title_font)

    # Draw verse
    y_verse = start_y + title_h + title_gap
    for line in lines:
        draw.text((x, y_verse), line, fill=color, font=verse_font)
        y_verse += line_spacing

    img.save(output_file)
    return str(output_file)

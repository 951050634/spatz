from pathlib import Path
import shutil
import subprocess
from PIL import Image, ImageDraw, ImageFont

SOURCE = Path(__file__).resolve().parent
FIGURE = SOURCE.parent
BUILD = SOURCE / "build"
BUILD.mkdir(exist_ok=True)

for name in ("fig2_v4", "fig3_v4"):
    with (BUILD / f"{name}.log").open("w", encoding="utf-8") as log:
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
             f"-output-directory={BUILD}", f"{name}.tex"],
            cwd=SOURCE, check=True, stdout=log, stderr=subprocess.STDOUT,
        )
    pdf = BUILD / f"{name}.pdf"
    shutil.copy2(pdf, FIGURE / pdf.name)
    subprocess.run(
        ["pdftoppm", "-r", "600", "-png", "-singlefile",
         str(pdf), str(FIGURE / name)], check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

base = Image.open(SOURCE / "fig4-base.png").convert("RGB")
draw = ImageDraw.Draw(base)
font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf")
font = ImageFont.truetype(str(font_path), 22)

# Replace only the four memory-box headers; preserve their borders and values.
for box, label, size in (
    ((970, 128, 1194, 162), "State A [N]", 22),
    ((1235, 128, 1457, 162), "Tile State [N]", 22),
    ((970, 239, 1194, 273), "State B [N]", 22),
    ((1235, 239, 1457, 273), "Merge Weights [N]", 17),
):
    x0, y0, x1, y1 = box
    header_font = ImageFont.truetype(str(font_path), size)
    draw.rectangle((x0 + 4, y0 + 3, x1 - 4, y1 - 3), fill=(255, 255, 255))
    draw.text(((x0 + x1) / 2, (y0 + y1) / 2), label,
              font=header_font, fill=(15, 15, 15), anchor="mm")

# Correct the terminal-tile label to match T=N/B in the caption and text.
draw.rectangle((1260, 451, 1511, 502), fill=(240, 240, 240))
draw.text((1380, 478), "Tile T − 1", font=font,
          fill=(10, 10, 10), anchor="mm")

base.save(FIGURE / "fig4_v4.png", optimize=True)

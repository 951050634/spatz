from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent
S = 3
K = 1.0
FONT = "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"
BOLD = "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"
BLUE = (35, 91, 167)
RED = (188, 42, 42)
PURPLE = (112, 74, 176)


def f(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size * S)


def point(xy):
    return tuple(round(v * S * K) for v in xy)


def draw_arrow(draw, pts, color, width=4, head=12, both=False):
    q = [point(xy) for xy in pts]
    draw.line(q, fill=color, width=width * S, joint="curve")
    def triangle(tip, prev):
        dx, dy = tip[0] - prev[0], tip[1] - prev[1]
        mag = (dx * dx + dy * dy) ** 0.5 or 1
        ux, uy = dx / mag, dy / mag
        px, py = -uy, ux
        h, w = head * S, head * 0.62 * S
        base = (tip[0] - ux * h, tip[1] - uy * h)
        return [tip, (base[0] + px * w, base[1] + py * w),
                (base[0] - px * w, base[1] - py * w)]
    draw.polygon(triangle(q[-1], q[-2]), fill=color)
    if both:
        draw.polygon(triangle(q[0], q[1]), fill=color)


def label_lines(draw, x, ys, lines, font_size=16, color=(28, 28, 28), bold=False):
    font = f(font_size, bold)
    for y, line in zip(ys, lines):
        draw.text(point((x, y)), line, font=font, fill=color, anchor="mm")


# Fig. 2: show the owner-routed accelerator response and scalar-state reads.
im = Image.open(ROOT / "fig2_fixed-base.png").convert("RGB")
assert im.size == (1254, 1254), im.size
K = im.width / 1248
hi = im.resize((im.width * S, im.height * S), Image.Resampling.LANCZOS)
d = ImageDraw.Draw(hi)
# Blank gap between the SMU/RVV blocks and shared TCDM, then redraw its bus paths.
d.rectangle([point((32, 816)), point((1223, 932))], fill=(255, 255, 255))
# TCDM top boundary remains a crisp green edge.
d.line([point((30, 933)), point((1223, 933))], fill=(31, 150, 53), width=2 * S)
# SMU writes scalar state and merge weights; it reads old and tile-local state.
# Arrow positions sit between labels so the buses do not obscure their names.
draw_arrow(d, [(250, 817), (250, 929)], RED, width=4, head=12)
draw_arrow(d, [(455, 817), (455, 929)], RED, width=4, head=12)
draw_arrow(d, [(590, 929), (590, 823)], BLUE, width=4, head=12)
# RVV reads the two merge weights and reads/writes output tiles in shared TCDM.
draw_arrow(d, [(920, 929), (920, 823)], BLUE, width=4, head=12)
draw_arrow(d, [(1175, 929), (1175, 823)], BLUE, width=4, head=12, both=True)
label_lines(d, 135, [846, 872], ["write scalar state", "(m′, l′)"], 18)
label_lines(d, 340, [846, 872], ["write merge weights", "(w_old, w_tile)"], 18)
label_lines(d, 525, [846, 872], ["read scalar inputs", "(m, l, m_t, l_t)"], 16)
label_lines(d, 790, [846, 872], ["read merge weights", "(w_old, w_tile)"], 18)
label_lines(d, 1035, [846, 872], ["read/write output tiles", "(O, O_t, O′)"], 18)
# Owner-tagged response returns to the issuing scalar core.
box = [point((314, 365)), point((493, 456))]
d.rounded_rectangle(box, radius=9 * S, fill=(247, 241, 255), outline=PURPLE, width=2 * S)
label_lines(d, 403.5, [385, 407, 433],
            ["Owner-routed", "response demux", "completion / status"], 16, PURPLE, True)
draw_arrow(d, [(407, 492), (407, 458)], PURPLE, width=4, head=11)
draw_arrow(d, [(314, 410), (303, 410)], PURPLE, width=4, head=9)
fig2 = hi.resize(im.size, Image.Resampling.LANCZOS)
# Lanczos can pull a trace pixel across the panel edge; clear the four old
# connector stubs while keeping the original colored border intact.
d2 = ImageDraw.Draw(fig2)
for x in (295, 360, 849, 931):
    for y in range(810, 815):
        sample = fig2.getpixel((round((x - 8) * K), round(y * K)))
        d2.line([(round((x - 4) * K), round(y * K)),
                 (round((x + 4) * K), round(y * K))], fill=sample, width=1)
fig2.save(OUT / "fig2_fixed.png", optimize=True)

# Fig. 3: close the persistent-state loop back to the FP32-visible TCDM state.
im = Image.open(ROOT / "fig3-base.png").convert("RGB")
assert im.size == (1254, 1254), im.size
K = im.width / 1248
hi = im.resize((im.width * S, im.height * S), Image.Resampling.LANCZOS)
d = ImageDraw.Draw(hi)
# Identify the returned values in the memory-visible state card. The arrows
# entering this card below now close the state loop without tiny side labels.
d.rounded_rectangle([point((50, 372)), point((362, 485))],
                    radius=9 * S, fill=(231, 244, 255),
                    outline=(118, 178, 230), width=2 * S)
d.text(point((206, 396)), "FP32-visible state", font=f(21, True),
       fill=(25, 35, 45), anchor="mm")
d.text(point((206, 429)), "m′: FP16-RNE", font=f(20),
       fill=(25, 35, 45), anchor="mm")
d.text(point((206, 461)), "l′: Q16.32", font=f(20),
       fill=(25, 35, 45), anchor="mm")
# Move the existing EXP-to-accumulator return bus into a distinct lower lane.
# This leaves a clean lane for the maximum-state return path.
d.rectangle([point((165, 508)), point((1244, 551))], fill=(255, 255, 255))
draw_arrow(d, [(1234, 507), (1234, 540), (176, 540), (176, 552)],
           (24, 24, 24), width=3, head=10)
# Maximum return path: mixed-precision maximum returns through the FP32 carrier.
draw_arrow(d, [(585, 500), (585, 520), (18, 520), (18, 398), (50, 398)],
           BLUE, width=4, head=11)
# Normalizer return path leaves the accumulator's Q16.32 carrier block and
# rejoins the FP32-visible state without crossing the dashed precision arrows.
draw_arrow(d, [(33, 831), (18, 831), (18, 452), (50, 452)],
           BLUE, width=4, head=11)
label_lines(d, 500, [510], ["m′ (FP16-RNE)"], 17, BLUE, True)
hi.resize(im.size, Image.Resampling.LANCZOS).save(OUT / "fig3.png", optimize=True)

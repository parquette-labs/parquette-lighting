#!/usr/bin/env python3
"""Generate the Parquette disco-ball icons for Open Stage Control.

Renders a 3D mirror-ball (orthographic sphere projection, per-facet
diffuse shading + random accent/sparkle tiles) at high resolution, then
downsamples to:
  - favicon.png  256x256, transparent background (browser tab icon)
  - logo.png     512x512, opaque theme background, ball inset to the
                 maskable safe zone (apple-touch-icon + PWA manifest icon)

Run: python3 make_icons.py <output_dir>
"""
import math
import random
import sys
from PIL import Image, ImageDraw

OUT = sys.argv[1] if len(sys.argv) > 1 else "."

SS = 2048  # hi-res master canvas
CX = CY = SS / 2
R = SS * 0.46
THEME_BG = (33, 37, 43, 255)  # OSC --color-background #21252b

random.seed(1977)


def lerp(a, b, t):
    return a + (b - a) * t


def sphere_pt(phi_deg, theta_deg):
    p = math.radians(phi_deg)
    t = math.radians(theta_deg)
    return (math.cos(p) * math.sin(t), math.sin(p), math.cos(p) * math.cos(t))


def project(pt):
    return (CX + pt[0] * R, CY - pt[1] * R)


def render_ball() -> Image.Image:
    img = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Grout base circle (shows between the inset mirror tiles, fills poles).
    d.ellipse([CX - R, CY - R, CX + R, CY + R], fill=(16, 21, 34, 255))

    # Light direction: upper-left, toward the viewer.
    lx, ly, lz = -0.42, 0.55, 0.72
    ln = math.sqrt(lx * lx + ly * ly + lz * lz)
    lx, ly, lz = lx / ln, ly / ln, lz / ln

    dark = (34, 46, 70)
    lite = (210, 226, 247)
    accents = [(255, 61, 139), (61, 240, 255), (163, 190, 140),
               (180, 142, 173), (235, 203, 139)]

    n_lat, n_lon = 16, 32
    lat0, lat1 = -82.0, 82.0

    for i in range(n_lat):
        phi_a = lerp(lat0, lat1, i / n_lat)
        phi_b = lerp(lat0, lat1, (i + 1) / n_lat)
        for j in range(n_lon):
            th_a = 360.0 * j / n_lon
            th_b = 360.0 * (j + 1) / n_lon
            corners = [sphere_pt(phi_a, th_a), sphere_pt(phi_a, th_b),
                       sphere_pt(phi_b, th_b), sphere_pt(phi_b, th_a)]
            nx = sum(c[0] for c in corners) / 4
            ny = sum(c[1] for c in corners) / 4
            nz = sum(c[2] for c in corners) / 4
            nn = math.sqrt(nx * nx + ny * ny + nz * nz)
            nx, ny, nz = nx / nn, ny / nn, nz / nn
            if nz <= 0.02:  # back-facing / silhouette sliver
                continue

            diff = max(0.0, nx * lx + ny * ly + nz * lz)
            shade = min(1.0, (0.12 + 0.88 * diff) * random.uniform(0.9, 1.08))

            roll = random.random()
            if roll < 0.10:  # bright white sparkle
                s = min(1.0, 0.6 + 0.5 * shade)
                color = (int(255 * s), int(255 * s), int(255 * s))
            elif roll < 0.24:  # colored disco tile
                base = random.choice(accents)
                s = 0.45 + 0.6 * shade
                color = tuple(min(255, int(c * s)) for c in base)
            else:  # silver-blue mirror tile
                color = tuple(int(lerp(dark[k], lite[k], shade)) for k in range(3))

            pts = [project(c) for c in corners]
            mx = sum(p[0] for p in pts) / 4
            my = sum(p[1] for p in pts) / 4
            poly = [(mx + (px - mx) * 0.82, my + (py - my) * 0.82) for px, py in pts]
            d.polygon(poly, fill=color + (255,))

    # Soft specular glow, upper-left, clipped to the ball.
    glow = Image.new("L", (SS, SS), 0)
    gd = ImageDraw.Draw(glow)
    gx, gy, gr = CX - R * 0.34, CY - R * 0.40, R * 0.52
    for rr in range(int(gr), 0, -2):
        gd.ellipse([gx - rr, gy - rr, gx + rr, gy + rr],
                   fill=int(85 * (1 - rr / gr) ** 2))
    clip = Image.new("L", (SS, SS), 0)
    ImageDraw.Draw(clip).ellipse([CX - R, CY - R, CX + R, CY + R], fill=255)
    glow = Image.composite(glow, Image.new("L", (SS, SS), 0), clip)
    shine = Image.new("RGBA", (SS, SS), (255, 255, 255, 0))
    shine.putalpha(glow)
    return Image.alpha_composite(img, shine)


def main():
    master = render_ball()

    favicon = master.resize((256, 256), Image.LANCZOS)
    favicon.save(f"{OUT}/favicon.png")

    logo = Image.new("RGBA", (512, 512), THEME_BG)
    d = int(512 * 0.80)  # ball fits the maskable safe zone (center 80%)
    ball = master.resize((d, d), Image.LANCZOS)
    off = (512 - d) // 2
    logo.alpha_composite(ball, (off, off))
    logo.save(f"{OUT}/logo.png")

    # 256x256 preview on the theme bg so we can eyeball the tab look.
    prev = Image.new("RGBA", (256, 256), THEME_BG)
    prev.alpha_composite(favicon, (0, 0))
    prev.save(f"{OUT}/preview_on_theme.png")

    print(f"wrote favicon.png, logo.png, preview_on_theme.png to {OUT}")


if __name__ == "__main__":
    main()

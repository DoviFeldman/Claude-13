"""Generate the PWA icons (dark tile + lightning bolt) with no image deps.

Run from the repo root: python scripts/make_icons.py
"""

import struct
import zlib
import pathlib

BG = (11, 16, 32)
BOLT = (255, 215, 94)

# Bolt polygon in unit coordinates (x, y), y down.
BOLT_POLY = [
    (0.58, 0.10), (0.32, 0.54), (0.47, 0.54),
    (0.40, 0.90), (0.70, 0.44), (0.53, 0.44),
]


def point_in_poly(x, y, poly):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def make_png(size, path):
    rows = []
    ss = 3  # supersampling for smoother edges
    for py in range(size):
        row = bytearray([0])  # filter type 0
        for px in range(size):
            hits = 0
            for sy in range(ss):
                for sx in range(ss):
                    x = (px + (sx + 0.5) / ss) / size
                    y = (py + (sy + 0.5) / ss) / size
                    if point_in_poly(x, y, BOLT_POLY):
                        hits += 1
            a = hits / (ss * ss)
            row.extend(round(BG[c] + (BOLT[c] - BG[c]) * a) for c in range(3))
        rows.append(bytes(row))

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data)))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"".join(rows), 9)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
           chunk(b"IDAT", idat) + chunk(b"IEND", b""))
    pathlib.Path(path).write_bytes(png)
    print(f"wrote {path} ({len(png)} bytes)")


if __name__ == "__main__":
    out = pathlib.Path(__file__).resolve().parent.parent / "docs" / "icons"
    out.mkdir(parents=True, exist_ok=True)
    make_png(192, out / "icon-192.png")
    make_png(512, out / "icon-512.png")

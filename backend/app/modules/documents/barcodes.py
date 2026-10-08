"""Code128 and QR as SVG data URIs, embedded in the WeasyPrint HTML templates (ROADMAP §6.1)."""

from __future__ import annotations

import base64
import io

import segno
from barcode import Code128
from barcode.writer import SVGWriter


def code128_data_uri(value: str, module_width_mm: float = 0.33, height_mm: float = 9.0) -> str:
    buf = io.BytesIO()
    Code128(value, writer=SVGWriter()).write(
        buf,
        options={
            "write_text": False,
            "module_width": module_width_mm,
            "module_height": height_mm,
            "quiet_zone": 3.0,
            "background": "white",
            "foreground": "black",
        },
    )
    return "data:image/svg+xml;base64," + base64.b64encode(buf.getvalue()).decode()


def qr_data_uri(value: str) -> str:
    uri: str = segno.make(value, error="m", micro=False).svg_data_uri(scale=4, border=2)
    return uri

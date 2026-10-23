"""80 mm thermal queue token (ROADMAP §4.2): token number, order code and a QR carrying the code only."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import clock, codes
from app.modules.documents import barcodes
from app.modules.documents.slip import _env, html_to_pdf
from app.modules.orders.models import LabOrder
from app.modules.queue.models import QueueToken


def render_token(db: Session, token: QueueToken, order: LabOrder, reprint: int = 0) -> bytes:
    assert order.order_code is not None
    s = get_settings()
    html = (
        _env()
        .get_template("token.html")
        .render(
            token=token,
            code=codes.format_order_code(order.order_code),
            qr=barcodes.qr_data_uri(order.order_code),
            institution_en=s.institution_name_en,
            lab_en=s.lab_name_en,
            printed_at=clock.local_now(),
            reprint=reprint,
        )
    )
    return html_to_pdf(html)

"""Prescription upload (1–3 images, compressed client-side to ≤ 1 MB each) and image access."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.core import audit, storage
from app.core.actor import Actor
from app.core.errors import Invalid, NotFound
from app.modules.patients.models import Channel
from app.modules.prescriptions.models import Prescription

MAX_IMAGES = 3
MAX_IMAGE_BYTES = 1_200_000  # the client compresses to ≤ 1 MB; small headroom for metadata

_MAGIC: list[tuple[bytes, str, str]] = [
    (b"\xff\xd8\xff", "jpg", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "png", "image/png"),
    (b"RIFF", "webp", "image/webp"),  # RIFF....WEBP, checked below
]


@dataclass(frozen=True)
class ImageIn:
    data: bytes
    filename: str | None = None


def sniff(data: bytes) -> tuple[str, str]:
    for magic, ext, ctype in _MAGIC:
        if data.startswith(magic) and (ext != "webp" or data[8:12] == b"WEBP"):
            return ext, ctype
    raise Invalid("UNSUPPORTED_IMAGE")


def content_type_for(key: str) -> str:
    ext = key.rsplit(".", 1)[-1]
    return {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "application/octet-stream")


def create(
    db: Session,
    patient_id: uuid.UUID,
    images: list[ImageIn],
    actor: Actor,
    channel: Channel,
    doctor_name: str | None = None,
    prescription_date: date | None = None,
) -> Prescription:
    if not 1 <= len(images) <= MAX_IMAGES:
        raise Invalid("PRESCRIPTION_IMAGE_COUNT", min=1, max=MAX_IMAGES)
    checked: list[tuple[bytes, str, str]] = []
    for img in images:
        if len(img.data) > MAX_IMAGE_BYTES:
            raise Invalid("IMAGE_TOO_LARGE", max_bytes=MAX_IMAGE_BYTES)
        ext, ctype = sniff(img.data)
        checked.append((img.data, ext, ctype))
    pid = uuid.uuid4()
    keys: list[str] = []
    for n, (data, ext, ctype) in enumerate(checked, start=1):
        key = f"{patient_id}/{pid}/{n}.{ext}"
        storage.put("prescriptions", key, data, ctype)
        keys.append(key)
    p = Prescription(
        id=pid,
        patient_id=patient_id,
        images=keys,
        doctor_name=(doctor_name or "").strip() or None,
        prescription_date=prescription_date,
        channel=channel,
        uploaded_by_staff_id=actor.id if actor.type == "staff" else None,
    )
    db.add(p)
    audit.record(
        db,
        actor,
        "prescription.upload",
        entity_type="prescription",
        entity_id=p.id,
        patient_id=patient_id,
        after={"images": len(keys)},
    )
    return p


def add_images(db: Session, p: Prescription, images: list[ImageIn], actor: Actor) -> None:
    """Extra pages sent while answering a clarification request (total still ≤ 3)."""
    if len(p.images) + len(images) > MAX_IMAGES:
        raise Invalid("PRESCRIPTION_IMAGE_COUNT", min=1, max=MAX_IMAGES)
    keys = list(p.images)
    for img in images:
        if len(img.data) > MAX_IMAGE_BYTES:
            raise Invalid("IMAGE_TOO_LARGE", max_bytes=MAX_IMAGE_BYTES)
        ext, ctype = sniff(img.data)
        key = f"{p.patient_id}/{p.id}/{len(keys) + 1}.{ext}"
        storage.put("prescriptions", key, img.data, ctype)
        keys.append(key)
    p.images = keys
    audit.record(
        db, actor, "prescription.add_images", entity_type="prescription", entity_id=p.id, patient_id=p.patient_id
    )


def get(db: Session, prescription_id: uuid.UUID) -> Prescription:
    p = db.get(Prescription, prescription_id)
    if p is None:
        raise NotFound("prescription")
    return p


def image(p: Prescription, n: int) -> tuple[bytes, str]:
    if not 1 <= n <= len(p.images):
        raise NotFound("prescription_image")
    key = str(p.images[n - 1])
    return storage.get("prescriptions", key), content_type_for(key)

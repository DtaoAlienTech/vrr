"""Turns an uploaded photo into safe, small web copies. No database and no files here: bytes in,
bytes out, so every rule can be tested with small in-memory images.

What happens to a photo:
- The real file type is read from the content (JPEG, PNG or WebP). The file name is ignored.
- Huge pictures (more than 6000 px on a side) and broken or disguised files are refused.
- It is rotated the way the camera meant it, converted to sRGB, and ALL metadata is dropped
  (camera model, date, GPS location).
- WebP copies are made at 400, 800, 1200 and 1600 px wide (never larger than the original).
"""

import io
import re
import warnings
from dataclasses import dataclass

from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = ("JPEG", "PNG", "WEBP")
MAX_SIDE = 6000
TARGET_WIDTHS = (400, 800, 1200, 1600)
WEBP_QUALITY = 80

Image.MAX_IMAGE_PIXELS = MAX_SIDE * MAX_SIDE  # a second safety net against "decompression bombs"

_SRGB = ImageCms.createProfile("sRGB")


class FileRejected(ValueError):
    """The upload is not acceptable. The message is safe to show to the person uploading."""


@dataclass(frozen=True)
class Variant:
    width: int
    height: int
    data: bytes


# ---- what kind of file is this? (from its first bytes, never from its name) ----


def detect_kind(raw: bytes) -> str | None:
    """ "image" (JPEG, PNG or WebP), "pdf", or None for anything else."""
    head = raw[:16]
    if head.startswith(b"%PDF-"):
        return "pdf"
    if (
        head.startswith(b"\xff\xd8\xff")
        or head.startswith(b"\x89PNG\r\n\x1a\n")
        or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")
    ):
        return "image"
    return None


# ---- images ----


def _to_clean_rgb(img: Image.Image, icc_profile: bytes | None) -> Image.Image:
    """sRGB pixels only: no profile, no EXIF, no other metadata can survive."""
    has_alpha = img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info
    if icc_profile and img.mode in ("RGB", "CMYK"):
        try:  # wide-gamut photos would look dull without this
            profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_profile))
            img = ImageCms.profileToProfile(img, profile, _SRGB, outputMode="RGB")
        except (ImageCms.PyCMSError, OSError, ValueError):
            pass  # an unreadable profile: keep the pixels as they are
    img = img.convert("RGBA" if has_alpha else "RGB")
    return Image.frombytes(img.mode, img.size, img.tobytes())  # a fresh image: no metadata


def _widths(original_width: int) -> list[int]:
    smaller = {w for w in TARGET_WIDTHS if w < original_width}
    return sorted(smaller | {min(original_width, max(TARGET_WIDTHS))})


def process_image(raw: bytes) -> list[Variant]:
    """The web copies of a photo, smallest first. The last one is the largest (up to 1600 px)."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw), formats=ALLOWED_FORMATS) as opened:
                width, height = opened.size
                if max(width, height) > MAX_SIDE:
                    raise FileRejected(
                        f"The picture is too large (at most {MAX_SIDE} px on a side)."
                    )
                if width < 1 or height < 1:
                    raise FileRejected("The picture is empty.")
                if getattr(opened, "n_frames", 1) > 1:
                    opened.seek(0)  # animated: keep the first picture only
                icc_profile = opened.info.get("icc_profile")
                upright = ImageOps.exif_transpose(opened)  # apply the camera's rotation
                clean = _to_clean_rgb(upright, icc_profile)
    except FileRejected:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise FileRejected(
            f"The picture is too large (at most {MAX_SIDE} px on a side)."
        ) from error
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        EOFError,
        ValueError,
        TypeError,
    ) as error:
        raise FileRejected("This file is not a valid JPEG, PNG or WebP picture.") from error

    variants = []
    for target in _widths(clean.width):
        size = (target, max(1, round(clean.height * target / clean.width)))
        copy = clean if size == clean.size else clean.resize(size, Image.Resampling.LANCZOS)
        out = io.BytesIO()
        copy.save(out, "WEBP", quality=WEBP_QUALITY, method=4)
        variants.append(Variant(copy.width, copy.height, out.getvalue()))
    return variants


# ---- PDFs ----

# Names of PDF features that run code or reach out of the document. A syllabus or a circular needs
# none of them. (This is a safety net, not a full scanner: staff are trusted, the file is served
# with nosniff and as application/pdf, and nothing here is ever executed on the server.)
_DANGEROUS_PDF_NAMES = re.compile(
    rb"/(JavaScript|JS|Launch|EmbeddedFile|RichMedia|SubmitForm|ImportData)(?![A-Za-z0-9_.\-])"
)
_NAME_ESCAPE = re.compile(rb"#([0-9A-Fa-f]{2})")


def check_pdf(raw: bytes) -> None:
    if not raw.startswith(b"%PDF-") or b"%%EOF" not in raw[-2048:]:
        raise FileRejected("This file is not a valid PDF.")
    # "/J#61vaScript" is the same name as "/JavaScript": undo such escapes before looking
    plain = _NAME_ESCAPE.sub(lambda m: bytes([int(m.group(1), 16)]), raw)
    if _DANGEROUS_PDF_NAMES.search(plain):
        raise FileRejected("This PDF contains scripts or attachments, which are not allowed.")

"""The photo pipeline: what is accepted, how it is resized, and what is thrown away."""

import io
import time

import pytest
from PIL import Image, ImageCms

from app.services import images
from app.services.images import FileRejected, check_pdf, detect_kind, process_image

PDF = (
    b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"trailer\n<< /Root 1 0 R >>\n%%EOF\n"
)


def picture(fmt="JPEG", size=(300, 200), mode="RGB", color=(200, 40, 40), **save) -> bytes:
    img = Image.new(mode, size, color if mode in ("RGB", "RGBA") else 128)
    out = io.BytesIO()
    img.save(out, fmt, **save)
    return out.getvalue()


def decode(variant) -> Image.Image:
    img = Image.open(io.BytesIO(variant.data))
    img.load()
    return img


def widths(raw: bytes) -> list[int]:
    return [v.width for v in process_image(raw)]


# ---- file type: decided by the content ----


@pytest.mark.parametrize(
    ("raw", "kind"),
    [
        (picture("JPEG"), "image"),
        (picture("PNG"), "image"),
        (picture("WEBP"), "image"),
        (PDF, "pdf"),
        (b"GIF89a\x01\x00\x01\x00", None),
        (b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", None),
        (b"<html><script>alert(1)</script></html>", None),
        (b"MZ\x90\x00 an executable", None),
        (b"PK\x03\x04 a zip file", None),
        (b"RIFF\x00\x00\x00\x00WAVE", None),
        (b"", None),
        (b"%PD", None),
    ],
)
def test_the_kind_comes_from_the_first_bytes(raw, kind):
    assert detect_kind(raw) == kind


# ---- sizes ----


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        ((3000, 2000), [400, 800, 1200, 1600]),
        ((1601, 900), [400, 800, 1200, 1600]),
        ((1600, 900), [400, 800, 1200, 1600]),
        ((1156, 868), [400, 800, 1156]),
        ((801, 600), [400, 800, 801]),
        ((300, 200), [300]),
        ((400, 400), [400]),
        ((1, 1), [1]),
    ],
)
def test_copies_are_never_larger_than_the_original_or_1600(size, expected):
    assert widths(picture("JPEG", size)) == expected


def test_copies_keep_the_shape_and_are_webp():
    variants = process_image(picture("JPEG", (3000, 2000)))
    for variant in variants:
        img = decode(variant)
        assert img.format == "WEBP" and img.size == (variant.width, variant.height)
        assert abs(variant.height - variant.width * 2 / 3) <= 1
    assert [v.width for v in variants] == sorted(v.width for v in variants)  # smallest first
    assert variants[-1].width == 1600


def test_a_very_wide_thin_picture_still_has_a_height():
    variants = process_image(picture("PNG", (3000, 1)))
    assert all(v.height >= 1 for v in variants)


def test_the_file_name_does_not_matter():
    assert widths(picture("PNG", (500, 500))) == [400, 500]


# ---- privacy: no metadata survives ----


def exif_picture(orientation=1, **extra) -> bytes:
    exif = Image.Exif()
    exif[0x010F] = "SecretCamera Inc"  # Make
    exif[0x0110] = "Model-9000"
    exif[0x0112] = orientation
    exif[0x9003] = "2026:10:30 08:15:00"  # when it was taken
    exif.get_ifd(0x8825).update({1: "N", 2: (13.0, 4.0, 5.0), 3: "E", 4: (80.0, 1.0, 2.0)})  # GPS
    return picture("JPEG", (300, 200), exif=exif.tobytes(), **extra)


def test_camera_data_and_gps_location_are_removed():
    raw = exif_picture()
    assert b"SecretCamera" in raw  # (the test file really does contain it)
    for variant in process_image(raw):
        assert b"SecretCamera" not in variant.data and b"Model-9000" not in variant.data
        assert b"2026:10:30" not in variant.data and b"EXIF" not in variant.data
        img = decode(variant)
        assert len(img.getexif()) == 0
        assert not {"exif", "xmp", "icc_profile", "comment"} & set(img.info)


@pytest.mark.parametrize(
    ("orientation", "size"), [(1, (300, 200)), (3, (300, 200)), (6, (200, 300)), (8, (200, 300))]
)
def test_the_cameras_rotation_is_applied_to_the_pixels(orientation, size):
    variant = process_image(exif_picture(orientation))[-1]
    assert (variant.width, variant.height) == size


def test_embedded_comments_and_icc_profiles_are_not_kept():
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    raw = picture("PNG", (300, 200), icc_profile=profile)
    img = decode(process_image(raw)[-1])
    assert "icc_profile" not in img.info


# ---- colour and transparency ----


def test_transparency_is_kept():
    img = Image.new("RGBA", (300, 200), (0, 0, 0, 0))
    img.paste((255, 0, 0, 255), (0, 0, 150, 200))
    out = io.BytesIO()
    img.save(out, "PNG")
    decoded = decode(process_image(out.getvalue())[-1])
    assert decoded.mode == "RGBA"
    assert decoded.getpixel((10, 10))[3] == 255 and decoded.getpixel((290, 10))[3] == 0


def test_palette_pictures_with_transparency_keep_it():
    img = Image.new("P", (100, 100), 0)
    img.putpalette([255, 0, 0] * 256)
    out = io.BytesIO()
    img.save(out, "PNG", transparency=0)
    assert decode(process_image(out.getvalue())[-1]).mode == "RGBA"


@pytest.mark.parametrize("mode", ["L", "CMYK", "1", "LA"])
def test_other_colour_modes_are_converted(mode):
    fmt = "JPEG" if mode in ("L", "CMYK") else "PNG"
    result = process_image(picture(fmt, (200, 100), mode))
    assert decode(result[-1]).mode in ("RGB", "RGBA")


def test_wide_gamut_photos_are_converted_to_srgb():
    # a profile other than sRGB must be applied, not just thrown away
    adobe = ImageCms.ImageCmsProfile(ImageCms.createProfile("LAB")).tobytes()
    raw = picture("JPEG", (200, 100), icc_profile=adobe)
    assert process_image(raw)  # the conversion path runs without trouble


def test_animated_pictures_become_one_still_picture():
    first, second = Image.new("RGB", (120, 80), "red"), Image.new("RGB", (120, 80), "blue")
    out = io.BytesIO()
    first.save(out, "WEBP", save_all=True, append_images=[second], duration=100)
    variants = process_image(out.getvalue())
    assert len(variants) == 1
    assert decode(variants[0]).getpixel((5, 5))[0] > 200  # the first frame: red


# ---- refused files ----


def test_the_size_limit_is_checked_without_decoding_the_picture():
    started = time.monotonic()
    for size in ((6001, 10), (10, 6001), (6001, 6001)):
        with pytest.raises(FileRejected, match="too large"):
            process_image(picture("PNG", size))
    assert time.monotonic() - started < 2  # a huge solid picture costs almost nothing to refuse


def test_the_largest_allowed_picture_is_accepted():
    assert widths(picture("PNG", (6000, 8))) == [400, 800, 1200, 1600]


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"hello world",
        b"GIF89a" + b"\x00" * 40,
        b"BM" + b"\x00" * 40,
        b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>",
        PDF,
        b"\xff\xd8\xff" + b"garbage" * 20,  # starts like a JPEG, is not one
        b"\x89PNG\r\n\x1a\n" + b"garbage" * 20,
        b"RIFF\x10\x00\x00\x00WEBPgarbage!!!!",
    ],
)
def test_files_that_are_not_pictures_are_refused(raw):
    with pytest.raises(FileRejected, match="valid JPEG, PNG or WebP"):
        process_image(raw)


def test_truncated_pictures_are_refused():
    raw = picture("JPEG", (1200, 800))
    with pytest.raises(FileRejected):
        process_image(raw[: len(raw) // 2])


def test_a_tiff_with_a_picture_name_is_refused():
    out = io.BytesIO()
    Image.new("RGB", (50, 50)).save(out, "TIFF")
    with pytest.raises(FileRejected):
        process_image(out.getvalue())


def test_html_hidden_after_a_picture_is_not_kept():
    raw = picture("JPEG", (200, 100)) + b"<script>alert(1)</script>"
    for variant in process_image(raw):
        assert (
            b"<script>" not in variant.data
        )  # the picture is re-encoded; the extra bytes are gone


def test_the_decompression_bomb_guard_is_on():
    assert images.Image.MAX_IMAGE_PIXELS == images.MAX_SIDE * images.MAX_SIDE


# ---- PDFs ----


def test_a_plain_pdf_is_accepted():
    check_pdf(PDF)
    check_pdf(PDF.replace(b"/Pages 2 0 R", b"/JSON 5 /Javascripty 6"))  # similar words are fine


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"not a pdf %%EOF",
        b"%PDF-1.4 no end marker",
        b"%%EOF" + b"x" * 5000 + b"%PDF-1.4",
        b"<html>%PDF-1.4 %%EOF",
        PDF.replace(b"%%EOF", b"/JavaScript (app.alert(1)) %%EOF"),
        PDF.replace(b"%%EOF", b"/JS (app.alert(1)) %%EOF"),
        PDF.replace(b"%%EOF", b"/J#61vaScr#69pt (x) %%EOF"),  # the same name, written with escapes
        PDF.replace(b"%%EOF", b"/S /Launch /F (cmd.exe) %%EOF"),
        PDF.replace(b"%%EOF", b"/Type /EmbeddedFile %%EOF"),
        PDF.replace(b"%%EOF", b"/RichMedia %%EOF"),
        PDF.replace(b"%%EOF", b"/SubmitForm %%EOF"),
    ],
)
def test_dangerous_or_broken_pdfs_are_refused(raw):
    with pytest.raises(FileRejected):
        check_pdf(raw)

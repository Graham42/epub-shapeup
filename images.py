"""Image fixes for e-ink readers: opaque backgrounds and still frames for animations."""

from io import BytesIO

from PIL import Image, ImageChops, ImageSequence

WHITE = (255, 255, 255, 255)


def is_animated(data: bytes) -> bool:
    """True if the image has more than one frame (e.g. animated GIF)."""
    with Image.open(BytesIO(data)) as img:
        return getattr(img, "n_frames", 1) > 1


def flatten(data: bytes) -> bytes:
    """Composite a transparent PNG onto white; return the input unchanged if it is fully opaque.

    Dark-mode readers show transparent line art as black-on-black, so any image with
    non-opaque pixels is flattened. Output is a lossless PNG at the original size,
    'L' when the content is grayscale, else 'RGB'.
    """
    with Image.open(BytesIO(data)) as img:
        rgba = img.convert("RGBA")
        if rgba.getchannel("A").getextrema()[0] == 255:
            return data
        return _encode_on_white(rgba, img.info)


def still_frame(data: bytes) -> bytes:
    """Return the longest-displayed frame of an animation as a lossless PNG on white.

    Animations that demonstrate an interaction hold the finished, settled state on
    screen the longest (typically the last frame, before looping), while transition
    frames flash by. Ties go to the later frame, so frames without timing yield the
    last frame. For the Hill Chart GIF this is the final frame (4.5 s hold), showing
    every dot in its new position after saving.
    """
    with Image.open(BytesIO(data)) as img:
        best, best_duration = None, -1
        for frame in ImageSequence.Iterator(img):
            duration = frame.info.get("duration") or 0
            if duration >= best_duration:
                best, best_duration = frame.convert("RGBA"), duration
        assert best is not None
        return _encode_on_white(best, img.info)


def _encode_on_white(rgba: Image.Image, info: dict) -> bytes:
    """Composite RGBA onto white and encode as lossless PNG, 'L' if gray, keeping DPI.

    The ICC profile is kept only for RGB output, since the sources carry RGB profiles
    that would be invalid on a grayscale PNG.
    """
    rgb = Image.alpha_composite(Image.new("RGBA", rgba.size, WHITE), rgba).convert("RGB")
    params = {"dpi": info["dpi"]} if "dpi" in info else {}
    if _is_gray(rgb):
        out = rgb.convert("L")
    else:
        out = rgb
        if info.get("icc_profile"):
            params["icc_profile"] = info["icc_profile"]
    buf = BytesIO()
    out.save(buf, "PNG", optimize=False, **params)
    return buf.getvalue()


def _is_gray(rgb: Image.Image) -> bool:
    """True if every pixel has R == G == B, so conversion to 'L' is lossless."""
    r, g, b = rgb.split()
    return ImageChops.difference(r, g).getbbox() is None and ImageChops.difference(g, b).getbbox() is None

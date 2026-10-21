"""Restore logical reading order for Arabic glyphs extracted from PDFs."""

from __future__ import annotations

import math
import unicodedata
from collections.abc import Mapping

__all__ = ["LogicalineError", "logical_lines"]
__version__ = "0.1.1"

_OPEN_PARENS = frozenset({"(", "\uFD3E"})
_CLOSE_PARENS = frozenset({")", "\uFD3F"})


class _Missing:
    pass


_MISSING = _Missing()


class LogicalineError(ValueError):
    """Raised when glyph input is missing required fields or has a bad type."""


def logical_lines(glyphs, *, normalize: bool = False) -> list[str]:
    """Group glyphs into lines and return each line in logical reading order.

    A glyph is a dict or an object with ``t``, ``x0``, and ``y0``.
    ``x1`` and ``y1`` are optional. Coordinates follow PDF user space:
    x grows to the right and y grows upward. The first string is the
    top line on the page. With ``normalize=True`` each returned line is
    passed through Unicode NFKC, which maps Arabic presentation forms
    (U+FB50 to U+FEFF) such as the lam-alef ligature back to base letters.
    """
    items = _coerce_glyphs(glyphs)
    if normalize:
        return [
            unicodedata.normalize("NFKC", _line_to_logical(_sort_line(line)))
            for line in _group_lines(items)
        ]
    lines = _group_lines(items)
    return [_line_to_logical(_sort_line(line)) for line in lines]


def _coerce_glyphs(glyphs) -> list[dict]:
    if glyphs is None or isinstance(glyphs, (str, bytes, bytearray, Mapping)):
        raise LogicalineError("glyphs must be a sequence of glyph dicts or objects")
    try:
        raw = list(glyphs)
    except TypeError as exc:
        raise LogicalineError(
            "glyphs must be a sequence of glyph dicts or objects"
        ) from exc

    items: list[dict] = []
    for index, glyph in enumerate(raw):
        items.extend(_expand_mixed(_coerce_one(glyph, index)))
    return items


def _lookup(glyph, key):
    if isinstance(glyph, Mapping):
        if key not in glyph:
            return _MISSING
        return glyph[key]
    if hasattr(glyph, key):
        return getattr(glyph, key)
    return _MISSING


def _coerce_one(glyph, index: int) -> dict:
    if glyph is None or isinstance(glyph, (str, bytes, bytearray, int, float, bool)):
        raise LogicalineError(
            "each glyph must be a dict or an object with t, x0, and y0"
        )
    missing = [key for key in ("t", "x0", "y0") if _lookup(glyph, key) is _MISSING]
    if missing:
        names = ", ".join(missing)
        raise LogicalineError(f"each glyph requires t, x0, and y0; missing {names}")

    text = _lookup(glyph, "t")
    if not isinstance(text, str):
        raise LogicalineError("glyph t must be a string")

    record = {
        "t": text,
        "x0": _number(_lookup(glyph, "x0"), "x0"),
        "y0": _number(_lookup(glyph, "y0"), "y0"),
        "x1": None,
        "y1": None,
        "_i": index,
    }
    for key in ("x1", "y1"):
        value = _lookup(glyph, key)
        if value is _MISSING or value is None:
            continue
        record[key] = _number(value, key)
    return record


def _number(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LogicalineError(f"glyph {name} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise LogicalineError(f"glyph {name} must be a finite number")
    return number


def _expand_mixed(glyph: dict) -> list[dict]:
    """Split a glyph whose text mixes Arabic letters with left-to-right characters."""
    text = glyph["t"]
    strong = {_char_role(ch) for ch in text}
    strong.discard("N")
    if strong != {"R", "L"}:
        return [glyph]
    parts = []
    for offset, ch in enumerate(text):
        part = dict(glyph)
        part["t"] = ch
        part["x0"] = glyph["x0"] + offset * 1e-6
        parts.append(part)
    return parts


def _span(glyph: dict) -> tuple[float, float]:
    y0 = glyph["y0"]
    y1 = glyph["y1"] if glyph["y1"] is not None else y0
    if y0 <= y1:
        return y0, y1
    return y1, y0


def _top(glyph: dict) -> float:
    return _span(glyph)[1]


class _Line:
    __slots__ = ("glyphs", "hi", "lo", "min_height", "seed_y0")

    def __init__(self, glyph: dict) -> None:
        lo, hi = _span(glyph)
        self.glyphs = [glyph]
        self.lo, self.hi = lo, hi
        self.min_height = hi - lo if hi > lo else None
        self.seed_y0 = glyph["y0"]

    def accepts(self, glyph: dict) -> bool:
        glo, ghi = _span(glyph)
        if min(ghi, self.hi) - max(glo, self.lo) > 0:
            return True
        heights = [h for h in (self.min_height, ghi - glo) if h and h > 0]
        tolerance = max(min(heights) * 0.5, 1.0) if heights else 2.0
        return abs(glyph["y0"] - self.seed_y0) <= tolerance

    def add(self, glyph: dict) -> None:
        self.glyphs.append(glyph)
        lo, hi = _span(glyph)
        height = hi - lo
        if height > 0 and (self.min_height is None or height < self.min_height):
            self.min_height = height


def _group_lines(glyphs: list[dict]) -> list[list[dict]]:
    ordered = sorted(glyphs, key=lambda glyph: (-_top(glyph), glyph["x0"], glyph["_i"]))
    lines: list[_Line] = []
    for glyph in ordered:
        for line in reversed(lines):
            if line.accepts(glyph):
                line.add(glyph)
                break
        else:
            lines.append(_Line(glyph))
    result = [line.glyphs for line in lines]
    result.sort(key=lambda line: -max(_top(item) for item in line))
    return result


def _sort_line(line: list[dict]) -> list[dict]:
    return sorted(line, key=lambda glyph: (glyph["x0"], glyph["_i"]))


def _is_digit(ch: str) -> bool:
    code = ord(ch)
    if "0" <= ch <= "9":
        return True
    return 0x0660 <= code <= 0x0669 or 0x06F0 <= code <= 0x06F9


def _is_latin_letter(ch: str) -> bool:
    if unicodedata.category(ch)[:1] != "L":
        return False
    return unicodedata.name(ch, "").startswith("LATIN")


def _is_arabic_letter(ch: str) -> bool:
    if unicodedata.category(ch)[:1] != "L":
        return False
    code = ord(ch)
    return (
        0x0600 <= code <= 0x06FF
        or 0x0750 <= code <= 0x077F
        or 0x0870 <= code <= 0x089F
        or 0x08A0 <= code <= 0x08FF
        or 0xFB50 <= code <= 0xFDFF
        or 0xFE70 <= code <= 0xFEFE
        or 0x1EE00 <= code <= 0x1EEFF
    )


def _char_role(ch: str) -> str:
    if _is_arabic_letter(ch):
        return "R"
    if _is_digit(ch) or _is_latin_letter(ch):
        return "L"
    return "N"


def _text_has_arabic(text: str) -> bool:
    return any(_is_arabic_letter(ch) for ch in text)


def _text_has_digit(text: str) -> bool:
    return any(_is_digit(ch) for ch in text)


def _glyph_role(text: str) -> str:
    roles = {_char_role(ch) for ch in text}
    roles.discard("N")
    if not roles:
        return "N"
    if roles == {"R"}:
        return "R"
    if roles == {"L"}:
        return "L"
    return "M"


def _paren_side(text: str) -> str | None:
    stripped = "".join(ch for ch in text if not ch.isspace())
    if stripped and all(ch in _OPEN_PARENS for ch in stripped):
        return "open"
    if stripped and all(ch in _CLOSE_PARENS for ch in stripped):
        return "close"
    return None


def _number_beside(line: list[dict], roles: list[str], start: int, step: int) -> bool:
    count = len(line)
    cursor = start
    while 0 <= cursor < count:
        role = roles[cursor]
        text = line[cursor]["t"]
        if role == "L" and _text_has_digit(text):
            return True
        if role == "L" and _paren_side(text):
            cursor += step
            continue
        if role == "N" and _paren_side(text) is None:
            cursor += step
            continue
        return False
    return False


def _attach_parentheses(line: list[dict], roles: list[str]) -> None:
    changed = True
    while changed:
        changed = False
        for index, glyph in enumerate(line):
            if roles[index] != "N":
                continue
            side = _paren_side(glyph["t"])
            opens = side == "open" and _number_beside(line, roles, index + 1, 1)
            closes = side == "close" and _number_beside(line, roles, index - 1, -1)
            if opens or closes:
                roles[index] = "L"
                changed = True


def _resolve_neutrals(roles: list[str], embedding: str) -> list[str]:
    resolved = list(roles)
    index = 0
    count = len(resolved)
    while index < count:
        if resolved[index] != "N":
            index += 1
            continue
        start = index
        while index < count and resolved[index] == "N":
            index += 1
        left = resolved[start - 1] if start else None
        right = resolved[index] if index < count else None
        if left == right == "R":
            fill = "R"
        elif left == right == "L":
            fill = "L"
        else:
            fill = embedding
        for cursor in range(start, index):
            resolved[cursor] = fill
    return resolved


def _roles_for_line(line: list[dict]) -> list[str]:
    roles = [_glyph_role(glyph["t"]) for glyph in line]
    _attach_parentheses(line, roles)
    embedding = "R" if any(_text_has_arabic(glyph["t"]) for glyph in line) else "L"
    return _resolve_neutrals(roles, embedding)


def _line_to_logical(line: list[dict]) -> str:
    if not any(_text_has_arabic(glyph["t"]) for glyph in line):
        return "".join(glyph["t"] for glyph in line)

    roles = _roles_for_line(line)
    runs: list[list] = []
    for glyph, role in zip(line, roles):
        if runs and runs[-1][0] == role:
            runs[-1][1].append(glyph)
        else:
            runs.append([role, [glyph]])

    parts: list[str] = []
    for role, group in reversed(runs):
        if role == "R":
            group = group[::-1]
        parts.append("".join(glyph["t"] for glyph in group))
    return "".join(parts)

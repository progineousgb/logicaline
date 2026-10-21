"""Round-trip logical strings through visual glyph placement."""

import unicodedata
import unittest

from logicaline import LogicalineError, logical_lines

LINE_SECTION = "القسم الرئيسي - عدد 5161"
LINE_DATE = "2 جمادى الآخرة 1444 (18 يناير 2023)"
LINE_INDIC = "عدد ٥١٦١"
LINE_ENGLISH = "Invoice 5161"

# Visual left-to-right text for the two mixed lines. Digit runs stay in
# logical order. Arabic runs are reversed. The pieces are the directional
# runs of each logical string.
VISUAL_SECTION = "5161" + "القسم الرئيسي - عدد "[::-1]
VISUAL_DATE = (
    "2023)"
    + " يناير "[::-1]
    + "1444 (18"
    + " جمادى الآخرة "[::-1]
    + "2"
)
VISUAL_INDIC = "٥١٦١" + "عدد "[::-1]

_OPEN_PARENS = frozenset({"(", "\uFD3E"})
_CLOSE_PARENS = frozenset({")", "\uFD3F"})


class Glyph:
    def __init__(self, t, x0, y0):
        self.t = t
        self.x0 = x0
        self.y0 = y0


def _is_digit(ch):
    code = ord(ch)
    return (
        "0" <= ch <= "9"
        or 0x0660 <= code <= 0x0669
        or 0x06F0 <= code <= 0x06F9
    )


def _is_latin(ch):
    return unicodedata.category(ch)[:1] == "L" and unicodedata.name(
        ch, ""
    ).startswith("LATIN")


def _is_arabic(ch):
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


def _role(ch):
    if _is_arabic(ch):
        return "R"
    if _is_digit(ch) or _is_latin(ch):
        return "L"
    return "N"


def _paren_side(ch):
    if ch in _OPEN_PARENS:
        return "open"
    if ch in _CLOSE_PARENS:
        return "close"
    return None


def _number_beside(chars, roles, start, step):
    cursor = start
    count = len(chars)
    while 0 <= cursor < count:
        if roles[cursor] == "L" and _is_digit(chars[cursor]):
            return True
        if roles[cursor] == "L" and _paren_side(chars[cursor]):
            cursor += step
            continue
        if roles[cursor] == "N" and _paren_side(chars[cursor]) is None:
            cursor += step
            continue
        return False
    return False


def _logical_runs(text):
    """Split a logical string into RTL and LTR runs."""
    chars = list(text)
    roles = [_role(ch) for ch in chars]
    changed = True
    while changed:
        changed = False
        for index, ch in enumerate(chars):
            if roles[index] != "N":
                continue
            side = _paren_side(ch)
            if side == "open" and _number_beside(chars, roles, index + 1, 1):
                roles[index] = "L"
                changed = True
            elif side == "close" and _number_beside(chars, roles, index - 1, -1):
                roles[index] = "L"
                changed = True
    embedding = "R" if any(role == "R" for role in roles) else "L"
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
    runs = []
    for ch, role in zip(chars, resolved):
        if runs and runs[-1][0] == role:
            runs[-1][1].append(ch)
        else:
            runs.append([role, [ch]])
    return runs


def place_visually(text, y, step=10.0):
    """Place a logical string the way an RTL line is painted.

    Arabic letters move right to left along x. Digit runs and Latin letters
    move left to right. When the string contains Arabic, runs themselves are
    laid out from right to left.
    """
    runs = _logical_runs(text)
    has_arabic = any(role == "R" for role, _chars in runs)
    visual_runs = []
    if has_arabic:
        for role, chars in reversed(runs):
            visual_runs.append(chars[::-1] if role == "R" else chars)
    else:
        visual_runs = [chars for _role, chars in runs]

    glyphs = []
    x = 0.0
    for chars in visual_runs:
        for ch in chars:
            glyphs.append(
                {
                    "t": ch,
                    "x0": x,
                    "y0": float(y),
                    "x1": x + step * 0.8,
                    "y1": float(y) + 12.0,
                }
            )
            x += step
    return glyphs


def visual_text(glyphs):
    ordered = sorted(glyphs, key=lambda glyph: glyph["x0"])
    return "".join(glyph["t"] for glyph in ordered)


class LogicalLinesTests(unittest.TestCase):
    def test_arabic_section_and_number(self):
        glyphs = place_visually(LINE_SECTION, y=180)
        visual = visual_text(glyphs)
        self.assertEqual(visual, VISUAL_SECTION)
        self.assertIn("5161", visual)
        self.assertNotIn("1615", visual)
        rightmost = max(glyphs, key=lambda glyph: glyph["x0"])
        self.assertEqual(rightmost["t"], "ا")
        self.assertEqual(logical_lines(glyphs), [LINE_SECTION])
        self.assertIn("5161", logical_lines(glyphs)[0])
        self.assertNotIn("1615", logical_lines(glyphs)[0])

    def test_arabic_date_with_parentheses(self):
        glyphs = place_visually(LINE_DATE, y=140)
        visual = visual_text(glyphs)
        self.assertEqual(visual, VISUAL_DATE)
        self.assertIn("1444", visual)
        self.assertIn("2023", visual)
        self.assertIn("(18", visual)
        self.assertNotIn("4441", visual)
        self.assertNotIn("3202", visual)
        self.assertNotIn(")18", visual)
        ordered = sorted(glyphs, key=lambda glyph: glyph["x0"])
        self.assertEqual(ordered[0]["t"], "2")
        self.assertEqual(ordered[-1]["t"], "2")
        result = logical_lines(glyphs)
        self.assertEqual(result, [LINE_DATE])
        self.assertIn("(18", result[0])
        self.assertIn("2023)", result[0])

    def test_pure_english_line(self):
        glyphs = [Glyph(ch, index * 10, 40) for index, ch in enumerate(LINE_ENGLISH)]
        self.assertEqual(logical_lines(glyphs), [LINE_ENGLISH])

    def test_stacked_lines_top_to_bottom(self):
        top = place_visually(LINE_SECTION, y=220)
        bottom = place_visually(LINE_DATE, y=80)
        self.assertEqual(
            logical_lines(top + bottom),
            [LINE_SECTION, LINE_DATE],
        )

    def test_arabic_indic_digits_keep_order(self):
        glyphs = place_visually(LINE_INDIC, y=60)
        visual = visual_text(glyphs)
        self.assertEqual(visual, VISUAL_INDIC)
        digits = "".join(ch for ch in visual if "\u0660" <= ch <= "\u0669")
        self.assertEqual(digits, "٥١٦١")
        result = logical_lines(glyphs)
        self.assertEqual(result, [LINE_INDIC])
        self.assertIn("٥١٦١", result[0])
        self.assertNotIn("١٦١٥", result[0])

    def test_missing_x0_raises(self):
        with self.assertRaises(LogicalineError) as caught:
            logical_lines([{"t": "A", "y0": 10}])
        message = str(caught.exception)
        self.assertIn("x0", message)
        self.assertTrue(message.isascii())

    def test_hand_placed_number_keeps_digit_order(self):
        glyphs = [
            {"t": "5", "x0": 0, "y0": 50},
            {"t": "1", "x0": 10, "y0": 50},
            {"t": "6", "x0": 20, "y0": 50},
            {"t": "1", "x0": 30, "y0": 50},
            {"t": " ", "x0": 40, "y0": 50},
            {"t": "د", "x0": 50, "y0": 50},
            {"t": "د", "x0": 60, "y0": 50},
            {"t": "ع", "x0": 70, "y0": 50},
        ]
        self.assertEqual(logical_lines(glyphs), ["عدد 5161"])

    def test_lam_alef_ligature_stays_intact(self):
        ligature = "\uFEFB"
        glyphs = [
            {"t": ligature, "x0": 0, "y0": 30, "x1": 8, "y1": 42},
            {"t": "ب", "x0": 10, "y0": 30, "x1": 18, "y1": 42},
        ]
        result = logical_lines(glyphs)
        self.assertEqual(result, ["ب" + ligature])
        self.assertIn(ligature, result[0])
        self.assertNotIn("\u0644\u0627", result[0])


if __name__ == "__main__":
    unittest.main()

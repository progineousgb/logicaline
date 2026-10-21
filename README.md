# logicaline

logicaline is a small Python library that restores logical reading order for Arabic text mixed with numbers. You pass glyphs an extractor has already produced. Each glyph has text and a box. logicaline groups those glyphs into lines and returns each line in logical reading order.

Arabic PDF text mixed with numbers often comes out reversed or scrambled when glyphs are read from left to right. That ordering bug is tracked in [pypdf issue 1629](https://github.com/py-pdf/pypdf/issues/1629). logicaline runs after extraction. The input is visual order, the order of the glyphs on the page. The output is logical order, the order in which the text is read.

## What you get

`logical_lines` returns a `list[str]`, one string per line, from the top of the page to the bottom. On a line that contains Arabic, runs are emitted from right to left, and characters inside an Arabic run are reversed. Western digits, Arabic-Indic digits, extended Arabic-Indic digits, and Latin letters keep the order they have on the page, so 5161 stays 5161. Parentheses that belong to a number stay around that number. A line with no Arabic stays left to right. Glyph text is joined as given, with nothing inserted between glyphs.

## Install

Install from this repository. logicaline is not published on PyPI.

```bash
pip install "git+https://github.com/progineousgb/logicaline.git"
```

Requires Python 3.11 or newer. The library has no third-party dependencies.

## Example

The strings below are visual left-to-right glyph order. Arabic runs are reversed. The numbers 5161, 1444, 18, and 2023 are already in logical digit order.

```python
from logicaline import logical_lines


def glyphs_ltr(text, y):
    return [
        {"t": ch, "x0": i * 10, "y0": y, "x1": i * 10 + 8, "y1": y + 12}
        for i, ch in enumerate(text)
    ]


glyphs = glyphs_ltr("5161 ددع - يسيئرلا مسقلا", 200)
glyphs += glyphs_ltr("2023) رياني 1444 (18 ةرخآلا ىدامج 2", 100)
print(logical_lines(glyphs))
```

```text
['القسم الرئيسي - عدد 5161', '2 جمادى الآخرة 1444 (18 يناير 2023)']
```

## API

```python
from logicaline import logical_lines, LogicalineError

lines = logical_lines([
    {"t": "...", "x0": 210, "y0": 100, "x1": 222, "y1": 114},
])
```

`lines` is a `list[str]`. A glyph may be a dict or an object with attributes `t`, `x0`, `y0`, `x1`, and `y1`. `x1` and `y1` are optional. Every glyph needs `t`, `x0`, and `y0`. Invalid input raises `LogicalineError` with an English message.

Coordinates follow PDF user space: `x` increases to the right and `y` increases upward. Lines are ordered from the top of the page downward. On each line, increasing `x0` is visual left-to-right order.

Glyphs share a line when their vertical ranges overlap, or when their `y0` values are close. Each glyph is classified as Arabic (letters and presentation forms, including a lam-alef ligature), left to right (Western digits, Arabic-Indic digits, extended Arabic-Indic digits, and Latin letters), or neutral (spaces and punctuation). Neutrals between two Arabic runs join the Arabic run. Neutrals between two left-to-right runs join that run. Parentheses around a number stay on that number.

If the line contains Arabic, runs are emitted from right to left. Characters are reversed inside Arabic runs only. Left-to-right runs keep their characters in order. A line with no Arabic is returned from left to right. A lam-alef ligature stays the glyph you passed.

## Limits

- logicaline is not a PDF parser. It does not open PDF files, and it does not depend on pypdf or PyMuPDF.
- It does not reshape Arabic. Shaping is the extractor's job. Pass a lam-alef ligature through as that glyph.
- Multi-column pages are not supported. Glyphs that share a vertical band become one line, so columns on that band are merged.
- Edge punctuation can still be ambiguous. Parentheses around a number stay with that number. Other mirrored brackets, and neutrals sitting on the boundary between Arabic and a number, can still land on either side.

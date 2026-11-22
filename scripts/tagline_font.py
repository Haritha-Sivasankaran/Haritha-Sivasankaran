"""JetBrains Mono Italic 500 (SIL Open Font License), subset to the tagline's characters.

Only the characters in the current tagline (plus quotes) are included. If CARD_TAGLINE changes,
re-download a subset from Google Fonts with the css2 `text=` parameter and replace this string.
"""

TAGLINE_FONT_WOFF2_B64 = (
    "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"
)

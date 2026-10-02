# font-peek

Inspect basic metadata in standalone TrueType (`.ttf`) and OpenType (`.otf`) font files using Python's standard library.

```sh
python font_peek.py Example.ttf Another.otf
```

It reports the outline flavor, units per em, glyph count, and available family, subfamily, full, version, and PostScript names. It reads local font files only; it does not render glyphs, validate every font table, or execute embedded content. Collections (`.ttc`) and web-font formats (`.woff`/`.woff2`) are not supported.

The parser follows the standalone SFNT directory and `name` table layout described in the [OpenType font file specification](https://learn.microsoft.com/en-us/typography/opentype/spec/otff) and [OpenType `name` table specification](https://learn.microsoft.com/en-us/typography/opentype/spec/name).

## License

MIT

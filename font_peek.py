#!/usr/bin/env python3
"""Read basic metadata from standalone TrueType and OpenType font files."""

import argparse
from pathlib import Path
import struct
import sys


SIGNATURES = {
    b"\x00\x01\x00\x00": "TrueType outlines",
    b"OTTO": "OpenType CFF outlines",
    b"true": "legacy TrueType outlines",
}
NAMES = (
    ("Family", (16, 1)),
    ("Subfamily", (17, 2)),
    ("Full name", (4,)),
    ("Version", (5,)),
    ("PostScript name", (6,)),
)


def read_at(source, offset, length, file_size, label):
    if offset < 0 or length < 0 or offset > file_size or length > file_size - offset:
        raise ValueError(f"{label} points outside the file")
    source.seek(offset)
    data = source.read(length)
    if len(data) != length:
        raise ValueError(f"truncated {label}")
    return data


def decode_name(platform, encoding, data):
    if platform in (0, 3):
        return data.decode("utf-16-be").strip().replace("\x00", "")
    if platform == 1 and encoding == 0:
        return data.decode("mac_roman").strip().replace("\x00", "")
    return ""


def preferred_name(source, file_size, table, wanted_ids):
    if table is None:
        return ""
    offset, length = table
    if length < 6:
        raise ValueError("name table is shorter than its header")
    fmt, count, storage = struct.unpack(">HHH", read_at(source, offset, 6, file_size, "name table"))
    if fmt not in (0, 1):
        raise ValueError(f"unsupported name table format {fmt}")
    record_bytes = count * 12
    records_end = 6 + record_bytes
    if records_end > length:
        raise ValueError("invalid name table record or string offsets")
    metadata_end = records_end
    if fmt == 1:
        if records_end + 2 > length:
            raise ValueError("truncated name language-tag count")
        tag_count = struct.unpack(">H", read_at(source, offset + records_end, 2, file_size, "language-tag count"))[0]
        tag_bytes = tag_count * 4
        metadata_end += 2 + tag_bytes
        if metadata_end > length:
            raise ValueError("truncated name language-tag records")
        tags = read_at(source, offset + records_end + 2, tag_bytes, file_size, "language-tag records")
        for index in range(tag_count):
            size, string_offset = struct.unpack_from(">HH", tags, index * 4)
            if string_offset > length - storage or size > length - storage - string_offset:
                raise ValueError("language tag points outside the name table")
    if storage < metadata_end or storage > length:
        raise ValueError("invalid name table record or string offsets")
    records = read_at(source, offset + 6, record_bytes, file_size, "name records")
    candidates = {}
    for index in range(count):
        platform, encoding, language, name_id, size, string_offset = struct.unpack_from(">HHHHHH", records, index * 12)
        if string_offset > length - storage or size > length - storage - string_offset:
            raise ValueError("name string points outside the name table")
        if name_id not in wanted_ids or platform not in (0, 1, 3):
            continue
        raw = read_at(source, offset + storage + string_offset, size, file_size, "name string")
        try:
            value = decode_name(platform, encoding, raw)
        except UnicodeError as error:
            raise ValueError(f"invalid encoding in name record {name_id}") from error
        if value:
            language_rank = 0 if (platform == 3 and language == 0x0409) or (platform == 0 and language == 0) else 1
            candidates.setdefault(name_id, []).append((language_rank, index, value))
    return {
        name_id: min(values)[2]
        for name_id, values in candidates.items()
    }


def inspect(path):
    file_size = path.stat().st_size
    with path.open("rb") as source:
        header = read_at(source, 0, 12, file_size, "font header")
        signature, table_count = struct.unpack_from(">4sH", header)
        if signature not in SIGNATURES:
            raise ValueError("not a supported standalone TrueType/OpenType font")
        if table_count == 0:
            raise ValueError("font has no tables")
        directory = read_at(source, 12, table_count * 16, file_size, "table directory")
        tables = {}
        for index in range(table_count):
            tag, _, offset, length = struct.unpack_from(">4sIII", directory, index * 16)
            if offset > file_size or length > file_size - offset:
                raise ValueError(f"{tag.decode('ascii', 'replace')} table points outside the file")
            if tag in tables:
                raise ValueError(f"duplicate {tag.decode('ascii', 'replace')} table")
            tables[tag] = (offset, length)

        output = [f"{path}: {SIGNATURES[signature]}"]
        head = tables.get(b"head")
        if head is not None:
            if head[1] < 20:
                raise ValueError("head table is shorter than required metadata")
            units = struct.unpack(">H", read_at(source, head[0] + 18, 2, file_size, "units per em"))[0]
            output.append(f"  Units per em: {units}")
        maxp = tables.get(b"maxp")
        if maxp is not None:
            if maxp[1] < 6:
                raise ValueError("maxp table is shorter than required metadata")
            glyphs = struct.unpack(">H", read_at(source, maxp[0] + 4, 2, file_size, "glyph count"))[0]
            output.append(f"  Glyphs: {glyphs}")
        names = preferred_name(source, file_size, tables.get(b"name"), {item for _, ids in NAMES for item in ids})
        for label, ids in NAMES:
            value = next((names[name_id] for name_id in ids if name_id in names), "")
            if value:
                output.append(f"  {label}: {value}")
        return output


def main():
    parser = argparse.ArgumentParser(description="Show basic metadata from standalone .ttf and .otf fonts.")
    parser.add_argument("fonts", nargs="+", type=Path, help="font files to inspect")
    args = parser.parse_args()
    failed = False
    for path in args.fonts:
        try:
            if not path.is_file():
                raise ValueError("not a file")
            print("\n".join(inspect(path)))
        except (OSError, ValueError) as error:
            print(f"font-peek: {path}: {error}", file=sys.stderr)
            failed = True
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())

"""Minimal read-only XLSX cell reader for offline human-review validators."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_REL_NS = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
_DOC_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _column_index(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference)
    if letters is None:
        raise ValueError("invalid cell reference")
    value = 0
    for character in letters.group(0):
        value = value * 26 + ord(character) - 64
    return value - 1


def _shared_strings(archive: zipfile.ZipFile) -> tuple[str, ...]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return ()
    return tuple("".join(node.itertext()) for node in root.findall("m:si", _NS))


def _sheet_paths(archive: zipfile.ZipFile) -> dict[str, str]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relations = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        item.attrib["Id"]: item.attrib["Target"]
        for item in relations.findall("r:Relationship", _REL_NS)
    }
    result = {}
    for sheet in workbook.findall("m:sheets/m:sheet", _NS):
        relationship = sheet.attrib[f"{{{_DOC_REL}}}id"]
        target = targets[relationship].lstrip("/")
        result[sheet.attrib["name"]] = target if target.startswith("xl/") else f"xl/{target}"
    return result


def _sheet_values(
    archive: zipfile.ZipFile, path: str, shared: tuple[str, ...]
) -> dict[int, list[str]]:
    root = ET.fromstring(archive.read(path))
    rows: dict[int, list[str]] = {}
    for row in root.findall("m:sheetData/m:row", _NS):
        row_number = int(row.attrib["r"])
        values: dict[int, str] = {}
        for cell in row.findall("m:c", _NS):
            index = _column_index(cell.attrib["r"])
            cell_type = cell.attrib.get("t")
            if cell_type == "inlineStr":
                node = cell.find("m:is", _NS)
                value = "" if node is None else "".join(node.itertext())
            else:
                node = cell.find("m:v", _NS)
                raw = "" if node is None or node.text is None else node.text
                value = shared[int(raw)] if cell_type == "s" and raw else raw
            values[index] = value
        width = max(values, default=-1) + 1
        rows[row_number] = [values.get(index, "") for index in range(width)]
    return rows


def read_workbook(path: Path) -> dict[str, dict[int, list[str]]]:
    with zipfile.ZipFile(path) as archive:
        shared = _shared_strings(archive)
        return {
            name: _sheet_values(archive, sheet_path, shared)
            for name, sheet_path in _sheet_paths(archive).items()
        }


def cell(rows: dict[int, list[str]], row: int, column: int) -> str:
    values = rows.get(row, [])
    return values[column] if column < len(values) else ""

#!/usr/bin/env python3
"""Parse and validate the README-backed Awesome KyoAni catalog."""

from __future__ import annotations

import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


ENTRY_RE = re.compile(r"^- \[([^\]]+)]\((https://[^)]+)\) - (.+)$")
TOC_RE = re.compile(r"^\s*- \[([^\]]+)]\(#([^)]+)\)$")
HEADING_RE = re.compile(r"^(#{2,3})\s+(.+?)\s*$")
SCOPE_RE = re.compile(r"^_[^_].*_$")
CATALOG_END = "Contributing"
NON_CATALOG_HEADINGS = {"Contents", "Contributing", "Footnotes"}


@dataclass(frozen=True)
class CatalogEntry:
    """One canonical README catalog entry."""

    name: str
    url: str
    description: str
    section: str
    line: int


@dataclass(frozen=True)
class Catalog:
    """Validated catalog data for quality checks and future consumers."""

    entries: tuple[CatalogEntry, ...]
    sections: tuple[str, ...]


class CatalogValidationError(ValueError):
    """Raised when one or more catalog invariants fail."""

    def __init__(self, issues: list[tuple[int, str]]) -> None:
        self.issues = tuple(issues)
        super().__init__("; ".join(message for _, message in issues))


def github_slug(title: str) -> str:
    """Return the GitHub-style heading slug used by this catalog's TOC."""

    title = re.sub(r"[`*_]", "", title.strip().lower())
    characters: list[str] = []
    for character in title:
        if character == "-" or not unicodedata.category(character).startswith(("P", "S")):
            characters.append(character)
    return "".join(characters).replace(" ", "-")


def normalize_url(url: str) -> str:
    """Normalize differences that must not create multiple catalog entries."""

    parts = urlsplit(url)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def alphabetical_key(value: str) -> str:
    """Return a case-insensitive human-facing key that ignores punctuation."""

    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum() or character.isspace())


def _next_content_line(lines: list[str], start: int) -> tuple[int, str] | None:
    for index in range(start, len(lines)):
        if lines[index].strip():
            return index + 1, lines[index]
    return None


def parse_catalog(markdown: str) -> Catalog:
    """Parse and validate catalog Markdown, raising all discovered issues."""

    lines = markdown.splitlines()
    issues: list[tuple[int, str]] = []
    entries: list[CatalogEntry] = []
    section_entries: dict[str, list[CatalogEntry]] = {}
    section_lines: dict[str, int] = {}
    catalog_headings: list[tuple[str, str, int]] = []
    toc: list[tuple[str, str, int]] = []
    work_sections: list[tuple[str, int]] = []
    current_h2 = ""
    current_h3 = ""
    in_contents = False
    catalog_started = False

    for index, line in enumerate(lines, start=1):
        heading = HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2)

            if level == 2:
                current_h2 = title
                current_h3 = ""
                in_contents = title == "Contents"
                if title == CATALOG_END:
                    break
                if title not in NON_CATALOG_HEADINGS:
                    catalog_started = True
                    catalog_headings.append((title, github_slug(title), index))
                    section_lines[title] = index
                    section_entries.setdefault(title, [])
                    scope = _next_content_line(lines, index)
                    if scope is None or not SCOPE_RE.fullmatch(scope[1]):
                        issues.append((index, f"section {title!r} must start with one italic scope sentence"))
                continue

            if level == 3 and current_h2 == "Works":
                current_h3 = title
                section = f"Works / {title}"
                catalog_headings.append((title, github_slug(title), index))
                work_sections.append((title, index))
                section_lines[section] = index
                section_entries.setdefault(section, [])
                continue

        if in_contents:
            toc_item = TOC_RE.match(line)
            if toc_item:
                toc.append((toc_item.group(1), toc_item.group(2), index))
            continue

        if not catalog_started:
            continue

        if line.startswith("- ["):
            match = ENTRY_RE.fullmatch(line)
            if not match:
                issues.append((index, "catalog entry does not match the canonical Markdown format"))
                continue

            name, url, description = match.groups()
            if current_h2 == "Works":
                if not current_h3:
                    issues.append((index, "entries under Works must belong to a work subsection"))
                    continue
                section = f"Works / {current_h3}"
            else:
                section = current_h2

            entry = CatalogEntry(name, url, description, section, index)
            entries.append(entry)
            section_entries.setdefault(section, []).append(entry)

            if not description or not (description[0].isupper() or description[0].isdigit()):
                issues.append((index, "description must start with an uppercase character"))
            if not description.endswith("."):
                issues.append((index, "description must end with a period"))

    expected_toc = [(name, anchor) for name, anchor, _ in catalog_headings]
    actual_toc = [(name, anchor) for name, anchor, _ in toc]
    if actual_toc != expected_toc:
        line = toc[0][2] if toc else 1
        issues.append((line, "Contents must list every catalog heading in README order with its GitHub anchor"))

    for section, section_line in section_lines.items():
        if section == "Works":
            continue
        if not section_entries.get(section):
            issues.append((section_line, f"section {section!r} must not be empty"))

    actual_works = [name for name, _ in work_sections]
    expected_works = sorted(actual_works, key=alphabetical_key)
    if actual_works != expected_works:
        line = work_sections[0][1] if work_sections else 1
        issues.append((line, "Works subsections must be alphabetized"))

    for section, items in section_entries.items():
        if section == "Works" or not items:
            continue
        actual_names = [entry.name for entry in items]
        expected_names = sorted(actual_names, key=alphabetical_key)
        if actual_names != expected_names:
            issues.append((items[0].line, f"entries in {section!r} must be alphabetized"))

    names: dict[str, CatalogEntry] = {}
    urls: dict[str, CatalogEntry] = {}
    for entry in entries:
        name_key = entry.name.casefold()
        if name_key in names:
            first = names[name_key]
            issues.append((entry.line, f"duplicate entry name also used on line {first.line}: {entry.name}"))
        else:
            names[name_key] = entry

        url_key = normalize_url(entry.url)
        if url_key in urls:
            first = urls[url_key]
            issues.append((entry.line, f"duplicate resource URL also used on line {first.line}: {entry.url}"))
        else:
            urls[url_key] = entry

    if not entries:
        issues.append((1, "catalog contains no entries"))

    if issues:
        issues.sort(key=lambda issue: (issue[0], issue[1]))
        raise CatalogValidationError(issues)

    populated_sections = tuple(
        section for section, items in section_entries.items() if section != "Works" and items
    )
    return Catalog(tuple(entries), populated_sections)


def main(argv: list[str] | None = None) -> int:
    arguments = argv if argv is not None else sys.argv[1:]
    if len(arguments) != 1:
        print("usage: python3 tools/catalog.py README.md", file=sys.stderr)
        return 2

    path = Path(arguments[0])
    try:
        catalog = parse_catalog(path.read_text(encoding="utf-8"))
    except CatalogValidationError as error:
        for line, message in error.issues:
            print(f"{path}:{line}: {message}", file=sys.stderr)
        return 1

    print(f"Validated {len(catalog.entries)} entries in {len(catalog.sections)} sections.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

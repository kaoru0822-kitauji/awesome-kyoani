from __future__ import annotations

import textwrap
import unittest

from tools.catalog import (
    CatalogValidationError,
    alphabetical_key,
    github_slug,
    normalize_url,
    parse_catalog,
)


def document(entries: str, *, toc_anchor: str = "resources", scope: str = "_Useful resources._") -> str:
    return (
        "# Awesome Test\n\n"
        "## Contents\n\n"
        f"- [Resources](#{toc_anchor})\n\n"
        "## Resources\n\n"
        f"{scope}\n\n"
        f"{entries}\n\n"
        "## Contributing\n\n"
        "Done.\n"
    )


class CatalogTests(unittest.TestCase):
    def test_valid_catalog(self) -> None:
        catalog = parse_catalog(
            document(
                "- [Alpha](https://example.com/alpha) - An alpha resource.\n"
                "- [Beta](https://example.com/beta) - A beta resource."
            )
        )
        self.assertEqual([entry.name for entry in catalog.entries], ["Alpha", "Beta"])
        self.assertEqual(catalog.sections, ("Resources",))

    def test_rejects_malformed_entry(self) -> None:
        with self.assertRaisesRegex(CatalogValidationError, "canonical Markdown format"):
            parse_catalog(document("- [Alpha](https://example.com/alpha): Wrong separator."))

    def test_rejects_non_https_entry(self) -> None:
        with self.assertRaisesRegex(CatalogValidationError, "canonical Markdown format"):
            parse_catalog(document("- [Alpha](http://example.com/alpha) - An alpha resource."))

    def test_rejects_bad_description(self) -> None:
        with self.assertRaises(CatalogValidationError) as caught:
            parse_catalog(document("- [Alpha](https://example.com/alpha) - bad description"))
        messages = [message for _, message in caught.exception.issues]
        self.assertIn("description must start with an uppercase character", messages)
        self.assertIn("description must end with a period", messages)

    def test_rejects_duplicate_names_case_insensitively(self) -> None:
        with self.assertRaisesRegex(CatalogValidationError, "duplicate entry name"):
            parse_catalog(
                document(
                    "- [Alpha](https://example.com/one) - The first resource.\n"
                    "- [alpha](https://example.com/two) - The second resource."
                )
            )

    def test_rejects_normalized_duplicate_urls_across_sections(self) -> None:
        markdown = textwrap.dedent(
            """\
            # Awesome Test

            ## Contents

            - [Resources](#resources)
            - [Works](#works)
              - [Example Work](#example-work)

            ## Resources

            _Useful resources._

            - [Alpha](https://example.com/item/) - The first placement.

            ## Works

            _Work resources._

            ### Example Work

            - [Beta](https://EXAMPLE.com/item#details) - The duplicate placement.

            ## Contributing
            """
        )
        with self.assertRaisesRegex(CatalogValidationError, "duplicate resource URL"):
            parse_catalog(markdown)

    def test_rejects_entry_order(self) -> None:
        with self.assertRaisesRegex(CatalogValidationError, "must be alphabetized"):
            parse_catalog(
                document(
                    "- [Beta](https://example.com/beta) - A beta resource.\n"
                    "- [Alpha](https://example.com/alpha) - An alpha resource."
                )
            )

    def test_rejects_stale_toc_anchor(self) -> None:
        with self.assertRaisesRegex(CatalogValidationError, "Contents must list"):
            parse_catalog(document("- [Alpha](https://example.com/alpha) - An alpha resource.", toc_anchor="wrong"))

    def test_rejects_missing_scope_sentence(self) -> None:
        with self.assertRaisesRegex(CatalogValidationError, "italic scope sentence"):
            parse_catalog(document("- [Alpha](https://example.com/alpha) - An alpha resource.", scope="Plain text."))

    def test_rejects_empty_section(self) -> None:
        with self.assertRaisesRegex(CatalogValidationError, "must not be empty"):
            parse_catalog(document("Plain text without an entry."))

    def test_slug_matches_punctuation_heavy_titles(self) -> None:
        self.assertEqual(github_slug("K-On!"), "k-on")
        self.assertEqual(
            github_slug("Love, Chunibyo & Other Delusions"),
            "love-chunibyo--other-delusions",
        )

    def test_url_normalization_preserves_query(self) -> None:
        self.assertEqual(
            normalize_url("https://EXAMPLE.com/path/?id=1#top"),
            "https://example.com/path?id=1",
        )

    def test_alphabetical_key_ignores_title_punctuation(self) -> None:
        names = ["K-On!", "Kanon", "KyoAni.cn", "KyoAni FR"]
        self.assertEqual(
            sorted(names, key=alphabetical_key),
            ["Kanon", "K-On!", "KyoAni FR", "KyoAni.cn"],
        )


if __name__ == "__main__":
    unittest.main()

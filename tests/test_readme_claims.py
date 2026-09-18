from __future__ import annotations

import re
import sys
import unittest
from argparse import _SubParsersAction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import harness  # noqa: E402

README = (ROOT / "README.md").read_text(encoding="utf-8")


def _int(pattern: str) -> int:
    match = re.search(pattern, README)
    assert match, f"README no longer states: {pattern}"
    return int(match.group(1))


def _top_level_commands() -> list[str]:
    for action in harness.build_parser()._actions:
        if isinstance(action, _SubParsersAction):
            return sorted(action.choices)
    raise AssertionError("harness parser has no subcommands")


class ReadmeClaimTest(unittest.TestCase):
    """The front-page counts are claims, so they are checked like claims."""

    def test_schema_count(self) -> None:
        self.assertEqual(
            _int(r"\[!\[schemas: (\d+)\]"),
            len(list((ROOT / "schemas").glob("*.schema.json"))),
        )

    def test_cli_command_count(self) -> None:
        self.assertEqual(_int(r"harness CLI — (\d+) commands"), len(_top_level_commands()))

    def test_mcp_tool_surface_counts(self) -> None:
        from mcp_server import MUTATING_TOOL_NAMES, tool_surface

        self.assertEqual(_int(r"(\d+) read-only tools"), len(tool_surface(False)))
        self.assertEqual(_int(r"(\d+) opt-in mutating tool"), len(MUTATING_TOOL_NAMES))
        self.assertEqual(tool_surface(True), sorted(set(tool_surface(False)) | set(MUTATING_TOOL_NAMES)))

    def test_poster_image_exists(self) -> None:
        match = re.search(r"!\[[^\]]*\]\((assets/[^)]+)\)", README)
        self.assertIsNotNone(match, "README must embed the poster from assets/")
        self.assertTrue((ROOT / match.group(1)).is_file(), match.group(1))


if __name__ == "__main__":
    unittest.main()

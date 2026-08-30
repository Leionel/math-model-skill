from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from claims.compile_writer_package import select_writer_patterns  # noqa: E402


class WriterPatternsTest(unittest.TestCase):
    def test_patterns_follow_existing_units_and_scope(self) -> None:
        plan = {
            "argument_units": [
                {"unit_id": "U-FRAME", "rhetorical_role": "problem_tension"},
                {"unit_id": "U-MODEL", "rhetorical_role": "model_choice"},
                {"unit_id": "U-RESULT", "rhetorical_role": "result_observation"},
                {
                    "unit_id": "U-BRIDGE",
                    "rhetorical_role": "comparison",
                    "scope": {"type": "cross_question", "question_ids": ["q1", "q2"]},
                },
                {"unit_id": "U-BOUNDARY", "rhetorical_role": "boundary"},
            ]
        }

        cards = {row["pattern_id"]: row for row in select_writer_patterns(plan)}

        self.assertEqual(
            set(cards),
            {
                "problem_framing",
                "model_exposition",
                "alternative_rejection",
                "result_interpretation",
                "cross_question_synthesis",
                "model_critique",
            },
        )
        self.assertEqual(cards["cross_question_synthesis"]["unit_ids"], ["U-BRIDGE"])
        self.assertIn("U-MODEL", cards["model_exposition"]["unit_ids"])
        self.assertIn("U-BOUNDARY", cards["model_critique"]["unit_ids"])
        self.assertIn("moves", cards["result_interpretation"])


if __name__ == "__main__":
    unittest.main()

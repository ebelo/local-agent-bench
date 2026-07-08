import unittest

from local_agent_bench.judge import JUDGE_FAIL, JUDGE_PARTIAL, _parse_judge_response


class JudgeParserTest(unittest.TestCase):
    def test_parses_clean_judge_json(self) -> None:
        result = _parse_judge_response(
            '{"verdict": "PARTIAL", "score": 0.5, "reasoning": "Used bash but answer was incomplete."}'
        )

        self.assertEqual(result["judge_verdict"], JUDGE_PARTIAL)
        self.assertEqual(result["judge_score"], 0.5)
        self.assertIn("Used bash", result["judge_reasoning"])

    def test_recovers_from_truncated_reasoning_json(self) -> None:
        result = _parse_judge_response(
            '{"verdict": "FAIL", "score": 0.0, "reasoning": "The agent did not read the fixture note'
        )

        self.assertEqual(result["judge_verdict"], JUDGE_FAIL)
        self.assertEqual(result["judge_score"], 0.0)


if __name__ == "__main__":
    unittest.main()

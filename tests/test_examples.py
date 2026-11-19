import runpy
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "tools" / "examples.py"


class ExampleTests(unittest.TestCase):
    def test_committed_examples_match_the_renderer(self):
        scenes = runpy.run_path(str(TOOL))["scenes"]
        for path, svg in scenes():
            with self.subTest(example=path.name):
                self.assertEqual(path.read_text(encoding="utf-8"), svg)


if __name__ == "__main__":
    unittest.main()

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from github_island.__main__ import main
from github_island.growth import advance
from github_island.models import canonical_json
from github_island.render import render
from github_island.state import read_json

FIXTURE = Path(__file__).parent / "fixtures" / "reviews.json"


class DrawTests(unittest.TestCase):
    def run_main(self, *argv):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = main(list(argv))
        return code, errors.getvalue()

    def test_draw_writes_the_image_for_a_state_file(self):
        state = advance(read_json(FIXTURE))
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "state.json"
            target = Path(directory) / "island.svg"
            source.write_text(canonical_json(state), encoding="utf-8")
            code, _ = self.run_main("draw", "--state", str(source), str(target))
            self.assertEqual(code, 0)
            self.assertEqual(target.read_bytes(), render(state))

    def test_draw_rejects_an_invalid_state(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "state.json"
            target = Path(directory) / "island.svg"
            source.write_text("{}", encoding="utf-8")
            code, errors = self.run_main("draw", "--state", str(source), str(target))
            self.assertEqual(code, 1)
            self.assertIn("error:", errors)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()

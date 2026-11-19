import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from github_island.__main__ import main
from github_island.render import DEFAULT, render_scene


class CliTests(unittest.TestCase):
    def run_main(self, *argv):
        with contextlib.redirect_stdout(io.StringIO()):
            return main(list(argv))

    def test_scene_writes_the_rendered_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "scene.svg"
            code = self.run_main(
                "scene",
                str(target),
                "--profile",
                "1,0,0.5,0,1",
                "--transparent",
                "--key",
                "k",
            )
            self.assertEqual(code, 0)
            traits = dict(zip(DEFAULT, (1, 0, 0.5, 0, 1)))
            self.assertEqual(
                target.read_text(encoding="utf-8"),
                render_scene(traits, transparent=True, key="k"),
            )

    def test_scene_rejects_a_malformed_profile(self):
        for value in ("1,2", "1,1,1,1,2", "a,b,c,d,e"):
            with (
                self.subTest(profile=value),
                tempfile.TemporaryDirectory() as directory,
            ):
                with (
                    contextlib.redirect_stderr(io.StringIO()),
                    self.assertRaises(SystemExit),
                ):
                    self.run_main(
                        "scene", str(Path(directory) / "x.svg"), "--profile", value
                    )


if __name__ == "__main__":
    unittest.main()

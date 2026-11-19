"""The playground site is the page plus exactly the modules the renderer needs."""

import json
import re
import runpy
import tempfile
import unittest
from pathlib import Path

from github_island.growth import CAPS
from github_island.render import STAGE_GROWTH

ROOT = Path(__file__).resolve().parents[1]
TOOL = runpy.run_path(str(ROOT / "tools" / "playground.py"))
PAGE = (ROOT / "playground" / "index.html").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
PACKAGE = ROOT / "src" / "github_island"


class BuildTests(unittest.TestCase):
    def test_build_copies_the_page_and_the_listed_modules_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            site = TOOL["build"](Path(directory) / "site")
            self.assertEqual((site / "index.html").read_text(encoding="utf-8"), PAGE)
            listed = json.loads((site / "py" / "modules.json").read_text())
            self.assertEqual(listed, list(TOOL["MODULES"]))
            copied = sorted(p.stem for p in (site / "py" / "github_island").iterdir())
            self.assertEqual(copied, sorted(TOOL["MODULES"]))
            for name in listed:
                self.assertEqual(
                    (site / "py" / "github_island" / f"{name}.py").read_bytes(),
                    (PACKAGE / f"{name}.py").read_bytes(),
                )
            self.assertTrue((site / ".nojekyll").exists())

    def test_the_listed_modules_import_only_each_other(self):
        for name in TOOL["MODULES"]:
            source = (PACKAGE / f"{name}.py").read_text(encoding="utf-8")
            needed = set(re.findall(r"^\s*from \.(\w+) import", source, re.MULTILINE))
            with self.subTest(module=name):
                self.assertEqual(needed - set(TOOL["MODULES"]), set())

    def test_the_site_leaves_out_network_and_publication_code(self):
        self.assertIn("render", TOOL["MODULES"])
        for name in ("github", "normalize", "probe", "publish", "generate", "__main__"):
            self.assertNotIn(name, TOOL["MODULES"])


class PageTests(unittest.TestCase):
    def test_the_runtime_is_pinned_to_one_version(self):
        sources = re.findall(r'<script src="([^"]+)"', PAGE)
        self.assertEqual(len(sources), 1)
        self.assertRegex(
            sources[0],
            r"^https://cdn\.jsdelivr\.net/pyodide/v\d+\.\d+\.\d+/full/pyodide\.js$",
        )

    def test_the_page_loads_the_module_list_that_the_tool_writes(self):
        self.assertIn('fetch("py/modules.json")', PAGE)
        self.assertIn("py/github_island/${name}.py", PAGE)

    def test_signals_and_stages_on_the_page_exist_in_the_renderer(self):
        block = PAGE[PAGE.index("const SIGNALS") : PAGE.index("const PRESETS")]
        signals = re.findall(r'^\s+\["(\w+)", "', block, re.MULTILINE)
        self.assertEqual(len(signals), 6)
        self.assertEqual(set(signals) - set(CAPS), set())
        presets = PAGE[PAGE.index("const PRESETS") : PAGE.index("const BUDGET")]
        stages = set(re.findall(r'stage: "(\w+)"', presets))
        self.assertTrue(stages)
        self.assertEqual(stages - set(STAGE_GROWTH), set())
        for name in signals:
            self.assertEqual(len(re.findall(rf"\b{name}: [0-9.]+", presets)), 5)

    def test_the_page_calls_the_renderer_and_no_copy_of_it(self):
        self.assertIn(
            "from github_island.render import STAGE_GROWTH, render_scene", PAGE
        )
        self.assertIn("from github_island.growth import CAPS", PAGE)


class WorkflowTests(unittest.TestCase):
    def test_actions_are_pinned_to_full_commits(self):
        uses = re.findall(r"uses: (\S+)", WORKFLOW)
        self.assertEqual(len(uses), 4)
        for action in uses:
            with self.subTest(action=action):
                self.assertRegex(action, r"^actions/[\w-]+@[0-9a-f]{40}$")

    def test_only_the_deploy_job_holds_permissions(self):
        self.assertIn("\npermissions: {}\n", WORKFLOW)
        self.assertEqual(
            re.findall(
                r"^      (\S+): (\S+)$",
                WORKFLOW.split("    permissions:")[1].split("    environment:")[0],
                re.MULTILINE,
            ),
            [("contents", "read"), ("pages", "write"), ("id-token", "write")],
        )

    def test_it_deploys_only_from_the_default_branch_of_this_repository(self):
        self.assertIn("github.repository == 'AndrewDongminYoo/github-island'", WORKFLOW)
        self.assertIn("github.event.repository.default_branch", WORKFLOW)
        self.assertIn("python3 tools/playground.py _site", WORKFLOW)


if __name__ == "__main__":
    unittest.main()

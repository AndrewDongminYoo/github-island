"""The README shows the published image from its stable address."""

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

from github_island.bundle import SVG
from github_island.publish import BRANCH

README = Path(__file__).resolve().parents[1] / "README.md"
EMBED = (
    f"https://raw.githubusercontent.com/AndrewDongminYoo/github-island/{BRANCH}/{SVG}"
)


class Images(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            self.images.append(dict(attrs))


def embeds(text):
    parser = Images()
    parser.feed(text)
    return [image for image in parser.images if image.get("src") == EMBED]


class ReadmeTests(unittest.TestCase):
    def test_readme_embeds_the_published_image_once_with_a_description(self):
        found = embeds(README.read_text(encoding="utf-8"))
        self.assertEqual(len(found), 1)
        self.assertGreater(len(found[0].get("alt", "").strip()), 20)

    def test_the_check_fails_on_a_wrong_branch_or_an_empty_description(self):
        text = README.read_text(encoding="utf-8")
        self.assertEqual(embeds(text.replace(f"/{BRANCH}/", "/main/")), [])
        blank = re.sub(r'(<img src="[^"]+") alt="[^"]*"', r'\1 alt=""', text)
        self.assertEqual(embeds(blank)[0]["alt"], "")

    def test_the_embed_matches_the_published_file_name_and_branch(self):
        self.assertTrue(EMBED.endswith("/output/island.svg"))


if __name__ == "__main__":
    unittest.main()

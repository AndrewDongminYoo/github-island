"""Contributions to repositories the subject does not own: collection to image."""

import copy
import re
import unittest
from datetime import date

from test_growth import snapshot
from test_normalize import FixtureClient, event, page

from github_island.config import Config
from github_island.growth import CAPS, activity_xp, advance, traits
from github_island.models import validate_snapshot
from github_island.normalize import activity_query, collect
from github_island.render import render, render_scene
from github_island.state import validate_state

FIELDS = {
    "prs": "pullRequestContributions",
    "issues": "issueContributions",
    "reviews": "pullRequestReviewContributions",
}


def collect_with(nodes_by_metric):
    """Collect two days from a client that returns the given nodes per metric."""
    client = FixtureClient()

    def transform(query, variables, user):
        for metric, field in FIELDS.items():
            if field in query:
                first_window = variables["to"].startswith("2026-11-14") or (
                    metric != "reviews"
                )
                nodes = nodes_by_metric.get(metric, []) if first_window else []
                user["contributionsCollection"][field] = page(nodes)
        return user

    client.transform = transform
    return collect(
        Config("octocat", "owner/island"),
        date(2026, 11, 13),
        date(2026, 11, 15),
        client,
        observed_on=date(2026, 11, 15),
    )


def homes(svg):
    return len(re.findall('<use href="#home"', svg))


class CollectionTests(unittest.TestCase):
    def test_only_other_owners_count_as_outside(self):
        value = collect_with(
            {
                "prs": [
                    event("2026-11-13", "OWN"),
                    event("2026-11-13", "THEIRS", repository="R2", owner="ORG"),
                    event("2026-11-14", "ALSO", repository="R3", owner="U2"),
                ],
                "issues": [
                    event(
                        "2026-11-13",
                        "I1",
                        repository="R2",
                        owner="ORG",
                        metric="issues",
                    ),
                    event("2026-11-13", "I2", metric="issues"),
                ],
            }
        )
        self.assertEqual(
            value["days"],
            {
                "2026-11-13": {"prs": 2, "issues": 2, "reviews": 0, "outside": 2},
                "2026-11-14": {"prs": 1, "issues": 0, "reviews": 0, "outside": 1},
            },
        )

    def test_a_repeated_node_counts_once(self):
        node = event("2026-11-13", "THEIRS", repository="R2", owner="ORG")
        value = collect_with({"prs": [node, copy.deepcopy(node)]})
        self.assertEqual(value["days"]["2026-11-13"]["prs"], 1)
        self.assertEqual(value["days"]["2026-11-13"]["outside"], 1)

    def test_reviews_private_and_excluded_repositories_never_count(self):
        value = collect_with(
            {
                "reviews": [
                    event(
                        "2026-11-13",
                        "REVIEWED",
                        repository="R2",
                        owner="ORG",
                        metric="reviews",
                    )
                ],
                "prs": [
                    event("2026-11-13", "HIDDEN", visibility="PRIVATE", owner="ORG"),
                    event("2026-11-13", "HOST", repository="G", owner="ORG"),
                ],
            }
        )
        self.assertEqual(
            value["days"]["2026-11-13"],
            {"prs": 0, "issues": 0, "reviews": 1, "outside": 0},
        )

    def test_a_missing_owner_fails_the_collection(self):
        node = event("2026-11-13", "THEIRS", repository="R2")
        del node["pullRequest"]["repository"]["owner"]
        with self.assertRaisesRegex(ValueError, "missing required fields"):
            collect_with({"prs": [node]})

    def test_the_query_asks_for_the_owner_where_it_is_used(self):
        self.assertIn("owner{id}", activity_query("prs"))
        self.assertIn("owner{id}", activity_query("issues"))
        self.assertNotIn("owner", activity_query("reviews"))


class SchemaTests(unittest.TestCase):
    def test_snapshot_rejects_more_outside_than_activity(self):
        value = snapshot(prs=1)
        day = next(iter(value["days"]))
        value["days"][day]["outside"] = 1
        validate_snapshot(value)
        value["days"][day]["outside"] = 2
        with self.assertRaisesRegex(ValueError, "Outside contributions exceed"):
            validate_snapshot(value)

    def test_snapshot_requires_the_outside_field(self):
        value = snapshot()
        del value["days"][next(iter(value["days"]))]["outside"]
        with self.assertRaises(ValueError):
            validate_snapshot(value)

    def test_state_keeps_and_checks_outside(self):
        value = snapshot(prs=2)
        for counts in value["days"].values():
            counts["outside"] = 1
        state = advance(value)
        self.assertEqual(state["current_traits"]["outside"], 30)
        broken = copy.deepcopy(state)
        day = state["last_complete_activity_day"]
        broken["days"][day]["outside"] = 3
        broken["current_traits"]["outside"] = 32
        with self.assertRaisesRegex(ValueError, "Outside contributions exceed"):
            validate_state(broken)

    def test_outside_earns_no_experience_of_its_own(self):
        counts = {"prs": 1, "reviews": 0, "issues": 0, "outside": 0}
        self.assertEqual(activity_xp(counts), activity_xp({**counts, "outside": 1}))

    def test_outside_trait_saturates_at_its_cap(self):
        zero = dict.fromkeys(CAPS, 0)
        self.assertEqual(CAPS["outside"], 10)
        self.assertEqual(traits(zero)["outside"], 0.0)
        self.assertEqual(traits({**zero, "outside": 10})["outside"], 1.0)
        self.assertLess(traits({**zero, "outside": 9})["outside"], 1.0)


class VisitorTests(unittest.TestCase):
    def scene(self, **signals):
        base = dict.fromkeys(
            ("prs", "reviews", "issues", "stars", "forks", "growth"), 0
        )
        return render_scene({**base, **signals})

    def test_outside_alone_brings_visitors(self):
        self.assertEqual(homes(self.scene()), 0)
        self.assertNotIn('class="bob', self.scene())
        self.assertEqual(self.scene(outside=0.2).count('class="bob'), 1)
        self.assertEqual(homes(self.scene(outside=0.65)), 1)
        self.assertEqual(homes(self.scene(outside=1)), 3)

    def test_visitors_follow_the_larger_of_reviews_and_outside(self):
        self.assertEqual(self.scene(reviews=1), self.scene(reviews=1, outside=0.4))
        self.assertEqual(self.scene(outside=1), self.scene(reviews=0.4, outside=1))

    def test_a_state_with_outside_contributions_draws_visitors(self):
        quiet = snapshot(prs=1)
        busy = snapshot(prs=1)
        for counts in list(busy["days"].values())[-10:]:
            counts["outside"] = 1
        self.assertEqual(homes(render(advance(quiet)).decode()), 0)
        self.assertEqual(homes(render(advance(busy)).decode()), 3)


if __name__ == "__main__":
    unittest.main()

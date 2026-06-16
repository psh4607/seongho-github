from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "seongho-github"
    / "skills"
    / "gh-address-comments"
    / "scripts"
    / "review_workflow.py"
)

FETCH_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "seongho-github"
    / "skills"
    / "gh-address-comments"
    / "scripts"
    / "fetch_comments.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("review_workflow", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_fetch_module():
    spec = importlib.util.spec_from_file_location("fetch_comments", FETCH_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ReviewWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = load_module()
        self.raw_payload = {
            "pull_request": {
                "number": 17,
                "url": "https://github.com/acme/widgets/pull/17",
                "title": "Improve widgets",
                "owner": "acme",
                "repo": "widgets",
            },
            "conversation_comments": [
                {
                    "id": "IC_1",
                    "url": "https://github.com/acme/widgets/pull/17#issuecomment-1",
                    "body": "Please explain the migration fallback.",
                    "author": {"login": "reviewer"},
                    "createdAt": "2026-06-16T00:00:00Z",
                }
            ],
            "reviews": [
                {
                    "id": "PRR_1",
                    "url": "https://github.com/acme/widgets/pull/17#pullrequestreview-1",
                    "state": "CHANGES_REQUESTED",
                    "body": "This needs a regression test.",
                    "author": {"login": "reviewer"},
                    "submittedAt": "2026-06-16T00:01:00Z",
                },
                {
                    "id": "PRR_2",
                    "state": "APPROVED",
                    "body": "",
                    "author": {"login": "approver"},
                    "submittedAt": "2026-06-16T00:02:00Z",
                },
            ],
            "review_threads": [
                {
                    "id": "PRRT_open",
                    "isResolved": False,
                    "isOutdated": False,
                    "path": "src/widget.ts",
                    "line": 41,
                    "comments": {
                        "nodes": [
                            {
                                "id": "PRRC_1",
                                "url": "https://github.com/acme/widgets/pull/17#discussion_r1",
                                "body": "Handle the empty value here.",
                                "author": {"login": "reviewer"},
                                "createdAt": "2026-06-16T00:03:00Z",
                            }
                        ]
                    },
                },
                {
                    "id": "PRRT_done",
                    "isResolved": True,
                    "isOutdated": False,
                    "path": "src/old.ts",
                    "line": 2,
                    "comments": {"nodes": []},
                },
            ],
        }

    def test_build_decision_plan_collects_unresolved_threads_and_body_comments(self) -> None:
        plan = self.workflow.build_decision_plan(self.raw_payload)

        self.assertEqual(plan["schema_version"], 1)
        self.assertEqual(plan["pull_request"]["url"], "https://github.com/acme/widgets/pull/17")

        items = plan["items"]
        self.assertEqual(
            [item["source"] for item in items],
            [
                "inline_thread",
                "review_body",
                "conversation_comment",
            ],
        )

        inline = items[0]
        self.assertEqual(inline["github_id"], "PRRT_open")
        self.assertEqual(inline["file"], "src/widget.ts")
        self.assertEqual(inline["line"], 41)
        self.assertTrue(inline["can_resolve"])
        self.assertEqual(inline["decision"], "pending")

        review_body = items[1]
        self.assertEqual(review_body["github_id"], "PRR_1")
        self.assertFalse(review_body["can_resolve"])
        self.assertIn("regression test", review_body["body"])

        comment = items[2]
        self.assertEqual(comment["github_id"], "IC_1")
        self.assertFalse(comment["can_resolve"])

    def test_validate_plan_requires_review_decisions_and_accept_evidence(self) -> None:
        plan = self.workflow.build_decision_plan(self.raw_payload)

        errors = self.workflow.validate_decision_plan(plan, require_commit_for_accept=True)
        self.assertTrue(any("pending" in error for error in errors))

        plan["items"][0].update(
            {
                "decision": "accept",
                "response": "Fixed empty values and added coverage.",
                "verification": "python -m unittest",
                "commit": "abc1234",
            }
        )
        plan["items"][1].update(
            {
                "decision": "reject",
                "response": "The existing regression test already covers this path.",
                "verification": "",
                "commit": "",
            }
        )
        plan["items"][2].update(
            {
                "decision": "no_action",
                "response": "Informational note; no code change needed.",
                "leave_unresolved_reason": "Top-level PR comments cannot be resolved.",
            }
        )

        self.assertEqual(
            self.workflow.validate_decision_plan(plan, require_commit_for_accept=True),
            [],
        )

    def test_publish_operations_reply_inline_and_comment_for_body_feedback(self) -> None:
        plan = self.workflow.build_decision_plan(self.raw_payload)
        plan["items"][0].update(
            {
                "decision": "accept",
                "response": "Fixed empty values and added coverage.",
                "verification": "python -m unittest",
                "commit": "abc1234",
            }
        )
        plan["items"][1].update(
            {
                "decision": "reject",
                "response": "Rejecting because the suggested behavior would regress imports.",
                "verification": "",
                "commit": "",
            }
        )
        plan["items"][2].update(
            {
                "decision": "no_action",
                "response": "Informational note; no code change needed.",
            }
        )

        operations = self.workflow.build_publish_operations(plan)

        self.assertEqual(
            [op["operation"] for op in operations],
            [
                "reply_review_thread",
                "resolve_review_thread",
                "post_pr_comment",
            ],
        )
        self.assertEqual(operations[0]["thread_id"], "PRRT_open")
        self.assertIn("Fixed empty values", operations[0]["body"])
        self.assertEqual(operations[1]["thread_id"], "PRRT_open")
        self.assertEqual(operations[2]["pr"], "https://github.com/acme/widgets/pull/17")
        self.assertIn("Rejecting because", operations[2]["body"])

    def test_fetch_comments_query_exposes_source_urls(self) -> None:
        fetch_comments = load_fetch_module()

        query = fetch_comments.QUERY

        self.assertIn("comments(first: 100, after: $commentsCursor)", query)
        self.assertIn("reviews(first: 100, after: $reviewsCursor)", query)
        self.assertIn("comments(first: 100) {", query)
        self.assertGreaterEqual(query.count("url"), 3)


if __name__ == "__main__":
    unittest.main()

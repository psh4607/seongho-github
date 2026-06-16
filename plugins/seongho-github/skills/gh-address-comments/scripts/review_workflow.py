#!/usr/bin/env python3
"""
PR review handling guardrail.

Workflow:
  1. fetch_comments.py > pr-review.raw.json
  2. review_workflow.py plan --input pr-review.raw.json --output pr-review.decisions.json
  3. Fill each decision item after implementing review feedback.
  4. review_workflow.py validate --plan pr-review.decisions.json
  5. review_workflow.py publish --plan pr-review.decisions.json
  6. review_workflow.py publish --plan pr-review.decisions.json --apply
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
DECISIONS = {"pending", "accept", "reject", "no_action"}

REPLY_MUTATION = """
mutation($threadId: ID!, $body: String!) {
  addPullRequestReviewThreadReply(input: {
    pullRequestReviewThreadId: $threadId,
    body: $body
  }) {
    comment {
      id
      url
    }
  }
}
"""

RESOLVE_MUTATION = """
mutation($threadId: ID!) {
  resolveReviewThread(input: { threadId: $threadId }) {
    thread {
      id
      isResolved
    }
  }
}
"""


def read_json(path: str) -> dict[str, Any]:
    if path == "-":
        return json.loads(sys.stdin.read())
    return json.loads(Path(path).read_text())


def write_json(path: str, payload: dict[str, Any]) -> None:
    data = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if path == "-":
        sys.stdout.write(data)
        return
    Path(path).write_text(data)


def author_login(node: dict[str, Any]) -> str:
    author = node.get("author") or {}
    login = author.get("login")
    return str(login) if login else ""


def clean_body(value: Any) -> str:
    return str(value or "").strip()


def thread_comments(thread: dict[str, Any]) -> list[dict[str, Any]]:
    comments = thread.get("comments") or {}
    nodes = comments.get("nodes") or []
    return [node for node in nodes if isinstance(node, dict)]


def latest_thread_comment(thread: dict[str, Any]) -> dict[str, Any]:
    comments = thread_comments(thread)
    return comments[-1] if comments else {}


def simplify_comments(comments: list[dict[str, Any]]) -> list[dict[str, str]]:
    simplified = []
    for comment in comments:
        simplified.append(
            {
                "id": str(comment.get("id") or ""),
                "url": str(comment.get("url") or ""),
                "author": author_login(comment),
                "created_at": str(comment.get("createdAt") or ""),
                "body": clean_body(comment.get("body")),
            }
        )
    return simplified


def empty_decision_fields(can_resolve: bool) -> dict[str, Any]:
    return {
        "decision": "pending",
        "response": "",
        "verification": "",
        "commit": "",
        "resolve": bool(can_resolve),
        "leave_unresolved_reason": "",
        "notes": "",
    }


def build_decision_plan(
    raw_payload: dict[str, Any],
    *,
    include_resolved: bool = False,
    include_empty_reviews: bool = False,
) -> dict[str, Any]:
    pull_request = raw_payload.get("pull_request") or {}
    items: list[dict[str, Any]] = []

    thread_index = 1
    for thread in raw_payload.get("review_threads") or []:
        if thread.get("isResolved") and not include_resolved:
            continue

        comments = thread_comments(thread)
        latest = latest_thread_comment(thread)
        item = {
            "item_id": f"T{thread_index:03d}",
            "source": "inline_thread",
            "github_id": str(thread.get("id") or ""),
            "comment_id": str(latest.get("id") or ""),
            "source_url": str(latest.get("url") or ""),
            "author": author_login(latest),
            "file": str(thread.get("path") or ""),
            "line": thread.get("line"),
            "is_outdated": bool(thread.get("isOutdated")),
            "can_resolve": True,
            "body": clean_body(latest.get("body")),
            "comments": simplify_comments(comments),
        }
        item.update(empty_decision_fields(can_resolve=True))
        items.append(item)
        thread_index += 1

    review_index = 1
    for review in raw_payload.get("reviews") or []:
        body = clean_body(review.get("body"))
        if not body and not include_empty_reviews:
            continue

        item = {
            "item_id": f"R{review_index:03d}",
            "source": "review_body",
            "github_id": str(review.get("id") or ""),
            "source_url": str(review.get("url") or ""),
            "author": author_login(review),
            "state": str(review.get("state") or ""),
            "submitted_at": str(review.get("submittedAt") or ""),
            "can_resolve": False,
            "body": body,
        }
        item.update(empty_decision_fields(can_resolve=False))
        items.append(item)
        review_index += 1

    comment_index = 1
    for comment in raw_payload.get("conversation_comments") or []:
        body = clean_body(comment.get("body"))
        if not body:
            continue

        item = {
            "item_id": f"C{comment_index:03d}",
            "source": "conversation_comment",
            "github_id": str(comment.get("id") or ""),
            "source_url": str(comment.get("url") or ""),
            "author": author_login(comment),
            "created_at": str(comment.get("createdAt") or ""),
            "can_resolve": False,
            "body": body,
        }
        item.update(empty_decision_fields(can_resolve=False))
        items.append(item)
        comment_index += 1

    return {
        "schema_version": SCHEMA_VERSION,
        "pull_request": pull_request,
        "instructions": {
            "decision": "Set to accept, reject, or no_action. Do not publish pending items.",
            "response": "Required for every non-pending item. This is posted to GitHub for accept/reject.",
            "verification": "Required for accept decisions.",
            "commit": "Required for accept decisions unless validate/publish is run with the explicit override.",
            "resolve": "Only inline_thread items can be resolved. Body comments are answered with PR comments.",
        },
        "items": items,
    }


def validate_decision_plan(
    plan: dict[str, Any],
    *,
    require_commit_for_accept: bool = True,
) -> list[str]:
    errors: list[str] = []

    if plan.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}.")

    pull_request = plan.get("pull_request") or {}
    if not pull_request.get("url") and not pull_request.get("number"):
        errors.append("pull_request.url or pull_request.number is required.")

    items = plan.get("items")
    if not isinstance(items, list):
        errors.append("items must be a list.")
        return errors

    for index, item in enumerate(items, start=1):
        item_name = str(item.get("item_id") or f"item {index}")
        source = str(item.get("source") or "")
        decision = str(item.get("decision") or "pending")
        can_resolve = bool(item.get("can_resolve"))
        should_resolve = bool(item.get("resolve"))
        response = clean_body(item.get("response"))
        verification = clean_body(item.get("verification"))
        commit = clean_body(item.get("commit"))

        if source not in {"inline_thread", "review_body", "conversation_comment"}:
            errors.append(f"{item_name}: unknown source '{source}'.")

        if decision not in DECISIONS:
            errors.append(f"{item_name}: decision must be one of {sorted(DECISIONS)}.")
            continue

        if decision == "pending":
            errors.append(f"{item_name}: decision is pending.")
            continue

        if not response:
            errors.append(f"{item_name}: response is required.")

        if decision == "accept":
            if not verification:
                errors.append(f"{item_name}: verification is required for accept.")
            if require_commit_for_accept and not commit:
                errors.append(f"{item_name}: commit is required for accept.")

        if not can_resolve and should_resolve:
            errors.append(f"{item_name}: only inline_thread items can be resolved.")

        if decision == "no_action" and can_resolve and should_resolve:
            errors.append(
                f"{item_name}: no_action cannot resolve an inline thread; use reject or set resolve=false."
            )

        if decision in {"accept", "reject"} and can_resolve and not should_resolve:
            reason = clean_body(item.get("leave_unresolved_reason"))
            if not reason:
                errors.append(
                    f"{item_name}: leave_unresolved_reason is required when an inline thread is not resolved."
                )

    return errors


def decision_label(decision: str) -> str:
    return {
        "accept": "반영",
        "reject": "반려",
        "no_action": "조치 없음",
        "pending": "미결정",
    }.get(decision, decision)


def source_label(item: dict[str, Any]) -> str:
    source = item.get("source")
    if source == "inline_thread":
        file_part = item.get("file") or "unknown file"
        line = item.get("line")
        if line:
            return f"inline thread {item.get('github_id')} at {file_part}:{line}"
        return f"inline thread {item.get('github_id')} at {file_part}"
    if source == "review_body":
        return f"review body {item.get('github_id')}"
    if source == "conversation_comment":
        return f"conversation comment {item.get('github_id')}"
    return str(item.get("github_id") or item.get("item_id") or "review item")


def format_response_body(item: dict[str, Any], *, include_source: bool) -> str:
    decision = str(item.get("decision") or "")
    lines = [f"리뷰 {decision_label(decision)} 처리했습니다.", ""]

    if include_source:
        lines.extend(
            [
                f"- 대상: {source_label(item)}",
                f"- 원문: {item.get('source_url') or item.get('github_id')}",
                "",
            ]
        )

    lines.append(clean_body(item.get("response")))

    verification = clean_body(item.get("verification"))
    if verification:
        lines.extend(["", f"검증: `{verification}`"])

    commit = clean_body(item.get("commit"))
    if commit:
        lines.append(f"커밋: `{commit}`")

    reason = clean_body(item.get("leave_unresolved_reason"))
    if reason:
        lines.append(f"미해결 유지 사유: {reason}")

    return "\n".join(lines).strip() + "\n"


def build_publish_operations(plan: dict[str, Any]) -> list[dict[str, Any]]:
    pull_request = plan.get("pull_request") or {}
    pr_ref = str(pull_request.get("url") or pull_request.get("number") or "")
    operations: list[dict[str, Any]] = []

    for item in plan.get("items") or []:
        decision = str(item.get("decision") or "pending")
        if decision not in {"accept", "reject"}:
            continue

        if item.get("source") == "inline_thread":
            operations.append(
                {
                    "operation": "reply_review_thread",
                    "item_id": item.get("item_id"),
                    "thread_id": item.get("github_id"),
                    "body": format_response_body(item, include_source=False),
                }
            )
            if item.get("resolve", True):
                operations.append(
                    {
                        "operation": "resolve_review_thread",
                        "item_id": item.get("item_id"),
                        "thread_id": item.get("github_id"),
                    }
                )
            continue

        operations.append(
            {
                "operation": "post_pr_comment",
                "item_id": item.get("item_id"),
                "pr": pr_ref,
                "body": format_response_body(item, include_source=True),
            }
        )

    return operations


def run(cmd: list[str], *, cwd: Path | None = None, stdin: str | None = None) -> str:
    process = subprocess.run(cmd, input=stdin, capture_output=True, cwd=cwd, text=True)
    if process.returncode != 0:
        message = (process.stderr or process.stdout or "").strip()
        raise RuntimeError(message or f"Command failed: {' '.join(cmd)}")
    return process.stdout


def run_json(cmd: list[str], *, cwd: Path | None = None, stdin: str | None = None) -> dict[str, Any]:
    output = run(cmd, cwd=cwd, stdin=stdin)
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse JSON: {exc}\nRaw:\n{output}") from exc


def ensure_gh_authenticated(repo: Path) -> None:
    try:
        run(["gh", "auth", "status"], cwd=repo)
    except RuntimeError as exc:
        raise RuntimeError("gh 인증이 필요합니다. `gh auth login` 후 다시 실행하세요.") from exc


def ensure_git_clean(repo: Path) -> None:
    status = run(["git", "status", "--short"], cwd=repo).strip()
    if status:
        raise RuntimeError(
            "working tree가 clean하지 않습니다. 리뷰 반영 변경을 commit한 뒤 publish하세요.\n"
            f"{status}"
        )


def graphql(query: str, fields: list[str], *, repo: Path) -> dict[str, Any]:
    payload = run_json(["gh", "api", "graphql", "-F", "query=@-", *fields], cwd=repo, stdin=query)
    if payload.get("errors"):
        raise RuntimeError(f"GitHub GraphQL error: {json.dumps(payload['errors'], ensure_ascii=False)}")
    return payload


def reply_to_thread(thread_id: str, body: str, *, repo: Path) -> str:
    payload = graphql(
        REPLY_MUTATION,
        ["-F", f"threadId={thread_id}", "-f", f"body={body}"],
        repo=repo,
    )
    comment = payload["data"]["addPullRequestReviewThreadReply"]["comment"]
    return str(comment.get("url") or comment.get("id"))


def resolve_thread(thread_id: str, *, repo: Path) -> str:
    payload = graphql(RESOLVE_MUTATION, ["-F", f"threadId={thread_id}"], repo=repo)
    thread = payload["data"]["resolveReviewThread"]["thread"]
    return f"{thread['id']} isResolved={thread['isResolved']}"


def post_pr_comment(pr_ref: str, body: str, *, repo: Path) -> str:
    if not pr_ref:
        raise RuntimeError("PR reference is empty.")

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as tmp:
        tmp.write(body)
        tmp_path = Path(tmp.name)

    try:
        return run(["gh", "pr", "comment", pr_ref, "--body-file", str(tmp_path)], cwd=repo).strip()
    finally:
        tmp_path.unlink(missing_ok=True)


def apply_operation(operation: dict[str, Any], *, repo: Path) -> str:
    op = operation["operation"]
    if op == "reply_review_thread":
        return reply_to_thread(str(operation["thread_id"]), str(operation["body"]), repo=repo)
    if op == "resolve_review_thread":
        return resolve_thread(str(operation["thread_id"]), repo=repo)
    if op == "post_pr_comment":
        return post_pr_comment(str(operation["pr"]), str(operation["body"]), repo=repo)
    raise RuntimeError(f"Unknown operation: {op}")


def render_operations(operations: list[dict[str, Any]]) -> None:
    if not operations:
        print("No GitHub write operations.")
        return

    for index, operation in enumerate(operations, start=1):
        op = operation["operation"]
        item_id = operation.get("item_id")
        if op == "post_pr_comment":
            target = operation.get("pr")
        else:
            target = operation.get("thread_id")
        print(f"{index}. {op} item={item_id} target={target}")
        body = operation.get("body")
        if body:
            print(body.rstrip())
            print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PR review 반영/반려 결정 파일을 만들고 검증한 뒤 GitHub에 게시합니다.",
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="help", help="도움말을 출력하고 종료합니다.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="fetch_comments.py raw JSON을 decision plan으로 변환합니다.")
    plan_parser.add_argument("--input", required=True, help="fetch_comments.py output JSON path. '-'면 stdin.")
    plan_parser.add_argument("--output", required=True, help="decision plan JSON path. '-'면 stdout.")
    plan_parser.add_argument("--include-resolved", action="store_true", help="이미 resolved된 inline thread도 포함합니다.")
    plan_parser.add_argument("--include-empty-reviews", action="store_true", help="body가 빈 review도 포함합니다.")

    validate_parser = subparsers.add_parser("validate", help="decision plan이 publish 가능한지 검사합니다.")
    validate_parser.add_argument("--plan", required=True, help="decision plan JSON path.")
    validate_parser.add_argument(
        "--allow-missing-accept-commit",
        action="store_true",
        help="accept 항목의 commit 필수 조건을 완화합니다.",
    )

    publish_parser = subparsers.add_parser("publish", help="GitHub reply/comment/resolve 작업을 dry-run 또는 apply합니다.")
    publish_parser.add_argument("--plan", required=True, help="decision plan JSON path.")
    publish_parser.add_argument("--repo", default=".", help="대상 git repository path.")
    publish_parser.add_argument("--apply", action="store_true", help="실제로 GitHub에 게시합니다. 생략하면 dry-run입니다.")
    publish_parser.add_argument(
        "--allow-missing-accept-commit",
        action="store_true",
        help="accept 항목의 commit 필수 조건을 완화합니다.",
    )
    publish_parser.add_argument(
        "--skip-clean-check",
        action="store_true",
        help="--apply 때 git status clean 검사를 건너뜁니다.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        if args.command == "plan":
            raw_payload = read_json(args.input)
            plan = build_decision_plan(
                raw_payload,
                include_resolved=args.include_resolved,
                include_empty_reviews=args.include_empty_reviews,
            )
            write_json(args.output, plan)
            return 0

        if args.command == "validate":
            plan = read_json(args.plan)
            errors = validate_decision_plan(
                plan,
                require_commit_for_accept=not args.allow_missing_accept_commit,
            )
            if errors:
                for error in errors:
                    print(f"Error: {error}", file=sys.stderr)
                return 1
            print("Decision plan is valid.")
            return 0

        if args.command == "publish":
            plan = read_json(args.plan)
            errors = validate_decision_plan(
                plan,
                require_commit_for_accept=not args.allow_missing_accept_commit,
            )
            if errors:
                for error in errors:
                    print(f"Error: {error}", file=sys.stderr)
                return 1

            operations = build_publish_operations(plan)
            if not args.apply:
                print("Dry run. Re-run with --apply to write to GitHub.")
                render_operations(operations)
                return 0

            repo = Path(args.repo).resolve()
            ensure_gh_authenticated(repo)
            if not args.skip_clean_check:
                ensure_git_clean(repo)

            for operation in operations:
                result = apply_operation(operation, repo=repo)
                print(f"{operation['operation']} {operation.get('item_id')}: {result}")
            return 0

        raise RuntimeError(f"Unknown command: {args.command}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

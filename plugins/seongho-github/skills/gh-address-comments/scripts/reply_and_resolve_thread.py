#!/usr/bin/env python3
"""
PR review thread에 reply를 달고 resolve합니다.

전제 조건:
  - `gh auth login`으로 인증되어 있어야 합니다.
  - thread id는 `fetch_comments.py`의 review_threads[].id에서 가져옵니다.

사용법:
  python reply_and_resolve_thread.py --thread-id PRRT_kw... --body "수정했습니다."
  python reply_and_resolve_thread.py --thread-id PRRT_kw... --body-file reply.md
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


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


def run(cmd: list[str]) -> str:
    process = subprocess.run(cmd, capture_output=True, text=True)
    if process.returncode != 0:
        message = (process.stderr or process.stdout or "").strip()
        raise RuntimeError(message or f"명령이 실패했습니다: {' '.join(cmd)}")
    return process.stdout


def run_json(cmd: list[str]) -> dict[str, Any]:
    output = run(cmd)
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"JSON을 parse할 수 없습니다: {exc}\nRaw:\n{output}") from exc


def ensure_gh_authenticated() -> None:
    try:
        run(["gh", "auth", "status"])
    except RuntimeError as exc:
        raise RuntimeError("gh 인증이 필요합니다. `gh auth login` 후 다시 실행하세요.") from exc


def graphql(query: str, fields: list[str]) -> dict[str, Any]:
    payload = run_json(["gh", "api", "graphql", "-f", f"query={query}", *fields])
    if payload.get("errors"):
        raise RuntimeError(f"GitHub GraphQL error: {json.dumps(payload['errors'], ensure_ascii=False)}")
    return payload


def read_body(args: argparse.Namespace) -> str:
    if args.body_file:
        body = Path(args.body_file).read_text()
    else:
        body = args.body or ""

    body = body.strip()
    if not body:
        raise RuntimeError("reply body가 비어 있습니다.")
    return body


def reply_to_thread(thread_id: str, body: str) -> dict[str, Any]:
    return graphql(REPLY_MUTATION, ["-F", f"threadId={thread_id}", "-f", f"body={body}"])


def resolve_thread(thread_id: str) -> dict[str, Any]:
    return graphql(RESOLVE_MUTATION, ["-F", f"threadId={thread_id}"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PR review thread에 reply를 달고 resolve합니다.",
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="help", help="도움말을 출력하고 종료합니다.")
    parser.add_argument("--thread-id", required=True, help="review thread id.")
    body = parser.add_mutually_exclusive_group(required=True)
    body.add_argument("--body", help="reply body.")
    body.add_argument("--body-file", help="reply body를 담은 markdown/text 파일.")
    parser.add_argument(
        "--no-resolve",
        action="store_true",
        help="reply만 달고 resolve는 하지 않습니다.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        ensure_gh_authenticated()
        body = read_body(args)
        reply_result = reply_to_thread(args.thread_id, body)
        comment = reply_result["data"]["addPullRequestReviewThreadReply"]["comment"]
        print(f"reply: {comment.get('url') or comment.get('id')}")

        if args.no_resolve:
            print("resolve: skipped")
            return 0

        resolve_result = resolve_thread(args.thread_id)
        thread = resolve_result["data"]["resolveReviewThread"]["thread"]
        print(f"resolve: {thread['id']} isResolved={thread['isResolved']}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

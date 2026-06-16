#!/usr/bin/env python3
"""
PR conversation comment, review, review thread(inline thread)를 모두 가져옵니다.
내부적으로 다음 명령을 사용합니다.

  gh api graphql

전제 조건:
  - `gh auth login`으로 인증되어 있어야 합니다.
  - PR 인자를 제공하거나, 현재 branch에 연결된 PR이 있어야 합니다.

사용법:
  python fetch_comments.py > pr_comments.json
  python fetch_comments.py --pr 123 > pr_comments.json
  python fetch_comments.py --repo owner/name --pr 123 > pr_comments.json
  python fetch_comments.py --pr https://github.com/owner/name/pull/123 > pr_comments.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Any

QUERY = """\
query(
  $owner: String!,
  $repo: String!,
  $number: Int!,
  $commentsCursor: String,
  $reviewsCursor: String,
  $threadsCursor: String
) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      number
      url
      title
      state

      # Top-level "Conversation" comments (issue comments on the PR)
      comments(first: 100, after: $commentsCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          url
          body
          createdAt
          updatedAt
          author { login }
        }
      }

      # Review submissions (Approve / Request changes / Comment), with body if present
      reviews(first: 100, after: $reviewsCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          url
          state
          body
          submittedAt
          author { login }
        }
      }

      # Inline review threads (grouped), includes resolved state
      reviewThreads(first: 100, after: $threadsCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          diffSide
          startLine
          startDiffSide
          originalLine
          originalStartLine
          resolvedBy { login }
          comments(first: 100) {
            nodes {
              id
              url
              body
              createdAt
              updatedAt
              author { login }
            }
          }
        }
      }
    }
  }
}
"""


def _run(cmd: list[str], stdin: str | None = None) -> str:
    p = subprocess.run(cmd, input=stdin, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{p.stderr}")
    return p.stdout


def _run_json(cmd: list[str], stdin: str | None = None) -> dict[str, Any]:
    out = _run(cmd, stdin=stdin)
    try:
        return json.loads(out)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse JSON from command output: {e}\nRaw:\n{out}") from e


def _ensure_gh_authenticated() -> None:
    try:
        _run(["gh", "auth", "status"])
    except RuntimeError:
        print("run `gh auth login` to authenticate the GitHub CLI", file=sys.stderr)
        raise RuntimeError("gh auth status failed; run `gh auth login` to authenticate the GitHub CLI") from None


def gh_pr_view_json(fields: str) -> dict[str, Any]:
    # fields는 "number,headRepositoryOwner,headRepository" 같은 comma-separated list입니다.
    return _run_json(["gh", "pr", "view", "--json", fields])


def gh_repo_name_with_owner() -> tuple[str, str]:
    repo = _run_json(["gh", "repo", "view", "--json", "nameWithOwner"])
    name_with_owner = repo["nameWithOwner"]
    owner, name = name_with_owner.split("/", 1)
    return owner, name


def parse_pr_url(value: str) -> tuple[str, str, int] | None:
    match = re.match(r"^https://github\.com/([^/]+)/([^/]+)/pull/([0-9]+)(?:[/?#].*)?$", value)
    if not match:
        return None
    owner, repo, number = match.groups()
    return owner, repo, int(number)


def parse_repo(value: str) -> tuple[str, str]:
    if "/" not in value:
        raise RuntimeError("--repo must be in owner/name format")
    owner, repo = value.split("/", 1)
    if not owner or not repo:
        raise RuntimeError("--repo must be in owner/name format")
    return owner, repo


def get_current_pr_ref() -> tuple[str, str, int]:
    """
    Resolve the PR for the current branch (whatever gh considers associated).
    Works for cross-repo PRs too, by reading head repository owner/name.
    """
    pr = gh_pr_view_json("number,headRepositoryOwner,headRepository")
    owner = pr["headRepositoryOwner"]["login"]
    repo = pr["headRepository"]["name"]
    number = int(pr["number"])
    return owner, repo, number


def resolve_pr_ref(repo_arg: str | None, pr_arg: str | None) -> tuple[str, str, int]:
    if pr_arg:
        parsed_url = parse_pr_url(pr_arg)
        if parsed_url:
            return parsed_url

        try:
            number = int(pr_arg)
        except ValueError as exc:
            raise RuntimeError("--pr must be a PR number or https://github.com/owner/name/pull/number URL") from exc

        if repo_arg:
            owner, repo = parse_repo(repo_arg)
        else:
            owner, repo = gh_repo_name_with_owner()
        return owner, repo, number

    if repo_arg:
        raise RuntimeError("--repo requires --pr; otherwise use the current branch PR")

    return get_current_pr_ref()


def gh_api_graphql(
    owner: str,
    repo: str,
    number: int,
    comments_cursor: str | None = None,
    reviews_cursor: str | None = None,
    threads_cursor: str | None = None,
) -> dict[str, Any]:
    """
    Call `gh api graphql` using -F variables, avoiding JSON blobs with nulls.
    Query is passed via stdin using query=@- to avoid shell newline/quoting issues.
    """
    cmd = [
        "gh",
        "api",
        "graphql",
        "-F",
        "query=@-",
        "-F",
        f"owner={owner}",
        "-F",
        f"repo={repo}",
        "-F",
        f"number={number}",
    ]
    if comments_cursor:
        cmd += ["-F", f"commentsCursor={comments_cursor}"]
    if reviews_cursor:
        cmd += ["-F", f"reviewsCursor={reviews_cursor}"]
    if threads_cursor:
        cmd += ["-F", f"threadsCursor={threads_cursor}"]

    return _run_json(cmd, stdin=QUERY)


def fetch_all(owner: str, repo: str, number: int) -> dict[str, Any]:
    conversation_comments: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    review_threads: list[dict[str, Any]] = []

    comments_cursor: str | None = None
    reviews_cursor: str | None = None
    threads_cursor: str | None = None

    pr_meta: dict[str, Any] | None = None

    while True:
        payload = gh_api_graphql(
            owner=owner,
            repo=repo,
            number=number,
            comments_cursor=comments_cursor,
            reviews_cursor=reviews_cursor,
            threads_cursor=threads_cursor,
        )

        if "errors" in payload and payload["errors"]:
            raise RuntimeError(f"GitHub GraphQL errors:\n{json.dumps(payload['errors'], indent=2)}")

        pr = payload["data"]["repository"]["pullRequest"]
        if pr_meta is None:
            pr_meta = {
                "number": pr["number"],
                "url": pr["url"],
                "title": pr["title"],
                "state": pr["state"],
                "owner": owner,
                "repo": repo,
            }

        c = pr["comments"]
        r = pr["reviews"]
        t = pr["reviewThreads"]

        conversation_comments.extend(c.get("nodes") or [])
        reviews.extend(r.get("nodes") or [])
        review_threads.extend(t.get("nodes") or [])

        comments_cursor = c["pageInfo"]["endCursor"] if c["pageInfo"]["hasNextPage"] else None
        reviews_cursor = r["pageInfo"]["endCursor"] if r["pageInfo"]["hasNextPage"] else None
        threads_cursor = t["pageInfo"]["endCursor"] if t["pageInfo"]["hasNextPage"] else None

        if not (comments_cursor or reviews_cursor or threads_cursor):
            break

    assert pr_meta is not None
    return {
        "pull_request": pr_meta,
        "conversation_comments": conversation_comments,
        "reviews": reviews,
        "review_threads": review_threads,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="gh api graphql로 PR comments, reviews, review threads를 가져옵니다.",
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="help", help="도움말을 출력하고 종료합니다.")
    parser.add_argument(
        "--repo",
        help="owner/name 형식의 repository. --pr이 GitHub PR URL이면 생략할 수 있습니다.",
    )
    parser.add_argument(
        "--pr",
        help="PR 번호 또는 https://github.com/owner/name/pull/number URL. 생략하면 현재 branch PR을 사용합니다.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    _ensure_gh_authenticated()
    owner, repo, number = resolve_pr_ref(args.repo, args.pr)
    result = fetch_all(owner, repo, number)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

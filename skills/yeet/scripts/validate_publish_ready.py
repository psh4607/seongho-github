#!/usr/bin/env python3
"""
PR publish 직전에 branch name, commit message, PR body 규칙을 검사합니다.

사용 예시:
  python validate_publish_ready.py --repo . --body-file /tmp/pr-body.md --title "Escape YAML scalars" --commit-message "fix: escape yaml scalars"
  python validate_publish_ready.py --branch feat/INF-668/bullet-child-padding --body "## 작업 배경..." --title "Adjust bullet spacing" --commit-message "feat: adjust bullet spacing"
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


ALLOWED_TYPES = ("feat", "fix", "docs", "refactor", "test", "chore")
BRANCH_RE = re.compile(
    r"^(?P<type>feat|fix|docs|refactor|test|chore)/"
    r"(?:(?P<ticket>[A-Z][A-Z0-9]+-\d+)/)?"
    r"(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)$"
)
COMMIT_RE = re.compile(r"^(feat|fix|docs|refactor|test|chore)(\([^)]+\))?: .+")
TOOL_TITLE_PREFIXES = (
    "[codex]",
    "codex:",
    "codex -",
    "codex ",
    "[agent]",
    "agent:",
    "agent -",
    "agent ",
)
DEFAULT_REQUIRED_SECTIONS = ("작업 배경", "티켓 및 링크", "작업 내용", "테스트")
COMMON_TEMPLATE_PATHS = (
    ".github/pull_request_template.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    "PULL_REQUEST_TEMPLATE.md",
)
PLACEHOLDER_MARKERS = (
    "[TICKET-ID](https://...)",
    "<왜 이 변경이 필요한지>",
    "<주요 변경 1>",
    "<주요 변경 2>",
    "<실행한 검증 명령>",
    "[]()",
    "Test A",
)


def run_git(repo: Path, args: list[str]) -> str:
    process = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
    )
    if process.returncode != 0:
        message = (process.stderr or process.stdout or "").strip()
        raise RuntimeError(message or f"git {' '.join(args)} failed")
    return process.stdout.strip()


def current_branch(repo: Path) -> str:
    return run_git(repo, ["branch", "--show-current"])


def read_body(args: argparse.Namespace) -> str:
    if args.body_file:
        return Path(args.body_file).read_text()
    if args.body is not None:
        return args.body
    return ""


def find_templates(repo: Path) -> list[Path]:
    templates: list[Path] = []
    seen: set[tuple[int, int]] = set()

    def add_template(path: Path) -> None:
        if not path.is_file():
            return
        stat = path.stat()
        key = (stat.st_dev, stat.st_ino)
        if key in seen:
            return
        seen.add(key)
        templates.append(path)

    for rel in COMMON_TEMPLATE_PATHS:
        add_template(repo / rel)

    template_dir = repo / ".github" / "PULL_REQUEST_TEMPLATE"
    if template_dir.is_dir():
        for path in sorted(template_dir.glob("*.md")):
            add_template(path)

    return templates


def normalize_heading(value: str) -> str:
    value = value.strip().strip("#").strip()
    value = value.strip("*").strip()
    value = re.sub(r"\s+", " ", value)
    return value


def markdown_headings(markdown: str) -> list[str]:
    headings: list[str] = []
    for line in markdown.splitlines():
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        if match:
            headings.append(normalize_heading(match.group(1)))
    return headings


def template_required_headings(template: str) -> list[str]:
    return [
        heading
        for heading in markdown_headings(template)
        if heading and not heading.lower().startswith(("as-is", "to-be"))
    ]


def branch_ticket(branch: str) -> str | None:
    match = BRANCH_RE.match(branch)
    if not match:
        return None
    return match.group("ticket")


def validate_branch(branch: str, errors: list[str]) -> None:
    if BRANCH_RE.match(branch):
        return

    if branch.startswith("codex/") or branch.startswith("agent/"):
        errors.append(
            f"branch '{branch}' uses a tool prefix. Use type/ticket/slug or type/slug."
        )
        return

    branch_type = branch.split("/", 1)[0]
    if branch_type not in ALLOWED_TYPES:
        errors.append(
            f"branch '{branch}' must start with one of: {', '.join(ALLOWED_TYPES)}."
        )
        return

    errors.append(
        f"branch '{branch}' must match type/TICKET/slug or type/slug. "
        "Example: feat/INF-668/bullet-child-padding"
    )


def validate_commit_message(message: str | None, errors: list[str]) -> None:
    if message is None:
        return
    if COMMIT_RE.match(message.strip()):
        return
    errors.append(
        "commit message must match 'type: 내용' or 'type(scope): 내용' "
        f"with type in {', '.join(ALLOWED_TYPES)}."
    )


def validate_title(title: str | None, errors: list[str]) -> None:
    if title is None:
        return

    normalized = title.strip()
    if not normalized:
        errors.append("PR title must not be empty.")
        return

    lowered = normalized.lower()
    if lowered.startswith(TOOL_TITLE_PREFIXES):
        errors.append(
            "PR title must summarize the diff without a tool prefix such as [codex]."
        )


def validate_body_against_template(
    body: str,
    templates: list[Path],
    errors: list[str],
) -> None:
    body_headings = markdown_headings(body)

    if templates:
        if len(templates) > 1:
            errors.append(
                "multiple PR templates found. Choose one explicitly and validate with --template."
            )
            return

        template = templates[0]
        required = template_required_headings(template.read_text())
        missing = [heading for heading in required if heading not in body_headings]
        if missing:
            errors.append(
                f"PR body does not follow template {template}: missing headings {missing}."
            )
        return

    missing = [section for section in DEFAULT_REQUIRED_SECTIONS if section not in body_headings]
    if missing:
        errors.append(
            f"PR body must include default sections when no template exists: {missing}."
        )


def validate_placeholders(body: str, errors: list[str]) -> None:
    leftovers = [marker for marker in PLACEHOLDER_MARKERS if marker in body]
    if leftovers:
        errors.append(f"PR body still contains placeholders: {leftovers}.")


def validate_ticket_link(
    body: str,
    ticket: str | None,
    allow_unlinked_ticket: bool,
    errors: list[str],
) -> None:
    if not ticket or allow_unlinked_ticket:
        return

    link_re = re.compile(rf"\[{re.escape(ticket)}\]\(https?://[^)]+\)")
    if link_re.search(body):
        return

    errors.append(
        f"ticket {ticket} must be a clickable Markdown link, or rerun with "
        "--allow-unlinked-ticket only when a reliable URL cannot be inferred."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="branch, commit message, PR body publish rules를 검사합니다.",
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="help", help="도움말을 출력하고 종료합니다.")
    parser.add_argument("--repo", default=".", help="대상 Git repository path.")
    parser.add_argument("--branch", help="검사할 branch name. 생략하면 현재 branch를 사용합니다.")
    parser.add_argument("--title", help="검사할 PR title.")
    parser.add_argument("--commit-message", help="검사할 commit message.")
    parser.add_argument("--template", help="사용할 PR template path. 여러 template이 있을 때 필수입니다.")
    parser.add_argument(
        "--allow-unlinked-ticket",
        action="store_true",
        help="ticket URL을 신뢰성 있게 만들 수 없을 때 Markdown link 요구를 완화합니다.",
    )
    body = parser.add_mutually_exclusive_group(required=True)
    body.add_argument("--body", help="PR body markdown string.")
    body.add_argument("--body-file", help="PR body markdown file path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    errors: list[str] = []

    try:
        branch = args.branch or current_branch(repo)
        body = read_body(args)
        templates = [Path(args.template).resolve()] if args.template else find_templates(repo)

        validate_branch(branch, errors)
        validate_title(args.title, errors)
        validate_commit_message(args.commit_message, errors)
        validate_body_against_template(body, templates, errors)
        validate_placeholders(body, errors)
        validate_ticket_link(
            body=body,
            ticket=branch_ticket(branch),
            allow_unlinked_ticket=args.allow_unlinked_ticket,
            errors=errors,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if errors:
        print("Publish guardrail failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Publish guardrail passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

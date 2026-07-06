---
name: github
description: GitHub URL, GitHub PR URL, issue URL, repository URL이 포함된 일반 GitHub 작업의 진입점입니다. gh와 로컬 git으로 PR/issue/repo를 확인하고, PR 리뷰/코파일럿 리뷰는 gh-address-comments, CI/check 실패는 gh-fix-ci, 커밋/push/PR 생성은 yeet로 라우팅합니다.
---

# GitHub

## 개요

이 스킬은 GitHub 작업의 일반 진입점입니다. 로컬 저장소나 사용자가 지정한 GitHub 대상을 먼저 확인하고, `git`과 `gh`로 필요한 맥락을 수집한 뒤, 의도가 명확해지면 전문 스킬로 바로 넘깁니다.

이 플러그인은 `gh` 우선, Codex GitHub connector fallback 원칙을 따릅니다.

- checkout, 브랜치, diff, status, commit, push 맥락은 로컬 `git`을 사용합니다.
- 인증, 저장소 메타데이터, pull request, issue, comment, label, PR 생성은 `gh`를 사용합니다.
- REST나 일반 `gh` 출력이 리뷰 스레드 상태, 페이지네이션, inline anchor를 충분히 보존하지 못하면 `gh api graphql`을 사용합니다.
- `gh`가 `API rate limit exceeded`, `X-RateLimit-Remaining: 0`, 또는 REST `/user` 403 때문에 실패하면 `gh auth refresh`를 반복하지 말고 Codex GitHub connector를 read-only 호출로 확인한 뒤 가능한 PR/issue/review/comment/thread 작업을 connector로 진행합니다.
- 모든 GitHub 작업은 사용자가 자기 shell에서 재현할 수 있는 명령 중심으로 진행합니다.

의도가 명확해지면 일반 triage 범위를 오래 끌지 말고 바로 전문 스킬로 라우팅합니다.

## 책임 범위

요청이 더 좁은 전문 워크플로우를 필요로 하지 않을 때 이 스킬에서 직접 처리합니다.

- repo, PR, issue, 또는 로컬 checkout이 식별된 뒤 저장소 방향 잡기
- 최근 PR 또는 issue triage
- PR 메타데이터 요약
- PR patch 확인
- top-level PR comment, label, reaction 확인
- issue 조회와 요약
- 요청 범위가 충분히 좁고 publish workflow가 필요 없을 때의 PR 생성

사용자 요청이나 로컬 git 맥락만으로 저장소를 식별할 수 없다면 추측하지 말고 repo 식별자를 요청합니다.

## 라우팅 규칙

1. 먼저 작업 맥락을 확인합니다.
   - 사용자가 repository, PR 번호, issue 번호, URL을 제공했다면 그것을 사용합니다.
   - "이 브랜치", "현재 PR"에 대한 요청이면 `git remote -v`, `git branch --show-current`, `gh pr view --json number,url,headRefName,baseRefName`으로 로컬 git 맥락을 확인합니다.
   - 로컬 확인 후에도 repository가 모호하면 repo 식별자를 요청합니다.
2. 행동하기 전에 요청을 분류합니다.
   - `repo or PR triage`: PR, issue, patch, comment, label, reaction, repository state 요약
   - `review follow-up`: unresolved review thread, requested changes, inline review feedback 처리
   - `CI debugging`: failing check, Actions log, CI root cause 분석
   - `publish changes`: branch 생성/전환, stage, commit, push, draft PR 생성
3. 분류가 끝나면 바로 전문 스킬로 넘깁니다.
   - 리뷰 코멘트와 requested changes: `../gh-address-comments/SKILL.md`
   - GitHub Actions 실패 체크: `../gh-fix-ci/SKILL.md`
   - commit, push, PR 생성: `../yeet/SKILL.md`

## URL 기반 즉시 라우팅

- GitHub PR URL과 `리뷰`, `코파일럿`, `Copilot`, `review`, `comment`, `requested changes`, `thread`, `resolve`, `반영`, `처리`가 함께 나오면 `../gh-address-comments/SKILL.md`를 우선 사용합니다.
- GitHub PR URL과 `CI`, `check`, `checks`, `failing`, `failed`, `Actions`, `workflow`, `log`, `로그`가 함께 나오면 `../gh-fix-ci/SKILL.md`를 우선 사용합니다.
- `커밋`, `commit`, `push`, `PR 만들어`, `PR 생성`, `draft PR`, `pull request 만들어`가 나오면 `../yeet/SKILL.md`를 우선 사용합니다.
- PR/issue/repo를 단순히 읽거나 요약하는 요청이면 이 스킬에서 `gh`로 triage합니다.

## 기본 워크플로우

1. 원격 GitHub 데이터가 필요하면 `gh` 설치와 인증 상태를 확인합니다.
2. repository와 item scope를 확인합니다.
3. `gh --json`, `gh api`, `gh api graphql`로 구조화된 맥락을 수집합니다.
4. triage로 충분한지, 전문 스킬이 필요한지 판단합니다.
5. 무엇을 확인했고, 무엇이 바뀌었고, 무엇이 남았는지 명확히 요약합니다.

## Codex GitHub Connector Fallback

`gh auth status` 실패를 무조건 로그인 만료로 해석하지 않습니다.

- rate limit 신호: `API rate limit exceeded`, `X-RateLimit-Remaining: 0`, REST `/user` 403, 또는 `gh auth status`가 invalid token처럼 보이지만 `gh auth token`/GraphQL/repo read는 되는 상태.
- 이 경우 사용자에게 device-code 재인증이나 `gh auth refresh` 반복을 요청하지 않습니다.
- `tool_search`로 GitHub connector 도구를 로드하고, `_list_recent_issues` 같은 가벼운 read-only 호출로 connector가 살아있는지 확인합니다.
- connector가 지원하면 PR metadata, review threads, reviews, comments, issue comments, inline replies, top-level PR comments, thread resolve/unresolve는 connector로 진행합니다.
- connector 도구가 없는 GitHub Actions job log 조회나 PR 생성은 `gh` reset time과 connector capability gap을 보고하고 멈춥니다.
- connector fallback을 썼다면 최종 보고에 `gh` REST rate limit 때문에 connector로 진행했다고 명시합니다.

## 출력 기준

- triage 요청은 repository, PR, issue 상태와 다음 행동을 간결하게 요약합니다.
- 혼합 요청은 어떤 전문 경로로 이동하는지와 이유를 설명합니다.
- write action은 적용 전에 정확한 PR, issue, label, reaction, branch, commit 대상을 다시 확인합니다.
- GitHub Actions 로그를 PR 메타데이터만으로 확인할 수 있다고 말하지 않습니다. run과 log는 `gh`로 확인합니다.

## 예시

- "이 repo의 open PR들을 요약하고 무엇을 봐야 하는지 알려줘."
- "이 PR 좀 도와줘."
- "PR 482의 최신 코멘트를 보고 actionable한 것만 알려줘."
- "이 브랜치의 failing check를 디버깅해줘."
- "이 변경사항을 커밋하고 push한 다음 draft PR을 만들어줘."

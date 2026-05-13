---
name: "yeet"
description: "로컬 변경사항의 scope를 확인하고, 의도적으로 commit한 뒤, branch를 push하고, gh로 draft PR을 생성합니다."
---

# GitHub 변경사항 게시

## 개요

이 스킬은 사용자가 로컬 checkout의 변경사항을 branch 준비, staging, commit, push, pull request 생성까지 끝내길 명시적으로 원할 때만 사용합니다.

이 워크플로우는 local-first입니다.

- branch 생성, staging, commit, push는 로컬 `git`을 사용합니다.
- 현재 브랜치 PR 탐색, 인증 확인, remote metadata, PR 생성은 `gh`를 사용합니다.
- 일반 `gh` 명령으로 필요한 field를 깔끔하게 얻기 어렵다면 `gh api` 또는 `gh api graphql`을 사용합니다.

## 전제 조건

- GitHub CLI `gh`가 필요합니다. `gh --version`으로 확인하고, 없으면 설치를 요청한 뒤 멈춥니다.
- 인증된 `gh` session이 필요합니다. `gh auth status`를 실행하고, 인증되어 있지 않으면 `gh auth login` 후 다시 확인하도록 요청합니다.
- 어떤 변경사항이 PR에 포함되어야 하는지 로컬 git repository에서 명확히 확인해야 합니다.

## 이름 규칙

- Branch: `main`, `master`, 또는 remote default branch에서 시작한다면 사용자가 다른 이름을 요청하지 않는 한 `agent/{description}`을 사용합니다.
- Commit: 실제 diff를 기준으로 짧은 imperative 문장 또는 conventional commit 형식을 고릅니다.
- PR title: 특정 도구 이름을 prefix로 붙이지 않고 전체 diff를 요약합니다.
- PR body: 실제 Markdown을 temp file에 작성한 뒤 `gh pr create`에 `--body-file`로 전달합니다.

## 워크플로우

1. 의도한 scope를 확인합니다.
   - staging 전에 `git status -sb`와 diff를 확인합니다.
   - branch에 이미 commit된 작업이 있을 수 있으면 `git diff origin/<base>...HEAD`로 예상 base와 비교합니다.
   - working tree에 관계없는 변경사항이 섞여 있으면 `git add -A`를 기본값으로 사용하지 않습니다. 어떤 파일을 PR에 포함할지 사용자에게 확인합니다.
2. branch 전략을 정합니다.
   - `gh repo view --json defaultBranchRef` 또는 `git remote show origin`으로 default branch를 찾습니다.
   - 현재 branch가 `main`, `master`, 또는 default branch라면 `agent/{description}`을 생성합니다.
   - 그 외에는 사용자가 rename이나 split을 요청하지 않는 한 현재 branch에 머뭅니다.
3. 의도한 변경사항만 stage합니다.
   - working tree가 섞여 있으면 명시적인 file path를 선호합니다.
   - 전체 working tree가 scope에 포함된다고 사용자가 확인한 경우에만 `git add -A`를 사용합니다.
4. 확인된 commit message로 commit합니다.
5. 아직 실행하지 않았다면 가장 관련 있는 검증을 실행합니다.
   - dependency나 tool이 없어서 실패하면 합리적인 범위에서 설치 후 한 번 다시 실행합니다.
   - 환경 제한 때문에 막히면 blocker를 정확히 보고합니다.
6. tracking과 함께 push합니다: `git push -u origin $(git branch --show-current)`.
7. `gh pr create`로 draft PR을 엽니다.
   - 사용자가 base branch를 지정했다면 그것을 사용하고, 아니면 remote default branch를 사용합니다.
   - 명시적인 flag를 선호합니다: `--draft`, `--base`, `--head`, `--title`, `--body-file`.
   - commit history가 그대로 PR 설명으로 적합할 때만 `--fill`을 사용합니다.
8. branch name, commit, PR target, validation, 사용자가 확인해야 할 남은 항목을 요약합니다.

## Write Safety

- 관계없는 사용자 변경사항을 조용히 stage하지 않습니다.
- working tree가 섞여 있으면 scope 확인 없이 push하지 않습니다.
- 사용자가 ready-for-review PR을 명시적으로 요청하지 않는 한 draft PR을 기본값으로 합니다.
- repository가 접근 가능한 GitHub remote와 연결되어 있지 않다면 추측하지 말고 blocker를 설명한 뒤 멈춥니다.

## PR Body 기준

PR description은 실제 Markdown prose로 작성하고 다음을 포함합니다.

- 무엇이 바뀌었는지
- 왜 바뀌었는지
- 사용자 또는 개발자 영향
- fix PR이라면 root cause
- 검증에 사용한 check

---
name: "yeet"
description: "로컬 변경사항으로 GitHub PR을 생성하거나 커밋, push, draft PR, pull request 생성, branch naming, PR template 작성이 필요할 때 사용합니다. git과 gh로 scope 확인, type/ticket/slug branch 생성, type: 내용 commit, push, gh pr create를 수행합니다."
---

# GitHub 변경사항 게시

## 개요

이 스킬은 사용자가 로컬 checkout의 변경사항을 branch 준비, staging, commit, push, pull request 생성까지 끝내길 명시적으로 원할 때 사용합니다. "PR 만들어줘", "커밋하고 push해줘", "현재 변경사항으로 draft PR 만들어줘" 같은 요청이 여기에 해당합니다.

이 워크플로우는 local-first입니다.

- branch 생성, staging, commit, push는 로컬 `git`을 사용합니다.
- 현재 브랜치 PR 탐색, 인증 확인, remote metadata, PR 생성은 `gh`를 사용합니다.
- 일반 `gh` 명령으로 필요한 field를 깔끔하게 얻기 어렵다면 `gh api` 또는 `gh api graphql`을 사용합니다.
- `gh`가 `API rate limit exceeded`, `X-RateLimit-Remaining: 0`, REST `/user` 403으로 막히면 `gh auth refresh`를 반복하지 않고 Codex GitHub connector로 가능한 remote metadata만 확인합니다.

## 전제 조건

- GitHub CLI `gh`가 필요합니다. `gh --version`으로 확인하고, 없으면 설치를 요청한 뒤 멈춥니다.
- 인증된 `gh` session이 필요합니다. `gh auth status`를 실행하고, 인증되어 있지 않으면 `gh auth login` 후 다시 확인하도록 요청합니다.
- 단, `gh auth status` 실패가 REST rate limit 때문이면 로그인 만료로 취급하지 않습니다. connector로 확인 가능한 범위는 진행하고, PR 생성은 connector에 명시 도구가 없으면 `gh` reset 이후로 미룹니다.
- 어떤 변경사항이 PR에 포함되어야 하는지 로컬 git repository에서 명확히 확인해야 합니다.
- PR 생성 직전에 bundled guardrail script를 실행해야 합니다. 실패하면 branch, commit message, PR body를 고친 뒤 다시 실행합니다.

## 이름 규칙

- Branch: 새 branch가 필요하면 `[type]/[ticket]/[내용]` 형식을 사용합니다.
  - `type`은 필수이며 실제 diff를 기준으로 고릅니다.
  - 허용 type:
    - `feat`: 새로운 기능
    - `fix`: 버그 수정
    - `docs`: 문서 변경
    - `refactor`: 리팩토링
    - `test`: 테스트
    - `chore`: 빌드, 설정 등
  - `ticket`은 선택사항입니다. Jira ticket id, Linear ticket id 등을 대화, branch, commit, issue, PR context에서 추론합니다.
  - ticket이 있으면 `type/TICKET/slug`, ticket이 없으면 `type/slug`를 사용합니다.
  - `slug`는 실제 diff와 대화 맥락에서 추론한 짧은 kebab-case 설명으로 작성합니다.
- Commit: `type: 내용` 형식을 기본으로 사용합니다. 내용은 실제 diff를 기준으로 짧은 imperative 문장 또는 conventional commit 스타일로 작성합니다.
- PR title: 특정 도구 이름을 prefix로 붙이지 않고 전체 diff를 요약합니다.
- PR body: repository에 PR template이 있으면 그 template을 따릅니다. 없으면 `작업 배경`, `티켓 및 링크`, `작업 내용`, `테스트` 섹션을 작성합니다. PR body는 실제 Markdown을 temp file에 작성한 뒤 `gh pr create`에 `--body-file`로 전달합니다.

## 워크플로우

1. 의도한 scope를 확인합니다.
   - staging 전에 `git status -sb`와 diff를 확인합니다.
   - branch에 이미 commit된 작업이 있을 수 있으면 `git diff origin/<base>...HEAD`로 예상 base와 비교합니다.
   - working tree에 관계없는 변경사항이 섞여 있으면 `git add -A`를 기본값으로 사용하지 않습니다. 어떤 파일을 PR에 포함할지 사용자에게 확인합니다.
2. branch 전략을 정합니다.
   - `gh repo view --json defaultBranchRef` 또는 `git remote show origin`으로 default branch를 찾습니다.
   - 현재 branch가 `main`, `master`, 또는 default branch라면 이름 규칙에 맞는 새 branch를 생성합니다.
   - 그 외에도 현재 branch가 이름 규칙을 어기면 PR 생성 전에 compliant branch를 새로 만들거나 rename합니다.
   - 이미 non-compliant branch가 remote에 push되어 있으면 사용자에게 확인한 뒤 compliant branch로 새로 push합니다.
   - 새 branch 이름을 만들 때는 먼저 type을 확정하고, session context에서 ticket id와 내용 slug를 추론합니다.
   - type이 모호하면 diff의 주된 의도를 기준으로 고릅니다. 기능 추가는 `feat`, 버그 수정은 `fix`, 문서만 바뀌면 `docs`, 동작 변화 없는 구조 개선은 `refactor`, 테스트만 추가/수정하면 `test`, 빌드/설정/잡무성 변경은 `chore`를 사용합니다.
3. 의도한 변경사항만 stage합니다.
   - working tree가 섞여 있으면 명시적인 file path를 선호합니다.
   - 전체 working tree가 scope에 포함된다고 사용자가 확인한 경우에만 `git add -A`를 사용합니다.
4. 이름 규칙에 맞는 commit message로 commit합니다.
   - 기본 형식은 `type: 내용`입니다.
   - 내용은 branch slug보다 사람이 읽기 좋은 짧은 imperative 문장으로 작성합니다.
5. 아직 실행하지 않았다면 가장 관련 있는 검증을 실행합니다.
   - dependency나 tool이 없어서 실패하면 합리적인 범위에서 설치 후 한 번 다시 실행합니다.
   - 환경 제한 때문에 막히면 blocker를 정확히 보고합니다.
6. tracking과 함께 push합니다: `git push -u origin $(git branch --show-current)`.
7. `gh pr create`로 draft PR을 엽니다.
   - 사용자가 base branch를 지정했다면 그것을 사용하고, 아니면 remote default branch를 사용합니다.
   - 명시적인 flag를 선호합니다: `--draft`, `--base`, `--head`, `--title`, `--body-file`.
   - `--fill`은 기본적으로 사용하지 않습니다. PR template/body guardrail을 우회하기 쉽기 때문입니다.
   - PR template을 찾고, 있으면 그 구조를 유지해 실제 내용으로 채웁니다.
   - template이 없으면 이 스킬의 기본 PR body 섹션을 사용합니다.
   - `gh pr create` 실행 직전에 `scripts/validate_publish_ready.py`를 실행합니다.
   - REST rate limit으로 `gh pr create`가 불가능하고 connector에 PR 생성 도구가 없다면, commit/push까지만 완료하고 PR title/body/base/head와 reset time을 보고합니다.
8. branch name, commit, PR target, validation, guardrail 결과, 사용자가 확인해야 할 남은 항목을 요약합니다.

## Publish Guardrail

PR 생성 직전에 다음 script를 실행합니다.

```bash
python "<path-to-skill>/scripts/validate_publish_ready.py" \
  --repo "." \
  --body-file "<pr-body-file>" \
  --title "<pr-title>" \
  --commit-message "<commit-message>"
```

이 script는 다음을 검사합니다.

- branch가 `type/TICKET/slug` 또는 `type/slug` 형식인지
- branch type이 `feat`, `fix`, `docs`, `refactor`, `test`, `chore` 중 하나인지
- commit message가 `type: 내용` 또는 `type(scope): 내용` 형식인지
- PR title이 도구 prefix 없이 diff를 요약하는지
- repository PR template이 있으면 PR body가 template heading을 유지하는지
- template이 없으면 `작업 배경`, `티켓 및 링크`, `작업 내용`, `테스트` 섹션이 있는지
- branch에 ticket segment가 있으면 PR body에 clickable Markdown ticket link가 있는지
- PR body에 placeholder가 남아 있지 않은지

ticket URL을 신뢰성 있게 만들 수 없을 때만 `--allow-unlinked-ticket`을 사용합니다. 이 경우 최종 요약에 ticket link를 만들지 못한 이유를 적습니다.

## Write Safety

- 관계없는 사용자 변경사항을 조용히 stage하지 않습니다.
- working tree가 섞여 있으면 scope 확인 없이 push하지 않습니다.
- 사용자가 ready-for-review PR을 명시적으로 요청하지 않는 한 draft PR을 기본값으로 합니다.
- repository가 접근 가능한 GitHub remote와 연결되어 있지 않다면 추측하지 말고 blocker를 설명한 뒤 멈춥니다.
- publish guardrail이 실패하면 PR을 생성하지 않습니다.

## PR Body 기준

FE 변경사항을 포함한 PR이면 `../../docs/pr-screenshot-attachments.md`를 읽고, 처음 읽는 사람 중심의 PR body 정책을 적용합니다. 스크린샷은 20-30초 fast path만 기본 시도하고, 실패하거나 실제 인증 화면 QA가 필요하면 PR 생성을 막지 않고 follow-up comment로 분리합니다. Dia CDP와 Computer Use fallback은 사용자가 스크린샷/실제 화면 확인을 강하게 요구할 때만 사용합니다.

먼저 repository의 PR template을 찾습니다.

- `.github/pull_request_template.md`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/PULL_REQUEST_TEMPLATE/*.md`
- `PULL_REQUEST_TEMPLATE.md`

template이 있으면 section 제목과 checklist를 유지하고, 비어 있는 placeholder를 실제 diff에 맞게 채웁니다. template이 여러 개라면 PR 성격에 가장 가까운 것을 고르고, 고르기 어렵다면 사용자에게 선택을 요청합니다.

template이 없으면 다음 구조를 사용합니다.

```markdown
## 작업 배경

<왜 이 변경이 필요한지>

## 티켓 및 링크

- [TICKET-ID](https://...)

## 작업 내용

- <주요 변경 1>
- <주요 변경 2>

## 테스트

- <실행한 검증 명령>
```

티켓 링크는 가능하면 클릭 가능한 Markdown 링크로 작성합니다. 대화, branch, commit, PR/issue 본문, Jira/Linear URL, 또는 repository 문맥에서 URL을 추론할 수 있으면 `[TICKET-ID](URL)` 형식으로 씁니다. ticket id만 있고 URL을 신뢰성 있게 만들 수 없으면 id만 적고 추측 URL은 만들지 않습니다.

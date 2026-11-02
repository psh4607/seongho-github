---
name: "yeet"
description: "로컬 변경사항으로 GitHub PR을 생성하거나 커밋, push, draft PR, pull request 생성, branch naming, PR template 작성이 필요할 때 사용합니다. 저장소의 개발·승격 흐름과 기존 PR 이력으로 base/head를 검증하고 git과 gh로 commit, push, PR 생성을 수행합니다."
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
- branch 생성·전환·rename 전에 [저장소 flow와 PR 대상 결정](references/repository-flow.md)을 읽고 대상 repository, base, head와 근거를 정합니다. default branch나 배포 트리거만으로 base를 결정하지 않습니다.
- PR 생성 직전에 bundled guardrail script를 실행해야 합니다. 실패하면 branch, commit message, PR body를 고친 뒤 다시 실행합니다.

## 이름 규칙

- 저장소의 명시적인 branch/commit 규칙이 아래 기본값보다 우선합니다. 기존 공유 브랜치, release/hotfix 브랜치, 승격 PR의 `exp`/`develop` 등을 기본 이름 규칙에 맞추려고 rename하지 않습니다.
- Branch: 새 branch가 필요하고 저장소 규칙이 없으면 `[type]/[ticket]/[내용]` 형식을 사용합니다.
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
   - committed 작업과 미커밋 작업을 구분합니다. base가 정해지면 `<base-ref>...HEAD` diff와 `<base-ref>..HEAD` commit 목록 모두로 PR 범위를 확인합니다.
   - working tree에 관계없는 변경사항이 섞여 있으면 `git add -A`를 기본값으로 사용하지 않습니다. 어떤 파일을 PR에 포함할지 사용자에게 확인합니다.
2. repository flow와 branch 전략을 정합니다.
   - `references/repository-flow.md`에 따라 지침, 최근 같은 종류의 PR, 브랜치 관계, CI/배포 역할을 확인합니다.
   - feature/fix, release/promotion, hotfix/backport, stacked PR을 구분합니다. 사용자에게 `head → base`, 선택 근거, 병합 시 CI/배포 영향을 짧게 알립니다. 근거가 일치하면 재승인을 받지 않고 진행합니다.
   - 개발 통합·보호·공유 브랜치에서 일반 기능 작업을 게시한다면 검증된 출발점에서 새 작업 브랜치를 만듭니다. 승격 PR은 기존 통합 브랜치를 head로 유지할 수 있습니다.
   - 현재 작업 브랜치와 기존 PR을 재사용할 수 있으면 유지합니다. 이름만 고치기 위해 공유 이력을 옮기거나 default branch에서 다시 시작하지 않습니다.
   - 새 이름은 저장소 규칙을 우선하며, 규칙이 없으면 실제 diff의 type, 알려진 ticket, 짧은 slug를 사용합니다.
3. 의도한 변경사항만 stage합니다.
   - working tree가 섞여 있으면 명시적인 file path를 선호합니다.
   - 전체 working tree가 scope에 포함된다고 사용자가 확인한 경우에만 `git add -A`를 사용합니다.
4. 이름 규칙에 맞는 commit message로 commit합니다.
   - 기본 형식은 `type: 내용`입니다.
   - 내용은 branch slug보다 사람이 읽기 좋은 짧은 imperative 문장으로 작성합니다.
5. 아직 실행하지 않았다면 가장 관련 있는 검증을 실행합니다.
   - dependency나 tool이 없어서 실패하면 합리적인 범위에서 설치 후 한 번 다시 실행합니다.
   - 환경 제한 때문에 막히면 blocker를 정확히 보고합니다.
6. 확인한 head repository의 push remote에 명시적인 head branch를 push합니다. fork에서는 base repository와 push remote가 다를 수 있으므로 `origin`을 고정하지 않습니다.
7. `gh pr create`로 draft PR을 엽니다.
   - 결정한 base/head를 사용합니다. base가 미확정이면 default branch로 대체하지 않습니다.
   - 동일한 head repository/branch의 기존 open PR을 먼저 확인하고 중복 생성하지 않습니다. 기존 base와 결정한 base가 다르면 이유를 확인하며 조용히 retarget하지 않습니다.
   - `--repo`, `--base`, `--head`, `--title`, `--body-file`을 명시하고 기본적으로 `--draft`를 사용합니다.
   - `--fill`은 기본적으로 사용하지 않습니다. PR template/body guardrail을 우회하기 쉽기 때문입니다.
   - PR template을 찾고, 있으면 그 구조를 유지해 실제 내용으로 채웁니다.
   - template이 없으면 이 스킬의 기본 PR body 섹션을 사용합니다.
   - `gh pr create` 실행 직전에 `scripts/validate_publish_ready.py`를 실행합니다.
   - REST rate limit으로 `gh pr create`가 불가능하고 connector에 PR 생성 도구가 없다면, commit/push까지만 완료하고 PR title/body/base/head와 reset time을 보고합니다.
8. 생성한 PR을 `gh pr view <url> --json url,baseRefName,headRefName,headRefOid,headRepository,headRepositoryOwner,isDraft`로 다시 읽어 의도한 repository/base/head/SHA와 대조합니다. 불일치하면 review/merge로 넘어가지 말고 원인을 해결합니다.
9. PR 링크, `head → base`, 선택 근거, 검증 결과, 필요한 후속 승격·역동기화와 남은 항목을 요약합니다. PR 생성 요청만으로 merge·deploy·추가 동기화 PR까지 수행하지 않습니다.

## Publish Guardrail

PR 생성 직전에 다음 script를 실행합니다.

```bash
python "<path-to-skill>/scripts/validate_publish_ready.py" \
  --repo "." \
  --body-file "<pr-body-file>" \
  --title "<pr-title>" \
  --commit-message "<commit-message>"
```

이 script는 **이름과 본문 형식만** 검사합니다. repository flow, base 적합성, 실제 PR diff와 배포 영향은 검증하지 않습니다. script 통과로 위 target 확인을 대체하지 않습니다. 저장소 고유 이름 규칙이나 승격 head는 아래 naming policy로 검사하며 브랜치를 기본 규칙에 맞춰 강제로 바꾸지 않습니다.

이 script는 다음을 검사합니다.

- branch가 `type/TICKET/slug` 또는 `type/slug` 형식인지
- branch type이 `feat`, `fix`, `docs`, `refactor`, `test`, `chore` 중 하나인지
- commit message가 `type: 내용` 또는 `type(scope): 내용` 형식인지
- PR title이 도구 prefix 없이 diff를 요약하는지
- repository PR template이 있으면 PR body가 template heading을 유지하는지
- template이 없으면 `작업 배경`, `티켓 및 링크`, `작업 내용`, `테스트` 섹션이 있는지
- branch에 ticket segment가 있으면 PR body에 clickable Markdown ticket link가 있는지
- PR body에 placeholder가 남아 있지 않은지

저장소 고유 이름 규칙이 있거나 기존 승격 head를 유지해야 하면 `--naming-policy-file <json-file>`을 추가합니다. JSON의 `source`에는 실제 확인한 지침 경로/PR 번호 또는 사용자 지시를 기록하고, `branch_pattern`과 `commit_pattern` 중 필요한 항목만 저장소 규칙에 맞는 정규식으로 지정합니다. 전체 문자열을 검사하며 생략한 항목에는 기본 규칙이 적용됩니다.

```json
{"source": "AGENTS.md:34; 기존 승격 PR #9", "branch_pattern": "exp"}
```

이 파일은 확인한 정책을 전달하는 수단이며 정책의 진위를 자동 검증하지 않습니다. 통과시키려고 `.*`를 넣거나 근거를 만들어내지 않습니다. title/body/template/ticket 검사는 계속 적용되며 Git hook을 변경하거나 우회하지 않습니다. 승격 PR에 새 commit이 없다면 `--commit-message`는 생략할 수 있습니다.

ticket URL을 신뢰성 있게 만들 수 없을 때만 `--allow-unlinked-ticket`을 사용합니다. 이 경우 최종 요약에 ticket link를 만들지 못한 이유를 적습니다.

## Write Safety

- 관계없는 사용자 변경사항을 조용히 stage하지 않습니다.
- working tree가 섞여 있으면 scope 확인 없이 push하지 않습니다.
- 사용자가 ready-for-review PR을 명시적으로 요청하지 않는 한 draft PR을 기본값으로 합니다.
- repository가 접근 가능한 GitHub remote와 연결되어 있지 않다면 추측하지 말고 blocker를 설명한 뒤 멈춥니다.
- publish guardrail이 실패하면 PR을 생성하지 않습니다.

## PR Body 기준

FE 변경사항을 포함한 PR이면 `../../docs/pr-screenshot-attachments.md`를 읽고, 처음 읽는 사람 중심의 PR body 정책을 적용합니다. 스크린샷은 20-30초 fast path만 기본 시도하고, 실패하거나 실제 인증 화면 QA가 필요하면 PR 생성을 막지 않고 follow-up comment로 분리합니다. Dia CDP와 Computer Use fallback은 사용자가 스크린샷/실제 화면 확인을 강하게 요구할 때만 사용합니다.

먼저 **선택한 base repository의 최신 base SHA**에서 PR template과 관련 작성 지침을 확인합니다. 로컬 checkout이 오래됐거나 다른 branch/fork를 보고 있으면 로컬 template을 그대로 쓰지 않습니다.

1. 확인한 base remote를 fetch한 뒤 정확한 ref/SHA에서 `git ls-tree -r --name-only <base-sha>`와 `git show <base-sha>:<template-path>`로 읽거나, GitHub Contents/Tree API의 `ref=<base-sha>`를 사용합니다. repository, SHA, template 경로를 검증 기록에 남깁니다.
2. template을 임시 파일에 저장하고 검사기에 `--template <downloaded-file>`을 명시합니다. 최신 template이 삭제·이동됐다면 오래된 로컬 파일로 대체하지 않습니다. 인증·네트워크 오류를 template 부재로 처리하지 않습니다.
3. base에 template이 없음을 확인한 경우에만 기본 본문 구조를 사용합니다. 이때 오래된 로컬 template이 남아 있으면 빈 임시 디렉터리를 `--repo`로 지정하고 실제 `--branch`를 명시해 기본 본문 검사를 수행합니다. 실제 repository/branch 검증은 별도로 유지합니다.
4. 여러 template이 있으면 작업에 맞는 것을 고릅니다. template이 참조하는 STYLE/기여 지침도 읽고, 저장소의 명시적인 필수·조건부·권장 구분을 따릅니다. 로컬 도구는 원격 최신성이나 자연어 정책의 진위를 자동 판정하지 않습니다.

다음 경로와 `.github/`, `docs/`, root의 대소문자 변형을 확인합니다.

- `.github/pull_request_template.md`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/PULL_REQUEST_TEMPLATE/*.md`
- `PULL_REQUEST_TEMPLATE.md`

template이 있으면 적용되는 section 제목과 checklist를 유지하고, 비어 있는 placeholder를 실제 diff에 맞게 채웁니다. HTML 주석과 fenced code block 안의 예시 제목은 필수 section으로 세지 않습니다. template이 여러 개라면 PR 성격에 가장 가까운 것을 고르고, 고르기 어렵다면 사용자에게 선택을 요청합니다.

저장소가 생략을 허용한 선택/조건부 section은 `--template-policy-file <json-file>`로 설명합니다. `--template`과 함께 사용하며, 정확한 제목마다 생략 근거를 적습니다. 하위 제목도 생략하려면 각각 명시합니다.

```json
{
  "source": "owner/repo@base-sha:.github/pull_request_template.md — UI가 아닌 변경에서 UI review 생략 허용",
  "optional_headings": {
    "UI review": "CI 설정만 바꾸므로 UI 변경 조건에 해당하지 않음",
    "Findings": "해당하지 않는 UI review의 하위 항목",
    "Needs a human / needs a device": "해당하지 않는 UI review의 하위 항목"
  }
}
```

이 정책은 근거를 전달하는 수단입니다. 적용되는 필수 section을 통과 목적으로 제외하지 않습니다. 저장소가 advisory로만 정한 항목은 게시 차단으로 승격하지 말고 누락을 보고합니다. 제목의 `필수`/`required`/`mandatory` 표시는 면제할 수 없고, 알 수 없는 제목·빈 근거·전체 section 면제도 거부합니다. 그 밖의 필수 section, ticket link, placeholder 검사는 유지합니다. 섹션 내용의 충실성·조건 충족 여부는 diff와 지침을 읽어 별도로 판단합니다.

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

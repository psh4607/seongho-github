---
name: gh-address-comments
description: GitHub PR URL, Copilot review, 코파일럿 리뷰, PR 리뷰 확인/처리/반영 요청을 처리합니다. unresolved review thread, requested changes, inline review comment를 gh와 GitHub GraphQL로 확인하고, 필요한 수정, thread reply, resolve, commit, push까지 수행할 때 이 스킬을 우선 사용합니다.
---

# GitHub PR 코멘트 처리

사용자가 GitHub pull request의 review, Copilot review, requested changes, inline comment를 확인하거나 처리하길 원할 때 이 스킬을 사용합니다. thread-aware review data는 일반 PR comment만으로 충분하지 않으므로 `gh api graphql` 문제로 취급합니다.

원격 read 전에 `gh auth status`를 실행합니다. 인증이 실패하면 사용자에게 `gh auth login`을 요청하고 다시 시도합니다.

## Quick Start

리뷰 처리 artifact는 repo 밖 임시 디렉터리에 둡니다.

- 작업 디렉터리: `PR_REVIEW_DIR=$(mktemp -d)`
- 현재 branch PR: `python "<path-to-skill>/scripts/fetch_comments.py"`
- 특정 PR 번호: `python "<path-to-skill>/scripts/fetch_comments.py" --repo owner/name --pr 123`
- PR URL: `python "<path-to-skill>/scripts/fetch_comments.py" --pr https://github.com/owner/name/pull/123`
- decision file 생성: `python "<path-to-skill>/scripts/review_workflow.py" plan --input "$PR_REVIEW_DIR/raw.json" --output "$PR_REVIEW_DIR/decisions.json"`
- decision 검증: `python "<path-to-skill>/scripts/review_workflow.py" validate --plan "$PR_REVIEW_DIR/decisions.json"`
- GitHub write dry-run: `python "<path-to-skill>/scripts/review_workflow.py" publish --plan "$PR_REVIEW_DIR/decisions.json" --repo .`
- GitHub write apply: `python "<path-to-skill>/scripts/review_workflow.py" publish --plan "$PR_REVIEW_DIR/decisions.json" --repo . --apply`
- thread reply 후 resolve: `python "<path-to-skill>/scripts/reply_and_resolve_thread.py" --thread-id <thread-id> --body-file <reply.md>`

## 워크플로우

1. PR을 확인합니다.
   - 사용자가 repository와 PR 번호 또는 URL을 제공했다면 그것을 직접 사용합니다.
   - 현재 branch PR에 대한 요청이면 로컬 git 맥락과 `gh pr view --json number,url,headRepositoryOwner,headRepository,headRefName,baseRefName`을 사용해 확인합니다.
2. thread-aware read로 review context를 확인합니다.
   - 넓은 PR 메타데이터는 `gh pr view --json number,url,title,state,author,headRefName,baseRefName,files,comments,reviews`를 사용합니다.
   - unresolved review thread, inline review location, resolution state가 중요하면 bundled `scripts/fetch_comments.py` workflow를 사용해 repo 밖 임시 디렉터리에 raw JSON을 저장합니다.
   - bundled script에 없는 custom field나 mutation이 필요하면 직접 `gh api graphql`을 호출합니다.
3. decision file을 생성합니다.
   - `python scripts/review_workflow.py plan --input "$PR_REVIEW_DIR/raw.json" --output "$PR_REVIEW_DIR/decisions.json"`을 실행합니다.
   - 생성된 `items[]`는 unresolved inline thread, body가 있는 review, conversation comment를 포함합니다.
   - 각 item의 `decision`은 반드시 `accept`, `reject`, `no_action` 중 하나로 바꿉니다. `pending`이 남으면 publish할 수 없습니다.
   - inline thread는 `can_resolve=true`입니다. review body와 conversation comment는 GitHub에 resolve primitive가 없으므로 top-level PR comment로 응답합니다.
4. 리뷰 내용을 반영하거나 반려합니다.
   - `accept`: 코드 또는 문서에 반영하고 관련 검증을 실행합니다. decision item에 `response`, `verification`, `commit`을 기록합니다.
   - `reject`: 반려 이유를 `response`에 기술합니다. 코드 변경이 없다면 `commit`은 비워둡니다.
   - `no_action`: approval, bot/status noise, 중복 정보처럼 반영/반려 대상이 아닌 항목에만 사용합니다. actionable feedback을 숨기는 용도로 쓰지 않습니다.
   - 코멘트끼리 충돌하거나 behavioral regression이 예상되면 구현 전에 tradeoff를 분명히 설명하고 필요한 경우 사용자 확인을 받습니다.
5. 수정 후 commit/push합니다.
   - `accept` 항목이 있으면 관련 변경을 commit하고 현재 PR branch에 push합니다.
   - 하나의 commit이 여러 review item을 처리하면 같은 commit hash를 각 item의 `commit`에 기록합니다.
   - 코드 변경 없이 반려만 하는 경우에는 commit/push를 만들지 않습니다.
6. decision file을 검증합니다.
   - `python scripts/review_workflow.py validate --plan "$PR_REVIEW_DIR/decisions.json"`을 실행합니다.
   - `accept` 항목에는 `response`, `verification`, `commit`이 필요합니다.
   - `reject` 항목에는 `response`가 필요합니다.
   - inline thread를 resolve하지 않을 때는 `resolve=false`와 `leave_unresolved_reason`을 기록합니다.
7. GitHub write를 dry-run 후 apply합니다.
   - 가능한 가장 관련 있는 local test 또는 check를 실행합니다.
   - `python scripts/review_workflow.py publish --plan "$PR_REVIEW_DIR/decisions.json" --repo .`로 게시될 reply/comment/resolve 작업을 먼저 확인합니다.
   - dry-run이 의도와 맞으면 `python scripts/review_workflow.py publish --plan "$PR_REVIEW_DIR/decisions.json" --repo . --apply`로 GitHub에 반영합니다.
   - `--apply`는 기본적으로 `git status --short`가 clean인지 확인합니다. 리뷰 반영 변경을 commit하기 전에는 publish하지 않습니다.
   - inline thread의 `accept`/`reject` 항목은 review thread reply를 작성한 뒤 `resolve=true`일 때 resolve합니다.
   - review body 또는 conversation comment의 `accept`/`reject` 항목은 source를 명시한 top-level PR comment를 작성합니다.
8. 결과를 요약합니다.
   - 처리한 thread, 남긴 reply의 요지, resolve 여부, commit, push 결과, 검증 결과를 나열합니다.
   - 의도적으로 남긴 thread가 있으면 이유를 분명히 씁니다.

## Decision File Contract

`scripts/review_workflow.py plan`이 생성하는 JSON을 작업의 source of truth로 사용합니다.

- `source`: `inline_thread`, `review_body`, `conversation_comment` 중 하나입니다.
- `decision`: `pending`, `accept`, `reject`, `no_action` 중 하나입니다. publish 전 `pending`은 허용하지 않습니다.
- `response`: GitHub에 남길 응답입니다. 모든 non-pending item에 필요합니다.
- `verification`: `accept` 항목에 필요한 검증 명령 또는 확인 내용입니다.
- `commit`: `accept` 항목에 필요한 commit hash입니다. 정말 commit이 불가능한 예외 상황에서만 script override를 사용합니다.
- `resolve`: inline thread에만 의미가 있습니다. body comment 계열은 resolve할 수 없으므로 PR comment로만 응답합니다.
- `leave_unresolved_reason`: inline thread를 reply만 하고 resolve하지 않을 때 필요한 이유입니다.

## GitHub Thread Writes

review thread에 답변하고 resolve할 때는 다음 GraphQL mutation을 사용합니다.

- reply: `addPullRequestReviewThreadReply`
- resolve: `resolveReviewThread`

reply body는 다음 내용을 포함해 간결하게 작성합니다.

- 어떤 변경을 했는지
- 왜 그 방식으로 처리했는지
- 어떤 검증을 했는지 또는 무엇이 아직 미검증인지

## Write Safety

- 사용자가 PR 리뷰 처리를 요청하면, 선택된 actionable review thread에 대한 코드 수정, thread reply, thread resolve, commit, push까지 수행하는 것으로 해석합니다.
- PR 리뷰 처리 요청 없이 단순히 "읽어줘", "요약해줘", "검토해줘"라고 한 경우에는 GitHub에 reply, review thread resolve, review submit, commit, push를 하지 않습니다.
- 처리하지 않은 thread를 resolved로 표시하지 않습니다.
- 실제 코드 변경이나 확인 없이 형식적인 reply만 달지 않습니다.
- 리뷰 코멘트끼리 충돌하거나 behavioral regression을 만들 수 있으면 변경 전에 tradeoff를 설명합니다.
- 코멘트가 모호하면 추측하지 말고 clarification을 요청하거나 제안 답변을 작성합니다.
- flat PR comment를 완전한 review-thread 상태로 취급하지 않습니다.
- 중간에 `gh` auth 또는 rate limit 문제가 발생하면 사용자에게 재인증 후 retry를 요청합니다.

## Fallback

`gh`로 PR을 명확히 확인할 수 없으면 blocker가 repository scope 부족인지, PR context 부족인지, CLI authentication 문제인지 설명한 뒤 필요한 repo/PR 식별자 또는 갱신된 `gh` login을 요청합니다.

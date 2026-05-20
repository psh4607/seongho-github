---
name: gh-address-comments
description: GitHub PR URL, Copilot review, 코파일럿 리뷰, PR 리뷰 확인/처리/반영 요청을 처리합니다. unresolved review thread, requested changes, inline review comment를 gh와 GitHub GraphQL로 확인하고, 필요한 수정, thread reply, resolve, commit, push까지 수행할 때 이 스킬을 우선 사용합니다.
---

# GitHub PR 코멘트 처리

사용자가 GitHub pull request의 review, Copilot review, requested changes, inline comment를 확인하거나 처리하길 원할 때 이 스킬을 사용합니다. thread-aware review data는 일반 PR comment만으로 충분하지 않으므로 `gh api graphql` 문제로 취급합니다.

원격 read 전에 `gh auth status`를 실행합니다. 인증이 실패하면 사용자에게 `gh auth login`을 요청하고 다시 시도합니다.

## Quick Start

- 현재 branch PR: `python "<path-to-skill>/scripts/fetch_comments.py"`
- 특정 PR 번호: `python "<path-to-skill>/scripts/fetch_comments.py" --repo owner/name --pr 123`
- PR URL: `python "<path-to-skill>/scripts/fetch_comments.py" --pr https://github.com/owner/name/pull/123`
- thread reply 후 resolve: `python "<path-to-skill>/scripts/reply_and_resolve_thread.py" --thread-id <thread-id> --body-file <reply.md>`

## 워크플로우

1. PR을 확인합니다.
   - 사용자가 repository와 PR 번호 또는 URL을 제공했다면 그것을 직접 사용합니다.
   - 현재 branch PR에 대한 요청이면 로컬 git 맥락과 `gh pr view --json number,url,headRepositoryOwner,headRepository,headRefName,baseRefName`을 사용해 확인합니다.
2. thread-aware read로 review context를 확인합니다.
   - 넓은 PR 메타데이터는 `gh pr view --json number,url,title,state,author,headRefName,baseRefName,files,comments,reviews`를 사용합니다.
   - unresolved review thread, inline review location, resolution state가 중요하면 bundled `scripts/fetch_comments.py` workflow를 사용합니다.
   - bundled script에 없는 custom field나 mutation이 필요하면 직접 `gh api graphql`을 호출합니다.
3. actionable review thread를 묶습니다.
   - file 또는 behavior area 기준으로 comment를 그룹화합니다.
   - actionable change request, informational comment, approval, already-resolved thread, outdated thread, duplicate를 구분합니다.
4. 수정 전에 scope를 확인합니다.
   - actionable thread를 번호와 한 줄 요약으로 제시합니다.
   - 사용자가 "PR 리뷰 처리해줘", "리뷰 반영해줘"처럼 전체 처리를 요청했다면 unresolved actionable thread 전체를 기본 scope로 봅니다.
   - 사용자가 특정 thread만 지정했다면 그 thread만 처리합니다.
   - 요청 범위가 불명확하거나 thread 간 충돌이 있으면 어떤 thread를 처리할지 묻습니다.
5. 선택된 수정을 로컬에서 구현합니다.
   - 각 코드 변경이 어떤 thread 또는 feedback cluster를 처리하는지 추적 가능하게 유지합니다.
   - 코멘트가 코드 변경보다 설명을 요구한다면 억지로 코드를 바꾸지 말고 답변 초안을 작성합니다.
6. 검증하고 게시합니다.
   - 가능한 가장 관련 있는 local test 또는 check를 실행합니다.
   - 처리한 review thread마다 변경 이유와 검증 내용을 짧게 정리한 reply를 작성합니다.
   - `scripts/reply_and_resolve_thread.py` 또는 직접 `gh api graphql` mutation으로 해당 thread에 reply를 달고 resolve합니다.
   - 수정 내용을 commit하고 현재 PR branch에 push합니다.
   - commit message는 실제 변경 내용을 기준으로 짧게 작성합니다.
7. 결과를 요약합니다.
   - 처리한 thread, 남긴 reply의 요지, resolve 여부, commit, push 결과, 검증 결과를 나열합니다.
   - 의도적으로 남긴 thread가 있으면 이유를 분명히 씁니다.

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

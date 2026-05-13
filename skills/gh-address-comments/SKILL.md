---
name: gh-address-comments
description: GitHub pull request의 actionable review feedback을 처리합니다. unresolved review thread, requested changes, inline review comment를 확인하고, gh와 GitHub GraphQL로 선택된 수정을 구현할 때 사용합니다.
---

# GitHub PR 코멘트 처리

사용자가 GitHub pull request의 requested changes를 처리하길 원할 때 이 스킬을 사용합니다. thread-aware review data는 일반 PR comment만으로 충분하지 않으므로 `gh api graphql` 문제로 취급합니다.

원격 read 전에 `gh auth status`를 실행합니다. 인증이 실패하면 사용자에게 `gh auth login`을 요청하고 다시 시도합니다.

## Quick Start

- 현재 branch PR: `python "<path-to-skill>/scripts/fetch_comments.py"`
- 특정 PR 번호: `python "<path-to-skill>/scripts/fetch_comments.py" --repo owner/name --pr 123`
- PR URL: `python "<path-to-skill>/scripts/fetch_comments.py" --pr https://github.com/owner/name/pull/123`

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
   - 사용자가 전부 수정하라고 하지 않았다면 어떤 thread를 처리할지 묻습니다.
   - 사용자가 전부 수정하라고 했다면 unresolved actionable thread 전체로 해석하고, 모호한 항목은 별도로 표시합니다.
5. 선택된 수정을 로컬에서 구현합니다.
   - 각 코드 변경이 어떤 thread 또는 feedback cluster를 처리하는지 추적 가능하게 유지합니다.
   - 코멘트가 코드 변경보다 설명을 요구한다면 억지로 코드를 바꾸지 말고 답변 초안을 작성합니다.
6. 결과를 요약합니다.
   - 처리한 thread, 의도적으로 남긴 thread, 변경을 뒷받침하는 test 또는 check를 나열합니다.

## Write Safety

- 사용자가 명시적으로 요청하지 않는 한 GitHub에 reply, review thread resolve, review submit을 하지 않습니다.
- 리뷰 코멘트끼리 충돌하거나 behavioral regression을 만들 수 있으면 변경 전에 tradeoff를 설명합니다.
- 코멘트가 모호하면 추측하지 말고 clarification을 요청하거나 제안 답변을 작성합니다.
- flat PR comment를 완전한 review-thread 상태로 취급하지 않습니다.
- 중간에 `gh` auth 또는 rate limit 문제가 발생하면 사용자에게 재인증 후 retry를 요청합니다.

## Fallback

`gh`로 PR을 명확히 확인할 수 없으면 blocker가 repository scope 부족인지, PR context 부족인지, CLI authentication 문제인지 설명한 뒤 필요한 repo/PR 식별자 또는 갱신된 `gh` login을 요청합니다.

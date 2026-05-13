# Seongho GitHub

로컬 `git`, GitHub CLI `gh`, GitHub GraphQL을 기준으로 동작하는 개인 GitHub 워크플로우 스킬 모음입니다. GitHub PR URL 기반 리뷰 처리, Copilot review 대응, CI 디버깅, PR 생성 작업을 명확히 소유하도록 구성했습니다.

## 정책

- 브랜치, diff, 커밋, push 작업은 로컬 checkout을 기준으로 판단합니다.
- GitHub 인증, PR 탐색, PR 생성, 리뷰 코멘트, Actions 확인은 `gh`를 사용합니다.
- 리뷰 스레드 상태, inline 위치, 페이지네이션, resolve 상태처럼 일반 `gh` 출력만으로 부족한 정보는 `gh api graphql`로 가져옵니다.
- 사용자가 명시적으로 요청하지 않는 한 다른 플러그인의 GitHub app 도구를 사용하지 않습니다.
- 생성하는 브랜치명과 PR 제목은 중립적으로 작성합니다. 특정 도구 이름을 prefix로 붙이지 않습니다.

## 스킬

- `github`: GitHub URL, PR URL, issue URL 기반 작업의 일반 진입점과 라우팅.
- `yeet`: 로컬 변경사항을 branch naming, 커밋, push, draft PR까지 게시.
- `gh-address-comments`: PR 리뷰, Copilot review, requested changes를 GraphQL로 확인하고 reply/resolve/commit/push까지 처리.
- `gh-fix-ci`: GitHub Actions, PR checks, workflow log를 확인하고 수정 방향 제시.

## 설치 메모

이 저장소는 독립적으로 동작하도록 구성했습니다. `.app.json` 통합 manifest를 포함하지 않습니다.

이 저장소는 plugin marketplace root로도 동작합니다. GitHub repo를 marketplace source로 추가하면 이 플러그인을 사용할 수 있습니다.

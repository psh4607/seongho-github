# Seongho GitHub

로컬 `git`, GitHub CLI `gh`, GitHub GraphQL, Codex GitHub connector fallback을 기준으로 동작하는 개인 GitHub 워크플로우 스킬 모음입니다. GitHub PR URL 기반 리뷰 처리, Copilot review 대응, CI 디버깅, PR 생성 작업을 명확히 소유하도록 구성했습니다.

## 정책

- 브랜치, diff, 커밋, push 작업은 로컬 checkout을 기준으로 판단합니다.
- GitHub 인증, PR 탐색, PR 생성, 리뷰 코멘트, Actions 확인은 `gh`를 사용합니다.
- 리뷰 스레드 상태, inline 위치, 페이지네이션, resolve 상태처럼 일반 `gh` 출력만으로 부족한 정보는 `gh api graphql`로 가져옵니다.
- `gh`가 `API rate limit exceeded`, `X-RateLimit-Remaining: 0`, REST `/user` 403으로 막히면 `gh auth refresh`를 반복하지 않고 Codex GitHub connector로 가능한 PR/issue/review/comment/thread 작업을 진행합니다.
- Codex GitHub connector에 명시 도구가 없는 GitHub Actions job log 조회나 PR 생성은 `gh` reset time과 capability gap을 보고합니다.
- 생성하는 브랜치명과 PR 제목은 중립적으로 작성합니다. 특정 도구 이름을 prefix로 붙이지 않습니다.
- FE 변경 PR의 스크린샷 첨부 정책은 [PR Screenshot Attachments](plugins/seongho-github/docs/pr-screenshot-attachments.md)를 따릅니다.

## 스킬

- `github`: GitHub URL, PR URL, issue URL 기반 작업의 일반 진입점과 라우팅.
- `yeet`: 로컬 변경사항을 branch naming, 커밋, push, draft PR까지 게시.
- `gh-address-comments`: PR 리뷰, Copilot review, requested changes를 GraphQL로 확인하고 decision file guardrail로 반영/반려, reply/comment, resolve, commit/push까지 처리.
- `gh-fix-ci`: GitHub Actions, PR checks, workflow log를 확인하고 수정 방향 제시.

## 설치 메모

이 저장소는 독립적으로 동작하도록 구성했습니다. `.app.json` 통합 manifest를 포함하지 않습니다.

이 저장소는 plugin marketplace root로도 동작합니다. 실제 plugin root는 `plugins/seongho-github`이며, GitHub repo를 marketplace source로 추가하면 이 플러그인을 사용할 수 있습니다.

## Claude Code 설치

Codex 플러그인(`plugins/seongho-github`)이 원본입니다. Claude Code 플러그인(`claude/seongho-github`)은 매니페스트만 따로 두고, `skills/<skill>`과 `docs`는 원본을 가리키는 상대 경로 심링크로 연결합니다. Claude Code가 설치할 때 링크 대상을 플러그인 캐시로 복사하므로 스킬 본문은 원본 한 곳에서만 관리합니다.

Claude Code 세션에서 마켓플레이스를 추가한 뒤 플러그인을 설치합니다.

```text
/plugin marketplace add psh4607/seongho-github
/plugin install seongho-github@seongho-github
```

셸에서는 `claude plugin marketplace add psh4607/seongho-github`와 `claude plugin install seongho-github@seongho-github`를 실행합니다. 설치한 스킬은 `seongho-github:github`, `seongho-github:yeet`처럼 `<plugin>:<skill>` 이름으로 노출됩니다.

- 심링크를 지원하는 git checkout이 필요합니다. macOS와 Linux는 기본으로 지원합니다. Windows에서는 Developer Mode를 켜고 `git config --global core.symlinks true`를 설정한 뒤 마켓플레이스를 추가합니다. 심링크가 텍스트 파일로 checkout되면 설치는 성공한다고 나오지만 스킬이 하나도 로드되지 않습니다. 설치 후 `claude plugin details seongho-github@seongho-github`에서 `Skills (4)`가 보이는지 확인합니다.
- 4개 스킬을 모두 링크합니다. 스킬 본문의 Codex GitHub connector fallback은 `gh` REST rate limit 때만 쓰는 보조 경로이며, Codex GitHub connector가 없는 Claude Code에서는 스킬 지침대로 reset time과 capability gap을 보고합니다.
- Codex 매니페스트의 `version`이나 메타데이터를 바꾸면 `claude/seongho-github/.claude-plugin/plugin.json`도 같은 값으로 바꿉니다. Claude Code는 `version`이 바뀌어야 설치본을 갱신합니다. `tests/test_claude_plugin.py`가 두 매니페스트와 심링크가 어긋나지 않는지 검사합니다.
- 매니페스트는 `claude plugin validate .`와 `claude plugin validate ./claude/seongho-github`로 검증합니다. 심링크된 스킬은 validator가 따라가지 않는다는 경고가 나오며, 설치본에서는 정상으로 로드됩니다.

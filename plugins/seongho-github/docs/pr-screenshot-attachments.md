# PR Screenshot Attachments

## Goal

FE 변경 PR을 처음 읽는 사람이 코드 diff를 열기 전에 화면 변화의 의도를 이해할 수 있도록 PR 본문에 스크린샷을 첨부한다.

이 기능은 best-effort로 동작한다. 스크린샷 캡처나 GitHub 첨부가 실패해도 PR 생성, commit, push를 막지 않는다.

## Constraint

GitHub는 PR/Issue comment body를 생성하거나 수정하는 API는 제공하지만, PR에 파일을 직접 attachment로 업로드하는 공식 API endpoint는 제공하지 않는다.

따라서 `gh` 또는 GitHub REST/GraphQL API만으로 `github.com/user-attachments/assets/...` URL을 만들 수 있다고 가정하지 않는다.

## Preferred Flow

1. `yeet`이 commit, push, draft PR 생성을 완료한다.
2. FE 변경사항이면 화면 캡처 대상 URL을 정한다.
   - 로컬 dev server URL
   - Vercel preview URL
   - 사용자가 명시한 URL
3. Playwright로 스크린샷을 캡처한다.
4. GitHub 웹 UI를 통해 스크린샷 파일을 PR body 또는 PR comment 입력창에 첨부한다.
5. GitHub가 생성한 Markdown 이미지 URL을 PR body의 `화면 변경` 섹션에 반영한다.
6. 자동화에 사용한 탭이나 브라우저 세션은 가능한 범위에서 닫는다.

## Browser Fallback Order

1. Codex Browser / Playwright
   - 전용 브라우저 프로필에서 GitHub 로그인이 확인되면 먼저 사용한다.
   - file chooser 또는 paste upload로 첨부한다.
   - 작업 후 사용한 탭을 닫는다.
2. Dia CDP
   - Codex Browser에 GitHub 인증 정보가 없을 때만 사용한다.
   - 사용자의 기존 GitHub 로그인 세션이 필요한 경우에 적합하다.
   - 새 탭을 열어 작업하고, 작업 후 해당 탭을 닫는다.
3. Computer Use
   - CDP에서 file chooser, drag/drop, paste 처리가 불안정할 때만 사용한다.
   - 실제 UI 조작으로 첨부한다.
4. Skip
   - 위 경로가 모두 실패하면 스크린샷 첨부를 포기한다.
   - PR body에는 자동 첨부 실패 사유를 짧게 남긴다.

## PR Body Shape

PR body는 단순 변경 나열보다 처음 읽는 사람에게 설명하는 순서로 작성한다.

```markdown
## 작업 배경

<기존 화면이나 흐름에서 무엇이 불편했는지>

## 변경 의도

<왜 이 방향으로 바꿨는지>

## 화면 변경

![변경된 화면](https://github.com/user-attachments/assets/...)

자동 캡처 기준: `<url or route>`

## 구현 요약

<화면 변화와 직접 연결되는 구현만 요약>

## 검증

<무엇을 보장하기 위해 어떤 검증을 실행했는지>
```

테스트 추가는 독립적인 성과처럼 쓰지 않는다. 예를 들어 `테스트를 추가했습니다` 대신 `빈 상태에서도 CTA 위치가 깨지지 않도록 렌더링 테스트를 추가했습니다`처럼 검증 의도를 같이 적는다.

## Failure Body

스크린샷 자동 첨부가 실패하면 PR 생성을 중단하지 않고 다음처럼 남긴다.

```markdown
## 화면 변경

스크린샷 자동 첨부를 시도했지만 GitHub 브라우저 세션 또는 업로드 단계에서 실패했습니다.
캡처 대상: `<url or route>`
실패 단계: `<capture | github-login | upload | body-update>`
```

## Storage Policy

회사 S3/CDN 버킷은 기본 경로로 사용하지 않는다.

필요할 경우 사용자가 명시적으로 승인한 외부 storage만 별도 모드로 추가한다. 기본 모드는 GitHub 웹 UI attachment 업로드다.

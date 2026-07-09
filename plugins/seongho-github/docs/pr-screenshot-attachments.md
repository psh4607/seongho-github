# PR Screenshot Attachments

## Goal

FE 변경 PR을 처음 읽는 사람이 코드 diff를 열기 전에 화면 변화의 의도를 이해할 수 있도록 PR 본문에 스크린샷을 첨부한다.

이 기능은 best-effort로 동작한다. 스크린샷 캡처, GitHub 첨부, 실제 인증 화면 QA가 실패하거나 오래 걸려도 PR 생성, commit, push를 막지 않는다.

## Constraint

GitHub는 PR/Issue comment body를 생성하거나 수정하는 API는 제공하지만, PR에 파일을 직접 attachment로 업로드하는 공식 API endpoint는 제공하지 않는다.

따라서 `gh` 또는 GitHub REST/GraphQL API만으로 `github.com/user-attachments/assets/...` URL을 만들 수 있다고 가정하지 않는다.

## Default Flow

1. `yeet`이 설명 중심의 PR body를 작성한다.
2. commit, push, draft PR 생성을 먼저 완료한다.
3. FE 변경사항이면 스크린샷 fast path만 시도한다.
   - Codex Browser / Playwright로 이미 접근 가능한 화면
   - 이미 준비된 local dev server, static reproduction, 또는 Vercel preview
   - 총 20-30초 안에 캡처와 GitHub upload가 가능한 경우
4. fast path가 실패하거나 인증/실데이터 진입이 필요하면 스크린샷을 skip한다.
5. 실제 인증 화면 QA가 필요하면 PR을 막지 않고 follow-up PR comment로 분리한다.

## Fast Path

- Codex Browser / Playwright를 기본값으로 사용한다.
- GitHub PR 페이지가 이미 로그인되어 있고 댓글 입력창이 바로 보일 때만 attachment upload를 시도한다.
- GitHub upload가 느리거나 브라우저 세션이 애매하면 즉시 skip한다.
- 로컬 재현 화면을 캡처할 수는 있지만, 실제 preview 증거처럼 쓰지 않는다. 반드시 `local reproduction` 또는 `로컬 재현 화면`으로 라벨링한다.
- 작업 후 사용한 탭, 임시 서버, 임시 파일은 가능한 범위에서 정리한다.

## Explicit Screenshot Required

사용자가 "스크린샷 꼭 붙여줘", "실제 화면까지 확인해줘"처럼 강하게 요구할 때만 느린 fallback을 탄다.

1. Codex Browser / Playwright
2. Dia CDP
   - Codex Browser에 GitHub 또는 서비스 인증 정보가 없고, 사용자의 기존 브라우저 세션이 필요한 경우에만 사용한다.
3. Computer Use
   - CDP에서 file chooser, drag/drop, paste 처리가 불안정할 때만 사용한다.
4. Skip
   - 위 경로가 모두 실패하면 스크린샷 첨부를 포기하고 실패 단계만 남긴다.

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

스크린샷 fast path가 실패하면 PR 생성을 중단하지 않고 다음처럼 남긴다.

```markdown
## 화면 변경

스크린샷은 fast path에서 자동 첨부하지 못했습니다.
캡처 대상: `<url or route>`
실패 단계: `<capture | github-login | upload | body-update>`
```

실제 인증 화면 QA가 남아 있으면 별도 코멘트로 분리한다.

```markdown
실제 preview QA는 배포 준비 후 follow-up comment로 남기겠습니다.
남은 확인: `<route and state>`
```

## Storage Policy

회사 S3/CDN 버킷은 기본 경로로 사용하지 않는다.

필요할 경우 사용자가 명시적으로 승인한 외부 storage만 별도 모드로 추가한다. 기본 모드는 GitHub 웹 UI attachment 업로드다.

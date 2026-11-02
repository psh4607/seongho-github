# 저장소 flow와 PR 대상 결정

PR 생성과 branch 재구성 전에 읽습니다. 목표는 flow 이름을 맞히는 것이 아니라, 이번 변경이 들어갈 **repository/base/head와 이후 승격 경로**를 근거로 결정하는 것입니다. 저장소의 flow 자체를 바꾸는 작업은 별도 요청입니다.

## 1. 작업 종류와 근거

먼저 feature/fix, release/promotion, hotfix/backport, stacked PR 중 이번 작업의 목적을 정합니다. “exp 배포”는 환경 요구이며 `exp` 또는 `main`을 base로 지정한 것과 다릅니다. coordinator가 배포 트리거를 근거로 선택한 base도 사용자 지정으로 간주하지 않습니다. 원래 사용자 요구와 저장소 지침에 맞는지 검증합니다.

다음 순서로 필요한 근거를 모읍니다.

1. 사용자가 이번 작업에 명시한 target과 기존에 합의한 결정. 명확한 예외 지시는 존중하고 일반 flow와 다른 점을 알립니다. 상충하는 사용자 요구가 있으면 확인합니다.
2. 해당 checkout에 적용되는 `AGENTS.md`, `CONTRIBUTING`, 개발·릴리스 문서. 개발 통합 브랜치와 릴리스 브랜치를 구분합니다.
3. 같은 head repository/branch의 기존 open PR, branch별 `gh-merge-base`, worktree 생성 맥락. 기존 PR의 base도 오류일 수 있으므로 지침·이력과 대조합니다. push upstream은 PR base의 증거가 아닙니다.
4. 최근 merged/open PR의 **종류별** `head → base` 경로. 기능 PR과 승격/동기화 PR을 섞어 다수결로 base를 고르지 않습니다. 필요하면 관련 PR body와 diff를 읽습니다. 조회한 범위를 명시하고 부족하면 해당 종류로 추가 조회합니다.
5. 실제 remote branches와 ancestry/diff, CI branch/path filters, publish/deploy 조건. workflow의 `main → exp 환경 배포`는 feature PR을 main에 직접 보내라는 정책이 아닙니다. 브랜치 이름이나 존재만으로 역할을 단정하지 않습니다.

default branch는 후보·메타데이터일 뿐 자동 fallback이 아닙니다. 문서가 없더라도 최근 동종 PR과 실제 branch 관계가 일치하면 진행할 수 있습니다. 명확한 사용자 지정도 없고 신뢰할 근거가 부족하거나 서로 충돌하면 선택지와 이유를 좁혀 한 번 질문합니다. 그동안 diff, 테스트, PR 본문 준비는 계속하되 base 의존 branch 재구성·게시·병합은 보류합니다.

## 2. 최소 조회 예시

아래 값은 실제 확인한 repository/remote/ref로 대체합니다. `origin`이 fork인지, base repository가 upstream인지 먼저 확인합니다. URL에 자격 증명이 포함돼 있다면 출력에서 제거합니다.

```bash
git status -sb
git branch --show-current
git remote -v
git config --get branch.<current-branch>.gh-merge-base
gh repo view <base-owner/repo> --json nameWithOwner,defaultBranchRef
gh pr list --repo <base-owner/repo> --state open --head <head-branch> \
  --json number,url,baseRefName,headRefName,headRepository,headRepositoryOwner
gh pr list --repo <base-owner/repo> --state merged --limit 30 \
  --json number,title,baseRefName,headRefName,mergedAt,url
```

`--head` 검색은 branch 이름만으로 fork 소유자를 보장하지 않으므로 결과의 head repository/owner도 대조합니다. 설정값이 없다는 정상 결과와 인증/네트워크/API 실패를 구분합니다. 조회 실패를 “PR 없음” 또는 default base 사용의 근거로 바꾸지 않습니다.

선택한 base를 소유한 remote를 fetch한 뒤, 검증된 remote-tracking ref와 실제 head commit을 비교합니다. 로컬 branch 이름 충돌을 피하도록 전체 ref를 쓸 수 있습니다.

```bash
git fetch <base-remote>
git log --oneline <base-ref>..HEAD
git diff --stat <base-ref>...HEAD
git diff <base-ref>...HEAD
git diff
git diff --cached
```

commit 목록과 three-dot diff에 의도하지 않은 기능이 들어가면 base를 바꾸어 숨기지 않습니다. stacked 의존성, 잘못된 출발점, 통합 브랜치의 미승격 작업, squash/cherry-pick 중복인지 확인합니다. 동일 patch여도 ancestry가 다를 수 있어 ahead/behind 숫자나 merge-base만으로 정상 여부를 판정하지 않습니다. shallow checkout에 필요한 이력이 없으면 해당 ref의 이력을 보강하거나 한계를 보고합니다. 사용자 변경을 잃는 reset/rebase, 공유 이력 재작성, 무단 force-push는 하지 않습니다.

## 3. flow별 판단 예시

아래는 판단 예시이며 branch 이름을 강제하는 규칙이 아닙니다. 로컬 문서와 이력이 우선합니다.

| 확인된 운영 방식 | 일반 기능 PR | 별도로 확인할 경로 |
| --- | --- | --- |
| GitHub Flow / trunk-based | 짧은 작업 branch → 실제 통합 trunk (`main`, `master` 등) | release/backport branch가 있다면 해당 정책 |
| Git Flow | feature → develop 계열 통합 branch | release/hotfix → 대상 release/main 및 통합 branch 반영 정책 |
| exp/dev 통합 후 승격 | feature → exp/dev | 검증 후 exp/dev → main 등 승격 PR |
| release branch 유지 | 작업 대상 버전에 맞는 base | backport 필요 여부와 방식 |
| stacked PR | 후속 작업 → 선행 작업 branch | 선행 PR 병합 후 base/diff 재검증 |
| fork 기여 | fork head → upstream의 기여 대상 branch | base repository와 head owner를 별도로 확인 |

승격 PR은 통합 branch 전체가 head일 수 있고, 일반 기능 PR은 변경 범위가 좁아야 합니다. 필요한 배포가 main에서만 실행된다는 이유로 기능 통합 단계를 건너뛰거나 feature PR을 배포 PR로 바꾸지 않습니다. 반대로 명시적으로 허용된 hotfix를 무조건 develop으로 돌리지 않습니다.

main 직접 반영이 허용된 예외라면 장기 통합 branch로 역동기화가 필요한지 기록합니다. merge, cherry-pick, backport 중 어떤 방식인지 저장소 정책을 확인합니다. 역동기화 누락이 반드시 충돌을 만든다고 단정하지 말고 이력 분기·중복 적용·추후 충돌 가능성을 설명합니다. 요청 범위를 넘는 승격/동기화 PR을 자동 생성하거나 병합하지 않습니다.

## 4. 생성 전후 검증

생성 전에 다음을 짧게 기록하고 사용자에게 target과 핵심 근거를 알립니다. 별도 승인 체크리스트를 만들 필요는 없습니다.

- 작업 종류, base repository/branch/ref, head repository/branch/SHA
- 근거: 관련 지침 경로와 동종 PR 번호 또는 명확한 사용자 지정
- PR에 들어갈 commit/diff 범위, 병합 시 실제 CI/배포 영향
- 후속 승격/역동기화가 필요한지와 현재 요청 범위에 포함되는지

결정한 값으로 `gh pr create --repo ... --base ... --head ... --title ... --body-file ...`를 실행합니다. draft 기본값은 본문 스킬을 따릅니다. fork head는 지원되는 `owner:branch` 형태로 구분하고, 도구가 해당 소유자 유형을 지원하지 않으면 다른 repository로 보내지 말고 기능 한계를 보고합니다.

생성 후 반환된 PR URL을 다시 조회해 base/head repository·branch·SHA를 결정값과 대조합니다. 명령이 실패해도 PR이 생성됐을 수 있으므로 재시도 전에 기존 PR을 확인합니다. base/head가 바뀌거나 선행 PR이 병합되면 diff, CI, 리뷰 조건을 다시 확인합니다. 기존 PR을 retarget할 때도 이 절차를 적용하며, 이전 base에서의 검증 결과를 그대로 사용하지 않습니다.

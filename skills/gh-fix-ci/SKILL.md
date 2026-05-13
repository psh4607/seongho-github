---
name: "gh-fix-ci"
description: "GitHub PR URL의 CI 실패, failing checks, failed checks, GitHub Actions, workflow log, PR checks를 디버깅하거나 수정할 때 사용합니다. gh pr checks, gh run view, gh api로 PR metadata, Actions check, log를 확인합니다."
---

# GitHub Actions CI 수정

## 개요

이 스킬은 pull request의 CI 실패, PR checks 실패, GitHub Actions check 실패, workflow log 조사가 필요할 때 사용합니다.

이 워크플로우는 `gh` 우선입니다.

- PR metadata, 변경 파일, 현재 branch PR 확인에는 `gh pr view`를 사용합니다.
- GitHub Actions check와 log 확인에는 `gh pr checks`, `gh run view`, `gh api`를 사용합니다.
- 먼저 root cause를 요약하고, 집중된 수정 계획을 제안한 뒤, 명시적인 승인 후 구현합니다.

전제 조건: GitHub CLI로 한 번 인증한 뒤 `gh auth status`로 확인합니다. Actions 확인에는 보통 repo와 workflow scope가 필요합니다.

## 입력

- `repo`: 대상 repo 안의 path, 기본값 `.`
- `pr`: PR 번호 또는 URL, 선택사항. 없으면 현재 branch PR을 사용합니다.
- 해당 repo host에 대한 `gh` 인증

## Quick Start

- `python "<path-to-skill>/scripts/inspect_pr_checks.py" --repo "." --pr "<number-or-url>"`
- 요약용 machine-friendly output이 필요하면 `--json`을 추가합니다.

## 워크플로우

1. `gh` 인증을 확인합니다.
   - repo 안에서 `gh auth status`를 실행합니다.
   - 인증되어 있지 않으면 repo와 workflow scope를 포함해 `gh auth login`을 실행하도록 요청합니다.
2. PR을 확인합니다.
   - 사용자가 PR 번호나 URL을 제공했다면 그것을 직접 사용합니다.
   - 그렇지 않으면 `gh pr view --json number,url,headRefName,baseRefName`으로 현재 branch PR을 우선 확인합니다.
   - 실패를 diff와 연결해야 하면 `gh pr view --json files`로 변경 파일을 가져옵니다.
3. GitHub Actions failing check를 확인합니다.
   - 권장: `gh` field drift와 job-log fallback을 처리하는 bundled script를 실행합니다.
     - `python "<path-to-skill>/scripts/inspect_pr_checks.py" --repo "." --pr "<number-or-url>"`
     - machine-friendly output이 필요하면 `--json`을 추가합니다.
   - 수동 fallback:
     - `gh pr checks <pr> --json name,state,bucket,link,startedAt,completedAt,workflow`
     - field가 거부되면 `gh`가 알려주는 available field로 다시 실행합니다.
     - 각 failing check의 details URL에서 run id를 추출하고 다음을 실행합니다.
       - `gh run view <run_id> --json name,workflowName,conclusion,status,url,event,headBranch,headSha`
       - `gh run view <run_id> --log`
     - job log를 직접 가져와야 하면 다음을 사용합니다.
       - `gh api "/repos/<owner>/<repo>/actions/jobs/<job_id>/logs" > "<path>"`
4. GitHub Actions가 아닌 check를 분리합니다.
   - details URL이 GitHub Actions run이 아니면 external로 표시하고 URL만 보고합니다.
   - 사용자가 별도 조사를 명시적으로 요청하지 않는 한 Buildkite 등 다른 provider는 파고들지 않습니다.
5. 실패를 요약합니다.
   - failing check 이름, run URL, 간결한 log snippet을 제공합니다.
   - log가 없으면 명시적으로 말하고 확실하지 않은 내용을 단정하지 않습니다.
6. 집중된 수정 계획을 제안하고 승인을 기다립니다.
   - 계획은 failing check와 관찰된 root cause에 직접 연결되어야 합니다.
7. 승인 후 구현합니다.
   - 승인된 수정만 로컬에 적용합니다.
   - 가능한 가장 관련 있는 로컬 검증을 실행합니다.
8. 상태를 다시 확인하고 남은 risk를 요약합니다.
   - 관련 test와 `gh pr checks` 재실행을 제안합니다.
   - 아직 검증하지 못한 것, flaky 가능성, external failing check 여부를 보고합니다.

## Bundled Resources

### scripts/inspect_pr_checks.py

failing PR check를 가져오고, GitHub Actions log를 수집하며, 실패 snippet을 추출합니다. 실패가 남아 있으면 non-zero로 종료하므로 automation에도 사용할 수 있습니다.

사용 예시:

- `python "<path-to-skill>/scripts/inspect_pr_checks.py" --repo "." --pr "123"`
- `python "<path-to-skill>/scripts/inspect_pr_checks.py" --repo "." --pr "https://github.com/org/repo/pull/123" --json`
- `python "<path-to-skill>/scripts/inspect_pr_checks.py" --repo "." --max-lines 200 --context 40`

## Guardrails

- 사용자가 별도 investigation을 명시적으로 원하지 않는 한 GitHub Actions가 아닌 provider는 report-only로 취급합니다.
- 실패가 local diff와 명확히 무관하면 code change를 제안하기 전에 그렇게 말합니다.

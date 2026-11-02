import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'plugins/seongho-github/skills/yeet/scripts/validate_publish_ready.py'
BODY = '## 작업 배경\n승격\n## 티켓 및 링크\n없음\n## 작업 내용\n검증된 변경 승격\n## 테스트\nCI 통과\n'


class PublishNamingPolicyTests(unittest.TestCase):
    def run_guard(self, branch, policy=None, body=BODY, message='chore: promote release'):
        with tempfile.TemporaryDirectory() as tmp:
            command = [sys.executable, str(SCRIPT), '--repo', tmp, '--branch', branch,
                       '--body', body, '--title', 'Promote release', '--commit-message', message]
            if policy is not None:
                path = Path(tmp) / 'policy.json'
                path.write_text(json.dumps(policy))
                command += ['--naming-policy-file', str(path)]
            return subprocess.run(command, capture_output=True, text=True)

    def test_repository_policy_accepts_promotion_head_without_renaming(self):
        result = self.run_guard('exp', {'source': 'AGENTS.md:34; promotion PR #9', 'branch_pattern': 'exp'})
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_default_policy_still_rejects_unrecognised_head(self):
        self.assertNotEqual(self.run_guard('exp').returncode, 0)

    def test_policy_requires_evidence(self):
        result = self.run_guard('exp', {'branch_pattern': 'exp'})
        self.assertNotEqual(result.returncode, 0)

    def test_repository_policy_does_not_disable_body_checks(self):
        result = self.run_guard('exp', {'source': 'AGENTS.md:34', 'branch_pattern': 'exp'}, body='')
        self.assertNotEqual(result.returncode, 0)

    def test_pattern_must_match_entire_branch(self):
        result = self.run_guard('exp-extra', {'source': 'AGENTS.md:34', 'branch_pattern': 'exp'})
        self.assertNotEqual(result.returncode, 0)

    def test_repository_commit_convention(self):
        result = self.run_guard('feat/example', {'source': 'CONTRIBUTING.md:12', 'commit_pattern': 'PROJ-[0-9]+ .+'}, message='PROJ-12 Add action')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_policy_fails_closed(self):
        result = self.run_guard('exp', {'source': 'AGENTS.md:34', 'branch_pattern': '['})
        self.assertNotEqual(result.returncode, 0)

    def test_blank_names_and_messages_are_not_validated_by_permissive_policy(self):
        for branch, message in [('bad branch', 'release'), ('exp', '')]:
            result = self.run_guard(branch, {'source': 'AGENTS.md:34', 'branch_pattern': '.*', 'commit_pattern': '.*'}, message=message)
            self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()

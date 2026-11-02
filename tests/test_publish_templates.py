import importlib.util
import inspect
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'plugins/seongho-github/skills/yeet/scripts/validate_publish_ready.py'
spec = importlib.util.spec_from_file_location('publish_guard', SCRIPT)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class TemplateTests(unittest.TestCase):
    def test_only_rendered_headings_count(self):
        markdown = '## Summary\n<!--\n## Performance\n-->\n```md\n## Example\n```\n~~~\n## Another example\n~~~\n## Testing\n'
        self.assertEqual(guard.markdown_headings(markdown), ['Summary', 'Testing'])

    def test_inline_backtick_run_does_not_hide_following_heading(self):
        self.assertEqual(guard.markdown_headings('## Summary\n```npm test``` passed\n## Testing'), ['Summary', 'Testing'])

    def test_comment_marker_inside_fence_does_not_hide_following_heading(self):
        self.assertEqual(guard.markdown_headings('## Summary\n```html\n<!--\n```\n## Testing'), ['Summary', 'Testing'])

    def test_hidden_body_heading_cannot_satisfy_requirement(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'template.md'
            path.write_text('## Summary\n## Testing\n')
            errors = []
            guard.validate_body_against_template('## Summary\n<!-- ## Testing -->', [path], errors)
            self.assertTrue(errors)

class OptionalTemplateTests(unittest.TestCase):
    def check(self, body, optional):
        self.assertIn('optional_headings', inspect.signature(guard.validate_body_against_template).parameters, 'Repository optional-section policy is not supported')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'template.md'
            path.write_text('## Summary\n## Testing\n## Proof\n## 작업 내용 (필수)\n')
            errors = []
            guard.validate_body_against_template(body, [path], errors, optional_headings=optional)
            return errors

    def test_documented_optional_section_can_be_omitted(self):
        self.assertEqual(self.check('## Summary\n## Testing\n## 작업 내용 (필수)', {'Proof': 'Template permits omission for non-UI changes; CI-only diff.'}), [])

    def test_other_required_sections_still_checked(self):
        self.assertTrue(self.check('## Summary', {'Proof': 'CI-only change'}))

    def test_unknown_heading_or_empty_reason_rejected(self):
        for optional in [{'Typo': 'Not applicable'}, {'Proof': ''}, {'작업 내용 (필수)': 'Skip'}]:
            with self.assertRaises(ValueError):
                self.check('## Summary', optional)

class TemplateCliTests(unittest.TestCase):
    def run_guard(self, policy):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.github').mkdir()
            (root / '.github/pull_request_template.md').write_text('## Obsolete local heading')
            template = root / 'remote-template.md'
            template.write_text('## Summary\n## Testing\n## Proof\n<!-- ## Example -->')
            policy_path = root / 'policy.json'
            policy_path.write_text(json.dumps(policy))
            return subprocess.run([sys.executable, str(SCRIPT), '--repo', tmp,
                '--branch', 'fix/template-check', '--body', '## Summary\nCI config only\n## Testing\nFixture check',
                '--template', str(template), '--template-policy-file', str(policy_path)], text=True, capture_output=True)

    def test_explicit_remote_template_and_documented_omission(self):
        result = self.run_guard({'source': 'repo@sha:template permits omission for CI-only work', 'optional_headings': {'Proof': 'No visible behavior change'}})
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_policy_evidence_is_rejected(self):
        result = self.run_guard({'source': '', 'optional_headings': {'Proof': 'CI only'}})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('repository evidence', result.stderr)

    def test_required_section_not_exempted_still_fails(self):
        result = self.run_guard({'source': 'repo@sha:template', 'optional_headings': {}})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Proof', result.stderr)

if __name__ == '__main__':
    unittest.main()

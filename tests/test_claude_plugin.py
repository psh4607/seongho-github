import json
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODEX_PLUGIN = ROOT / 'plugins/seongho-github'
CLAUDE_PLUGIN = ROOT / 'claude/seongho-github'
SHARED_FIELDS = ('name', 'version', 'description', 'author', 'homepage', 'repository', 'license', 'keywords')
# Codex 전용 도구에 의존해 Claude Code에 링크하지 않는 스킬. 추가할 때는 README와 PR에 사유를 남긴다.
CODEX_ONLY_SKILLS = set()
# 스킬 본문이 플러그인 루트 기준으로 참조하는 리소스.
SHARED_ROOT_RESOURCES = ('docs',)


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


class ClaudePluginTests(unittest.TestCase):
    def assert_relative_link(self, link, target):
        self.assertTrue(link.is_symlink(), f'{link} must be a symlink')
        self.assertFalse(os.path.isabs(os.readlink(link)), f'{link} must use a relative target')
        self.assertEqual(link.resolve(), target.resolve())

    def test_manifest_metadata_matches_codex(self):
        codex = load_json(CODEX_PLUGIN / '.codex-plugin/plugin.json')
        claude = load_json(CLAUDE_PLUGIN / '.claude-plugin/plugin.json')
        for field in SHARED_FIELDS:
            self.assertEqual(claude.get(field), codex.get(field), field)
        self.assertEqual(claude.get('displayName'), codex['interface']['displayName'])

    def test_skills_link_to_codex_sources(self):
        codex_skills = {path.name for path in (CODEX_PLUGIN / 'skills').iterdir() if (path / 'SKILL.md').is_file()}
        claude_skills = {path.name for path in (CLAUDE_PLUGIN / 'skills').iterdir() if not path.name.startswith('.')}
        self.assertEqual(claude_skills, codex_skills - CODEX_ONLY_SKILLS)
        for name in claude_skills:
            self.assert_relative_link(CLAUDE_PLUGIN / 'skills' / name, CODEX_PLUGIN / 'skills' / name)

    def test_shared_root_resources_link_to_codex_sources(self):
        for name in SHARED_ROOT_RESOURCES:
            self.assert_relative_link(CLAUDE_PLUGIN / name, CODEX_PLUGIN / name)

    def test_marketplace_lists_claude_plugin(self):
        marketplace = load_json(ROOT / '.claude-plugin/marketplace.json')
        entries = {entry['name']: entry for entry in marketplace['plugins']}
        self.assertEqual(entries['seongho-github']['source'], './claude/seongho-github')


if __name__ == '__main__':
    unittest.main()

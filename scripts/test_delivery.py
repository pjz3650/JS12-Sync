"""Checks for distribution integrity and the CI -> Render verification gate."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import deploy_render
import package_release


class DeliveryTests(unittest.TestCase):
    def test_package_is_repeatable_and_excludes_local_secrets(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ('README.md', 'LICENSE', '.env.example', 'Instalar JS12 Sync.cmd',
                         'CONTRIBUTING.md', 'docs/ci-cd.md', 'docs/theme-studio.md',
                         'docs/assets/banner.svg', 'mp4-sync/app.py',
                         'mp4-sync/requirements-lock.txt', 'mp4-sync/README.md'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('example', encoding='utf-8')
            for name in ('.env.local', 'mp4-sync/auth-user.bin', 'mp4-sync/song.mp3'):
                (root / name).write_text('private', encoding='utf-8')
            with patch.object(package_release, 'ROOT', root):
                package_release.package('a' * 40)
                first = (root / 'dist/JS12-Sync-Windows.zip').read_bytes()
                package_release.package('a' * 40)
                self.assertEqual(first, (root / 'dist/JS12-Sync-Windows.zip').read_bytes())
            with zipfile.ZipFile(io.BytesIO(first)) as archive:
                names = archive.namelist()
                self.assertFalse(any(name.endswith(('.env.local', '.bin', '.mp3')) for name in names))
                self.assertEqual(json.loads(archive.read('JS12-Sync/RELEASE.json'))['commit'], 'a' * 40)

    def run_deploy(self, version_hash, download=b'tested-package'):
        digest = hashlib.sha256(b'tested-package').hexdigest()
        responses = [io.BytesIO(b''), io.BytesIO(json.dumps({
            'commit': 'a' * 40, 'sha256': digest if version_hash is None else version_hash,
        }).encode()), io.BytesIO(download)]
        responses[0].status = 200
        environment = {'RENDER_DEPLOY_HOOK_URL': 'https://api.render.com/deploy/srv-test?key=secret',
                       'RENDER_SITE_URL': 'https://example.onrender.com', 'GITHUB_SHA': 'a' * 40}
        with patch.dict('os.environ', environment, clear=True), \
             patch.object(deploy_render, 'urlopen', side_effect=responses) as request, \
             patch.object(Path, 'read_text', return_value=digest + '  JS12-Sync-Windows.zip'):
            deploy_render.deploy()
        return request

    def test_deploy_checks_exact_commit_and_public_download(self):
        request = self.run_deploy(None)
        hook = request.call_args_list[0].args[0]
        self.assertIn('ref=' + 'a' * 40, hook.full_url)
        self.assertEqual(hook.method, 'POST')
        self.assertEqual(request.call_count, 3)

    def test_deploy_rejects_package_different_from_ci(self):
        with self.assertRaisesRegex(RuntimeError, 'differs'):
            self.run_deploy('wrong-hash')

    def test_deploy_rejects_corrupt_public_download(self):
        with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
            self.run_deploy(None, b'corrupt')


if __name__ == '__main__':
    unittest.main()

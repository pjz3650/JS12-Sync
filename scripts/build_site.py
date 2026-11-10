"""Build the desktop application's public download page on Render (stdlib only)."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from package_release import ROOT, package


def build():
    commit = os.environ.get('RENDER_GIT_COMMIT') or subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    package(commit)
    site = ROOT / 'dist' / 'site'
    downloads = site / 'downloads'
    downloads.mkdir(parents=True, exist_ok=True)
    for name in ('JS12-Sync-Windows.zip', 'SHA256SUMS.txt'):
        shutil.copyfile(ROOT / 'dist' / name, downloads / name)
    digest = hashlib.sha256((downloads / 'JS12-Sync-Windows.zip').read_bytes()).hexdigest()
    (site / 'version.json').write_text(json.dumps({
        'commit': commit, 'sha256': digest, 'built_at': time.time(),
    }), encoding='utf-8')
    template = (ROOT / 'site' / 'index.html').read_text(encoding='utf-8')
    (site / 'index.html').write_text(template.replace('{{COMMIT}}', commit).replace('{{SHA256}}', digest), encoding='utf-8')
    print(f'Site ready: {commit}')


if __name__ == '__main__':
    build()

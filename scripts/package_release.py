"""Package only distributable application files, with provenance and checksums."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def package(commit):
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Expected a full Git commit SHA')
    files = [ROOT / name for name in (
        'README.md', 'LICENSE', '.env.example', 'Instalar JS12 Sync.cmd',
        'CONTRIBUTING.md', 'docs/ci-cd.md', 'docs/theme-studio.md', 'docs/assets/banner.svg',
    )]
    # No recursive directory copy: local settings, tokens, caches and venv stay out.
    for pattern in ('*.py', '*.cmd', 'requirements*.txt', 'README.md'):
        files.extend(sorted((ROOT / 'mp4-sync').glob(pattern)))
    entries = {path.relative_to(ROOT).as_posix(): path.read_bytes() for path in files}
    manifest = {
        'commit': commit,
        'platform': 'Windows',
        'python': '3.13',
        'installation': 'Instalar JS12 Sync.cmd',
        'files': {name: hashlib.sha256(data).hexdigest() for name, data in entries.items()},
    }
    entries['RELEASE.json'] = json.dumps(manifest, indent=2).encode('utf-8')
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    archive_path = output / 'JS12-Sync-Windows.zip'
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(entries.items()):
            # Stable metadata makes Windows CI and the Linux Render build identical.
            info = zipfile.ZipInfo('JS12-Sync/' + name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('Corrupt release archive')
        for name, digest in manifest['files'].items():
            if hashlib.sha256(archive.read('JS12-Sync/' + name)).hexdigest() != digest:
                raise RuntimeError(f'Invalid packaged file: {name}')
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    (output / 'SHA256SUMS.txt').write_text(f'{digest}  {archive_path.name}\n', encoding='ascii')
    print(f'{archive_path.name}: {len(entries)} files; SHA256 {digest}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    package(parser.parse_args().commit)

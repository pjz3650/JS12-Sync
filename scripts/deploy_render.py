"""Trigger Render for the tested SHA, then verify the public deployment and ZIP."""
import hashlib
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


def deploy():
    hook = os.environ['RENDER_DEPLOY_HOOK_URL']
    site = os.environ['RENDER_SITE_URL'].rstrip('/')
    commit = os.environ['GITHUB_SHA']
    parsed = urlsplit(hook)
    if parsed.scheme != 'https' or parsed.hostname != 'api.render.com':
        raise ValueError('Expected an HTTPS Render deploy hook')
    if urlsplit(site).scheme != 'https':
        raise ValueError('Expected an HTTPS public site URL')
    query = dict(parse_qsl(parsed.query))
    query['ref'] = commit
    url = urlunsplit(parsed._replace(query=urlencode(query)))
    # Never print hook URLs, responses, or exceptions containing credentials.
    try:
        with urlopen(Request(url, method='POST'), timeout=30) as response:
            if response.status != 200:
                raise RuntimeError('Render rejected deployment')
    except (HTTPError, URLError) as error:
        raise RuntimeError('Render deploy hook failed; check the repository secret') from None
    print(f'Render deploy requested for {commit}', flush=True)
    expected = Path('dist/SHA256SUMS.txt').read_text().split()[0]
    deadline = time.monotonic() + 720
    while time.monotonic() < deadline:
        try:
            nonce = time.time_ns()
            with urlopen(f'{site}/version.json?verify={nonce}', timeout=30) as response:
                version = json.load(response)
            if version.get('commit') == commit:
                if version.get('sha256') != expected:
                    raise RuntimeError('Render package differs from the Windows CI artifact')
                with urlopen(f'{site}/downloads/JS12-Sync-Windows.zip?verify={nonce}', timeout=60) as response:
                    digest = hashlib.sha256(response.read()).hexdigest()
                if digest != expected:
                    raise RuntimeError('Public download checksum mismatch')
                print(f'Deployment verified: {site}; SHA256 {digest}')
                summary = os.environ.get('GITHUB_STEP_SUMMARY')
                if summary:
                    with open(summary, 'a', encoding='utf-8') as stream:
                        stream.write(f'### Render verificado\n\n[Aplicacao publicada]({site})\n\nCommit: {commit}\n\nSHA256: {digest}\n')
                return
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            pass
        time.sleep(15)
    raise RuntimeError('Timed out waiting for the tested commit on Render')


if __name__ == '__main__':
    deploy()

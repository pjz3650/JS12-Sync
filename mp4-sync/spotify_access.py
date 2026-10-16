"""Read-only Spotify OAuth PKCE; no password, desktop-cache or browser-cookie access."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import ctypes
import json
import secrets
import time
import webbrowser

import requests
from spotipy.cache_handler import CacheHandler
from spotipy.oauth2 import SpotifyPKCE

REDIRECT = 'http://127.0.0.1:8765/callback'
SCOPES = 'playlist-read-private playlist-read-collaborative'


class Blob(ctypes.Structure):
    _fields_ = [('size', ctypes.c_ulong), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def protect(data, decrypt=False):
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    if decrypt:
        ok = ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target))
    else:
        ok = ctypes.windll.crypt32.CryptProtectData(ctypes.byref(source), 'JS12 Spotify', None, None, None, 1, ctypes.byref(target))
    if not ok:
        raise OSError('Falha na protecao da autorizacao do Spotify pelo Windows.')
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        ctypes.windll.kernel32.LocalFree(ctypes.cast(target.data, ctypes.c_void_p))


class ProtectedCache(CacheHandler):
    def __init__(self, path):
        self.path = Path(path)

    def get_cached_token(self):
        try:
            return json.loads(protect(self.path.read_bytes(), decrypt=True))
        except (OSError, ValueError):
            return None

    def save_token_to_cache(self, token_info):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(protect(json.dumps(token_info).encode('utf-8')))


class SpotifyAccess:
    def __init__(self, client_id, state_dir, notify=print, cancelled=lambda: False):
        if not client_id or len(client_id) != 32 or not all(c in '0123456789abcdefABCDEF' for c in client_id):
            raise ValueError('Configure o Client ID do seu aplicativo Spotify uma vez, em Configurar acesso.')
        self.notify = notify
        self.cancelled = cancelled
        self.state = secrets.token_urlsafe(24)
        self.oauth = SpotifyPKCE(client_id=client_id, redirect_uri=REDIRECT, state=self.state,
                                scope=SCOPES, cache_handler=ProtectedCache(Path(state_dir) / ('auth-' + client_id + '.bin')),
                                open_browser=False, requests_timeout=20)

    def connect(self, interactive=False):
        if self.oauth.validate_token(self.oauth.cache_handler.get_cached_token()):
            return
        if not interactive:
            raise RuntimeError('Conecte sua conta pelo botao Conectar Spotify antes de ativar o automatico.')
        result = {}
        expected_state = self.state

        class Callback(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlsplit(self.path)
                if parsed.path != '/callback':
                    self.send_error(404)
                    return
                values = parse_qs(parsed.query)
                if not secrets.compare_digest(values.get('state', [''])[0], expected_state):
                    self.send_error(400, 'Invalid state')
                    return
                result.update({key: items[0] for key, items in values.items()})
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write('Pode voltar ao JS12 Sync no computador.'.encode('utf-8'))

            def log_message(self, *_):
                pass  # Authorization codes must never be logged.

        with HTTPServer(('127.0.0.1', 8765), Callback) as server:
            server.timeout = 1
            webbrowser.open(self.oauth.get_authorize_url(state=self.state))
            self.notify('Autorize o acesso de leitura no navegador. Aguardando por ate 3 minutos...')
            deadline = time.monotonic() + 180
            while not result and time.monotonic() < deadline:
                if self.cancelled():
                    raise RuntimeError('Conexão interrompida.')
                server.handle_request()
        if result.get('error'):
            raise RuntimeError('O acesso ao Spotify nao foi autorizado.')
        if not result.get('code'):
            raise RuntimeError('O login expirou. Clique em Conectar Spotify para tentar novamente.')
        self.oauth.get_access_token(code=result['code'], check_cache=False)

    def pages(self, path):
        url = 'https://api.spotify.com/v1/' + path.lstrip('/')
        while url:
            if self.cancelled():
                raise RuntimeError('Consulta interrompida.')
            parsed = urlsplit(url)
            if parsed.scheme != 'https' or parsed.netloc != 'api.spotify.com' or not parsed.path.startswith('/v1/'):
                raise RuntimeError('Endereco inesperado na resposta do Spotify.')
            for attempt in range(3):
                token = self.oauth.get_access_token()
                response = requests.get(url, headers={'Authorization': 'Bearer ' + token}, timeout=25)
                if response.status_code == 429 and attempt < 2:
                    delay = min(30, max(1, int(response.headers.get('Retry-After', '5'))))
                    self.notify(f'Spotify pediu uma pausa de {delay}s.')
                    time.sleep(delay)
                    continue
                if response.status_code in (401, 403):
                    raise RuntimeError(f'Spotify recusou este acesso ({response.status_code}). Verifique a conta autorizada e as permissoes do aplicativo.')
                if not response.ok:
                    raise RuntimeError(f'Falha na consulta ao Spotify: HTTP {response.status_code}.')
                break
            response.raise_for_status()
            payload = response.json()
            yield from payload.get('items', [])
            url = payload.get('next')

    def playlists(self):
        return [{'id': p['id'], 'name': p['name'], 'tracks_count': (p.get('items') or p.get('tracks') or {}).get('total', 0)}
                for p in self.pages('me/playlists?limit=50') if p and p.get('id')]

    def tracks(self, playlist):
        tracks = []
        for entry in self.pages(f"playlists/{playlist['id']}/items?limit=50"):
            raw = (entry or {}).get('item') or (entry or {}).get('track')
            if not raw or raw.get('type', 'track') != 'track' or not raw.get('id') or entry.get('is_local') or raw.get('is_local'):
                self.notify(f"{playlist['name']}: item local, indisponivel ou podcast ignorado.")
                continue
            artists = [artist['name'] for artist in raw.get('artists', [])]
            if not artists:
                continue
            tracks.append({'id': raw['id'], 'name': raw['name'], 'artist': artists[0], 'artists': artists,
                           'duration': int(raw.get('duration_ms', 0) / 1000), 'raw': raw})
        return dict(playlist, tracks=tracks)

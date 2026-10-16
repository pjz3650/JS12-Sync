"""Device identification and non-destructive file deployment for the JS-12."""
from pathlib import Path
import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata

DEVICE_SERIAL = '4512482ADF0FEEEE'
DEVICE_VENDOR = 'VEN_ACTIONS'
MANAGED = 'SPOTIFY_SYNC'
CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def safe_name(value, limit=65):
    text = unicodedata.normalize('NFKD', str(value)).encode('ascii', 'ignore').decode()
    text = re.sub(r'[^A-Za-z0-9 _().-]', '_', text).strip(' .')
    text = re.sub(r'\s+', ' ', text)[:limit].strip(' .') or 'Sem nome'
    if text.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
        text = '_' + text
    return text


def valid_id(value):
    if not re.fullmatch(r'[A-Za-z0-9]{1,32}', str(value)):
        raise ValueError('Identificador de faixa ou playlist invalido.')
    return str(value)


def device_roots():
    # Read-only discovery, matched to the actual player's USB serial, not a fixed D:.
    script = """
    $letters = @();
    Get-CimInstance Win32_DiskDrive | Where-Object {
      $_.PNPDeviceID -like '*VEN_ACTIONS*' -and $_.PNPDeviceID -like '*4512482ADF0FEEEE*'
    } | ForEach-Object {
      Get-CimAssociatedInstance -InputObject $_ -Association Win32_DiskDriveToDiskPartition | ForEach-Object {
        Get-CimAssociatedInstance -InputObject $_ -Association Win32_LogicalDiskToPartition | ForEach-Object {
          $letters += $_.DeviceID
        }
      }
    }; ConvertTo-Json -InputObject @($letters | Select-Object -Unique) -Compress
    """
    result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', script],
                            capture_output=True, text=True, timeout=20, creationflags=CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError('Nao foi possivel identificar o USB pelo Windows.')
    values = json.loads(result.stdout.strip() or '[]')
    return [Path(letter + '\\') for letter in values if re.fullmatch(r'[A-Za-z]:', letter)]


def volume_serial(root):
    serial = ctypes.c_ulong()
    ok = ctypes.windll.kernel32.GetVolumeInformationW(str(root), None, 0, ctypes.byref(serial), None, None, None, 0)
    if not ok:
        raise OSError('MP4 desconectado ou indisponivel.')
    return serial.value


def fingerprint(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def contained(path, root):
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(Path(root).resolve()):
        raise ValueError('Destino fora da pasta de sincronizacao.')
    return resolved


def atomic_bytes(target, data, guard):
    guard()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.js12-', suffix='.tmp', delete=False) as out:
            temporary = Path(out.name)
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        guard()
        os.replace(temporary, target)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def atomic_copy(source, target, guard):
    guard()
    if target.exists():
        if fingerprint(source) == fingerprint(target):
            return False
        raise RuntimeError(f'Arquivo existente diferente; preservado: {target.name}')
    guard()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.js12-', suffix='.tmp', delete=False) as out:
            temporary = Path(out.name)
            with source.open('rb') as stream:
                while chunk := stream.read(1024 * 1024):
                    guard()
                    out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        if fingerprint(source) != fingerprint(temporary):
            raise OSError('A copia nao passou na verificacao de integridade.')
        guard()
        os.replace(temporary, target)
        return True
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def deploy(root, playlists, cached, guard, notify=print):
    """Only writes our marked directory; never edits firmware, LIBs or existing MP3s."""
    root = Path(root)
    guard()
    managed = contained(root / MANAGED, root)
    marker = managed / '.js12-sync.json'
    if managed.exists() and not marker.exists():
        raise RuntimeError('SPOTIFY_SYNC ja existe sem identificacao do programa; pasta preservada.')
    owned = json.loads(marker.read_text(encoding='utf-8')) if marker.exists() else {'app': 'js12-sync-v1', 'playlists': {}}
    if owned.get('app') != 'js12-sync-v1':
        raise RuntimeError('Pasta de destino nao reconhecida.')
    for playlist in playlists:
        valid_id(playlist['id'])
        for track in playlist['tracks']:
            valid_id(track['id'])
    music = contained(managed / 'Music', managed)
    needed, seen = 0, set()
    for playlist in playlists:
        for track in playlist['tracks']:
            source = cached.get(track['id'])
            name = safe_name(f"{track['artist']} - {track['name']}", 75) + '-' + track['id'] + '.mp3'
            target = contained(music / name, managed)
            if track['id'] not in seen and source and Path(source).is_file() and not target.exists():
                needed += Path(source).stat().st_size
            seen.add(track['id'])
    if shutil.disk_usage(root).free < needed + 16 * 1024 * 1024:
        raise OSError('Espaco insuficiente no MP4 para esta sincronizacao.')
    guard()
    managed.mkdir(exist_ok=True)
    atomic_bytes(marker, json.dumps(owned, ensure_ascii=False).encode('utf-8'), guard)
    music.mkdir(exist_ok=True)
    installed = {}
    copied = 0
    for playlist in playlists:
        for track in playlist['tracks']:
            song_id = track['id']
            source = cached.get(song_id)
            if song_id in installed or not source or not Path(source).is_file():
                continue
            name = safe_name(f"{track['artist']} - {track['name']}", 75) + '-' + song_id + '.mp3'
            target = contained(music / name, managed)
            copied += int(atomic_copy(Path(source), target, guard))
            installed[song_id] = target
        missing = [track for track in playlist['tracks'] if track['id'] not in installed]
        playlist_name = safe_name(playlist['name']) + '-' + playlist['id'] + '.m3u'
        target = contained(managed / playlist_name, managed)
        # Preserve the previous full playlist if this run failed to obtain any item.
        if missing:
            notify(f"{playlist['name']}: faltam {len(missing)} faixas; lista anterior preservada.")
            continue
        lines = ['#EXTM3U', '#PLAYLIST:' + safe_name(playlist['name'], 120)]
        for track in playlist['tracks']:
            lines += [f"#EXTINF:{track.get('duration', -1)},{safe_name(track['artist'] + ' - ' + track['name'], 160)}",
                      'Music\\' + installed[track['id']].name]
        atomic_bytes(target, ('\r\n'.join(lines) + '\r\n').encode('ascii'), guard)
        previous = owned['playlists'].get(playlist['id'])
        if previous and previous != playlist_name:
            old = contained(managed / previous, managed)
            if old.suffix.lower() == '.m3u' and old.is_file():
                guard()
                old.unlink()
        owned['playlists'][playlist['id']] = playlist_name
        atomic_bytes(marker, json.dumps(owned, ensure_ascii=False, indent=2).encode('utf-8'), guard)
        notify(f"Playlist pronta: {playlist['name']} ({len(playlist['tracks'])} faixas).")
    return copied

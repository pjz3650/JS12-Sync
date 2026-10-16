"""Separate, disposable download process. Receives metadata, never OAuth tokens."""
import json
from pathlib import Path
import sys

from core import valid_id


def to_song(track):
    from spotdl.types.song import Song
    raw = track.get('raw', {})
    album = raw.get('album') or {}
    artists = track.get('artists') or [track['artist']]
    date = album.get('release_date') or '2000'
    images = album.get('images') or []
    return Song(
        name=track['name'], artists=artists, artist=artists[0], genres=[],
        disc_number=raw.get('disc_number') or 1, disc_count=raw.get('disc_number') or 1,
        album_name=album.get('name') or track['name'],
        album_artist=next(iter(album.get('artists') or []), {}).get('name') or artists[0],
        duration=track.get('duration', 0), year=int(date[:4]), date=date,
        track_number=raw.get('track_number') or 1, tracks_count=album.get('total_tracks') or 1,
        song_id=valid_id(track['id']), explicit=bool(raw.get('explicit')), publisher='',
        url='https://open.spotify.com/track/' + valid_id(track['id']),
        isrc=(raw.get('external_ids') or {}).get('isrc'),
        cover_url=images[0].get('url') if images else None, copyright_text=None,
        album_id=album.get('id') or '', artist_id=(raw.get('artists') or [{}])[0].get('id') or '',
        album_type=album.get('album_type') or 'album')


def valid_audio(path):
    from mutagen.mp3 import MP3
    try:
        return path.is_file() and MP3(path).info.length > 0
    except Exception:
        return False


def run(job_path):
    from spotdl.download.downloader import Downloader
    job = json.loads(Path(job_path).read_text(encoding='utf-8'))
    cache = Path(job['cache']).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    results, pending = {}, []
    for track in job['tracks']:
        song_id = valid_id(track['id'])
        path = cache / (song_id + '.mp3')
        if valid_audio(path):
            results[song_id] = str(path)
        else:
            # Cache belongs exclusively to this program; retry incomplete downloads.
            if path.exists():
                path.unlink()
            pending.append(to_song(track))
    print(f'{len(results)} faixas no cache; {len(pending)} para procurar.', flush=True)
    if pending:
        downloader = Downloader(settings={
            'audio_providers': ['youtube-music', 'youtube'], 'lyrics_providers': [],
            'output': str(cache / '{track-id}.{output-ext}'), 'format': 'mp3',
            'bitrate': '128k', 'overwrite': 'skip', 'threads': 2, 'simple_tui': True,
            'print_errors': True, 'fetch_albums': False,
        })
        try:
            for song, path in downloader.download_multiple_songs(pending):
                if path and Path(path).resolve() == cache / (song.song_id + '.mp3') and valid_audio(Path(path)):
                    results[song.song_id] = str(Path(path).resolve())
        finally:
            downloader.loop.close()
    Path(job['result']).write_text(json.dumps(results), encoding='utf-8')
    print(f'{len(results)} faixas disponiveis; {len(job["tracks"]) - len(results)} pendentes.', flush=True)


if __name__ == '__main__':
    run(sys.argv[1])

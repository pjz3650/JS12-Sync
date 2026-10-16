"""Offline tests: file safety, Spotify response shapes and download integration."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

import core
from download_worker import to_song
from spotify_access import SpotifyAccess, ProtectedCache, protect


def track(song_id='song1'):
    return {'id': song_id, 'name': 'Canção', 'artist': 'Artista', 'artists': ['Artista'], 'duration': 123}


def playlist(pid='list1', tracks=None):
    return {'id': pid, 'name': 'Minha playlist', 'tracks': tracks if tracks is not None else [track()]}


class FileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.usb = self.base / 'usb'
        self.usb.mkdir()
        self.source = self.base / 'song.mp3'
        self.source.write_bytes(b'audio-for-copy-test')

    def test_duplicate_tracks_share_audio_and_keep_order_and_original(self):
        original = self.usb / 'original.mp3'
        original.write_bytes(b'original-do-usuario')
        hidden = self.usb / 'MUSIC.LIB'
        hidden.write_bytes(b'library')
        lists = [playlist(tracks=[track(), track('song2'), track()]), playlist('list2')]
        cache = {'song1': str(self.source), 'song2': str(self.source)}
        self.assertEqual(core.deploy(self.usb, lists, cache, lambda: None, lambda _: None), 2)
        self.assertEqual(original.read_bytes(), b'original-do-usuario')
        self.assertEqual(hidden.read_bytes(), b'library')
        music = self.usb / core.MANAGED / 'Music'
        self.assertEqual(len(list(music.glob('*.mp3'))), 2)
        lines = next((self.usb / core.MANAGED).glob('*list1.m3u')).read_text().splitlines()
        entries = [line for line in lines if not line.startswith('#')]
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0], entries[2])
        self.assertNotEqual(entries[0], entries[1])
        # Incremental sync must not require space for all existing audio again.
        with patch('core.shutil.disk_usage', return_value=Mock(free=16 * 1024 * 1024 + 1)):
            self.assertEqual(core.deploy(self.usb, lists, cache, lambda: None, lambda _: None), 0)

    def test_unmarked_folder_is_untouched(self):
        folder = self.usb / core.MANAGED
        folder.mkdir()
        own = folder / 'mine.txt'
        own.write_text('user')
        with self.assertRaises(RuntimeError):
            core.deploy(self.usb, [playlist()], {'song1': self.source}, lambda: None)
        self.assertEqual(list(folder.iterdir()), [own])

    def test_traversal_id_rejected_before_writing(self):
        with self.assertRaises(ValueError):
            core.deploy(self.usb, [playlist('../evil')], {}, lambda: None)
        self.assertEqual(list(self.usb.iterdir()), [])

    def test_insufficient_space_writes_nothing(self):
        with patch('core.shutil.disk_usage', return_value=Mock(free=0)):
            with self.assertRaises(OSError):
                core.deploy(self.usb, [playlist()], {'song1': self.source}, lambda: None)
        self.assertEqual(list(self.usb.iterdir()), [])

    def test_disconnect_mid_copy_has_no_final_or_temp_file(self):
        calls = 0

        def guard():
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError('disconnected')
        with self.assertRaises(OSError):
            core.atomic_copy(self.source, self.usb / 'output.mp3', guard)
        self.assertEqual(list(self.usb.iterdir()), [])

    def test_existing_different_file_preserved(self):
        target = self.usb / 'existing.mp3'
        target.write_bytes(b'preserve')
        with self.assertRaises(RuntimeError):
            core.atomic_copy(self.source, target, lambda: None)
        self.assertEqual(target.read_bytes(), b'preserve')

    def test_missing_download_preserves_previous_playlist(self):
        core.deploy(self.usb, [playlist()], {'song1': self.source}, lambda: None, lambda _: None)
        m3u = next((self.usb / core.MANAGED).glob('*.m3u'))
        before = m3u.read_bytes()
        core.deploy(self.usb, [playlist(tracks=[track(), track('missing')])], {'song1': self.source}, lambda: None, lambda _: None)
        self.assertEqual(m3u.read_bytes(), before)


class AccessTests(unittest.TestCase):
    def test_dpapi_and_cache_roundtrip(self):
        secret = b'example-not-real-token'
        encrypted = protect(secret)
        self.assertNotIn(secret, encrypted)
        self.assertEqual(protect(encrypted, decrypt=True), secret)
        with tempfile.TemporaryDirectory() as folder:
            cache = ProtectedCache(Path(folder) / 'token.bin')
            self.assertIsNone(cache.get_cached_token())
            cache.save_token_to_cache({'access_token': 'fake-token'})
            self.assertEqual(cache.get_cached_token()['access_token'], 'fake-token')

    def test_new_and_legacy_items_and_skip_local(self):
        api = SpotifyAccess('0' * 32, Path(tempfile.gettempdir()), lambda _: None)
        raw = {'type': 'track', 'id': 'song1', 'name': 'Song', 'artists': [{'name': 'Artist'}], 'duration_ms': 123000}
        api.pages = lambda _: iter([{'item': raw}, {'track': dict(raw, id='song2')}, {'item': dict(raw, is_local=True)}, None])
        result = api.tracks({'id': 'list1', 'name': 'List'})
        self.assertEqual([t['id'] for t in result['tracks']], ['song1', 'song2'])

    def test_paginated_api_and_no_external_next_url(self):
        api = SpotifyAccess('0' * 32, Path(tempfile.gettempdir()), lambda _: None)
        api.oauth.get_access_token = lambda: 'fake-token'
        responses = [Mock(ok=True, status_code=200), Mock(ok=True, status_code=200)]
        responses[0].json.return_value = {'items': [1], 'next': 'https://api.spotify.com/v1/me/playlists?offset=1'}
        responses[1].json.return_value = {'items': [2], 'next': None}
        with patch('spotify_access.requests.get', side_effect=responses) as request:
            self.assertEqual(list(api.pages('me/playlists')), [1, 2])
            self.assertEqual(request.call_count, 2)
        responses[0].json.return_value = {'items': [], 'next': 'https://example.com/steal'}
        with patch('spotify_access.requests.get', return_value=responses[0]) as request:
            with self.assertRaises(RuntimeError):
                list(api.pages('me/playlists'))
            self.assertEqual(request.call_count, 1)

    def test_metadata_does_not_require_spotify_refetch(self):
        song = to_song(track())
        for field in ('genres', 'disc_count', 'tracks_count', 'track_number', 'album_id', 'album_artist'):
            self.assertIsNotNone(getattr(song, field))
        self.assertEqual(song.song_id, 'song1')


if __name__ == '__main__':
    unittest.main()

"""Offline tests for declarative generation, revision approval and exports."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
import zipfile

from theme_agent import generate_design, local_setting, API_URL
from theme_design import (ThemeSession, RESOLUTIONS, design_digest, dimensions, element,
                          example_design, export_approved, is_approval, render_screen, rgb565le, validate_design)


class DesignTests(unittest.TestCase):
    def test_all_resolutions_render_and_rgb565_length(self):
        for resolution in RESOLUTIONS:
            with self.subTest(resolution=resolution):
                design = example_design(resolution)
                image = render_screen(design, resolution)
                self.assertEqual(image.size, dimensions(resolution))
                self.assertEqual(len(rgb565le(image)), image.width * image.height * 2)

    def test_out_of_screen_and_unknown_fields_rejected(self):
        design = example_design()
        design['screens'][0]['elements'][0]['x'] = 128
        with self.assertRaises(ValueError):
            validate_design(design, '128x160')
        design = example_design()
        design['screens'][0]['elements'][0]['command'] = 'anything'
        with self.assertRaises(ValueError):
            validate_design(design, '128x160')

    def test_tiny_icons_render_safely(self):
        from theme_design import ICONS
        for icon in ICONS:
            design = example_design()
            design['screens'][0]['elements'] = [element('icon', 0, 0, 1, 1, icon=icon)]
            render_screen(design, '128x160')

    def test_changes_require_new_approval(self):
        session = ThemeSession(design=example_design())
        session.approve()
        self.assertTrue(session.approved)
        updated = deepcopy(session.design)
        updated['name'] = 'Alterado'
        session.revise(updated)
        self.assertFalse(session.approved)
        session.approve()
        # Even a mutation outside revise cannot silently keep an old approval.
        session.design['name'] = 'Outro'
        self.assertFalse(session.approved)

    def test_user_phrase_exact_and_negated_not_approved(self):
        self.assertTrue(is_approval('Ficou bom!'))
        self.assertTrue(is_approval('Ficou bom, pode implementar.'))
        for phrase in ('não ficou bom', 'ficou bom mas mude a cor', 'ele disse ficou bom', 'ficou bom?', 'se ficou bom'):
            self.assertFalse(is_approval(phrase))

    def test_roundtrip_and_tampered_approval_invalidated(self):
        session = ThemeSession(design=example_design())
        session.history.append({'role': 'user', 'content': 'quero verde'})
        session.approve()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'session.json'
            session.save(path)
            data = json.loads(path.read_text(encoding='utf-8'))
            self.assertTrue(ThemeSession.from_dict(data).approved)
            data['design']['name'] = 'Alterado depois de aprovar'
            self.assertFalse(ThemeSession.from_dict(data).approved)

    def test_export_requires_approval_and_never_claims_installable(self):
        session = ThemeSession(design=example_design())
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                export_approved(session, folder)
            session.approve()
            package = export_approved(session, folder)
            with zipfile.ZipFile(package) as archive:
                manifest = json.loads(archive.read('manifest.json'))
                self.assertFalse(manifest['installable'])
                self.assertFalse(manifest['resolution_confirmed_on_device'])
                self.assertEqual(manifest['approved_design_sha256'], design_digest(session.design, session.resolution))
                for name, digest in manifest['files'].items():
                    import hashlib
                    self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), digest)
                self.assertEqual(len(archive.read('screen-01.rgb565le')), 128 * 160 * 2)
                self.assertTrue(all('/' not in name and '\\' not in name for name in archive.namelist()))


class AgentTests(unittest.TestCase):
    def test_local_key_lookup_without_mutating_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '.env.local'
            path.write_text('OPENAI_API_KEY="fake-only-for-test"\n', encoding='utf-8')
            with patch.dict('os.environ', {}, clear=True):
                self.assertEqual(local_setting('OPENAI_API_KEY', folder), 'fake-only-for-test')
                self.assertFalse(local_setting('MISSING', folder))

    def response(self, design=None):
        payload = {'reply': 'Aqui está a proposta.', 'design': design or example_design()}
        return Mock(status_code=200, json=lambda: {'status': 'completed', 'output': [
            {'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(payload)}]}]})

    def test_structured_api_contract_and_no_key_in_body(self):
        with patch('theme_agent.local_setting', return_value='fake-token'), patch('theme_agent.requests.post', return_value=self.response()) as request:
            result = generate_design([{'role': 'user', 'content': 'quero verde'}], None, '128x160')
            self.assertEqual(result['design'], example_design())
            args, kwargs = request.call_args
            self.assertEqual(args[0], API_URL)
            self.assertFalse(kwargs['allow_redirects'])
            self.assertFalse(kwargs['json']['store'])
            self.assertNotIn('fake-token', json.dumps(kwargs['json']))
            self.assertNotIn('tools', kwargs['json'])
            self.assertTrue(kwargs['json']['text']['format']['strict'])

    def test_api_limit_does_not_expose_server_body_or_retry(self):
        response = Mock(status_code=429, text='sensitive detail')
        with patch('theme_agent.local_setting', return_value='fake-token'), patch('theme_agent.requests.post', return_value=response) as request:
            with self.assertRaises(RuntimeError) as context:
                generate_design([{'role': 'user', 'content': 'oi'}], None, '128x160')
            self.assertNotIn('sensitive detail', str(context.exception))
            self.assertEqual(request.call_count, 1)

    def test_invalid_ai_drawing_rejected(self):
        design = example_design()
        design['screens'][0]['elements'][0]['color'] = 'url(example.com)'
        with patch('theme_agent.local_setting', return_value='fake-token'), patch('theme_agent.requests.post', return_value=self.response(design)):
            with self.assertRaises(RuntimeError):
                generate_design([{'role': 'user', 'content': 'oi'}], None, '128x160')


if __name__ == '__main__':
    unittest.main()

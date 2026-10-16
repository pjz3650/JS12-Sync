"""Bounded, declarative screen designs. No model-generated code is executed."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata
import uuid
import zipfile

from PIL import Image, ImageDraw, ImageFont

RESOLUTIONS = ('128x160', '160x128', '128x128', '240x320', '320x240')
KINDS = ('rect', 'text', 'line', 'circle', 'progress', 'icon')
ICONS = ('none', 'music', 'play', 'pause', 'folder', 'settings', 'battery', 'headphones')
IMPLEMENTATION_BLOCKERS = (
    'Backup completo do firmware original ainda não obtido e validado.',
    'Conversão do desenho para os recursos STY/MCG do aparelho ainda não implementada.',
    'Gravação e recuperação do firmware ainda não validadas neste aparelho.',
)


def object_schema(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


ELEMENT_SCHEMA = object_schema({
    'kind': {'type': 'string', 'enum': list(KINDS)},
    'x': {'type': 'integer'}, 'y': {'type': 'integer'},
    'width': {'type': 'integer'}, 'height': {'type': 'integer'},
    'color': {'type': 'string'}, 'text': {'type': 'string'},
    'size': {'type': 'integer'}, 'radius': {'type': 'integer'},
    'value': {'type': 'integer'}, 'icon': {'type': 'string', 'enum': list(ICONS)},
})
DESIGN_SCHEMA = object_schema({
    'name': {'type': 'string'}, 'summary': {'type': 'string'},
    'screens': {'type': 'array', 'minItems': 1, 'maxItems': 4, 'items': object_schema({
        'name': {'type': 'string'}, 'background': {'type': 'string'},
        'elements': {'type': 'array', 'maxItems': 36, 'items': ELEMENT_SCHEMA},
    })},
})
RESPONSE_SCHEMA = object_schema({'reply': {'type': 'string'}, 'design': DESIGN_SCHEMA})


def dimensions(resolution):
    if resolution not in RESOLUTIONS:
        raise ValueError('Escolha uma resolução disponível.')
    return tuple(map(int, resolution.split('x')))


def bounded_int(value, lower, upper, label):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError(f'{label} fora dos limites permitidos.')
    return value


def short_text(value, maximum, label):
    if not isinstance(value, str) or len(value) > maximum or any(ord(c) < 32 for c in value):
        raise ValueError(f'{label} inválido ou longo demais.')
    return value


def color(value):
    if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
        raise ValueError('Use cores no formato #RRGGBB.')
    return value


def validate_design(design, resolution):
    width, height = dimensions(resolution)
    if not isinstance(design, dict) or set(design) != {'name', 'summary', 'screens'}:
        raise ValueError('Estrutura do desenho inválida.')
    short_text(design['name'], 90, 'Nome')
    short_text(design['summary'], 800, 'Resumo')
    screens = design['screens']
    if not isinstance(screens, list) or not 1 <= len(screens) <= 4:
        raise ValueError('O desenho precisa ter entre uma e quatro telas.')
    for screen in screens:
        if not isinstance(screen, dict) or set(screen) != {'name', 'background', 'elements'}:
            raise ValueError('Tela inválida.')
        short_text(screen['name'], 60, 'Nome da tela')
        color(screen['background'])
        elements = screen['elements']
        if not isinstance(elements, list) or len(elements) > 36:
            raise ValueError('Uma tela pode ter até 36 elementos.')
        for item in elements:
            if not isinstance(item, dict) or set(item) != set(ELEMENT_SCHEMA['properties']):
                raise ValueError('Elemento inválido.')
            if item['kind'] not in KINDS or item['icon'] not in ICONS:
                raise ValueError('Tipo de elemento inválido.')
            x = bounded_int(item['x'], 0, width - 1, 'Posição X')
            y = bounded_int(item['y'], 0, height - 1, 'Posição Y')
            bounded_int(item['width'], 1, width - x, 'Largura')
            bounded_int(item['height'], 1, height - y, 'Altura')
            bounded_int(item['size'], 6, 32, 'Tamanho da fonte')
            bounded_int(item['radius'], 0, min(item['width'], item['height']) // 2, 'Raio')
            bounded_int(item['value'], 0, 100, 'Progresso')
            short_text(item['text'], 160, 'Texto')
            color(item['color'])
    return deepcopy(design)


def element(kind, x, y, width, height, color='#eeeeee', text='', size=10, radius=0, value=0, icon='none'):
    return dict(kind=kind, x=x, y=y, width=width, height=height, color=color, text=text,
                size=size, radius=radius, value=value, icon=icon)


def example_design(resolution='128x160'):
    width, height = dimensions(resolution)
    # Deliberately a sample, never attributed to an AI request.
    return validate_design({'name': 'Exemplo — Noite verde', 'summary': 'Exemplo local para explorar a prévia; ainda não foi gerado pela IA.',
        'screens': [{'name': 'Música', 'background': '#101b24', 'elements': [
            element('text', 8, 5, width - 16, 18, '#7be5ae', 'MINHAS MUSICAS', 10),
            element('rect', 8, 29, width - 16, height // 3, '#1d3944', radius=5),
            element('icon', width // 2 - 10, 37, 20, 24, '#7be5ae', icon='music'),
            element('text', 8, height // 2 + 8, width - 16, 18, '#ffffff', 'Sua musica', 12),
            element('text', 8, height // 2 + 27, width - 16, 13, '#adc2ce', 'Artista', 9),
            element('progress', 8, height - 28, width - 16, 4, '#7be5ae', value=42),
            element('icon', width // 2 - 6, height - 18, 12, 12, '#7be5ae', icon='play'),
        ]}]}, resolution)


def _font(size):
    path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'segoeui.ttf'
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default(size=size)


def _icon(draw, item):
    x, y, w, h = (item[k] for k in ('x', 'y', 'width', 'height'))
    c, icon = item['color'], item['icon']
    if icon == 'play':
        draw.polygon([(x, y), (x + w - 1, y + h // 2), (x, y + h - 1)], fill=c)
    elif icon == 'pause':
        draw.rectangle((x, y, x + max(1, w // 3) - 1, y + h - 1), fill=c)
        draw.rectangle((x + 2 * w // 3, y, x + w - 1, y + h - 1), fill=c)
    elif icon == 'music':
        draw.line([(x + w // 3, y + h * 3 // 4), (x + w // 3, y + 2), (x + w - 2, y), (x + w - 2, y + h * 2 // 3)], fill=c, width=2)
        draw.ellipse((x, y + h * 2 // 3, x + w // 3, y + h - 1), fill=c)
        draw.ellipse((x + w * 2 // 3, y + h // 2, x + w - 1, y + h * 3 // 4), fill=c)
    elif icon == 'folder':
        draw.rectangle((x, y + h // 4, x + w - 1, y + h - 1), outline=c)
        draw.line((x, y + h // 4, x, y, x + w // 2, y, x + w // 2, y + h // 4), fill=c)
    elif icon == 'battery':
        draw.rectangle((x, y, x + max(1, w - 3), y + h - 1), outline=c)
        draw.rectangle((x + w - 2, y + h // 3, x + w - 1, y + 2 * h // 3), fill=c)
    elif icon == 'headphones':
        draw.arc((x, y, x + w - 1, y + h - 1), 180, 360, fill=c, width=2)
        draw.line((x, y + h // 2, x, y + h - 1), fill=c, width=2)
        draw.line((x + w - 1, y + h // 2, x + w - 1, y + h - 1), fill=c, width=2)
    elif icon == 'settings':
        draw.ellipse((x, y, x + w - 1, y + h - 1), outline=c, width=2)
        draw.ellipse((x + w // 3, y + h // 3, x + w * 2 // 3, y + h * 2 // 3), outline=c)


def render_screen(design, resolution, index=0):
    design = validate_design(design, resolution)
    size = dimensions(resolution)
    screen = design['screens'][index]
    image = Image.new('RGB', size, screen['background'])
    draw = ImageDraw.Draw(image)
    for item in screen['elements']:
        x, y, w, h = (item[k] for k in ('x', 'y', 'width', 'height'))
        box = (x, y, x + w - 1, y + h - 1)
        kind, c = item['kind'], item['color']
        if kind == 'rect':
            draw.rounded_rectangle(box, radius=item['radius'], fill=c)
        elif kind == 'circle':
            draw.ellipse(box, fill=c)
        elif kind == 'line':
            draw.line((x, y, x + w - 1, y + h - 1), fill=c)
        elif kind == 'text':
            # Clip to the declared text box, including overlong model-generated text.
            layer = Image.new('RGB', (w, h))
            layer.paste(image.crop((x, y, x + w, y + h)))
            ImageDraw.Draw(layer).text((0, 0), item['text'], fill=c, font=_font(item['size']))
            image.paste(layer, (x, y))
        elif kind == 'progress':
            draw.rectangle(box, outline=c)
            progress = int((w - 2) * item['value'] / 100)
            if progress > 0 and h > 2:
                draw.rectangle((x + 1, y + 1, x + progress, y + h - 2), fill=c)
        elif kind == 'icon':
            # Isolate icon drawing to its box, including tiny icon edge cases.
            layer = image.crop((x, y, x + w, y + h))
            _icon(ImageDraw.Draw(layer), dict(item, x=0, y=0))
            image.paste(layer, (x, y))
    return image


def rgb565le(image):
    output = bytearray()
    for r, g, b in image.convert('RGB').get_flattened_data():
        value = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        output.extend(value.to_bytes(2, 'little'))
    return bytes(output)


def design_digest(design, resolution):
    validate_design(design, resolution)
    data = json.dumps({'resolution': resolution, 'design': design}, sort_keys=True, ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(data).hexdigest()


def is_approval(message):
    if '?' in message:
        return False
    text = unicodedata.normalize('NFKD', message.lower())
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r'[^a-z0-9 ]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text in {'ficou bom', 'ficou bom pode aprovar', 'ficou bom pode aplicar',
                    'ficou bom pode implementar', 'aprovar', 'aprovo', 'pode aprovar', 'aprovado'}


class ThemeSession:
    def __init__(self, resolution='128x160', design=None):
        dimensions(resolution)
        self.resolution = resolution
        self.design = validate_design(design, resolution) if design else None
        self.history = []
        self.approved_digest = None
        self.approved_at = None

    @property
    def approved(self):
        return bool(self.design and self.approved_digest == design_digest(self.design, self.resolution))

    def revise(self, design):
        self.design = validate_design(design, self.resolution)
        self.approved_digest = self.approved_at = None

    def approve(self):
        if not self.design:
            raise ValueError('Gere ou carregue um desenho antes de aprovar.')
        self.approved_digest = design_digest(self.design, self.resolution)
        self.approved_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self):
        return {'version': 1, 'resolution': self.resolution, 'design': self.design,
                'history': self.history[-60:], 'approved_digest': self.approved_digest,
                'approved_at': self.approved_at}

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or data.get('version') != 1:
            raise ValueError('Projeto de tela não reconhecido.')
        session = cls(data['resolution'], data.get('design'))
        history = data.get('history', [])
        if not isinstance(history, list) or len(history) > 60:
            raise ValueError('Histórico inválido.')
        for entry in history:
            if not isinstance(entry, dict) or entry.get('role') not in ('user', 'assistant') or not isinstance(entry.get('content'), str) or len(entry['content']) > 8000:
                raise ValueError('Mensagem inválida no histórico.')
        session.history = history
        if session.design and data.get('approved_digest') == design_digest(session.design, session.resolution):
            session.approved_digest = data['approved_digest']
            session.approved_at = data.get('approved_at')
        return session

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='.theme-', dir=path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(self.to_dict(), stream, ensure_ascii=False, indent=2)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def export_approved(session, folder):
    if not session.approved:
        raise ValueError('Aprove a revisão atual antes de exportar.')
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    files = {'design.json': json.dumps({'resolution': session.resolution, 'design': session.design}, ensure_ascii=False, indent=2).encode('utf-8')}
    for i in range(len(session.design['screens'])):
        image = render_screen(session.design, session.resolution, i)
        buffer = io.BytesIO()
        image.save(buffer, 'PNG')
        files[f'screen-{i + 1:02d}.png'] = buffer.getvalue()
        files[f'screen-{i + 1:02d}.rgb565le'] = rgb565le(image)
    manifest = {'format': 'js12-design-package-v1', 'installable': False,
                'resolution': session.resolution, 'resolution_confirmed_on_device': False,
                'approved_at': session.approved_at, 'approved_design_sha256': session.approved_digest,
                'blockers': list(IMPLEMENTATION_BLOCKERS),
                'files': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}
    files['manifest.json'] = json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8')
    files['LEIA-ME.txt'] = ('PACOTE DE DESENHO — NÃO É FIRMWARE NEM TEMA INSTALÁVEL.\n'
        'PNG e RGB565LE são recursos genéricos de prévia. Não são arquivos STY/MCG.\n'
        'A resolução é uma escolha de projeto, ainda não confirmada na unidade física.\n'
        'Copiar este ZIP para o MP4 não muda a interface.\n\n' + '\n'.join(IMPLEMENTATION_BLOCKERS)).encode('utf-8')
    target = folder / ('tema-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8] + '.zip')
    temporary = target.with_suffix('.tmp')
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in files.items():
                archive.writestr(name, data)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target

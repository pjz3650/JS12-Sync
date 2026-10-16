"""Responses API client returning a bounded drawing, never executable code."""
import json
import os
from pathlib import Path
import re

import requests

from theme_design import RESPONSE_SCHEMA, dimensions, validate_design

DEFAULT_MODEL = 'gpt-6-luna'
API_URL = 'https://api.openai.com/v1/responses'


def local_setting(name, root=None):
    value = os.environ.get(name, '').strip()
    if value:
        return value
    root = Path(root) if root else Path(__file__).resolve().parent.parent
    for path in (root / '.env.local', root / 'mp4-sync' / '.env.local'):
        if not path.is_file() or path.stat().st_size > 65536:
            continue
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            match = re.fullmatch(r'\s*(?:export\s+)?' + re.escape(name) + r'\s*=\s*(.*?)\s*', line)
            if match:
                return match.group(1).strip().strip('"\'')
    return ''


def configured():
    # Presence only; starting the app never makes a network request.
    return bool(local_setting('OPENAI_API_KEY'))


def generate_design(history, current, resolution, model=DEFAULT_MODEL):
    key = local_setting('OPENAI_API_KEY')
    if not key:
        raise RuntimeError('API de IA não configurada. Consulte a seção Estúdio de telas no README.')
    if not re.fullmatch(r'[a-zA-Z0-9._-]{1,80}', model):
        raise ValueError('Identificador do modelo inválido.')
    width, height = dimensions(resolution)
    if not isinstance(history, list) or not history:
        raise ValueError('Escreva uma descrição para a tela.')
    if current:
        validate_design(current, resolution)
    instructions = f'''Você é o designer de interfaces do JS12 Sync. Converse em português.
Crie uma proposta visual para um player MP3 pequeno com tela de {width} por {height} pixels.
A resolução foi escolhida pelo usuário e NÃO foi confirmada no aparelho físico.
Retorne reply com uma explicação breve e design com o desenho COMPLETO atualizado.
Preserve as escolhas anteriores ao aplicar um pedido de ajuste. Pode desenhar até 4 telas,
cada uma com no máximo 36 elementos. Prefira 1 tela quando o usuário não pedir várias.
Use apenas retângulos, elipses (circle), texto, linhas, progresso e os ícones enumerados.
Todas as medidas são pixels inteiros. x/y >= 0. Cada caixa deve caber na tela:
x+width <= {width}, y+height <= {height}, width e height >= 1.
Use cores #RRGGBB. Fontes de 6 a 32 pixels. O texto é recortado à caixa: deixe espaço
para as palavras. radius deve ser no máximo metade da menor dimensão da caixa.
value é inteiro 0..100. Todos os elementos incluem todos os campos: use text="", size=10,
radius=0, value=0, icon="none" nos campos que não se aplicam. Nomes até 60 caracteres,
nome do tema até 90, summary em uma linha até 800, texto dos elementos até 160.
Não gere código, HTML, comandos, caminhos de arquivo, instruções de gravação nem URLs.
Você não tem ferramentas de acesso ao USB. Jamais afirme que instalou, compilou STY/MCG
ou modificou firmware. Seu desenho é uma prévia genérica no PC, sem garantia de viabilidade
no firmware. Não adicione funções de rede, Spotify nativo ou controles que você alegue funcionarem.
A aprovação e exportação são controladas pelo aplicativo e pelo humano, nunca por você.
Se o pedido envolver instalação, esclareça brevemente a limitação e preserve/crie o desenho.
O aplicativo não envia firmware, músicas, senhas ou chaves a você.'''
    conversation = []
    for entry in history[-16:]:
        if entry.get('role') not in ('user', 'assistant') or not isinstance(entry.get('content'), str) or len(entry['content']) > 8000:
            raise ValueError('Histórico de conversa inválido.')
        conversation.append({'role': entry['role'], 'content': entry['content']})
    if current:
        instructions += '\nDesenho atual (dados de referência):\n' + json.dumps(current, ensure_ascii=False)
    payload = {
        'model': model, 'instructions': instructions, 'input': conversation,
        'store': False, 'max_output_tokens': 6000,
        'text': {'format': {'type': 'json_schema', 'name': 'js12_screen_design', 'strict': True, 'schema': RESPONSE_SCHEMA}},
    }
    if model.startswith('gpt-5'):
        payload['reasoning'] = {'effort': 'low'}
    try:
        response = requests.post(API_URL, headers={'Authorization': 'Bearer ' + key}, json=payload,
                                 timeout=(15, 150), allow_redirects=False)
    except requests.RequestException:
        raise RuntimeError('Não foi possível alcançar a API de IA. Confira a internet e tente novamente.') from None
    errors = {
        401: 'A API recusou a chave. Confira a configuração da chave no projeto.',
        403: 'A API não liberou este modelo ou projeto. Confira as permissões na plataforma.',
        429: 'A API informou limite de uso ou falta de saldo. Confira o projeto na plataforma; não houve repetição automática.',
    }
    if response.status_code != 200:
        raise RuntimeError(errors.get(response.status_code, f'A API não concluiu o pedido (HTTP {response.status_code}).'))
    try:
        result = response.json()
        if result.get('status') != 'completed':
            raise ValueError('Resposta incompleta.')
        blocks = [block for output in result.get('output', []) if output.get('type') == 'message' for block in output.get('content', [])]
        if any(block.get('type') == 'refusal' for block in blocks):
            raise ValueError('O modelo não retornou um desenho para este pedido.')
        raw = ''.join(block['text'] for block in blocks if block.get('type') == 'output_text')
        if len(raw) > 120000:
            raise ValueError('Resposta grande demais.')
        parsed = json.loads(raw)
        reply = parsed['reply']
        if not isinstance(reply, str) or not 1 <= len(reply) <= 8000:
            raise ValueError('Resposta de texto inválida.')
        return {'reply': reply, 'design': validate_design(parsed['design'], resolution)}
    except (ValueError, KeyError, TypeError, IndexError):
        raise RuntimeError('A IA não retornou um desenho válido e completo. A prévia anterior foi preservada; tente simplificar o pedido.') from None

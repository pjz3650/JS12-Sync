"""Chat, preview and explicit approval. Firmware installation is unavailable."""
from copy import deepcopy
import json
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from PIL import Image, ImageTk

from theme_agent import DEFAULT_MODEL, configured, generate_design, local_setting
from theme_design import (RESOLUTIONS, ThemeSession,
                          example_design, render_screen, export_approved, is_approval)


class ThemeStudio(ttk.Frame):
    def __init__(self, parent, state_dir):
        super().__init__(parent, padding=14)
        self.state_dir = Path(state_dir) / 'studio'
        self.project_path = self.state_dir / 'session.json'
        self.events = queue.Queue()
        self.busy = False
        self.closed = False
        self.request_id = 0
        self.last_package = None
        try:
            self.session = ThemeSession.from_dict(json.loads(self.project_path.read_text(encoding='utf-8')))
        except (OSError, ValueError, KeyError, TypeError):
            self.session = ThemeSession()
        self.resolution = tk.StringVar(value=self.session.resolution)
        self.screen = tk.StringVar()
        self.model = tk.StringVar(value=local_setting('OPENAI_MODEL') or DEFAULT_MODEL)
        self.status = tk.StringVar()
        ttk.Label(self, text='Estúdio de telas com IA', font=('Segoe UI', 17, 'bold')).pack(anchor='w')
        ttk.Label(self, text='Descreva, veja a prévia e peça ajustes. Diga “ficou bom” para aprovar a revisão.').pack(anchor='w', pady=(3, 10))
        controls = ttk.Frame(self)
        controls.pack(fill='x')
        ttk.Label(controls, text='Resolução de projeto:').pack(side='left')
        self.resolution_box = ttk.Combobox(controls, textvariable=self.resolution, values=RESOLUTIONS, width=12, state='readonly')
        self.resolution_box.pack(side='left', padx=6)
        self.resolution_box.bind('<<ComboboxSelected>>', self.change_resolution)
        ttk.Label(controls, text='Modelo:').pack(side='left', padx=(12, 0))
        self.model_entry = ttk.Entry(controls, textvariable=self.model, width=20)
        self.model_entry.pack(side='left', padx=6)
        self.sample_button = ttk.Button(controls, text='Exemplo local', command=self.load_example)
        self.sample_button.pack(side='right')
        self.new_button = ttk.Button(controls, text='Novo desenho', command=self.new_design)
        self.new_button.pack(side='right', padx=6)
        ttk.Label(self, text='A resolução real do JS-12 ainda precisa ser confirmada. A prévia usa fontes do PC.', foreground='#795100').pack(anchor='w', pady=(6, 8))

        body = ttk.Panedwindow(self, orient='horizontal')
        body.pack(fill='both', expand=True)
        left = ttk.Frame(body)
        right = ttk.Frame(body, padding=(14, 0, 0, 0))
        body.add(left, weight=3)
        body.add(right, weight=2)
        transcript = ttk.Frame(left)
        transcript.pack(fill='both', expand=True)
        self.chat = tk.Text(transcript, state='disabled', wrap='word', font=('Segoe UI', 10), width=48, height=15)
        self.chat.pack(side='left', fill='both', expand=True)
        scrollbar = ttk.Scrollbar(transcript, command=self.chat.yview)
        scrollbar.pack(side='right', fill='y')
        self.chat.configure(yscrollcommand=scrollbar.set)
        self.chat.tag_configure('user', foreground='#1d526f', spacing1=10)
        self.chat.tag_configure('assistant', foreground='#254f36', spacing1=10)
        self.chat.tag_configure('system', foreground='#685f4c', spacing1=10)
        ttk.Label(left, text='Seu pedido (Ctrl+Enter para enviar):').pack(anchor='w', pady=(8, 3))
        self.prompt = tk.Text(left, height=3, wrap='word', font=('Segoe UI', 10))
        self.prompt.pack(fill='x')
        self.prompt.bind('<Control-Return>', lambda _: self.send() or 'break')
        buttons = ttk.Frame(left)
        buttons.pack(fill='x', pady=8)
        self.send_button = ttk.Button(buttons, text='Enviar para IA', command=self.send)
        self.send_button.pack(side='left')
        self.cancel_button = ttk.Button(buttons, text='Cancelar pedido', command=self.cancel_request, state='disabled')
        self.cancel_button.pack(side='left', padx=6)

        ttk.Label(right, text='Prévia da revisão atual', font=('Segoe UI', 11, 'bold')).pack(anchor='w')
        self.screen_box = ttk.Combobox(right, textvariable=self.screen, state='readonly')
        self.screen_box.pack(fill='x', pady=6)
        self.screen_box.bind('<<ComboboxSelected>>', lambda _: self.preview())
        self.canvas = tk.Canvas(right, background='#e7ebee', highlightthickness=0, width=350, height=390)
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda _: self.preview())
        self.preview_image = None
        self.approval_label = ttk.Label(right, text='Nenhum desenho aprovado.', wraplength=350)
        self.approval_label.pack(anchor='w', pady=(8, 3))
        self.approve_button = ttk.Button(right, text='Ficou bom — aprovar e exportar', command=self.approve)
        self.approve_button.pack(fill='x', pady=4)
        ttk.Button(right, text='Abrir pasta de desenhos', command=self.open_folder).pack(fill='x', pady=4)
        ttk.Button(right, text='Aplicar no MP4 — indisponível', state='disabled').pack(fill='x', pady=4)
        ttk.Label(right, text='Falta validar o formato STY/MCG, o backup completo e a recuperação. Exportar não instala a interface.', wraplength=350, foreground='#795100').pack(anchor='w', pady=5)
        ttk.Label(self, textvariable=self.status, wraplength=940).pack(anchor='w', pady=(8, 0))
        self.append('system', 'Este chat cria desenhos no PC. Ao aprovar, você recebe um pacote com imagens e o projeto; a instalação no aparelho ainda não está disponível. Apenas a conversa e o desenho atual são enviados à API. As chamadas usam a cobrança da API da sua conta.')
        for entry in self.session.history:
            self.append(entry['role'], entry['content'])
        self.refresh()
        self.after(120, self.pump)

    def append(self, role, message):
        names = {'user': 'Você', 'assistant': 'IA', 'system': 'Estúdio'}
        self.chat.configure(state='normal')
        self.chat.insert('end', names.get(role, role) + ': ' + message + '\n', role)
        self.chat.see('end')
        self.chat.configure(state='disabled')

    def remember(self, role, message):
        self.session.history.append({'role': role, 'content': message})
        self.session.history = self.session.history[-60:]
        self.append(role, message)

    def persist(self):
        try:
            self.session.save(self.project_path)
        except OSError:
            self.append('system', 'Não foi possível salvar o projeto local. Confira o espaço e as permissões da pasta de dados.')

    def refresh(self):
        names = [s['name'] for s in self.session.design['screens']] if self.session.design else []
        previous = self.screen_box.current()
        self.screen_box.configure(values=[f'{i + 1}. {name}' for i, name in enumerate(names)])
        if names:
            self.screen_box.current(min(max(previous, 0), len(names) - 1))
        else:
            self.screen.set('')
        self.approval_label.configure(text='Revisão aprovada. Um novo ajuste exige outra aprovação.' if self.session.approved else 'Prévia não aprovada.' if names else 'Nenhum desenho gerado.')
        self.approve_button.configure(state='normal' if names and not self.busy else 'disabled')
        self.status.set('IA configurada. Os pedidos usam a API da sua conta.' if configured() else 'Configure OPENAI_API_KEY no arquivo local indicado no README para usar o chat. O exemplo funciona sem API.')
        self.preview()

    def preview(self):
        self.canvas.delete('all')
        if not self.session.design:
            self.canvas.create_text(max(100, self.canvas.winfo_width() // 2), 80,
                text='Descreva uma tela no chat\nou abra o exemplo local.', fill='#53626d', justify='center')
            return
        image = render_screen(self.session.design, self.session.resolution, max(0, self.screen_box.current()))
        width, height = image.size
        cw, ch = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        scale = min((cw - 24) / width, (ch - 30) / height, 4)
        scale = max(.2, scale)
        resized = image.resize((max(1, int(width * scale)), max(1, int(height * scale))), Image.Resampling.NEAREST)
        self.preview_image = ImageTk.PhotoImage(resized)
        self.canvas.create_image(cw // 2, ch // 2, image=self.preview_image)

    def set_busy(self, value):
        self.busy = value
        self.send_button.configure(state='disabled' if value else 'normal')
        self.cancel_button.configure(state='normal' if value else 'disabled')
        self.sample_button.configure(state='disabled' if value else 'normal')
        self.new_button.configure(state='disabled' if value else 'normal')
        self.resolution_box.configure(state='disabled' if value else 'readonly')
        self.model_entry.configure(state='disabled' if value else 'normal')
        self.approve_button.configure(state='normal' if self.session.design and not value else 'disabled')

    def send(self):
        if self.busy:
            return
        message = self.prompt.get('1.0', 'end').strip()
        if not message:
            return
        if len(message) > 6000:
            self.append('system', 'Use até 6.000 caracteres por pedido.')
            return
        if is_approval(message):
            self.prompt.delete('1.0', 'end')
            self.remember('user', message)
            self.approve()
            return
        self.prompt.delete('1.0', 'end')
        self.remember('user', message)
        self.persist()
        self.set_busy(True)
        self.status.set('A IA está preparando a tela. Você pode continuar usando a aba de playlists.')
        self.request_id += 1
        request_id = self.request_id
        history = deepcopy(self.session.history)
        current = deepcopy(self.session.design)
        resolution, model = self.session.resolution, self.model.get().strip()

        def task():
            try:
                result = generate_design(history, current, resolution, model)
                self.events.put((request_id, 'result', result))
            except Exception as error:
                # The API client supplies sanitized errors; never log request headers.
                safe = str(error) if isinstance(error, (RuntimeError, ValueError)) else 'Não foi possível preparar o desenho. A prévia anterior foi preservada.'
                self.events.put((request_id, 'error', safe))
        threading.Thread(target=task, daemon=True).start()

    def pump(self):
        if self.closed:
            return
        try:
            while True:
                request_id, kind, result = self.events.get_nowait()
                if request_id != self.request_id:
                    continue
                self.set_busy(False)
                if kind == 'result':
                    self.session.revise(result['design'])
                    self.remember('assistant', result['reply'])
                    self.persist()
                    self.refresh()
                else:
                    self.append('system', result)
                    self.status.set('Pedido não concluído. Confira a mensagem no chat.')
        except queue.Empty:
            pass
        self.after(120, self.pump)

    def cancel_request(self):
        # Discard any eventual response. A request already sent may still be billed.
        self.request_id += 1
        self.set_busy(False)
        self.append('system', 'Resposta cancelada nesta janela. Um pedido já enviado à API pode continuar em processamento e ser cobrado.')
        self.refresh()

    def approve(self):
        if self.busy:
            return
        if not self.session.design:
            self.append('system', 'Gere uma tela primeiro; não há uma revisão para aprovar.')
            return
        try:
            self.session.approve()
            self.persist()
            self.last_package = export_approved(self.session, self.state_dir / 'exports')
            self.append('system', f'Revisão aprovada e pacote salvo: {self.last_package}\nO pacote contém desenho, PNG e recursos RGB565LE. Ele não é um tema STY/MCG instalável e não foi gravado no MP4.')
            self.refresh()
        except (OSError, ValueError):
            self.append('system', 'Não foi possível exportar. Confira as permissões e o espaço disponível na pasta de desenhos.')

    def new_design(self):
        if self.busy:
            return False
        if (self.session.design or self.session.history) and not messagebox.askyesno('Novo desenho', 'Substituir o desenho e a conversa atuais? Os pacotes já exportados permanecem salvos.', parent=self):
            return False
        self.session = ThemeSession(self.resolution.get())
        self.chat.configure(state='normal')
        self.chat.delete('1.0', 'end')
        self.chat.configure(state='disabled')
        self.persist()
        self.refresh()
        return True

    def change_resolution(self, _=None):
        if not self.new_design():
            self.resolution.set(self.session.resolution)

    def load_example(self):
        if self.new_design():
            self.session.revise(example_design(self.session.resolution))
            self.append('system', 'Exemplo local carregado; não houve chamada à IA. Peça ajustes no chat para continuar.')
            self.persist()
            self.refresh()

    def open_folder(self):
        self.state_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(self.state_dir)

    def shutdown(self):
        self.closed = True
        self.request_id += 1

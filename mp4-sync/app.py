"""Windows desktop playlist selector and JS-12 synchronizer."""
import ctypes
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser

from core import device_roots, volume_serial, deploy, CREATE_NO_WINDOW
from spotify_access import SpotifyAccess, REDIRECT
from theme_studio import ThemeStudio

HERE = Path(__file__).resolve().parent
STATE = Path(os.environ['LOCALAPPDATA']) / 'JS12Sync'
STATE.mkdir(parents=True, exist_ok=True)


class App:
    def __init__(self, root):
        self.root = root
        root.title('JS12 Sync — playlists no MP4')
        root.geometry('1100x820')
        root.minsize(960, 760)
        try:
            self.config = json.loads((STATE / 'config.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self.config = {}
        self.events = queue.Queue()
        self.busy = False
        self.process = None
        self.stop = threading.Event()
        self.playlists = []
        self.roots = []
        self.scanning = False
        self.last_mask = None
        self.all = tk.BooleanVar(value=self.config.get('all', True))
        self.auto = tk.BooleanVar(value=self.config.get('auto', False))
        self.status = tk.StringVar(value='Identificando o MP4...')
        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill='both', expand=True)
        outer = ttk.Frame(self.tabs, padding=16)
        self.tabs.add(outer, text='Playlists e MP4')
        self.studio = ThemeStudio(self.tabs, STATE)
        self.tabs.add(self.studio, text='Personalizar tela com IA')
        if '--studio' in sys.argv:
            self.tabs.select(self.studio)
        ttk.Label(outer, text='Spotify → JS-12', font=('Segoe UI', 19, 'bold')).pack(anchor='w')
        ttk.Label(outer, text='Escolha no PC. Escute os arquivos transferidos no MP4.').pack(anchor='w', pady=(2, 12))
        row = ttk.Frame(outer)
        row.pack(fill='x')
        ttk.Button(row, text='Configurar acesso', command=self.setup).pack(side='left')
        ttk.Button(row, text='Conectar Spotify / atualizar', command=lambda: self.start(self.load_playlists)).pack(side='left', padx=8)
        ttk.Checkbutton(outer, text='Todas as playlists disponíveis na minha conta', variable=self.all, command=self.options_changed).pack(anchor='w', pady=(14, 5))
        ttk.Label(outer, text='Ou desmarque acima e selecione as desejadas (Ctrl ou Shift para várias):').pack(anchor='w')
        frame = ttk.Frame(outer)
        frame.pack(fill='both', expand=True, pady=6)
        self.listbox = tk.Listbox(frame, selectmode='extended', exportselection=False, font=('Segoe UI', 10), height=10)
        self.listbox.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(frame, command=self.listbox.yview)
        scroll.pack(side='right', fill='y')
        self.listbox.configure(yscrollcommand=scroll.set)
        self.listbox.bind('<<ListboxSelect>>', lambda _: self.save())
        ttk.Checkbutton(outer, text='Sincronizar ao conectar este MP4 (com o programa aberto)', variable=self.auto, command=self.save).pack(anchor='w')
        actions = ttk.Frame(outer)
        actions.pack(fill='x', pady=10)
        ttk.Button(actions, text='Sincronizar agora', command=self.sync_clicked).pack(side='left')
        ttk.Button(actions, text='Parar', command=self.cancel).pack(side='left', padx=8)
        ttk.Button(actions, text='Iniciar com o Windows', command=self.install_startup).pack(side='right')
        ttk.Label(outer, textvariable=self.status).pack(anchor='w')
        self.logbox = tk.Text(outer, height=9, wrap='word', state='disabled', font=('Consolas', 9))
        self.logbox.pack(fill='both', pady=(8, 0))
        self.log('Primeiro uso: configure seu Client ID e conecte a conta. Não precisa de Client Secret.')
        self.log('MP3: cache no PC + pasta SPOTIFY_SYNC no aparelho. Músicas existentes são preservadas.')
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(150, self.pump)
        root.after(300, self.watch)
        if '--watch' in sys.argv:
            root.iconify()

    def log(self, message):
        self.events.put(('log', str(message)))

    def save(self):
        self.config.update(all=self.all.get(), auto=self.auto.get())
        if self.playlists:
            self.config['selected'] = [self.playlists[i]['id'] for i in self.listbox.curselection()]
        temp = STATE / 'config.tmp'
        temp.write_text(json.dumps(self.config, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temp, STATE / 'config.json')

    def options_changed(self):
        self.save()

    def start(self, action):
        if self.busy:
            self.log('Aguarde a tarefa atual ou clique em Parar.')
            return
        self.save()
        config = dict(self.config)
        self.busy = True
        self.stop.clear()
        self.status.set('Trabalhando...')

        def task():
            try:
                action(config)
            except Exception as error:
                self.log('Não concluído: ' + str(error))
            finally:
                self.events.put(('done', None))
        threading.Thread(target=task, daemon=True).start()

    def api(self, config, interactive=False):
        api = SpotifyAccess(config.get('client_id', ''), STATE, self.log, self.stop.is_set)
        api.connect(interactive=interactive)
        return api

    def load_playlists(self, config):
        api = self.api(config, interactive=True)
        playlists = api.playlists()
        self.events.put(('playlists', playlists))
        self.log(f'{len(playlists)} playlists disponíveis. Escolha todas ou selecione na lista.')

    def sync_clicked(self):
        self.start(self.sync)

    def sync(self, config):
        roots = device_roots()
        if len(roots) != 1:
            raise RuntimeError('Conecte o JS-12 com serial 4512482ADF0FEEEE e aguarde o Windows montar a unidade.')
        root = roots[0]
        serial = volume_serial(root)

        def guard():
            if self.stop.is_set():
                raise RuntimeError('Tarefa interrompida. O cache já pronto foi preservado.')
            if volume_serial(root) != serial:
                raise RuntimeError('O MP4 foi desconectado ou a unidade mudou. Reconecte e sincronize novamente.')

        api = self.api(config)
        available = api.playlists()
        self.events.put(('playlists', available))
        selected = available if config.get('all', True) else [p for p in available if p['id'] in config.get('selected', [])]
        if not selected:
            raise RuntimeError('Nenhuma playlist selecionada ou disponível.')
        playlists = []
        for playlist in selected:
            guard()
            self.log('Lendo playlist: ' + playlist['name'])
            try:
                playlists.append(api.tracks(playlist))
            except Exception as error:
                self.log(f"{playlist['name']}: não foi possível ler ({error}). As demais continuam.")
        if not playlists:
            raise RuntimeError('Nenhuma das playlists selecionadas pôde ser lida.')
        unique = {t['id']: t for p in playlists for t in p['tracks']}
        self.log(f'{len(playlists)} playlists; {len(unique)} faixas diferentes. Procurando áudio nas fontes externas...')
        guard()
        with tempfile.TemporaryDirectory(prefix='job-', dir=STATE) as job_dir:
            job_path = Path(job_dir) / 'job.json'
            result_path = Path(job_dir) / 'result.json'
            job_path.write_text(json.dumps({'tracks': list(unique.values()), 'cache': str(STATE / 'Music'), 'result': str(result_path)}), encoding='utf-8')
            log_path = STATE / 'download.log'
            python = Path(sys.executable).with_name('python.exe')
            with log_path.open('w', encoding='utf-8') as logfile:
                with subprocess.Popen([str(python), '-u', str(HERE / 'download_worker.py'), str(job_path)],
                                      cwd=HERE, stdout=logfile, stderr=subprocess.STDOUT,
                                      creationflags=CREATE_NO_WINDOW, env=dict(os.environ, PYTHONUTF8='1')) as process:
                    self.process = process
                    last = time.monotonic()
                    while process.poll() is None:
                        if self.stop.wait(.5):
                            self.kill_worker()
                            raise RuntimeError('Download interrompido; cache pronto preservado.')
                        if time.monotonic() - last > 25:
                            self.log('Download em andamento. Detalhes em ' + str(log_path))
                            last = time.monotonic()
                    self.process = None
                    if process.returncode:
                        raise RuntimeError('O download falhou. Consulte ' + str(log_path))
            cached = json.loads(result_path.read_text(encoding='utf-8'))
            guard()
            # Reconfirm USB hardware identity before writing anything.
            if root not in device_roots():
                raise RuntimeError('Identidade USB mudou. Cache preservado no PC.')
            self.log('Copiando e verificando os arquivos no MP4...')
            count = deploy(root, playlists, cached, guard, self.log)
            missing = len(unique) - len(cached)
            self.log(f'Fim: {count} arquivos novos copiados; {missing} faixas sem áudio. Ejete o MP4 pelo Windows antes de tirar o cabo.')
            if missing:
                self.log('Playlists com faixas pendentes mantêm sua lista anterior. Veja download.log para os motivos.')

    def pump(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'log':
                    self.logbox.configure(state='normal')
                    self.logbox.insert('end', value + '\n')
                    self.logbox.see('end')
                    self.logbox.configure(state='disabled')
                elif kind == 'playlists':
                    selected = set(self.config.get('selected', []))
                    self.playlists = value
                    self.listbox.delete(0, 'end')
                    for i, p in enumerate(value):
                        self.listbox.insert('end', f"{p['name']}  ({p['tracks_count']} faixas)")
                        if p['id'] in selected:
                            self.listbox.selection_set(i)
                elif kind == 'device':
                    self.scanning = False
                    self.roots = value
                    try:
                        self.last_mask = (ctypes.windll.kernel32.GetLogicalDrives(), *(volume_serial(r) for r in value))
                    except OSError:
                        self.last_mask = None
                    if not self.busy:
                        self.status.set('MP4 conectado: ' + str(value[0]) if value else 'MP4 não conectado.')
                    if value and self.auto.get() and not self.busy:
                        self.start(self.sync)
                elif kind == 'done':
                    self.busy = False
                    self.status.set('Tarefa encerrada — confira o registro abaixo.')
        except queue.Empty:
            pass
        self.root.after(150, self.pump)

    def watch(self):
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        # USB replug may reuse the same drive letter; serial/presence is checked too.
        signature = [mask]
        for root in self.roots:
            try:
                signature.append(volume_serial(root))
            except OSError:
                signature.append(None)
        signature = tuple(signature)
        if signature != self.last_mask and not self.scanning:
            self.last_mask = signature
            self.scanning = True

            def scan():
                try:
                    found = device_roots()
                except Exception as error:
                    self.log(str(error))
                    found = []
                self.events.put(('device', found))
            threading.Thread(target=scan, daemon=True).start()
        self.root.after(2000, self.watch)

    def setup(self):
        if self.busy:
            self.log('Encerre a tarefa antes de alterar o acesso.')
            return
        dialog = tk.Toplevel(self.root)
        dialog.title('Acesso de leitura ao Spotify')
        dialog.geometry('650x440')
        dialog.transient(self.root)
        box = ttk.Frame(dialog, padding=18)
        box.pack(fill='both', expand=True)
        ttk.Label(box, text='Configuração única', font=('Segoe UI', 15, 'bold')).pack(anchor='w')
        ttk.Label(box, text='1. Abra o painel e crie um aplicativo.\n2. Em “Which API/SDKs are you planning to use?”, marque somente Web API.\n3. Cadastre exatamente o Redirect URI abaixo.\n4. Cole o Client ID. Não informe senha nem Client Secret.', justify='left', wraplength=600).pack(anchor='w', pady=10)
        ttk.Button(box, text='Abrir painel de desenvolvedor do Spotify', command=lambda: webbrowser.open('https://developer.spotify.com/dashboard')).pack(anchor='w')
        redirect = ttk.Entry(box)
        redirect.insert(0, REDIRECT)
        redirect.configure(state='readonly')
        redirect.pack(fill='x', pady=10)
        ttk.Label(box, text='Client ID:').pack(anchor='w')
        entry = ttk.Entry(box)
        entry.insert(0, self.config.get('client_id', ''))
        entry.pack(fill='x', pady=5)

        def commit():
            value = entry.get().strip()
            if len(value) != 32 or any(c not in '0123456789abcdefABCDEF' for c in value):
                messagebox.showerror('Client ID', 'Copie o Client ID de 32 caracteres do seu aplicativo.', parent=dialog)
                return
            self.config['client_id'] = value
            self.save()
            dialog.destroy()
            self.start(self.load_playlists)
        ttk.Button(box, text='Salvar e conectar Spotify', command=commit).pack(anchor='e', pady=10)

    def install_startup(self):
        startup = Path(os.environ['APPDATA']) / 'Microsoft/Windows/Start Menu/Programs/Startup/JS12 Sync.lnk'
        # PowerShell single-quoted literals escape apostrophes; no credential interpolation.
        quote = lambda s: "'" + str(s).replace("'", "''") + "'"
        pythonw = Path(sys.executable).with_name('pythonw.exe')
        script = "$s=(New-Object -ComObject WScript.Shell).CreateShortcut(" + quote(startup) + ");$s.TargetPath=" + quote(pythonw) + ";$s.Arguments=" + quote('"' + str(HERE / 'app.py') + '" --watch') + ";$s.WorkingDirectory=" + quote(HERE) + ";$s.Save()"
        result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', script], capture_output=True, creationflags=CREATE_NO_WINDOW)
        self.log('Atalho criado na inicialização do Windows. Para desativar, remova JS12 Sync da pasta Inicializar.' if result.returncode == 0 else 'Não foi possível criar o atalho de inicialização.')

    def kill_worker(self):
        process = self.process
        if process and process.poll() is None:
            subprocess.run(['taskkill.exe', '/PID', str(process.pid), '/T', '/F'], capture_output=True, creationflags=CREATE_NO_WINDOW)

    def cancel(self):
        self.stop.set()
        self.log('Interrupção solicitada. Uma consulta em andamento pode levar alguns segundos.')

    def close(self):
        self.save()
        self.studio.shutdown()
        self.stop.set()
        self.kill_worker()
        self.root.destroy()


if __name__ == '__main__':
    kernel = ctypes.windll.kernel32
    kernel.CreateMutexW.restype = ctypes.c_void_p
    mutex = kernel.CreateMutexW(None, False, 'Local\\JS12Sync-4512482ADF0FEEEE')
    if kernel.GetLastError() == 183:
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo('JS12 Sync', 'O programa já está aberto. Procure JS12 Sync na barra de tarefas.')
        root.destroy()
    else:
        root = tk.Tk()
        App(root)
        root.mainloop()

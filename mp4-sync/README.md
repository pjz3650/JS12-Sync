# JS12 Sync

Aplicativo de desktop para Windows que lista playlists da sua conta Spotify, permite selecionar quais sincronizar e transfere arquivos MP3 para um player JS-12 conectado por USB.

**Projeto experimental:** a interface, o conversor e os testes offline foram verificados. A sincronização completa com uma conta Spotify e a leitura das listas M3U no JS-12 ainda precisam de validação. A identificação USB está configurada para uma unidade específica; veja [compatibilidade](#compatibilidade-e-outros-aparelhos) antes de usar outro dispositivo.

## O que faz

- Lista as playlists disponibilizadas pela API à conta autorizada, com seleção individual ou de todas.
- Consulta metadados no Spotify e usa o [spotDL](https://github.com/spotDL/spotify-downloader) para buscar áudio em fontes externas YouTube Music/YouTube.
- Converte áudio para MP3 de 128 kb/s, mantém cache no PC e evita duplicar a mesma faixa entre playlists.
- Gera listas M3U e copia os arquivos para a pasta `SPOTIFY_SYNC` do aparelho.
- Pode sincronizar ao conectar o USB, enquanto o programa estiver aberto.
- Verifica a integridade das cópias e preserva as músicas existentes fora da pasta gerenciada.

Não instala Spotify no MP4, não modifica o firmware e não exporta os downloads offline do Premium. O menu de seleção funciona no computador; o aparelho usa seu próprio menu de música. As fontes externas podem retornar outra gravação ou não encontrar uma faixa. Use apenas conteúdo que você tenha autorização para baixar e observe os termos dos serviços utilizados.

## Requisitos

- Windows com PowerShell, acesso a dispositivos USB e interface gráfica. O código usa APIs específicas do Windows, incluindo DPAPI e CIM; não há suporte a Linux ou macOS nesta versão.
- Python **3.13** com Tkinter. O ambiente de desenvolvimento utilizou Python 3.13.5; outras versões não foram validadas.
- Internet para instalar dependências, autorizar o Spotify, consultar playlists e obter novos áudios.
- Conta Spotify e um aplicativo pessoal cadastrado no Spotify for Developers. Consulte as [regras atuais do modo de desenvolvimento](https://developer.spotify.com/documentation/web-api/references/changes/february-2026).
- Espaço livre no computador para o cache e no player para as músicas.
- Git, caso prefira clonar o repositório; também é possível baixar e extrair o ZIP pelo GitHub.

O computador fornece a conexão de rede. Depois da transferência, os MP3 podem ser reproduzidos no player sem internet.

## Instalação do zero

No PowerShell, entre na pasta do repositório clonado ou extraído. Para clonar este projeto:

```powershell
git clone https://github.com/pjz3650/JS12-Sync.git
cd JS12-Sync
cd mp4-sync
```

Se você reorganizou um fork para colocar o conteúdo de `mp4-sync` na raiz, omita o último `cd`. Todos os comandos abaixo devem ser executados na pasta que contém `app.py`.

Crie o ambiente e instale as dependências:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
```

`requirements-lock.txt` registra as versões do ambiente utilizado. Para resolver novamente as dependências a partir da versão principal fixada do spotDL, use `requirements.txt` em vez do arquivo de lock. Atualizações podem alterar o comportamento das fontes de áudio e precisam ser verificadas.

Instale os executáveis auxiliares pelo spotDL:

```powershell
.\.venv\Scripts\python.exe -m spotdl --download-ffmpeg
.\.venv\Scripts\python.exe -m spotdl --download-deno
```

Esses comandos fazem downloads e colocam os auxiliares na pasta `.spotdl` do seu usuário Windows. Não é necessário ativar o ambiente virtual nem alterar a política de execução de scripts do PowerShell.

## Como executar

Na pasta `mp4-sync`, execute:

```powershell
.\.venv\Scripts\python.exe app.py
```

Ou dê dois cliques em **Abrir JS12 Sync.cmd**. O atalho usa o ambiente `.venv` local e abre a interface sem console. Para investigar erros de inicialização, prefira o comando acima, que mostra as mensagens no terminal.

### Configurar o Spotify pela primeira vez

1. Clique em **Configurar acesso** no programa e abra o [painel do Spotify for Developers](https://developer.spotify.com/dashboard).
2. Crie um aplicativo pessoal. Sugestão de nome: `JS12 Sync`; descrição: `Aplicativo pessoal para consultar minhas playlists`.
3. Em **Which API/SDKs are you planning to use?**, marque somente **Web API**.
4. Cadastre exatamente este **Redirect URI** e salve:

   ```text
   http://127.0.0.1:8765/callback
   ```

5. Abra as configurações do aplicativo no painel, copie o **Client ID** e cole na janela do JS12 Sync.
6. Clique em **Salvar e conectar Spotify** e autorize o acesso de leitura na página oficial que abrir no navegador.

Não informe senha nem **Client Secret** ao JS12 Sync. A autorização usa OAuth com PKCE e solicita apenas os escopos `playlist-read-private` e `playlist-read-collaborative`.

O servidor de retorno do login escuta somente em `127.0.0.1:8765`, durante a autorização, por até três minutos. Cadastre o endereço exatamente como acima; não substitua `127.0.0.1` por `localhost`.

### Selecionar e sincronizar

1. Clique em **Conectar Spotify / atualizar** para carregar a lista.
2. Deixe **Todas as playlists** marcada ou desmarque e selecione as desejadas com Ctrl/Shift.
3. Conecte o player com um cabo USB de dados e aguarde sua identificação pelo Windows.
4. Clique em **Sincronizar agora** e acompanhe o registro na janela.
5. Aguarde o fim e ejete a unidade pelo Windows antes de retirar o cabo.

O programa atualiza os metadados das playlists selecionadas a cada sincronização. A API pode limitar o acesso a playlists de terceiros ou do próprio Spotify; “todas” significa todas as que forem disponibilizadas à conta. **Músicas curtidas** não são incluídas como uma playlist nesta versão. Itens locais, podcasts e itens indisponíveis são ignorados.

Se uma playlist não puder ser lida, o erro aparece no registro e as demais continuam. Se faltarem downloads de faixas, o M3U anterior dessa playlist é preservado; os áudios obtidos ainda podem ser copiados. Assim, uma execução pode terminar com pendências: confira o registro.

**Parar** solicita a interrupção e preserva o cache pronto. Uma requisição HTTP em andamento pode demorar alguns segundos para terminar. Fechar a janela também encerra o processo de download do programa.

### Sincronização ao conectar o USB

Após validar uma sincronização manual, marque **Sincronizar ao conectar este MP4**. O programa precisa permanecer aberto; pode ficar minimizado. Isso não instala um serviço do Windows.

O botão **Iniciar com o Windows** cria um atalho na pasta Inicializar do usuário, que abre o programa minimizado. Configure o acesso e a seleção antes de habilitar esse uso. Se mover o projeto ou recriar o ambiente em outro caminho, recrie o atalho.

Para desativar a inicialização, pressione Win+R, execute `shell:startup` e remova o atalho **JS12 Sync**. Para desativar a transferência automática, desmarque a opção na interface.

## Arquivos e dados pessoais

Os dados de execução ficam fora do repositório, em `%LOCALAPPDATA%\JS12Sync`:

| Arquivo ou pasta | Conteúdo |
| --- | --- |
| `config.json` | Client ID, seleção de playlists e preferências |
| `auth-<client-id>.bin` | Token OAuth protegido com DPAPI do usuário Windows |
| `Music/` | Cache de MP3, reutilizado nas próximas sincronizações |
| `download.log` | Registro detalhado da última busca de áudio |
| `job-*/` | Arquivos temporários com metadados durante a sincronização |

O programa não lê cookies, senhas nem o cache do aplicativo Spotify. A proteção DPAPI não transforma o arquivo de autorização em algo que deva ser compartilhado: mantenha os tokens e os dados pessoais fora do GitHub. Os logs também podem conter nomes de faixas, URLs e caminhos locais.

Para reiniciar a configuração, feche o programa e remova `config.json` e os arquivos `auth-*.bin` dessa pasta. A autorização também pode ser revogada nas configurações da sua conta Spotify. Remover `Music` apaga apenas o cache local e exige obter novamente os áudios em sincronizações futuras; não remove as cópias já feitas no player.

No player, a estrutura gerenciada é:

```text
SPOTIFY_SYNC/
  .js12-sync.json
  Music/
    Artista - Musica-ID.mp3
  Nome da playlist-ID.m3u
```

As listas usam caminhos relativos e mantêm a ordem das faixas. Os nomes de arquivos são simplificados para caracteres ASCII. Faixas com o mesmo ID compartilham um MP3. Arquivos antigos não são apagados automaticamente ao desmarcar playlists ou remover músicas delas. Renomear uma playlist substitui apenas o M3U anterior registrado pelo programa.

As músicas e arquivos `.LIB` existentes fora dessa pasta não são alterados. Uma pasta `SPOTIFY_SYNC` sem o marcador do programa é recusada. Arquivos MP3 de destino que já existam com conteúdo diferente são preservados, e a operação informa erro.

## Compatibilidade e outros aparelhos

Esta versão foi preparada para um **JS-12 com processador ATJ2127**, identificado como ACTIONS USB DISK 2.0. A descoberta filtra `VEN_ACTIONS` e o serial específico `4512482ADF0FEEEE`; não depende de a letra da unidade ser D:.

**Um outro JS-12 não será reconhecido automaticamente.** Ainda não existe seleção de aparelho pela interface. Para adaptar o projeto, revise a identificação no código de `core.py`: o filtro PowerShell de `device_roots()` contém os valores literais, portanto alterar apenas as constantes `DEVICE_SERIAL`/`DEVICE_VENDOR` não basta nesta versão. Atualize também as referências ao serial em `app.py` para manter mensagens e identificação da instância coerentes. Confirme o PNPDeviceID do dispositivo pretendido; não remova o filtro para aceitar qualquer pendrive.

A leitura de **M3U no firmware desta unidade ainda não foi confirmada fisicamente**. A documentação do SDK sugere suporte, mas isso não garante que o menu do aparelho exponha as listas. Os MP3 permanecem disponíveis como arquivos. Uma exportação alternativa em pastas por playlist ainda não foi implementada.

## Desenvolvimento e testes

Estrutura principal:

```text
mp4-sync/
  app.py                 # Interface Tkinter, seleção e monitoramento do USB
  spotify_access.py      # OAuth PKCE, cache DPAPI e leitura paginada da API
  download_worker.py     # Processo separado de busca/conversão com spotDL
  core.py                # Identificação USB, integridade e cópia dos arquivos
  test_sync.py           # Testes offline
  requirements.txt       # Dependência principal fixada
  requirements-lock.txt  # Versões do ambiente utilizado
  Abrir JS12 Sync.cmd     # Inicializador Windows
```

Execute na pasta do aplicativo:

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_sync
```

Os 11 testes offline cobrem preservação de arquivos, ordem e deduplicação, espaço insuficiente, desconexão durante a cópia, IDs inválidos, preservação de listas com downloads pendentes, cache DPAPI e respostas da API simuladas. Não utilizam sua conta Spotify nem escrevem no player físico. O conversor e o cache também foram verificados separadamente com um áudio sintético.

A validação com login real, downloads das playlists e reprodução das listas no JS-12 continua pendente. Não há instalador, executável único, atualização automática ou suporte a múltiplos modelos de player nesta versão.

## Problemas comuns

| Sintoma | O que verificar |
| --- | --- |
| `py` não encontrado | Instale Python 3.13 com o Python Launcher; reabra o terminal. |
| Ambiente Python não encontrado | Crie `.venv` na mesma pasta de `app.py`, seguindo a instalação. |
| A janela fecha ao abrir | Execute `app.py` pelo terminal para visualizar o erro. |
| Erro no retorno do login | Confira o Redirect URI exato e se a porta 8765 está livre. Reinicie a conexão se passaram três minutos. |
| Spotify retorna 401/403 | Confira a conta autorizada, o cadastro/permissões do aplicativo e as restrições do modo de desenvolvimento. Reconecte a conta quando necessário. |
| Player não encontrado | Confira cabo, montagem da unidade e a identificação específica descrita na seção de compatibilidade. |
| Faixas não foram obtidas | Consulte `download.log`. Fontes externas podem bloquear requisições ou não oferecer uma correspondência. |
| Espaço insuficiente | Libere espaço no player. O programa reserva uma margem adicional de 16 MiB e não apaga músicas para abrir espaço. |
| MP3 aparecem, mas playlists não | O suporte a M3U precisa ser validado no firmware do aparelho. |

## Antes de publicar no GitHub

- Publique o código, os arquivos de dependências, os testes e a documentação. Não envie `.venv`, caches, logs, tokens OAuth, arquivos de configuração pessoais nem músicas.
- O `.gitignore` em `mp4-sync` já exclui `.venv`, logs e bytecode Python. Ele não cobre todos os tipos de dados pessoais nem arquivos que já tenham sido rastreados: revise `git status` e o conteúdo preparado para commit.
- Uma pasta local `device-research`, quando presente, contém material separado de investigação do aparelho e é ignorada pelo Git. Não é necessária para executar o aplicativo. Revise-a antes de publicar; não redistribua dumps de firmware, binários de terceiros ou dados pessoais sem autorização. Evite adicionar toda a raiz ao commit sem revisar.
- Ao publicar um fork, atualize os links e a URL de clone para o seu repositório.
- O código do projeto está sob a [licença MIT](../LICENSE). Preserve os avisos da licença ao redistribuir. Dependências e ferramentas têm suas próprias licenças.
- Ao abrir uma issue, informe Windows, Python, passos para reproduzir e o trecho relevante do erro. Remova tokens, dados pessoais e caminhos privados dos registros enviados.

Este é um projeto independente, sem afiliação com Spotify, Actions Semiconductor, YouTube ou spotDL.

## Referências

- [Spotify Web API](https://developer.spotify.com/documentation/web-api)
- [Autorização PKCE](https://developer.spotify.com/documentation/web-api/tutorials/code-pkce-flow)
- [Redirect URIs](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri)
- [Itens das playlists](https://developer.spotify.com/documentation/web-api/reference/get-playlists-items)
- [Restrições do modo de desenvolvimento](https://developer.spotify.com/documentation/web-api/references/changes/february-2026)
- [spotDL: código e documentação](https://github.com/spotDL/spotify-downloader)

# Pipeline CI/CD - laboratorio DevOps

Repositorio: https://github.com/pjz3650/JS12-Sync

## Estrategia

O JS12 Sync e um aplicativo desktop Windows em Python/Tkinter, com DPAPI para
credenciais e integracao USB. O deployment distribui um ZIP instalavel pelo
GitHub Releases, adequado a esse tipo de aplicativo. Nao existe servidor web.
O ZIP contem a aplicacao, manuais, licenca, dependencias fixadas, instalador
e RELEASE.json com commit e hashes dos arquivos. Requer Windows, Python 3.13
com Launcher/Tcl/Tk e internet. Nao e um .exe autonomo.

## CI -> CD -> aplicacao publicada

Arquivo: [.github/workflows/ci-cd.yml](../.github/workflows/ci-cd.yml).

1. Cada push na main e cada pull request para main executam a CI em Windows.
2. Checkout; Python 3.13; instalacao de requirements-lock.txt; pip check;
   compileall; 22 testes offline; verificacao de imports e inicializacao Tcl/Tk.
3. A CI empacota os arquivos permitidos, confere hashes internos e testa novamente
   os 22 testes a partir do ZIP extraido. O pacote e preservado como artifact.
4. O CD usa needs: ci e so executa para push em refs/heads/main. Um PR nunca publica.
5. O mesmo artifact aprovado e recuperado e seu SHA256 conferido. Uma release
   com tag unica por run/tentativa e criada como draft e publicada com ZIP e checksum.
6. O CD baixa o ZIP pela URL publica sem autenticacao e compara o SHA256 com a CI.
   A URL e o checksum sao registrados no resumo da execucao.

Somente o job CD possui contents: write. A pipeline usa GITHUB_TOKEN automatico;
nao precisa de PAT nem segredos Spotify/OpenAI. O job CI tem somente leitura.
Nao sao incluidos .env locais, tokens, ambiente virtual, cache ou musicas.
As releases anteriores continuam acessiveis para reinstalacao de uma versao anterior.

## Instalar a publicacao

Abra https://github.com/pjz3650/JS12-Sync/releases/latest, baixe o ZIP e o checksum.
Compare com Get-FileHash -Algorithm SHA256. Extraia o ZIP em uma pasta gravavel,
execute Instalar JS12 Sync.cmd e depois mp4-sync/Abrir JS12 Sync.cmd.
O instalador prepara o ambiente e obtem FFmpeg/Deno pelo spotDL. Spotify e IA
continuam a exigir configuracao pessoal, conforme o manual. Use uma nova pasta
ao trocar de release; os dados pessoais continuam em LOCALAPPDATA/JS12Sync.

## Registro real da utilizacao da IA

Ferramenta: Codex, neste chat. Quantidade de prompts do usuario ate esta versao: **1**.
Prompt literal (com PDF do laboratorio anexado):

> implementa o roteiro do PDF nesse repo [https://github.com/pjz3650/JS12-Sync](https://github.com/pjz3650/JS12-Sync)

Resultado: pipeline CI/CD, empacotamento, instalador e documentacao. A IA inspecionou
o codigo e os testes existentes para selecionar Windows e distribuicao desktop.
Os comandos internos de ferramentas nao foram contados como novos prompts do usuario.
Nao foram inventadas interacoes, falhas remotas ou aprovacoes humanas.

Problemas encontrados durante a preparacao:

- A pasta inicialmente aberta pertencia a outro projeto; foi feito um clone isolado.
- O primeiro clone nao conseguiu resolver GitHub no sandbox; nova tentativa com
  acesso de rede autorizado concluiu o clone.
- A extracao do PDF encontrou caractere nao suportado pelo terminal; UTF-8 resolveu.
- Nao havia pipeline ou instalador para o pacote distribuido; ambos foram adicionados.

Alteracoes: workflow com separacao CI/CD; script de ZIP e hashes; instalador Windows;
README e CONTRIBUTING atualizados; este registro. Nenhuma funcionalidade USB ou
de IA da aplicacao foi alterada. Alteracoes manuais do usuario: nenhuma observada
nesta sessao. Os arquivos foram escritos pela IA e verificados com ferramentas.

## Como validar e coletar evidencias

Consulte https://github.com/pjz3650/JS12-Sync/actions. Uma execucao de PR deve
aprovar a CI e pular CD; uma execucao de push na main deve aprovar os dois jobs.
Abra o resumo do CD para localizar o download verificado e o SHA256. Na release,
RELEASE.json identifica o mesmo commit da execucao. O relatorio de entrega deve
registrar URLs, resultados reais e quaisquer falhas encontradas, sem afirmar
sincronizacao USB, login real, downloads de musicas ou geracao IA como testados.

Verificacoes locais equivalentes, na raiz e com as dependencias instaladas:

```powershell
python -m pip check
python -m compileall -q mp4-sync scripts
python -m unittest discover -s mp4-sync -p "test_*.py" -v
python scripts/package_release.py --commit (git rev-parse HEAD)
```

As verificacoes offline e a abertura minima Tcl/Tk nao substituem testes com
conta Spotify autorizada e aparelho fisico. Falha de qualquer etapa da CI impede CD.
Se a publicacao falhar, confira permissao contents: write e politicas de Actions
do repositorio. Uma falha de verificacao publica apos a publicacao marca CD como
falho, mesmo que a release ja esteja acessivel; investigue antes de usa-la.

Referencias oficiais:

- https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions
- https://github.com/actions/setup-python
- https://docs.github.com/en/rest/releases/releases

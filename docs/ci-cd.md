# Pipeline CI/CD - laboratório DevOps

Repositório: https://github.com/pjz3650/JS12-Sync

Página pública: https://js12-sync.onrender.com

## Estratégia de deployment

O aplicativo usa Python/Tkinter, DPAPI e USB no Windows. Por solicitação do
usuário, o deployment usa **Render Static Site** para distribuir o aplicativo
Windows por uma página pública com ZIP, instruções e checksum. O aplicativo
continua sendo executado no computador do usuário; a interface Tkinter não roda
no navegador. O ZIP requer Python 3.13 com Launcher/Tcl/Tk e internet.
O instalador prepara o ambiente e baixa FFmpeg/Deno via spotDL.

## Fluxo automático

Arquivo: [.github/workflows/ci-cd.yml](../.github/workflows/ci-cd.yml).

1. Push em main e pull_request para main executam CI em Windows/Python 3.13.
2. Checkout; dependências fixadas; pip check; compileall; 22 testes offline e 5 testes de distribuição;
   imports do app e inicialização mínima de Tkinter.
3. Geração do ZIP e da página pública; extração do ZIP; repetição dos 22 testes.
4. Publicação do ZIP e SHA256SUMS como artifact. Sem tokens, .env local ou músicas.
5. O job CD tem needs: ci e só executa em push para refs/heads/main.
6. O CD dispara o deploy hook do Render com ref igual ao SHA aprovado. Auto-Deploy
   fica Off para impedir publicação independente dos testes. Deploys são serializados.
7. O Render executa python3 scripts/build_site.py, gera o pacote e publica dist/site.
8. A pipeline aguarda version.json identificar o mesmo commit e uma construção
   posterior ao pedido de deploy (com tolerância de relógio de 5 segundos), e compara o hash
   do ZIP publicado com o artifact da CI. Timeout ou divergência fazem o CD falhar.

O empacotamento fixa metadados e finais de linha para produzir os mesmos bytes
em Windows e Linux. RELEASE.json registra commit e hashes internos. Reverter uma
versão deve ser feito por um novo commit revert em main, passando pela mesma CI.

## Configuração Render e GitHub

O [render.yaml](../render.yaml) documenta o serviço. Também pode ser criado no
painel como Static Site, repositório público, branch main, Build Command
`python3 scripts/build_site.py`, Publish Directory `dist/site` e Auto-Deploy Off.

No GitHub, configure:

- Secret de Actions RENDER_DEPLOY_HOOK_URL: deploy hook do serviço Render.
- Variable de Actions RENDER_SITE_URL: URL HTTPS pública do site, sem barra final.

O hook é uma credencial: nunca deve aparecer no código, no relatório ou nos logs.
Não são necessárias chaves Spotify/OpenAI na pipeline. São configurações locais
para uso posterior do aplicativo. O GITHUB_TOKEN tem somente contents: read.

## Registro real do uso da IA

Ferramenta: Codex, neste chat. **5 mensagens do usuário até esta versão** (3 orientações e 2 respostas de autorização):

1. Com o PDF do laboratório anexado: “implementa o roteiro do PDF nesse repo
   [https://github.com/pjz3650/JS12-Sync](https://github.com/pjz3650/JS12-Sync)”.
   Resultado: inspeção, workflow Windows, instalador, empacotamento e PR #1.
   A primeira proposta usava GitHub Releases.
2. “quando for fazer o deploy, use o render. Abra a área de login na barra lateral
   quando for usar”. Resultado: CD adaptado ao Render, página de distribuição,
   blueprint e verificação pública; login aberto no painel lateral.
3. “ja fiz o login ja”. Resultado: sessão autenticada verificada e continuação da
   configuração do serviço. Login foi realizado manualmente pelo usuário.
4. “ja integrei, pode subir a main”. Resultado: merge manual do usuário confirmado;
   publicação e configuração do serviço na main continuaram.
5. “Autorizo salvar o hook no GitHub”. Resultado: deploy hook salvo como secret
   de Actions e URL pública salva como variable; CD reexecutado.

Não se contam chamadas internas de ferramentas como prompts do usuário.
Nenhuma interação, falha remota ou aprovação foi inventada.

Problemas e alterações:

- A pasta aberta pertencia a outro projeto: clone isolado em tmp/JS12-Sync.
- O sandbox bloqueou a rede no primeiro clone e operações temporárias da suíte:
  verificações repetidas fora do sandbox com autorização; 22 testes locais passaram.
- Terminal não suportou um caractere do PDF: extração refeita em UTF-8.
- A revisão automática bloqueou a tentativa inicial de integrar a versão que
  publicaria GitHub Releases. Essa publicação não ocorreu. A orientação seguinte
  do usuário definiu Render como destino.
- Pacotes gerados em sistemas diferentes poderiam divergir por metadados e finais
  de linha: ZIP determinístico e regras explícitas em .gitattributes.
- Alterações pela IA: workflow, instalador, scripts de pacote/site/deploy,
  render.yaml, página HTML, README, CONTRIBUTING e este registro.
- O primeiro CD da main executou antes da configuração de hook e URL; falhou
  com Expected an HTTPS Render deploy hook. Secret e variable foram configurados.
- A primeira gravação do secret pela interface falhou; o formulário foi
  reaberto, preenchido e a confirmação Repository secret added foi verificada.
- A verificação pública foi reforçada com horário de construção para não aceitar
  uma publicação antiga do mesmo commit durante reexecuções.
- Alterações manuais observadas: login do usuário no Render e merge do PR; nenhuma edição
  manual de código foi observada nesta sessão.

## Evidências verificadas

PR: https://github.com/pjz3650/JS12-Sync/pull/1

Primeira execução (antes da adaptação para Render):
https://github.com/pjz3650/JS12-Sync/actions/runs/42798415785

CI success; 22 testes no código e 22 no ZIP; Tkinter OK; CD skipped em PR.
Essa execução comprova a CI inicial, não um deployment Render.
Execução de push na main:
https://github.com/pjz3650/JS12-Sync/actions/runs/42800035698

Primeira tentativa: CI success, CD failure por configuração ausente. Após
configurar secret/variable e repetir o job, CI e CD success. Commit:
320425add57e73f96961fcb869f8b4024e651e26. Pacote público conferido com SHA256:
efaee1538433ebe31e7ec16e20b3e41047b76a4df649cbe9a9b6fca134268825.

O relatório PDF reúne o YAML completo, prompts, alterações e evidências. Uma
execução posterior valida também o reforço de horário e esta documentação.

## Análise

A IA acelerou a preparação, mas a validação dependeu de testes reais e da
inspeção dos resultados. A escolha de Windows preservou testes DPAPI. A mudança
para Render exigiu separar distribuição pela web de execução desktop. A condição
needs: ci impede CD se os testes falharem; o SHA e o checksum verificam que o
pacote acessível corresponde ao código aprovado. Testes com conta Spotify,
aparelho físico e geração real com IA continuam fora desta validação.

Referências oficiais:

- https://render.com/docs/deploy-hooks
- https://render.com/docs/blueprint-spec
- https://render.com/docs/static-sites
- https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions

# Estúdio de telas com IA

O estúdio fica na aba **Personalizar tela com IA** do JS12 Sync. Ele transforma uma descrição em uma prévia de tela, permite ajustes em conversa e exporta a revisão aprovada para o computador.

**Ainda não instala a interface no MP4.** O botão de aplicação permanece indisponível. Faltam a conversão validada para o formato de recursos do firmware, um backup completo do original e um método de gravação/recuperação testado. Copiar um desenho ou ZIP para a unidade USB não muda o menu do aparelho.

## Configuração

Instale o projeto pelo [guia principal](../mp4-sync/README.md). O chat usa a API da OpenAI; o Client ID do Spotify é independente e não autoriza a IA.

A chave deve estar em `OPENAI_API_KEY` no ambiente ou no arquivo **`.env.local` na raiz do repositório**. Um arquivo alternativo também é reconhecido em `mp4-sync/.env.local`. O arquivo [`.env.example`](../.env.example) documenta os nomes das variáveis, sem credenciais. Nunca publique uma chave real, inclusive em issues ou capturas de tela.

O modelo padrão é `gpt-6-luna`. É possível mudar o campo **Modelo** antes de enviar um pedido ou definir `OPENAI_MODEL` no ambiente/arquivo local. O modelo escolhido precisa estar disponível ao projeto e aceitar a Responses API com saída estruturada. Não há troca silenciosa de modelo nem repetição automática de chamadas com erro.

As chamadas à API usam a cobrança e os limites do projeto na plataforma. Ao abrir o programa ou carregar o exemplo local, nenhuma chamada de IA é feita.

## Criar e ajustar uma tela

1. Abra **Personalizar tela com IA**.
2. Escolha a **resolução de projeto**. A opção inicial, `128x160`, é uma hipótese de trabalho, não uma medição confirmada do seu JS-12. Há outras opções comuns; selecionar uma não confirma compatibilidade física.
3. Descreva o que quer. Por exemplo:

   > Quero uma tela de reprodução com fundo preto, destaque verde, título da música, artista, barra de progresso e botão de play. Letras grandes, sem muitos enfeites.

4. Clique em **Enviar para IA** ou pressione Ctrl+Enter.
5. Confira a prévia e peça ajustes, como `aumente o título e troque o verde por azul`.
6. Se houver várias telas, alterne pelo seletor acima da prévia.

Você pode experimentar **Exemplo local** sem chave e sem internet. Ele é identificado como um desenho de exemplo, não como uma resposta de IA. O botão **Novo desenho** substitui a conversa e o desenho atuais após confirmação; pacotes exportados continuam disponíveis.

O desenho permite até quatro telas com 36 elementos cada: retângulos, elipses, linhas, texto, barras de progresso e um conjunto limitado de ícones. Não há execução de HTML, Python ou comandos produzidos pelo modelo. As fontes exibidas são do PC e não representam a fonte original do firmware. Os elementos desenhados não adicionam funções ao aparelho.

## Aprovar uma revisão

Diga exatamente **`ficou bom`** no chat ou clique em **Ficou bom — aprovar e exportar**. A frase é tratada localmente e não precisa de outra chamada à API. `Não ficou bom`, perguntas e mensagens com pedidos adicionais de mudança não aprovam o desenho.

A aprovação corresponde ao desenho e à resolução atuais, identificados por SHA-256. Uma nova resposta de desenho invalida a aprovação anterior. Mesmo uma alteração externa no conteúdo do projeto invalida uma aprovação cujo hash não corresponda mais à revisão.

A aprovação gera um ZIP em:

```text
%LOCALAPPDATA%\JS12Sync\studio\exports\
```

O pacote contém:

| Arquivo | Finalidade |
| --- | --- |
| `design.json` | Desenho declarativo e resolução escolhida |
| `screen-01.png`, etc. | Prévia renderizada de cada tela |
| `screen-01.rgb565le`, etc. | Raster genérico RGB565, little-endian, dois bytes por pixel |
| `manifest.json` | Hashes, identificação da revisão aprovada e impedimentos à instalação |
| `LEIA-ME.txt` | Explicação do conteúdo e das limitações |

O manifesto informa explicitamente `installable: false`. Os rasters **não são STY/MCG**, não têm cabeçalhos do formato Actions e não podem ser gravados como firmware. A organização de pixels e cores exigida pelo hardware ainda precisa ser investigada. Não há envio automático desses pacotes ao MP4.

## Histórico, privacidade e cancelamento

A conversa recente, o desenho e a aprovação são salvos localmente em `%LOCALAPPDATA%\JS12Sync\studio\session.json`. O aplicativo restaura a sessão na próxima abertura. Ele mantém até 60 mensagens e envia até as 16 mais recentes junto do desenho atual para dar contexto aos ajustes.

Somente a conversa, a resolução e o desenho atual entram no corpo do pedido de geração. Não são anexados firmware, biblioteca musical, tokens do Spotify ou arquivos da máquina. A chave da OpenAI é usada apenas para autenticar a requisição HTTPS. Evite incluir dados pessoais nos pedidos.

Os pedidos usam `store: false`; isso não é uma promessa de ausência total de retenção pelo provedor. Consulte os [controles de dados da API](https://developers.openai.com/api/docs/guides/your-data).

**Cancelar pedido** descarta a eventual resposta nesta janela. Uma requisição já enviada pode continuar sendo processada e cobrada pela API. Não existe promessa de cancelamento remoto ou reembolso. A aba de playlists permanece disponível durante a geração.

## Diagnóstico

- **Chave não configurada:** confira a variável ou o arquivo local, sem copiar o valor para logs ou issues.
- **401:** a API recusou a chave.
- **403:** confira o acesso do projeto/chave ao modelo selecionado.
- **429:** verifique limites ou saldo do projeto na plataforma; o aplicativo não repete o pedido automaticamente.
- **Resposta incompleta ou desenho inválido:** a prévia anterior é preservada. Simplifique o pedido e tente novamente.
- **Prévia diferente do aparelho:** a exportação ainda é um projeto gráfico; resolução, fontes, recursos e compilação nativa não foram validados no player.

## Verificações

A suíte offline cobre desenho nas cinco resoluções, rejeição de elementos inválidos, hash da aprovação, sessão local, recusa de exportação sem aprovação, integridade do pacote e contrato HTTP simulado. A integração também foi verificada com uma resposta real da API e com um teste isolado da interface, sem gravar no aparelho.

Execute na raiz:

```powershell
.\mp4-sync\.venv\Scripts\python.exe -m unittest discover -s mp4-sync -p "test_*.py" -v
```

Referências da integração: [Responses API e saídas estruturadas](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses) e [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna).

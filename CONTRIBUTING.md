# Contribuindo com o JS12 Sync

Obrigado por ajudar a tornar o projeto útil em mais aparelhos. Comece pelo [guia de instalação](mp4-sync/README.md) e pelas limitações de compatibilidade antes de testar no seu player.

## Preparar e verificar uma alteração

1. Crie uma branch com um nome descritivo, por exemplo `feature/device-selection`, `fix/usb-detection` ou `docs/setup-guide`.
2. Faça uma alteração de escopo claro. Preserve a identificação do USB e o comportamento de não apagar músicas existentes.
3. Execute os testes offline na raiz do repositório:

   ```powershell
   .\mp4-sync\.venv\Scripts\python.exe -m unittest discover -s mp4-sync -p "test_*.py" -v
   ```

4. Abra um pull request para `main`, explicando o problema, o resultado e como verificou a alteração. Diferencie testes simulados de testes feitos em aparelho físico.

Execute a suíte em Windows. Os testes não precisam de autorização Spotify, músicas ou acesso a USB real. A execução automática no GitHub Actions ainda não está configurada.

## Relatar problemas

Abra uma [issue](https://github.com/pjz3650/JS12-Sync/issues) informando:

- Versões do Windows e Python.
- Passos para reproduzir, resultado esperado e resultado observado.
- Mensagem de erro relevante, removendo tokens, nomes privados e caminhos pessoais.
- Modelo e modo USB do aparelho, se o problema envolver detecção. Não envie dumps de firmware nem bibliotecas pessoais.

Não inclua senhas, Client Secret, tokens OAuth, arquivos `auth-*.bin`, músicas ou logs completos sem revisar seu conteúdo.

## Histórico e licença

Prefira commits pequenos e descritivos: `feat:`, `fix:`, `test:`, `docs:` e `chore:` ajudam a identificar o escopo. As branches de implementação publicadas inicialmente são pontos do histórico; use `main` para obter a versão integrada.

O código do projeto está sob a [licença MIT](LICENSE). Ferramentas e dependências conservam suas próprias licenças.

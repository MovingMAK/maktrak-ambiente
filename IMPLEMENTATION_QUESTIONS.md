# Perguntas e dúvidas para implementação do MakTrak setup

Antes de implementar o instalador, precisamos esclarecer os pontos abaixo para garantir que o script atenda às expectativas e seja seguro de usar.

1. Política de atualização do OS
- Confirmar comportamento padrão: `--update-os` deve ser desligado por padrão (não atualizar).
- Em caso afirmativo, quais comandos/gestores usar para cada sistema (`apt upgrade`, `winget upgrade all`, `choco upgrade all`)?

2. Gerentes de pacote
- No Windows, prefere `winget` ou `choco` quando ambos existirem? Devo implementar detecção e fallback automático?
- No Linux, usar `snap` quando disponível; para pacotes que não têm snap, usar `apt` ou PPAs?

3. Permissões e UAC
- O script deve pedir elevação automaticamente quando necessário, ou apenas instruir o usuário a executar com privilégios (
  `sudo` / executar como Administrador)?
- Em ambientes não-interativos, como CI, qual política deseja (falhar ou tentar sudo sem prompt)?

4. Interatividade e aceitação de termos
- Modo `--yes` deve aceitar EULAs/termos automaticamente onde possível? Ou deve falhar quando uma EULA exigir aceitação manual?

5. Ferramentas específicas
- Confirmação de lista mínima por categoria (resuma/corrija):
  - Mecânica: FreeCAD
  - Eletrônica: KiCad
  - Firmware: Arduino CLI, VS Code
  - Servidor: VS Code, Flutter (configurar builds Windows/Linux), Web local
  - Geral: git, Sublime Text, Sublime Merge, Markdown preview tool
  - IA: (quais ferramentas/SDKs?)

6. Testes automatizados
- Quais testes automatizados mínimos espera para cada ferramenta? Exemplos aceitáveis:
  - Executar `--version`/`--help` e validar saída
  - Compilar projeto de exemplo (quando disponível)
- Aceita que alguns testes só sejam manuais por limitações do ambiente (ex.: validar GUI)?
- As decisões e métodos de teste detalhados podem ser documentados em [TESTING.md](TESTING.md).

7. Plataforma alvo e arquitetura
- A prioridade inicial é suportar `x86_64`.
- Além das versões de SO listadas, há alguma outra arquitetura relevante?

8. Cronograma e priorização
- A prioridade é a lógica do próprio script.
- Quais categorias são prioridade inicial (por exemplo: Geral + Firmware + Eletrônica)?

9. Referências e links
- Confirmar que o link literário fornecido ([https://share.google/aimode/jQQQFq4VttHpozdoF](https://share.google/aimode/jQQQFq4VttHpozdoF)) é o único recurso a consultar ou há mais.


Por favor responda estas perguntas para que eu gere o esqueleto do script e os arquivos de configuração iniciais (`repos.yaml`, `modules.yaml`).

# Perguntas e dúvidas para implementação do MakTrak setup

Antes de implementar o instalador, precisamos esclarecer os pontos abaixo para garantir que o script atenda às expectativas e seja seguro de usar.

1. Repositórios
- Qual é a lista completa de repositórios a clonar? Existe um repositório central com todos os URLs?
- Deseja clonar tudo em um diretório padrão (ex.: `~/maktrak/src`) ou cada repositório em pastas específicas?

2. Política de atualização do OS
- Confirmar comportamento padrão: `--update-os` deve ser desligado por padrão (não atualizar).
- Em caso afirmativo, quais comandos/gestores usar para cada sistema (`apt upgrade`, `winget upgrade all`, `choco upgrade all`)?

3. Gerentes de pacote
- No Windows, prefere `winget` ou `choco` quando ambos existirem? Devo implementar detecção e fallback automático?
- No Linux, usar `snap` quando disponível; para pacotes que não têm snap, usar `apt` ou PPAs?

4. Permissões e UAC
- O script deve pedir elevação automaticamente quando necessário, ou apenas instruir o usuário a executar com privilégios (
  `sudo` / executar como Administrador)?
- Em ambientes não-interativos, como CI, qual política deseja (falhar ou tentar sudo sem prompt)?

5. Interatividade e aceitação de termos
- Modo `--yes` deve aceitar EULAs/termos automaticamente onde possível? Ou deve falhar quando uma EULA exigir aceitação manual?

6. Ferramentas específicas
- Confirmação de lista mínima por categoria (resuma/corrija):
  - Mecânica: FreeCAD
  - Eletrônica: KiCad
  - Firmware: Arduino CLI, VS Code
  - Servidor: VS Code, Flutter (configurar builds Windows/Linux), Web local
  - Geral: git, Sublime Text, Sublime Merge, Markdown preview tool
  - IA: (quais ferramentas/SDKs?)

7. Testes automatizados
- Quais testes automatizados mínimos espera para cada ferramenta? Exemplos aceitáveis:
  - Executar `--version`/`--help` e validar saída
  - Compilar projeto de exemplo (quando disponível)
- Aceita que alguns testes só sejam manuais por limitações do ambiente (ex.: validar GUI)?
- As decisões e métodos de teste detalhados podem ser documentados em [TESTING.md](TESTING.md).

8. Suporte a containerização
- Deseja suporte para Docker/Podman para instalar e testar componentes server/web em containers em vez de VMs?
- Observação: containers são importantes, mas serão deixados para uma etapa posterior, portanto não precisam ser incorporados à primeira versão do script.

9. Licenças e termos
- Tem restrições legais quanto a instalação automática de softwares proprietários (ex.: Sublime, drivers)?

10. Licenças e termos
- Tem restrições legais quanto a instalação automática de softwares proprietários (ex.: Sublime, drivers)?

11. Logs e telemetria
- Deseja coletar logs e status em um arquivo `maktrak_setup.log`? Deseja opção para enviar relatórios de erro (privacidade)?

12. Plataforma alvo e arquitetura
- Além das versões de SO listadas, quais arquiteturas (x86_64, arm64) precisam ser suportadas?

13. Cronograma e priorização
- Quais categorias são prioridade inicial (por exemplo: Geral + Firmware + Eletrônica)?

14. Referências e links
- Confirmar que o link literário fornecido ([https://share.google/aimode/jQQQFq4VttHpozdoF](https://share.google/aimode/jQQQFq4VttHpozdoF)) é o único recurso a consultar ou há mais.


Por favor responda estas perguntas para que eu gere o esqueleto do script e os arquivos de configuração iniciais (`repos.yaml`, `modules.yaml`).

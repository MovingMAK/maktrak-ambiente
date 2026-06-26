# MakTrak — Plano de implementação do instalador

Resumo: documento curto descrevendo o objetivo, restrições e design proposto para um script Python multiplataforma que cria/configura ambientes de desenvolvimento e produção para o projeto MakTrak.

Objetivos principais
- Fornecer um script Python executável em Windows e Linux para instalar/configurar ferramentas por categoria (mecânica, eletrônica, firmware, servidor, IA, etc.).
- Ser idempotente e verificável (testes/validações após instalação).
- Permitir controlar se o script atualiza o sistema operacional (flag `--update-os`, padrão: desligado).
- Clonar um conjunto configurável de repositórios antes das instalações.

Requisitos e restrições
- Suportar Windows 10/11 e Xubuntu 24.04/26.04.
- Instalações de GUI no Linux podem usar `snap` quando disponível; no Windows usar `winget`/`choco` se disponível, com fallback para instaladores oficiais.
- O script deve pedir privilégios elevador quando necessário (administrador/sudo) e suportar um modo não-interativo (`--yes`).
- Validar presença de dependências (ex.: `git`) e instalar apenas quando ausentes.

Design proposto (alto nível)
1. Arquivos de configuração
   - `repos.yaml` — lista de repositórios a clonar (nome, URL, destino, branch/tag opcional).
   - `modules.yaml` — lista de módulos por categoria com meta: nome, package manager, comando de verificação, comando de instalação, pós-tarefas.
   - O script deve suportar clonagem autenticada do GitHub usando token pessoal (PAT) definido em variável de ambiente (`GITHUB_TOKEN` ou `GH_TOKEN`).
2. Estrutura do script
   - `maktrak_setup.py` — CLI usando `argparse` com flags: `--repos-file`, `--modules-file`, `--update-os`, `--yes`, `--dry-run`, `--category` (filtrar categorias), `--test`.
   - Módulos internos: os_utils (detecção e wrappers de package managers), git_utils, installer (idempotência), tester (scripts de verificação), logger.
3. Fluxo de execução
   - Detectar SO e ambiente (WSL, headless, CI).
   - Ler configuração de repositórios e clonar (com retry/logging).
   - Para cada módulo habilitado:
     - Verificar se já está instalado (comando de verificação configurável).
     - Se ausente, executar instalador adequado (snap/apt/apt-get, winget/choco, executável .exe/.msi, pip, flutter sdk installer etc.).
     - Executar verificações pós-instalação (ex.: `code --version`, `arduino-cli version`, `kicad --version`).
   - Gerar relatório final com status (OK/failed/warnings) e códigos de saída.
4. Testes automatizados
   - Testes unitários simples para funções utilitárias (detecção SO, parsing YAML, verificação de instalação).
   - Testes integrados opcionais que executam comandos de verificação no ambiente alvo (manual/automatizado).

Instalação de ferramentas específicas (exemplos)
- Geral: `git` (sempre verificar/instalar).
- Editores: `sublime-text`, `sublime-merge` — em Linux via `snap install` quando aplicável; no Windows via `winget`.
- IDEs/SDKs: `vscode` (snap/winget), `arduino` (CLI/installers), `flutter` (extra steps para PATH e build targets), `freecad`, `kicad`.

Testes e validação
- Validar cada instalação sempre que possível.
- Verificar ferramentas com comandos como `--version`, `--help` ou outras verificações apropriadas.
- O plano detalhado de testes está descrito em [TESTING.md](TESTING.md).
- Containers são relevantes, mas serão tratados em uma etapa posterior, não no escopo inicial.
- Recomenda-se deixar `--update-os` desligado por padrão; documentar risco e permitir ligar explicitamente.
- Instalações que requerem UI/aceitação de EULA devem ser explícitas e documentadas (modo `--yes` pode ignorar prompts quando aceitável).

Próximos artefatos a implementar
- `maktrak_setup.py` (esqueleto CLI e detectores de SO).
- `repos.yaml` e `modules.yaml` com exemplos mínimos.
- `IMPLEMENTATION_QUESTIONS.md` com dúvidas a esclarecer antes da implementação.

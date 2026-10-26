# MakTrak Setup — Implementação

Estado atual e próximos passos do instalador. Este documento reflete o que
existe hoje no código (`maktrak_setup.py`), não o plano original — o histórico
fica no git. O comportamento do instalador é descrito no README.

## Estado atual

- Arquivo baixado pelo bootstrap: `maktrak_setup.py` (orquestrador + classe base
  `SetupBase` + catálogo `_PKG`), sem dependências externas. No modo `prod` o
  próprio orquestrador baixa um segundo arquivo, o `server_setup.py`
  (autossuficiente: não importa `maktrak_setup` e não depende de clone).
- Instalação por SO: `apt`/`snap` no Linux e `winget` no Windows. Não há
  `choco` — o `winget` cobre os pacotes necessários.
- Privilégios elevados (sudo/admin), keepalive de sudo e atualização do
  ambiente (`apt upgrade` / `winget upgrade --all`).
- Seleção de **modo** (`dev` ou `prod`) e dos componentes do modo. Catálogos:
  `DEV_MODULES`/`DEV_REPOSITORIES` e `PROD_MODULES`/`PROD_REPOSITORIES`. No
  `prod` o componente é `servidor-prod` e o catálogo de repositórios de dev é
  vazio; `ia` (Ollama/Open WebUI) segue fora da seleção.
- Modo `prod` **delegado**: sem ferramentas de dev e sem build. O orquestrador
  baixa o `server_setup.py` (repo público, mesma branch escolhida, com fallback
  para `main`) e o executa como processo separado. O `server_setup.py` é um
  bootstrap fino: clona o repositório do servidor (raso, na branch pedida) em
  `~/maktrak-server` e executa o `install_server.py` do clone, que cria o venv,
  grava a unit `maktrak-server.service` e valida `GET /moving`. O serviço roda
  `main.py --port 8000` (`--extern` por padrão) no Linux (systemd) e no Windows
  (`schtasks`). O código da API chega pelo `POST /maktrak/deploy`.
- No modo `prod` o token GitHub vem de `GITHUB_TOKEN`/`GH_TOKEN` ou de
  `~/.git-credentials`; se o clone falhar, o script pede o token uma vez. Ele é
  injetado no git por variável de ambiente (`GIT_CONFIG_*`), não pela linha de
  comando.
- Credenciais GitHub (store, variável de ambiente ou prompt), clone e
  atualização dos repositórios e associação ao Sublime Merge.
- Execução das derivadas (`repo_setup.py` de cada componente) nas fases
  `init → install → configure → test` e relatório consolidado.
- Extensões VS Code universais e helpers de Flutter, Android, PlatformIO e
  Python (venv) na classe base.
- Bootstrap em um comando por SO: `setup_windows.ps1` (Windows) e `setup.sh`
  (Linux/macOS).

## Próximos passos

Pendências herdadas da divisão base/derivada e do estado atual:

- [ ] Validar o fluxo completo em máquina limpa no Windows (elevação,
      Windows Terminal, winget) e no Linux.
- [ ] Validar macOS no fluxo real — hoje a detecção cobre `macos`, mas o
      `install_pkgs` instala apenas em Linux/Windows.
- [ ] Migrar/validar os `repo_setup.py` dos demais repositórios
      (`maktrak-hw`, `maktrak-fw`, `maktrak-server`) contra o `SetupBase`
      atual.
- [ ] Versionar o contrato base/derivada (ex.: `SETUP_API_VERSION` no
      bootstrap e `REQUIRES_SETUP_API` na derivada) para não carregar uma
      derivada incompatível.
- [ ] Ampliar os testes automatizados além de credenciais git: seleção de
      componentes, carga de derivadas, propagação de falhas até o relatório
      e instalação Android.
- [ ] Fechar os serviços de produção que faltam (reverse proxy nginx para a API
      na porta 8000 e health checks contínuos) e as questões de IA — ver
      `IMPLEMENTATION_QUESTIONS.md`.
- [ ] Definir uma URL oficial imutável (release/tag) para instalações de
      produção.

## Documentos relacionados

- `README.md` — como executar e arquitetura (classe base + derivadas).
- `IMPLEMENTATION_QUESTIONS.md` — dúvidas em aberto.
- `TESTING.md` — testes e validações.
- `URGENT_REVIEW.md` — pendências técnicas mapeadas em revisão (não
  aplicadas).

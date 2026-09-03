# MakTrak Setup — Implementação

Estado atual e próximos passos do instalador. Este documento reflete o que
existe hoje no código (`maktrak_setup.py`), não o plano original — o histórico
fica no git. O comportamento do instalador é descrito no README.

## Estado atual

- Único arquivo baixado: `maktrak_setup.py` (orquestrador + classe base
  `SetupBase` + catálogo `_PKG`), sem dependências externas.
- Instalação por SO: `apt`/`snap` no Linux e `winget` no Windows. Não há
  `choco` — o `winget` cobre os pacotes necessários.
- Privilégios elevados (sudo/admin), keepalive de sudo e atualização do
  ambiente (`apt upgrade` / `winget upgrade --all`).
- Seleção de componentes no modo `dev`. O modo `prod` (servidor-prod/IA)
  está pausado, sem módulos definidos (`PROD_MODULES` vazio).
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
- [ ] Decidir as questões em aberto de produção/IA (ver
      `IMPLEMENTATION_QUESTIONS.md`) antes de retomar o modo `prod`.
- [ ] Definir uma URL oficial imutável (release/tag) para instalações de
      produção.

## Documentos relacionados

- `README.md` — como executar e arquitetura (classe base + derivadas).
- `IMPLEMENTATION_QUESTIONS.md` — dúvidas em aberto.
- `TESTING.md` — testes e validações.
- `URGENT_REVIEW.md` — pendências técnicas mapeadas em revisão (não
  aplicadas).

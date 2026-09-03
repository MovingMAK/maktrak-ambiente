# Análise de simplificações do `maktrak_setup.py`

> Data: 2026-09-03
> Base: `maktrak_setup.py` v1.3.6 (1768 linhas)
> Objetivo: classificar propostas de simplificação pela quantidade de linhas
> removíveis, para priorizar o que vale a pena fazer.

Método: leitura do arquivo, verificação de usos dentro deste repositório e
cruzamento com a revisão anterior (`URGENT_REVIEW.md`). Toda remoção de método
da classe base precisa ser confirmada nos repositórios derivados
(`maktrak-hw`, `maktrak-fw`, `maktrak-server`) que não estão neste workspace.

---

## Resumo (ordenado por linhas removíveis)

| # | Proposta | Linhas removíveis (~) | Tipo |
|---|----------|----------------------:|------|
| 1 | Dev vira "tudo": sem seleção de componentes (mantendo dev e prod) | ~80 | Estrutural |
| 2 | Elevação + preparo do terminal movidos para o bootstrap Windows | 65–90 | Estrutural |
| 3 | Helpers de sistema não usados (`service_enable`, `service_restart`, `write_config`, `append_line`) | 29 | Código morto |
| 4 | `self.managers` + `_detect_package_managers()` | 19 | Código morto |
| 5 | `_refresh_path()` (delegação desnecessária) | 5 | Duplicação |
| 6 | Duplicação do Windows Terminal (bootstrap + derivado) | 4 | Duplicação |
| 7 | Entrada `chromium` no `_PKG` | 1 | Código morto |

Soma dos itens de baixo risco (3, 4, 5, 6, 7): **≈ 58 linhas**.

---

## Detalhe das propostas

### 1. Dev vira "tudo" — sem seleção de componentes — ~80 linhas

Hipótese: remover a pergunta "Escolha componentes" do modo dev; `dev` passa a
clonar e executar **todos** os repositórios de uma vez. `dev` e `prod` seguem
como os dois modos — o `mode` continua em `_ui_select_mode()`/`main()`; quando
o `prod` for retomado, ganha sua própria lista de repositórios.

Blocos removidos (68 linhas):

- Catálogos `DEV_MODULES`, `DEV_REPOSITORIES` e o `PROD_MODULES` vazio com o
  comentário (96–113) — 18 linhas;
- `_ui_select_components()` (1211) — 19 linhas;
- `_get_repositories_to_clone()` (1617) — 8 linhas;
- `_get_software_for_components()` (1627) — 12 linhas;
- `_get_repo_key()` (1754) — 11 linhas.

Reescritas pequenas (≈ −12 linhas):

- `_ui_confirm(mode, repos, branch)`: some a linha "Componentes" e o bloco
  "Softwares" (~ −7);
- `main()`: `repos = sorted(REPOSITORIES) if mode == "dev" else []` e o loop
  passa a rodar cada repo clonado uma vez, sem `_get_repo_key()` (~ −3);
- `_git_clone_repos(repos, branch)` recebendo a lista pronta (~ −2).

Resultado: **≈ 80 linhas** (~4,5% do arquivo), mantendo `SetupBase`, as 4 fases
e as derivadas intactas.

Bônus: hoje, "todos" no dev executa o repo `hardware` **duas vezes**
(`mecanica` e `eletronica` mapeiam para `hardware`) — com dev = tudo, cada repo
roda uma única vez.

- Risco: médio — muda a interação (dev passa a instalar tudo; perde-se o setup
  seletivo por categoria).
- Exige: decidir se o dev seletivo ainda é necessário e garantir que todos os
  repos de dev tenham `repo_setup.py` coerente.

### 2. Elevação e preparo do terminal no bootstrap Windows — 65–90 linhas

O `maktrak_setup.py` reexecuta a si mesmo como administrador e dentro do
Windows Terminal: `_windows_prepare_terminal()` (linhas 1065–1129, 65 linhas)
instala o WT, define-o como padrão e reabre o processo elevado; o ramo Windows
de `_sys_require_admin()` (1132–1160) repete a elevação por outro caminho.

Se o `setup_windows.ps1` for executado elevado e já preparar o Windows
Terminal, o re-lançamento interno deixa de ser necessário. Redução estimada:
65+ linhas em `_windows_prepare_terminal()` mais parte de `_sys_require_admin()`.

- Risco: alto — é o fluxo mais sensível do Windows (elevação e janela correta).
- Exige: teste manual completo no Windows antes e depois.

### 3. Helpers de sistema não usados — 29 linhas

`service_enable` (495–497, 3), `service_restart` (499–501, 3),
`write_config` (503–516, 14) e `append_line` (518–526, 9). Nenhum
`repo_setup.py` os usa hoje (revisão `URGENT_REVIEW.md`); `IaSetup`, que
precisaria deles, reimplementa tudo com `sudo tee`.

- Alternativa (não remove linhas da base): migrar `IaSetup`/`ServerSetup` para
  usá-los quando a produção for retomada.
- Confirmar nos repositórios derivados antes de remover.

### 4. `self.managers` + `_detect_package_managers()` — 19 linhas

A detecção (205–222, 18 linhas) só é atribuída em `__init__` (187) e nunca é
lida em lugar nenhum deste repositório — o `install_pkgs` decide por
SO, não pelo dicionário `managers`.

- Confirmar que nenhuma derivada lê `self.managers`.

### 5. `_refresh_path()` como método estático — 5 linhas

`SetupBase._refresh_path()` (428–433) apenas delega para a função global
`_windows_refresh_path()`. Trocar as duas chamadas
(`self._refresh_path()` → `_windows_refresh_path()`) e remover o método
economiza 5 linhas sem mudar comportamento.

### 6. Instalação duplicada do Windows Terminal — 4 linhas

O WT é instalado em dois lugares: `_windows_prepare_terminal()` no boot do
Windows e `install_pkgs("windows-terminal")` pelo derivado de ambiente
(`DEV_MODULES["ambiente"]`, linha 97, e `repo_setup.py`, linha 21). No Linux a
entrada do `_PKG` é `()` vazia, então `install_pkgs` ainda emite um aviso a
cada execução.

- Manter a instalação apenas no bootstrap (ou apenas no derivado), não nos
  dois. Remover também o aviso no Linux.

### 7. Entrada `chromium` no `_PKG` — 1 linha

`"chromium"` (linha 126) não é usado por nenhum componente; o winget é vazio.

---

## Notas

- Os itens 3 e 4 tocam a API da classe base compartilhada: antes de aplicar,
  confirmar os usos nos `repo_setup.py` de `maktrak-hw`, `maktrak-fw` e
  `maktrak-server`.
- Os itens 1 e 2 mudam comportamento/fluxo e devem ser tratados como
  refatoração com teste manual, não como limpeza rápida.
- Sugestão de ordem: aplicar 3, 4, 5, 6, 7 (≈ 58 linhas, baixo risco) e decidir
  à parte os itens estruturais 1 e 2 (dev = tudo e elevação no bootstrap).

---

## Status da aplicação (2026-09-03)

- **Aplicados**: itens 3, 4, 5 e 6 (helpers de sistema não usados,
  `self.managers`, `_refresh_path()` e Windows Terminal duplicado) e o
  **bônus** — cada `repo_setup.py` roda uma única vez (deduplicação por
  repositório), mantendo a seleção de cenários de dev intacta.
- **Item 7 revertido por decisão (software base SEMPRE)**: o orquestrador
  instala em toda execução o software base via `_install_base_software()`:
  git + Google Chrome (browser essencial; não há snap oficial — Linux com o
  `.deb` do Google, Windows com o MSI oficial via `msiexec`, pois o pacote
  `Google.Chrome` do winget costuma falhar com hash desatualizado).
- **Não aplicado — item 1**: dev = tudo / junção dos cenários de dev (decisão
  de manter a seleção de componentes).
- **Não aplicado — item 2**: elevação + preparo do terminal movidos para o
  bootstrap Windows. Exige validação manual no Windows e ajuste do fluxo
  `irm | iex` (sem arquivo local para re-elevar); fica para uma sessão com
  acesso ao Windows.

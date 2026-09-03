# MakTrak Ambiente

Configuração rápida de ambiente para desenvolvimento e produção no projeto
MakTrak. Um único instalador (`maktrak_setup.py`) é baixado e executado; ele
atualiza o sistema, clona os repositórios dos componentes e configura cada um.

## Como executar

### Windows (PowerShell)

```powershell
irm "https://raw.githubusercontent.com/MovingMAK/maktrak-ambiente/main/setup_windows.ps1" | iex
```

O bootstrap instala o Python 3 (se ausente), baixa o `maktrak_setup.py` e o
executa.

### Linux (bash)

Baixe e execute (sem usar pipe, para o instalador poder ler suas respostas):

```bash
wget -q "https://raw.githubusercontent.com/MovingMAK/maktrak-ambiente/main/setup-linux.sh" -O /tmp/setup-linux.sh && bash /tmp/setup-linux.sh
```

(Se preferir `curl`: `curl -fsSL "<url>" -o /tmp/setup-linux.sh && bash /tmp/setup-linux.sh`.)
O bootstrap garante o `python3`, baixa o `maktrak_setup.py` e o executa.
(No macOS o mesmo script funciona via bash.)

Os scripts de bootstrap vivem na raiz deste repositório
(`setup_windows.ps1` e `setup-linux.sh`); quem preferir pode baixá-los e
executá-los localmente.

## O que o instalador faz

- detecta o sistema operacional e prepara o terminal (Windows Terminal no
  Windows);
- exige privilégios elevados (sudo/administrador) e mantém o ticket sudo
  vivo durante a execução;
- atualiza o ambiente (`apt upgrade` / `winget upgrade --all`);
- instala sempre o software base: git e Google Chrome (browser essencial);
- pergunta quais componentes instalar (modo dev) e confirma o resumo;
- coleta ou reutiliza credenciais GitHub para repositórios privados;
- clona/atualiza os repositórios dos componentes selecionados;
- executa o setup de cada componente e consolida um relatório final.

## Arquitetura: classe base + scripts derivados

A instalação é dividida em duas partes:

- `maktrak_setup.py` — o único arquivo baixado. Contém o orquestrador
  (privilégios, atualização do ambiente, seleção, clone e relatório) e a
  classe base `SetupBase`, com o catálogo de software (`_PKG`) e os helpers
  reutilizáveis (apt/snap/winget, git, Flutter, Android, VS Code etc.).
- `repo_setup.py` — um por repositório de componente (`maktrak-ambiente`,
  `maktrak-hw`, `maktrak-fw`, `maktrak-server`). Define uma classe que herda
  de `SetupBase` e declara apenas o que é específico daquele componente.

Cada script derivado implementa as mesmas 4 fases:

- `init()` — anuncia e prepara o que será feito;
- `install()` — instala os pacotes do componente;
- `configure()` — aplica configurações e serviços;
- `test()` — valida o resultado e alimenta o relatório.

O orquestrador clona os repositórios selecionados, carrega o `repo_setup.py`
de cada um, instancia a classe derivada e executa as 4 fases em sequência. A
derivada importa `SetupBase` de `maktrak_setup`; como o orquestrador registra
o próprio módulo em `sys.modules` antes de carregá-la, o import resolve sem
dependência de caminho.

## Observações

- O download do instalador é feito do repositório público
  `MovingMAK/maktrak-ambiente` (branch `main`).
- Durante a execução, o script pode pedir usuário/token do GitHub para
  acessar repositórios privados da organização.

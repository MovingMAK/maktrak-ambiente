# MakTrak Ambiente

Configuração rápida de ambiente para desenvolvimento e produção no projeto
MakTrak. Um único instalador é baixado e executado:

- **`dev`** — o `maktrak_setup.py` atualiza o sistema, clona os repositórios
  dos componentes e configura cada um;
- **`prod`** — o `maktrak_setup.py` delega para o `server_setup.py` (baixado do
  mesmo repositório), que clona o repositório do servidor e executa o
  `install_server.py` dele — sem ferramentas de dev e sem buildar.

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
- pergunta o **modo** — `dev` (desenvolvimento) ou `prod` (produção) — os
  componentes do modo e confirma o resumo;
- coleta ou reutiliza credenciais GitHub para repositórios privados;
- clona/atualiza os repositórios dos componentes selecionados;
- executa o setup de cada componente e consolida um relatório final.

No modo `prod` os passos de clone, extensões do VS Code e derivadas **não**
rodam: o instalador baixa e executa o `server_setup.py` (ver “Modos”).

### Modos

| Modo | Uso | Componentes |
|------|-----|-------------|
| `dev` | desenvolvimento (ferramentas de build/edição no host) | `ambiente`, `mecanica`, `eletronica`, `firmware`, `servidor` |
| `prod` | servidor em operação (sem ferramentas de dev) | `servidor-prod` |

No modo `prod` o orquestrador **não instala ferramentas de dev nem builda**.
Ele baixa o `server_setup.py` (mesmo repositório, mesma branch escolhida) e o
executa. Esse script é um bootstrap fino:

1. confere requisitos (`git`, sistema suportado);
2. clona o repositório do servidor (raso, na branch pedida) em
   `~/maktrak-server` — ou atualiza o clone existente;
3. executa o `install_server.py` do clone, que cria o venv
   (`~/.venvs/maktrak-server`), grava a unit a partir de
   `deploy/server/systemd/maktrak-server.service`, habilita/inicia o serviço e
   confere `GET /moving`.

O serviço roda `main.py --port 8000` (`--extern` por padrão) e se chama
`maktrak-server` (systemd no Linux; tarefa agendada no Windows). O deploy usa
`POST /maktrak/deploy` e substitui apenas `server_api/exec/`; os bancos em
`server_api/database/` ficam intactos.

A pasta do projeto fica fora do clone de desenvolvimento
(`~/repos/movingmak/maktrak/`) de propósito.

Requisitos do modo `prod`: `git` e um token GitHub com leitura no repositório
`maktrak-server` (privado). O token vem de `GITHUB_TOKEN`/`GH_TOKEN` ou de
`~/.git-credentials`; sem ele, o clone falha e o script pede o token (uma vez).
O token é injetado no git por variável de ambiente (`GIT_CONFIG_*`), não pela
linha de comando. No Linux o serviço usa systemd; no Windows, `schtasks`.

## Arquitetura: classe base + scripts derivados

A instalação é dividida em duas partes:

- `maktrak_setup.py` — o arquivo baixado pelo bootstrap. Contém o orquestrador
  (privilégios, atualização do ambiente, seleção, clone e relatório) e a
  classe base `SetupBase`, com o catálogo de software (`_PKG`) e os helpers
  reutilizáveis (apt/snap/winget, git, Flutter, Android, VS Code etc.).
- `repo_setup.py` — um por repositório de componente (`maktrak-ambiente`,
  `maktrak-hw`, `maktrak-fw`, `maktrak-server`). Define uma classe que herda
  de `SetupBase` e declara apenas o que é específico daquele componente.
- `server_setup.py` — o setup de **produção**. Ao contrário das derivadas, é
  **autossuficiente de propósito**: não importa `maktrak_setup` e não depende de
  clone, para poder rodar sozinho num equipamento limpo. O orquestrador o baixa
  e executa quando o modo é `prod`; ele também pode ser baixado e rodado
  diretamente numa máquina de produção.

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
- No modo `prod` são baixados dois arquivos do repositório público
  (`maktrak_setup.py` e `server_setup.py`); o código do servidor vem do clone de
  `maktrak-server` (privado), usando o token.

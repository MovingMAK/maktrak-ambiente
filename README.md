# MakTrak Ambiente

Configuração rápida de ambiente para desenvolvimento e produção no projeto
MakTrak. Um único instalador é baixado e executado:

- **`dev`** — o `maktrak_setup.py` atualiza o sistema, clona os repositórios
  dos componentes e configura cada um;
- **`prod`** — o `maktrak_setup.py` delega para o `server_setup.py` (baixado do
  mesmo repositório), que instala o runtime do servidor e sobe o recebedor de
  deploy. Sem clonar repositórios e sem buildar.

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

No modo `prod` **nada é clonado nem buildado**. O `maktrak_setup.py` baixa o
`server_setup.py` (mesmo repositório, mesma branch escolhida) e o executa. Esse
script:

1. instala o runtime Python (venv em `~/.venvs/maktrak-server` com
   FastAPI/uvicorn/pydantic/starlette);
2. baixa o recebedor de deploy (`deploy.py`, `errors.py` e
   `deploy_receiver.py`, do repositório `maktrak-server`) para a pasta do
   projeto;
3. cria e sobe o serviço systemd `maktrak-receiver.service` (porta 8001);
4. confere `GET /maktrak` e imprime o relatório.

O código da API chega depois, pelo `POST /maktrak/deploy` — por isso a pasta do
projeto (`~/maktrak-server` por default) fica fora do clone de desenvolvimento
(`~/repos/movingmak/maktrak/`) e `server_api/database` é preservada.

Requisitos do modo `prod`: Linux com systemd e um token GitHub com leitura no
repositório `maktrak-server` (privado). O token pode vir de `GITHUB_TOKEN` ou do
`~/.git-credentials`; sem ele o setup avisa e não instala nada. O que ainda falta
em produção — unit/nginx para a API em si (porta 8000) e health checks
contínuos — está em `IMPLEMENTATION_QUESTIONS.md`.

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
  (`maktrak_setup.py` e `server_setup.py`); os arquivos do recebedor vêm do
  `maktrak-server` (privado) via API de conteúdo do GitHub, usando o token.

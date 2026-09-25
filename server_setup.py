#!/usr/bin/env python3
"""MakTrak Setup - Servidor de Producao (modo `prod`).

Instala SOMENTE o que um equipamento servidor precisa para entrar em operacao:

  1. runtime Python (venv com fastapi/uvicorn/pydantic/starlette);
  2. o recebedor de deploy minimo (`deploy.py`, `errors.py` e
     `deploy_receiver.py`, do repo `MovingMAK/maktrak-server`);
  3. um servico systemd que mantem o recebedor no ar.

NAO clona repositorio e NAO builda nada: o codigo da API chega depois, pelo
`POST /maktrak/deploy` (pacote gerado por `server_api/utils/deploy/deploy.py`
no equipamento de origem).

Uso:
    # Delegado pelo orquestrador (modo prod): o maktrak_setup.py baixa este
    # arquivo do repo publico e o executa.
    python3 server_setup.py --branch main

    # Direto, num equipamento de producao:
    wget -q https://raw.githubusercontent.com/MovingMAK/maktrak-ambiente/main/server_setup.py
    python3 server_setup.py

Este arquivo e autossuficiente de proposito: nao importa `maktrak_setup` e nao
depende de clone nenhum, para poder rodar sozinho em uma maquina limpa.
"""

import argparse
import getpass
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# ============================================================================
# IDENTIFICACAO E VERSAO
# ============================================================================

SETUP_NAME = "MakTrak Setup - Servidor de Producao"
SETUP_VERSION = "1.0.0"
SETUP_DATE = "2026-09-25"

# Cores ANSI (desativadas quando a saida nao e TTY)
ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"
ANSI_CYAN = "\033[36m"

SUDO_KEEPALIVE_INTERVAL = 120  # segundos entre renovacoes do ticket sudo


def configurar_saida():
    """Garante saida UTF-8 mesmo com stdout redirecionado para arquivo.

    No Windows/Linux, `print` com emoji quebra com UnicodeEncodeError quando a
    saida vai para arquivo (cp1252) — o crash mataria a rotina no meio.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _cores_ativas():
    """True quando a saida e um terminal (permite cores ANSI)."""
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


# Ajusta a saida no proprio carregamento: este script imprime emojis e pode ter
# stdout redirecionado (log de servico, pipe, `> arquivo`), onde o encoding
# cp1252 do Windows quebraria com UnicodeEncodeError e mataria a rotina.
configurar_saida()


def print_banner():
    """Imprime nome + versao + data deste script, em destaque colorido."""
    cor = ANSI_GREEN if _cores_ativas() else ""
    fim = ANSI_RESET if cor else ""
    print(f"{ANSI_BOLD if cor else ''}{cor}== {SETUP_NAME} "
          f"v{SETUP_VERSION} ({SETUP_DATE}) =={fim}")


def _titulo(texto):
    """Cabecalho de secao."""
    print(f"\n--- {texto} ---")


# ============================================================================
# CONSTANTES DE PRODUCAO
# ============================================================================

# Repo (privado) de onde vem o recebedor de deploy. Requer token GitHub.
REPO_SERVIDORES = "MovingMAK/maktrak-server"

# Arquivos do recebedor minimo, relativos ao repo. O recebedor importa `deploy`,
# que por sua vez importa `errors` — os tres andam juntos.
ARQUIVOS_RECEBEDOR = (
    "server_api/exec/errors.py",
    "server_api/exec/deploy.py",
    "server_api/exec/deploy_receiver.py",
)

# Pasta do projeto servidor no equipamento (alvo que o deploy substitui).
# Fica FORA de ~/repos/movingmak (clone de dev) de proposito: producao nao
# compartilha pasta com desenvolvimento.
ALVO_PADRAO = Path.home() / "maktrak-server"

PORTA_PADRAO = 8001  # a API usa 8000; o recebedor fica em 8001
VENV_NOME = "maktrak-server"
RUNTIME_PKGS = ("fastapi", "uvicorn", "pydantic", "starlette")

UNIT_NAME = "maktrak-receiver.service"
UNIT_PATH = Path("/etc/systemd/system") / UNIT_NAME


# ============================================================================
# EXECUCAO E PRIVILEGIOS
# ============================================================================

def _detect_os():
    """Detecta o SO: linux | windows | macos."""
    system = platform.system()
    if system == "Linux":
        return "linux"
    if system == "Windows":
        return "windows"
    if system == "Darwin":
        return "macos"
    print(f"Sistema nao suportado: {system}")
    sys.exit(1)


OS_TYPE = _detect_os()


def _run(cmd, capture_output=False, text=True, cwd=None):
    """Executa um comando e retorna subprocess.CompletedProcess."""
    try:
        return subprocess.run(cmd, capture_output=capture_output, text=text,
                              cwd=cwd)
    except Exception as exc:
        print(f"  ❌ Falha ao executar: {' '.join(str(c) for c in cmd)}")
        print(f"    {exc}")
        return subprocess.CompletedProcess(args=cmd, returncode=-1)


def _sudo_ok():
    """True se o ticket sudo esta valido (checagem nao interativa)."""
    if OS_TYPE != "linux":
        return True
    try:
        return subprocess.run(["sudo", "-n", "true"],
                              capture_output=True).returncode == 0
    except Exception:
        return False


def sudo_ensure():
    """Solicita/renova o ticket sudo. Retorna True se ficou valido."""
    if _sudo_ok():
        return True
    _run(["sudo", "-v"])
    if _sudo_ok():
        print("  ✅ Sudo renovado.")
        return True
    print("  ⚠️ Sudo indisponivel; as etapas com systemd vao falhar.")
    return False


def sudo_keepalive():
    """Thread daemon que renova o ticket sudo a cada 2 minutos.

    Evita a expiracao durante operacoes longas (apt, pip, downloads).
    """
    if OS_TYPE != "linux":
        return None

    def _refresh():
        while True:
            time.sleep(SUDO_KEEPALIVE_INTERVAL)
            try:
                subprocess.run(["sudo", "-n", "-v"], capture_output=True)
            except Exception:
                pass

    thread = threading.Thread(target=_refresh, daemon=True,
                              name="sudo-keepalive")
    thread.start()
    return thread


def _apt_install(pkgs):
    """Instala pacotes via apt-get. Retorna True em sucesso."""
    if not pkgs:
        return True
    print(f"  Instalando via apt: {', '.join(pkgs)}...")
    _run(["sudo", "apt-get", "update"])
    return _run(["sudo", "apt-get", "install", "-y", *pkgs]).returncode == 0


# ============================================================================
# TOKEN GITHUB (repo de servidores e privado)
# ============================================================================

def _token_do_store():
    """Le o token do ~/.git-credentials (primeira linha do GitHub)."""
    store_path = Path.home() / ".git-credentials"
    try:
        for line in store_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("https://") and "@github.com" in line:
                creds = line[len("https://"):].split("@")[0]
                user, _, token = creds.partition(":")
                if user and token:
                    return urllib.parse.unquote(token)
    except Exception:
        pass
    return ""


def resolver_token():
    """Obtem o token GitHub (ambiente, store ou prompt). '' se indisponivel.

    O recebedor vive no repo privado `MovingMAK/maktrak-server`, entao o setup
    de producao precisa de leitura nesse repo (o download usa a API de
    conteudo do GitHub).
    """
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        print("  ✅ Usando GITHUB_TOKEN do ambiente")
        return token.strip()
    token = _token_do_store()
    if token:
        print("  ✅ Usando credenciais de ~/.git-credentials")
        return token
    if not sys.stdin.isatty():
        return ""
    _titulo("Autenticacao GitHub (repo privado de servidores)")
    print("  O recebedor de deploy fica em "
          f"{REPO_SERVIDORES} (privado).")
    print("  Dica: defina GITHUB_TOKEN no ambiente para nao digitar aqui.")
    try:
        informado = getpass.getpass("  GitHub token (Enter = cancelar): ")
    except Exception:
        informado = ""
    return informado.strip()


# ============================================================================
# DOWNLOAD (API de conteudo do GitHub)
# ============================================================================

def _url_conteudo(repo, caminho, ref):
    """URL da API de conteudo (conteudo cru) de um arquivo do repositorio."""
    repo_q = urllib.parse.quote(repo, safe="/")
    caminho_q = urllib.parse.quote(caminho, safe="/")
    ref_q = urllib.parse.quote(ref, safe="")
    return (f"https://api.github.com/repos/{repo_q}/contents/{caminho_q}"
            f"?ref={ref_q}")


def baixar_arquivo(repo, caminho, ref, token):
    """Baixa o conteudo cru de um arquivo do repo (via API do GitHub).

    Retorna os bytes do arquivo ou None (imprime o motivo da falha).
    """
    req = urllib.request.Request(
        _url_conteudo(repo, caminho, ref),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.raw+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "maktrak-setup",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            print("  ❌ Token GitHub invalido ou expirado (401).")
        elif exc.code == 403:
            print("  ⚠️ Acesso negado pelo GitHub (403) — token sem permissao "
                  "de leitura no repo?")
        elif exc.code == 404:
            print(f"  ❌ Nao encontrado: {caminho} (ref '{ref}') em {repo} "
                  "(branch inexistente ou token sem acesso ao repo privado).")
        else:
            print(f"  ❌ HTTP {exc.code} ao baixar {caminho}")
        return None
    except Exception as exc:
        print(f"  ❌ Falha de rede ao baixar {caminho}: {exc}")
        return None


def _sha256_curto(dados):
    """Primeiros 12 caracteres do SHA-256 (identificacao rapida)."""
    return hashlib.sha256(dados).hexdigest()[:12]


def _gravar_se_mudou(destino, dados):
    """Grava o arquivo apenas se o conteudo mudou. True se houve escrita."""
    try:
        if destino.exists() and destino.read_bytes() == dados:
            print(f"       = {destino.name} (sem mudanca)")
            return False
    except Exception:
        pass
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(dados)
    print(f"       ✅ {destino.name} ({len(dados)} bytes, "
          f"sha256 {_sha256_curto(dados)})")
    return True


def instalar_recebedor(alvo, ref, token):
    """Baixa os arquivos do recebedor para `<alvo>/server_api/exec/`.

    Retorna (ok, houve_mudanca).
    """
    _titulo("Recebedor de deploy (codigo)")
    if not token:
        print("  ❌ Sem token GitHub: impossivel baixar o recebedor de "
              f"{REPO_SERVIDORES} (repo privado).")
        print("     Defina GITHUB_TOKEN (ou configure ~/.git-credentials) e "
              "rode de novo.")
        return False, False

    destino_dir = alvo / "server_api" / "exec"
    mudou = False
    for caminho in ARQUIVOS_RECEBEDOR:
        dados = baixar_arquivo(REPO_SERVIDORES, caminho, ref, token)
        if dados is None:
            return False, mudou
        mudou = _gravar_se_mudou(destino_dir / Path(caminho).name, dados) or mudou

    # `server_api/database` e poupado no deploy; criar desde ja evita que o
    # primeiro pacote aplique sobre uma pasta inexistente.
    (alvo / "server_api" / "database").mkdir(parents=True, exist_ok=True)
    print(f"  ✅ Recebedor em {destino_dir}")
    return True, mudou


# ============================================================================
# RUNTIME PYTHON (venv)
# ============================================================================

def venv_dir():
    """Pasta do venv de runtime deste equipamento."""
    return Path.home() / ".venvs" / VENV_NOME


def venv_python():
    """Interpretador do venv (dentro de Scripts/ no Windows)."""
    base = venv_dir()
    return base / ("Scripts" if OS_TYPE == "windows" else "bin") / (
        "python.exe" if OS_TYPE == "windows" else "python")


def preparar_runtime():
    """Garante o venv com as dependencias de runtime da API/recebedor."""
    _titulo("Runtime Python (venv)")
    venv_py = venv_python()
    if not venv_py.exists():
        print(f"  Criando venv {venv_dir()}...")
        rc = _run([sys.executable, "-m", "venv", str(venv_dir())]).returncode
        if rc != 0 or not venv_py.exists():
            # Debian/Ubuntu: venv pode faltar (python3-venv)
            _apt_install(["python3-venv"])
            _run([sys.executable, "-m", "venv", str(venv_dir())])
    if not venv_py.exists():
        print("  ❌ Falha ao criar o venv. Verifique o python3-venv.")
        return None
    print(f"  ✅ Venv: {venv_dir()}")
    _run([str(venv_py), "-m", "pip", "install", "--upgrade", "pip"])
    rc = _run([str(venv_py), "-m", "pip", "install",
               *RUNTIME_PKGS]).returncode
    if rc != 0:
        print(f"  ❌ Falha ao instalar {', '.join(RUNTIME_PKGS)} no venv.")
        return None
    print(f"  ✅ Pacotes: {', '.join(RUNTIME_PKGS)}")
    return venv_py


# ============================================================================
# SERVICO SYSTEMD
# ============================================================================

def unit_text(usuario, alvo, porta, externo, python):
    """Conteudo da unit systemd do recebedor (funcao pura = testavel)."""
    args = f"--port {porta}" + (" --extern" if externo else "")
    return f"""\
[Unit]
Description=MakTrak - recebedor de deploy (uvicorn)
Documentation=https://github.com/{REPO_SERVIDORES}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={usuario}
WorkingDirectory={alvo / 'server_api'}
Environment=PYTHONUNBUFFERED=1
ExecStart={python} {alvo / 'server_api' / 'exec' / 'deploy_receiver.py'} {args}
# O recebedor encerra depois de aplicar um pacote; o Restart sobe o codigo novo.
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""


def _unit_ativa():
    """True se o servico esta ativo no systemd."""
    result = _run(["systemctl", "is-active", UNIT_NAME], capture_output=True)
    return (result.stdout or "").strip() == "active"


def instalar_servico(alvo, porta, externo, python):
    """Escreve a unit e (re)inicia o servico. Retorna (ok, unit_mudou)."""
    _titulo("Servico systemd")
    usuario = getpass.getuser()
    conteudo = unit_text(usuario, alvo, porta, externo, python)
    try:
        atual = UNIT_PATH.read_text(encoding="utf-8")
    except Exception:
        atual = ""
    unit_mudou = atual != conteudo
    if unit_mudou:
        tmp = Path("/tmp") / UNIT_NAME
        tmp.write_text(conteudo, encoding="utf-8")
        if _run(["sudo", "install", "-m", "0644", str(tmp),
                 str(UNIT_PATH)]).returncode != 0:
            print(f"  ❌ Falha ao gravar {UNIT_PATH}")
            return False, unit_mudou
        print(f"  ✅ Unit gravada: {UNIT_PATH} (Usuario: {usuario})")
    else:
        print(f"  ✅ Unit ja atualizada: {UNIT_PATH}")

    _run(["sudo", "systemctl", "daemon-reload"])
    _run(["sudo", "systemctl", "enable", UNIT_NAME])
    return True, unit_mudou


def reiniciar_servico():
    """Reinicia o servico para carregar unit/arquivos novos."""
    return _run(["sudo", "systemctl", "restart", UNIT_NAME]).returncode == 0


# ============================================================================
# HEALTH CHECK
# ============================================================================

def health_check(porta, tentativas=20):
    """Consulta GET /maktrak ate responder. Retorna (ok, detalhe)."""
    url = f"http://127.0.0.1:{porta}/maktrak"
    for _ in range(tentativas):
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                dados = json.loads(resp.read().decode("utf-8", "replace"))
            return True, f"versao {dados.get('versao')} - {dados.get('status')}"
        except Exception:
            time.sleep(1)
    return False, f"sem resposta em {url}"


# ============================================================================
# ENTRADA DO USUARIO
# ============================================================================

def _perguntar(texto, default):
    """Prompt com default; devolve o default quando nao ha terminal."""
    if not sys.stdin.isatty():
        return default
    resposta = input(texto).strip()
    return resposta or default


def _perguntar_porta(default):
    """Le uma porta valida (1-65535), com default."""
    while True:
        bruto = _perguntar(f"Porta do recebedor (Enter = {default}): ",
                           str(default))
        try:
            porta = int(bruto)
        except ValueError:
            print(f"  ⚠️ Porta invalida: {bruto!r}")
            continue
        if 0 < porta < 65536:
            return porta
        print(f"  ⚠️ Porta fora da faixa: {porta} (use 1-65535)")


def _perguntar_sim(texto, default=True):
    """Pergunta sim/nao (aceita s/y/Enter)."""
    if not sys.stdin.isatty():
        return default
    sufixo = "(S/n)" if default else "(s/N)"
    resposta = input(f"{texto} {sufixo}: ").strip().lower()
    if not resposta:
        return default
    return resposta in {"s", "sim", "y", "yes"}


# ============================================================================
# PLANO / EXECUCAO
# ============================================================================

def checar_requisitos():
    """Confere SO e systemd. Retorna (ok, mensagem)."""
    if OS_TYPE != "linux":
        return False, (f"o modo prod por enquanto suporta apenas Linux "
                       f"(detectado: {OS_TYPE}).")
    if not shutil.which("systemctl") or not os.path.isdir("/run/systemd/system"):
        return False, ("systemd nao esta disponivel (necessario para manter o "
                       "recebedor no ar).")
    return True, ""


def main():
    """MakTrak Setup - instalacao do servidor de producao."""
    print("=" * 60)
    print_banner()
    print("=" * 60)
    print("Modo producao: runtime + recebedor de deploy. Sem clone de "
          "repositorio e sem build.")

    parser = argparse.ArgumentParser(
        description="MakTrak Setup - Servidor de Producao (modo `prod`)")
    parser.add_argument("--alvo", default=None,
                        help=f"pasta do projeto servidor (default: {ALVO_PADRAO})")
    parser.add_argument("--porta", type=int, default=None,
                        help=f"porta do recebedor (default: {PORTA_PADRAO})")
    parser.add_argument("--branch", default="main",
                        help="branch/tag do repo de servidores (default: main)")
    parser.add_argument("--local", action="store_true",
                        help="escuta apenas em 127.0.0.1 (default: exposto na rede)")
    parser.add_argument("--dry-run", action="store_true",
                        help="mostra o plano e sai, sem alterar nada")
    args = parser.parse_args()

    ok, motivo = checar_requisitos()
    if not ok:
        print(f"\n❌ Producao indisponivel neste equipamento: {motivo}")
        print("   Nada foi alterado. O modo dev continua disponivel.")
        return 2

    # ── Coleta (todas as respostas antes de executar) ────────────────────
    alvo_bruto = args.alvo or _perguntar(
        f"Pasta do projeto servidor (Enter = {ALVO_PADRAO}): ", str(ALVO_PADRAO))
    alvo = Path(alvo_bruto).expanduser().resolve()
    porta = args.porta if args.porta else _perguntar_porta(PORTA_PADRAO)
    if not 0 < porta < 65536:
        print(f"❌ Porta invalida: {porta} (use 1-65535)")
        return 1
    externo = not args.local
    if not args.local and sys.stdin.isatty():
        externo = _perguntar_sim("Expor o recebedor na rede (0.0.0.0)?", True)

    # Token ANTES do resumo: o recebedor vive num repo privado e sem token nao
    # ha o que instalar. Assim todas as respostas sao coletadas antes da
    # confirmacao (mesma convencao do orquestrador).
    token = resolver_token()

    _titulo("Resumo da instalacao (producao)")
    print("Modo: prod")
    print("Servidor: runtime Python + recebedor de deploy (systemd)")
    print(f"Branch do repo de servidores: {args.branch}")
    print(f"Pasta do projeto (alvo do deploy): {alvo}")
    print(f"Porta do recebedor: {porta} "
          f"({'0.0.0.0 (rede)' if externo else '127.0.0.1 (local)'})")
    print(f"Ambiente virtual: {venv_dir()}")
    print(f"Servico: {UNIT_NAME}")
    print(f"Token GitHub: {'ok' if token else 'ausente'}")
    print("Repositorios: nenhum (o codigo chega pelo POST /maktrak/deploy)")

    if args.dry_run:
        print("\n(dry-run) Nada foi alterado.")
        return 0

    if not token:
        print("\n❌ Sem token GitHub nao ha como baixar o recebedor de "
              f"{REPO_SERVIDORES} (repo privado).")
        print("   Defina GITHUB_TOKEN no ambiente (ou configure "
              "~/.git-credentials) e rode de novo.")
        return 1

    if sys.stdin.isatty():
        confirm = input("\nProsseguir? (Y/n): ").strip().lower()
        if confirm not in {"y", "yes", "s", "sim", ""}:
            print("Instalacao cancelada.")
            return 0

    # ── Execucao ─────────────────────────────────────────────────────────
    resultados = {}
    _titulo("Privilegios")
    ok_sudo = sudo_ensure()
    resultados["sudo"] = ok_sudo
    if ok_sudo:
        sudo_keepalive()

    python = preparar_runtime()
    resultados["runtime-python"] = python is not None
    if not python:
        print("\n❌ Sem runtime Python nao ha como subir o recebedor.")
        _relatorio(resultados)
        return 1

    alvo.mkdir(parents=True, exist_ok=True)
    ok_recebedor, recebedor_mudou = instalar_recebedor(alvo, args.branch, token)
    resultados["recebedor-codigo"] = ok_recebedor
    if not ok_recebedor:
        _relatorio(resultados)
        return 1

    ok_unit, unit_mudou = instalar_servico(alvo, porta, externo, python)
    resultados["systemd-unit"] = ok_unit
    if not ok_unit:
        _relatorio(resultados)
        return 1

    # Reinicia quando a unit ou o codigo mudou (para carregar o que mudou);
    # se nada mudou, apenas garante o servico no ar.
    ativo = _unit_ativa()
    if unit_mudou or recebedor_mudou or not ativo:
        resultados["servico-reiniciado"] = reiniciar_servico()
    else:
        print("  ✅ Servico ja ativo e sem mudancas; nada a reiniciar.")

    ok_health, detalhe = health_check(porta)
    resultados["health-check"] = ok_health
    print(f"  {'✅' if ok_health else '❌'} GET /maktrak: {detalhe}")

    _relatorio(resultados)

    if ok_health:
        print("\n" + "=" * 60)
        print("✅ Servidor de producao pronto para receber deploy!")
        print("=" * 60)
        _proximos_passos(alvo, porta)
        return 0
    print("\n⚠️ O recebedor nao respondeu. Veja os logs:")
    print(f"     journalctl -u {UNIT_NAME} -n 50 --no-pager")
    return 1


def _relatorio(resultados):
    """Relatorio final da instalacao de producao."""
    _titulo("Relatorio de instalacao (producao)")
    for nome, status in resultados.items():
        print(f"  {'✅' if status else '❌'} {nome}: "
              f"{'OK' if status else 'FALHA'}")


def _proximos_passos(alvo, porta):
    """Imprime como enviar um deploy e como acompanhar o servico."""
    print("\nProximos passos:")
    print(f"  - logs do recebedor : journalctl -u {UNIT_NAME} -f")
    print(f"  - status do servico : systemctl status {UNIT_NAME}")
    print(f"  - pasta do projeto  : {alvo} (alvo do deploy; "
          f"server_api/database e preservado)")
    print("  - enviar um deploy  : no equipamento de origem, dentro do repo "
          "maktrak-server:")
    print(f"      python server_api/utils/deploy/deploy.py --servidor "
          f"<ip-deste-equipamento>:{porta}")


if __name__ == "__main__":
    sys.exit(main())

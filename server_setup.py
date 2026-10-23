#!/usr/bin/env python3
"""
MakTrak Setup — Servidor de produção (modo `prod`).

Bootstrap fino: garante os requisitos, obtém o código do servidor e delega a
instalação para o `install_server.py` do próprio repositório clonado.

  1. confere requisitos (git, sistema suportado);
  2. clona o repositório do servidor (raso, na branch pedida) — ou atualiza o
     clone existente;
  3. executa `install_server.py`, que cria o venv, instala o serviço e valida
     `GET /moving`.

O código da API chega depois pelo `POST /maktrak/deploy`; este script não
instala nem configura o recebedor por conta própria.

Uso:
    python3 server_setup.py                       # interativo
    python3 server_setup.py --branch main --port 8000 --extern
    python3 server_setup.py --target ~/maktrak-server --dry-run
"""

import argparse
import base64
import os
import platform
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

REPO_SERVIDORES = "https://github.com/MovingMAK/maktrak-server.git"
DESTINO_PADRAO = Path.home() / "maktrak-server"
PORTA_PADRAO = 8000


def _run(cmd, env=None):
    """Executa um comando herdando o terminal; devolve o returncode."""
    try:
        return subprocess.run(cmd, env=env).returncode
    except OSError as erro:
        print(f"  ❌ falha ao executar {' '.join(cmd)}: {erro}")
        return 1


def token_do_ambiente_ou_store():
    """Token GitHub: GITHUB_TOKEN/GH_TOKEN ou ~/.git-credentials."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token.strip()
    store = Path.home() / ".git-credentials"
    try:
        for linha in store.read_text(encoding="utf-8").splitlines():
            if linha.startswith("https://") and "@github.com" in linha:
                credenciais = linha[len("https://"):].split("@")[0]
                usuario, _, senha = credenciais.partition(":")
                if usuario and senha:
                    return urllib.parse.unquote(senha)
    except OSError:
        pass
    return ""


def _ambiente_git(token):
    """Ambiente do git com o token fora da linha de comando (via config)."""
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    if token:
        credencial = base64.b64encode(
            f"x-access-token:{token}".encode("utf-8")
        ).decode("ascii")
        # Acrescenta ao GIT_CONFIG_* existente (o ambiente pode já usar).
        indice = int(env.get("GIT_CONFIG_COUNT", "0") or 0)
        env["GIT_CONFIG_COUNT"] = str(indice + 1)
        env[f"GIT_CONFIG_KEY_{indice}"] = "http.https://github.com/.extraheader"
        env[f"GIT_CONFIG_VALUE_{indice}"] = f"Authorization: Basic {credencial}"
    return env


def obter_codigo(destino, branch, token):
    """Clona (raso) ou atualiza o repositório do servidor. Devolve True/False."""
    git_dir = destino / ".git"
    if git_dir.is_dir():
        print(f"  Atualizando clone em {destino} (branch {branch})...")
        rc = _run(["git", "-C", str(destino), "fetch", "--depth", "1",
                   "origin", branch], env=_ambiente_git(token))
        if rc != 0:
            return False
        return _run(["git", "-C", str(destino), "reset", "--hard",
                     "FETCH_HEAD"]) == 0

    destino.parent.mkdir(parents=True, exist_ok=True)
    print(f"  Clonando {REPO_SERVIDORES} (branch {branch})...")
    return _run(["git", "clone", "--depth", "1", "--branch", branch,
                 REPO_SERVIDORES, str(destino)],
                env=_ambiente_git(token)) == 0


def _perguntar(texto, padrao):
    """Lê uma resposta; Enter usa o padrão."""
    try:
        resposta = input(f"{texto} (Enter = {padrao}): ").strip()
    except (EOFError, KeyboardInterrupt):
        return str(padrao)
    return resposta or str(padrao)


def main():
    parser = argparse.ArgumentParser(
        description="Instala um servidor MakTrak de produção.")
    parser.add_argument("--target", default=None,
                        help=f"pasta do projeto (default: {DESTINO_PADRAO})")
    parser.add_argument("--branch", default="main",
                        help="branch do repositório do servidor (default: main)")
    parser.add_argument("--port", type=int, default=None,
                        help=f"porta da API (default: {PORTA_PADRAO})")
    parser.add_argument("--extern", action="store_true",
                        help="escuta em 0.0.0.0 (padrão quando interativo)")
    parser.add_argument("--local", action="store_true",
                        help="escuta apenas em 127.0.0.1")
    parser.add_argument("--dry-run", action="store_true",
                        help="mostra o plano e sai, sem alterar nada")
    args = parser.parse_args()

    sistema = platform.system()
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        print("❌ Não rode como root (nem com sudo): use o seu usuário; "
              "o instalador chama sudo quando precisa.")
        return 1
    if sistema not in ("Linux", "Windows"):
        print(f"❌ Sistema não suportado: {sistema} (use Linux ou Windows).")
        return 1
    if not shutil.which("git"):
        print("❌ git não encontrado; instale o git e rode de novo.")
        return 1

    interativo = sys.stdin.isatty()
    destino = Path(
        args.target or (_perguntar("Pasta do projeto", DESTINO_PADRAO)
                        if interativo else DESTINO_PADRAO)
    ).expanduser().resolve()
    porta = args.port or (int(_perguntar("Porta da API", PORTA_PADRAO))
                          if interativo else PORTA_PADRAO)
    externo = not args.local
    if interativo and not args.local and not args.extern:
        externo = _perguntar("Expor na rede (0.0.0.0)? (s/n)", "s").lower() \
            in ("s", "sim", "y", "yes")

    print("\n--- Resumo ---")
    print(f"  repositório: {REPO_SERVIDORES} (branch {args.branch})")
    print(f"  pasta      : {destino}")
    print(f"  porta      : {porta} ({'0.0.0.0' if externo else '127.0.0.1'})")

    if args.dry_run:
        print("\n(dry-run) Nada foi alterado.")
        return 0

    token = token_do_ambiente_ou_store()
    if not obter_codigo(destino, args.branch, token):
        if token or not interativo:
            print("❌ Falha ao obter o código. Verifique o token/branch.")
            return 1
        print("  O repositório é privado; informe um token do GitHub.")
        token = input("  GitHub token (Enter = cancelar): ").strip()
        if not token or not obter_codigo(destino, args.branch, token):
            print("❌ Falha ao obter o código.")
            return 1

    instalador = destino / "install_server.py"
    if not instalador.is_file():
        print(f"❌ {instalador} não encontrado no clone.")
        return 1

    comando = [sys.executable, str(instalador), "--port", str(porta)]
    comando.append("--extern" if externo else "--local")
    print(f"\n--- Instalando o serviço ({instalador.name}) ---")
    return _run(comando)


if __name__ == "__main__":
    sys.exit(main())

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
    env["LC_ALL"] = "C"   # mensagens do git em inglês (ver classificar_falha)
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


def _executar(cmd, env=None):
    """Executa capturando a saída. Devolve `(ok, texto)`."""
    try:
        resultado = subprocess.run(cmd, env=env, capture_output=True, text=True)
    except OSError as erro:
        return False, f"{type(erro).__name__}: {erro}"
    return resultado.returncode == 0, (resultado.stderr or resultado.stdout or "")


# Trechos das mensagens do git (em inglês, garantido por LC_ALL=C) que
# identificam a causa — coletados de execuções reais.
_FALHA_CREDENCIAL = (
    "authentication failed",
    "invalid username or token",
    "unable to get password",
    "could not read username",
)
_FALHA_REDE = (
    "could not resolve host",
    "failed to connect",
    "connection timed out",
    "network is unreachable",
    "could not read from remote repository",
)
_FALHA_BRANCH = (
    "not found in upstream origin",
    "couldn't find remote ref",
)


def classificar_falha(saida):
    """Causa da falha do git: `credencial`, `rede`, `branch` ou `outro`."""
    texto = (saida or "").lower()
    if any(marca in texto for marca in _FALHA_CREDENCIAL):
        return "credencial"
    if any(marca in texto for marca in _FALHA_REDE):
        return "rede"
    if any(marca in texto for marca in _FALHA_BRANCH):
        return "branch"
    return "outro"


def mensagem_falha(motivo, branch, destino):
    """Mensagem para o usuário, conforme a causa."""
    if motivo == "credencial":
        return ("O GitHub recusou a credencial. Defina GITHUB_TOKEN com "
                "leitura em maktrak-server e rode de novo.")
    if motivo == "branch":
        return f"A branch '{branch}' não existe no repositório."
    if motivo == "rede":
        return "Sem acesso ao GitHub (rede, DNS ou proxy)."
    if motivo == "destino":
        return (f"{destino} já existe e não é um clone do repositório. "
                "Remova a pasta ou use --target com outro caminho.")
    return "Falha ao obter o código (veja a saída do git acima)."


def obter_codigo(destino, branch, token):
    """Clona (raso) ou atualiza o repositório. Devolve `(ok, motivo)`.

    `motivo` é o que `classificar_falha` devolve, ou `destino` quando a pasta
    já existe sem ser um clone (o `git clone` recusaria com erro obscuro).
    """
    git_dir = destino / ".git"
    if git_dir.is_dir():
        print(f"  Atualizando clone em {destino} (branch {branch})...")
        ok, saida = _executar(["git", "-C", str(destino), "fetch", "--depth", "1",
                               "origin", branch], env=_ambiente_git(token))
        if not ok:
            print(f"  {saida.strip()}")
            return False, classificar_falha(saida)
        ok, saida = _executar(["git", "-C", str(destino), "reset", "--hard",
                               "FETCH_HEAD"])
        if not ok:
            print(f"  {saida.strip()}")
            return False, "outro"
        return True, ""

    if destino.is_dir() and any(destino.iterdir()):
        return False, "destino"

    destino.parent.mkdir(parents=True, exist_ok=True)
    print(f"  Clonando {REPO_SERVIDORES} (branch {branch})...")
    ok, saida = _executar(["git", "clone", "--depth", "1", "--branch", branch,
                           REPO_SERVIDORES, str(destino)],
                          env=_ambiente_git(token))
    if not ok:
        print(f"  {saida.strip()}")
        return False, classificar_falha(saida)
    return True, ""


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
    ok, motivo = obter_codigo(destino, args.branch, token)

    # Só a recusa de credencial pede token; erro de rede, branch ou pasta não.
    if not ok and motivo == "credencial" and not token and interativo:
        print("  O repositório é privado; informe um token do GitHub.")
        token = input("  GitHub token (Enter = cancelar): ").strip()
        if token:
            ok, motivo = obter_codigo(destino, args.branch, token)

    if not ok:
        print(f"❌ {mensagem_falha(motivo, args.branch, destino)}")
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

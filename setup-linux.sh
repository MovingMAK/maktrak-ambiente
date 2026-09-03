#!/usr/bin/env bash
# MakTrak Setup - bootstrap (Linux/macOS)
#
# Garante o python3, baixa o maktrak_setup.py e o executa.
#
# Uso:
#   bash setup-linux.sh
#   # ou (baixe e execute, para o instalador ler suas respostas):
#   wget -q "<url deste arquivo>" -O /tmp/setup-linux.sh && bash /tmp/setup-linux.sh
set -euo pipefail

URL="https://raw.githubusercontent.com/MovingMAK/maktrak-ambiente/main/maktrak_setup.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# 1. Garante o python3 (apt no Debian/Ubuntu, brew no macOS)
if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 ausente. Instalando..."
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update && sudo apt-get install -y python3
    elif command -v brew >/dev/null 2>&1; then
        brew install python
    else
        echo "Sem gerenciador de pacotes conhecido. Instale o Python 3 e rode de novo." >&2
        exit 1
    fi
fi

# 2. Baixa o instalador (wget) e executa
# (wget ja vem por padrao no Debian/Ubuntu; curl costuma faltar.)
wget -q "$URL" -O "$TMP/maktrak_setup.py"

# Executa. Se o stdin nao for um terminal (ex.: veio por pipe), le as
# respostas direto de /dev/tty para o input() do Python nao falhar com EOF.
if [ -t 0 ]; then
    python3 "$TMP/maktrak_setup.py"
else
    echo "Sem terminal no stdin; tentando ler do /dev/tty..." >&2
    python3 "$TMP/maktrak_setup.py" < /dev/tty
fi

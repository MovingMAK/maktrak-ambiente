#!/usr/bin/env python3
"""MakTrak Setup - bootstrap + orquestrador multicomponente.

Uso:
    curl -fsSL "https://raw.githubusercontent.com/MovingMAK/maktrak-ambiente/main/maktrak_setup.py" \
        -o /tmp/maktrak_setup.py && python3 /tmp/maktrak_setup.py
"""
import sys
import platform
import subprocess
import shutil
import os
import time
import json
import base64
import zipfile
import importlib.util
import urllib.request
import base64
import ctypes
import threading
from pathlib import Path
from abc import ABC, abstractmethod
from urllib.parse import quote, unquote


# ============================================================================
# IDENTIFICACAO E VERSAO
# ============================================================================

SETUP_NAME = "MakTrak Setup"
SETUP_VERSION = "1.2.2"
SETUP_DATE = "2026-08-05"

# Cores ANSI (terminais modernos; desativadas quando a saida nao e TTY)
ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
ANSI_CYAN = "\033[36m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"
ANSI_MAGENTA = "\033[35m"
ANSI_BLUE = "\033[34m"


def _setup_windows_console():
    """Configura o console do Windows: ANSI (cores) + UTF-8 (emojis).

    Os emojis/simbolos do script sao exibidos corretamente em terminais com
    fonte compativel (Windows Terminal + Cascadia/Segoe UI Emoji). Em consoles
    legados (conhost com fonte raster) ainda aparecem como retangulos — nesse
    caso, use o Windows Terminal.
    """
    if platform.system() != "Windows":
        return
    try:
        ctypes.windll.kernel32.SetConsoleMode(
            ctypes.windll.kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        subprocess.run(["cmd", "/c", "chcp", "65001"],
                       capture_output=True, text=True)
    except Exception:
        pass


def _supports_color():
    """True se a saida aceita ANSI (TTY, ou Windows com VT ativo)."""
    if platform.system() == "Windows":
        return True
    try:
        return sys.stdout.isatty()
    except Exception:
        return True


def print_banner(name, version=SETUP_VERSION, accent=ANSI_CYAN, date=SETUP_DATE):
    """Imprime nome + versao + data do script, em destaque colorido quando possivel.

    Usado no inicio do orquestrador (main) e no init() de cada repo_setup.py.
    """
    _setup_windows_console()
    stamp = f"v{version} ({date})" if date else f"v{version}"
    if _supports_color():
        print(f"{ANSI_BOLD}{accent}== {name} {stamp} =={ANSI_RESET}")
    else:
        print(f"== {name} {stamp} ==")


# ============================================================================
# CONSTANTES
# ============================================================================

MOVINGMAK_REPOS_BASE = Path.home() / "repos" / "movingmak" / "maktrak"
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 3
SUDO_KEEPALIVE_INTERVAL = 120  # segundos entre renovacoes do ticket sudo

REPOSITORIES = {
    "ambiente":    "https://github.com/MovingMAK/maktrak-ambiente.git",
    "servidores":  "https://github.com/MovingMAK/maktrak-server.git",
    "hardware":    "https://github.com/MovingMAK/maktrak-hw.git",
    "firmware":    "https://github.com/MovingMAK/maktrak-fw.git",
    "app":         "https://github.com/MovingMAK/maktrak-app.git",
}

DEV_MODULES = {
    "ambiente":   ["vscode", "windows-terminal"],
    "mecanica":   ["freecad"],
    "eletronica": ["kicad"],
    "firmware":   ["vscode"],
    "servidor":   ["vscode", "flutter"],
    "app":        ["vscode", "flutter"],
}

DEV_REPOSITORIES = {
    "ambiente":   ["ambiente"],
    "mecanica":   ["hardware"],
    "eletronica": ["hardware"],
    "firmware":   ["firmware"],
    "servidor":   ["servidores"],
    "app":        ["app"],
}

PROD_MODULES = {
    "servidor-prod": ["vscode"],
    "ia": [],
}

# ============================================================================
# _PKG - CATALOGO DE SOFTWARE CONHECIDO
# ============================================================================
# Formato:
#   Linux: (gerenciador, extra, pacote)
#     gerenciador: "apt" | "snap"
#     extra:       "" | "classic" | "ppa:..."
#     pacote:      nome do pacote no gerenciador
#   Windows: "<winget-id>"  (string)

_PKG = {
    "chromium": {"linux": ('snap', '', 'chromium'), "windows": ""},
    "flutter": {"linux": ('snap', 'classic', 'flutter'), "windows": ''},
    "freecad": {"linux": ('snap', '', 'freecad'), "windows": 'FreeCAD.FreeCAD'},
    "git": {"linux": ('apt', '', 'git'), "windows": 'Git.Git'},
    "kicad": {"linux": ('apt', 'ppa:kicad/kicad-10.0-releases', 'kicad'), "windows": 'KiCad.KiCad'},
    "nginx": {"linux": ('apt', '', 'nginx'), "windows": 'NGINX.NGINX'},
    "postgresql": {"linux": ('apt', '', 'postgresql'), "windows": 'PostgreSQL.PostgreSQL'},
    "sqlite3":    {"linux": ('apt', '', 'sqlite3'), "windows": 'SQLite.SQLite'},
    "sublime-merge": {"linux": ('snap', 'classic', 'sublime-merge'), "windows": 'SublimeHQ.SublimeMerge'},
    "vscode": {"linux": ('snap', 'classic', 'code'), "windows": 'Microsoft.VisualStudioCode'},
    "windows-terminal": {"linux": (), "windows": 'Microsoft.WindowsTerminal'},
}

# ============================================================================
# COMANDO DE VERSAO POR APLICATIVO (para assert_executable)
# ============================================================================
# Formato: nome -> (binario, [args]) | None
#   None       => verificar apenas PRESENCA (apps GUI sem --version confiavel)
#   (bin, args)=> binario + argumentos que imprimem a versao e saem com rc=0
_VERSION_CMD = {
    "freecad": None,                         # GUI; --version trava sem display
    "kicad": ("kicad-cli", ["--version"]),   # CLI rapido, nao abre a GUI
    "nginx": ("nginx", ["-v"]),              # nginx so aceita -v / -V
}


# ═════════════════════════════════════════════════════════════════════════════
# CLASS BASE - SetupBase(ABC)
# ═════════════════════════════════════════════════════════════════════════════

def _windows_refresh_path():
    """Atualiza o PATH do processo atual no Windows (le Machine + User).

    Deve ser chamado apos comandos de instalacao (winget install/upgrade, etc.)
    para que executaveis recem-instalados fiquem visiveis ao processo atual.
    """
    if platform.system() != "Windows":
        return
    cmd = (
        "[System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' + "
        "[System.Environment]::GetEnvironmentVariable('Path','User')"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True,
        )
    except Exception as exc:
        print(f"  ⚠️ Falha ao ler PATH do Windows: {exc}")
        return
    if result.returncode == 0 and result.stdout.strip():
        os.environ["PATH"] = result.stdout.strip()


class SetupBase(ABC):
    """Classe base para scripts de setup derivados.

    A derivada herda desta classe e implementa as 4 fases:
        init(), install(), configure(), test()
    """

    def __init__(self):
        self.os_type = self._detect_os()
        self.managers = self._detect_package_managers()
        self.results = {}

    # ── Deteccao ──────────────────────────────────────────────────────────

    def _detect_os(self):
        """Detecta o SO: linux | windows | macos."""
        system = platform.system()
        if system == "Linux":
            return "linux"
        elif system == "Windows":
            return "windows"
        elif system == "Darwin":
            return "macos"
        else:
            print(f"Sistema nao suportado: {system}")
            sys.exit(1)

    def _detect_package_managers(self):
        """Detecta gerenciadores de pacote disponiveis."""
        managers = {}
        if self.os_type == "linux":
            if subprocess.run(["which", "snap"], capture_output=True).returncode == 0:
                managers["snap"] = True
            if subprocess.run(["which", "apt"], capture_output=True).returncode == 0:
                managers["apt"] = True
            if subprocess.run(["which", "pip"], capture_output=True).returncode == 0:
                managers["pip"] = True
        elif self.os_type == "windows":
            if subprocess.run(["where", "winget"], capture_output=True).returncode == 0:
                managers["winget"] = True
            if subprocess.run(["where", "pip"], capture_output=True).returncode == 0:
                managers["pip"] = True
        return managers

    # ── Execucao low-level (privado) ──────────────────────────────────────

    def _run(self, cmd, capture_output=False, text=True, input_data=None, cwd=None):
        """Executa um comando e retorna subprocess.CompletedProcess."""
        if cmd and cmd[0] == "sudo" and not self._sudo_ok():
            print("  ⚠️ Ticket sudo expirado. Execute 'sudo -v' no terminal para renovar.")
        # Windows: comandos como `code`/`flutter` sao .cmd/.bat. Resolver o
        # caminho completo faz o subprocess executa-los via cmd.exe; por nome
        # puro o CreateProcess procura so .exe e falha com WinError 2.
        if self.os_type == "windows" and cmd and "/" not in cmd[0] and "\\" not in cmd[0]:
            resolved = shutil.which(cmd[0])
            if resolved:
                cmd = [resolved] + list(cmd[1:])
        try:
            result = subprocess.run(cmd, capture_output=capture_output, text=text,
                                    input=input_data, cwd=cwd)
        except Exception as exc:
            print(f"  ❌ Falha ao executar: {' '.join(cmd)}")
            print(f"    {exc}")
            return subprocess.CompletedProcess(args=cmd, returncode=-1)
        # Windows: comandos de instalacao alteram o PATH do processo.
        # Renova o PATH para que executaveis recem-instalados (git, flutter,
        # code, pio, ...) fiquem visiveis aos comandos seguintes.
        if self.os_type == "windows" and self._cmd_may_change_path(cmd):
            self._refresh_path()
        return result

    # ── Sudo ─────────────────────────────────────────────────────────────

    def _sudo_ok(self):
        """True se o ticket sudo esta valido (checagem nao interativa)."""
        if self.os_type != "linux":
            return True
        try:
            return subprocess.run(["sudo", "-n", "true"],
                                  capture_output=True).returncode == 0
        except Exception as exc:
            print(f"  ⚠️ Falha ao checar sudo: {exc}")
            return False

    def sudo_ensure(self):
        """Garante ticket sudo valido. Se expirou, orienta o usuario a renovar.

        Preserva o espaco do usuario (nao roda como root); apenas mantem o
        carimbo sudo ativo. Retorna False se nao for possivel renovar.
        """
        if self._sudo_ok():
            return True
        print("  ⚠️ Privilegios sudo expirados.")
        print("  Execute 'sudo -v' em OUTRO terminal e tecle ENTER aqui.")
        try:
            input()
        except EOFError:
            print("  ❌ Sem terminal interativo. Rode o script num terminal com TTY.")
            return False
        if self._sudo_ok():
            print("  ✅ Sudo renovado.")
            return True
        print("  ❌ Sudo ainda invalido. Abortando fase.")
        return False

    # ── Instalacao de software ────────────────────────────────────────────

    def install_pkgs(self, *names):
        """Instala um ou mais pacotes do catalogo _PKG.

        Agrupa apt com PPAs (add-apt-repository + apt update unico),
        snap executa individualmente, winget executa individualmente.
        """
        if not names:
            return

        pkgs = []
        for name in names:
            entry = _PKG.get(name)
            if not entry:
                print(f"  ⚠️ Pacote desconhecido: {name} - adicione ao _PKG")
                continue
            pkgs.append((name, entry))

        if self.os_type == "linux":
            self._install_linux(pkgs)
        elif self.os_type == "windows":
            self._install_windows(pkgs)
        else:
            print(f"  ⚠️ SO nao suportado para install_pkgs: {self.os_type}")

    def _apt_installed(self):
        """Conjunto de nomes de pacotes apt ja instalados."""
        try:
            result = subprocess.run(["dpkg", "--get-selections"],
                                    capture_output=True, text=True, timeout=30)
        except Exception as exc:
            print(f"  ⚠️ Falha ao listar pacotes apt: {exc}")
            return set()
        installed = set()
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1] == "install":
                installed.add(parts[0])
        return installed

    def _snap_installed(self):
        """Conjunto de nomes de snaps ja instalados."""
        try:
            result = subprocess.run(["snap", "list"],
                                    capture_output=True, text=True, timeout=30)
        except Exception as exc:
            print(f"  ⚠️ Falha ao listar snaps: {exc}")
            return set()
        installed = set()
        for line in result.stdout.splitlines()[1:]:
            parts = line.split()
            if parts:
                installed.add(parts[0])
        return installed

    def _ppa_present(self, ppa):
        """True se o PPA ja esta configurado em /etc/apt/sources.list.d/."""
        try:
            files = os.listdir("/etc/apt/sources.list.d/")
        except Exception as exc:
            print(f"  ⚠️ Falha ao listar PPAs: {exc}")
            return False
        # ppa:kicad/kicad-10.0-releases -> arquivo contem kicad-10_0-releases
        ppa_name = ppa.split("/")[-1].replace(".", "_")
        return any(ppa_name in f for f in files)

    def _install_linux(self, pkgs):
        """Instala pacotes no Linux, agrupando apt e PULANDO os ja instalados.

        Evita re-instalar snaps presentes. Para apt, pula apenas quando o
        pacote ja esta instalado E o PPA necessario ja esta configurado;
        se o PPA for novo (ex.: nova serie do kicad), ele e adicionado e o
        apt install faz o upgrade.
        """
        apt_installed = self._apt_installed()
        snap_installed = self._snap_installed()
        apt_pkgs = []
        snap_pkgs = []
        ppas = []

        for name, entry in pkgs:
            info = entry.get("linux")
            if not info:
                print(f"  ⚠️ {name}: sem entrada Linux no _PKG")
                continue
            manager, extra, pkg_name = info

            if manager == "apt":
                ppa_present = True
                if extra and extra.startswith("ppa:"):
                    ppa_present = self._ppa_present(extra)
                    if not ppa_present:
                        ppas.append(extra)
                if pkg_name in apt_installed and ppa_present:
                    print(f"  ✅ {name} ja instalado (apt)")
                    continue
                apt_pkgs.append(pkg_name)
            elif manager == "snap":
                if pkg_name in snap_installed:
                    print(f"  ✅ {name} ja instalado (snap)")
                    continue
                snap_pkgs.append((pkg_name, extra))

        # PPAs
        for ppa in ppas:
            self._run(["sudo", "add-apt-repository", "--yes", ppa])

        # apt update (se houver PPAs novos)
        if ppas or apt_pkgs:
            self._run(["sudo", "apt", "update"])

        # apt install (batch)
        if apt_pkgs:
            cmd = ["sudo", "apt", "install", "-y"] + apt_pkgs
            self._run(cmd)

        # snap install (individual)
        for pkg_name, classic in snap_pkgs:
            cmd = ["sudo", "snap", "install", pkg_name]
            if classic:
                cmd.append("--classic")
            self._run(cmd)

    def _install_windows(self, pkgs):
        """Instala pacotes no Windows via winget."""
        for name, entry in pkgs:
            winget_id = entry.get("windows")
            if not winget_id:
                print(f"  ⚠️ {name}: sem instalacao winget no _PKG "
                      f"(pode usar metodo proprio)")
                continue
            self._run([
                "winget", "install", "--id", winget_id, "-e",
                "--accept-package-agreements", "--accept-source-agreements",
            ])
        self._refresh_path()

    @staticmethod
    def _cmd_may_change_path(cmd):
        """Heuristica: o comando pode ter alterado o PATH no Windows?"""
        if not cmd:
            return False
        tokens = {str(c).lower() for c in cmd}
        joined = " ".join(tokens)
        # winget (install/upgrade) e instaladores em geral atualizam o PATH
        return "winget" in joined or "install" in tokens or "upgrade" in tokens

    @staticmethod
    def _refresh_path():
        """Atualiza o PATH do processo atual no Windows (delega)."""
        _windows_refresh_path()

    # ── Teste de executavel ───────────────────────────────────────────────

    def _resolve_shortcut_target(self, lnk_path):
        """Resolve o destino de um atalho .lnk (via WScript.Shell)."""
        ps = ('$s=(New-Object -ComObject WScript.Shell).CreateShortcut('
              f'"{lnk_path}"); Write-Output $s.TargetPath')
        result = self._run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True)
        target = (result.stdout or "").strip()
        if target and os.path.isfile(target):
            return target
        return ""

    def _find_shortcut_binary(self, name):
        """Windows: localiza o executavel via atalho da area de trabalho.

        FreeCAD/KiCad criam atalho no Desktop mas nao entram no PATH.
        """
        if self.os_type != "windows":
            return ""
        desktop_dirs = [
            os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
            os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "Desktop"),
        ]
        for d in desktop_dirs:
            if not os.path.isdir(d):
                continue
            for fn in sorted(os.listdir(d)):
                if fn.lower().endswith(".lnk") and name.lower() in fn.lower():
                    target = self._resolve_shortcut_target(os.path.join(d, fn))
                    if target:
                        return target
        return ""

    def assert_executable(self, name, timeout=20):
        """Verifica se um executavel esta instalado (PRESENCA e obrigatoria).

        Para a maioria, tambem roda um comando de versao (--version por
        padrao, ou o mapeado em _VERSION_CMD). FALHA somente se o binario
        nao existir. Se a checagem de versao falhar/timeout, registra o
        executavel como OK com aviso (instalado nao e falha).
        No Windows, se nao estiver no PATH, resolve via atalho do Desktop.
        """
        binary = shutil.which(name)
        if not binary and self.os_type == "windows":
            binary = self._find_shortcut_binary(name)
            if binary:
                bindir = os.path.dirname(binary)
                os.environ["PATH"] = bindir + os.pathsep + os.environ["PATH"]
                print(f"  ✅ {name}: resolvido via atalho ({binary})")
        if not binary:
            self.results[name] = False
            return False

        info = _VERSION_CMD.get(name, (name, ["--version"]))
        ver_bin = None
        if info is not None:
            ver_bin_name, ver_args = info
            ver_bin = shutil.which(ver_bin_name) if ver_bin_name else binary
        if ver_bin:
            try:
                result = subprocess.run([ver_bin] + ver_args,
                                        capture_output=True, text=True,
                                        timeout=timeout)
                if result.returncode == 0:
                    version = (result.stdout or result.stderr).strip().splitlines()
                    if version:
                        self.results[f"{name}_version"] = version[0][:60]
            except subprocess.TimeoutExpired:
                print(f"  ⚠️ {name}: checagem de versao excedeu {timeout}s (ignorado)")
            except Exception as exc:
                print(f"  ⚠️ {name}: nao foi possivel obter versao: {exc}")
        self.results[name] = True
        return True

    # ── Sistema - servicos, configuracao, comandos ────────────────────────

    def service_enable(self, name):
        """Habilita um servico systemd."""
        self._run(["sudo", "systemctl", "enable", name])

    def service_restart(self, name):
        """Reinicia um servico systemd."""
        self._run(["sudo", "systemctl", "restart", name])

    def write_config(self, path, content, sudo=True):
        """Escreve um arquivo de configuracao (string ou dict JSON)."""
        if isinstance(content, dict):
            content = json.dumps(content, indent=4)
        path = Path(path)
        if sudo:
            self._run(["bash", "-c", f"cat <<'EOF' | sudo tee {path}\n{content}\nEOF"])
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

    def append_line(self, file_path, line):
        """Adiciona uma linha ao final de um arquivo."""
        self._run(["bash", "-c", f"echo '{line}' | sudo tee -a {file_path}"])

    def create_symlink(self, target, link):
        """Cria um symlink (sudo)."""
        self._run(["sudo", "ln", "-sf", target, link])

    # ── Flutter ───────────────────────────────────────────────────────────

    def _ensure_flutter_path(self):
        """Garante `flutter` no PATH (Windows: sem winget confiavel).

        Se `flutter` nao estiver no PATH, procura em locais comuns do SDK;
        se nao achar, baixa o SDK oficial e adiciona `bin` ao PATH.
        Retorna True se disponivel.
        """
        if shutil.which("flutter"):
            return True
        if self.os_type != "windows":
            return False
        candidates = [
            os.path.expandvars(r"%USERPROFILE%\flutter\bin"),
            os.path.expandvars(r"%LOCALAPPDATA%\Flutter\bin"),
            os.path.expandvars(r"%LOCALAPPDATA%\flutter\bin"),
            r"C:\flutter\bin",
        ]
        for d in candidates:
            if os.path.isfile(os.path.join(d, "flutter.bat")):
                os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
                print(f"  ✅ flutter encontrado em {d} (adicionado ao PATH)")
                return True
        print("  flutter nao instalado; baixando o SDK oficial...")
        return self._install_flutter_windows()

    def _install_flutter_windows(self):
        """Baixa o SDK oficial do Flutter no Windows (fallback ao winget).

        O pacote `Flutter.Flutter` do winget foi removido do repositorio; o
        metodo oficial e baixar o zip do SDK e adicionar `bin` ao PATH.
        Retorna True se o SDK ficou disponivel.
        """
        dest_root = Path(os.path.expandvars(r"%USERPROFILE%"))
        try:
            rel_url = ("https://storage.googleapis.com/flutter_infra_release/"
                       "releases/releases_windows.json")
            with urllib.request.urlopen(rel_url, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            stable = [h for h in data.get("releases", []) if h.get("channel") == "stable"]
            if not stable:
                print("  ❌ Flutter: sem release stable no indice")
                return False
            archive = stable[0]["archive"]
            zip_url = f"{data['base_url']}/{archive}"
            zip_path = dest_root / "flutter.zip"
            print(f"  Baixando Flutter SDK ({archive})...")
            urllib.request.urlretrieve(zip_url, zip_path)
            print("  Extraindo...")
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(dest_root)
            zip_path.unlink()
        except Exception as exc:
            print(f"  ❌ Falha ao baixar Flutter SDK: {exc}")
            return False
        bin_dir = dest_root / "flutter" / "bin"
        if bin_dir.is_dir():
            os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ["PATH"]
            print(f"  ✅ Flutter SDK instalado em {bin_dir.parent}")
            return True
        print("  ❌ Flutter SDK extraido, mas `bin` nao encontrado")
        return False

    def flutter_build(self, path, platform_target):
        """Compila um projeto Flutter para a plataforma alvo."""
        self._ensure_flutter_path()
        self._run(["flutter", "build", platform_target], cwd=str(path))

    def flutter_test(self, path):
        """Executa os testes de um projeto Flutter."""
        self._ensure_flutter_path()
        self._run(["flutter", "test"], cwd=str(path))

    def flutter_config(self, opts):
        """Aplica configuracoes no Flutter (ex: --enable-web)."""
        self._ensure_flutter_path()
        self._run(["flutter", "config"] + opts)

    # ── Android SDK ───────────────────────────────────────────────────────

    def setup_android(self):
        """Instala JDK + KVM + cmdline-tools + SDK + aceita licencas.

        A aceitacao de licencas acontece DEPOIS do SDK instalado e sem
        prompt interativo (arquivos gravados em <SDK>/licenses/).
        """
        self._android_install_jdk()
        self._android_setup_kvm()
        sdk_root = self._get_android_sdk_path()
        if not sdk_root:
            print("  XX Android SDK nao localizado")
            return False
        sdkmanager = self._android_ensure_sdkmanager(sdk_root)
        if not sdkmanager:
            return False
        self._android_install_sdk(sdkmanager)
        self._android_accept_licenses(sdk_root)
        return True

    def _cmdline_bin(self, sdk_root, name):
        """Caminho do executavel na bin do cmdline-tools (Windows: .bat)."""
        exe = name + (".bat" if self.os_type == "windows" else "")
        return os.path.join(sdk_root, "cmdline-tools", "latest", "bin", exe)

    def create_avd(self, name, device, target, description=""):
        """Cria um Android Virtual Device."""
        sdk_root = self._get_android_sdk_path()
        if not sdk_root:
            return
        avdmanager = self._cmdline_bin(sdk_root, "avdmanager")
        if not os.path.exists(avdmanager):
            print(f"  ⚠️ avdmanager nao encontrado, ignorando AVD {name}")
            return
        result = self._run([avdmanager, "list", "avd", "-c"], capture_output=True)
        if name in result.stdout:
            print(f"  ✅ AVD {name} ja existe")
            return
        if not self._avd_device_exists(avdmanager, device):
            print(f"  ⚠️ device '{device}' nao existe no catalogo do avdmanager; "
                  f"ignorando AVD {name}")
            return
        print(f"  Criando AVD {name} ({description})...")
        result = self._run([
            avdmanager, "create", "avd", "--force",
            "--device", device, "--name", name,
            "--package", f"system-images;{target};google_apis;x86_64",
            "--tag", "google_apis",
        ])
        if result.returncode == 0:
            print(f"  ✅ AVD {name} criado")
        else:
            print(f"  ❌ Falha ao criar AVD {name}")

    def _avd_device_exists(self, avdmanager, device):
        """Verifica se o device id existe no catalogo do avdmanager."""
        try:
            result = subprocess.run([avdmanager, "list", "device", "-c"],
                                    capture_output=True, text=True, timeout=30)
            for line in (result.stdout or "").splitlines():
                line = line.strip().strip('"')
                if line == device:
                    return True
        except Exception as exc:
            print(f"  ⚠️ Falha ao listar devices do AVD: {exc}")
        return False

    def _android_install_jdk(self):
        """Instala JDK para desenvolvimento Android."""
        print("  Instalando JDK...")
        if self.os_type == "linux":
            self._run(["sudo", "apt", "install", "-y", "default-jdk-headless"])
        elif self.os_type == "windows":
            self._run(["winget", "install", "--id", "Microsoft.OpenJDK.17",
                       "-e", "--accept-package-agreements"])

    def _android_setup_kvm(self):
        """Configura KVM para aceleracao de emulador (Linux)."""
        if self.os_type != "linux":
            return
        print("  Configurando KVM...")
        self._run(["sudo", "apt", "install", "-y",
                   "qemu-system-x86", "libvirt-daemon-system", "libvirt-clients",
                   "bridge-utils", "virt-manager"])
        self._run(["sudo", "adduser", os.environ.get("USER", ""), "kvm"])

    def _android_accept_licenses(self, sdk_root=None):
        """Aceita licencas do Android SDK sem prompt interativo.

        Escreve diretamente os arquivos de licenca em <SDK>/licenses/,
        com os hashes conhecidos da android-sdk-license. Nao depende de
        TTY nem de resposta do usuario.
        """
        sdk_root = sdk_root or self._get_android_sdk_path()
        if not sdk_root:
            print("  ⚠️ SDK nao localizado; pulando aceite de licencas")
            return
        licenses_dir = Path(sdk_root) / "licenses"
        licenses_dir.mkdir(parents=True, exist_ok=True)
        (licenses_dir / "android-sdk-license").write_text(
            "\n".join([
                "8933bad161af4178b1185d1a37fbf41ea5269c55",
                "d56f5187479451eabf01fb78af6dfcb131a6481e",
                "24333f8a63b6825ea9c5514f83c2829b004d1fee",
            ]) + "\n", encoding="utf-8")
        (licenses_dir / "android-sdk-preview-license").write_text(
            "84831b9409646a918e30573bab4c9c91346d8abd\n", encoding="utf-8")
        print("  ✅ Licencas Android aceitas (arquivos gravados no SDK)")

    def _android_ensure_sdkmanager(self, sdk_root):
        """Garante que sdkmanager esta instalado e executavel."""
        sdkmanager = self._cmdline_bin(sdk_root, "sdkmanager")
        if not os.path.exists(sdkmanager):
            print("  Instalando Android cmdline-tools...")
            self._install_cmdline_tools(sdk_root)
        if os.access(sdkmanager, os.X_OK):
            return sdkmanager
        if os.path.exists(sdkmanager):
            os.chmod(sdkmanager, 0o755)
            for fn in os.listdir(os.path.dirname(sdkmanager)):
                fp = os.path.join(os.path.dirname(sdkmanager), fn)
                if os.path.isfile(fp):
                    os.chmod(fp, 0o755)
            return sdkmanager
        return None

    def _android_install_sdk(self, sdkmanager):
        """Instala Android SDK: platform tools, build tools, system images."""
        print("  Instalando Android SDK...")
        self._run([sdkmanager, "--install",
                   "platform-tools",
                   "build-tools;36.0.0",
                   "platforms;android-36",
                   "platforms;android-34",
                   "system-images;android-36;google_apis;x86_64",
                   "system-images;android-34;google_apis;x86_64",
                   "emulator"])

    def _get_android_sdk_path(self):
        """Retorna o caminho do Android SDK."""
        try:
            self._ensure_flutter_path()
            result = self._run(["flutter", "doctor", "-v"], capture_output=True)
            for line in (result.stdout or "").splitlines():
                if "Android SDK" in line:
                    path = line.split("at")[-1].strip()
                    if os.path.isdir(path):
                        return path
        except Exception as exc:
            print(f"  ⚠️ Falha ao detectar Android SDK via flutter doctor: {exc}")
        candidates = [
            os.environ.get("ANDROID_HOME"),
            os.environ.get("ANDROID_SDK_ROOT"),
            str(Path.home() / "Android" / "Sdk"),
            str(Path.home() / "android" / "sdk"),
        ]
        for c in candidates:
            if c and os.path.isdir(c):
                return c
        return str(Path.home() / "Android" / "Sdk")

    def _install_cmdline_tools(self, sdk_root):
        """Download e extrai Android cmdline-tools."""
        tools_dir = Path(sdk_root) / "cmdline-tools"
        tools_dir.mkdir(parents=True, exist_ok=True)
        url = ("https://dl.google.com/android/repository/"
               "commandlinetools-linux-11076708_latest.zip")
        if platform.system() == "Windows":
            url = ("https://dl.google.com/android/repository/"
                   "commandlinetools-win-11076708_latest.zip")
        zip_path = tools_dir / "cmdline-tools.zip"
        print("  Downloading Android cmdline-tools...")
        try:
            urllib.request.urlretrieve(url, zip_path)
        except Exception as exc:
            print(f"  XX Download falhou: {exc}")
            return
        print("  Extraindo...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tools_dir)
        zip_path.unlink()
        (tools_dir / "latest").mkdir(exist_ok=True)
        for item in (tools_dir / "cmdline-tools").iterdir():
            if item.name != "latest":
                shutil.move(str(item), str(tools_dir / "latest" / item.name))
        (tools_dir / "cmdline-tools").rmdir()
        bin_dir = tools_dir / "latest" / "bin"
        if bin_dir.exists():
            for fn in bin_dir.iterdir():
                fn.chmod(fn.stat().st_mode | 0o111)

    # ── VS Code ───────────────────────────────────────────────────────────

    def vscode_install_extensions(self, exts):
        """Instala extensoes do VS Code."""
        _vscode_install_extensions(exts)

    def vscode_set_setting(self, key, value):
        """Ajusta uma configuracao do VS Code via settings.json."""
        _vscode_set_setting(key, value)

    # ── Dependencias de build (usadas pelas derivadas) ────────────────────

    def _venv_available(self):
        """True se o modulo venv esta disponivel (pacote python3-venv)."""
        try:
            return subprocess.run([sys.executable, "-c", "import venv"],
                                  capture_output=True).returncode == 0
        except Exception as exc:
            print(f"  ⚠️ Falha ao checar modulo venv: {exc}")
            return False

    def _platformio_bin_dir(self):
        """Diretorio dos executaveis do PlatformIO (venv do penv)."""
        base = Path.home() / ".platformio" / "penv"
        return base / ("Scripts" if self.os_type == "windows" else "bin")

    def _platformio_exe(self, bin_dir):
        """Caminho do executavel `pio` no diretorio do PlatformIO."""
        return bin_dir / ("pio.exe" if self.os_type == "windows" else "pio")

    def _platformio_add_to_path(self, bin_dir):
        """Adiciona o diretorio bin do PlatformIO ao PATH do processo."""
        if bin_dir.is_dir() and str(bin_dir) not in os.environ.get("PATH", ""):
            os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ["PATH"]
            print(f"  ✅ PlatformIO adicionado ao PATH ({bin_dir})")

    def ensure_platformio(self):
        """Instala PlatformIO Core se o CLI `pio` nao estiver disponivel.

        Retorna o caminho do binario `pio` (ou None em caso de falha).
        Garante o diretorio do penv no PATH (no Windows o instalador nao
        registra os executaveis).
        """
        bin_dir = self._platformio_bin_dir()
        pio = shutil.which("pio") or str(self._platformio_exe(bin_dir))
        if shutil.which("pio") or os.path.isfile(pio):
            self._platformio_add_to_path(bin_dir)
            print("  ✅ PlatformIO disponivel")
            return pio
        # O instalador do PlatformIO cria um venv; garante o python3-venv
        if not self._venv_available():
            print("  Instalando python3-venv (necessario para o PlatformIO)...")
            self._run(["sudo", "apt", "install", "-y", "python3-venv"])
        print("  Instalando PlatformIO Core...")
        url = ("https://raw.githubusercontent.com/platformio/"
               "platformio-core-installer/master/get-platformio.py")
        dest = Path.home() / ".platformio" / "get-platformio.py"
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            urllib.request.urlretrieve(url, dest)
            self._run([sys.executable, str(dest)])
        except Exception as exc:
            print(f"  ❌ Falha ao instalar PlatformIO: {exc}")
            return None
        # Apos instalar, garante o diretorio no PATH do processo
        self._platformio_add_to_path(bin_dir)
        pio = shutil.which("pio") or str(self._platformio_exe(bin_dir))
        if shutil.which("pio") or os.path.isfile(pio):
            return pio
        print("  ⚠️ PlatformIO instalado, mas `pio` nao encontrado no PATH")
        return None

    def platformio_prime(self, project_dir=None):
        """Pre-download das dependencias do projeto PlatformIO (prime).

        Roda `pio pkg install` no diretorio do projeto para baixar
        plataforma, frameworks e toolchains ANTES do build. Isso separa o
        download lento (fase de instalacao) da checagem de sucesso do
        build (fase de teste), que passa a usar o cache e responde rapido.
        Retorna True se os pacotes foram preparados.
        """
        bin_dir = self._platformio_bin_dir()
        self._platformio_add_to_path(bin_dir)
        pio = shutil.which("pio") or str(self._platformio_exe(bin_dir))
        if not os.path.isfile(pio) or not project_dir:
            return False
        print("  Preparando dependencias do PlatformIO (download antecipado)...")
        result = self._run([pio, "pkg", "install"], cwd=str(project_dir))
        return result.returncode == 0

    def ensure_pip_packages(self, *packages, venv_name="maktrak", python=None):
        """Instala pacotes Python num venv isolado.

        Evita PEP 668 (externally-managed) e a falta do pip3 do sistema.
        `python` permite usar um interpretador especifico (ex.: Python 3.12)
        quando o pacote nao suporta o Python do sistema (ex.: open-webui).
        Retorna o diretorio bin do venv (para localizar executaveis como
        `uvicorn`) ou None em caso de falha (pip nao instalou com sucesso).
        """
        if not packages:
            return None
        python = python or sys.executable
        venv_dir = Path.home() / ".venvs" / venv_name
        is_windows = platform.system() == "Windows"
        bin_dir = venv_dir / ("Scripts" if is_windows else "bin")
        venv_py = bin_dir / ("python.exe" if is_windows else "python")

        if not venv_py.exists():
            print(f"  Criando venv {venv_dir} (python: {python})...")
            result = self._run([python, "-m", "venv", str(venv_dir)])
            if result.returncode != 0 or not venv_py.exists():
                print("  Instalando python3-venv...")
                self._run(["sudo", "apt", "install", "-y", "python3-venv"])
                self._run([python, "-m", "venv", str(venv_dir)])
        if not venv_py.exists():
            print("  ❌ Falha ao criar venv. Verifique python3-venv.")
            return None

        print(f"  Instalando pacotes Python: {', '.join(packages)}...")
        self._run([str(venv_py), "-m", "pip", "install", "--upgrade", "pip"])
        result = self._run([str(venv_py), "-m", "pip", "install"] + list(packages))
        if result.returncode != 0:
            print(f"  ⚠️ Falha ao instalar pacotes no venv '{venv_name}': "
                  f"{', '.join(packages)} (pip rc={result.returncode})")
            return None
        return str(bin_dir)

    def install_flutter_linux_tools(self):
        """Instala as ferramentas exigidas pelo Flutter para build Linux."""
        if self.os_type == "linux":
            print("  Instalando ferramentas de build Linux (clang, cmake, ninja, GTK3)...")
            self._run(["sudo", "apt", "install", "-y",
                       "clang", "cmake", "ninja-build", "g++", "pkg-config",
                       "libgtk-3-dev"])
        elif self.os_type == "windows":
            print("  ⚠️ build Linux nao se aplica no Windows")

    # ── Fases abstratas - a derivada implementa as 4 ──────────────────────

    @abstractmethod
    def init(self):
        """Fase de inicializacao. Chamada antes de install()."""
        ...

    @abstractmethod
    def install(self):
        """Fase de instalacao. Instalar pacotes via self.install_pkgs()."""
        ...

    @abstractmethod
    def configure(self):
        """Fase de configuracao. Aplicar settings, servicos, etc."""
        ...

    @abstractmethod
    def test(self):
        """Fase de teste. Verificar instalacao via self.assert_executable()."""
        ...



# ============================================================================
# FUNCOES DO ORQUESTRADOR (standalone - nao estao na SetupBase)
# ============================================================================

def _windows_prepare_terminal():
    """Windows: garante o Windows Terminal instalado e como terminal padrao.

    Deve rodar ANTES da elevacao para que a janela admin (onde o setup roda)
    abra no WT, com suporte a emojis. Idempotente e best-effort (nao falha
    se o winget nao conseguir instalar).
    """
    if platform.system() != "Windows":
        return
    # 1. Instala o WT se ausente (per-user; nao exige admin)
    if not shutil.which("wt"):
        print("  Instalando Windows Terminal...")
        subprocess.run(
            ["winget", "install", "--id", "Microsoft.WindowsTerminal", "-e",
             "--accept-package-agreements", "--accept-source-agreements"],
            text=True)
        _windows_refresh_path()
    # 2. So define como padrao se estiver disponivel
    if shutil.which("wt"):
        wt_clsid = "{2EACA947-7F5F-4CFA-BA87-8F7FBEEFBE69}"
        for val in ("DelegationConsole", "DelegationTerminal"):
            subprocess.run(
                ["reg", "add", r"HKCU\Console\%Startup", "/v", val,
                 "/t", "REG_SZ", "/d", wt_clsid, "/f"],
                capture_output=True, text=True)
        print("  ✅ Windows Terminal instalado e definido como terminal padrao")
        # So consoles NOVOS abrem no WT; esta janela ja esta aberta.
        # Se nao estamos no WT nem como admin, re-abre em WT: a subsequente
        # elevacao (ShellExecuteW) usara o terminal padrao = WT.
        if not os.environ.get("WT_SESSION"):
            try:
                is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
            except Exception:
                is_admin = False
            if not is_admin:
                script_path = os.path.abspath(sys.argv[0])
                script_args = subprocess.list2cmdline(sys.argv[1:])
                cmd = f'"{sys.executable}" {script_path} {script_args}'
                subprocess.run(["wt", "-w", "new", "powershell", "-NoExit", "-Command", cmd])
                print("  🔄 Reabrindo no Windows Terminal...")
                sys.exit(0)
            print("  ⚠️ Esta janela continua no console atual. Abra uma NOVA "
                  "janela do Windows Terminal (ou rode de novo) p/ ver emojis.")
    else:
        print("  ⚠️ Windows Terminal indisponivel; a janela admin abrira "
              "no console padrao")


def _sys_require_admin():
    """Requer privilegios de administrador/sudo no inicio da execucao."""
    os_type = platform.system().lower()
    if os_type == "windows":
        try:
            is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception as exc:
            print(f"  ⚠️ Falha ao checar privilegios de admin: {exc}")
            is_admin = False
        if not is_admin:
            print("Privilegios de administrador necessarios. Solicitando elevacao...")
            script_path = os.path.abspath(sys.argv[0])
            script_and_args = subprocess.list2cmdline([script_path] + sys.argv[1:])
            command = f'& "{sys.executable}" {script_and_args}'
            params = subprocess.list2cmdline(["-NoExit", "-Command", command])
            rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe",
                                                      params, None, 1)
            if rc > 32:
                print("✅ Elevacao solicitada. Continuando na janela elevada.")
                sys.exit(0)
            print("❌ Nao foi possivel elevar privilegios.")
            sys.exit(1)
    elif os_type.startswith("linux"):
        result = subprocess.run(["sudo", "-v"], text=True)
        if result.returncode != 0:
            print("❌ Privilegios sudo necessarios.")
            sys.exit(1)
    print("✅ Privilegios OK")


def _sudo_keepalive():
    """Thread daemon que renova o ticket sudo a cada 2 minutos.

    Evita que o carimbo sudo expire durante operacoes longas (apt upgrade,
    builds Flutter, downloads), que foi a causa dos `sudo: timed out`.
    Usa `sudo -n -v`: nao pede senha, apenas renova com a credencial em
    cache. Preserva o espaco do usuario (o script continua como usuario).
    """
    if platform.system().lower() != "linux":
        return None

    def _refresh():
        while True:
            time.sleep(SUDO_KEEPALIVE_INTERVAL)
            try:
                subprocess.run(["sudo", "-n", "-v"], capture_output=True)
            except Exception as exc:
                print(f"  ⚠️ Keepalive sudo falhou: {exc}")

    thread = threading.Thread(target=_refresh, daemon=True, name="sudo-keepalive")
    thread.start()
    print(f"  ✅ Keepalive de sudo ativo "
          f"(renova a cada {SUDO_KEEPALIVE_INTERVAL}s durante a execucao)")
    return thread


def _sys_update_environment():
    """Atualiza listas de pacotes (apt update / winget upgrade)."""
    os_type = platform.system().lower()
    if os_type.startswith("linux"):
        if subprocess.run(["sudo", "-n", "true"], capture_output=True).returncode != 0:
            print("  ⚠️ Ticket sudo expirado. Execute 'sudo -v' no terminal antes de continuar.")
        print("  apt update...")
        subprocess.run(["sudo", "apt", "update"], text=True)
        print("  apt upgrade -y...")
        subprocess.run(["sudo", "apt", "upgrade", "-y"], text=True)
    elif os_type == "windows":
        print("  winget upgrade...")
        subprocess.run(["winget", "upgrade", "--all",
                        "--accept-package-agreements", "--accept-source-agreements"], text=True)
        _windows_refresh_path()


def _ui_select_mode():
    """Solicita ao usuario selecionar modo dev ou prod."""
    while True:
        c = input("\nModo? (1=dev, 2=prod): ").strip()
        if c == "1":
            return "dev"
        elif c == "2":
            return "prod"
        print("Invalido. Digite 1 ou 2.")


def _ui_select_components(items_dict, label):
    """Solicita ao usuario selecionar componentes."""
    categories = list(items_dict.keys())
    print(f"\n--- Selecionar componentes ({label}) ---")
    for i, cat in enumerate(categories, 1):
        print(f"{i}. {cat}")
    print(f"{len(categories) + 1}. todos")
    choice = input("Escolha (separados por virgula): ").strip()
    if choice == str(len(categories) + 1):
        return categories
    result = []
    for c in choice.split(","):
        try:
            idx = int(c.strip()) - 1
            if 0 <= idx < len(categories):
                result.append(categories[idx])
        except ValueError:
            print(f"  ⚠️ Entrada invalida ignorada: {c!r}")
    return result


def _ui_confirm(mode, components, branch="main"):
    """Exibe resumo e solicita confirmacao do usuario."""
    print(f"\n--- Resumo da Instalacao ---")
    print(f"Modo: {mode}")
    print(f"Branch: {branch}")
    print(f"Componentes: {', '.join(components)}")
    software = _get_software_for_components(components, mode)
    if software:
        print(f"Softwares: {', '.join(software)}")
    else:
        print("Softwares: nenhum")
    repos = _get_repositories_to_clone(mode, components)
    if repos:
        print(f"Repositorios: {', '.join(repos)}")
    confirm = input("\nProsseguir? (YES/no): ").strip().lower()
    return confirm in {"yes", ""}


def _ui_select_branch():
    """Solicita ao usuario uma branch especifica (default: main)."""
    branch = input("Branch dos repositorios? (Enter = main): ").strip()
    return branch if branch else "main"


def _ui_print_report(all_results):
    """Exibe relatorio detalhado por componente e por teste."""
    if not all_results:
        return
    print("\n--- Relatorio de Instalacao ---")
    overall_ok = True
    for component, results in sorted(all_results.items()):
        if not isinstance(results, dict):
            continue
        # Apenas resultados booleanos contam para o status do componente
        comp_ok = all(v for k, v in results.items() if isinstance(v, bool))
        comp_ok = comp_ok if any(isinstance(v, bool) for v in results.values()) else True
        icon = "✅" if comp_ok else "❌"
        print(f"\n  {icon} {component}")
        for name, status in sorted(results.items()):
            if isinstance(status, bool):
                print(f"      {'✅' if status else '❌'} {name}: {'OK' if status else 'FALHA'}")
            else:
                print(f"      ℹ️ {name}: {status}")
        if not comp_ok:
            overall_ok = False
    if overall_ok:
        print("\n✅ Todos os modulos instalados com sucesso!")
    else:
        print("\n⚠️ Alguns modulos falharam. Revise os detalhes acima.")


def _vscode_install_extensions(exts):
    """Instala extensoes do VS Code (standalone)."""
    # Resolve o caminho completo do `code`: no Windows ele e `code.cmd`
    # (batch); por nome puro o CreateProcess procura so `code.exe` e falha.
    code_bin = shutil.which("code")
    if not code_bin:
        print("  ⚠️ `code` nao encontrado; pulando instalacao de extensoes")
        return
    for ext in exts:
        result = subprocess.run(
            [code_bin, "--install-extension", ext],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(f"       ✅ Extensao: {ext}")
        else:
            print(f"       ⚠️ Falha na extensao: {ext}")


def _vscode_set_setting(key, value):
    """Ajusta uma configuracao do VS Code via settings.json."""
    settings_path = Path.home() / ".config" / "Code" / "User" / "settings.json"
    try:
        if settings_path.exists():
            settings = json.loads(settings_path.read_text())
        else:
            settings = {}
            settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings[key] = value
        settings_path.write_text(json.dumps(settings, indent=4))
    except Exception as exc:
        print(f"  ⚠️ Nao foi possivel atualizar settings.json: {exc}")


def _vscode_install_base():
    """Instala extensoes VS Code universais (todos os ambientes)."""
    _vscode_install_extensions([
        # Markdown
        "zaaack.markdown-editor",
        "shd101wyy.markdown-preview-enhanced",
        # Python
        "ms-python.python",
        "ms-toolsai.jupyter",
        # C/C++
        "ms-vscode.cpptools",
        "xaver.clang-format",
        # Git
        "eamodio.gitlens",
        "GitHub.vscode-pull-request-github",
        # Copilot
        "vizards.deepseek-v4-for-copilot",
        "github.copilot-chat",
        # TOML
        "tamasfe.even-better-toml",
    ])
    _vscode_set_setting("workbench.editor.limit.value", 20)


# ============================================================================
# REGISTRO EM sys.modules + CARREGADOR DINAMICO
# ============================================================================

def register_module(path):
    """Registra este modulo em sys.modules para import pelas derivadas."""
    name = "maktrak_setup"
    if name not in sys.modules:
        sys.modules[name] = sys.modules["__main__"]


def load_derived(repo_setup_path, component=None):
    """Carrega repo_setup.py e retorna a classe derivada de SetupBase.

    Se a derivada expõe SETUP_CLASSES (mapa componente -> classe), usa a
    classe correspondente ao componente. Isso evita que um repo_setup.py com
    varias classes (ex.: servidores: ServerSetup + IaSetup) pegue a classe
    errada por ordem alfabetica. Senao, retorna a primeira subclasse.
    """
    spec = importlib.util.spec_from_file_location(
        f"repo_{repo_setup_path.parent.name}", repo_setup_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cls_map = getattr(module, "SETUP_CLASSES", None)
    if component and isinstance(cls_map, dict) and component in cls_map:
        return cls_map[component]
    for attr_name in dir(module):
        obj = getattr(module, attr_name)
        if isinstance(obj, type) and issubclass(obj, SetupBase) and obj is not SetupBase:
            return obj
    raise ValueError(f"Nenhuma classe SetupBase encontrada em {repo_setup_path}")


# ============================================================================
# GIT - PRIVADO DO ORQUESTRADOR
# ============================================================================

def _git_validate():
    """Verifica se git esta disponivel."""
    try:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True)
    except FileNotFoundError:
        print("  ⚠️ git nao encontrado no PATH")
        return False
    return result.returncode == 0


def _git_username_from_store(store_path):
    """Extrai o username do .git-credentials, se possivel."""
    try:
        if store_path.exists():
            line = store_path.read_text(encoding="utf-8").strip().splitlines()[0]
            if line.startswith("https://") and "@" in line:
                userinfo = line[len("https://"):].split("@")[0]
                return unquote(userinfo.split(":", 1)[0])
    except Exception:
        pass
    return ""


def _git_ensure_identity(username=""):
    """Garante user.name/user.email do git (necessario p/ pull/merge/commit).

    Usa o username do GitHub (quando conhecido) para a identidade:
      user.name  = <username>
      user.email = <username>@users.noreply.github.com
    Senao, usa um default generico do setup. Nao sobrescreve identidade
    ja configurada. Grava em --global (configurado no sistema).
    """
    name = subprocess.run(["git", "config", "--global", "user.name"],
                          capture_output=True, text=True).stdout.strip()
    email = subprocess.run(["git", "config", "--global", "user.email"],
                           capture_output=True, text=True).stdout.strip()
    if not name:
        default_name = username or "MakTrak Setup"
        subprocess.run(["git", "config", "--global", "user.name", default_name],
                       capture_output=True, text=True)
        name = default_name
    if not email:
        base = (username or "maktrak").lower()
        default_email = f"{base}@users.noreply.github.com"
        subprocess.run(["git", "config", "--global", "user.email", default_email],
                       capture_output=True, text=True)
        email = default_email
    print(f"  ✅ Identidade git: {name} <{email}>")


def _git_setup_credentials():
    """Configura credenciais GitHub (token via store, env, ou prompt)."""
    store_path = Path.home() / ".git-credentials"

    # Identidade git derivada do username do GitHub quando possivel; sem
    # isso o pull/merge de repo existente falha em maquina nova.
    username = (os.environ.get("GITHUB_USER") or os.environ.get("GIT_USER")
                or _git_username_from_store(store_path) or "")
    _git_ensure_identity(username)

    # Garante o helper `store` (e especificamente para o GitHub) em TODOS os
    # caminhos. Sem isso, no Windows o Git Credential Manager (GCM) fica
    # ativo e abre splash interativo (navegador/codigo) durante o clone.
    subprocess.run(["git", "config", "--global", "credential.helper", "store"],
                   capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "--global",
         "credential.https://github.com.helper", "store"],
        capture_output=True, text=True)

    # Tenta ler credenciais salvas (valida formato github antes de usar)
    if store_path.exists():
        try:
            line = store_path.read_text(encoding="utf-8").strip().splitlines()[0]
            if line.startswith("https://") and "@github.com" in line:
                creds = line[len("https://"):].split("@")[0]
                if ":" in creds:
                    print("✅ Credenciais GitHub encontradas no store")
                    return
        except Exception as exc:
            print(f"  ⚠️ Nao foi possivel ler credenciais salvas: {exc}")

    # Environment variables
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    username = os.environ.get("GITHUB_USER") or os.environ.get("GIT_USER") or "git"
    if token:
        print("✅ Usando GITHUB_TOKEN do ambiente")
        _git_write_credentials(username, token, store_path)
        return

    # Prompt interativo
    print("\n--- Autenticacao GitHub ---")
    username = input("GitHub username: ").strip()
    token = input("GitHub personal access token: ").strip()
    if not username or not token:
        print("❌ Credenciais necessarias para repositorios privados")
        sys.exit(1)
    _git_write_credentials(username, token, store_path)


def _git_write_credentials(username, token, store_path):
    """Persiste credenciais no arquivo .git-credentials."""
    encoded_username = quote(username)
    encoded_token = quote(token)
    store_path.write_text(f"https://{encoded_username}:{encoded_token}@github.com\n",
                          encoding="utf-8")
    store_path.chmod(0o600)


def _git_auth_header():
    """Retorna o header HTTP 'Authorization: Basic ...' para o GitHub.

    Le a credencial do .git-credentials (escrita antes do clone) e a injeta
    diretamente no comando git via http.extraHeader. Isso dispensa o
    credential helper/GCM — resolvendo o 'could not read Username' no
    Windows quando o helper nao esta configurado. Retorna None sem credencial.
    """
    store_path = Path.home() / ".git-credentials"
    try:
        line = store_path.read_text(encoding="utf-8").strip().splitlines()[0]
        if line.startswith("https://") and "@github.com" in line:
            creds = line[len("https://"):].split("@")[0]
            user, _, token = creds.partition(":")
            if user and token:
                raw = f"{unquote(user)}:{unquote(token)}".encode("utf-8")
                return "Authorization: Basic " + base64.b64encode(raw).decode("ascii")
    except Exception:
        pass
    return None


def _git_clone_repos(mode, components, branch="main"):
    """Clona ou atualiza os repositorios dos componentes selecionados."""
    repos = _get_repositories_to_clone(mode, components)
    if not repos:
        return True
    print(f"\nClonando {len(repos)} repositorio(s) (branch: {branch})...")
    for repo_name in repos:
        repo_url = REPOSITORIES.get(repo_name)
        if not repo_url:
            print(f"❌ URL nao configurada para: {repo_name}")
            return False
        if not _git_clone_one(repo_name, repo_url, branch):
            return False
    return True


def _git_clone_one(repo_name, repo_url, branch="main"):
    """Clona ou atualiza um repositorio em uma branch especifica."""
    dest = MOVINGMAK_REPOS_BASE / repo_name
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"  Clonando {repo_name} ({branch})...")
        cmd = ["git", "clone", "--progress", "--branch", branch,
               repo_url, str(dest)]
        result = _git_run_with_retry(cmd, repo_name)
        if result.returncode == 0:
            print(f"  ✅ Clonado {repo_name} ({branch})")
            _git_register_sublime_merge(dest)
            return True
        print(f"  ❌ Falha ao clonar {repo_name}")
        return False
    print(f"  Repositorio ja existe: {dest}")
    # Troca para a branch desejada antes do pull
    subprocess.run(["git", "-C", str(dest), "checkout", branch],
                   capture_output=True, text=True)
    result = _git_run_with_retry(
        ["git", "-C", str(dest), "pull", "--force"], repo_name
    )
    if result.returncode == 0:
        print(f"  ✅ Atualizado {repo_name} ({branch})")
        _git_register_sublime_merge(dest)
        return True
    print(f"  ❌ Falha ao atualizar {repo_name}")
    return False


def _git_run_with_retry(args, repo_name):
    """Executa comando git com retry em caso de erro de autenticacao/rede."""
    # Impede prompts interativos: GCM (Windows) nao abre splash e o terminal
    # nao pede senha. A credencial deve vir do store (gravado antes do clone).
    env = dict(os.environ)
    env["GCM_INTERACTIVE"] = "never"
    env["GIT_TERMINAL_PROMPT"] = "0"
    # Injeta autenticacao via header HTTP quando ha credencial no store.
    # Dispensa o helper/GCM (as vezes nao configurado no Windows) e evita o
    # erro "could not read Username" no clone de repos novos.
    cmd = list(args)
    auth = _git_auth_header()
    if auth:
        cmd = [args[0], "-c", f"http.extraHeader={auth}"] + list(args[1:])
    for attempt in range(1, MAX_RETRIES + 1):
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if result.returncode == 0:
            return result
        is_auth = "403" in result.stderr or "Authentication failed" in result.stderr
        is_net = ("Could not resolve host" in result.stderr or
                  "Connection refused" in result.stderr or
                  "Connection timed out" in result.stderr)
        if attempt < MAX_RETRIES and (is_auth or is_net):
            delay = RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
            print(f"  ⚠️ Tentativa {attempt}/{MAX_RETRIES} - retentando em {delay}s...")
            time.sleep(delay)
        else:
            break
    # Falha definitiva: imprime o motivo real do git para ajudar no diagnostico
    err_lines = [l for l in (result.stderr or "").splitlines() if l.strip()]
    out_lines = [l for l in (result.stdout or "").splitlines() if l.strip()]
    if err_lines:
        print("  ⚠️ Detalhe do erro (git):")
        for line in err_lines[-8:]:
            print(f"    {line.strip()}")
    elif out_lines:
        print("  ⚠️ Saida (git):")
        for line in out_lines[-8:]:
            print(f"    {line.strip()}")
    return result


def _git_register_sublime_merge(repo_path):
    """Abre o repositorio no Sublime Merge (background)."""
    candidates = ["smerge", "sublime-merge"]
    if platform.system() == "Windows":
        candidates = ["smerge.exe", "sublime-merge.exe"]
    exe = None
    for c in candidates:
        exe = shutil.which(c)
        if exe:
            break
    if not exe:
        return
    try:
        subprocess.Popen([exe, "--background", str(repo_path)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as exc:
        print(f"  ⚠️ Nao foi possivel abrir Sublime Merge: {exc}")


def _get_repositories_to_clone(mode, components):
    """Retorna lista de chaves de repositorios a clonar."""
    if mode != "dev":
        return []
    repos = set()
    for component in components:
        repos.update(DEV_REPOSITORIES.get(component, []))
    return sorted(repos)


def _get_software_for_components(components, mode):
    """Retorna lista de software necessarios para os componentes."""
    source = DEV_MODULES if mode == "dev" else PROD_MODULES
    software = set()
    for c in components:
        software.update(source.get(c, []))
    return sorted(software)


# ============================================================================
# ORQUESTRADOR
# ============================================================================

def main():
    """MakTrak Setup - bootstrap + orquestrador."""
    # Configura console (UTF-8 + ANSI) antes de qualquer saida
    _setup_windows_console()
    if platform.system() == "Windows":
        # Instala/configura o Windows Terminal ANTES da elevacao, para que a
        # janela admin (onde o setup roda) abra no WT com suporte a emojis.
        _windows_prepare_terminal()
    print("=" * 60)
    print_banner(SETUP_NAME, SETUP_VERSION)
    print("=" * 60)

    # 0. Registra este modulo para as derivadas poderem importar
    register_module(Path(__file__))

    # 1. Detecta OS, privilegios, package managers
    _sys_require_admin()
    # Mantem o ticket sudo vivo durante toda a execucao (evita expiracao)
    _sudo_keepalive()

    # 2. Interacao com usuario (todas as perguntas primeiro)
    mode = _ui_select_mode()
    if mode == "dev":
        components = _ui_select_components(DEV_MODULES, "Desenvolvimento")
    else:
        components = _ui_select_components(PROD_MODULES, "Producao")

    repos = _get_repositories_to_clone(mode, components)
    branch = _ui_select_branch() if repos else "main"

    if not _ui_confirm(mode, components, branch):
        print("Instalacao cancelada.")
        sys.exit(0)

    # 3. Garante git (pre-requisito para o credential helper e o clone)
    if not _git_validate():
        print("Instalando git...")
        os_type = platform.system().lower()
        if os_type.startswith("linux"):
            subprocess.run(["sudo", "apt", "install", "-y", "git"], text=True)
        elif os_type == "windows":
            subprocess.run(["winget", "install", "--id", "Git.Git", "-e",
                           "--accept-package-agreements", "--accept-source-agreements"],
                          text=True)
            _windows_refresh_path()
        if not _git_validate():
            print("❌ Git e obrigatorio. Instale manualmente e tente novamente.")
            sys.exit(1)

    # 4. Credenciais GitHub (todos os dados do usuario obtidos primeiro)
    if repos:
        _git_setup_credentials()

    # 5. Atualizacao do sistema (apt upgrade / winget upgrade) — somente
    #    depois de obter todos os dados do usuario, em todos os sistemas
    _sys_update_environment()

    # 6. Clone dos repositorios
    if repos:
        if not _git_clone_repos(mode, components, branch):
            print("Falha ao clonar repositorios.")
            sys.exit(1)

    # 7. Executa as derivadas em ETAPAS (instalar -> extensoes -> configurar/testar).
    #    Assim o software (incluindo VS Code) e instalado ANTES das extensoes,
    #    e `code` ja esta disponivel quando as extensoes universais rodam.
    instances = []
    for component in components:
        repo_key = _get_repo_key(component)
        repo_path = MOVINGMAK_REPOS_BASE / repo_key / "repo_setup.py"
        if not repo_path.exists():
            print(f"\n❌ repo_setup.py nao encontrado em {repo_path}")
            sys.exit(1)
        cls = load_derived(repo_path, component)
        instance = cls()
        instances.append((component, instance))
        print(f"\n── {component} (instalacao) ──")
        # Garante ticket sudo valido antes de instalar
        instance.sudo_ensure()
        for phase in ["init", "install"]:
            try:
                getattr(instance, phase)()
            except Exception as exc:
                print(f"  ❌ Fase {phase} falhou: {exc}")
                instance.results[f"phase:{phase}"] = False

    # Extensoes VS Code universais (agora o VS Code ja esta instalado)
    print("\nInstalando extensoes VS Code universais...")
    _vscode_install_base()

    # Configuracao e testes de cada derivada
    all_results = {}
    for component, instance in instances:
        print(f"\n── {component} (configuracao/teste) ──")
        instance.sudo_ensure()
        for phase in ["configure", "test"]:
            try:
                getattr(instance, phase)()
            except Exception as exc:
                print(f"  ❌ Fase {phase} falhou: {exc}")
                instance.results[f"phase:{phase}"] = False
        all_results[component] = instance.results

    # 7. Relatorio consolidado
    _ui_print_report(all_results)

    # 8. Configuracao Xfce (Xubuntu) — removida: quebrava a barra de tarefas

    print("\n" + "=" * 60)
    print("✅ MakTrak Setup concluido!")
    print("=" * 60)


def _get_repo_key(component):
    """Mapeia componente para chave de repositorio."""
    dirs = DEV_REPOSITORIES.get(component)
    if dirs:
        return dirs[0]
    # Modo prod: servidor-prod e ia usam a config do repo servidores
    PROD_REPOSITORIES = {
        "servidor-prod": "servidores",
        "ia": "servidores",
    }
    return PROD_REPOSITORIES.get(component, component)


if __name__ == "__main__":
    main()

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
import zipfile
import importlib.util
import urllib.request
import ctypes
import threading
from pathlib import Path
from abc import ABC, abstractmethod
from urllib.parse import quote, unquote


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
    "ambiente":   ["vscode"],
    "mecanica":   ["freecad"],
    "eletronica": ["kicad"],
    "firmware":   ["arduino-cli", "vscode"],
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
    "arduino-cli": {"linux": ('snap', '', 'arduino-cli'), "windows": 'Arduino.ArduinoCLI'},
    "chromium": {"linux": ('snap', '', 'chromium'), "windows": ""},
    "flutter": {"linux": ('snap', 'classic', 'flutter'), "windows": 'Flutter.Flutter'},
    "freecad": {"linux": ('snap', '', 'freecad'), "windows": 'FreeCAD.FreeCAD'},
    "git": {"linux": ('apt', '', 'git'), "windows": 'Git.Git'},
    "kicad": {"linux": ('apt', 'ppa:kicad/kicad-10.0-releases', 'kicad'), "windows": 'KiCad.KiCad'},
    "nginx": {"linux": ('apt', '', 'nginx'), "windows": 'NGINX.NGINX'},
    "postgresql": {"linux": ('apt', '', 'postgresql'), "windows": 'PostgreSQL.PostgreSQL'},
    "sqlite3":    {"linux": ('apt', '', 'sqlite3'), "windows": 'SQLite.SQLite'},
    "sublime-merge": {"linux": ('snap', 'classic', 'sublime-merge'), "windows": 'SublimeHQ.SublimeMerge'},
    "vscode": {"linux": ('snap', 'classic', 'code'), "windows": 'Microsoft.VisualStudioCode'},
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
        try:
            return subprocess.run(cmd, capture_output=capture_output, text=text,
                                  input=input_data, cwd=cwd)
        except Exception as exc:
            print(f"  ❌ Falha ao executar: {' '.join(cmd)}")
            print(f"    {exc}")
            return subprocess.CompletedProcess(args=cmd, returncode=-1)

    # ── Sudo ─────────────────────────────────────────────────────────────

    def _sudo_ok(self):
        """True se o ticket sudo esta valido (checagem nao interativa)."""
        if self.os_type != "linux":
            return True
        try:
            return subprocess.run(["sudo", "-n", "true"],
                                  capture_output=True).returncode == 0
        except Exception:
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
        except Exception:
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
        except Exception:
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
        except Exception:
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
                print(f"  ⚠️ {name}: sem entrada Windows no _PKG")
                continue
            self._run([
                "winget", "install", "--id", winget_id, "-e",
                "--accept-package-agreements", "--accept-source-agreements",
            ])
        self._refresh_path()

    @staticmethod
    def _refresh_path():
        """Atualiza o PATH do processo atual no Windows."""
        if platform.system() != "Windows":
            return
        cmd = (
            "[System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' + "
            "[System.Environment]::GetEnvironmentVariable('Path','User')"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            os.environ["PATH"] = result.stdout.strip()

    # ── Teste de executavel ───────────────────────────────────────────────

    def assert_executable(self, name, timeout=20):
        """Verifica se um executavel esta instalado (PRESENCA e obrigatoria).

        Para a maioria, tambem roda um comando de versao (--version por
        padrao, ou o mapeado em _VERSION_CMD). FALHA somente se o binario
        nao existir. Se a checagem de versao falhar/timeout, registra o
        executavel como OK com aviso (instalado nao e falha).
        """
        binary = shutil.which(name)
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

    def flutter_build(self, path, platform_target):
        """Compila um projeto Flutter para a plataforma alvo."""
        self._run(["flutter", "build", platform_target], cwd=str(path))

    def flutter_test(self, path):
        """Executa os testes de um projeto Flutter."""
        self._run(["flutter", "test"], cwd=str(path))

    def flutter_config(self, opts):
        """Aplica configuracoes no Flutter (ex: --enable-web)."""
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

    def create_avd(self, name, device, target, description=""):
        """Cria um Android Virtual Device."""
        sdk_root = self._get_android_sdk_path()
        if not sdk_root:
            return
        avdmanager = os.path.join(sdk_root, "cmdline-tools", "latest", "bin", "avdmanager")
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
        except Exception:
            pass
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
        sdkmanager = os.path.join(sdk_root, "cmdline-tools", "latest", "bin", "sdkmanager")
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
            result = self._run(["flutter", "doctor", "-v"], capture_output=True)
            for line in result.stdout.splitlines():
                if "Android SDK" in line:
                    path = line.split("at")[-1].strip()
                    if os.path.isdir(path):
                        return path
        except Exception:
            pass
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

    def ensure_platformio(self):
        """Instala PlatformIO Core se o CLI `pio` nao estiver disponivel.

        Retorna o caminho do binario `pio` (ou None em caso de falha).
        """
        pio = shutil.which("pio") or str(Path.home() / ".platformio" / "penv" / "bin" / "pio")
        if shutil.which("pio") or os.path.isfile(pio):
            print("  ✅ PlatformIO disponivel")
            return pio
        print("  Instalando PlatformIO Core...")
        url = ("https://raw.githubusercontent.com/platformio/"
               "platformio-core-installer/master/get-platformio.py")
        dest = Path.home() / ".platformio" / "get-platformio.py"
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            urllib.request.urlretrieve(url, dest)
            self._run(["python3", str(dest)])
        except Exception as exc:
            print(f"  ❌ Falha ao instalar PlatformIO: {exc}")
            return None
        pio = shutil.which("pio") or str(Path.home() / ".platformio" / "penv" / "bin" / "pio")
        if os.path.isfile(pio):
            return pio
        print("  ⚠️ PlatformIO instalado, mas `pio` nao encontrado no PATH")
        return None

    def ensure_pip_packages(self, *packages, venv_name="maktrak"):
        """Instala pacotes Python num venv isolado.

        Evita PEP 668 (externally-managed) e a falta do pip3 do sistema.
        Retorna o diretorio bin do venv (para localizar executaveis como
        `uvicorn`) ou None em caso de falha.
        """
        if not packages:
            return None
        venv_dir = Path.home() / ".venvs" / venv_name
        is_windows = platform.system() == "Windows"
        bin_dir = venv_dir / ("Scripts" if is_windows else "bin")
        python = bin_dir / ("python.exe" if is_windows else "python")

        if not python.exists():
            print(f"  Criando venv {venv_dir}...")
            result = self._run([sys.executable, "-m", "venv", str(venv_dir)])
            if result.returncode != 0 or not python.exists():
                print("  Instalando python3-venv...")
                self._run(["sudo", "apt", "install", "-y", "python3-venv"])
                self._run([sys.executable, "-m", "venv", str(venv_dir)])
        if not python.exists():
            print("  ❌ Falha ao criar venv. Verifique python3-venv.")
            return None

        print(f"  Instalando pacotes Python: {', '.join(packages)}...")
        self._run([str(python), "-m", "pip", "install", "--upgrade", "pip"])
        self._run([str(python), "-m", "pip", "install"] + list(packages))
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

def _sys_require_admin():
    """Requer privilegios de administrador/sudo no inicio da execucao."""
    os_type = platform.system().lower()
    if os_type == "windows":
        try:
            is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
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
            except Exception:
                pass

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
        subprocess.run(["winget", "upgrade"], text=True)
        subprocess.run(["winget", "upgrade", "--all",
                        "--accept-package-agreements", "--accept-source-agreements"], text=True)


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
            pass
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
    for ext in exts:
        result = subprocess.run(
            ["code", "--install-extension", ext],
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


def load_derived(repo_setup_path):
    """Carrega repo_setup.py e retorna a classe derivada de SetupBase."""
    spec = importlib.util.spec_from_file_location(
        f"repo_{repo_setup_path.parent.name}", repo_setup_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
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
        return False
    return result.returncode == 0


def _git_setup_credentials():
    """Configura credenciais GitHub (token via store, env, ou prompt)."""
    store_path = Path.home() / ".git-credentials"

    # Tenta ler credenciais salvas
    if store_path.exists():
        try:
            line = store_path.read_text(encoding="utf-8").strip().splitlines()[0]
            if line.startswith("https://"):
                print("✅ Credenciais GitHub encontradas no store")
                return
        except Exception:
            pass

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

    # Configura git credential helper
    subprocess.run(["git", "config", "--global", "credential.helper", "store"],
                   capture_output=True, text=True)


def _git_write_credentials(username, token, store_path):
    """Persiste credenciais no arquivo .git-credentials."""
    encoded_username = quote(username)
    encoded_token = quote(token)
    store_path.write_text(f"https://{encoded_username}:{encoded_token}@github.com\n",
                          encoding="utf-8")
    store_path.chmod(0o600)


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
    for attempt in range(1, MAX_RETRIES + 1):
        result = subprocess.run(args, capture_output=True, text=True)
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
    except Exception:
        pass


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
    print("=" * 60)
    print("MakTrak Setup")
    print("=" * 60)

    # 0. Registra este modulo para as derivadas poderem importar
    register_module(Path(__file__))

    # 1. Detecta OS, privilegios, package managers
    _sys_require_admin()
    # Mantem o ticket sudo vivo durante toda a execucao (evita expiracao)
    _sudo_keepalive()

    # 2. Instala git se necessario (pre-requisito para clonar)
    if not _git_validate():
        print("Instalando git...")
        os_type = platform.system().lower()
        if os_type.startswith("linux"):
            subprocess.run(["sudo", "apt", "install", "-y", "git"], text=True)
        elif os_type == "windows":
            subprocess.run(["winget", "install", "--id", "Git.Git", "-e",
                           "--accept-package-agreements", "--accept-source-agreements"],
                          text=True)
        if not _git_validate():
            print("❌ Git e obrigatorio. Instale manualmente e tente novamente.")
            sys.exit(1)

    # 3. Interacao com usuario (todas as perguntas primeiro)
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

    # 4. Acoes (so depois de todas as perguntas)
    _sys_update_environment()

    # 5. Credenciais GitHub + clone
    if repos:
        _git_setup_credentials()
        if not _git_clone_repos(mode, components, branch):
            print("Falha ao clonar repositorios.")
            sys.exit(1)

    # 6. Extensoes VS Code universais
    print("\nInstalando extensoes VS Code universais...")
    _vscode_install_base()

    # 7. Executa cada derivada
    all_results = {}
    for component in components:
        repo_key = _get_repo_key(component)
        repo_path = MOVINGMAK_REPOS_BASE / repo_key / "repo_setup.py"
        if not repo_path.exists():
            print(f"\n❌ repo_setup.py nao encontrado em {repo_path}")
            sys.exit(1)
        cls = load_derived(repo_path)
        instance = cls()
        print(f"\n── {component} ──")
        # Garante ticket sudo valido antes das fases (evita falhas silenciosas)
        instance.sudo_ensure()
        for phase in ["init", "install", "configure", "test"]:
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
    return component


if __name__ == "__main__":
    main()

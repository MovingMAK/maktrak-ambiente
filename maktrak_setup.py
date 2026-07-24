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
from pathlib import Path
from abc import ABC, abstractmethod
from urllib.parse import quote, unquote


# ============================================================================
# CONSTANTES
# ============================================================================

MOVINGMAK_REPOS_BASE = Path.home() / "repos" / "movingmak" / "maktrak"
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 3

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
    "kicad": {"linux": ('apt', 'ppa:kicad/kicad-9.0-releases', 'kicad'), "windows": 'KiCad.KiCad'},
    "nginx": {"linux": ('apt', '', 'nginx'), "windows": 'NGINX.NGINX'},
    "postgresql": {"linux": ('apt', '', 'postgresql'), "windows": 'PostgreSQL.PostgreSQL'},
    "sublime-merge": {"linux": ('snap', 'classic', 'sublime-merge'), "windows": 'SublimeHQ.SublimeMerge'},
    "vscode": {"linux": ('snap', 'classic', 'code'), "windows": 'Microsoft.VisualStudioCode'},
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
        try:
            return subprocess.run(cmd, capture_output=capture_output, text=text,
                                  input=input_data, cwd=cwd)
        except Exception as exc:
            print(f"  XX Falha ao executar: {' '.join(cmd)}")
            print(f"    {exc}")
            return subprocess.CompletedProcess(args=cmd, returncode=-1)

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
                print(f"  \u26a0 Pacote desconhecido: {name} - adicione ao _PKG")
                continue
            pkgs.append((name, entry))

        if self.os_type == "linux":
            self._install_linux(pkgs)
        elif self.os_type == "windows":
            self._install_windows(pkgs)
        else:
            print(f"  \u26a0 SO nao suportado para install_pkgs: {self.os_type}")

    def _install_linux(self, pkgs):
        """Instala pacotes no Linux, agrupando apt."""
        apt_pkgs = []
        snap_pkgs = []
        ppas = []

        for name, entry in pkgs:
            info = entry.get("linux")
            if not info:
                print(f"  \u26a0 {name}: sem entrada Linux no _PKG")
                continue
            manager, extra, pkg_name = info

            if manager == "apt":
                if extra and extra.startswith("ppa:"):
                    ppas.append(extra)
                apt_pkgs.append(pkg_name)
            elif manager == "snap":
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
                print(f"  \u26a0 {name}: sem entrada Windows no _PKG")
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

    def assert_executable(self, name):
        """Verifica se um executavel esta instalado e funcional.

        Faz which + --version. Retorna bool e preenche self.results[name].
        """
        binary = shutil.which(name)
        if not binary:
            self.results[name] = False
            return False

        result = self._run([binary, "--version"], capture_output=True)
        ok = result.returncode == 0
        self.results[name] = ok
        return ok

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
        """Instala JDK + KVM + licencas + cmdline-tools + SDK."""
        self._android_install_jdk()
        self._android_setup_kvm()
        self._android_accept_licenses()
        sdk_root = self._get_android_sdk_path()
        if not sdk_root:
            print("  XX Android SDK nao localizado")
            return False
        sdkmanager = self._android_ensure_sdkmanager(sdk_root)
        if not sdkmanager:
            return False
        self._android_install_sdk(sdkmanager)
        return True

    def create_avd(self, name, device, target, description=""):
        """Cria um Android Virtual Device."""
        sdk_root = self._get_android_sdk_path()
        if not sdk_root:
            return
        avdmanager = os.path.join(sdk_root, "cmdline-tools", "latest", "bin", "avdmanager")
        if not os.path.exists(avdmanager):
            print(f"  \u26a0 avdmanager nao encontrado, ignorando AVD {name}")
            return
        result = self._run([avdmanager, "list", "avd", "-c"], capture_output=True)
        if name in result.stdout:
            print(f"  \u2713 AVD {name} ja existe")
            return
        print(f"  Criando AVD {name} ({description})...")
        self._run([
            avdmanager, "create", "avd", "--force",
            "--device", device, "--name", name,
            "--package", f"system-images;{target};google_apis;x86_64",
            "--tag", "google_apis",
        ])

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
                   "qemu-kvm", "libvirt-daemon-system", "libvirt-clients",
                   "bridge-utils", "virt-manager"])
        self._run(["sudo", "adduser", os.environ.get("USER", ""), "kvm"])

    def _android_accept_licenses(self):
        """Aceita licencas do Android SDK via Flutter."""
        print("  Aceitando licencas Android...")
        self._run(["flutter", "doctor", "--android-licenses"], input_data="y\n" * 10)

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
        """Instala Android platform tools e build tools."""
        print("  Instalando Android platform tools...")
        self._run([sdkmanager, "--install",
                   "platform-tools",
                   "build-tools;36.0.0",
                   "platforms;android-36",
                   "platforms;android-34",
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

    def install_extensions(self, exts):
        """Instala extensoes do VS Code."""
        for ext in exts:
            result = self._run(["code", "--install-extension", ext, "--force"],
                               capture_output=True)
            if result.returncode == 0:
                print(f"       \u2713 Extensao: {ext}")
            else:
                print(f"       \u26a0 Falha na extensao: {ext}")

    def set_setting(self, key, value):
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
            print(f"  \u26a0 Nao foi possivel atualizar settings.json: {exc}")

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

def require_admin():
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
                print("\u2713 Elevacao solicitada. Continuando na janela elevada.")
                sys.exit(0)
            print("\u2717 Nao foi possivel elevar privilegios.")
            sys.exit(1)
    elif os_type.startswith("linux"):
        result = subprocess.run(["sudo", "-v"], text=True)
        if result.returncode != 0:
            print("\u2717 Privilegios sudo necessarios.")
            sys.exit(1)
    print("\u2713 Privilegios OK")


def update_environment():
    """Atualiza listas de pacotes (apt update / winget upgrade)."""
    os_type = platform.system().lower()
    if os_type.startswith("linux"):
        print("  apt update...")
        subprocess.run(["sudo", "apt", "update"], text=True)
        print("  apt upgrade -y...")
        subprocess.run(["sudo", "apt", "upgrade", "-y"], text=True)
    elif os_type == "windows":
        print("  winget upgrade...")
        subprocess.run(["winget", "upgrade"], text=True)
        subprocess.run(["winget", "upgrade", "--all",
                        "--accept-package-agreements", "--accept-source-agreements"], text=True)


def select_mode():
    """Solicita ao usuario selecionar modo dev ou prod."""
    while True:
        c = input("\nModo? (1=dev, 2=prod): ").strip()
        if c == "1":
            return "dev"
        elif c == "2":
            return "prod"
        print("Invalido. Digite 1 ou 2.")


def select_components(items_dict, label):
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


def confirm(mode, components):
    """Exibe resumo e solicita confirmacao do usuario."""
    print(f"\n--- Resumo da Instalacao ---")
    print(f"Modo: {mode}")
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


def select_branch():
    """Solicita ao usuario uma branch especifica (default: main)."""
    branch = input("Branch dos repositorios? (Enter = main): ").strip()
    return branch if branch else "main"


def print_report(results):
    """Exibe relatorio formatado dos resultados."""
    if not results:
        return
    print("\n--- Relatorio de Instalacao ---")
    all_ok = True
    for name, status in sorted(results.items()):
        icon = "\u2713" if status else "\u2717"
        print(f"  {icon} {name}: {'OK' if status else 'FALHA'}")
        if not status:
            all_ok = False
    if all_ok:
        print("\n\u2713 Todos os modulos instalados com sucesso!")
    else:
        print("\n\u26a0 Alguns modulos falharam.")


# ============================================================================
# REGISTRO EM sys.modules + CARREGADOR DINAMICO
# ============================================================================

def register_module(path):
    """Registra maktrak_setup.py em sys.modules para import pelas derivadas."""
    name = "maktrak_setup"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)


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

def _validate_git():
    """Verifica se git esta disponivel."""
    try:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True)
    except FileNotFoundError:
        return False
    return result.returncode == 0


def _setup_credentials():
    """Configura credenciais GitHub (token via store, env, ou prompt)."""
    store_path = Path.home() / ".git-credentials"

    # Tenta ler credenciais salvas
    if store_path.exists():
        try:
            line = store_path.read_text(encoding="utf-8").strip().splitlines()[0]
            if line.startswith("https://"):
                print("\u2713 Credenciais GitHub encontradas no store")
                return
        except Exception:
            pass

    # Environment variables
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    username = os.environ.get("GITHUB_USER") or os.environ.get("GIT_USER") or "git"
    if token:
        print("\u2713 Usando GITHUB_TOKEN do ambiente")
        _write_git_credentials(username, token, store_path)
        return

    # Prompt interativo
    print("\n--- Autenticacao GitHub ---")
    username = input("GitHub username: ").strip()
    token = input("GitHub personal access token: ").strip()
    if not username or not token:
        print("\u2717 Credenciais necessarias para repositorios privados")
        sys.exit(1)
    _write_git_credentials(username, token, store_path)

    # Configura git credential helper
    subprocess.run(["git", "config", "--global", "credential.helper", "store"],
                   capture_output=True, text=True)


def _write_git_credentials(username, token, store_path):
    """Persiste credenciais no arquivo .git-credentials."""
    encoded_username = quote(username)
    encoded_token = quote(token)
    store_path.write_text(f"https://{encoded_username}:{encoded_token}@github.com\n",
                          encoding="utf-8")
    store_path.chmod(0o600)


def _clone_repos(mode, components, branch="main"):
    """Clona ou atualiza os repositorios dos componentes selecionados."""
    repos = _get_repositories_to_clone(mode, components)
    if not repos:
        return True
    print(f"\nClonando {len(repos)} repositorio(s) (branch: {branch})...")
    for repo_name in repos:
        repo_url = REPOSITORIES.get(repo_name)
        if not repo_url:
            print(f"\u2717 URL nao configurada para: {repo_name}")
            return False
        if not _clone_one(repo_name, repo_url, branch):
            return False
    return True


def _clone_one(repo_name, repo_url, branch="main"):
    """Clona ou atualiza um repositorio em uma branch especifica."""
    dest = MOVINGMAK_REPOS_BASE / repo_name
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"  Clonando {repo_name} ({branch})...")
        cmd = ["git", "clone", "--progress", "--branch", branch,
               repo_url, str(dest)]
        result = _run_git_with_retry(cmd, repo_name)
        if result.returncode == 0:
            print(f"  \u2713 Clonado {repo_name} ({branch})")
            _register_sublime_merge(dest)
            return True
        print(f"  \u2717 Falha ao clonar {repo_name}")
        return False
    print(f"  Repositorio ja existe: {dest}")
    # Troca para a branch desejada antes do pull
    subprocess.run(["git", "-C", str(dest), "checkout", branch],
                   capture_output=True, text=True)
    result = _run_git_with_retry(
        ["git", "-C", str(dest), "pull", "--force"], repo_name
    )
    if result.returncode == 0:
        print(f"  \u2713 Atualizado {repo_name} ({branch})")
        _register_sublime_merge(dest)
        return True
    print(f"  \u2717 Falha ao atualizar {repo_name}")
    return False


def _run_git_with_retry(args, repo_name):
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
            print(f"  \u26a0 Tentativa {attempt}/{MAX_RETRIES} - retentando em {delay}s...")
            time.sleep(delay)
        else:
            break
    return result


def _register_sublime_merge(repo_path):
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
# XFCE PANEL (Xubuntu)
# ============================================================================

def _configure_xfce_panel():
    """Configura o painel Xfce: barra inferior com 2 linhas."""
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
    if "xfce" not in desktop.lower():
        return
    print("\nConfigurando painel Xfce...")
    result = subprocess.run(
        ["xfconf-query", "-c", "xfce4-panel", "-p", "/panels"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return
    panels = result.stdout.strip().splitlines()
    if not panels:
        return
    panel_num = panels[0].strip()
    subprocess.run(["xfconf-query", "-c", "xfce4-panel", "-p",
                    f"/panels/{panel_num}/position", "-s", "p=6;x=0;y=0"],
                   capture_output=True)
    subprocess.run(["xfconf-query", "-c", "xfce4-panel", "-p",
                    f"/panels/{panel_num}/nrows", "-s", "2"],
                   capture_output=True)
    subprocess.run(["xfce4-panel", "-r"], capture_output=True)
    print("  \u2713 Painel configurado: barra inferior, 2 linhas")


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
    require_admin()

    # 2. Instala git se necessario (pre-requisito para clonar)
    if not _validate_git():
        print("Instalando git...")
        os_type = platform.system().lower()
        if os_type.startswith("linux"):
            subprocess.run(["sudo", "apt", "install", "-y", "git"], text=True)
        elif os_type == "windows":
            subprocess.run(["winget", "install", "--id", "Git.Git", "-e",
                           "--accept-package-agreements", "--accept-source-agreements"],
                          text=True)
        if not _validate_git():
            print("\u2717 Git e obrigatorio. Instale manualmente e tente novamente.")
            sys.exit(1)

    # 3. Atualiza ambiente
    update_environment()

    # 4. Interacao com usuario
    mode = select_mode()
    if mode == "dev":
        components = select_components(DEV_MODULES, "Desenvolvimento")
    else:
        components = select_components(PROD_MODULES, "Producao")

    if not confirm(mode, components):
        print("Instalacao cancelada.")
        sys.exit(0)

    # 5. Credenciais GitHub + clone
    repos = _get_repositories_to_clone(mode, components)
    if repos:
        branch = select_branch()
        _setup_credentials()
        if not _clone_repos(mode, components, branch):
            print("Falha ao clonar repositorios.")
            sys.exit(1)

    # 6. Executa cada derivada
    all_results = {}
    for component in components:
        repo_key = _get_repo_key(component)
        repo_path = MOVINGMAK_REPOS_BASE / repo_key / "repo_setup.py"
        if not repo_path.exists():
            print(f"\n── {component} ──")
            print("  \u26a0 repo_setup.py nao encontrado. Execute via bootstrap completo.")
            continue
        cls = load_derived(repo_path)
        instance = cls()
        print(f"\n── {component} ──")
        instance.init()
        instance.install()
        instance.configure()
        instance.test()
        all_results[component] = instance.results

    # 7. Relatorio consolidado
    print_report(all_results)

    # 8. Xfce panel (Xubuntu)
    _configure_xfce_panel()

    print("\n" + "=" * 60)
    print("\u2713 MakTrak Setup concluido!")
    print("=" * 60)


def _get_repo_key(component):
    """Mapeia componente para chave de repositorio."""
    for repo_key, comps in DEV_REPOSITORIES.items():
        if component in comps:
            return repo_key
    return component


if __name__ == "__main__":
    main()

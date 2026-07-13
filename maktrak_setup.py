#!/usr/bin/env python3
"""
MakTrak Setup Script
Multiplataforma installer for MakTrak development and production environments.
"""

import sys
import platform
import subprocess
import shutil
import os
import time
import ctypes
from pathlib import Path
from urllib.parse import quote, unquote
import urllib.request
import zipfile
import json


# ============================================================================
# CONFIGURATION: Repositories and Modules
# ============================================================================

# Base directory for all cloned repositories
MOVINGMAK_REPOS_BASE = Path.home() / "repos" / "movingmak" / "maktrak"

REPOSITORIES = {
    "ambiente": "https://github.com/MovingMAK/maktrak-ambiente.git",
    "servidores": "https://github.com/MovingMAK/maktrak-server.git",
    "hardware": "https://github.com/MovingMAK/maktrak-hw.git",
    "firmware": "https://github.com/MovingMAK/maktrak-fw.git",
    "app": "https://github.com/MovingMAK/maktrak-app.git",
    "aplicativos": "https://github.com/MovingMAK/maktrak-app.git",
}

# Modules organized by category for dev mode
DEV_MODULES = {
    "ambiente": ["vscode"],
    "mecanica": ["freecad"],
    "eletronica": ["kicad"],
    "firmware": ["arduino-cli", "vscode"],
    "servidor": ["vscode", "flutter"],
    "app": ["vscode", "flutter"],
}

# Repository mapping for dev categories
DEV_REPOSITORIES = {
    "ambiente": ["ambiente"],
    "mecanica": ["hardware"],
    "eletronica": ["hardware"],
    "firmware": ["firmware"],
    "servidor": ["servidores"],
    "app": ["app"],
}

# Modules for prod mode
PROD_MODULES = {
    "servidor-prod": ["vscode"],
    "ia": [],  # To be determined: vLLM, MLX, llama.cpp, Exo
}


# ============================================================================
# OS Detection and Package Managers
# ============================================================================

def detect_os():
    """Detect the operating system."""
    system = platform.system()
    if system == "Linux":
        return "linux"
    elif system == "Windows":
        return "windows"
    elif system == "Darwin":
        return "macos"
    else:
        print(f"Unsupported OS: {system}")
        sys.exit(1)


def detect_package_managers(os_type):
    """Detect available package managers."""
    managers = {}
    
    if os_type == "linux":
        # Check for snap
        if subprocess.run(["which", "snap"], capture_output=True).returncode == 0:
            managers["snap"] = True
        # Check for apt
        if subprocess.run(["which", "apt"], capture_output=True).returncode == 0:
            managers["apt"] = True
        # Check for pip
        if subprocess.run(["which", "pip"], capture_output=True).returncode == 0:
            managers["pip"] = True
    
    elif os_type == "windows":
        # Check for winget
        if subprocess.run(["where", "winget"], capture_output=True).returncode == 0:
            managers["winget"] = True
        # Check for pip
        if subprocess.run(["where", "pip"], capture_output=True).returncode == 0:
            managers["pip"] = True
    
    return managers


def validate_git():
    """Validate that git is available."""
    try:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True)
    except FileNotFoundError:
        print("✗ Git not found in PATH")
        if platform.system() == "Windows":
            print("  Install hint: winget install --id Git.Git -e")
        elif platform.system() == "Linux":
            print("  Install hint: sudo apt install -y git")
        return False

    if result.returncode == 0:
        print(f"✓ Git found: {result.stdout.strip()}")
        return True

    print("✗ Git command failed")
    if result.stderr:
        print(result.stderr.strip())
    return False


def relaunch_windows_as_admin():
    """Relaunch the current script with UAC elevation on Windows and keep shell open."""
    script_path = os.path.abspath(sys.argv[0])
    script_and_args = subprocess.list2cmdline([script_path, *sys.argv[1:]])
    command = f'& "{sys.executable}" {script_and_args}'
    params = subprocess.list2cmdline(["-NoExit", "-Command", command])
    rc = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        "powershell.exe",
        params,
        None,
        1,
    )
    return rc > 32


def ensure_admin_privileges(os_type):
    """Require administrator/sudo privileges at the beginning of execution."""
    if os_type == "windows":
        try:
            is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            is_admin = False
        if not is_admin:
            print("Administrator privileges are required. Requesting elevation...")
            if relaunch_windows_as_admin():
                print("✓ Elevation request sent. Continuing in elevated window.")
                return "relaunch"
            print("✗ Could not request elevation. Please run PowerShell as Administrator.")
            return False
        return True

    if os_type == "linux":
        result = subprocess.run(["sudo", "-v"], text=True)
        if result.returncode != 0:
            print("✗ Sudo privileges are required.")
            print("  Please run with a user that can use sudo and try again.")
            return False
        return True

    return True


def refresh_windows_path_from_system():
    """Refresh current process PATH from system/user values after installations."""
    if platform.system() != "Windows":
        return

    command = (
        "[System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' + "
        "[System.Environment]::GetEnvironmentVariable('Path','User')"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        os.environ["PATH"] = result.stdout.strip()
        print("✓ PATH refreshed in current process")


# Package installers: (name, os) -> install command list
_INSTALL_COMMANDS = {
    ("git", "windows"): ["winget", "install", "--id", "Git.Git", "-e",
                         "--accept-package-agreements", "--accept-source-agreements"],
    ("git", "linux"):   ["sudo", "apt", "install", "-y", "git"],
    ("sublime-merge", "windows"): ["winget", "install", "--id", "SublimeHQ.SublimeMerge", "-e",
                                    "--accept-package-agreements", "--accept-source-agreements"],
    ("sublime-merge", "linux"):   ["sudo", "snap", "install", "sublime-merge", "--classic"],
}


def _install_package(name, os_type):
    """Install a system package using the pre-configured command for the OS."""
    cmd = _INSTALL_COMMANDS.get((name, os_type))
    if not cmd:
        print(f"✗ Automatic {name} installation not implemented for OS: {os_type}")
        return False

    print(f"Attempting to install {name}...")
    try:
        result = subprocess.run(cmd, text=True)
    except Exception as exc:
        print(f"✗ Failed to run {name} installation command")
        print(str(exc))
        return False

    if result.returncode != 0:
        print(f"✗ Failed to install {name} automatically")
        return False

    if os_type == "windows":
        refresh_windows_path_from_system()

    print(f"✓ {name} installation command completed")
    return True


# ============================================================================
# User Interaction
# ============================================================================

def select_mode():
    """Prompt user to select dev or prod mode."""
    while True:
        c = input("\nMode? (1=dev, 2=prod): ").strip()
        if c == "1":
            return "dev"
        elif c == "2":
            return "prod"
        print("Invalid. Enter 1 or 2.")


def _select_components(items_dict, label):
    """Prompt user to select components from a dictionary of options."""
    categories = list(items_dict.keys())
    print(f"\n--- Select {label} Components ---")
    for i, cat in enumerate(categories, 1):
        print(f"{i}. {cat}")
    print(f"{len(categories) + 1}. todos (all categories)")

    choice = input("Enter your choice (comma-separated for multiple): ").strip()

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


def get_software_for_components(components, mode):
    """Return software packages needed for the selected components only."""
    source = DEV_MODULES if mode == "dev" else PROD_MODULES
    software = set()
    for c in components:
        software.update(source.get(c, []))
    return sorted(software)


def get_repositories_for_components(components):
    """Return the repositories required by the selected dev components."""
    repos = set()
    for component in components:
        repos.update(DEV_REPOSITORIES.get(component, []))
    return sorted(repos)


def get_credential_store_path():
    """Return the path of the Git credential store file."""
    return Path.home() / ".git-credentials"


def read_github_credentials_from_store(store_path=None):
    """Read GitHub credentials from the Git credential store file if present."""
    path = store_path or get_credential_store_path()
    if not path.exists():
        return None

    try:
        line = path.read_text(encoding="utf-8").strip().splitlines()[0]
    except (OSError, IndexError):
        return None

    if not line.startswith("https://"):
        return None

    try:
        auth_part = line.split("https://", 1)[1].split("@", 1)[0]
    except IndexError:
        return None

    if ":" not in auth_part:
        return None

    username, token = auth_part.split(":", 1)
    return unquote(username), unquote(token)


def write_github_credentials_to_store(username, token, store_path=None):
    """Persist GitHub credentials in a simple Git-compatible credential store file."""
    path = store_path or get_credential_store_path()
    encoded_username = quote(username)
    encoded_token = quote(token)
    path.write_text(f"https://{encoded_username}:{encoded_token}@github.com\n", encoding="utf-8")
    path.chmod(0o600)


def configure_git_credential_helper():
    """Configure Git to use the credential store for HTTPS authentication."""
    result = subprocess.run(
        ["git", "config", "--global", "credential.helper", "store"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("✓ Git credential helper configured for automatic HTTPS authentication")
        return True
    else:
        print("✗ Failed to configure Git credential helper")
        print(result.stderr)
        return False


def get_github_credentials(store_path=None):
    """Collect GitHub credentials for private repository access or reuse stored credentials.

    Priority:
    1. Saved credential store file (.git-credentials)
    2. GITHUB_TOKEN or GH_TOKEN environment variable
    3. Interactive prompt
    """
    # Priority 1: check credential store
    existing = read_github_credentials_from_store(store_path)
    if existing:
        print("✓ Reusing saved GitHub credentials from the local credential store")
        return existing

    # Priority 2: check environment variables
    env_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    env_username = os.environ.get("GITHUB_USER") or os.environ.get("GIT_USER") or "git"
    if env_token:
        print("✓ Using GitHub token from environment variable")
        write_github_credentials_to_store(env_username, env_token, store_path)
        return env_username, env_token

    # Priority 3: interactive prompt
    print("\n--- GitHub Authentication ---")
    print("  Tip: Set GITHUB_TOKEN or GH_TOKEN environment variable to skip this prompt.")
    username = input("GitHub username: ").strip()
    token = input("GitHub personal access token (hidden): ").strip()
    if not username or not token:
        print("✗ GitHub username and token are required for private repository access")
        return None

    write_github_credentials_to_store(username, token, store_path)
    return username, token


def confirm_actions(mode, components, os_type, managers):
    """Show user a summary of planned actions and request confirmation."""
    print("\n--- Installation Summary ---")
    print(f"Mode: {mode}")
    print(f"OS: {os_type}")
    print(f"Package managers available: {', '.join(managers.keys())}")
    print("Update OS packages: yes")
    print("Components to install:")
    for component in components:
        print(f"  - {component}")
    software = get_software_for_components(components, mode)
    print("Software to install:")
    if software:
        for item in software:
            print(f"  - {item}")
    else:
        print("  - none")

    # Extensões do VS Code
    if "vscode" in software:
        vscode_exts = _get_vscode_extensions(components)
        if vscode_exts:
            print("VS Code extensions to install:")
            for ext in vscode_exts:
                print(f"  - {ext}")
    
    repos = get_repositories_to_clone(mode, components)
    if repos:
        print(f"Repositories to clone (into {MOVINGMAK_REPOS_BASE}):")
        for repo in repos:
            repo_url = REPOSITORIES.get(repo, "")
            if repo_url:
                print(f"  - {repo}: {repo_url}")
            else:
                print(f"  - {repo}")
    else:
        print("No repositories to clone for the selected configuration.")
    
    confirm = input("\nProceed with these actions? (YES/no): ").strip().lower()
    return confirm in {"yes", ""}


def get_clone_destination(repo_name):
    """Return the standard clone destination path for a repo.

    Linux:   ~/repos/movingmak/maktrak/<repo-name>
    Windows: %USERPROFILE%\\repos\\movingmak\\maktrak\\<repo-name>
    """
    return MOVINGMAK_REPOS_BASE / repo_name


def find_sublime_merge_executable():
    """Return the Sublime Merge executable name or path if installed."""
    candidates = ["smerge", "sublime-merge"]
    if platform.system() == "Windows":
        candidates = [
            "smerge.exe",
            "sublime-merge.exe",
            "smerge",
            "sublime-merge",
            r"C:\Program Files\Sublime Merge\smerge.exe",
            r"C:\Program Files (x86)\Sublime Merge\smerge.exe",
        ]
    found = None
    for candidate in candidates:
        if os.path.isabs(candidate) and os.path.exists(candidate):
            found = candidate
            break
        found = shutil.which(candidate)
        if found:
            break
    if found:
        print(f"✓ Sublime Merge detected at: {found}")
        return found
    print("⚠ Sublime Merge executable not found in PATH or default locations")
    return None


def register_repo_with_sublime_merge(repo_path):
    """Open a repository in Sublime Merge (background) after cloning, so it appears in the sidebar."""
    exe = find_sublime_merge_executable()
    if not exe:
        return

    try:
        print(f"  Opening {repo_path.name} in Sublime Merge (background)...")
        subprocess.Popen(
            [exe, "--background", str(repo_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"  ✓ {repo_path.name} registered in Sublime Merge")
    except Exception:
        print(f"  ⚠ Could not open {repo_path.name} in Sublime Merge (repo is cloned locally)")


MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 3


def _run_git_with_retry(args, repo_name, operation_label):
    """Run a git command with exponential backoff retry."""
    for attempt in range(1, MAX_RETRIES + 1):
        result = subprocess.run(args, capture_output=True, text=True)
        if result.returncode == 0:
            return result

        is_auth_error = "403" in result.stderr or "Authentication failed" in result.stderr
        is_network_error = (
            "Could not resolve host" in result.stderr
            or "Connection refused" in result.stderr
            or "Connection timed out" in result.stderr
        )

        if attempt < MAX_RETRIES and (is_auth_error or is_network_error):
            delay = RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
            print(f"  ⚠ {operation_label} failed (attempt {attempt}/{MAX_RETRIES})"
                  f" — retrying in {delay}s...")
            if is_auth_error:
                print(f"    Possible authentication issue. Check your GitHub token.")
            time.sleep(delay)
        else:
            break

    return result


def clone_repository(repo_name, repo_url):
    """Clone or update a repository at the standard destination with retry support."""
    dest = get_clone_destination(repo_name)

    # Fresh clone
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"Cloning {repo_name} into {dest}...")
        result = _run_git_with_retry(
            ["git", "clone", "--progress", repo_url, str(dest)],
            repo_name, f"git clone {repo_name}",
        )
        if result.returncode == 0:
            print(f"✓ Cloned {repo_name}")
            register_repo_with_sublime_merge(dest)
            return True
        print(f"✗ Failed to clone {repo_name}")
        if result.stderr:
            print(f"  {result.stderr.strip()}")
        if dest.exists() and not (dest / ".git").exists():
            try:
                dest.rmdir()
            except OSError:
                pass
        return False

    # Already exists
    print(f"Repository already exists: {dest}")
    if not (dest / ".git").exists():
        print(f"✗ {dest} exists but is not a git repository")
        return False

    print(f"Pulling latest changes in {repo_name}...")
    result = _run_git_with_retry(
        ["git", "-C", str(dest), "pull", "--force"],
        repo_name, f"git pull {repo_name}",
    )
    if result.returncode == 0:
        print(f"✓ Updated {repo_name}")
        register_repo_with_sublime_merge(dest)
        return True
    print(f"✗ Failed to update {repo_name}")
    if result.stderr:
        print(f"  {result.stderr.strip()}")
    return False


def get_repositories_to_clone(mode, components):
    """Return the list of repository keys to clone based on mode and components."""
    if mode == "dev":
        return get_repositories_for_components(components)
    # Prod mode does not clone repositories
    return []


def clone_repositories(mode, components):
    """Clone repositories required for the selected mode and components."""
    repos = get_repositories_to_clone(mode, components)
    if not repos:
        print("  No repositories to clone for the selected configuration.")
        return True

    print(f"\nDownloading {len(repos)} repositories...")
    for repo in repos:
        repo_url = REPOSITORIES.get(repo)
        if not repo_url:
            print(f"✗ No URL configured for repository: {repo}")
            return False
        if not clone_repository(repo, repo_url):
            return False
    return True


# ============================================================================
# Software Installation
# ============================================================================

# Installers: maps software name -> (verify_cmd, linux_install_cmd, windows_install_cmd)
# verify_cmd: list of args; returns 0 if already installed
# install_cmd: list of args to install
SOFTWARE_INSTALLERS = {
    "vscode": {
        "verify": ["code", "--version"],
        "linux": ["sudo", "snap", "install", "code", "--classic"],
        "windows": ["winget", "install", "--id", "Microsoft.VisualStudioCode",
                     "-e", "--accept-package-agreements", "--accept-source-agreements"],
    },
    "flutter": {
        "verify": ["flutter", "--version"],
        "linux": ["sudo", "snap", "install", "flutter", "--classic"],
        "windows": ["winget", "install", "--id", "Flutter.Flutter",
                     "-e", "--accept-package-agreements", "--accept-source-agreements"],
    },
    "arduino-cli": {
        "verify": ["arduino-cli", "version"],
        "linux": ["sudo", "snap", "install", "arduino-cli"],
        "windows": ["winget", "install", "--id", "Arduino.ArduinoCLI",
                     "-e", "--accept-package-agreements", "--accept-source-agreements"],
    },
    "freecad": {
        "verify": ["freecad", "--version"],
        "linux": ["sudo", "snap", "install", "freecad"],
        "windows": ["winget", "install", "--id", "FreeCAD.FreeCAD",
                     "-e", "--accept-package-agreements", "--accept-source-agreements"],
    },
    "kicad": {
        "verify": None,  # checked via shutil.which to avoid launching GUI
        "linux": ["bash", "-c",
                  "sudo apt install -y software-properties-common && "
                  "sudo add-apt-repository --yes ppa:kicad/kicad-9.0-releases && "
                  "sudo apt update && sudo apt install -y kicad"],
        "windows": ["winget", "install", "--id", "KiCad.KiCad",
                     "-e", "--accept-package-agreements", "--accept-source-agreements"],
    },
}


def is_software_installed(software_name):
    """Check if a software is already installed using its verify command."""
    entry = SOFTWARE_INSTALLERS.get(software_name)
    if not entry:
        return None  # unknown software

    cmd = entry.get("verify")
    if cmd is None:
        # No safe CLI check — fall back to checking if binary exists in PATH
        return shutil.which(software_name) is not None

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def install_single_software(software_name, os_type):
    """Install a single software package using the appropriate command for the OS."""
    entry = SOFTWARE_INSTALLERS.get(software_name)
    if not entry:
        print(f"  ⚠ Unknown software: {software_name}")
        return False

    print(f"  ── {software_name} ──")

    installed = is_software_installed(software_name)
    if installed is None:
        print(f"       No verifier available, attempting install...")
    elif installed:
        print(f"       ✓ Already installed")
        return True

    if os_type == "linux":
        cmd = entry.get("linux")
    elif os_type == "windows":
        cmd = entry.get("windows")
    else:
        print(f"       ✗ No installer for {os_type}")
        return False

    if not cmd:
        print(f"       ✗ No installer configured")
        return False

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"       ✗ Failed")
        if result.stderr:
            for line in result.stderr.strip().splitlines()[:5]:
                print(f"         {line}")
        return False

    if os_type == "windows":
        refresh_windows_path_from_system()

    print(f"       ✓ Installed")
    return True


def _get_vscode_extensions(components):
    """Return the list of VS Code extension IDs based on selected components."""
    exts = [
        "GitHub.vscode-pull-request-github",
        "yzhang.markdown-all-in-one",
        "zaaack.markdown-editor",
        "ms-python.python",
    ]
    if "app" in components or "servidor" in components:
        exts.extend(["dart-code.dart-code", "dart-code.flutter"])
    if "firmware" in components:
        exts.append("pioarduino.pioarduino-ide")
    return exts


def setup_vscode(components):
    """Configure VS Code: install extensions per component and adjust settings."""
    print("  Configuring VS Code...")
    extensions = _get_vscode_extensions(components)

    for ext in extensions:
        result = subprocess.run(
            ["code", "--install-extension", ext, "--force"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(f"       ✓ Extension installed: {ext}")
        else:
            print(f"       ⚠ Extension failed: {ext}")

    # Increase "Open Recent" list to 20 items
    settings_path = Path.home() / ".config" / "Code" / "User" / "settings.json"
    try:
        if settings_path.exists():
            settings = json.loads(settings_path.read_text())
        else:
            settings = {}
            settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings["workbench.editor.limit.value"] = 20
        settings_path.write_text(json.dumps(settings, indent=4))
        print("       ✓ Open Recent increased to 20")
    except Exception:
        print("       ⚠ Could not update settings.json")


def setup_flutter_platforms(os_type):
    """Configure Flutter for all target platforms (web, linux/windows, android)."""
    print("  Configuring Flutter platforms...")

    # Enable web platform
    subprocess.run(["flutter", "config", "--enable-web"], capture_output=True, text=True)

    # Enable desktop platform
    if platform.system() == "Linux":
        subprocess.run(["flutter", "config", "--enable-linux-desktop"], capture_output=True, text=True)
        # Install mesa-utils for eglinfo driver info
        subprocess.run(["sudo", "apt", "install", "-y", "mesa-utils"], text=True,
                       capture_output=True)
    elif platform.system() == "Windows":
        subprocess.run(["flutter", "config", "--enable-windows-desktop"], capture_output=True, text=True)

    # Install Chromium so flutter devices shows web device
    if os_type == "linux":
        has_browser = (
            shutil.which("chromium") or
            shutil.which("chromium-browser") or
            shutil.which("google-chrome")
        )
        if not has_browser:
            print("  Installing Chromium for Flutter web...")
            subprocess.run(["sudo", "snap", "install", "chromium"], text=True)

        # Flutter expects google-chrome; snap installs chromium at /snap/bin/chromium
        if not shutil.which("google-chrome") and shutil.which("chromium"):
            print("  Creating google-chrome symlink for Flutter...")
            subprocess.run(["sudo", "ln", "-sf", "/snap/bin/chromium",
                            "/usr/local/bin/google-chrome"], text=True)

    print("  Pre-caching Flutter artifacts for all platforms...")
    result = subprocess.run(["flutter", "precache"], text=True)
    if result.returncode == 0:
        print("  ✓ Flutter artifacts cached")
    else:
        print("  ⚠ Flutter precache had warnings, continuing...")


def _android_install_jdk():
    """Install JDK for Android development."""
    print("  Installing JDK for Android development...")
    if platform.system() == "Linux":
        subprocess.run(["sudo", "apt", "install", "-y", "default-jdk-headless"], text=True)
    elif platform.system() == "Windows":
        subprocess.run(["winget", "install", "--id", "Microsoft.OpenJDK.17",
                         "-e", "--accept-package-agreements"], text=True)


def _android_setup_kvm():
    """Set up KVM for Android emulator acceleration on Linux."""
    if platform.system() != "Linux":
        return
    print("  Setting up KVM for Android emulator acceleration...")
    subprocess.run(["sudo", "apt", "install", "-y",
                    "qemu-kvm", "libvirt-daemon-system", "libvirt-clients",
                    "bridge-utils", "virt-manager"], text=True)
    subprocess.run(["sudo", "adduser", os.environ.get("USER", ""), "kvm"],
                   capture_output=True, text=True)
    if os.path.exists("/dev/kvm"):
        print("  ✓ KVM available")
    else:
        print("  ⚠ /dev/kvm not found — emulators will run without acceleration (slow)")


def _android_accept_licenses():
    """Accept Android SDK licenses via Flutter."""
    print("  Accepting Android SDK licenses...")
    result = subprocess.run(["flutter", "doctor", "--android-licenses"],
                            input="y\n" * 10, text=True, capture_output=True)
    if result.returncode == 0:
        print("  ✓ Android licenses accepted")
    else:
        print("  ⚠ Android license acceptance had issues, continuing...")


def _android_ensure_sdkmanager(sdk_root):
    """Ensure sdkmanager is installed and executable."""
    sdkmanager = os.path.join(sdk_root, "cmdline-tools", "latest", "bin", "sdkmanager")
    if not os.path.exists(sdkmanager):
        print("  Installing Android SDK cmdline-tools...")
        _install_cmdline_tools(sdk_root)

    if os.access(sdkmanager, os.X_OK):
        return sdkmanager

    if os.path.exists(sdkmanager):
        print("  Fixing sdkmanager permissions...")
        os.chmod(sdkmanager, 0o755)
        for f in os.listdir(os.path.dirname(sdkmanager)):
            fp = os.path.join(os.path.dirname(sdkmanager), f)
            if os.path.isfile(fp):
                os.chmod(fp, 0o755)
        return sdkmanager

    print("  ✗ sdkmanager not found after install attempt, skipping Android setup")
    return None


def _android_install_sdk(sdkmanager):
    """Install Android platform tools and build tools via sdkmanager."""
    print("  Installing Android platform tools and build tools...")
    result = subprocess.run([sdkmanager, "--install",
                             "platform-tools",
                             "build-tools;36.0.0",
                             "platforms;android-36",
                             "platforms;android-34",
                             "emulator"],
                            text=True)
    if result.returncode != 0:
        print("  ⚠ sdkmanager install had issues, continuing...")


def _android_create_avds(sdk_root):
    """Create the two standard AVDs."""
    _create_avd(sdk_root, "pixel_9", "android-36",
                "Pixel_9_API_36", "Most recent API")
    _create_avd(sdk_root, "pixel_8", "android-34",
                "Pixel_8_API_34", "Most used API (Android 14)")


def setup_android_sdk():
    """Install Android SDK, accept licenses, create AVDs."""
    _android_install_jdk()
    _android_setup_kvm()
    _android_accept_licenses()

    sdk_root = _get_android_sdk_path()
    if not sdk_root:
        print("  ✗ Could not locate Android SDK")
        return False

    sdkmanager = _android_ensure_sdkmanager(sdk_root)
    if not sdkmanager:
        return False

    _android_install_sdk(sdkmanager)
    _android_create_avds(sdk_root)
    return True


def _get_android_sdk_path():
    """Return the Android SDK root path."""
    # Try to get from flutter doctor output
    try:
        result = subprocess.run(
            ["flutter", "doctor", "-v"],
            capture_output=True, text=True,
        )
        for line in result.stdout.splitlines():
            if "Android SDK" in line:
                path = line.split("at")[-1].strip()
                if os.path.isdir(path):
                    return path
    except Exception:
        pass

    # Check common locations
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


def _install_cmdline_tools(sdk_root):
    """Download and install Android SDK command-line tools."""
    tools_dir = Path(sdk_root) / "cmdline-tools"
    tools_dir.mkdir(parents=True, exist_ok=True)

    url = ("https://dl.google.com/android/repository/"
           "commandlinetools-linux-11076708_latest.zip")
    if platform.system() == "Windows":
        url = ("https://dl.google.com/android/repository/"
               "commandlinetools-win-11076708_latest.zip")

    zip_path = tools_dir / "cmdline-tools.zip"
    print(f"  Downloading Android cmdline-tools...")
    try:
        urllib.request.urlretrieve(url, zip_path)
    except Exception as exc:
        print(f"  ✗ Failed to download: {exc}")
        return

    print(f"  Extracting...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(tools_dir)
    zip_path.unlink()

    # Move to latest/ subdirectory as sdkmanager expects
    (tools_dir / "latest").mkdir(exist_ok=True)
    for item in (tools_dir / "cmdline-tools").iterdir():
        if item.name != "latest":
            shutil.move(str(item), str(tools_dir / "latest" / item.name))
    (tools_dir / "cmdline-tools").rmdir()

    # Fix permissions — extracted files lack execute bit
    bin_dir = tools_dir / "latest" / "bin"
    if bin_dir.exists():
        for f in bin_dir.iterdir():
            f.chmod(f.stat().st_mode | 0o111)


def _create_avd(sdk_root, device, target, name, description):
    """Create an Android Virtual Device."""
    avdmanager = os.path.join(sdk_root, "cmdline-tools", "latest", "bin", "avdmanager")
    if not os.path.exists(avdmanager):
        print(f"  ⚠ avdmanager not found, skipping AVD {name}")
        return

    # Check if AVD already exists
    result = subprocess.run([avdmanager, "list", "avd", "-c"],
                            capture_output=True, text=True)
    if name in result.stdout:
        print(f"  ✓ AVD {name} already exists")
        return

    print(f"  Creating AVD {name} ({description})...")
    subprocess.run([
        avdmanager, "create", "avd",
        "--force",
        "--device", device,
        "--name", name,
        "--package", f"system-images;{target};google_apis;x86_64",
        "--tag", "google_apis",
    ], text=True, capture_output=True)


def install_modules(os_type, components, mode):
    """Install software modules for the selected components.

    Returns a dict with status per module.
    """
    software_list = get_software_for_components(components, mode)
    if not software_list:
        print("  No software modules to install.")
        return {}

    print(f"\nInstalling {len(software_list)} software modules...")
    results = {}
    needs_flutter_setup = False
    needs_android = False

    for sw in software_list:
        if not install_single_software(sw, os_type):
            print(f"  ✗ Aborting — {sw} failed to install")
            return None
        results[sw] = "OK"
        if sw == "flutter":
            needs_flutter_setup = True
            if "app" in components:
                needs_android = True

    # Post-install: VS Code extensions and settings
    if results.get("vscode") == "OK":
        setup_vscode(components)

    # Post-install: Flutter platform configuration
    if needs_flutter_setup:
        setup_flutter_platforms(os_type)

    # Post-install: Android SDK + AVDs (only if app component is selected)
    if needs_android:
        print("  Setting up Android SDK and emulators...")
        if not setup_android_sdk():
            print("  ✗ Aborting — Android SDK setup failed")
            return None

    return results


def print_installation_report(results):
    """Print a formatted report of installation results."""
    if results is None:
        return
    if not results:
        return
    print("\n--- Installation Report ---")
    all_ok = True
    for sw, status in sorted(results.items()):
        icon = "✓" if status == "OK" else "✗"
        print(f"  {icon} {sw}: {status}")
        if status != "OK":
            all_ok = False
    if all_ok:
        print("\n✓ All modules installed successfully!")
    else:
        print("\n⚠ Some modules failed. Review the output above.")


# ============================================================================
# Environment Update
# ============================================================================

def update_environment(os_type, managers):
    """Update package lists (mandatory) and upgrade packages.

    Linux:   sudo apt update && sudo apt upgrade -y
    Windows: winget upgrade --all
    """
    if os_type == "linux" and "apt" in managers:
        print("  Updating package lists (sudo apt update)...")
        result = subprocess.run(["sudo", "apt", "update"], text=True)
        if result.returncode == 0:
            print("  ✓ Package lists updated")
        else:
            print("  ⚠ Package lists update returned warnings, continuing...")

        print("  Upgrading system packages (sudo apt upgrade -y)...")
        result = subprocess.run(["sudo", "apt", "upgrade", "-y"], text=True)
        if result.returncode == 0:
            print("  ✓ System packages upgraded")
        else:
            print("  ⚠ System upgrade had issues, continuing...")

    elif os_type == "windows":
        print("  Updating package lists (winget upgrade)...")
        result = subprocess.run(
            ["winget", "upgrade"],
            text=True,
        )
        if result.returncode == 0:
            print("  ✓ Package lists updated")
        else:
            print("  ⚠ Package lists update had issues, continuing...")

        print("  Upgrading all packages...")
        result = subprocess.run(
            ["winget", "upgrade", "--all", "--accept-package-agreements",
             "--accept-source-agreements"],
            text=True,
        )
        if result.returncode == 0:
            print("  ✓ Packages upgraded")
        else:
            print("  ⚠ Upgrade had issues, continuing...")
    else:
        print("  ⚠ No supported package manager found for automatic updates")
        print("  (continuing without updates)")


# ============================================================================
# Main Flow
# ============================================================================

def main():
    """Main entry point."""
    print("=" * 60)
    print("MakTrak Setup Script")
    print("=" * 60)
    
    # Step 1: Detect OS
    print("\n[1/8] Detecting operating system...")
    os_type = detect_os()
    print(f"✓ OS detected: {os_type}")

    # Step 1b: Require administrator/sudo privileges
    print("\n[1b/8] Checking privileges...")
    privilege_state = ensure_admin_privileges(os_type)
    if privilege_state == "relaunch":
        sys.exit(0)
    if not privilege_state:
        sys.exit(1)
    
    # Step 2: Detect package managers
    print("\n[2/8] Detecting package managers...")
    managers = detect_package_managers(os_type)
    if managers:
        print(f"✓ Package managers found: {', '.join(managers.keys())}")
    else:
        print("✗ No package managers found")
        sys.exit(1)
    
    # Step 3: Install version control tools (git + Sublime Merge)
    print("\n[3/8] Installing version control tools...")
    if not validate_git():
        if not _install_package("git", os_type):
            print("✗ Git is required but could not be installed")
            sys.exit(1)
        if not validate_git():
            print("✗ Git is required but not available after installation attempt")
            sys.exit(1)

    if not find_sublime_merge_executable():
        print("  Installing Sublime Merge...")
        if not _install_package("sublime-merge", os_type):
            print("  ⚠ Could not install Sublime Merge automatically. Continuing without it.")
    
    # Step 4: Select mode and components
    print("\n[4/8] User configuration...")
    mode = select_mode()
    
    if mode == "dev":
        components = _select_components(DEV_MODULES, "Development")
    else:
        components = _select_components(PROD_MODULES, "Production")
    
    # Step 5: Update environment
    print("\n[5/8] Updating environment...")
    update_environment(os_type, managers)
    
    # Step 6: Confirm actions
    print("\n[6/8] Confirmation...")
    if not confirm_actions(mode, components, os_type, managers):
        print("Installation cancelled.")
        sys.exit(0)
    
    # Step 7: Download repositories (clone/update)
    print("\n[7/8] Downloading repositories...")
    
    repos_to_clone = get_repositories_to_clone(mode, components)
    if repos_to_clone:
        credentials = get_github_credentials()
        if credentials is None:
            print("GitHub credentials are required for private repository access.")
            sys.exit(1)
        
        if not configure_git_credential_helper():
            sys.exit(1)
    
    if not clone_repositories(mode, components):
        print("Some repositories failed to download. Review the output and try again.")
        sys.exit(1)
    
    # Step 8: Install software modules
    print("\n[8/8] Installing software modules...")
    results = install_modules(os_type, components, mode)
    if results is None:
        sys.exit(1)
    print_installation_report(results)

    # Post-install extras: configure Xfce panel on Xubuntu
    _configure_xfce_panel()

    print("\n" + "=" * 60)
    print("✓ MakTrak Setup completed successfully!")
    print("=" * 60)
    print("\nNext steps:")
    print("- Validate installation (run validation commands)")
    print("- Start developing!")


# ============================================================================
# Xfce Panel Configuration (Xubuntu)
# ============================================================================

def _configure_xfce_panel():
    """Configure Xfce panel: bottom bar with 2 rows (Xubuntu only)."""
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
    if "xfce" not in desktop.lower():
        return

    print("\nConfiguring Xfce panel...")
    result = subprocess.run(
        ["xfconf-query", "-c", "xfce4-panel", "-p", "/panels"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("  \u26a0 Could not query panel configuration")
        return

    panels = result.stdout.strip().splitlines()
    if not panels:
        print("  \u26a0 No panels found")
        return

    panel_num = panels[0].strip()

    subprocess.run([
        "xfconf-query", "-c", "xfce4-panel", "-p",
        f"/panels/{panel_num}/position",
        "-s", "p=6;x=0;y=0",
    ], capture_output=True, text=True)

    subprocess.run([
        "xfconf-query", "-c", "xfce4-panel", "-p",
        f"/panels/{panel_num}/nrows", "-s", "2",
    ], capture_output=True, text=True)

    subprocess.run(["xfce4-panel", "-r"], capture_output=True, text=True)
    print("  \u2713 Panel configured: bottom bar, 2 rows")


if __name__ == "__main__":
    main()

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
        # Check for apt-get
        if subprocess.run(["which", "apt-get"], capture_output=True).returncode == 0:
            managers["apt-get"] = True
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


def run_install_command(cmd, os_type, package_name):
    """Run an install command and apply post-install actions."""
    print(f"Attempting to install {package_name}...")
    try:
        result = subprocess.run(cmd, text=True)
    except Exception as exc:
        print(f"✗ Failed to run {package_name} installation command")
        print(str(exc))
        return False

    if result.returncode != 0:
        print(f"✗ Failed to install {package_name} automatically")
        return False

    if os_type == "windows":
        refresh_windows_path_from_system()

    print(f"✓ {package_name} installation command completed")
    return True


def install_git(os_type):
    """Try to install Git using a fixed package manager command per OS."""

    if os_type == "windows":
        cmd = [
            "winget",
            "install",
            "--id",
            "Git.Git",
            "-e",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ]

    elif os_type == "linux":
        cmd = ["sudo", "apt", "install", "-y", "git"]

    else:
        print(f"✗ Automatic Git installation not implemented for OS: {os_type}")
        return False

    return run_install_command(cmd, os_type, "Git")


def install_sublime_merge(os_type):
    """Try to install Sublime Merge with a fixed package manager command per OS."""
    if os_type == "windows":
        cmd = [
            "winget",
            "install",
            "--id",
            "SublimeHQ.SublimeMerge",
            "-e",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ]
    elif os_type == "linux":
        cmd = ["sudo", "snap", "install", "sublime-merge", "--classic"]
    else:
        print(f"✗ Automatic Sublime Merge installation not implemented for OS: {os_type}")
        return False

    return run_install_command(cmd, os_type, "Sublime Merge")


# ============================================================================
# User Interaction
# ============================================================================

def select_mode():
    """Prompt user to select dev or prod mode."""
    while True:
        print("\n--- Select Execution Mode ---")
        print("1. dev   - Development environment")
        print("2. prod  - Production environment")
        choice = input("Enter your choice (1 or 2): ").strip()
        
        if choice == "1":
            return "dev"
        elif choice == "2":
            return "prod"
        else:
            print("Invalid choice. Please enter 1 or 2.")


def select_dev_components():
    """Prompt user to select dev components."""
    print("\n--- Select Development Components ---")
    components = []
    
    for i, category in enumerate(DEV_MODULES.keys(), 1):
        print(f"{i}. {category}")
    print(f"{len(DEV_MODULES) + 1}. todos (all categories)")
    
    choice = input("Enter your choice (comma-separated for multiple): ").strip()
    
    if choice == str(len(DEV_MODULES) + 1):
        # Select all
        components = list(DEV_MODULES.keys())
    else:
        # Select specific categories
        choices = [c.strip() for c in choice.split(",")]
        categories = list(DEV_MODULES.keys())
        for c in choices:
            try:
                idx = int(c) - 1
                if 0 <= idx < len(categories):
                    components.append(categories[idx])
            except ValueError:
                pass
    
    return components


def select_prod_components():
    """Prompt user to select prod components."""
    print("\n--- Select Production Components ---")
    components = []
    
    for i, category in enumerate(PROD_MODULES.keys(), 1):
        print(f"{i}. {category}")
    print(f"{len(PROD_MODULES) + 1}. todos (all components)")
    
    choice = input("Enter your choice (comma-separated for multiple): ").strip()
    
    if choice == str(len(PROD_MODULES) + 1):
        # Select all
        components = list(PROD_MODULES.keys())
    else:
        # Select specific components
        choices = [c.strip() for c in choice.split(",")]
        categories = list(PROD_MODULES.keys())
        for c in choices:
            try:
                idx = int(c) - 1
                if 0 <= idx < len(categories):
                    components.append(categories[idx])
            except ValueError:
                pass
    
    return components


def get_software_for_components(components, mode):
    """Return software packages to install.

    Current policy: install all known software in all OSes by default.
    Exceptions can be added later.
    """
    software = set()
    for values in DEV_MODULES.values():
        software.update(values)
    for values in PROD_MODULES.values():
        software.update(values)
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
    print("Components to install:")
    for component in components:
        print(f"  - {component}")
    software = get_software_for_components(components, mode)
    print("Software policy: install all programs on all OSes (exceptions defined later).")
    print("Software to install:")
    if software:
        for item in software:
            print(f"  - {item}")
    else:
        print("  - none")
    
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
    for candidate in candidates:
        if os.path.isabs(candidate) and os.path.exists(candidate):
            print(f"✓ Sublime Merge detected at: {candidate}")
            return candidate
        path = shutil.which(candidate)
        if path:
            print(f"✓ Sublime Merge detected at: {path}")
            return path
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
    import time as _time

    for attempt in range(1, MAX_RETRIES + 1):
        result = subprocess.run(args, capture_output=True, text=True)
        if result.returncode == 0:
            return result

        is_auth_error = "403" in result.stderr or "Authentication failed" in result.stderr
        is_network_error = (
            "Could not resolve host" in result.stderr
            or "Connection refused" in result.stderr
            or "Connection timed out" in result.stderr
            or "failed" in result.stderr.lower()
        )

        if attempt < MAX_RETRIES and (is_auth_error or is_network_error):
            delay = RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
            print(f"  ⚠ {operation_label} failed (attempt {attempt}/{MAX_RETRIES})"
                  f" — retrying in {delay}s...")
            if is_auth_error:
                print(f"    Possible authentication issue. Check your GitHub token.")
            _time.sleep(delay)
        else:
            break

    return result


def clone_repository(repo_name, repo_url):
    """Clone or update a repository at the standard destination with retry support."""
    dest = get_clone_destination(repo_name)
    if dest.exists():
        print(f"Repository already exists: {dest}")
        if (dest / ".git").exists():
            print(f"Pulling latest changes in {repo_name}...")
            result = _run_git_with_retry(
                ["git", "-C", str(dest), "pull"],
                repo_name,
                f"git pull {repo_name}",
            )
            if result.returncode == 0:
                print(f"✓ Updated {repo_name}")
                register_repo_with_sublime_merge(dest)
            else:
                print(f"✗ Failed to update {repo_name}")
                if result.stderr:
                    print(f"  {result.stderr.strip()}")
                return False
            return True
        else:
            print(f"✗ {dest} exists but is not a git repository")
            return False
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"Cloning {repo_name} into {dest}...")
        result = _run_git_with_retry(
            ["git", "clone", "--progress", repo_url, str(dest)],
            repo_name,
            f"git clone {repo_name}",
        )
        if result.returncode == 0:
            print(f"✓ Cloned {repo_name}")
            register_repo_with_sublime_merge(dest)
            return True
        else:
            print(f"✗ Failed to clone {repo_name}")
            if result.stderr:
                print(f"  {result.stderr.strip()}")
            # Remove empty destination directory if clone failed
            if dest.exists() and not (dest / ".git").exists():
                try:
                    dest.rmdir()
                except OSError:
                    pass
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
    success = True
    for repo in repos:
        repo_url = REPOSITORIES.get(repo)
        if not repo_url:
            print(f"✗ No URL configured for repository: {repo}")
            success = False
            continue
        if not clone_repository(repo, repo_url):
            success = False
    return success


# ============================================================================
# Main Flow
# ============================================================================

def main():
    """Main entry point."""
    print("=" * 60)
    print("MakTrak Setup Script")
    print("=" * 60)
    
    # Step 1: Detect OS
    print("\n[1/6] Detecting operating system...")
    os_type = detect_os()
    print(f"✓ OS detected: {os_type}")

    # Step 1b: Require administrator/sudo privileges
    print("\n[1b/6] Checking privileges...")
    privilege_state = ensure_admin_privileges(os_type)
    if privilege_state == "relaunch":
        sys.exit(0)
    if not privilege_state:
        sys.exit(1)
    
    # Step 2: Detect package managers
    print("\n[2/6] Detecting package managers...")
    managers = detect_package_managers(os_type)
    if managers:
        print(f"✓ Package managers found: {', '.join(managers.keys())}")
    else:
        print("✗ No package managers found")
        sys.exit(1)
    
    # Step 3: Install version control tools (git + Sublime Merge)
    print("\n[3/6] Installing version control tools...")
    if not validate_git():
        if not install_git(os_type):
            print("✗ Git is required but could not be installed")
            sys.exit(1)
        if not validate_git():
            print("✗ Git is required but not available after installation attempt")
            sys.exit(1)

    if not find_sublime_merge_executable():
        print("  Installing Sublime Merge...")
        if not install_sublime_merge(os_type):
            print("  ⚠ Could not install Sublime Merge automatically. Continuing without it.")
    
    # Step 4: Select mode and components
    print("\n[4/6] User configuration...")
    mode = select_mode()
    
    if mode == "dev":
        components = select_dev_components()
    else:
        components = select_prod_components()
    
    # Step 5: Confirm actions
    print("\n[5/6] Confirmation...")
    if not confirm_actions(mode, components, os_type, managers):
        print("Installation cancelled.")
        sys.exit(0)
    
    # Step 6: Download repositories (clone/update)
    print("\n[6/6] Downloading repositories...")
    
    repos_to_clone = get_repositories_to_clone(mode, components)
    if repos_to_clone:
        # Collect GitHub credentials only if there are repos to clone
        credentials = get_github_credentials()
        if credentials is None:
            print("GitHub credentials are required for private repository access.")
            sys.exit(1)
        
        if not configure_git_credential_helper():
            print("Failed to configure Git credential helper. Continuing anyway...")
    
    if not clone_repositories(mode, components):
        print("Some repositories failed to download. Review the output and try again.")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✓ All repositories downloaded successfully!")
    print("=" * 60)
    print("\nNext steps:")
    print("- Update environment (mandatory)")
    print("- Install modules")
    print("- Validate installation")


if __name__ == "__main__":
    main()

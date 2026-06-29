#!/usr/bin/env python3
"""
MakTrak Setup Script
Multiplataforma installer for MakTrak development and production environments.
"""

import sys
import platform
import subprocess
import os
from pathlib import Path


# ============================================================================
# CONFIGURATION: Repositories and Modules
# ============================================================================

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
    "mecanica": ["freecad"],
    "eletronica": ["kicad"],
    "firmware": ["arduino-cli", "vscode"],
    "servidor": ["vscode", "flutter"],
    "app": ["vscode", "flutter"],
}

# Repository mapping for dev categories
DEV_REPOSITORIES = {
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
        # Check for choco
        if subprocess.run(["where", "choco"], capture_output=True).returncode == 0:
            managers["choco"] = True
        # Check for pip
        if subprocess.run(["where", "pip"], capture_output=True).returncode == 0:
            managers["pip"] = True
    
    return managers


def validate_git():
    """Validate that git is available."""
    result = subprocess.run(["git", "--version"], capture_output=True)
    if result.returncode == 0:
        print(f"✓ Git found: {result.stdout.decode().strip()}")
        return True
    else:
        print("✗ Git not found")
        return False


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
    """Return the software packages associated with the selected components."""
    software = set()
    if mode == "dev":
        for component in components:
            software.update(DEV_MODULES.get(component, []))
    else:
        for component in components:
            software.update(PROD_MODULES.get(component, []))
    return sorted(software)


def get_repositories_for_components(components):
    """Return the repositories required by the selected dev components."""
    repos = set()
    for component in components:
        repos.update(DEV_REPOSITORIES.get(component, []))
    return sorted(repos)


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
    print("Software to install:")
    if software:
        for item in software:
            print(f"  - {item}")
    else:
        print("  - none")
    if mode == "dev":
        repos = get_repositories_for_components(components)
    else:
        repos = sorted(PROD_MODULES.keys())
    
    print("Repositories to clone:")
    for repo in repos:
        repo_path = REPOSITORIES.get(repo, "")
        if repo_path:
            print(f"  - {repo}: {repo_path}")
        else:
            print(f"  - {repo}")
    
    confirm = input("\nProceed with these actions? (YES/no): ").strip().lower()
    return confirm in {"yes", ""}


# ============================================================================
# Main Flow
# ============================================================================

def main():
    """Main entry point."""
    print("=" * 60)
    print("MakTrak Setup Script")
    print("=" * 60)
    
    # Step 1: Detect OS
    print("\n[1/5] Detecting operating system...")
    os_type = detect_os()
    print(f"✓ OS detected: {os_type}")
    
    # Step 2: Detect package managers
    print("\n[2/5] Detecting package managers...")
    managers = detect_package_managers(os_type)
    if managers:
        print(f"✓ Package managers found: {', '.join(managers.keys())}")
    else:
        print("✗ No package managers found")
        sys.exit(1)
    
    # Step 3: Validate dependencies
    print("\n[3/5] Validating dependencies...")
    if not validate_git():
        print("✗ Git is required but not found")
        sys.exit(1)
    
    # Step 4: Select mode and components
    print("\n[4/5] User configuration...")
    mode = select_mode()
    
    if mode == "dev":
        components = select_dev_components()
    else:
        components = select_prod_components()
    
    # Step 5: Confirm actions
    print("\n[5/5] Confirmation...")
    if not confirm_actions(mode, components, os_type, managers):
        print("Installation cancelled.")
        sys.exit(0)
    
    print("\n" + "=" * 60)
    print("Ready to proceed with installation!")
    print("=" * 60)
    print("\nNext steps:")
    print("- Update environment (mandatory)")
    print("- Clone repositories")
    print("- Install modules")
    print("- Validate installation")
    print("\n[TODO] Implementation of remaining steps...")


if __name__ == "__main__":
    main()

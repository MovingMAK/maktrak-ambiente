"""
Setup MakTrak — Ambiente Base
Componentes: VS Code, configurações de desktop (Xfce)
"""

from maktrak_setup import SetupBase, print_banner, ANSI_CYAN

SETUP_NAME = "MakTrak Setup — Ambiente"
SETUP_VERSION = "1.0.1"
SETUP_DATE = "2026-08-04"


class AmbienteSetup(SetupBase):
    """Instalação e configuração do ambiente base MakTrak."""

    def init(self):
        print_banner(SETUP_NAME, SETUP_VERSION, accent=ANSI_CYAN, date=SETUP_DATE)
        print("  Preparando ambiente base...")

    def install(self):
        self.install_pkgs("vscode")

    def configure(self):
        # Extensoes universais sao instaladas pelo orquestrador
        pass

    def test(self):
        self.results["vscode"] = self.assert_executable("code")

"""
Setup MakTrak — Ambiente Base
Componentes: VS Code, configurações de desktop (Xfce)
"""

from maktrak_setup import SetupBase


class AmbienteSetup(SetupBase):
    """Instalação e configuração do ambiente base MakTrak."""

    def init(self):
        print("  Preparando ambiente base...")

    def install(self):
        self.install_pkgs("vscode")

    def configure(self):
        # Extensoes universais sao instaladas pelo orquestrador
        pass

    def test(self):
        self.results["vscode"] = self.assert_executable("code")

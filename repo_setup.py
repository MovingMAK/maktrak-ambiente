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
        self.install_extensions([
            "GitHub.vscode-pull-request-github",
            "yzhang.markdown-all-in-one",
            "zaaack.markdown-editor",
            "ms-python.python",
            "ms-vscode.cpptools",
        ])
        self.set_setting("workbench.editor.limit.value", 20)

    def test(self):
        self.results["vscode"] = self.assert_executable("code")

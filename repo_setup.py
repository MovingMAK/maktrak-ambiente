"""
Setup MakTrak — Ambiente Base
Componentes: VS Code, configurações de desktop (Xfce)
"""

from maktrak_setup import SetupBase


class AmbienteSetup(SetupBase):
    """Instalação e configuração do ambiente base MakTrak."""

    def install(self):
        self.install_pkg("vscode")

    def configure(self):
        self.install_extensions([
            "GitHub.vscode-pull-request-github",
            "yzhang.markdown-all-in-one",
            "zaaack.markdown-editor",
            "ms-python.python",
            "ms-vscode.cpptools",
        ])
        self.vscode_setting("workbench.editor.limit.value", 20)
        self._configure_xfce_panel()

    def test(self):
        self.results["vscode"] = self.run(["code", "--version"]).returncode == 0

    def _configure_xfce_panel(self):
        """Configura painel Xfce (Xubuntu): barra inferior com 2 linhas."""
        import os
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
        if "xfce" not in desktop.lower():
            return
        self.run(["xfconf-query", "-c", "xfce4-panel", "-p",
                   "/panels/panel-0/nrows", "-s", "2"])
        self.run(["xfce4-panel", "-r"])

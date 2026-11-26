"""
Janela para gerar o painel sem linha de comando: cole (Ctrl+V) ou escolha o
.json exportado do Trello e clique em "Gerar PDF". Usa o trello_report.py.

Abrir: duplo clique neste arquivo (Windows) ou `python trello_report_gui.pyw`.
"""

import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trello_report  # noqa: E402


def clipboard_file(root):
    """Caminho colado: texto ("Copiar como caminho") ou arquivo copiado no Explorer."""
    if sys.platform == "win32":
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-Clipboard -Format FileDropList | Select-Object -First 1 -ExpandProperty FullName"],
                capture_output=True, text=True, timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip()
            if out:
                return out
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        return root.clipboard_get().strip()
    except tk.TclError:
        return ""


def open_file(path):
    if sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


def main():
    root = tk.Tk()
    root.title("Painel do Trello")
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=14)
    frame.grid()

    ttk.Label(frame, text="Arquivo .json exportado do Trello (cole com Ctrl+V ou procure):").grid(
        row=0, column=0, columnspan=2, sticky="w")
    path_var = tk.StringVar()
    entry = ttk.Entry(frame, textvariable=path_var, width=70)
    entry.grid(row=1, column=0, pady=6, sticky="we")

    def paste(_event=None):
        path_var.set(clipboard_file(root).strip('"'))
        return "break"

    def browse():
        chosen = filedialog.askopenfilename(title="Escolha o .json do Trello",
                                            filetypes=[("JSON do Trello", "*.json"), ("Todos", "*.*")],
                                            initialdir=str(Path.home() / "Downloads"))
        if chosen:
            path_var.set(chosen)

    entry.bind("<Control-v>", paste)
    entry.bind("<Control-V>", paste)
    ttk.Button(frame, text="Procurar…", command=browse).grid(row=1, column=1, padx=(6, 0))

    status = tk.StringVar(value="")
    button = ttk.Button(frame, text="Gerar PDF")
    button.grid(row=2, column=0, columnspan=2, pady=(4, 6))
    ttk.Label(frame, textvariable=status, wraplength=520).grid(row=3, column=0, columnspan=2, sticky="w")

    def finish(message, result=None):
        status.set(message)
        button.state(["!disabled"])
        if result:
            open_file(result)

    def worker(src):
        try:
            browser = trello_report.find_browser()
            result = trello_report.generate(src, browser)
            note = "" if browser else " (sem Chrome/Edge: imprima o .html como PDF)"
            root.after(0, finish, f"Pronto: {result}{note}", result)
        except Exception as exc:  # mostra qualquer falha na janela
            root.after(0, finish, f"Erro: {exc}")

    def run():
        src = path_var.get().strip().strip('"')
        if not src or not Path(src).is_file():
            status.set("Informe um arquivo .json existente.")
            return
        button.state(["disabled"])
        status.set("Gerando…")
        threading.Thread(target=worker, args=(src,), daemon=True).start()

    button.configure(command=run)
    entry.bind("<Return>", lambda _e: run())
    entry.focus_set()
    root.mainloop()


if __name__ == "__main__":
    main()

"""
Janela para abrir o painel sem linha de comando: cole (Ctrl+V) o JSON do
Trello — o texto copiado da página "Exportar como JSON" ou o arquivo .json
copiado no Explorer — e o painel (.html interativo) abre no navegador.
Usa o trello_report.py. O PDF sai pelo botão "Imprimir / PDF" do painel.

Abrir: duplo clique neste arquivo (Windows), `python trello_report_gui.pyw`
ou o executável gerado a partir dele (ver guia.md).
Argumentos (opcionais): um arquivo .json abre o painel direto, sem janela
(é o que o "Abrir com" do Windows usa); uma pasta grava o painel nela (padrão:
Downloads). `--registrar` cadastra o programa no "Abrir com" dos .json.
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trello_report  # noqa: E402


def clipboard_content(root):
    """Arquivo copiado no Explorer (caminho) ou texto da área de transferência."""
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
        return root.clipboard_get()
    except tk.TclError:
        return ""


def open_file(path):
    if sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


APP_NAME = "Painel MakTrak"
PROG_ID = "PainelMakTrak.json"


def register_open_with():
    """Cadastra o programa no "Abrir com" dos .json, só para o usuário atual
    (HKCU, sem administrador). O executável é copiado para uma pasta fixa, para
    o cadastro não quebrar se o arquivo baixado for apagado."""
    import shutil
    import winreg
    if getattr(sys, "frozen", False):
        target = Path(os.environ["LOCALAPPDATA"]) / APP_NAME / f"{APP_NAME}.exe"
        target.parent.mkdir(parents=True, exist_ok=True)
        if Path(sys.executable).resolve() != target.resolve():
            shutil.copy2(sys.executable, target)
        command = f'"{target}" "%1"'
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\Applications\{target.name}") as key:
            winreg.SetValueEx(key, "FriendlyAppName", 0, winreg.REG_SZ, APP_NAME)
    else:
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        command = f'"{pythonw}" "{Path(__file__).resolve()}" "%1"'
    classes = r"Software\Classes"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{classes}\{PROG_ID}") as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "JSON do Trello")
        winreg.SetValueEx(key, "FriendlyTypeName", 0, winreg.REG_SZ, "JSON do Trello")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{classes}\{PROG_ID}\shell\open") as key:
        winreg.SetValueEx(key, "FriendlyAppName", 0, winreg.REG_SZ, APP_NAME)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{classes}\{PROG_ID}\shell\open\command") as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{classes}\.json\OpenWithProgids") as key:
        winreg.SetValueEx(key, PROG_ID, 0, winreg.REG_NONE, b"")
    import ctypes
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)  # avisa o Explorer
    return command


def open_direct(json_path, out_dir):
    """Aberto com um .json ("Abrir com"): gera e abre o painel, sem janela."""
    root = tk.Tk()
    root.withdraw()
    try:
        html_path, _ = trello_report.generate(json_path, None, out_dir)
        open_file(html_path)
    except Exception as exc:  # mostra qualquer falha numa caixa de mensagem
        messagebox.showerror(APP_NAME, f"Não foi possível gerar o painel de\n{json_path}\n\n{exc}")
    root.destroy()


def main():
    args = sys.argv[1:]
    out_dir = next((a for a in args if Path(a).is_dir()), str(Path.home() / "Downloads"))
    if "--registrar" in args:
        print(register_open_with())
        return
    json_file = next((a for a in args if a.lower().endswith(".json") and Path(a).is_file()), None)
    if json_file:
        open_direct(json_file, out_dir)
        return
    root = tk.Tk()
    root.title(APP_NAME)
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=14)
    frame.grid()

    ttk.Label(frame, text="Como usar", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
    ttk.Label(frame, justify="left", text=(
        "1. No Trello, abra o quadro → Menu (⋯) → Imprimir, exportar e compartilhar → Exportar como JSON.\n"
        "2. Copie o JSON: na página que abrir, Ctrl+A e Ctrl+C\n"
        "    (ou, se baixou o arquivo .json, selecione-o no Explorer e aperte Ctrl+C).\n"
        "3. Clique no campo abaixo e cole com Ctrl+V. O painel abre no navegador, pronto para filtrar.\n"
        "    Para PDF, use o botão “Imprimir / PDF” no topo do painel.")).grid(
        row=1, column=0, columnspan=2, sticky="w", pady=(2, 8))
    shown = tk.StringVar()
    entry = ttk.Entry(frame, textvariable=shown, width=70)
    entry.grid(row=2, column=0, pady=6, sticky="we")
    source = {"path": None, "text": None}

    status = tk.StringVar(value=f"O painel será gravado em: {out_dir}")
    button = ttk.Button(frame, text="Abrir painel")
    button.grid(row=3, column=0, columnspan=2, pady=(4, 6))
    ttk.Label(frame, textvariable=status, wraplength=560).grid(row=4, column=0, columnspan=2, sticky="w")

    def finish(message, result=None):
        status.set(message)
        button.state(["!disabled"])
        if result:
            open_file(result)

    def worker(path, text):
        tmp = None
        try:
            if text is not None:
                fd, tmp = tempfile.mkstemp(suffix=".json")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(text)
                path = tmp
            html_path, _ = trello_report.generate(path, None, out_dir)
            root.after(0, finish, f"Pronto: {html_path}", html_path)
        except Exception as exc:  # mostra qualquer falha na janela
            root.after(0, finish, f"Erro: {exc}")
        finally:
            if tmp:
                os.remove(tmp)

    def run():
        path, text = source["path"], source["text"]
        if text is None:
            path = (path or shown.get()).strip().strip('"')
            if not path or not Path(path).is_file():
                status.set("Cole o JSON do Trello (texto ou arquivo .json).")
                return
        button.state(["disabled"])
        status.set("Gerando o painel…")
        threading.Thread(target=worker, args=(path, text), daemon=True).start()

    def set_source(content):
        content = content.strip()
        source["path"] = source["text"] = None
        if content.startswith("{"):
            try:
                board = json.loads(content)
            except ValueError:
                status.set("O texto colado não é um JSON válido. Copie a página inteira (Ctrl+A, Ctrl+C).")
                return False
            source["text"] = content
            shown.set(f"[JSON colado: quadro “{board.get('name', '?')}”, {len(content) // 1024} KB]")
        else:
            source["path"] = content.strip('"')
            shown.set(source["path"])
        return True

    def paste(_event=None):
        if set_source(clipboard_content(root)):
            run()
        return "break"

    def browse():
        chosen = filedialog.askopenfilename(title="Escolha o .json do Trello",
                                            filetypes=[("JSON do Trello", "*.json"), ("Todos", "*.*")],
                                            initialdir=str(Path.home() / "Downloads"))
        if chosen and set_source(chosen):
            run()

    entry.bind("<Control-v>", paste)
    entry.bind("<Control-V>", paste)
    entry.bind("<Return>", lambda _e: run())
    ttk.Button(frame, text="Procurar…", command=browse).grid(row=2, column=1, padx=(6, 0))
    button.configure(command=run)

    def register():
        try:
            register_open_with()
            messagebox.showinfo(APP_NAME, "Pronto. Ao abrir um .json baixado do Trello, escolha "
                                          f"“{APP_NAME}” na lista do Windows (marque “Sempre” para ficar automático).")
        except Exception as exc:  # mostra qualquer falha na janela
            status.set(f"Erro ao cadastrar: {exc}")

    if sys.platform == "win32":
        ttk.Separator(frame).grid(row=5, column=0, columnspan=2, sticky="we", pady=(10, 6))
        ttk.Label(frame, text="Atalho: abrir o .json baixado do Trello direto com este programa.").grid(
            row=6, column=0, sticky="w")
        ttk.Button(frame, text="Usar para abrir arquivos .json", command=register).grid(row=6, column=1, padx=(6, 0))
    entry.focus_set()
    root.mainloop()


if __name__ == "__main__":
    main()

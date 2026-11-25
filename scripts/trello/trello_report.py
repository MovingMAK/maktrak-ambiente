"""
Gera o painel de progresso (PDF) a partir do .json exportado do Trello.

Só lê o arquivo exportado; não acessa o Trello. Mesma entrada, mesmo
resultado: as regras de classificação estão neste arquivo (ver guia.md).

Uso:
    python trello_report.py export.json                 # PDF ao lado do .json
    python trello_report.py a.json b.json --out pasta   # um PDF por arquivo
    python trello_report.py export.json --html-only     # só o .html
    python trello_report.py export.json --stage-name "3=Implantação"

O PDF é impresso por um Chrome/Edge/Chromium instalado (modo headless);
sem navegador, use --html-only e imprima o .html pelo navegador.
"""

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

TZ = timezone(timedelta(hours=-3))  # horário de Brasília
STALE_DAYS = 30

AREAS = ["Planejamento", "Hardware / Mecânica", "Firmware", "Back-end", "Front-end"]
# Prefixo do nome do cartão ("[HW/TG] ...") -> índice em AREAS.
PREFIX_AREA = {"PLN": 0, "ORG": 0, "HW": 1, "MEC": 1, "FW": 2,
               "BACK": 3, "SRV": 3, "FRONT": 4, "APP": 4}
# Trecho do nome da lista -> índice em AREAS.
LIST_AREA = [("PLANEJ", 0), ("HARDWARE", 1), ("MEC", 1), ("FIRMWARE", 2),
             ("BACK", 3), ("FRONT", 4)]

DONE, DOING, TODO = "done", "doing", "todo"


# -----------------------------------------------------------------------------
# Leitura e classificação
# -----------------------------------------------------------------------------
def parse_date(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(TZ)


def stage_of(name):
    m = re.search(r"ETAPA\s*#?\s*(\d+)", name.upper())
    return int(m.group(1)) if m else None


def area_from_list(name):
    upper = name.upper()
    for key, idx in LIST_AREA:
        if key in upper:
            return idx
    return None


def area_from_card(name):
    m = re.match(r"\s*\[([^\]]+)\]", name)
    if m:
        for token in re.split(r"[/|]", m.group(1).upper()):
            if token.strip() in PREFIX_AREA:
                return PREFIX_AREA[token.strip()]
    return None


def list_status(name):
    """(status, etapa) da lista, ou None se a lista não entra no painel."""
    upper = name.upper().strip()
    if upper.startswith("FEITO"):
        return DONE, stage_of(name)
    if upper.startswith("FAZENDO"):
        return DOING, None
    stage = stage_of(name)
    if stage is None:
        return None
    return (DONE if "CONCLU" in upper else TODO), stage


def stage_title(name):
    """Título da etapa a partir do nome da lista de concluídos."""
    parts = name.split(" - ", 1)
    if len(parts) < 2:
        return None
    title = re.sub(r"\s*-\s*CONCLU[IÍ]DA\s*$", "", parts[1], flags=re.I).strip()
    return title or None


def load_board(path):
    board = json.loads(Path(path).read_text(encoding="utf-8"))
    lists = [l for l in board["lists"] if not l["closed"]]
    list_info = {l["id"]: (l, list_status(l["name"])) for l in lists}

    cards = []
    for c in board["cards"]:
        if c["closed"] or c["idList"] not in list_info:
            continue
        lst, info = list_info[c["idList"]]
        if info is None:
            continue
        status, stage = info
        cards.append({"name": c["name"].strip(), "status": status, "stage": stage,
                      "area": area_from_list(lst["name"]) if status == TODO else None,
                      "members": c["idMembers"], "checked": bool(c["dueComplete"]),
                      "last": parse_date(c["dateLastActivity"]),
                      "pos": (lst["pos"], c["pos"]), "id": c["id"]})

    todo_stages = [c["stage"] for c in cards if c["status"] == TODO]
    all_stages = [c["stage"] for c in cards if c["stage"] is not None]
    current = min(todo_stages) if todo_stages else max(all_stages, default=1)
    for c in cards:
        if c["stage"] is None:
            c["stage"] = current
        if c["area"] is None:
            c["area"] = area_from_card(c["name"])
        if c["area"] is None:
            c["area"] = 0  # sem prefixo reconhecido: Planejamento

    titles = {}
    for l in lists:
        info = list_status(l["name"])
        if info and info[0] == DONE and info[1] is not None:
            titles.setdefault(info[1], stage_title(l["name"]))

    actions = board.get("actions", [])
    ref = max((parse_date(a["date"]) for a in actions),
              default=max((c["last"] for c in cards), default=datetime.now(TZ)))

    # Ritmo: primeira vez que cada cartão entrou numa lista "Feito", por semana.
    first_done = {}
    for a in actions:
        after = a.get("data", {}).get("listAfter")
        if a["type"] == "updateCard" and after and after["name"].upper().startswith("FEITO"):
            card_id = a["data"]["card"]["id"]
            when = parse_date(a["date"])
            if card_id not in first_done or when < first_done[card_id]:
                first_done[card_id] = when
    weeks = Counter((d - timedelta(days=d.weekday())).date() for d in first_done.values())
    first_week = min((parse_date(a["date"]) for a in actions), default=ref)
    first_week = (first_week - timedelta(days=first_week.weekday())).date()

    members = {m["id"]: m["fullName"].split()[0] for m in board.get("members", [])}
    return {"board": board["name"], "cards": cards, "current": current, "titles": titles,
            "ref": ref, "weeks": weeks, "first_week": first_week, "members": members,
            "partial_history": len(actions) >= 1000}


# -----------------------------------------------------------------------------
# HTML
# -----------------------------------------------------------------------------
def esc(text):
    return html.escape(str(text))


def pct(done, total):
    return round(100 * done / total) if total else 0


def counts(cards):
    c = Counter(x["status"] for x in cards)
    return c[DONE], c[DOING], c[TODO]


def bar(done, doing, todo):
    total = done + doing + todo or 1
    segs = [(done, "done"), (doing, "doing"), (todo, "todo")]
    return '<div class="bar">' + "".join(
        f'<span class="{cls}" style="width:{100 * n / total:.2f}%"></span>' for n, cls in segs if n
    ) + "</div>"


def card_items(cards, extra):
    return "".join(f"<li>{esc(c['name'])}<span class='muted'>{extra(c)}</span></li>" for c in cards)


def build_html(data, title, stage_names, stale_days):
    cards = data["cards"]
    ref = data["ref"]
    done, doing, todo = counts(cards)
    total = len(cards)
    unassigned = [c for c in cards if not c["members"]]
    stages = sorted({c["stage"] for c in cards})
    names = {**{s: t for s, t in data["titles"].items() if t}, **stage_names}
    sorted_cards = sorted(cards, key=lambda c: (c["area"], c["status"] != TODO, c["pos"]))

    out = [f"<h1>{esc(title)}</h1>",
           f"<p class='sub'>Quadro “{esc(data['board'])}” · dados até {ref:%d/%m/%y} · {total} tarefas ativas</p>"]

    # Resumo
    kpis = [("Progresso geral", f"{pct(done, total)}%", f"{done} de {total} tarefas", ""),
            ("Concluídas", done, "", "done"), ("Em andamento", doing, "", "doing"),
            ("A fazer", todo, "", "todo"),
            ("Sem responsável", len(unassigned), f"{pct(len(unassigned), total)}% das tarefas", "")]
    out.append("<div class='kpis'>" + "".join(
        f"<div class='box'><div class='label'>" + (f"<i class='dot {cls}'></i>" if cls else "") + f"{esc(k)}</div>"
        f"<div class='big'>{esc(v)}</div><div class='muted'>{esc(s)}</div></div>"
        for k, v, s, cls in kpis) + "</div>")

    legend = ("<p class='legend'><i class='dot done'></i>Concluído <i class='dot doing'></i>Em andamento "
              "<i class='dot todo'></i>A fazer</p>")

    # Roteiro de entregas
    tiles = []
    for s in stages:
        d, g, t = counts([c for c in cards if c["stage"] == s])
        if d and not g and not t:
            badge = "<span class='badge ok'>✓ Concluída</span>"
        elif s == data["current"]:
            badge = "<span class='badge run'>● Em execução</span>"
        else:
            badge = "<span class='badge'>○ Planejada</span>"
        tiles.append(f"<div class='box stage'><div class='label caps'>Etapa {s}</div>"
                     f"<div class='stitle'>{esc(names.get(s, ''))}</div>"
                     f"<div class='row'><span class='big'>{pct(d, d + g + t)}%</span>{badge}</div>"
                     f"{bar(d, g, t)}<div class='muted'>{d} concluídas · {g} em andamento · {t} a fazer</div></div>")
    out.append("<section><h2>Roteiro de entregas</h2><p class='muted'>Cada etapa do projeto e o quanto já foi entregue.</p>"
               + legend + "<div class='stages'>" + "".join(tiles) + "</div></section>")

    # Etapa x Área
    head = "".join(f"<th>{esc(a)}</th>" for a in AREAS) + "<th>Total</th>"
    rows = []
    for s in stages:
        cells = []
        for a in list(range(len(AREAS))) + [None]:
            group = [c for c in cards if c["stage"] == s and (a is None or c["area"] == a)]
            if not group:
                cells.append("<td><div class='cell empty'>—</div></td>")
                continue
            d, g, t = counts(group)
            cells.append(f"<td><div class='cell'><div class='row'><span><b>{d}</b>/{len(group)}</span>"
                         f"<span class='muted'>{pct(d, len(group))}%</span></div>{bar(d, g, t)}</div></td>")
        rows.append(f"<tr><th class='rowh'>Etapa {s}<div class='muted'>{esc(names.get(s, ''))}</div></th>{''.join(cells)}</tr>")
    out.append("<section class='break'><h2>Estrutura do projeto: Etapa × Área</h2>"
               "<p class='muted'>Cada célula é um pacote de trabalho. O número mostra concluídos/total.</p>"
               f"<table class='matrix'><tr><th></th>{head}</tr>{''.join(rows)}</table></section>")

    # Andamento por pessoa
    people = []
    groups = [(name, [c for c in cards if mid in c["members"]])
              for mid, name in sorted(data["members"].items(), key=lambda m: m[1])]
    groups.append(("Sem responsável", unassigned))
    for name, group in groups:
        if not group:
            continue
        d, g, t = counts(group)
        doing_list = [c for c in sorted_cards if c["status"] == DOING and c in group] if name != "Sem responsável" else []
        people.append(f"<div class='person'><div class='row'><div class='pname'><b>{esc(name)}</b>"
                      f"<div class='muted'>{len(group)} tarefas · {g} em andamento</div></div>"
                      f"<div class='pbar'>{bar(d, g, t)}</div><b class='ppct'>{pct(d, len(group))}%</b></div>"
                      + (f"<ul>{card_items(doing_list, lambda c: '')}</ul>" if doing_list else "") + "</div>")
    out.append("<div class='two'><section><h2>Andamento por pessoa</h2>"
               "<p class='muted'>Tarefas atribuídas a cada um (uma tarefa com 2 pessoas conta para as duas). "
               "Abaixo do nome: o que está em andamento.</p>" + "".join(people) + "</section>")

    # Ritmo de entregas
    week, last_week = data["first_week"], (ref - timedelta(days=ref.weekday())).date()
    series = []
    while week <= last_week:
        series.append((week, data["weeks"].get(week, 0)))
        week += timedelta(days=7)
    peak = max((n for _, n in series), default=0) or 1
    cols = "".join(f"<div class='col'><span class='n'>{n or ''}</span><span class='v' style='height:{100 * n / peak:.1f}%'></span>"
                   f"<span class='x'>{w:%d/%m}</span></div>" for w, n in series)
    note = " O Trello exporta só as últimas 1000 ações, então o histórico é parcial." if data["partial_history"] else ""
    out.append("<section><h2>Ritmo de entregas</h2>"
               f"<p class='muted'>Tarefas movidas para “Feito” por semana.{note}</p>"
               f"<div class='chart'>{cols}</div></section></div>")

    # Pontos de atenção
    who = lambda c: ", ".join(data["members"].get(m, "?") for m in c["members"])
    stale = sorted([c for c in cards if c["status"] == DOING and (ref.date() - c["last"].date()).days > stale_days],
                   key=lambda c: (c["last"], c["pos"]))
    checked = [c for c in sorted_cards if c["status"] == TODO and c["checked"]]
    orphan = [c for c in sorted_cards if c["status"] == DOING and not c["members"]]
    boxes = [
        ("alert", "!", f"Em andamento, parados há +{stale_days} dias", stale,
         "Estão em “Fazendo…” sem movimento. Ainda estão ativos?",
         lambda c: f" · {who(c) or 'sem responsável'} · {(ref.date() - c['last'].date()).days} dias"),
        ("warn", "?", "Marcados ✓ mas ainda na lista da etapa", checked,
         "Têm o check de concluído no Trello, mas não foram movidos para “Feito”. Estão concluídos?",
         lambda c: f" · E{c['stage']}"),
        ("warn", "?", "Em andamento sem responsável", orphan, "Ninguém atribuído no cartão.", lambda c: ""),
    ]
    out.append("<section class='break'><h2>Pontos de atenção</h2><p class='muted'>O que merece uma conversa na próxima reunião.</p>"
               "<div class='three'>" + "".join(
                   f"<div class='box'><h3><i class='ic {cls}'>{icon}</i>{esc(t)} ({len(items)})</h3>"
                   f"<p class='muted'>{esc(desc)}</p><ul>{card_items(items, extra)}</ul></div>"
                   for cls, icon, t, items, desc, extra in boxes) + "</div></section>")

    pending = [c for c in sorted_cards if c["stage"] == data["current"] and c["status"] != DONE]
    out.append(f"<section><h2><i class='ic info'>→</i>O que falta para fechar a Etapa {data['current']} ({len(pending)})</h2>"
               "<p class='muted'>Pendências da etapa atual (a fazer + em andamento).</p>"
               "<ul class='cols3'>" + card_items(pending, lambda c: f" · {AREAS[c['area']]}"
                                                 + (" · em andamento" if c["status"] == DOING else "")) + "</ul></section>")

    return ("<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
            f"<title>{esc(title)}</title><style>{CSS}</style></head><body>{''.join(out)}</body></html>")


CSS = """
@page { size: A4 landscape; margin: 10mm; }
* { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: "Segoe UI", system-ui, sans-serif; color: #111; font-size: 11px; margin: 0; }
h1 { font-size: 22px; margin: 0 0 2px; } h2 { font-size: 15px; margin: 0 0 4px; }
h3 { font-size: 12px; margin: 0 0 4px; display: flex; align-items: center; gap: 6px; }
.sub, .muted { color: #555; } .muted { font-size: 10px; }
section, .box { border: 1px solid #ddd; border-radius: 10px; padding: 10px 12px; margin-bottom: 10px; break-inside: avoid; }
.break { break-before: page; }
.kpis { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin: 12px 0 10px; }
.kpis .box { margin: 0; } .label { color: #444; } .caps { text-transform: uppercase; letter-spacing: .5px; font-size: 10px; }
.big { font-size: 22px; font-weight: 700; }
.dot { display: inline-block; width: 9px; height: 9px; border-radius: 2px; margin: 0 4px 0 8px; }
.label .dot { margin-left: 0; } .done { background: #12a012; } .doing { background: #2b7bd6; } .todo { background: #d9d8d0; }
.legend { margin: 6px 0; }
.stages { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; }
.stage { margin: 0; } .stitle { font-weight: 600; min-height: 28px; }
.row { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.badge { background: #eee; border-radius: 10px; padding: 1px 7px; font-size: 10px; font-weight: 600; }
.badge.ok { background: #e3f4e3; color: #0a700a; } .badge.run { background: #e3eefa; color: #1d63b8; }
.bar { display: flex; height: 9px; border-radius: 5px; overflow: hidden; background: #d9d8d0; margin: 5px 0; gap: 1px; }
.bar span { display: block; height: 100%; }
.matrix { width: 100%; border-collapse: separate; border-spacing: 5px; }
.matrix th { text-align: left; font-weight: 600; } .rowh { width: 15%; }
.cell { border: 1px solid #ddd; border-radius: 6px; padding: 4px 6px; } .cell.empty { border-style: dashed; color: #999; height: 38px; }
.two { display: grid; grid-template-columns: 1.1fr 1fr; gap: 10px; align-items: start; }
.three { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; } .three .box { margin: 0; }
.person { margin: 8px 0; } .pname { width: 26%; } .pbar { flex: 1; } .ppct { width: 34px; text-align: right; }
ul { margin: 4px 0 0; padding-left: 16px; } li { margin: 1px 0; }
.cols3 { columns: 3; column-gap: 18px; }
.chart { display: flex; align-items: flex-end; gap: 4px; height: 170px; border-bottom: 1px solid #bbb; margin-top: 18px; }
.col { flex: 1; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; height: 100%; position: relative; }
.col .v { width: 70%; background: #12a012; border-radius: 3px 3px 0 0; } .col .n { font-size: 9px; color: #555; }
.col .x { position: absolute; bottom: -14px; font-size: 8px; color: #666; }
.ic { display: inline-flex; width: 16px; height: 16px; border-radius: 50%; color: #fff; font-style: normal; font-size: 10px;
      align-items: center; justify-content: center; margin-right: 6px; }
.ic.alert { background: #d33; } .ic.warn { background: #f0b400; } .ic.info { background: #2b7bd6; }
"""


# -----------------------------------------------------------------------------
# PDF
# -----------------------------------------------------------------------------
def find_browser():
    names = ["chrome", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "msedge"]
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    for base in (os.environ.get("PROGRAMFILES", ""), os.environ.get("PROGRAMFILES(X86)", ""),
                 os.environ.get("LOCALAPPDATA", "")):
        for rel in (r"Google\Chrome\Application\chrome.exe", r"Microsoft\Edge\Application\msedge.exe"):
            path = Path(base) / rel
            if base and path.exists():
                return str(path)
    return None


def print_pdf(browser, html_path, pdf_path):
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run([browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        f"--user-data-dir={profile}", f"--print-to-pdf={pdf_path}",
                        Path(html_path).resolve().as_uri()],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)


def main():
    parser = argparse.ArgumentParser(description="Gera o painel de progresso (PDF) a partir do .json exportado do Trello.")
    parser.add_argument("json", nargs="+", help="Arquivo(s) .json exportado(s) do Trello")
    parser.add_argument("--out", help="Pasta de saída (padrão: a pasta de cada .json)")
    parser.add_argument("--title", help="Título do painel (padrão: 'Painel · <nome do quadro>')")
    parser.add_argument("--stage-name", action="append", default=[], metavar="N=TEXTO",
                        help="Nome da etapa N (repita para várias). Padrão: tirado da lista de concluídos.")
    parser.add_argument("--stale-days", type=int, default=STALE_DAYS,
                        help=f"Dias sem movimento para alertar (padrão: {STALE_DAYS})")
    parser.add_argument("--html-only", action="store_true", help="Gera só o .html, sem PDF")
    args = parser.parse_args()
    sys.stdout.reconfigure(errors="replace")  # console do Windows sem UTF-8

    stage_names = {}
    for item in args.stage_name:
        number, _, text = item.partition("=")
        if not number.strip().isdigit() or not text.strip():
            parser.error(f"--stage-name inválido: {item!r} (use N=TEXTO)")
        stage_names[int(number)] = text.strip()

    browser = None if args.html_only else find_browser()
    if not args.html_only and not browser:
        print("ERRO: Chrome/Edge/Chromium não encontrado. Use --html-only e imprima o .html pelo navegador.")
        return 2

    for src in args.json:
        data = load_board(src)
        title = args.title or f"Painel · {data['board']}"
        out_dir = Path(args.out) if args.out else Path(src).resolve().parent
        out_dir.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^\w.-]+", "_", data["board"]).strip("_") or "quadro"
        base = out_dir / f"Painel_{safe}_{data['ref']:%Y-%m-%d}"
        html_path = base.with_suffix(".html")
        html_path.write_text(build_html(data, title, stage_names, args.stale_days), encoding="utf-8")
        if args.html_only:
            print(f"{src} -> {html_path}")
            continue
        pdf_path = base.with_suffix(".pdf")
        print_pdf(browser, html_path, pdf_path)
        html_path.unlink()
        print(f"{src} -> {pdf_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Gera o painel de progresso a partir do .json exportado do Trello: um .html
interativo (filtros por etapa, área, pessoa, situação e busca) e o PDF.

Só lê o arquivo exportado; não acessa o Trello. Mesma entrada, mesmo
resultado: as regras de classificação estão neste arquivo (ver guia.md).
O PDF é a impressão do próprio .html, sem filtros.

Uso:
    python trello_report.py export.json                 # .html + .pdf ao lado do .json
    python trello_report.py a.json b.json --out pasta   # um par por arquivo
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
    for c in cards:
        when = first_done.get(c["id"])
        c["done_week"] = (when - timedelta(days=when.weekday())).date().isoformat() if when else None
    first_week = min((parse_date(a["date"]) for a in actions), default=ref)
    first_week = (first_week - timedelta(days=first_week.weekday())).date()

    members = {m["id"]: m["fullName"].split()[0] for m in board.get("members", [])}
    return {"board": board["name"], "cards": cards, "current": current, "titles": titles,
            "ref": ref, "first_week": first_week, "members": members,
            "partial_history": len(actions) >= 1000}


# -----------------------------------------------------------------------------
# HTML (interativo na tela; o mesmo arquivo, sem filtros, vira o PDF)
# -----------------------------------------------------------------------------
def build_data(data, title, stage_names, stale_days):
    """Dados já classificados que o HTML usa. Contas e filtros ficam no JS."""
    ref = data["ref"]
    names = {**{s: t for s, t in data["titles"].items() if t}, **stage_names}
    ordered = sorted(data["cards"], key=lambda c: (c["area"], c["status"] != TODO, c["pos"]))
    week, last_week = data["first_week"], (ref - timedelta(days=ref.weekday())).date()
    weeks = []
    while week <= last_week:
        weeks.append(week.isoformat())
        week += timedelta(days=7)
    return {
        "title": title, "board": data["board"], "ref": f"{ref:%d/%m/%y}",
        "current": data["current"], "areas": AREAS, "staleDays": stale_days,
        "partialHistory": data["partial_history"], "weeks": weeks,
        "stages": [{"n": s, "name": names.get(s, "")} for s in sorted({c["stage"] for c in ordered})],
        "members": sorted(set(data["members"].values())),
        "cards": [{"name": c["name"], "stage": c["stage"], "area": c["area"], "status": c["status"],
                   "members": [data["members"].get(m, "?") for m in c["members"]],
                   "idle": (ref.date() - c["last"].date()).days, "checked": c["checked"],
                   "doneWeek": c["done_week"]} for c in ordered],
    }


def build_html(data, title, stage_names, stale_days):
    payload = json.dumps(build_data(data, title, stage_names, stale_days), ensure_ascii=False)
    payload = payload.replace("</", "<\\/")  # não fechar o <script> por acidente
    return ("<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body>"
            f"{FILTERS}<main id='app'></main>"
            f"<script id='data' type='application/json'>{payload}</script>"
            f"<script>{JS}</script></body></html>")


FILTERS = """
<form id="filters" class="no-print" onsubmit="return false">
  <label>Etapa <select id="f-stage"></select></label>
  <label>Área <select id="f-area"></select></label>
  <label>Pessoa <select id="f-person"></select></label>
  <label>Situação <select id="f-status">
    <option value="">Todas</option><option value="todo">A fazer</option>
    <option value="doing">Em andamento</option><option value="done">Concluído</option></select></label>
  <label class="grow">Busca <input id="f-q" type="search" placeholder="texto do cartão"></label>
  <button type="button" id="f-clear">Limpar</button>
  <button type="button" onclick="window.print()">Imprimir / PDF</button>
</form>
"""

JS = r"""
const D = JSON.parse(document.getElementById('data').textContent);
const STATUS = {todo: 'A fazer', doing: 'Em andamento', done: 'Concluído'};
const NONE = '__none__';
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const pct = (d, t) => t ? Math.round(100 * d / t) : 0;
const counts = cs => [cs.filter(c => c.status === 'done').length, cs.filter(c => c.status === 'doing').length, cs.filter(c => c.status === 'todo').length];
const stageName = n => (D.stages.find(s => s.n === n) || {}).name || '';
const bar = (d, g, t) => '<div class="bar">' + [[d, 'done'], [g, 'doing'], [t, 'todo']].filter(x => x[0])
  .map(([n, c]) => `<span class="${c}" style="width:${(100 * n / ((d + g + t) || 1)).toFixed(2)}%"></span>`).join('') + '</div>';
const items = (cs, extra) => cs.map(c => `<li>${esc(c.name)}<span class="muted">${extra(c)}</span></li>`).join('');
const legend = '<p class="legend"><i class="dot done"></i>Concluído <i class="dot doing"></i>Em andamento <i class="dot todo"></i>A fazer</p>';

const F = {stage: '', area: '', person: '', status: '', q: ''};
const opts = (sel, list) => { sel.innerHTML = list.map(([v, t]) => `<option value="${esc(v)}">${esc(t)}</option>`).join(''); };
opts(document.getElementById('f-stage'), [['', 'Todas'], ...D.stages.map(s => [s.n, `Etapa ${s.n}${s.name ? ' · ' + s.name : ''}`])]);
opts(document.getElementById('f-area'), [['', 'Todas'], ...D.areas.map((a, i) => [i, a])]);
opts(document.getElementById('f-person'), [['', 'Todas'], ...D.members.map(m => [m, m]), [NONE, 'Sem responsável']]);

function filtered() {
  const q = F.q.trim().toLowerCase();
  return D.cards.filter(c => (F.stage === '' || c.stage === +F.stage) && (F.area === '' || c.area === +F.area)
    && (F.person === '' || (F.person === NONE ? !c.members.length : c.members.includes(F.person)))
    && (F.status === '' || c.status === F.status) && (!q || c.name.toLowerCase().includes(q)));
}

function render() {
  const cs = filtered();
  const [done, doing, todo] = counts(cs);
  const total = cs.length;
  const unassigned = cs.filter(c => !c.members.length);
  const active = Object.values(F).some(v => v !== '');
  const out = [];

  out.push(`<h1>${esc(D.title)}</h1><p class="sub">Quadro “${esc(D.board)}” · dados até ${esc(D.ref)} · ${total} tarefas`
    + (active ? ' (filtradas)' : ' ativas') + '</p>');

  // Resumo
  const kpis = [['Progresso geral', pct(done, total) + '%', `${done} de ${total} tarefas`, ''], ['Concluídas', done, '', 'done'],
    ['Em andamento', doing, '', 'doing'], ['A fazer', todo, '', 'todo'],
    ['Sem responsável', unassigned.length, `${pct(unassigned.length, total)}% das tarefas`, '']];
  out.push('<div class="kpis">' + kpis.map(([k, v, s, cls]) => `<div class="box"><div class="label">${cls ? `<i class="dot ${cls}"></i>` : ''}${k}</div>`
    + `<div class="big">${v}</div><div class="muted">${s}</div></div>`).join('') + '</div>');

  // Roteiro de entregas
  const stages = D.stages.map(s => s.n).filter(n => cs.some(c => c.stage === n));
  const tiles = stages.map(n => {
    const all = D.cards.filter(c => c.stage === n), [ad, ag, at] = counts(all);
    const [d, g, t] = counts(cs.filter(c => c.stage === n));
    const badge = ad && !ag && !at ? '<span class="badge ok">✓ Concluída</span>'
      : n === D.current ? '<span class="badge run">● Em execução</span>' : '<span class="badge">○ Planejada</span>';
    return `<div class="box stage"><div class="label caps">Etapa ${n}</div><div class="stitle">${esc(stageName(n))}</div>`
      + `<div class="row"><span class="big">${pct(d, d + g + t)}%</span>${badge}</div>${bar(d, g, t)}`
      + `<div class="muted">${d} concluídas · ${g} em andamento · ${t} a fazer</div></div>`;
  });
  out.push('<section><h2>Roteiro de entregas</h2><p class="muted">Cada etapa do projeto e o quanto já foi entregue.</p>'
    + legend + `<div class="stages">${tiles.join('')}</div></section>`);

  // Etapa x Área
  const head = D.areas.map(a => `<th>${esc(a)}</th>`).join('') + '<th>Total</th>';
  const rows = stages.map(n => {
    const cells = [...D.areas.keys(), null].map(a => {
      const g = cs.filter(c => c.stage === n && (a === null || c.area === a));
      if (!g.length) return '<td><div class="cell empty">—</div></td>';
      const [d, gg, t] = counts(g);
      return `<td><div class="cell"><div class="row"><span><b>${d}</b>/${g.length}</span><span class="muted">${pct(d, g.length)}%</span></div>${bar(d, gg, t)}</div></td>`;
    }).join('');
    return `<tr><th class="rowh">Etapa ${n}<div class="muted">${esc(stageName(n))}</div></th>${cells}</tr>`;
  }).join('');
  out.push('<section class="break"><h2>Estrutura do projeto: Etapa × Área</h2>'
    + '<p class="muted">Cada célula é um pacote de trabalho. O número mostra concluídos/total.</p>'
    + `<table class="matrix"><tr><th></th>${head}</tr>${rows}</table></section>`);

  // Andamento por pessoa
  const groups = D.members.map(m => [m, cs.filter(c => c.members.includes(m))]).concat([['Sem responsável', unassigned]])
    .filter(([name]) => F.person === '' || name === F.person || (F.person === NONE && name === 'Sem responsável'));
  const people = groups.filter(([, g]) => g.length).map(([name, g]) => {
    const [d, gg, t] = counts(g);
    const doingList = name === 'Sem responsável' ? [] : g.filter(c => c.status === 'doing');
    return `<div class="person"><div class="row"><div class="pname"><b>${esc(name)}</b><div class="muted">${g.length} tarefas · ${gg} em andamento</div></div>`
      + `<div class="pbar">${bar(d, gg, t)}</div><b class="ppct">${pct(d, g.length)}%</b></div>`
      + (doingList.length ? `<ul>${items(doingList, () => '')}</ul>` : '') + '</div>';
  }).join('');
  out.push('<div class="two"><section><h2>Andamento por pessoa</h2><p class="muted">Tarefas atribuídas a cada um (uma tarefa com 2 pessoas conta para as duas). '
    + `Abaixo do nome: o que está em andamento.</p>${people}</section>`);

  // Ritmo de entregas
  const perWeek = D.weeks.map(w => [w, cs.filter(c => c.doneWeek === w).length]);
  const peak = Math.max(1, ...perWeek.map(x => x[1]));
  const cols = perWeek.map(([w, n]) => `<div class="col"><span class="n">${n || ''}</span><span class="v" style="height:${(100 * n / peak).toFixed(1)}%"></span>`
    + `<span class="x">${w.slice(8, 10)}/${w.slice(5, 7)}</span></div>`).join('');
  out.push('<section><h2>Ritmo de entregas</h2><p class="muted">Tarefas movidas para “Feito” por semana.'
    + (D.partialHistory ? ' O Trello exporta só as últimas 1000 ações, então o histórico é parcial.' : '')
    + `</p><div class="chart">${cols}</div></section></div>`);

  // Pontos de atenção
  const who = c => c.members.join(', ') || 'sem responsável';
  const stale = cs.filter(c => c.status === 'doing' && c.idle > D.staleDays).sort((a, b) => b.idle - a.idle);
  const checked = cs.filter(c => c.status === 'todo' && c.checked);
  const orphan = cs.filter(c => c.status === 'doing' && !c.members.length);
  const boxes = [['alert', '!', `Em andamento, parados há +${D.staleDays} dias`, stale, 'Estão em “Fazendo…” sem movimento. Ainda estão ativos?', c => ` · ${esc(who(c))} · ${c.idle} dias`],
    ['warn', '?', 'Marcados ✓ mas ainda na lista da etapa', checked, 'Têm o check de concluído no Trello, mas não foram movidos para “Feito”. Estão concluídos?', c => ` · E${c.stage}`],
    ['warn', '?', 'Em andamento sem responsável', orphan, 'Ninguém atribuído no cartão.', () => '']];
  out.push('<section class="break"><h2>Pontos de atenção</h2><p class="muted">O que merece uma conversa na próxima reunião.</p><div class="three">'
    + boxes.map(([cls, icon, t, list, desc, extra]) => `<div class="box"><h3><i class="ic ${cls}">${icon}</i>${esc(t)} (${list.length})</h3>`
      + `<p class="muted">${esc(desc)}</p><ul>${items(list, extra)}</ul></div>`).join('') + '</div></section>');

  // O que falta (etapa filtrada ou a atual)
  const target = F.stage === '' ? D.current : +F.stage;
  const pending = cs.filter(c => c.stage === target && c.status !== 'done');
  out.push(`<section><h2><i class="ic info">→</i>O que falta para fechar a Etapa ${target} (${pending.length})</h2>`
    + '<p class="muted">Pendências da etapa (a fazer + em andamento).</p><ul class="cols3">'
    + items(pending, c => ` · ${esc(D.areas[c.area])}` + (c.status === 'doing' ? ' · em andamento' : '')) + '</ul></section>');

  // Tarefas (só na tela)
  const trs = cs.map(c => `<tr><td>${esc(c.name)}</td><td>E${c.stage}</td><td>${esc(D.areas[c.area])}</td><td><i class="dot ${c.status}"></i>${STATUS[c.status]}</td>`
    + `<td>${esc(c.members.join(', ') || '—')}</td><td class="num">${c.status === 'done' ? '' : c.idle}</td></tr>`).join('');
  out.push(`<section class="no-print"><h2>Tarefas (${total})</h2><table class="tasks"><tr><th>Tarefa</th><th>Etapa</th><th>Área</th>`
    + `<th>Situação</th><th>Responsáveis</th><th class="num">Dias sem movimento</th></tr>${trs}</table></section>`);

  document.getElementById('app').innerHTML = out.join('');
}

for (const [key, id] of [['stage', 'f-stage'], ['area', 'f-area'], ['person', 'f-person'], ['status', 'f-status'], ['q', 'f-q']]) {
  document.getElementById(id).addEventListener('input', e => { F[key] = e.target.value; render(); });
}
document.getElementById('f-clear').addEventListener('click', () => {
  document.getElementById('filters').reset();
  for (const k in F) F[k] = '';
  render();
});
render();
"""


CSS = """
@page { size: A4 landscape; margin: 10mm; }
* { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: "Segoe UI", system-ui, sans-serif; color: #111; background: #fff; font-size: 11px; margin: 0; padding: 0 16px 16px; }
h1 { font-size: 22px; margin: 0 0 2px; } h2 { font-size: 15px; margin: 0 0 4px; }
h3 { font-size: 12px; margin: 0 0 4px; display: flex; align-items: center; gap: 6px; }
.sub, .muted { color: #555; } .muted { font-size: 10px; }
section, .box { border: 1px solid #ddd; border-radius: 10px; padding: 10px 12px; margin-bottom: 10px; break-inside: avoid; }
.kpis { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin: 12px 0 10px; }
.kpis .box { margin: 0; } .label { color: #444; } .caps { text-transform: uppercase; letter-spacing: .5px; font-size: 10px; }
.big { font-size: 22px; font-weight: 700; }
.dot { display: inline-block; width: 9px; height: 9px; border-radius: 2px; margin: 0 4px 0 8px; }
.label .dot, td .dot { margin-left: 0; } .done { background: #12a012; } .doing { background: #2b7bd6; } .todo { background: #d9d8d0; }
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
.chart { display: flex; align-items: flex-end; gap: 4px; height: 170px; border-bottom: 1px solid #bbb; margin: 18px 0 14px; }
.col { flex: 1; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; height: 100%; position: relative; }
.col .v { width: 70%; background: #12a012; border-radius: 3px 3px 0 0; } .col .n { font-size: 9px; color: #555; }
.col .x { position: absolute; bottom: -14px; font-size: 8px; color: #666; }
.ic { display: inline-flex; width: 16px; height: 16px; border-radius: 50%; color: #fff; font-style: normal; font-size: 10px;
      align-items: center; justify-content: center; margin-right: 6px; }
.ic.alert { background: #d33; } .ic.warn { background: #f0b400; } .ic.info { background: #2b7bd6; }
#filters { position: sticky; top: 0; z-index: 1; display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: end;
           background: #f5f5f2; border-bottom: 1px solid #ddd; margin: 0 -16px 12px; padding: 10px 16px; font-size: 12px; }
#filters label { display: flex; flex-direction: column; gap: 2px; color: #444; } #filters .grow { flex: 1; min-width: 160px; }
#filters select, #filters input, #filters button { font: inherit; padding: 4px 6px; border: 1px solid #bbb; border-radius: 6px; background: #fff; }
#filters button { cursor: pointer; }
.tasks { width: 100%; border-collapse: collapse; } .tasks th, .tasks td { text-align: left; padding: 4px 6px; border-bottom: 1px solid #eee; }
.tasks th { position: sticky; top: 0; background: #fff; } .num { text-align: right; }
@media screen { body { font-size: 12px; } }
@media screen and (max-width: 800px) {
  .kpis, .two, .three { grid-template-columns: 1fr; } .cols3 { columns: 1; } .matrix { display: block; overflow-x: auto; }
}
@media print { .no-print { display: none !important; } body { padding: 0; } .break { break-before: page; } }
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
    parser = argparse.ArgumentParser(description="Gera o painel de progresso (.html interativo + PDF) a partir do .json exportado do Trello.")
    parser.add_argument("json", nargs="+", help="Arquivo(s) .json exportado(s) do Trello")
    parser.add_argument("--out", help="Pasta de saída (padrão: a pasta de cada .json)")
    parser.add_argument("--title", help="Título do painel (padrão: 'Painel · <nome do quadro>')")
    parser.add_argument("--stage-name", action="append", default=[], metavar="N=TEXTO",
                        help="Nome da etapa N (repita para várias). Padrão: tirado da lista de concluídos.")
    parser.add_argument("--stale-days", type=int, default=STALE_DAYS,
                        help=f"Dias sem movimento para alertar (padrão: {STALE_DAYS})")
    parser.add_argument("--html-only", action="store_true", help="Gera só o .html interativo, sem PDF")
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
        html_path, pdf_path = generate(src, browser, args.out, args.title, stage_names, args.stale_days)
        print(f"{src} -> {html_path}" + (f" e {pdf_path}" if pdf_path else ""))
    return 0


def generate(src, browser=None, out=None, title=None, stage_names=None, stale_days=STALE_DAYS):
    """Gera o painel de um .json: devolve (html interativo, pdf ou None sem browser)."""
    data = load_board(src)
    title = title or f"Painel · {data['board']}"
    out_dir = Path(out) if out else Path(src).resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w.-]+", "_", data["board"]).strip("_") or "quadro"
    base = out_dir / f"Painel_{safe}_{data['ref']:%Y-%m-%d}"
    html_path = base.with_suffix(".html")
    html_path.write_text(build_html(data, title, stage_names or {}, stale_days), encoding="utf-8")
    if not browser:
        return html_path, None
    pdf_path = base.with_suffix(".pdf")
    print_pdf(browser, html_path, pdf_path)
    return html_path, pdf_path


if __name__ == "__main__":
    sys.exit(main())

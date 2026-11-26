# Painel de progresso a partir do Trello

O `trello_report.py` lê o `.json` exportado de um quadro do Trello e gera um PDF de progresso, pronto para imprimir ou compartilhar. Ele não acessa o Trello nem altera nada: só lê o arquivo. As regras de classificação estão no próprio script, então o mesmo `.json` gera sempre o mesmo painel.

## Pré-requisitos

- Python 3.9+ (só biblioteca padrão).
- Chrome, Edge ou Chromium instalado: o script usa o navegador em modo headless para imprimir o PDF. Sem navegador, use `--html-only` e imprima o `.html` pelo navegador (Ctrl+P → Salvar como PDF, paisagem).

## Rotina de atualização

1. No Trello, abra o quadro → Menu → Imprimir, exportar e compartilhar → Exportar como JSON. Salve o arquivo.
2. Gere o PDF pela janela ou pela linha de comando (abaixo).

### Pela janela

Abra o `trello_report_gui.pyw` (duplo clique, ou `pythonw scripts/trello/trello_report_gui.pyw`). No campo, cole o arquivo (copie o `.json` no Explorer com Ctrl+C e cole com Ctrl+V; também aceita o caminho como texto) ou use **Procurar…**. Clique em **Gerar PDF**: o PDF é gerado ao lado do `.json` e aberto em seguida. A janela usa as regras padrão; as opções abaixo são só da linha de comando.

Se o duplo clique não abrir o Python (extensão `.pyw` sem associação), crie um atalho com destino `<pasta do Python>\pythonw.exe "<repo>\scripts\trello\trello_report_gui.pyw"`.

### Pela linha de comando

```bash
python scripts/trello/trello_report.py ~/Downloads/quadro.json
```

O PDF sai na mesma pasta do `.json`, com o nome `Painel_<quadro>_<AAAA-MM-DD>.pdf` (data da última ação registrada no export).

Opções:

| Opção | Efeito |
| --- | --- |
| `--out PASTA` | Grava os PDFs em outra pasta. |
| `--title TEXTO` | Título do painel (padrão: `Painel · <nome do quadro>`). |
| `--stage-name N=TEXTO` | Nome da etapa N; repita para várias (ex.: `--stage-name "3=Piloto"`). |
| `--stale-days N` | Dias sem movimento para o alerta de parados (padrão: 30). |
| `--html-only` | Gera só o `.html`, sem PDF. |

Vários `.json` de uma vez geram um PDF para cada um, o que serve para comparar a evolução entre exports.

Os `.json` e os PDFs têm dados internos do projeto: não versione (o `.gitignore` desta pasta já ignora `*.json`, `*.pdf` e `*.html`).

## O que entra no painel

Só cartões abertos em listas abertas. Cada lista é classificada pelo nome:

| Nome da lista | Situação dos cartões | Etapa |
| --- | --- | --- |
| começa com `Feito` | concluído | número de `Etapa#N` no nome; sem número, a etapa atual |
| começa com `Fazendo` | em andamento | etapa atual |
| contém `Etapa#N` e `CONCLU` | concluído | N |
| contém `Etapa#N` | a fazer | N |
| outras (ex.: fixos, futuro) | fora do painel | — |

A **etapa atual** é a menor etapa que ainda tem cartão a fazer.

**Área** de cada cartão:

- Cartão a fazer: pela lista (`Planejamento`, `Hardware`/`Mecânica`, `Firmware`, `BACK`, `FRONT` no nome).
- Concluído ou em andamento: pelo primeiro prefixo reconhecido entre colchetes no nome do cartão: `PLN`/`ORG` → Planejamento, `HW`/`MEC` → Hardware / Mecânica, `FW` → Firmware, `BACK`/`SRV` → Back-end, `FRONT`/`APP` → Front-end. Ex.: `[HW/TG] ...` → Hardware; `[SRV/BACK] ...` → Back-end.
- Sem prefixo reconhecido: Planejamento.

**Nome da etapa**: o texto depois de ` - ` na lista de concluídos da etapa (ex.: `Feito Etapa#2 - Protótipo` → "Protótipo"). Etapa sem lista de concluídos fica sem nome, a menos que se passe `--stage-name`.

## Seções do PDF

- **Resumo**: progresso geral (concluídas ÷ total), concluídas, em andamento, a fazer e sem responsável.
- **Roteiro de entregas**: uma caixa por etapa com % concluído e situação: Concluída (tudo feito), Em execução (etapa atual) ou Planejada.
- **Etapa × Área**: concluídos/total de cada pacote de trabalho.
- **Andamento por pessoa**: tarefas por membro (cartão com duas pessoas conta para as duas) e o que cada um tem em andamento; por último, os cartões sem responsável.
- **Ritmo de entregas**: cartões que entraram numa lista `Feito` por semana (segunda a domingo, horário de Brasília), contando só a primeira entrada de cada cartão. O Trello exporta no máximo as últimas 1000 ações; quando o export bate nesse limite, o painel avisa que o histórico é parcial.
- **Pontos de atenção**:
  - em andamento sem movimento há mais de `--stale-days` dias (diferença de datas entre a última atividade do cartão e a última ação do export);
  - marcados como concluídos (check da data de entrega) mas ainda numa lista a fazer;
  - em andamento sem responsável.
- **O que falta para fechar a etapa atual**: a fazer + em andamento da etapa atual, por área.

## Mudando as regras

Prefixos e palavras de área ficam nas constantes `PREFIX_AREA` e `LIST_AREA` no topo do script; a classificação das listas, em `list_status`. Ao mudar uma regra, atualize esta seção.

# Painel de progresso a partir do Trello

O `trello_report.py` lê o `.json` exportado de um quadro do Trello e gera o painel de progresso: um `.html` interativo, com filtros, e um PDF pronto para imprimir ou compartilhar. O PDF é a impressão do próprio `.html`, sem filtros, então os dois mostram sempre o mesmo. Ele não acessa o Trello nem altera nada: só lê o arquivo. As regras de classificação estão no próprio script, então o mesmo `.json` gera sempre o mesmo painel.

| Arquivo | Para quê |
| --- | --- |
| `trello_report.py` | Script principal: lê o `.json` e gera o `.html` (e o PDF, pela linha de comando). |
| `trello_report_gui.pyw` | Janela e "Abrir com": cole o JSON ou abra o `.json` e o painel abre no navegador. É a base do executável. |

## Uso pelo executável (Windows, sem Python)

O executável **Painel MakTrak.exe** é a janela empacotada com o Python dentro: quem usa não precisa instalar nada. Ele é distribuído por uma pasta compartilhada, não pelo repositório (ver "Gerando o executável").

**Primeira vez (uma vez por computador):**

1. Baixe o `Painel MakTrak.exe` da pasta compartilhada e abra. Como o executável não tem assinatura digital, o navegador avisa que ele "normalmente não é baixado" e o Windows pode mostrar "O Windows protegeu o computador" (**Mais informações → Executar assim mesmo**). É o aviso padrão para programa interno sem assinatura, não detecção de vírus.
2. No rodapé da janela, clique em **Usar para abrir arquivos .json**. O programa é copiado para `%LOCALAPPDATA%\Painel MakTrak\` e cadastrado no "Abrir com" dos `.json`, só para o usuário atual (sem administrador). Depois disso, o arquivo baixado pode ser apagado.

**No dia a dia**, qualquer um dos dois caminhos:

- **Abrir com:** no Trello, abra o quadro → Menu (⋯) → Imprimir, exportar e compartilhar → **Exportar como JSON** e baixe o arquivo. No Explorer, botão direito no `.json` → **Abrir com** → **Painel MakTrak**. O painel abre no navegador.
- **Colar:** abra o Painel MakTrak e aperte Ctrl+V no campo com o JSON copiado: o texto da página "Exportar como JSON" (Ctrl+A, Ctrl+C) ou o arquivo `.json` copiado no Explorer. Também há o botão **Procurar…**.

O painel (`.html`) é gravado na pasta Downloads de quem usa e abre no navegador. O PDF sai pelo botão **Imprimir / PDF** do painel.

Marcar **Sempre** no "Abrir com" faz **todo** `.json` do computador abrir com o Painel MakTrak; um `.json` que não seja do Trello mostra uma mensagem de erro. Quem lida com outros `.json` deve usar o "Abrir com" sem marcar "Sempre".

Quando sair uma versão nova do executável, repita a primeira vez (baixar, abrir, clicar no botão) para substituir a cópia cadastrada.

## Uso pelo Python

Pré-requisitos: Python 3.9+ (só biblioteca padrão) e Chrome, Edge ou Chromium instalado para o PDF (o script usa o navegador em modo headless). Sem navegador, use `--html-only` e imprima pelo botão **Imprimir / PDF** do `.html`.

### Pela janela

`pythonw scripts/trello/trello_report_gui.pyw` abre a mesma janela do executável. Argumentos opcionais:

| Argumento | Efeito |
| --- | --- |
| `<arquivo>.json` | Gera e abre o painel direto, sem janela (é o que o "Abrir com" usa). |
| `<pasta>` | Grava o painel nessa pasta em vez de Downloads. |
| `--registrar` | Cadastra o programa no "Abrir com" dos `.json` (o mesmo do botão). |

### Pela linha de comando

```bash
python scripts/trello/trello_report.py ~/Downloads/quadro.json
```

O `.html` e o PDF saem na mesma pasta do `.json`, com o nome `Painel_<quadro>_<AAAA-MM-DD>` (data da última ação registrada no export).

| Opção | Efeito |
| --- | --- |
| `--out PASTA` | Grava os arquivos em outra pasta. |
| `--title TEXTO` | Título do painel (padrão: `Painel · <nome do quadro>`). |
| `--stage-name N=TEXTO` | Nome da etapa N; repita para várias (ex.: `--stage-name "3=Piloto"`). |
| `--stale-days N` | Dias sem movimento para o alerta de parados (padrão: 30). |
| `--html-only` | Gera só o `.html` interativo, sem PDF. |

Vários `.json` de uma vez geram um painel para cada um, o que serve para comparar a evolução entre exports.

Os `.json`, `.html` e PDFs têm dados internos do projeto: não versione (o `.gitignore` desta pasta já os ignora, junto com os arquivos de build do executável).

## Gerando o executável

O executável é gerado com o [PyInstaller](https://pyinstaller.org), num ambiente virtual separado (ele é ferramenta de build, não dependência do script). Na pasta `scripts/trello`, no Windows:

```bash
python -m venv %TEMP%\painel-build
%TEMP%\painel-build\Scripts\python -m pip install pyinstaller
%TEMP%\painel-build\Scripts\python -m PyInstaller --onefile --windowed --name "Painel MakTrak" --paths . --distpath %TEMP%\painel-build\dist --workpath %TEMP%\painel-build\work --specpath %TEMP%\painel-build trello_report_gui.pyw
```

O resultado é `%TEMP%\painel-build\dist\Painel MakTrak.exe` (cerca de 12 MB). Substitua o arquivo na pasta compartilhada. O executável não vai para o repositório: é gerado a partir dos scripts.

## Filtros (no `.html`)

No topo do `.html` ficam os filtros: **Etapa**, **Área**, **Pessoa** (inclui "Sem responsável"), **Situação** (a fazer, em andamento, concluído) e **Busca** por texto no nome do cartão. Os filtros se combinam, e todas as seções se recalculam só com os cartões filtrados. Exceção: o selo da etapa (Concluída, Em execução, Planejada) considera sempre a etapa inteira. Com uma etapa filtrada, "O que falta" mostra essa etapa em vez da atual.

O `.html` tem ainda a seção **Tarefas**, só na tela: a lista dos cartões filtrados, com etapa, área, situação, responsáveis e dias sem movimento. O botão **Imprimir / PDF** imprime o que está na tela, com os filtros aplicados; a barra de filtros e a lista de tarefas não saem na impressão.

O `.html` é um arquivo só, sem dependências: abre offline em qualquer navegador. A prévia do Google Drive não executa `.html` (mostra o código): baixe o arquivo e abra no navegador.

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

## Seções do painel

- **Resumo**: progresso geral (concluídas ÷ total), concluídas, em andamento, a fazer e sem responsável.
- **Roteiro de entregas**: uma caixa por etapa com % concluído e situação: Concluída (tudo feito), Em execução (etapa atual) ou Planejada.
- **Etapa × Área**: concluídos/total de cada pacote de trabalho.
- **Andamento por pessoa**: tarefas por membro (cartão com duas pessoas conta para as duas) e o que cada um tem em andamento; por último, os cartões sem responsável.
- **Ritmo de entregas**: cartões do painel que entraram numa lista `Feito`, por semana (segunda a domingo, horário de Brasília), contando só a primeira entrada de cada cartão. O Trello exporta no máximo as últimas 1000 ações; quando o export bate nesse limite, o painel avisa que o histórico é parcial.
- **Pontos de atenção**:
  - em andamento sem movimento há mais de `--stale-days` dias (diferença de datas entre a última atividade do cartão e a última ação do export);
  - marcados como concluídos (check da data de entrega) mas ainda numa lista a fazer;
  - em andamento sem responsável.
- **O que falta para fechar a etapa atual**: a fazer + em andamento da etapa atual, por área.

## Mudando as regras

Prefixos e palavras de área ficam nas constantes `PREFIX_AREA` e `LIST_AREA` no topo do `trello_report.py`; a classificação das listas, em `list_status`. Ao mudar uma regra, atualize esta seção e gere o executável de novo.

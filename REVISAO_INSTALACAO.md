# Revisão — instalação e deploy em máquina limpa

- **Data:** 2026-10-26
- **Repositórios:** `maktrak-ambiente` e `maktrak-server` (`8f8da7d`), branch `MAK-22-Automatizar-deploy`
- **Objetivo:** verificar se o caminho de instalação funciona numa máquina nova, sem passos manuais
- **Status:** sem bloqueadores em aberto; restam melhorias (M1, M3, M4).

---

## 1. Método

Leitura integral dos quatro pontos de entrada do fluxo, conferência das dependências de
cada etapa e validação cruzada com o teste já realizado na VM `10.0.0.162`
(instalação, endpoints, deploy real, bump de versão, preservação de dados).

Arquivos analisados:

| Arquivo | Repo | Papel |
|---|---|---|
| `setup-linux.sh` | ambiente | bootstrap Linux: garante Python 3 e baixa o instalador |
| `setup_windows.ps1` | ambiente | bootstrap Windows: garante Python 3 e baixa o instalador |
| `maktrak_setup.py` | ambiente | orquestrador: escolhe modo `dev`/`prod` e delega |
| `server_setup.py` | ambiente | bootstrap de produção: clona o servidor e chama o instalador |
| `install_server.py` | server | cria venv, instala o serviço e valida |
| `deploy/server/systemd/maktrak-server.service` | server | unit systemd (template) |
| `do_deploy.py` | server | empacota `exec/` e envia o deploy |

---

## 2. Fluxo atual

```
setup-linux.sh [ref]
  └─ garante python3 (apt/brew)
  └─ baixa maktrak_setup.py da ref  →  exporta MAKTRAK_REF
        └─ modo dev  → instala ferramentas e clona os repos de dev
        └─ modo prod → baixa server_setup.py (mesma ref, fallback main)
              └─ confere git + SO
              └─ clona maktrak-server (raso) em ~/maktrak-server
                    └─ executa install_server.py do clone
                          └─ cria venv ~/.venvs/maktrak-server + dependências
                             (apt: python3-venv, net-tools)
                          └─ grava unit a partir do template
                          └─ systemctl enable + restart
                          └─ health check: GET /moving + POST /maktrak/deploy
```

Na VM o fluxo chegou ao fim e o serviço respondeu corretamente. O que segue são os pontos
em que **outra** máquina (mais limpa) falha, e os riscos que permanecem mesmo quando o
fluxo conclui.

---

## 3. Problemas menores

| # | Local | Problema | Efeito |
|---|---|---|---|
| M1 | `install_server.py:93-114` | `sudo` não é validado antes da sequência systemctl | Falha genérica "Falha ao gravar a unit (sudo?)" |
| M2 | `install_server.py:70-75` | `pip install` sem versões fixas | Instalação não reprodutível; já traz aviso de depreciação do Starlette |
| M3 | `install_server.py` | Não verifica se a porta está livre | Se 8000 estiver ocupada, o serviço entra em loop de restart |
| M4 | `install_server.py:132-146` | Windows usa `schtasks /SC ONSTART` (sem restart) | Crash não recupera sozinho, ao contrário do `Restart=always` no Linux |
| M5 | `install_server.py:139` | Windows roda como `SYSTEM` | Bancos criados com dono `SYSTEM` dentro da pasta do usuário |
| M6 | `install_server.py` + `repo_setup.py` | Venv compartilhado (`~/.venvs/maktrak-server`) entre dev e prod | Conflito de dependências se os dois modos coexistirem na mesma máquina |
| M7 | `install_server.py:216` | Mensagem de alvo inválido não sugere `--target` | Diagnóstico mais lento |

---

## 4. Riscos residuais (decisão de projeto, não bug)

| # | Risco | Observação |
|---|---|---|
| R1 | `--extern` sem autenticação | Endpoint de deploy aceita código arbitrário na rede; previsto para a Fase 4 |
| R2 | Deploy valida sintaxe, não import/startup | Código que compila mas falha ao subir retorna `200`; o `Restart=always` entra em loop até o limite do systemd e o serviço fica `failed` |
| R3 | Ref móvel no bootstrap (`main`) | Código executado muda sem aviso; para produção convém fixar tag e, se possível, hash |
| R4 | Downgrade permitido | Não há comparação entre versão instalada e versão do pacote |
| R5 | Aviso de depreciação do Starlette | `HTTP_422_UNPROCESSABLE_ENTITY`; cosmético, pré-existente em `main.py` e `deploy_server.py` |

---

## 5. Cobertura de testes hoje

**`maktrak-ambiente`** — 29 testes: seleção de modo, catálogos, delegação,
clone/atualização, falha de clone por causa (credencial, rede, branch, pasta
ocupada), ambiente do git, token e `_ensure_git()`.

**`maktrak-server`** — bloco de deploy dentro de `test_server.py`:

| Teste | Cobre |
|---|---|
| `testar_install_server` | flags (`--extern`/`--local`) e unit com `--aceitar-deploy` |
| `testar_estado_do_servidor` | `estado_servidor` e `corpo_status` |
| `testar_aplicar_pacote` | troca atômica, rollback, sintaxe, `cwd` |
| `testar_limites_pacote` | corpo, membros, descompactado, compressão |
| `testar_deploy_concorrente` | `409` sem ler o corpo |
| `testar_deploy_nao_bloqueia_loop` | threadpool |
| `testar_deploy_e2e` | `POST` + restart + stub `999.999` |

O teste de `install_server.py` compara a unit e o `.cmd` do Windows com a mesma
função de argumentos, o que impede a divergência entre os dois caminhos.

---

## 6. O que já está validado

Executado contra `10.0.0.162:8000` (VM com o código desta branch):

- `GET /moving` → `200`, `status: online`, `code: 0`, `version`, `build`, `installed_at`
- `GET /docs` → `200`; rota inexistente → `404` sem corpo
- `v0.1/dados`, `POST /v0.2/event` (`201`), `PUT /v0.2/getevents`, `POST /v0.2/geolocation` (`201`)
- Deploy: corpo vazio → `422`; não-zip → `422 INVALID_MIME`; 200 KB → `400 PAYLOAD_TOO_LARGE`
- Deploy real: `200`, `build` trocado, `journalctl` com `Finished`/`Started`
- Bump `0.1.0 → 0.1.1` refletido em `/moving`
- Bancos preservados (`xibonga = 1234` antes e depois; sem re-seed nos restarts)

---

## 7. Correções propostas

| Prioridade | Item | Arquivo | Esforço |
|---|---|---|---|
| P2 | M1 — validar `sudo` antes | `install_server.py` | ~4 linhas |
| P2 | M3 — checar porta livre | `install_server.py` | ~6 linhas |
| P2 | M4 — restart no Windows | `install_server.py` | ~15 linhas (mais complexo) |

---

## 8. Checklist para o teste manual

Sem pré-requisitos: `git`, `python3-venv` e `net-tools` (para `ifconfig`/
`netstat`) são instalados pelo próprio fluxo.

**Instalação**

```bash
wget -q https://raw.githubusercontent.com/MovingMAK/maktrak-ambiente/MAK-22-Automatizar-deploy/setup-linux.sh -O /tmp/setup-linux.sh
bash /tmp/setup-linux.sh MAK-22-Automatizar-deploy
```

Esperado ao final: `✅ GET …/moving: online` e `✅ POST /maktrak/deploy: habilitado`.

**Verificações**

- [ ] `systemctl status maktrak-server` ativo
- [ ] `systemctl is-enabled maktrak-server` → `enabled`
- [ ] `curl /moving` responde `online`
- [ ] `journalctl` mostra `Endpoint de deploy habilitado`
- [ ] reboot → serviço volta sozinho
- [ ] `kill -9` no PID → `Restart=always` reergue em ~3 s
- [ ] `do_deploy.py --host <ip>:8000` → `200` com `build` novo
- [ ] bancos preservados após deploy (sem re-seed)
- [ ] zip inválido, sem `VERSION`, corpo grande e `main.py` inválido → erros esperados sem parar o serviço

---

## 9. Conclusão

O desenho está correto e sem bloqueadores: as dependências de bootstrap (`git`,
`python3-venv`) são garantidas de forma idempotente antes de qualquer pergunta, os
argumentos do serviço têm uma única fonte para Linux e Windows e a falha ao obter o
código já aponta a causa real (credencial, rede, branch ou pasta ocupada).

O que resta são ajustes de robustez do instalador (`M1`, `M3`, `M4`), sem impacto no
funcionamento atual.

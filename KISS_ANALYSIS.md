# Análise de Simplificação — `maktrak_setup.py`

> Princípio KISS: manter funcionalidade, remover complexidade desnecessária.

---

## 1. `select_dev_components()` e `select_prod_components()` — Duplicação quase total

**Problema**: As duas funções são idênticas, só mudam `DEV_MODULES` vs `PROD_MODULES` e o texto "Development" vs "Production".

**Simplificação**: Unificar em `_select_components(items, label)`:

```python
def _select_components(items_dict, label):
    categories = list(items_dict.keys())
    print(f"\n--- Select {label} Components ---")
    for i, cat in enumerate(categories, 1):
        print(f"{i}. {cat}")
    print(f"{len(categories) + 1}. todos (all)")

    choice = input("Enter your choice (comma-separated): ").strip()
    if choice == str(len(categories) + 1):
        return categories
    result = []
    for c in choice.split(","):
        try:
            idx = int(c.strip()) - 1
            if 0 <= idx < len(categories):
                result.append(categories[idx])
        except ValueError:
            pass
    return result
```

**Ganho**: ~40 linhas a menos, manutenção centralizada.

---

## 2. `select_mode()` — Estrutura verbosa

**Problema**: 17 linhas para escolher entre 2 opções.

**Simplificação**: `while True` + dicionário:

```python
def select_mode():
    while True:
        c = input("\nMode? (1=dev, 2=prod): ").strip()
        if c in ("1", "2"):
            return "dev" if c == "1" else "prod"
        print("Invalid.")
```

**Ganho**: ~10 linhas a menos, legibilidade mantida.

---

## 3. `get_software_for_components()` — Bloco `if/elif` desnecessário

**Problema**: O parâmetro `mode` é usado para selecionar entre `DEV_MODULES` e `PROD_MODULES`, mas a função sempre itera sobre `DEV_MODULES.values()` nas duas branches.

**Simplificação**: Selecionar o dicionário fonte com um operador ternário:

```python
def get_software_for_components(components, mode):
    source = DEV_MODULES if mode == "dev" else PROD_MODULES
    software = set()
    for c in components:
        software.update(source.get(c, []))
    return sorted(software)
```

**Ganho**: 4 linhas a menos, sem `if/elif`.

---

## 4. `find_sublime_merge_executable()` — Print repetido

**Problema**: Os prints `✓ Sublime Merge detected at:` duplicam a mesma string para `isabs` e `shutil.which`.

**Simplificação**: Extrair o print para depois da detecção:

```python
def find_sublime_merge_executable():
    ...
    for candidate in candidates:
        if os.path.isabs(candidate) and os.path.exists(candidate):
            path = candidate
            break
        path = shutil.which(candidate)
        if path:
            break
    if path:
        print(f"✓ Sublime Merge detected at: {path}")
        return path
    ...
```

**Ganho**: 4 linhas a menos, sem duplicação de string.

---

## 5. `UPDATE_OS = True` — Constante inútil

**Problema**: `UPDATE_OS` é sempre `True`, nunca é alterado. Aparece em `confirm_actions()` como `{'yes' if UPDATE_OS else 'no'}` que sempre mostra "yes".

**Simplificação**: Remover a variável e hardcodar "yes" (ou remover a linha do sumário, já que atualizar o OS é sempre feito).

**Ganho**: 1 linha de config + simplificação em `confirm_actions`.

---

## 6. `get_repositories_for_components()` vs `DEV_REPOSITORIES` — Indireção extra

**Problema**: As categorias `mecanica` e `eletronica` apontam ambas para `"hardware"`, mas a função é usada apenas em `dev` mode. O dicionário `DEV_REPOSITORIES` é uma camada de indireção que poderia ser incorporada ao `DEV_MODULES`.

**Alternativa KISS**: Colocar os repositórios como parte de cada entry no dicionário de módulos, ou manter separado mas é aceitável. A indireção atual não é grave.

**Veredito**: Manter como está — a separação é útil para clareza.

---

## 7. `clone_repository()` — Blocos `if/else` profundos com retorno

**Problema**: A função tem `if/else` aninhados com múltiplos `return`, dificultando o fluxo. O tratamento de "diretório vazio após clone falho" é específico e poderia ser extraído.

**Simplificação**: Usar guard clauses (early returns) para achatar a estrutura:

```python
def clone_repository(repo_name, repo_url):
    dest = get_clone_destination(repo_name)
    if not dest.exists():
        return _clone_new(repo_name, repo_url, dest)
    if not (dest / ".git").exists():
        print(f"✗ {dest} exists but is not a git repository")
        return False
    print(f"Repository already exists: {dest}")
    return _pull_existing(repo_name, dest)
```

**Ganho**: 3 funções pequenas com responsabilidade única.

---

## 8. `setup_android_sdk()` — Função monolítica de ~100 linhas

**Problema**: A função faz tudo: JDK, KVM, licenças, SDK path, cmdline-tools, AVDs. Difícil de seguir e testar.

**Simplificação**: Cada passo já está comentado (`# 1.`, `# 2.`...) — extrair para funções privadas:

```python
def setup_android_sdk():
    _android_install_jdk()
    _android_setup_kvm()
    _android_accept_licenses()
    sdk_root = _get_android_sdk_path()
    if not sdk_root: return False
    _android_install_sdk(sdk_root)
    _android_create_avds(sdk_root)
    return True
```

**Ganho**: 6 funções pequenas, cada uma testável isoladamente.

---

## 9. `_get_android_sdk_path()` — Fallback frágil

**Problema**: `candidates[2] if candidates[2] else ...` — o índice 2 (`~/Android/Sdk`) pode ser `None` se `ANDROID_HOME` for `None` mas `ANDROID_SDK_ROOT` estiver definido. A indexação é confusa.

**Simplificação**:

```python
for c in candidates:
    if c and os.path.isdir(c):
        return c
return str(Path.home() / "Android" / "Sdk")  # best-effort fallback
```

**Ganho**: Remove indexação mágica, mais legível.

---

## 10. `install_git()` e `install_sublime_merge()` — Estrutura duplicada

**Problema**: Ambas montam comandos por OS e chamam `run_install_command()`. O padrão é repetido.

**Simplificação**: Extrair para uma factory:

```python
_INSTALLERS = {
    ("git", "windows"): ["winget", "install", "--id", "Git.Git", "-e", ...],
    ("git", "linux"):   ["sudo", "apt", "install", "-y", "git"],
    ("sublime-merge", "windows"): [...],
    ("sublime-merge", "linux"):   [...],
}

def _install_package(name, os_type):
    cmd = _INSTALLERS.get((name, os_type))
    if not cmd:
        print(f"✗ No installer for {name} on {os_type}")
        return False
    return run_install_command(cmd, os_type, name)
```

**Ganho**: `install_git()` e `install_sublime_merge()` viram chamadas de 1 linha cada. ~30 linhas a menos.

---

## 11. `configure_git_credential_helper()` — Verificação desnecessária

**Problema**: A função verifica `result.returncode` e imprime. Mas logo acima em `main()`, o retorno `False` é tratado com `"Continuing anyway..."`, então o print `"✗ Failed"` + `print(result.stderr)` é feito dentro da função, mas o script continua. Essa separação de responsabilidades é confusa.

**Simplificação**: Ou a função imprime E aborta, ou retorna e quem chama imprime. Atualmente faz as duas coisas.

**Sugestão**: Manter o print na função e remover a mensagem redundante do `main()`.

---

## 12. `install_modules()` — Lógica `needs_android` frágil

**Problema**: `needs_android` é `True` se flutter foi instalado E (`app` ou `servidor` está em components). Mas `servidor` não precisa de Android — apenas `app` precisa.

**Correção**:

```python
needs_android = (sw == "flutter" and "app" in components)
```

**Ganho**: Lógica correta, 1 linha a menos.

---

## 13. `_run_git_with_retry()` — String `"failed"` muito genérica

**Problema**: O teste `"failed" in result.stderr.lower()` pega qualquer mensagem com "failed", o que pode acionar retry para erros que não são de rede (ex.: "merge failed").

**Sugestão**: Restringir a erros de rede conhecidos e remover o catch-all `"failed"`.

---

## 14. `import` duplicado de `time`

**Problema**: `import time` está no topo (linha 12), que é suficiente.

**Status**: Já corrigido (era `import time as _time` local, removido). ✅

---

## 15. `confirm_actions()` — Dependência da global `UPDATE_OS`

**Problema**: A função acessa `UPDATE_OS` global. Se a variável for removida (item 5), precisa ser ajustada.

---

## 16. `run_install_command()` — Praticamente morta

**Problema**: Esta função é usada apenas por `install_git()` e `install_sublime_merge()`. O restante do código usa `install_single_software()` que tem seu próprio `subprocess.run`.

**Simplificação**: Se o item 10 for implementado, `run_install_command` pode ser inlined ou removida. Atualmente `install_git` e `install_sublime_merge` são as únicas chamadas.

---

## 17. `refresh_windows_path_from_system()` — Chamada espalhada

**Problema**: A função é chamada em 2 lugares: `run_install_command()` e `install_single_software()`. Pode ser consolidada em um único ponto se as funções forem unificadas (item 16).

---

## Resumo de impacto

| # | Simplificação | Linhas salvas | Risco |
|---|---------------|--------------|-------|
| 1 | Unificar `select_*_components` | ~40 | Baixo |
| 2 | Encurtar `select_mode` | ~10 | Baixo |
| 3 | Ternário em `get_software_for_components` | ~4 | Baixo |
| 5 | Remover `UPDATE_OS` | ~3 | Baixo |
| 7 | Refatorar `clone_repository` | ~10 | Médio |
| 8 | Quebrar `setup_android_sdk` | ~0* | Médio |
| 9 | Simplificar `_get_android_sdk_path` | ~5 | Baixo |
| 10 | Factory de installers | ~30 | Médio |
| 12 | Corrigir `needs_android` | 1 | Baixo |
| 16 | Remover `run_install_command` | ~15 | Médio |

> \* Item 8 não reduz linhas mas melhora testabilidade.

**Total estimado**: ~100-120 linhas a menos (~10% do script).

## Recomendação de prioridade

1. **Itens 1, 2, 3, 5, 9, 12** — Baixo risco, alto retorno imediato. Fazer primeiro.
2. **Itens 7, 8, 10** — Refatoração estrutural. Fazer com cuidado, após testes.
3. **Itens 13, 16** — Refinamentos. Podem esperar.

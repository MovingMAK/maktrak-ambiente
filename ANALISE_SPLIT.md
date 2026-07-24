# Análise: Split do `maktrak_setup.py` — Prévio de Implementação

> Data: 2026-07-23
> Branch: `MAK-175----Scripts-de-criacao-de-ambiente`
> Decisão: Herança com sobrecarga (Template Method), base reutilizável em `maksetup_core/`

---

## 1. Situação atual

O script monolítico (~1250 linhas) concentra toda a lógica de setup num único arquivo. O bootstrap é:

```bash
curl -fsSL "https://raw.githubusercontent.com/.../maktrak_setup.py" -o /tmp/maktrak_setup.py
python3 /tmp/maktrak_setup.py
```

**Um arquivo. Zero dependências externas.** Esse requisito não pode mudar.

| Responsabilidade | Linhas (~) | Permanece em `maktrak_setup.py` |
|---|---|---|
| Detecção de SO, package managers, privilégios | ~150 | ✅ `SetupBase` + métodos base |
| Git + Sublime Merge (instalação, credenciais, clone) | ~300 | ✅ Interno da base (`_git_*`), usado só pelo orquestrador |
| Interação com usuário (modo, componentes, confirmação) | ~100 | ✅ `ui_*` |
| Update de ambiente (apt/winget) | ~60 | ✅ `update_environment()` |
| Instalação de software (vscode, flutter, arduino-cli, etc.) | ~200 | ✅ `install_pkg()` + catálogo |
| VS Code extensões e settings | ~60 | ✅ `vscode_*` |
| Flutter platforms + Android SDK + AVDs | ~200 | ✅ `flutter_*`, `android_*` |
| Xfce panel | ~40 | Permanece |
| Reporting | ~30 | ✅ `print_report()` |

---

## 2. Motivação

| Por quê? | Exemplo |
|---|---|
| **Ownership por repositório** — cada time mantém suas regras de setup | Trocar `arduino-cli` por `platformio` não exige PR no `maktrak-ambiente` |
| **Versionamento independente** — setups evoluem no ritmo de cada repo | `maktrak-hw` pode exigir FreeCAD 1.0 enquanto `maktrak-app` exige Flutter 3.x |
| **Setup seletivo** — dev de firmware não precisa de Flutter/Android | Roda só `maktrak-fw/repo_setup.py` via orquestrador |
| **Complexidade localizada** — derivadas com 30-60 linhas vs. monolito 1250 | Fácil de entender, difícil de quebrar |
| **Flexibilidade futura** — servidores web e IA terão lógica complexa de config/testar | YAML falharia (não tem if/loop/assert), Python imperativo resolve |
| **Reuso máximo** — a base acumula conhecimento e as derivadas ficam cada vez mais enxutas | `install_pkg("nginx")` resolve apt/snap/winget automaticamente |

---

## 3. Modelo: Herança com registro em sys.modules

### 3.1. Conceito

A derivada herda de `SetupBase` normalmente (com `@abstractmethod`). O orquestrador **registra o próprio módulo em `sys.modules`** antes de carregar a derivada — assim a derivada consegue dar `from maktrak_setup import SetupBase` sem precisar de `sys.path` ou path de SO.

```
maktrak_setup.py (orquestrador + SetupBase)
  │
  ├── 1. Registra a si mesmo em sys.modules
  │     sys.modules["maktrak_setup"] = <módulo atual>
  │
  ├── 2. Carrega repo_setup.py via importlib
  │     → dentro dele: "from maktrak_setup import SetupBase"
  │     → Python encontra nos sys.modules → OK
  │
  ├── 3. cls = HardwareSetup   (a classe derivada)
  │
  ├── 4. instance = cls()
  │     → __init__() de SetupBase detecta SO, etc.
  │
  ├── 5. instance.init()       @abstractmethod
  │     instance.install()     @abstractmethod
  │     instance.configure()   @abstractmethod
  │     instance.test()        @abstractmethod
  │
  └── 6. Consolida results
```

### 3.2. Como fica em código

**Classe base** — `maktrak_setup.py`:

```python
from abc import ABC, abstractmethod

class SetupBase(ABC):
    def __init__(self):
        self.os_type = self._detect_os()
        self.managers = self._detect_package_managers()
        self.results = {}

    def install_pkgs(self, *names: str): ...
    def run(self, cmd: list): ...

    # Fases — todas @abstractmethod; a derivada implementa
    # mesmo que vazia, para regularidade
    @abstractmethod
    def init(self):              ...
    @abstractmethod
    def install(self):           ...
    @abstractmethod
    def configure(self):         ...
    @abstractmethod
    def test(self):              ...
```

**Derivada** — `maktrak-server/repo_setup.py`:

```python
from maktrak_setup import SetupBase    # ← encontra pelo sys.modules

class ServerSetup(SetupBase):
    def init(self):
        print("  Preparando servidor...")

    def install(self):
        self.install_pkgs("nginx", "flutter")

    def configure(self):
        self.write_config("/etc/nginx/...", {"server_name": "maktrak.dev"})
        self.service_enable("nginx")
        self.flutter_build(REPO, "web")

    def test(self):
        self.results["web"] = self._assert_http_ok("http://localhost:80")
```

**Orquestrador** — registra o módulo e carrega a derivada:

```python
import sys, importlib.util
from pathlib import Path

# Passo 1: registra o próprio módulo para a derivada encontrar
mod = importlib.util.module_from_spec(importlib.util.spec_from_file_location(
    "maktrak_setup", __file__))
sys.modules["maktrak_setup"] = mod

# Passo 2: carrega a derivada
spec = importlib.util.spec_from_file_location("mod", repo_path / "repo_setup.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)  # ← "from maktrak_setup import SetupBase" resolve aqui

# Passo 3: instancia e executa
cls = module.ServerSetup   # ou descobre dinamicamente
instance = cls()
instance.init()
instance.install()
instance.configure()
instance.test()
```

### 3.3. E o `from maktrak_setup import SetupBase`?

É análogo a um `#include "maktrak_setup.h"` em C++ — a derivada precisa saber o que é `SetupBase` para herdar dele. O `register_module()` no orquestrador só garante que o módulo `maktrak_setup` esteja disponível para o Python resolver o import no momento da definição da classe.

Fora isso, a herança é natural: `self.install_pkgs()`, `self.run()`, `self.results` funcionam sem nenhuma mágica.

### 3.4. Risco

| Risco | Mitigação |
|---|---|
| O `main()` é executado durante o registro? | Não — `spec_from_file_location` + `module_from_spec` só preparam; `exec_module` executa, mas `if __name__` protege. Para segurança total, extrair `SetupBase` para antes do `main()`. |
| Derivada esquece de implementar alguma fase? | `@abstractmethod` em todas as 4 fases impede a instanciação. O Python levanta `TypeError` na hora. |

---

## 4. Catálogo de serviços da classe base

Tudo dentro do **mesmo arquivo** (`maktrak_setup.py`). A classe `SetupBase` reúne:

### Núcleo

```python
class SetupBase:
    os_type: str           # "linux" | "windows" | "macos"
    managers: dict         # {"snap": True, "apt": True, ...}

    def require_admin(self): ...
    def update_environment(self): ...
    def run(self, cmd: list) -> subprocess.CompletedProcess: ...
    def run_with_output(self, cmd: list) -> str: ...
    def wait_for_port(self, port: int, timeout: int = 30): ...
```

### Instalação de software

```python
    def install_pkgs(self, *names: str): ...
    #   ↑ resolve um ou mais pacotes do _PKG, agrupa apt/snap/winget,
    #     adiciona PPAs uma vez + apt update único, e instala tudo
```

**Catálogo de software conhecido** (cresce com o tempo):

> O catálogo armazena **dados**, não comandos prontos. O `install_pkgs()` monta os comandos na hora:
> - **Windows**: só o id do winget (ex: `"Git.Git"`) → monta `winget install --id <id> -e`
> - **Linux**: tupla `(gerenciador, extra, pacote)` onde:
>   - `gerenciador`: `"apt"` ou `"snap"`
>   - `extra`: para apt é o PPA (vazio se none); para snap é `"classic"` ou `""`
>   - `pacote`: nome do pacote no gerenciador

```python
_PKG = {
    "git":         {"linux": ("apt",   "",          "git"),
                    "windows": "Git.Git"},
    "vscode":      {"linux": ("snap",  "classic",   "code"),
                    "windows": "Microsoft.VisualStudioCode"},
    "flutter":     {"linux": ("snap",  "classic",   "flutter"),
                    "windows": "Flutter.Flutter"},
    "arduino-cli": {"linux": ("snap",  "",          "arduino-cli"),
                    "windows": "Arduino.ArduinoCLI"},
    "freecad":     {"linux": ("snap",  "",          "freecad"),
                    "windows": "FreeCAD.FreeCAD"},
    "kicad":       {"linux": ("apt",   "ppa:kicad/kicad-9.0-releases", "kicad"),
                    "windows": "KiCad.KiCad"},
    "nginx":       {"linux": ("apt",   "",          "nginx"),
                    "windows": "NGINX.NGINX"},
    "postgresql":  {"linux": ("apt",   "",          "postgresql"),
                    "windows": "PostgreSQL.PostgreSQL"},
}
```

A derivada chama `self.install_pkgs("kicad", "nginx", "postgresql")` — a base agrupa: adiciona o PPA do kicad, roda `apt update` uma vez e instala tudo com `apt install -y kicad nginx postgresql`. Para snap e winget, executa cada pacote individualmente.

### Sistema — serviços, configuração, comandos

```python
    def service_enable(self, name: str): ...
    def service_restart(self, name: str): ...
    def write_config(self, path: str, content: dict | str, sudo: bool = True): ...
    def append_line(self, file: str, line: str): ...
    def create_symlink(self, target: str, link: str): ...
```

### Flutter

```python
    def flutter_build(self, path: Path, platform: str): ...
    def flutter_test(self, path: Path): ...
    def flutter_config(self, opts: list[str]): ...
```

### Android SDK

```python
    def setup_android(self): ...       # JDK + KVM + licenças + cmdline-tools
    def create_avd(self, name, device, api): ...
```

### VS Code

```python
    def install_extensions(self, exts: list[str]): ...
    def set_setting(self, key: str, value): ...
```

### Interação com usuário

```python
    def select_mode(self) -> str: ...
    def select_components(self, options: dict) -> list: ...
    def confirm(self, msg: str) -> bool: ...
    def print_report(self, results: dict): ...
```

---

## 5. Estrutura final

```
maktrak-ambiente/
  maktrak_setup.py              ← único arquivo: SetupBase + catálogo + orquestrador

maktrak-hw/repo_setup.py        ← from maktrak_setup import SetupBase
maktrak-fw/repo_setup.py        ← from maktrak_setup import SetupBase
maktrak-server/repo_setup.py    ← from maktrak_setup import SetupBase
maktrak-app/repo_setup.py       ← from maktrak_setup import SetupBase
```

**Apenas `maktrak_setup.py` é baixado via curl.** As derivadas são clonadas e carregadas em tempo de execução. O `from maktrak_setup import SetupBase` dentro delas resolve porque o orquestrador registrou o módulo em `sys.modules`.

Organização interna do `maktrak_setup.py`:

```
maktrak_setup.py
  ├── _PKG = { ... }           ← catálogo de software conhecido
  ├── class SetupBase(ABC):     ← classe com infraestrutura + abstractmethod
  │     ├── __init__()          ← detecta OS, package managers
  │     ├── require_admin()
  │     ├── update_environment()
  │     ├── install_pkg()
  │     ├── install_pkgs()
  │     ├── service_enable(), service_restart()
  │     ├── write_config(), append_line()
  │     ├── flutter_build(), flutter_test()
  │     ├── setup_android(), create_avd()
  │     ├── install_extensions(), set_setting()
  │     ├── select_mode(), select_components(), confirm()
  │     ├── print_report()
  │     ├── init()              ← @abstractmethod
  │     ├── install()           ← @abstractmethod
  │     ├── configure()         ← @abstractmethod
  │     └── test()              ← @abstractmethod
  │
  ├── register_self()           ← sys.modules["maktrak_setup"] = módulo atual
  ├── load_derived()            ← importlib para repo_setup.py
  └── main()                    ← orquestrador
```

---

## 6. Orquestrador

O `maktrak_setup.py` contém `SetupBase`, o catálogo, o registro em `sys.modules` e o `main()`.

```python
#!/usr/bin/env python3
"""MakTrak Setup — bootstrap + orquestrador multicomponente."""
import sys, platform, subprocess, shutil, os, time, json, zipfile
import importlib.util, urllib.request, ctypes
from pathlib import Path
from abc import ABC, abstractmethod

# ═══════════════════════════════════════════════════════════
# CLASS BASE (SetupBase + fases abstratas)
# ═══════════════════════════════════════════════════════════

class SetupBase(ABC):
    def __init__(self):
        self.os_type = self._detect_os()
        self.managers = self._detect_package_managers()
        self.results = {}

    def _detect_os(self) -> str: ...
    def _detect_package_managers(self) -> dict: ...
    def install_pkg(self, name: str) -> bool: ...
    def install_pkgs(self, *names: str) -> bool: ...
    def run(self, cmd: list): ...
    def write_config(self, path, content): ...
    def service_enable(self, name): ...
    def flutter_build(self, path, platform): ...
    def setup_android(self): ...
    # ... demais métodos auxiliares ...

    # ── Fases — todas @abstractmethod ──
    @abstractmethod
    def init(self):              ...
    @abstractmethod
    def install(self):           ...
    @abstractmethod
    def configure(self):         ...
    @abstractmethod
    def test(self):              ...

# ═══════════════════════════════════════════════════════════
# REGISTRO EM sys.modules
# ═══════════════════════════════════════════════════════════

def register_module(path: Path):
    """Registra maktrak_setup.py em sys.modules para import pelas derivadas."""
    name = "maktrak_setup"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)

# ═══════════════════════════════════════════════════════════
# CARREGADOR DINÂMICO
# ═══════════════════════════════════════════════════════════

def load_derived(repo_setup_path: Path):
    """Carrega repo_setup.py e retorna a classe derivada de SetupBase."""
    spec = importlib.util.spec_from_file_location(
        f"repo_{repo_setup_path.parent.name}", repo_setup_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, type) and issubclass(obj, SetupBase) and obj is not SetupBase:
            return obj
    raise ValueError(f"Nenhuma classe SetupBase em {repo_setup_path}")

# ═══════════════════════════════════════════════════════════
# ORQUESTRADOR
# ═══════════════════════════════════════════════════════════

def main():
    # 0. Registra este módulo para as derivadas poderem importar
    register_module(Path(__file__))

    base = SetupBase()

    # 1. Detecta OS, privilégios, package managers
    base.ensure_admin(base.os_type)
    base.update_environment()

    # 2. Interação com usuário
    mode = base.select_mode()
    components = base.select_components(...)
    if not base.confirm(mode, components):
        return

    # 3. Clona os repositórios dos componentes
    base._setup_credentials()
    base._clone_repos(get_repos(mode, components))

    # 4. Executa cada derivada
    all_results = {}
    for component in components:
        repo_path = get_repo_path(component) / "repo_setup.py"
        cls = load_derived(repo_path)
        instance = cls()
        print(f"\n── {component} ──")
        instance.init()
        instance.install()
        instance.configure()
        instance.test()
        all_results[component] = instance.results

    # 5. Relatório consolidado
    base.print_report(all_results)

if __name__ == "__main__":
    main()
```

### Exemplo de derivada

```python
# maktrak-hw/repo_setup.py
from maktrak_setup import SetupBase     # ← encontra sys.modules

class HardwareSetup(SetupBase):
    def init(self):
        print("  Preparando hardware...")

    def install(self):
        self.install_pkgs("freecad", "kicad")

    def configure(self):
        pass  # nada a configurar

    def test(self):
        r = self.run(["freecad", "--version"])
        self.results["freecad"] = r.returncode == 0
        self.results["kicad"] = shutil.which("kicad") is not None
```

---

## 7. Próximos passos

- [ ] **Estruturar `maktrak_setup.py`** — `SetupBase(ABC)`, catálogo `_PKG`, `register_module()`, `load_derived()`, `main()`
- [ ] **Criar repo piloto** — `maktrak-hw/repo_setup.py` com `from maktrak_setup import SetupBase; class HardwareSetup(SetupBase)`
- [ ] **Testar registro + carga** — `register_module()` → `load_derived()` → `instance = cls()` → fases
- [ ] **Testar bootstrap completo** — curl → `maktrak_setup.py` → clone → registra → carrega → executa → relatório
- [ ] **Testar Linux + Windows** com 1 repo piloto
- [ ] **Migrar demais repos** — `maktrak-fw`, `maktrak-server`, `maktrak-app`

---

## 8. Adendo para IA — Mapa de arquivos e convenções

### Arquivos do projeto

| Caminho relativo | Papel |
|---|---|
| `maktrak_setup.py` | Orquestrador + `SetupBase` + catálogo `_PKG`. Único arquivo baixado via curl. |
| `*/repo_setup.py` | Script derivado em cada repo. Deve conter uma classe que herda de `SetupBase` e implementa as 4 fases. |
| `maktrak-hw/repo_setup.py` | Setup de hardware (FreeCAD, KiCad, etc.) |
| `maktrak-fw/repo_setup.py` | Setup de firmware (arduino-cli, platformio, etc.) |
| `maktrak-server/repo_setup.py` | Setup de servidor (nginx, postgresql, flutter web, etc.) |
| `maktrak-app/repo_setup.py` | Setup do app mobile (flutter, Android SDK, AVDs, etc.) |

### Contrato da derivada

```python
from maktrak_setup import SetupBase

class MeuSetup(SetupBase):
    def init(self):       ...
    def install(self):    self.install_pkgs(...)
    def configure(self):  ...
    def test(self):       ...
```

- `init`, `install`, `configure`, `test` — todas `@abstractmethod`, todas obrigatórias
- Para pacotes conhecidos: `self.install_pkgs("git", "vscode", ...)`
- Para pacotes desconhecidos (fallback explícito): usar `self.run(["sudo", "apt", ...])`
- `self.results` é um `dict` — preencher com `str → bool` em cada fase
- `self.run(cmd)` executa e retorna `subprocess.CompletedProcess`
- `self.os_type` é `"linux"`, `"windows"` ou `"macos"`
- Não importar nada de `sys`, `os`, `subprocess` — usar os métodos da base

### Catálogo `_PKG`

Vive em `maktrak_setup.py`, antes da classe. Formato:

```python
_PKG = {
    "nome": {"linux": ("apt"|"snap", "<extra>", "<pacote>"),
             "windows": "<winget-id>"},
}
```

`<extra>`: para apt é o PPA (vazio se none); para snap é `"classic"` ou `""`.

### Fluxo de bootstrap

```
curl maktrak_setup.py
  → main()
    → register_module()    sys.modules["maktrak_setup"] = self
    → update_environment()
    → select_mode() / select_components()
    → _setup_credentials() / _clone_repos()
    → for each component:
        load_derived(repo/repo_setup.py)
        cls = <classe que herda SetupBase>
        instance = cls()
        instance.init()
        instance.install()
        instance.configure()
        instance.test()
    → print_report()
```

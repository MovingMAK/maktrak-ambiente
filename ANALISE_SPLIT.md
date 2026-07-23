# Análise: Split do `maktrak_setup.py`

> Data: 2026-07-23
> Branch: `MAK-175----Scripts-de-criacao-de-ambiente`
> Contexto: Separar o script monolítico em múltiplos scripts, cada um residindo no seu próprio repositório.

---

## 1. Situação atual

O script monolítico atual (~1250 linhas) tem estas responsabilidades:

| Responsabilidade | Linhas (~) | Acoplamento |
|---|---|---|
| Detecção de SO, package managers, privilégios admin | ~150 | Genérico |
| Git + Sublime Merge (instalação, credenciais, clone) | ~300 | Genérico |
| Interação com usuário (modo, componentes, confirmação) | ~100 | Genérico |
| Update de ambiente (apt/winget) | ~60 | Genérico |
| Instalação de software (vscode, flutter, arduino-cli, freecad, kicad) | ~200 | Específico por repo |
| VS Code extensões e settings | ~60 | Específico por repo |
| Flutter platforms + Android SDK + AVDs | ~200 | Específico (app, servidor) |
| Xfce panel | ~40 | Específico (Linux/Xubuntu) |
| Reporting | ~30 | Genérico |

As definições de quais softwares cada componente precisa estão centralizadas em dicionários (`DEV_MODULES`, `DEV_REPOSITORIES`, `SOFTWARE_INSTALLERS`).

### Mapeamento atual de categorias → repositórios

| Categoria | Repositório | Softwares |
|---|---|---|
| ambiente | maktrak-ambiente | vscode |
| mecanica | maktrak-hw | freecad |
| eletronica | maktrak-hw | kicad |
| firmware | maktrak-fw | arduino-cli, vscode |
| servidor | maktrak-server | vscode, flutter |
| app | maktrak-app | vscode, flutter |

---

## 2. Por que dividir? (motivação geral)

Estes pontos se aplicam a **qualquer** arquitetura de split — herança, YAML ou descentralizada. São os motivadores para abandonar o monolito.

### 2.1. Ownership por repositório
Cada time mantém as regras de setup **junto com o código** que desenvolve. Trocar `arduino-cli` por `platformio` no firmware não exige PR no `maktrak-ambiente` nem coordenação entre times.

### 2.2. Versionamento independente
`maktrak-hw` pode exigir FreeCAD 1.0 enquanto `maktrak-app` exige Flutter 3.x. As dependências evoluem no ritmo de cada repo, sem risco de quebrar o setup alheio.

### 2.3. Descoberta dinâmica
Adicionar um novo repositório (`maktrak-ia`) não exige alterar o script base — basta que o novo repo traga sua própria definição de setup (seja uma classe Python, um YAML, ou um script standalone).

### 2.4. Setup seletivo
Um desenvolvedor que só trabalha com firmware pode rodar apenas o setup do `maktrak-fw`, sem instalar Flutter, Android SDK, etc.

### 2.5. Complexidade localizada
O script atual tem ~1250 linhas. Separado, cada unidade tem 30–300 linhas.

### 2.6. Custos inerentes a qualquer split

Estes desafios existirão em **todas** as arquiteturas e precisam ser endereçados:

| Desafio | Impacto |
|---|---|
| **Deduplicação de software** — `vscode` e `flutter` são necessários em múltiplos componentes. Quem instala? O orquestrador precisa consolidar antes de executar. | Todo modelo |
| **Ordem de fases** — Flutter precisa ser instalado *antes* de `flutter config` e do Android SDK. O ciclo `install → configure → test` precisa ser respeitado. | Todo modelo |
| **Credenciais centralizadas** — O token GitHub é coletado uma vez e compartilhado. Os scripts filhos não devem repedir credenciais. | Todo modelo |
| **Relatório unificado** — O usuário espera um resumo consolidado ao final, não N relatórios separados. | Todo modelo |
| **Custo de migração** — Refatorar ~1250 linhas maduras tem risco de regressão. Testar em Windows + Linux para cada arquitetura é obrigatório. | Todo modelo |

As seções seguintes analisam como cada arquitetura lida com esses desafios.

---

## 3. Análise aprofundada: Herança com sobrecarga (modelo proposto)

### 3.1. Descrição do modelo

A ideia central é um padrão **Template Method** aplicado via herança, análogo a classes base com métodos virtuais em C++:

1. **Classe base** (`SetupBase`) vive no `maktrak-ambiente`. Contém **toda a infraestrutura**:
   - Detecção de SO (`detect_os()`)
   - Detecção de package managers (`detect_package_managers()`)
   - Verificação de privilégios admin/sudo
   - Métodos utilitários: `install_package()`, `run_command()`, `verify_installed()`
   - Atualização de ambiente (`apt update/upgrade`, `winget upgrade`)
   - Git + Sublime Merge (instalação, credenciais, clone)
   - Interação com usuário (modo, componentes, confirmação)
   - Reporting consolidado
   - O método `run()` que rege o ciclo de vida completo

2. **Classes derivadas** vivem em cada repositório (`maktrak-hw/setup.py`, `maktrak-fw/setup.py`, etc.). Sobrecarregam (override) apenas o que é específico:
   - `init()` — inicialização específica do componente
   - `install()` — quais softwares instalar e como
   - `configure()` — pós-instalação (ex: `flutter config`, Android SDK)
   - `test()` — validações (ex: `flutter doctor`, compilar firmware)

3. O script base no `maktrak-ambiente` **cria o tipo derivado e apenas executa as funções** — não precisa saber o que cada repo instala.

### 3.2. Como ficaria em Python

**Classe base** — `maktrak-ambiente/maksetup_core/base.py`:

```python
import sys
import platform
import subprocess
from pathlib import Path
from abc import ABC, abstractmethod

class SetupBase(ABC):
    """Classe base com toda a infraestrutura de setup."""

    def __init__(self):
        self.os_type = self._detect_os()
        self.managers = self._detect_package_managers()
        self.results = {}

    # ═══════════════════════════════════════════════
    # Infraestrutura (fornecida pela base)
    # ═══════════════════════════════════════════════

    def _detect_os(self) -> str:
        system = platform.system()
        return {"Linux": "linux", "Windows": "windows", "Darwin": "macos"}.get(system, "unknown")

    def _detect_package_managers(self) -> dict:
        managers = {}
        if self.os_type == "linux":
            if subprocess.run(["which", "snap"], capture_output=True).returncode == 0:
                managers["snap"] = True
            if subprocess.run(["which", "apt"], capture_output=True).returncode == 0:
                managers["apt"] = True
        elif self.os_type == "windows":
            if subprocess.run(["where", "winget"], capture_output=True).returncode == 0:
                managers["winget"] = True
        return managers

    def install_package(self, name: str, linux_cmd: list, windows_cmd: list,
                        verify_cmd: list = None) -> bool:
        """Instala um pacote usando o comando adequado ao SO detectado."""
        if verify_cmd and subprocess.run(verify_cmd, capture_output=True).returncode == 0:
            print(f"       ✓ {name} already installed")
            return True
        cmd = linux_cmd if self.os_type == "linux" else windows_cmd
        result = subprocess.run(cmd, capture_output=True, text=True)
        ok = result.returncode == 0
        print(f"       {'✓' if ok else '✗'} {name}")
        return ok

    def require_admin(self) -> bool:
        """Garante privilégios admin/sudo. Retorna False se falhar."""
        # ...implementação existente de ensure_admin_privileges...
        return True

    def update_environment(self):
        """Atualiza o SO (apt upgrade / winget upgrade)."""
        # ...implementação existente de update_environment...
        pass

    # ═══════════════════════════════════════════════
    # Métodos virtuais (sobrecarregados por cada repo)
    # ═══════════════════════════════════════════════

    def init(self):
        """Inicialização específica do componente. Opcional."""
        pass

    @abstractmethod
    def install(self):
        """Instala os softwares deste componente. Obrigatório."""
        ...

    def configure(self):
        """Pós-instalação / configuração. Opcional."""
        pass

    @abstractmethod
    def test(self):
        """Validações deste componente. Obrigatório."""
        ...

    # ═══════════════════════════════════════════════
    # Template method — rege o ciclo de vida
    # ═══════════════════════════════════════════════

    def run(self):
        """Template method: executa o ciclo completo."""
        print(f"\n── Setup: {self.__class__.__name__} ──")
        self.init()
        self.install()
        self.configure()
        self.test()
        return self.results
```

**Classe derivada** — `maktrak-hw/setup.py`:

```python
from maksetup_core.base import SetupBase

class HardwareSetup(SetupBase):
    """Setup do ambiente de hardware (FreeCAD + KiCad)."""

    def init(self):
        print("  Preparando ambiente de hardware...")

    def install(self):
        self.install_package(
            "freecad",
            linux_cmd=["sudo", "snap", "install", "freecad"],
            windows_cmd=["winget", "install", "--id", "FreeCAD.FreeCAD", "-e",
                         "--accept-package-agreements"],
            verify_cmd=["freecad", "--version"],
        )
        self.install_package(
            "kicad",
            linux_cmd=["bash", "-c",
                       "sudo add-apt-repository --yes ppa:kicad/kicad-9.0-releases && "
                       "sudo apt update && sudo apt install -y kicad"],
            windows_cmd=["winget", "install", "--id", "KiCad.KiCad", "-e",
                         "--accept-package-agreements"],
        )

    def configure(self):
        Path.home().joinpath(".config/FreeCAD").mkdir(parents=True, exist_ok=True)

    def test(self):
        self.results["freecad"] = subprocess.run(
            ["freecad", "--version"], capture_output=True
        ).returncode == 0
        self.results["kicad"] = subprocess.run(
            ["kicad", "--version"], capture_output=True
        ).returncode == 0
```

**Orquestrador** — `maktrak-ambiente/maktrak_setup.py`:

```python
#!/usr/bin/env python3
import sys
import importlib.util
from pathlib import Path

# Torna maksetup_core importável para os scripts derivados
sys.path.insert(0, str(Path(__file__).parent))

from maksetup_core.base import SetupBase

# ... clonagem de repositórios (usa infra da base ou próprio) ...

def load_setup_class(repo_path: Path) -> type:
    """Carrega dinamicamente a classe de setup de um repositório."""
    setup_file = repo_path / "setup.py"
    spec = importlib.util.spec_from_file_location(
        f"maksetup_{repo_path.name}", setup_file
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Encontra a subclasse de SetupBase no módulo
    for name in dir(module):
        obj = getattr(module, name)
        if (isinstance(obj, type)
                and issubclass(obj, SetupBase)
                and obj is not SetupBase):
            return obj
    raise ValueError(f"No SetupBase subclass found in {setup_file}")

# Para cada repo clonado:
#   cls = load_setup_class(repo_path)
#   instance = cls()
#   instance.run()
```

### 3.3. Análise crítica

#### ✅ Prós do modelo de herança

| Aspecto | Análise |
|---|---|
| **Separação clara de responsabilidades** | A base tem infraestrutura, as derivadas têm regras de negócio. Nunca se misturam. |
| **Derivadas são mínimas** | Cada `setup.py` de repo tem ~30-60 linhas. Só declara o que instalar, como configurar, como testar. |
| **Template Method garante ordem** | `run()` chama `init()` → `install()` → `configure()` → `test()` sempre na mesma ordem. Nenhum repo pode bagunçar o fluxo. |
| **Base fornece utilitários prontos** | `install_package()` já resolve SO, verificação de instalado, execução e logging. Derivada só passa os comandos. |
| **Tipagem e contratos** | Com `ABC` e `@abstractmethod`, Python **recusa instanciar** uma derivada que não implementa `install()` e `test()`. Erro claro em runtime. |
| **Descoberta dinâmica** | O orquestrador não conhece as classes derivadas em tempo de escrita — descobre via `importlib` em runtime. Adicionar um repo novo não altera o orquestrador. |
| **Natural para times multi-repo** | Cada time escreve sua derivada em Python puro, sem aprender YAML, sem DSL. |
| **Herança é idiomática em Python** | Python suporta herança, ABC, `super()`, `@abstractmethod` nativamente. Não é um hack. |

#### ❌ Contras e riscos do modelo de herança

| Aspecto | Análise | Gravidade |
|---|---|---|
| **Acoplamento físico base↔derivada** | A derivada faz `from maksetup_core.base import SetupBase`. Se a base mudar de caminho ou nome, **todas** as derivadas quebram. | 🔴 Alta |
| **Distribuição da classe base** | `maksetup_core` está no `maktrak-ambiente`, mas as derivadas estão em outros repos. Como a derivada encontra a base? Ver seção 4.4 abaixo. | 🔴 Alta |
| **Derivadas não executáveis standalone** | `python3 maktrak-hw/setup.py` falha porque `maksetup_core` não está no `sys.path`. Só funcionam quando chamadas pelo orquestrador. | 🟡 Média |
| **Versionamento base↔derivada** | Se a base v2 adiciona um novo método abstrato `validate_network()`, derivadas existentes quebram em runtime ao serem instanciadas. Precisam ser atualizadas em todos os repos simultaneamente. | 🟡 Média |
| **Sem verificação em compile-time** | Python não tem compilação. Erros como "esqueci de implementar `install()`" só aparecem quando o código roda. Diferente de C++ onde `virtual void install() = 0;` gera erro de link. | 🟡 Média |
| **ABC é verificado na instanciação, não na definição** | `class X(SetupBase): pass` é válido. Só falha ao tentar `X()`. Se o `importlib` só carrega o módulo sem instanciar, o erro passa despercebido até o `run()`. | 🟢 Baixa |
| **Dificuldade de teste isolado** | Para testar `HardwareSetup` sozinho, preciso ter `maksetup_core` disponível. Ou moco a base, ou testo via orquestrador. | 🟡 Média |
| **Complexidade de debug cross-repo** | Um erro em `HardwareSetup.install()` pode ser causado por um bug em `SetupBase.install_package()`. O stack trace cruza repositórios. | 🟢 Baixa |

### 3.4. O problema central: como a derivada importa a base?

Este é o **maior desafio técnico** do modelo. A classe base está no repo `maktrak-ambiente`. As classes derivadas estão nos repos `maktrak-hw`, `maktrak-fw`, etc. Quando o Python interpreta `from maksetup_core.base import SetupBase` dentro de `maktrak-hw/setup.py`, como ele encontra o módulo?

Quatro estratégias possíveis:

| Estratégia | Como funciona | Prós | Contras |
|---|---|---|---|
| **D1: `sys.path` injection** | O orquestrador faz `sys.path.insert(0, path_to_ambiente)` **antes** de importar as derivadas. O Python encontra `maksetup_core` pelo `sys.path`. | Simples, zero dependência extra, single source of truth. | Derivadas NUNCA funcionam standalone. Só o orquestrador sabe o caminho. |
| **D2: pip install editável** | `maksetup_core` é um pacote pip. O orquestrador faz `pip install -e .` no diretório do `maktrak-ambiente` antes de clonar. Derivadas importam normalmente. | Python padrão, tooling funciona (IDE, linter). Derivadas podem importar em testes. | Requer `pip` e `setuptools`. Polui o ambiente do usuário. Overhead de `setup.py`/`pyproject.toml`. |
| **D3: Cópia física** | O orquestrador copia `maksetup_core/` para dentro de cada repo clonado antes de executar. Ou cada repo já contém uma cópia versionada. | Derivadas funcionam standalone. Zero dependência de rede no runtime. | Risco de drift: cópias divergem. Atualizar a base exige PR em todos os repos. |
| **D4: Symlink** | O orquestrador cria symlink de `maksetup_core/` dentro de cada repo clonado. | Single source of truth, sem cópia. | Não funciona no Windows sem permissões especiais. Frágil. |

**Recomendação para este modelo: Estratégia D1 (`sys.path` injection).**

É a mais limpa para o cenário: o orquestrador sempre será o ponto de entrada, as derivadas são "plugins" que só existem no contexto do orquestrador. A impossibilidade de rodar standalone é uma limitação aceitável — os testes de cada derivada podem ser feitos via orquestrador com flags como `--repo hardware --test-only`.

```python
# No topo do maktrak_setup.py (orquestrador)
import sys
from pathlib import Path

AMBIENTE_ROOT = Path(__file__).resolve().parent
if str(AMBIENTE_ROOT) not in sys.path:
    sys.path.insert(0, str(AMBIENTE_ROOT))
```

### 3.5. Comparação com as arquiteturas alternativas

| Critério | Herança (este modelo) | YAML (Seção 4) | Descentralizado (Seção 4) |
|---|---|---|---|
| Flexibilidade (lógica condicional) | ✅ Python arbitrário | ❌ Só declarativo | ✅ Python arbitrário |
| Curva de aprendizado para o time | 🟡 Precisa entender herança + ABC | ✅ Só editar YAML | ✅ Python simples |
| Duplicação de boilerplate | ✅ Zero (tudo na base) | ✅ Zero (engine centralizado) | ❌ Máxima |
| Risco de quebra base↔repo | 🔴 API da base é contrato rígido | 🟡 Schema YAML pode mudar | ✅ Zero (sem base) |
| Executável standalone por repo | ❌ Não | ❌ Não (precisa do engine) | ✅ Sim |
| Adicionar novo repo | ✅ Basta criar derivada | ✅ Basta criar YAML | ✅ Script independente |
| Deduplicação de SW cross-repo | 🟡 Base gerencia | ✅ Engine gerencia | ❌ Cada um instala o seu |
| Teste isolado do repo | 🟡 Via orquestrador | 🟡 Via engine | ✅ Direto |

### 3.6. Variantes de API dentro do modelo de herança

A classe base pode expor a API para as derivadas de duas formas. A arquitetura é a mesma (herança + template method), mas o *estilo* difere:

| Estilo | Como a derivada declara o que instalar | Exemplo |
|---|---|---|
| **Imperativo** (descrito em 3.2) | Sobrecarrega `install()` e chama `self.install_package()` da base para cada software | `def install(self): self.install_package("freecad", ...)` |
| **Declarativo** | Sobrecarrega `get_software()` retornando uma lista de `SoftwareSpec`. A base itera e instala. | `def get_software(self): return [SoftwareSpec(...)]` |

**Comparação:**

| Critério | Imperativo | Declarativo |
|---|---|---|
| Controle da derivada | Total — decide ordem, condicionais, fallback | Nenhum — a base decide ordem e estratégia |
| Deduplicação cross-repo | Difícil — cada derivada executa independente | Fácil — a base coleta todas as specs, deduplica, e instala uma vez |
| Lógica condicional | Natural: `if gpu: install_cuda()` | Impossível no modelo puro; exigiria um campo `condition:` no YAML |
| Tamanho da derivada | ~30 linhas | ~15 linhas |
| Complexidade da base | Simples (só provê `install_package`) | Maior (precisa de `SoftwareSpec`, iteração, dedup) |

**Recomendação:** Começar com o estilo **declarativo** e permitir fallback para **imperativo** quando necessário. A base pode oferecer ambos:

```python
class SetupBase(ABC):
    # Opção 1: declarativo (a base itera)
    def get_software(self) -> list[SoftwareSpec]:
        return []

    # Opção 2: imperativo (a derivada controla)
    def install(self):
        for spec in self.get_software():
            self.install_package(spec.name, spec.linux_cmd, spec.windows_cmd, spec.verify_cmd)
```

Assim, 80% dos casos usam `get_software()` declarativo; os 20% que precisam de lógica condicional sobrescrevem `install()` diretamente.

---

## 4. Arquiteturas alternativas

Duas outras arquiteturas que resolvem o mesmo problema por caminhos diferentes.

> **Nota:** A "Arquitetura B" do rascunho original (hooks Python com lib compartilhada) foi removida por ser essencialmente igual ao modelo de herança da Seção 3. A diferença era apenas o estilo da API (retornar specs declarativas vs. override imperativo de `install()`). Esse debate é interno ao modelo de herança e está coberto em 3.6 abaixo.

### 🅰️ Arquitetura YAML: Plugins declarativos

O script base continua no `maktrak-ambiente`, mas em vez de classes Python, cada repo tem um arquivo `setup.yaml` **puramente declarativo**. O engine centralizado lê e executa.

```yaml
# Exemplo: maktrak-hw/setup.yaml
name: hardware
provides:
  software: [freecad, kicad]
  vscode_extensions: []
phases:
  install:
    - name: freecad
      verify: ["freecad", "--version"]
      linux: ["sudo", "snap", "install", "freecad"]
      windows: ["winget", "install", "--id", "FreeCAD.FreeCAD", "-e", "--accept-package-agreements", "--accept-source-agreements"]
    - name: kicad
      verify: null  # checked via shutil.which
      linux: ["bash", "-c", "sudo apt install -y software-properties-common && sudo add-apt-repository --yes ppa:kicad/kicad-9.0-releases && sudo apt update && sudo apt install -y kicad"]
      windows: ["winget", "install", "--id", "KiCad.KiCad", "-e", "--accept-package-agreements", "--accept-source-agreements"]
  configure: []
  validate:
    - ["freecad", "--version"]
```

| Prós | Contras |
|---|---|
| Separação de concerns sem duplicação de código (engine centralizado) | Engine centralizado — mudanças no engine afetam todos |
| Cada repo mantém seu manifesto, versionado junto com o código | Menos flexibilidade que Python (sem `if`, loops, subprocess) |
| Zero Python nos repos filhos — só YAML | Lógica condicional complexa (ex: "se GPU NVIDIA instalar CUDA") impossível |
| Fácil de validar (schema), fácil de extender | Engine é mais complexo (precisa interpretar o YAML) |
| Barreira de entrada baixíssima para times | — |

### 🅱️ Arquitetura Descentralizada: Scripts independentes

Cada repositório tem seu `setup.py` **totalmente autocontido** — detecta SO, verifica privilégios, instala, valida. O `maktrak-ambiente` tem apenas um script que clona e dispara `python3 <repo>/setup.py` em cada repo.

| Prós | Contras |
|---|---|
| Máxima independência — cada time é 100% dono do seu setup | Duplicação massiva de código (~150 linhas de boilerplate por repo) |
| Nenhuma lib compartilhada para manter | Sem visão unificada (relatório fragmentado) |
| Scripts executáveis standalone a qualquer momento | Orquestração frágil (ordem, falhas parciais, sem deduplição) |
| Debug e teste triviais (`python setup.py`) | Cada script precisa reimplementar Git, credenciais, etc. |

---

## 5. Recomendação

### 5.1. Matriz de decisão

| Critério | Herança (Seção 3) | YAML (Seção 4) | Descentralizado (Seção 4) |
|---|---|---|---|
| Custo de migração | 🟡 Médio (~1 semana) | 🟢 Baixo (~2-3 dias) | 🔴 Alto (~2 semanas) |
| Manutenibilidade futura | ✅ Alta (por time) | 🟡 Média (engine central) | 🟡 Média (duplicação) |
| Risco de quebra cross-repo | 🟡 Contrato da base | 🟡 Schema YAML | ✅ Zero |
| Flexibilidade para casos complexos | ✅ Python total | ❌ Limitada ao YAML | ✅ Python total |
| Curva de aprendizado | 🟡 Herança + ABC | ✅ YAML | ✅ Python simples |
| Testabilidade isolada | 🟡 Via orquestrador | 🟡 Via engine | ✅ Direta |

### 5.2. Caminho recomendado

```
HOJE                           MÉDIO PRAZO                     LONGO PRAZO
  │                                │                               │
  ├─ Script monolítico ────────────┤                               │
  │  (~1250 linhas)               │                               │
  │                                │                               │
  └─ Refatorar base em            │                               │
     maksetup_core/ ──────────────┤                               │
     (extrair engine do script)   │                               │
                                  │                               │
                                  ├─ Implementar derivadas        │
                                  │  por repo (herança)           │
                                  │  maktrak-hw/setup.py          │
                                  │  maktrak-fw/setup.py          │
                                  │  maktrak-server/setup.py      │
                                  │  maktrak-app/setup.py         │
                                  │                               │
                                  └─ Orquestrador usa ────────────┤
                                     importlib + sys.path         │
                                     para carregar derivadas      │
                                                                  │
                                                                  ├─ Se times precisarem
                                                                  │  de independência total:
                                                                  │  evoluir para pip package
                                                                  │  da base (D2)
```

**Passo 1 (hoje)**: Refatorar o script atual extraindo o engine para `maksetup_core/`:

- `maksetup_core/base.py` → classe `SetupBase` com `_detect_os()`, `_detect_package_managers()`, `install_package()`, `update_environment()`, `run()` (template method)
- `maksetup_core/git.py` → funções de clone, credenciais, Sublime Merge
- `maksetup_core/ui.py` → funções de interação com usuário
- O script atual vira o primeiro "cliente" da base (prova que a API funciona)

**Passo 2 (médio prazo)**: Para cada repositório, criar `setup.py` com a classe derivada. O orquestrador clona e carrega dinamicamente.

**Passo 3 (longo prazo, se necessário)**: Se times demandarem executar scripts standalone, evoluir `maksetup_core` para pacote pip (estratégia D2).

---

## 6. Desenho concreto: modelo de herança

### 6.1. Estrutura de diretórios

```
maktrak-ambiente/                    ← repo central
  maktrak_setup.py                   ← orquestrador (ponto de entrada)
  maksetup_core/                     ← classe base + engine
    __init__.py
    base.py                          ← SetupBase (ABC com template method)
    git.py                           ← clone, credenciais, Sublime Merge
    ui.py                            ← menus, seleção, confirmação
    installers.py                    ← _install_package, retry, etc.

maktrak-hw/                          ← repo de hardware
  setup.py                           ← class HardwareSetup(SetupBase)
  ...

maktrak-fw/                          ← repo de firmware
  setup.py                           ← class FirmwareSetup(SetupBase)
  ...

maktrak-server/                      ← repo de servidor
  setup.py                           ← class ServerSetup(SetupBase)
  ...

maktrak-app/                         ← repo de app
  setup.py                           ← class AppSetup(SetupBase)
  ...
```

### 6.2. Fluxo de execução do orquestrador

```
maktrak_setup.py
  │
  ├─ 1. sys.path.insert(0, raiz do maktrak-ambiente)
  │     → garante que maksetup_core é importável
  │
  ├─ 2. Detecta OS, package managers, pede credenciais
  │     → usa funções de maksetup_core/ui.py e maksetup_core/git.py
  │
  ├─ 3. Pede modo (dev/prod) e componentes
  │     → hardware, firmware, servidor, app, etc.
  │
  ├─ 4. Atualiza ambiente (apt upgrade / winget upgrade)
  │
  ├─ 5. Clona repositórios selecionados
  │     → ~/repos/movingmak/maktrak/<repo>/
  │
  ├─ 6. Para cada repo clonado:
  │     │
  │     ├─ 6a. importlib carrega setup.py do repo
  │     ├─ 6b. Encontra subclasse de SetupBase
  │     ├─ 6c. Instancia: obj = HardwareSetup()
  │     └─ 6d. Executa:  obj.run()
  │           │
  │           ├─ obj.init()        ← sobrecarga do repo
  │           ├─ obj.install()     ← sobrecarga do repo
  │           │    └─ chama self.install_package() da base
  │           ├─ obj.configure()   ← sobrecarga do repo
  │           └─ obj.test()        ← sobrecarga do repo
  │
  └─ 7. Consolida resultados de todos os repos
       → relatório unificado
```

### 6.3. API da classe base (`SetupBase`)

```python
class SetupBase(ABC):
    # ── Atributos fornecidos pela base ──
    os_type: str          # "linux" | "windows" | "macos"
    managers: dict        # {"snap": True, "apt": True, ...}
    results: dict         # {"freecad": True, "kicad": False, ...}

    # ── Métodos utilitários (chamados pelas derivadas) ──
    def install_package(name, linux_cmd, windows_cmd, verify_cmd=None) -> bool
    def run_command(cmd, check=True) -> subprocess.CompletedProcess
    def is_installed(verify_cmd) -> bool

    # ── Métodos de ciclo de vida (sobrecarregados pelas derivadas) ──
    def init(self):       ...   # opcional
    def install(self):    ...   # @abstractmethod — obrigatório
    def configure(self):  ...   # opcional
    def test(self):       ...   # @abstractmethod — obrigatório

    # ── Template method (NÃO sobrecarregar) ──
    def run(self):        # chama init → install → configure → test
```

---

## 7. Próximos passos

- [ ] **Validar modelo de herança** — revisar seção 3 com todos os stakeholders
- [ ] **Extrair `maksetup_core/`** — separar `base.py`, `git.py`, `ui.py`, `installers.py` do script monolítico atual
- [ ] **Definir API estável do `SetupBase`** — quais métodos são `@abstractmethod`, quais são opcionais, assinaturas
- [ ] **Definir contrato de `results`** — como cada derivada reporta sucesso/falha para o orquestrador consolidar
- [ ] **Escolher repositório piloto** — implementar a primeira derivada (sugestão: `maktrak-hw`, o mais independente)
- [ ] **Implementar orquestrador** — `sys.path` injection + `importlib` + loop de `run()`
- [ ] **Testar em Linux + Windows** — validar ciclo completo com 1 repo piloto
- [ ] **Planejar rollback** — se o modelo não funcionar, voltar ao monolito ou migrar para YAML (Arq. A)

# MakTrak — Plano de implementação do instalador

## Introdução

Objetivos principais
- Fornecer um script Python executável em Windows e Linux para instalar/configurar ferramentas por categoria (mecânica, eletrônica, firmware, servidor, IA, etc.).
- Ser idempotente e verificável (testes/validações após instalação).
- Atualizar o sistema operacional (`apt upgrade` / `winget upgrade`) sempre que executado.
- Clonar um conjunto configurável de repositórios antes das instalações.

Requisitos e restrições
- Suportar Windows 10/11 e Xubuntu 26.04.
- Instalações de GUI no Linux podem usar `snap` quando disponível; no Windows usar `winget`/`choco` se disponível, com fallback para instaladores oficiais.
- Atualizar o sistema operacional (`apt update && apt upgrade -y` / `winget upgrade --all`) sempre que executado, sem flags CLI.
- O script deve pedir privilégios elevados quando necessário (administrador/sudo).
- Validar presença de dependências (ex.: `git`) e instalar apenas quando ausentes.
- Argumentos via CLI (`--update-os`, etc.) serão implementados apenas nas etapas finais, se necessário.

## Sequência de implementação

1. Implementação inicial do script
   - Criar `maktrak_setup.py` com um fluxo simples e direto, sem camada de opções complexa.
   - Implementar a execução básica em passos claros: detectar ambiente, selecionar modo (dev ou prod), atualizar ambiente (mandatório), validar dependências, confirmar ações com o usuário, clonar repositórios, instalar ferramentas, validar resultado.
   - Evitar abstrações e módulos extras no início; o objetivo é entregar um instalador funcional.
   - Armazenar a lista de repositórios e definições de módulo dentro de `maktrak_setup.py`, sem depender de arquivos externos.

2. Perguntas ao usuário:
  - Seleção de modo de execução
    - Perguntar ao usuário se deseja criar um ambiente de `dev` ou `prod`.
    - O modo `dev` deve permitir seleção livre de categorias e componentes de desenvolvimento, incluindo a opção `todos`.
    - O modo `prod` deve permitir escolha livre entre `servidor-prod` e `IA interna`, incluindo 'todos'.
    - Os contextos de `servidor-dev` e `servidor-prod` são mutuamente exclusivos em cada execução.

3. Detecção de ambiente e inicialização
   - Detectar sistema operacional e ambiente de execução (WSL, headless, CI).
   - Identificar gerenciadores de pacote disponíveis (`snap`, `apt`, `winget`, `choco`, `pip`, etc.).
   - Validar dependências básicas como `git` antes de iniciar o fluxo.
   - Após a detecção e seleção de modo, executar a atualização de ambiente (mandatória) antes de prosseguir com instalações.

4. Clonagem de repositórios
   - Preâmbulo (instalar git + Sublime Merge juntos):
     - instalar `git` (sempre verificar/instalar)
     - instalar `sublime-merge` (sempre verificar/instalar)
     - Os dois são instalados no mesmo passo — "ferramentas de controle de versão".
   - Definir repositórios diretamente no script e clonar de acordo.
   - Aplicar retries e logging para falhas de rede ou autenticação.
   - Suportar clonagem autenticada do GitHub via token pessoal em variável de ambiente (`GITHUB_TOKEN` ou `GH_TOKEN`).
   - Diretório de clonagem:
     - Linux: `~/repos/movingmak/maktrak/<nome-do-repo>`
     - Windows: `%USERPROFILE%\repos\movingmak\maktrak\<nome-do-repo>`
   - Associar cada repositório ao Sublime Merge:
     - Após clonar, executar `sublime-merge --background <caminho-do-repo>` (ou `smerge.exe --background` no Windows) para abrir o repositório sem trazer a janela para o foco.
     - Isso evita múltiplos popups durante o setup.
     - O SM gerencia automaticamente a lista de repositórios recentes na barra lateral.
   - Repositórios a clonar:
     - `ambiente` — https://github.com/MovingMAK/maktrak-ambiente.git
     - `servidores` — https://github.com/MovingMAK/maktrak-server.git
     - `hardware` — https://github.com/MovingMAK/maktrak-hw.git
     - `firmware` — https://github.com/MovingMAK/maktrak-app.git
     - `aplicativos` — https://github.com/MovingMAK/maktrak-app.git

5. Instalação e validação de módulos
   - Para cada módulo habilitado (apenas o dos componentes selecionados):
     - Verificar se já está instalado usando comando de verificação configurável.
     - Se não estiver presente, executar instalador adequado.
     - Executar verificações pós-instalação.
   - Linux: instalação via `snap` preferencialmente; `apt` como fallback.
   - Windows: instalação via `winget`.
   - Programas individuais:
     - **vscode**: `snap install code --classic` (Linux) / `winget install Microsoft.VisualStudioCode` (Windows)
     - **arduino-cli**: `snap install arduino-cli` (Linux) / `winget install Arduino.ArduinoCLI` (Windows)
     - **freecad**: `snap install freecad` (Linux) / `winget install FreeCAD.FreeCAD` (Windows)
     - **kicad**: `snap install kicad` (Linux) / `winget install KiCad.KiCad` (Windows)
     - **flutter**: `snap install flutter --classic` (Linux) / `winget install Flutter.Flutter` (Windows)
       - Após instalar, executar `flutter config --enable-web --enable-linux-desktop` (linux) ou `--enable-windows-desktop` (windows)
       - Executar `flutter precache` para baixar cache de todas as plataformas
     - **Android SDK + AVDs** (quando app estiver entre os componentes selecionados):
       - Instalar JDK: `sudo apt install -y default-jdk-headless` (Linux) / winget (Windows)
       - Verificar/disponibilizar KVM no Linux:
         - `sudo apt install -y qemu-kvm libvirt-daemon-system libvirt-clients bridge-utils virt-manager`
         - `sudo adduser $USER kvm` (exige logout/login p/ efetivar)
         - Verificar `/dev/kvm` e `kvm-ok`
       - `flutter doctor --android-licenses` (aceitar licenças Android)
       - Instalar Android SDK cmdline-tools via `sdkmanager`
       - Criar 2 AVDs via `avdmanager`:
         - Um com a API level mais recente estável
         - Um com a API level mais usada no mundo (ex.: API 34 / Android 14)
   - Gerar relatório final com status por módulo: `OK`, `failed`, `warnings`.

6. Extras:
  - Em caso de Windows, programe o atalho ctrl+alt+t para abrir o powershell.
  - Caso tiver vscode instalado
    - configure o seguinte:
      - menu "open recent" aumentar para 20
    - instale as seguintes extensões:
      - `GitHub.vscode-pull-request-github` — GitHub Pull Requests (todos)
      - `yzhang.markdown-all-in-one` — Markdown All in One (todos)
      - `zaaack.markdown-editor` — Markdown Editor (todos)
      - `ms-python.python` — Python (todos)
      - `dart-code.dart-code` — Dart (app, servidor)
      - `dart-code.flutter` — Flutter com debug (app, servidor)
      - `platformio.platformio-ide` — PlatformIO IDE (apenas firmware)

7. Testes e validação
   - Validar a instalação com sucesso de cada item instalado.
   - Para softwares, testar builds de projetos já baixados nos repositórios:
     - firmware usando compilador Arduino.
     - app usando Flutter para:
       - plataforma nativa (`Linux` ou `Windows`),
       - web,
       - Android.
     - servidor-web (categoria `servidor` em dev) deve compilar para saída web usando Flutter.
     - servidor-prod deve ser capaz de hospedar uma página e testar acessos HTTP.
     - IA interna deve ser exposta por uma porta externa TCP/UDP e subir um serviço que responda a um prompt determinístico e conciso, por exemplo:
       - `Responda qual é o tipo em C para ponto flutuante de 64 bits. Responda exatamente apenas o tipo.`
       - saída esperada: `double`
   - Verificar ferramentas com comandos como `--version`, `--help` ou outras verificações apropriadas quando aplicável.
   - Documentar o risco de `--update-os` e manter o padrão desligado fora do modo `servidor-prod`.
   - Referenciar o plano detalhado em [TESTING.md](TESTING.md).

8. Melhorias e observabilidade
   - Adicionar suporte a logs e telemetria básicos.
   - Refinar validações e relatórios de execução.
   - Planejar suporte a containerização como etapa posterior.

9. Segurança, licenças, permissões e compatibilidade
   - Definir políticas de licença e uso de software proprietário.
   - Revisar tratamento de permissões e compatibilidade entre Windows e Linux.
   - Revisar, como último passo do desenvolvimento, itens relacionados a EULAs, termos e permissões, sem que isso impacte o escopo inicial.
   - Expandir o escopo conforme necessário.

## Próximos artefatos a implementar
- `maktrak_setup.py` (esqueleto CLI e detectores de SO).
- `IMPLEMENTATION_QUESTIONS.md` com dúvidas a esclarecer antes da implementação.

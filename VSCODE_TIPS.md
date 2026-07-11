# VS Code — Extensões e Configurações

Este documento lista as extensões e ajustes aplicados automaticamente pelo script de setup, organizados por componente.

## Extensões instaladas

### Para todos os componentes

| Extensão | ID | Função |
|----------|----|--------|
| GitHub Pull Requests | `GitHub.vscode-pull-request-github` | Revisar PRs, gerenciar issues, code review |
| Markdown All in One | `yzhang.markdown-all-in-one` | Atalhos, TOC, formatação de Markdown |
| Markdown Editor | `zaaack.markdown-editor` | Editor visual de Markdown |
| Python | `ms-python.python` | Suporte Python (LSP, debug, virtualenv) |

### Para app e servidor (Flutter/Dart)

| Extensão | ID | Função |
|----------|----|--------|
| Dart | `dart-code.dart-code` | Suporte à linguagem Dart (LSP, snippets, formatação) |
| Flutter | `dart-code.flutter` | Desenvolvimento Flutter com **debug completo**: breakpoints, step through, hot reload, inspeção de variáveis, widget inspector |

### Para firmware

| Extensão | ID | Função |
|----------|----|--------|
| PlatformIO IDE | `platformio.platformio-ide` | Desenvolvimento para microcontroladores (Arduino, ESP32, etc.) |

## Configurações aplicadas

| Ajuste | Valor | Descrição |
|--------|-------|-----------|
| `workbench.editor.limit.value` | `20` | Aumenta o histórico "Open Recent" para 20 itens |

## Atalhos úteis (Linux)

| Atalho | Ação |
|--------|------|
| `Ctrl+Shift+P` | Paleta de comandos |
| `F5` | Iniciar depuração Flutter |
| `Ctrl+F5` | Executar sem depuração |
| `Shift+F5` | Parar depuração |
| `Ctrl+Shift+D` | Painel de depuração |
| `Ctrl+\`` | Terminal integrado |
| `Ctrl+Shift+Y` | Painel de saída (debug console) |

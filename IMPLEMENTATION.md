# MakTrak — Plano de implementação do instalador

## Introdução

Resumo: documento curto descrevendo o objetivo, restrições e design proposto para um script Python multiplataforma que cria/configura ambientes de desenvolvimento e produção para o projeto MakTrak.

Objetivos principais
- Fornecer um script Python executável em Windows e Linux para instalar/configurar ferramentas por categoria (mecânica, eletrônica, firmware, servidor, IA, etc.).
- Ser idempotente e verificável (testes/validações após instalação).
- Permitir controlar se o script atualiza o sistema operacional (flag `--update-os`, padrão: desligado).
- Clonar um conjunto configurável de repositórios antes das instalações.

Requisitos e restrições
- Suportar Windows 10/11 e Xubuntu 24.04/26.04.
- Instalações de GUI no Linux podem usar `snap` quando disponível; no Windows usar `winget`/`choco` se disponível, com fallback para instaladores oficiais.
- O script deve pedir privilégios elevador quando necessário (administrador/sudo) e suportar um modo não-interativo (`--yes`).
- Validar presença de dependências (ex.: `git`) e instalar apenas quando ausentes.
- `--update-os` deve ser opção explícita do usuário no início do script em contextos gerais, mas deve ser impositivo para criar um ambiente de servidor-prod.

## Sequência de implementação

1. Implementação inicial do script
   - Criar `maktrak_setup.py` com um fluxo simples e direto, sem camada de opções complexa.
   - Implementar a execução básica em passos claros: selecionar modo (dev ou prod), detectar ambiente, validar dependências, clonar repositórios, instalar ferramentas, validar resultado.
   - Evitar abstrações e módulos extras no início; o objetivo é entregar um instalador funcional.
   - Armazenar a lista de repositórios e definições de módulo dentro de `maktrak_setup.py`, sem depender de arquivos externos.

2. Seleção de modo de execução
   - Perguntar ao usuário se deseja criar um ambiente de `dev` ou `prod`.
   - O modo `dev` deve permitir seleção livre de categorias e componentes de desenvolvimento, incluindo a opção `todos`.
   - O modo `prod` deve permitir escolha livre entre `servidor-prod` e `IA interna`, incluindo 'todos'.
   - Os contextos de `servidor-dev` e `servidor-prod` são mutuamente exclusivos em cada execução.

3. Detecção de ambiente e inicialização
   - Detectar sistema operacional e ambiente de execução (WSL, headless, CI).
   - Identificar gerenciadores de pacote disponíveis (`snap`, `apt`, `winget`, `choco`, `pip`, etc.).
   - Validar dependências básicas como `git` antes de iniciar o fluxo.

3. Clonagem de repositórios
   - Definir repositórios diretamente no script e clonar de acordo.
   - Aplicar retries e logging para falhas de rede ou autenticação.
   - Garantir que o destino de clonagem respeite o padrão configurado.
   - Suportar clonagem autenticada do GitHub via token pessoal em variável de ambiente (`GITHUB_TOKEN` ou `GH_TOKEN`).
   - Padronizar diretório de clonagem:
     - Linux: `~/home/repos/maktrak/<nome-do-repo>`
     - Windows: equivalente à raiz de usuário apropriada.

4. Instalação e validação de módulos
   - Para cada módulo habilitado:
     - Verificar se já está instalado usando comando de verificação configurável.
     - Se não estiver presente, executar instalador adequado:
       - Linux: `snap`, `apt`, `apt-get`, `pip`, etc.
       - Windows: `winget`, `choco`, instaladores `.exe`/`.msi`.
       - SDKs/IDEs específicos: `vscode`, `arduino`, `flutter`, `freecad`, `kicad`.
     - Executar verificações pós-instalação (por exemplo, `code --version`, `arduino-cli version`, `kicad --version`).
   - Gerar relatório final com status por módulo: `OK`, `failed`, `warnings`.

5. Exemplo de ferramentas e repositórios iniciais
   - Geral: `git` (sempre verificar/instalar).
   - Editores: `sublime-text`, `sublime-merge`.
   - IDEs/SDKs: `vscode`, `arduino`, `flutter`, `freecad`, `kicad`.
   - Repositórios iniciais a clonar:
     - `ambiente` — https://github.com/MovingMAK/maktrak-ambiente.git
     - `servidores` — https://github.com/MovingMAK/maktrak-server.git
     - `hardware` — https://github.com/MovingMAK/maktrak-hw.git
     - `firmware` — https://github.com/MovingMAK/maktrak-app.git
     - `aplicativos` — https://github.com/MovingMAK/maktrak-app.git

6. Testes e validação
   - Validar a instalação com sucesso de cada item instalado.
   - Para softwares, testar builds de projetos já baixados nos repositórios:
     - firmware usando compilador Arduino.
     - app usando Flutter para:
       - plataforma nativa (`Windows` ou `Linux`),
       - web,
       - Android.
     - servidores dev devem compilar para saída web usando Flutter.
     - servidores prod devem ser capazes de hospedar uma página e testar acessos.
     - IA interna deve subir um serviço TCP/UDP e responder a um prompt básico, por exemplo, "olá" com algo como "olá" ou outra resposta simples e previsível.
   - Verificar ferramentas com comandos como `--version`, `--help` ou outras verificações apropriadas quando aplicável.
   - Documentar o risco de `--update-os` e manter o padrão desligado fora do modo `servidor-prod`.
   - Referenciar o plano detalhado em [TESTING.md](TESTING.md).

7. Melhorias e observabilidade
   - Adicionar suporte a logs e telemetria básicos.
   - Refinar validações e relatórios de execução.
   - Planejar suporte a containerização como etapa posterior.

8. Segurança, licenças, permissões e compatibilidade
   - Definir políticas de licença e uso de software proprietário.
   - Revisar tratamento de permissões e compatibilidade entre Windows e Linux.
   - Colocar instalações que exigem aceitação de EULAs, termos ou permissões elevadas como último passo do fluxo.
   - Documentar claramente quando `--yes` pode ser usado para ignorar prompts e quando a aceitação deve ser manual.
   - Expandir o escopo conforme necessário.

## Próximos artefatos a implementar
- `maktrak_setup.py` (esqueleto CLI e detectores de SO).
- `IMPLEMENTATION_QUESTIONS.md` com dúvidas a esclarecer antes da implementação.

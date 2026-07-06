# MakTrak — Plano de implementação do instalador

## Introdução

Objetivos principais
- Fornecer um script Python executável em Windows e Linux para instalar/configurar ferramentas por categoria (mecânica, eletrônica, firmware, servidor, IA, etc.).
- Ser idempotente e verificável (testes/validações após instalação).
- Permitir controlar se o script atualiza o sistema operacional (flag `--update-os`, padrão: desligado).
- Clonar um conjunto configurável de repositórios antes das instalações.

Requisitos e restrições
- Suportar Windows 10/11 e Xubuntu 24.04/26.04.
- Instalações de GUI no Linux podem usar `snap` quando disponível; no Windows usar `winget`/`choco` se disponível, com fallback para instaladores oficiais.
- O script deve pedir privilégios elevador quando necessário (administrador/sudo).
- Validar presença de dependências (ex.: `git`) e instalar apenas quando ausentes.
- `--update-os` deve ser opção explícita do usuário no início do script em contextos gerais, mas deve ser impositivo para criar um ambiente de servidor-prod.

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
   - Preâmbulo (instalar): 
     - instalar `git` (sempre verificar/instalar) 
     - Editores: `sublime-text`, `sublime-merge`.
   - Definir repositórios diretamente no script e clonar de acordo.
   - Aplicar retries e logging para falhas de rede ou autenticação.
   - Suportar clonagem autenticada do GitHub via token pessoal em variável de ambiente (`GITHUB_TOKEN` ou `GH_TOKEN`).
   - Diretório de clonagem:
     - Linux: `~/home/repos/maktrak/<nome-do-repo>`
     - Windows: equivalente à raiz de usuário apropriada.
   - associar cada repositório ao sublime-merge (não sei como faz de forma eficiente).
   - Repositórios a clonar:
     - `ambiente` — https://github.com/MovingMAK/maktrak-ambiente.git
     - `servidores` — https://github.com/MovingMAK/maktrak-server.git
     - `hardware` — https://github.com/MovingMAK/maktrak-hw.git
     - `firmware` — https://github.com/MovingMAK/maktrak-app.git
     - `aplicativos` — https://github.com/MovingMAK/maktrak-app.git
   - depois de cada clone, associe o repositório ao sublime-merge.

5. Instalação e validação de módulos
   - Para cada módulo habilitado:
     - Verificar se já está instalado usando comando de verificação configurável.
     - Política atual: instalar todos os programas em todos os OS por padrão; exceções serão definidas posteriormente.
     - Se não estiver presente, executar instalador adequado:
       - Linux: `snap`, `apt`, `apt-get`, `pip`, etc.
       - Windows: `winget` (com fallback futuro somente se necessário).
       - SDKs/IDEs específicos: `vscode`, `arduino`, `flutter`, `freecad`, `kicad`.
     - Executar verificações pós-instalação (por exemplo, `code --version`, `arduino-cli version`, `kicad --version`).
   - Gerar relatório final com status por módulo: `OK`, `failed`, `warnings`.

6. Extras:
  - Em caso de Windows, programe o atalho ctrl+alt+t para abrir o powershell.
  - Caso tiver vscode instalado
    - configure o seguinte:
      - menu "open recent" aumentar para 20
    - instale as seguintes extensões:
      - github
      - aquele pra ver .md
      - o que precisa pra arduino

7. Testes e validação
   - Validar a instalação com sucesso de cada item instalado.
   - Para softwares, testar builds de projetos já baixados nos repositórios:
     - firmware usando compilador Arduino.
     - app usando Flutter para:
       - plataforma nativa (`Windows` ou `Linux`),
       - web,
       - Android.
     - servidores dev devem compilar para saída web usando Flutter.
     - servidores prod devem ser capazes de hospedar uma página e testar acessos.
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

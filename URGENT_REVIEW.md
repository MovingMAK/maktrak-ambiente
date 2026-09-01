# Revisao urgente do MakTrak Setup

Data da revisao: 2026-08-06

Este documento consolida os pontos encontrados na revisao conjunta do
orquestrador, das derivadas e da documentacao. Nenhuma correcao descrita aqui
foi aplicada ainda.

## Bloqueadores

### 1. Producao falha em uma maquina limpa

O modo `prod` nao clona repositorios, mas o orquestrador exige a existencia de
`repo_setup.py` em `~/repos/movingmak/maktrak/servidores/`. Assim, uma maquina
de producao sem clone previo falha antes de executar qualquer configuracao.

- Codigo: `maktrak_setup.py`, `_get_repositories_to_clone()` e `main()`.
- Impacto: instalacao de producao nao e autonoma.
- Direcao: clonar o repositorio de servidores/deploy tambem em `prod`, ou
  carregar uma configuracao de producao explicitamente versionada pelo
  bootstrap.

### 2. Perfil `servidor-prod` executa tarefas de desenvolvimento

`servidor-prod` e `servidor` carregam a mesma `ServerSetup`. Ela instala VS
Code, prepara um venv de desenvolvimento e tenta gerar builds Flutter web.

Alem disso, mesmo corrigindo o compartilhamento de classe, `ServerSetup` nao
deixa a API rodando de forma duradoura: `configure()` so builda os apps web e
`test()` sobe o `uvicorn` na porta 8787 apenas para checar uma resposta e mata
o processo em seguida (`proc.terminate()`), sem criar unit systemd nem
configurar o nginx (sem `server` block, sem reverse proxy). Ao contrario de
`IaSetup`, que cria units systemd de verdade para Ollama/Open WebUI,
`servidor-prod` hoje nao entrega nenhum servico persistente.

- Codigo: `servidores/repo_setup.py`, `SETUP_CLASSES` e `ServerSetup`.
- Impacto: ambiente de producao recebe ferramentas e tarefas desnecessarias;
  uma falha de build pode bloquear uma configuracao que deveria apenas servir
  a aplicacao. Mesmo com sucesso, nao ha API nem site persistente no ar apos
  o setup terminar.
- Direcao: criar `ProductionServerSetup` dedicado a runtime, servicos,
  configuracao e health checks (unit systemd para o uvicorn + config real de
  nginx). Manter builds no perfil de desenvolvimento ou no CI.

### 3. Requisitos declarados nao correspondem ao que e instalado

`DEV_MODULES` e `PROD_MODULES` alimentam selecao e resumo, mas as derivadas
tomam suas proprias decisoes de instalacao. Por exemplo, `servidor` declara
Flutter, mas `ServerSetup.install()` nao o instala e `configure()` chama
`flutter build web`.

- Codigo: `maktrak_setup.py`, `DEV_MODULES`/`PROD_MODULES`; e
  `servidores/repo_setup.py`, `ServerSetup`.
- Impacto: uma instalacao pode falhar por dependencia ausente apesar de o
  resumo afirmar que ela seria instalada.
- Direcao: cada derivada deve ser dona de seus requisitos. O orquestrador deve
  guardar somente metadados de selecao, repositorios e perfis.

### 4. Falhas de operacoes criticas podem nao aparecer no resultado

Varios helpers executam subprocessos e descartam o retorno. As derivadas
podem continuar apos uma falha e validar artefatos de execucoes anteriores.

- Codigo: `maktrak_setup.py`, `flutter_build()`, `flutter_test()`,
  `flutter_config()`, `setup_android()` e instaladores; derivadas de app,
  firmware e servidores.
- Impacto: relatorio final pode indicar sucesso incompleto ou diagnosticar a
  causa errada.
- Direcao: helpers de acao devem retornar `bool` ou `CompletedProcess`; as
  derivadas devem registrar cada resultado e interromper passos dependentes.

## Riscos altos

### Contrato do bootstrap com as derivadas nao e versionado

O usuario pode escolher uma branch dos repositorios, mas baixa um bootstrap de
outra revisao. `load_derived()` nao valida que a derivada requer a mesma API de
`SetupBase`.

- Impacto: uma derivada pode chamar um helper ausente ou com comportamento
  alterado.
- Direcao: definir `SETUP_API_VERSION` no bootstrap e
  `REQUIRES_SETUP_API` em cada derivada; validar antes de instanciar a classe.

### Android usa caminhos e configuracoes divergentes

O instalador termina no fallback `~/Android/Sdk`, enquanto o guia Windows usa
`%LOCALAPPDATA%\\Android\\Sdk`. O script tampouco persiste `ANDROID_HOME` ou
`ANDROID_SDK_ROOT` depois de instalar as command-line tools.

- Impacto: Flutter pode nao encontrar o SDK instalado numa maquina nova.
- Direcao: usar o caminho padrao por sistema, persistir as variaveis de
  ambiente e validar `flutter doctor` apos a instalacao.

### Fluxo de Android deve propagar resultados

As licencas agora sao gravadas antes de `sdkmanager --install`, eliminando o
prompt para imagens AVD. Porem, instalacao do JDK, KVM, ferramentas, SDK e AVD
ainda nao retorna um resultado composto para a derivada.

- Impacto: um APK pode falhar muito depois de uma etapa Android ja ter falhado.
- Direcao: `setup_android()` deve retornar `False` quando uma dependencia
falhar; `create_avd()` deve retornar o status de criacao ou de existencia.

Alem disso, `setup_android()` ja retorna `bool`, mas quem chama o ignora e
segue para `create_avd(...)` mesmo assim. (O build Android agora vive no setup
do servidor.)
- Impacto: falha do SDK Android e mascarada; `create_avd` roda contra um SDK
  potencialmente incompleto.
- Direcao: interromper `configure()` (ou marcar falha nos `results`) quando
  `setup_android()` retornar `False`.

### Token GitHub exposto via linha de comando

`_git_auth_header()` monta um header `Authorization: Basic <token em base64>`
e `_git_run_with_retry()` injeta esse header via `-c http.extraHeader=...`
como argumento do processo `git`. O valor fica visivel para outros
processos/usuarios da mesma maquina via `ps` ou `/proc/<pid>/cmdline` enquanto
o comando roda.

- Codigo: `maktrak_setup.py`, `_git_auth_header()` e `_git_run_with_retry()`.
- Impacto: vazamento local do PAT do usuario em maquinas compartilhadas.
- Direcao: evitar passar segredos via argv; usar um arquivo de config git
  temporario (permissao 0600) com `-c include.path=...` e remove-lo apos o
  comando, ou depender apenas do `credential.helper store` ja configurado.

### Elevacao de privilegios duplicada e fragil no Windows

`_windows_prepare_terminal()` ja reabre o script elevado dentro do Windows
Terminal via PowerShell `-EncodedCommand` (comando interno codificado em
base64). Se essa elevacao falhar silenciosamente, o fluxo continua e
`_sys_require_admin()` tenta elevar de novo por outro caminho
(`ShellExecuteW`/`runas`), sem reaproveitar a janela WT.

- Codigo: `maktrak_setup.py`, `_windows_prepare_terminal()` e
  `_sys_require_admin()`.
- Impacto: dois mecanismos de elevacao independentes para manter e testar;
  falha silenciosa de um e mascarada pelo outro.
- Direcao: unificar num unico caminho de elevacao, com log claro do metodo
  usado e falha explicita se nenhum funcionar.

### `git pull --force` sem checar o `checkout` anterior

Em `_git_clone_one()`, o resultado de `git checkout branch` e descartado
(`capture_output=True` sem checagem de `returncode`). Se o checkout falhar
(ex.: alteracoes locais nao commitadas), o `pull --force` seguinte roda na
branch errada sem aviso claro.

- Codigo: `maktrak_setup.py`, `_git_clone_one()`.
- Impacto: atualizacao silenciosa na branch errada num repositorio ja
  clonado.
- Direcao: checar o `returncode` do checkout e abortar/avisar antes do pull.

## Complexidade desnecessaria

### Helpers nao utilizados em `SetupBase`

`write_config()`, `append_line()`, `create_symlink()`, `service_enable()` e
`service_restart()` nao sao chamados por nenhum dos 5 `repo_setup.py` atuais.
`IaSetup`, que precisaria exatamente desses helpers para nginx/systemd,
reimplementa tudo na mao com `self._run(["sudo", "tee", ...])`.

- Codigo: `maktrak_setup.py`, `SetupBase`.
- Impacto: superficie de API especulativa que ninguem usa nem testa.
- Direcao: remover os helpers nao usados ou migrar `IaSetup`/`ServerSetup`
  para usa-los, eliminando a duplicacao.

## Arquitetura recomendada

Manter `maktrak_setup.py` pequeno em responsabilidades de infraestrutura:

- interface com usuario, privilegios e atualizacao do sistema;
- clone, autenticacao Git e carregamento versionado das derivadas;
- catalogo de pacotes e primitives reutilizaveis para subprocessos, arquivos,
  VS Code, Flutter, Android, Python e PlatformIO;
- execucao de fases e consolidacao de resultados.

Transferir para as derivadas as decisoes de dominio:

- ferramentas necessarias por perfil;
- extensoes do VS Code;
- versoes/AVDs Android requeridos pelo app;
- builds, servicos, modelos IA, configuracoes e health checks;
- definicao de sucesso de cada fase.

O objetivo nao e criar mais camadas: e eliminar as duas fontes de verdade
atuais, o catalogo de modulos no bootstrap e as instalacoes efetivas nas
derivadas.

## Documentacao inconsistente

### README

O comando de bootstrap aponta para a branch `docs-de-implementacao`, enquanto
o cabecalho de `maktrak_setup.py` aponta para `main`.

- Direcao: definir uma unica URL oficial, preferencialmente com release/tag
  imutavel para instalacoes de producao.

### IMPLEMENTATION.md

O arquivo e um plano historico e diverge do comportamento atual: cita Arduino
CLI, Flutter via winget, `flutter doctor --android-licenses`, configuracao de
Xfce removida e requisitos de producao nao implementados.

- Direcao: mover para `docs/history/` ou marcar claramente como historico.
  Criar uma especificacao operacional curta e atualizada.

### ANALISE_SPLIT.md

Tambem e uma analise previa e descreve componentes removidos ou substituidos,
como Arduino CLI, KiCad 9, Xfce e Flutter via winget.

- Direcao: preservar como decisao historica, com aviso no topo, sem apresenta-lo
  como referencia de implementacao atual.

### ANDROID-SETUP.md

O guia manual usa command-line tools `14742923`, enquanto o instalador baixa
`11076708`. Tambem pede `sdkmanager --licenses`, embora o fluxo automatizado
grave as aprovacoes antes do download.

- Direcao: escolher uma unica versao ou explicar como atualizar ambas. Separar
  explicitamente o fluxo manual do fluxo automatizado.

### VSCODE_TIPS.md

A lista esta defasada em relacao a `_vscode_install_base()`: faltam Jupyter,
Clang Format, GitLens, Copilot Chat, DeepSeek, TOML e Markdown Preview
Enhanced; inclui Markdown All in One, que o script nao instala.

- Direcao: tornar este documento a fonte de verdade e alinhar o codigo a ele,
  ou gerar a lista a partir de uma unica constante.

### IMPLEMENTATION_QUESTIONS.md

Contem perguntas ja respondidas e um rascunho de trabalho. A secao 4 (deploy
de API/webhook/rollback), porem, continua sendo uma decisao de arquitetura
em aberto e nao implementada em lugar nenhum do codigo — nao deve ser
arquivada junto com o resto.

- Direcao: encerrar as perguntas ja resolvidas (secoes 1-3) e manter a secao 4
  como pendencia ativa, nao como historico.

## Testes necessarios antes da refatoracao

A suite atual cobre apenas escrita de credenciais e a presenca de Git no host.
Adicionar testes com mocks para:

- selecao de perfis e repositorios em `dev` e `prod`;
- compatibilidade de versao bootstrap/derivada;
- propagacao de falhas de subprocessos e relatorio final;
- instalacao Android, licencas antes de downloads e criacao de AVD;
- carregamento correto de `ServerSetup`, `ProductionServerSetup` e `IaSetup`;
- instalacao de Flutter requerida pelo servidor de desenvolvimento;
- reexecucao idempotente de pacotes, venvs e PlatformIO;
- checkout falho antes do pull (nao deve seguir silenciosamente para o pull
  na branch errada);
- header de autenticacao git nao deve aparecer em argv de processos filhos.

O teste de Git deve simular o executavel; hoje ele depende do ambiente que roda
a suite.

## Ordem de execucao recomendada

1. Tornar o perfil de producao inicializavel em maquina limpa.
2. Separar `ServerSetup` de `ProductionServerSetup`.
3. Consolidar ownership de requisitos nas derivadas e ajustar o resumo da UI.
4. Propagar resultados de comandos criticos ate o relatorio final.
5. Corrigir caminho, variaveis de ambiente e validacao do SDK Android.
6. Corrigir exposicao de credencial via argv no clone/pull e o `checkout`
   silencioso antes do `pull --force`.
7. Remover helpers nao utilizados de `SetupBase` ou migrar `IaSetup`/
   `ServerSetup` para usa-los; unificar a elevacao de privilegios no Windows.
8. Adicionar testes de contrato antes de mudancas maiores.
9. Reescrever README e criar documentacao operacional; arquivar planos
   historicos (mantendo a secao 4 de `IMPLEMENTATION_QUESTIONS.md` como
   pendencia ativa).
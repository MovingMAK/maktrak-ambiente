# MakTrak Setup — Dúvidas em aberto

Decisões ainda não fechadas para o instalador. As perguntas já resolvidas
foram removidas ou absorvidas pelos documentos correspondentes
(`IMPLEMENTATION.md`, `TESTING.md`, `ANDROID-SETUP.md`, `VSCODE_TIPS.md`).

## Produção / IA (etapa pausada)

O modo `prod` é selecionável (componente `servidor-prod`) e **não** instala
ferramentas de dev nem builda: ele delega para o `server_setup.py`, que clona o
repositório do servidor e chama o `install_server.py` (venv + serviço +
health check na porta 8000). Falta o reverse proxy. Antes de fechar a etapa:

1. Qual servidor IA usar inicialmente? (vLLM, MLX, llama.cpp, Exo ou outro —
   KISS). Decisão de arquitetura.
2. Que serviços o ambiente de produção deve entregar (API persistente,
   reverse proxy nginx, health checks)? **Parcialmente respondido**: o
   `install_server.py` entrega a API como serviço (porta 8000, systemd ou
   `schtasks`) e um health check na instalação. Continuam em aberto o nginx e os
   health checks contínuos.

## Testes

3. Ampliar a suíte automatizada (hoje só cobre escrita de credenciais git e
   presença do git) para: seleção e clone de componentes, carga de
   derivadas, propagação de falhas até o relatório e instalação Android.
   Ver a seção "Testes necessários" em `URGENT_REVIEW.md`.

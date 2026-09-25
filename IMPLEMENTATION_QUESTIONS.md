# MakTrak Setup — Dúvidas em aberto

Decisões ainda não fechadas para o instalador. As perguntas já resolvidas
foram removidas ou absorvidas pelos documentos correspondentes
(`IMPLEMENTATION.md`, `TESTING.md`, `ANDROID-SETUP.md`, `VSCODE_TIPS.md`).

## Produção / IA (etapa pausada)

O modo `prod` é selecionável (componente `servidor-prod`) e **não** clona
repositório nem builda: ele delega para o `server_setup.py`, que entrega o
runtime e o recebedor de deploy como serviço systemd. Os **serviços de produção**
completos ainda não estão implementados. Antes de fechar a etapa:

1. Qual servidor IA usar inicialmente? (vLLM, MLX, llama.cpp, Exo ou outro —
   KISS). Decisão de arquitetura.
2. Que serviços o ambiente de produção deve entregar (API persistente,
   reverse proxy nginx, health checks)? **Parcialmente respondido** pelo
   `server_setup.py` (recebedor em 8001, via systemd). Continuam em aberto a
   unit/nginx para a API em si (porta 8000) e os health checks contínuos.

## Testes

3. Ampliar a suíte automatizada (hoje só cobre escrita de credenciais git e
   presença do git) para: seleção e clone de componentes, carga de
   derivadas, propagação de falhas até o relatório e instalação Android.
   Ver a seção "Testes necessários" em `URGENT_REVIEW.md`.

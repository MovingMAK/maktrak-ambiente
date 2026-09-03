# MakTrak Setup — Dúvidas em aberto

Decisões ainda não fechadas para o instalador. As perguntas já resolvidas
foram removidas ou absorvidas pelos documentos correspondentes
(`IMPLEMENTATION.md`, `TESTING.md`, `ANDROID-SETUP.md`, `VSCODE_TIPS.md`).

## Produção / IA (etapa pausada)

O modo `prod` está pausado e sem módulos definidos. Antes de retomá-lo:

1. Qual servidor IA usar inicialmente? (vLLM, MLX, llama.cpp, Exo ou outro —
   KISS). Decisão de arquitetura.
2. Que serviços o ambiente de produção deve entregar (API persistente,
   reverse proxy nginx, health checks)? Define o futuro
   `ProductionServerSetup` em `maktrak-server`.

## Testes

3. Ampliar a suíte automatizada (hoje só cobre escrita de credenciais git e
   presença do git) para: seleção e clone de componentes, carga de
   derivadas, propagação de falhas até o relatório e instalação Android.
   Ver a seção "Testes necessários" em `URGENT_REVIEW.md`.

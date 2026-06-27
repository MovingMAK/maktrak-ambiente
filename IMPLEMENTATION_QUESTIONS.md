# Perguntas e dúvidas para implementação do MakTrak setup

Este documento lista apenas as questões ainda em aberto, depois das definições já incorporadas ao plano de implementação.

1. Política de atualização do OS
- O comportamento padrão desejado é manter `--update-os` desligado para instalações gerais?
- Para o modo `servidor-prod`, a atualização de OS deve ser obrigatória?
- Quais comandos ou gestores de pacote devemos usar para atualizar o OS em cada plataforma?

2. Escolha de modo e categorias
- O script deve perguntar ao usuário se ele quer um ambiente `dev` ou `prod`?
- No modo `dev`, o usuário deve poder escolher qualquer combinação de categorias, incluindo `todos`?
- No modo `prod`, o usuário deve escolher entre `servidor-prod` e `IA interna`?
- `servidor-dev` está claramente dentro do modo `dev` e deve ser mutuamente exclusivo com `servidor-prod` em cada execução?

3. IA interna e ambiente de serviço
- O ambiente de IA deve ser exposto por uma porta externa TCP/UDP?
- Qual tipo de servidor IA devemos usar inicialmente?
- O teste básico de IA deve apenas validar uma resposta simples como "olá" -> "olá"?

4. Permissões, EULAs e aceitação de termos
- O modo `--yes` deve aceitar automaticamente EULAs/termos quando possível?
- Devemos deixar instalações que exigem aceitação manual de EULAs para o último passo do fluxo?

5. Testes automatizados
- Devemos testar a instalação bem-sucedida de cada item?
- Para software, devemos testar builds de projetos baixados, incluindo:
  - firmware com compilador Arduino;
  - app usando Flutter para plataforma nativa, web e e Android;
  - servidores dev com build para saída web via Flutter;
  - servidores prod com hospedagem de página e teste de acesso;
  - IA interna com serviço TCP/UDP respondendo a um prompt simples.
- Existem testes que devem ser opcionais por limitação de ambiente?

6. Lista mínima de componentes
- Há ferramentas ou SDKs adicionais obrigatórios para IA ou servidor-prod além do que já foi citado?

7. Referências
- Há mais recursos ou referências além do link fornecido ([https://share.google/aimode/jQQQFq4VttHpozdoF](https://share.google/aimode/jQQQFq4VttHpozdoF))?

Por favor responda somente as questões em aberto para que eu mantenha o documento enxuto e alinhado com o plano de implementação.
# Perguntas e dúvidas para implementação do MakTrak setup

Este documento lista apenas as questões ainda em aberto, depois das definições já incorporadas ao plano de implementação.

1. Política de atualização do OS
- Quais comandos ou gestores de pacote devemos usar para atualizar o OS em cada plataforma?

2. IA interna e ambiente de serviço
- O ambiente de IA deve ser exposto por uma porta externa TCP/UDP?
- Qual tipo de servidor IA devemos usar inicialmente?
- O teste básico de IA deve apenas validar uma resposta simples como "olá" -> "olá"?
- Sobre IA: estou incerto de como fazer, então trago alguns termos para discussão: vLLM, MLX, llama.cpp e Exo. Não sei se ajudam ou atrapalham, mas podem inspirar um caminho de implementação, que deve ser KISS.

3. Testes automatizados
- Devemos testar a instalação bem-sucedida de cada item?
- Existem testes que devem ser opcionais por limitação de ambiente?

4. Lista mínima de componentes
- Há ferramentas ou SDKs adicionais obrigatórios para IA ou servidor-prod além do que já foi citado?

5. Referências
- Há mais recursos ou referências além do link fornecido ([https://share.google/aimode/jQQQFq4VttHpozdoF](https://share.google/aimode/jQQQFq4VttHpozdoF))?

Por favor responda somente as questões em aberto para que eu mantenha o documento enxuto e alinhado com o plano de implementação.
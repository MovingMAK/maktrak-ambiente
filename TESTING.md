# Métodos de teste do MakTrak setup

Este documento reúne as abordagens de validação do script de setup do MakTrak. A ideia é separar as decisões de teste do escopo principal de implementação.

## Objetivo

Garantir que o script funcione corretamente em diferentes ambientes, com foco em:
- validação de instalação de ferramentas;
- verificação de dependências;
- checagem de comandos de pós-instalação;
- detecção de falhas e relatórios claros.

## Estratégias de teste

### 1. Testes unitários
- Validar funções de detecção de sistema operacional.
- Validar parsing de arquivos de configuração.
- Validar lógica de decisão de instalação.
- Validar regras de idempotência.

### 2. Testes de instalação em ambiente real
- Executar o script em um sistema limpo ou já preparado.
- Verificar se cada ferramenta é instalada ou ignorada corretamente.
- Confirmar se comandos de verificação funcionam após a instalação.

### 3. Testes de regressão
- Reexecutar o script após alterações.
- Garantir que ele não reaplica instalações desnecessariamente.
- Confirmar que o comportamento permanece consistente.

### 4. Teste com máquina virtual
- O uso de máquina virtual pode ser adotado como técnica de teste complementar, especialmente para validar o comportamento em ambientes diferentes sem alterar o host principal.
- Isso é uma estratégia de validação do script, não parte da automação de instalação.
- A VM pode ser usada para simular sistemas Windows/Linux e observar o comportamento do script em cenários controlados.

## Critérios de aceitação

Um teste é considerado satisfatório quando:
- a instalação ocorre sem erro quando a ferramenta está ausente;
- a execução é segura quando a ferramenta já existe;
- o script gera logs claros e status compreensíveis;
- falhas são reportadas sem interromper todo o fluxo de forma inesperada.

## Observações

- O uso de VM é opcional e complementar.
- A automação principal do script não depende de VM.
- Containers podem ser considerados mais adiante, mas não fazem parte da primeira etapa.

# TODO — MakTrak

> Pendências que atravessam os repositórios. Item resolvido sai daqui.

## 1. Nomenclatura de arquivos: a regra contradiz o que está versionado

`NAMING_CONVENTIONS.md` exige nomes de **arquivo** em inglês e kebab-case. Na prática:

- `firmware/docs/`: `PADROES_CODIGO.md`, `ARQUITETURA_TAREFAS.md`, `MIGRACAO_DOCUMENTACAO.md`,
  `DECISAO_ACELEROMETRO_I2C.md`, `GUIA_USO_VSCODE.md` — SCREAMING_SNAKE e em português.
- `servidores/`: `ANALISE_PROTOCOLOS_SERVER.md`, `tranqueiras/`.

Risco: a regra foi promovida ao guia genérico (`AI_agent_guide_generic.md`, seção
Idioma), então um agente pode lê-la como mandato para propor renames em massa.

Decisão pendente — escolher uma:

- (a) isentar documentação na regra: aplicar a nomenclatura a código, banco, API e
  endpoints, não a nomes de arquivos de doc;
- (b) padronizar de fato os documentos existentes;
- (c) aceitar a divergência e remover a menção a "arquivos" da regra.

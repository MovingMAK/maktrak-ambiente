# Naming Conventions — MakTrak

Este documento define os padrões de nomenclatura adotados em todo o projeto MakTrak, abrangendo banco de dados, API, código e documentação.

---

## 1. Idioma

**Todos os nomes** (tabelas, campos, variáveis, endpoints, arquivos) devem estar em **inglês**. Exceções permitidas apenas em textos descritivos e mensagens para o usuário final.

---

## 2. Tabelas de Banco de Dados

| Regra | Exemplo |
|-------|---------|
| PascalCase | `CommonEquips`, `GeolocationEvents` |
| Singular (entidade por registro) | `Company`, `Person` (não `Companies`, `People`) |
| Substantivo ou frase nominal | `FirmwareUpdates`, `ValveTriggerEvents` |

> **Nota:** Tabelas no plural (`Companies`, `People`, `Vehicles`, `Events`) foram mantidas por legibilidade da relação (1 empresa → N veículos → N eventos). Consistência prevalece sobre a regra do singular.

---

## 3. Campos de Banco de Dados e Variáveis de Código

### 3.1. Formato

```
thisIsMyName_type
```

- **camelCase** — primeira letra minúscula, palavras subsequentes maiúsculas.
- **Sufixo `_type`** — obrigatório **apenas** para tipos não óbvios.

### 3.2. Sufixos Obrigatórios (`_type`)

O sufixo `_type` explicita o **tipo de dado** quando este não é óbvio pelo nome ou pelo tipo SQL:

| Sufixo | Quando usar | Exemplos |
|--------|-------------|----------|
| `_int` | Inteiro com semântica de escala/deslocamento (não é contagem pura) | `latitude_int`, `longitude_int` |

> ⚠️ **Unidades de medida não são sufixos de tipo.** Unidades integram o nome em camelCase. Exemplos: `signalDbm`, `internalTempC`, `pressureBar` — o `Dbm`, `C` e `Bar` fazem parte do nome descritivo, não são sufixos tipológicos.

### 3.3. Sufixos Proibidos (implícitos pelo tipo do DB)

- `_id`, `_text`, `_integer`, `_real`, `_blob` — o tipo SQL já carrega essa informação.

### 3.4. Exceções — Nomes Curtos Consagrados

Campos de uso universal ou óbvios pelo contexto **não levam sufixo**:

| Campo | Tipo | Motivo |
|-------|------|--------|
| `id` | INTEGER | PK — toda tabela tem |
| `value` | INTEGER | Óbvio pelo contexto do evento |
| `name` | TEXT | Universal |
| `mac` | TEXT | Formato MAC conhecido |
| `plate` | TEXT | Placa veicular — formato conhecido |
| `epoch` | INTEGER | Timestamp Unix — formato padrão |
| `offset` | INTEGER | Paginação — universal |
| `limit` | INTEGER | Paginação — universal |
| `cpf` / `cnpj` | TEXT | Documentos brasileiros — formato conhecido |

---

## 4. Campos de Timestamp (Epoch)

### 4.1. Nomenclatura

| Contexto | Nome do campo | Descrição |
|----------|---------------|-----------|
| Genérico / leitura | `epoch` | Quando o contexto já deixa claro o que é (ex: `events.epoch`) |
| Momento específico | `{descricao}Epoch` | Ex: `activationEpoch`, `commissioningEpoch`, `decommissioningEpoch`, `registrationEpoch` |
| Dois timestamps relacionados | `{descricao}AtEpoch` | Ex: `capturedAtEpoch` (no hardware), `storedAtEpoch` (no servidor) |
| Confirmação de hardware | `confirmedAtEpoch` | Ex: firmware update confirmado |

---

## 5. Endpoints da API

| Regra | Exemplo |
|-------|---------|
| Kebab-case em inglês | `/maktrak/api/v0.3/telemetry/event` |
| Sem verbos nos caminhos (o HTTP method já é o verbo) | ✅ `POST /equipment/commission` ❌ `POST /equipment/doCommission` |
| Coleções no plural | `/events`, `/companies`, `/vehicles`, `/logs` |
| Recurso específico no singular | `/equipment/{uid}`, `/company/{uid}/logo` |

---

## 6. Resumo Visual

| Contexto | Estilo | Exemplo Correto | Exemplo Errado |
|----------|--------|-----------------|----------------|
| Tabela DB | PascalCase | `GeolocationEvents` | `geolocation_events` |
| Campo DB / Variável | camelCase + `_type` | `latitude_int`, `isActive_bool` | `latitude`, `isActive` |
| Endpoint | kebab-case | `/telemetry/events` | `/telemetryEvents` |
| Arquivo | kebab-case | `proposta-db.md` | `Proposta DB.md` |
| JSON (API) | camelCase | `"sensorMac"` | `"sensor_mac"` |

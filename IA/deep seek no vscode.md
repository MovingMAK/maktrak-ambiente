# Deep Seek no vscode

---
---

Garante que você mantenha toda a inteligência de contexto de projeto, agentes e indexação nativa do VS Code, apenas substituindo o "cérebro" pelo DeepSeek. [1]
Abaixo, veja como configurar os dois métodos: o seu principal (Copilot) e a sua segunda opção guardada (Continue). [2, 3]

## 🔑 Pré-requisitos (comum às duas opções)

1. **Crie sua conta** e gere uma chave de API em https://platform.deepseek.com/api_keys
   (Tutorial alternativo: https://developer.puter.com/tutorials/how-to-get-deepseek-api-key/)
2. **Copie a chave** (começa com `sk-`) — você vai colar ela adiante.
3. **Adicione créditos** em https://platform.deepseek.com/top_up ($2 já basta pra testar)

> ⚠️ Guarde sua chave em local seguro (Keepass, Bitwarden, etc). Não a comite em repositórios públicos nem compartilhe.

---

## 🚀 Opção 1 — GitHub Copilot Chat (Principal)

A ponte oficial recomendada pela DeepSeek injeta os modelos direto no seletor nativo do Copilot. [1, 4]

1. **Instale a extensão** — `Ctrl+Shift+X` → busque `DeepSeek V4 for Copilot Chat` (Vizards) e instale.
2. **Informe a chave** — `Ctrl+Shift+P` → `DeepSeek: Set API Key` → cole sua chave (começa com `sk-`) e Enter.
3. **Recarregue** se a extensão pedir (`Ctrl+Shift+P` → `Developer: Reload Window`).
4. **Abra o chat do Copilot** — clique no ícone do Copilot na barra lateral (ou `Ctrl+Shift+I`).
5. **Selecione o modelo** — na base do chat, clique no seletor e mude para **DeepSeek V4 Flash**.
   > 💡 Se preferir o **Pro**, a troca é só aqui (mas a qualquer tempo).
6. **Abra o painel Output** — `Ctrl+Shift+U` → no dropdown de canais, selecione `DeepSeek`.
7. **Teste** — mande um "oi" no chat. No Output aparecem linhas como (valores e formato podem variar):
   ```
   cache: hit=23552 miss=5044 rate=82%
   ```
   ou (linha completa):
   ```
   2026-07-07 22:28:14.423 [info] [main-agent] tokens: model=deepseek-v4-flash prompt=28596 completion=38 | cache: hit=23552 miss=5044 rate=82% | chars/tok=2.97
   ```
   > O importante é o `rate`. Acima de 90%? ✅ Tudo certo. Não apareceu nada? Recarregue o VS Code e tente de novo.

Dicas: 
  > 💡 Configuramos para **DeepSeek V4 Flash**, mas se preferir o **Pro**, basta trocar. O custo e a potência são maiores.

---

## 📂 Opção 2 — Continue (Backup, não testada)

Caso queira usar a extensão Continue como alternativa, configure o JSON abaixo. [2, 8]

1. Instale a extensão **Continue** no VS Code.
2. Clique no ícone do Continue na barra lateral → engrenagem ⚙️ → abre o `config.json`.
3. Substitua ou adicione o bloco abaixo dentro da lista `"models"`:

```json
{
  "models": [
    {
      "title": "DeepSeek V4 Pro (Reasoning)",
      "provider": "openai",
      "model": "deepseek-v4-pro",
      "apiKey": "SUA_CHAVE_API_AQUI_SK-...",
      "apiBase": "https://api.deepseek.com"
    },
    {
      "title": "DeepSeek V4 Flash (Fast)",
      "provider": "openai",
      "model": "deepseek-v4-flash",
      "apiKey": "SUA_CHAVE_API_AQUI_SK-...",
      "apiBase": "https://api.deepseek.com"
    }
  ],
  "tabAutocompleteModel": {
    "title": "DeepSeek V4 Flash Autocomplete",
    "provider": "openai",
    "model": "deepseek-v4-flash",
    "apiKey": "SUA_CHAVE_API_AQUI_SK-...",
    "apiBase": "https://api.deepseek.com"
  }
}
```

> Substitua `SUA_CHAVE_API_AQUI_SK-...` pela chave que você criou nos pré-requisitos (nos 3 campos).

4. **Abra o chat do Continue** — clique no ícone do Continue na barra lateral (ou `Ctrl+Alt+I`).
5. **Teste** — no canto inferior do chat, selecione `DeepSeek V4 Flash` no dropdown de modelos e mande uma mensagem.

[1] [https://github.com](https://github.com/Vizards/deepseek-v4-for-copilot)
[2] [https://deepseekai.guide](https://deepseekai.guide/tutorials/deepseek-with-vscode/)
[3] [https://chat-deep.ai](https://chat-deep.ai/guide/deepseek-v4-vscode/)
[4] [https://api-docs.deepseek.com](https://api-docs.deepseek.com/quick_start/agent_integrations/github_copilot)
[5] [https://github.com](https://github.com/ChenyuHeee/deepseek-copilot)
[6] [https://www.reddit.com](https://www.reddit.com/r/GithubCopilot/comments/1tzx9ke/deepseek_v4_for_github_copilot_setup_guide/)
[7] [https://chat-deep.ai](https://chat-deep.ai/guide/deepseek-github-copilot-chat/)
[8] [https://github.com](https://github.com/continuedev/continue/issues/440)

---

## 🧠 Cache Hit — entendendo e monitorando

O DeepSeek usa **KV-cache**: quando o início do prompt se repete entre chamadas, essa parte não é reprocessada e o custo cai drasticamente.

### hit / miss / rate

| Termo | O que é | Custa | Ideal |
|---|---|---|---|
| **Hit** 🟢 | Tokens **já processados** antes, reaproveitados do cache | Mínimo (~$0,0028/1M) | Quanto maior, melhor |
| **Miss** 🔴 | Tokens **novos** processados do zero | Cheio ($0,14/1M) | Quanto menor, melhor |
| **Rate** 🚀 | `hit ÷ (hit + miss)` — % de reaproveitamento | — | **>90%** é o normal |

> Na prática, se você **mantém o assunto num mesmo chat**, o rate fica acima de 90% naturalmente. Não precisa de técnica sofisticada.

### Flash vs Pro

| | **V4 Flash** 🏎️ | **V4 Pro** 🧠 |
|---|---|---|
| **Melhor para** | 90% do dia a dia: codar, revisar, debug, explicar | Problemas complexos, raciocínio profundo, arquitetura |
| **Velocidade** | Mais rápido | Mais lento (pensa mais) |
| **Contexto** | 1M tokens | 1M tokens |
| **Cache hit input** | $0,0028/1M | $0,0036/1M |
| **Cache miss input** | $0,14/1M | $0,435/1M |
| **Output** | $0,28/1M | $0,87/1M |

> 💡 **Regra prática:** comece sempre com **Flash**. Só troque para Pro se o Flash não der conta (problemas muito complexos).

### ✅ Boas práticas no dia a dia

| ✅ Faz | ❌ Evita |
|---|---|
| Manter o **mesmo chat** para o mesmo assunto/projeto | Abrir chat novo a cada pergunta |
| **Agrupar perguntas relacionadas** na mesma conversa | Perguntas soltas em chats separados |
| Incluir bloco de contexto fixo no início (`CONTEXTO_PROJETO.md`) | Variar a primeira linha do prompt (datas, IDs, carimbos) |
| **Monitorar o rate** no painel Output (`Ctrl+Shift+U`) | Ignorar o cache — você pode estar pagando mais que o necessário |
| Ficar atento se o chat está **muito longo** — tokens antigos podem sair do cache | Deixar o histórico crescer sem nunca verificar o rate |

### 🔍 Como monitorar na prática

**Via painel Output:**
`Ctrl+Shift+U` → no dropdown de canais, selecione `DeepSeek`

Você vê logs como:
```
cache: hit=87808 miss=878 rate=99%
```

**O que olhar:**
- `rate` acima de 90%? ✅ Tudo certo, menor custo.
- `rate` caiu muito? Pode ser: chat novo, mudança de assunto, ou histórico muito longo.
- `miss` subindo? Reveja as boas práticas acima.

### 📐 Prefixo (FIM) — técnica avançada

O DeepSeek V4 Flash suporta **Fill-in-the-Middle (FIM)**: você define um trecho fixo (`prefix`) reutilizado entre chamadas via API direta.

```python
prefix = "def calcular_total(items):"
suffix = "    return total"
```

> ⚠️ **Não essencial.** Com as boas práticas acima você já atinge >90% de rate naturalmente. FIM só é relevante se você estiver usando a **API diretamente** (não pelo Copilot) para autocomplete ou geração em lote.

---

## 💰 Preços (para uso pesado)

Se você usa DeepSeek intensamente (centenas de chamadas/dia), o custo ainda é bem menor que o Copilot. Mas é bom saber os números:

### Pico/Vale (BRT = UTC-3)

| Horário (BRT) | Preço |
|---|---|
| **22h–01h** 🔴 | Dobrado (2×) |
| **01h–03h** 🟢 | Normal |
| **03h–07h** 🔴 | Dobrado (2×) |
| **07h–22h** 🟢 | Normal |

> 💡 Use das **7h às 22h** — a maior parte do dia é preço normal.

### Tabela DeepSeek

| Modelo | Input (hit) | Input (miss) | Output |
|---|---|---|---|
| **V4 Flash** 🏎️ | $0,0028/1M | $0,14/1M | $0,28/1M |
| **V4 Pro** 🧠 | $0,0036/1M | $0,435/1M | $0,87/1M |

### Comparação com Copilot

| Situação | Recomendação |
|---|---|
| Uso leve esporádico | Copilot **Free** ✅ já resolve |
| Uso intenso (dev solo) | **DeepSeek API** 🚀 (~$2-5/mês vs $10/mês Copilot Pro) |
| Já assina Copilot Pro ($10) | Use os **$15 créditos** pra rodar DeepSeek sem custo extra |

# Outros

## pesquisas

https://share.google/aimode/GKYiQaDiIz1pkR7F8


# MakTrak Ambiente

Configuração rápida de ambiente para desenvolvimento e produção no projeto MakTrak.

## O que o `maktrak_setup.py` faz

O script:
- detecta o sistema operacional e ferramentas disponíveis;
- pergunta o modo de execução (`dev` ou `prod`) e os componentes;
- coleta/reutiliza credenciais GitHub para repositórios privados;
- clona/atualiza os repositórios necessários;
- tenta associar cada repositório ao Sublime Merge após clone/pull.

## Windows (PowerShell)

1. Instalar Python 3 via `winget`:

```powershell
winget install --id Python.Python.3 -e
```

Reinicie automaticamente o terminal para atualizar o PATH:

```powershell
Start-Process powershell -ArgumentList "-NoExit","-Command","Set-Location '$PWD'"; exit
```

2. Baixar e executar o script (linha única):

```powershell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/MovingMAK/maktrak-ambiente/refs/heads/docs-de-implementacao/maktrak_setup.py" -OutFile "$env:TEMP\maktrak_setup.py"; python "$env:TEMP\maktrak_setup.py"
```

## Linux (Debian/Ubuntu/Xubuntu)

1. Instalar Python 3 e `curl`:

```bash
sudo apt update && sudo apt install -y python3 curl
```

2. Baixar e executar o script (linha única):

```bash
curl -fsSL "https://raw.githubusercontent.com/MovingMAK/maktrak-ambiente/refs/heads/docs-de-implementacao/maktrak_setup.py" -o /tmp/maktrak_setup.py && python3 /tmp/maktrak_setup.py
```

## Observações

- O download do `maktrak_setup.py` é feito de repositório público.
- Durante a execução, o script pode pedir usuário/token do GitHub para acessar repositórios privados da organização.

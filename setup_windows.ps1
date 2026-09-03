<#
MakTrak Setup - bootstrap (Windows)

Instala o Python 3 (se ausente), baixa o maktrak_setup.py e o executa.
Pre-requisito: winget (presente por padrao no Windows 10/11).

Uso:
    powershell -ExecutionPolicy Bypass -File setup_windows.ps1
    # ou: irm "<url deste arquivo>" | iex
#>
$ErrorActionPreference = "Stop"

$Url    = "https://raw.githubusercontent.com/MovingMAK/maktrak-ambiente/main/maktrak_setup.py"
$Target = Join-Path $env:TEMP "maktrak_setup.py"

# 0. Requisitos basicos (TLS 1.2+ p/ o download; winget presente)
[Net.ServicePointManager]::SecurityProtocol = `
    [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw "winget nao encontrado. Instale o 'App Installer' (winget) e rode de novo."
}

# 1. Instala/garante o Python 3, sem perguntar nem testar antes. Se o Python
#    ja estiver instalado, o winget apenas informa "already installed" (nao e
#    falha — o passo 3 e quem valida).
Write-Host "Instalando/garantindo o Python 3 via winget..."
winget install --id Python.Python.3.12 -e --source winget --silent `
    --accept-package-agreements --accept-source-agreements

# 2. Revalida o PATH do processo a partir do registro (Machine + User)
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + `
            [System.Environment]::GetEnvironmentVariable("Path", "User")

# 3. Verifica ao final
& python3 --version
if ($LASTEXITCODE -ne 0) {
    # Caso comum no Windows: o comando `python3` ainda cai no alias da
    # Microsoft Store (WindowsApps vem antes no PATH). O launcher `py`
    # (instalado em System32) confirma o Python real e e usado para rodar.
    & py -3 --version
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3 nao respondeu apos a instalacao. Feche e reabra o terminal e rode de novo."
    }
    Write-Warning "python3 apontou para o alias da Store; usando 'py' para executar."
    $pythonCmd = "py"
} else {
    $pythonCmd = "python3"
}

# 4. Baixa e executa o instalador
Write-Host "Baixando maktrak_setup.py..."
Invoke-WebRequest -Uri $Url -OutFile $Target
& $pythonCmd $Target

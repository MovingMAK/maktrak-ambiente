# Android build and deploy setup via terminal

Este guia instala apenas o necessario para buildar e deployar um app Flutter em um celular Android fisico, sem Android Studio.

Requisitos minimos:

- JDK 17
- Android SDK command-line tools
- `platform-tools` / `adb`
- uma Android SDK Platform
- uma versao de Android Build Tools
- licencas do Android SDK aceitas
- depuracao USB ativa no celular

As URLs abaixo usam as command-line tools atuais da pagina oficial do Android em 2026-06-30: `14742923_latest`. Se algum link falhar no futuro, copie a URL nova na secao "Command line tools only" da pagina oficial:

https://developer.android.com/studio#command-line-tools-only

## Windows PowerShell

Instale o JDK 17:

```powershell
winget install --id EclipseAdoptium.Temurin.17.JDK -e
```

Crie a estrutura minima do Android SDK:

```powershell
$env:ANDROID_HOME="$env:LOCALAPPDATA\Android\Sdk"
New-Item -ItemType Directory -Force "$env:ANDROID_HOME\cmdline-tools\latest" | Out-Null
```

Baixe e instale as Android command-line tools:

```powershell
Invoke-WebRequest `
  -Uri "https://dl.google.com/android/repository/commandlinetools-win-14742923_latest.zip" `
  -OutFile "$env:TEMP\cmdline-tools.zip"

Expand-Archive "$env:TEMP\cmdline-tools.zip" "$env:TEMP\android-cmdline-tools" -Force
Copy-Item "$env:TEMP\android-cmdline-tools\cmdline-tools\*" "$env:ANDROID_HOME\cmdline-tools\latest" -Recurse -Force
```

Persista as variaveis de ambiente do usuario:

```powershell
[Environment]::SetEnvironmentVariable("ANDROID_HOME", $env:ANDROID_HOME, "User")
[Environment]::SetEnvironmentVariable(
  "Path",
  [Environment]::GetEnvironmentVariable("Path","User") +
    ";$env:ANDROID_HOME\cmdline-tools\latest\bin;$env:ANDROID_HOME\platform-tools",
  "User"
)
```

Feche e reabra o terminal. Depois instale os pacotes minimos do SDK:

```powershell
sdkmanager "platform-tools" "platforms;android-36" "build-tools;36.0.0"
sdkmanager --licenses
```

Verifique a instalacao:

```powershell
flutter doctor -v
adb devices
flutter devices
```

Opcionalmente, se o celular nao aparecer em `adb devices`, instale o driver USB do Google:

```powershell
sdkmanager "extras;google;usb_driver"
```

Muitos aparelhos ainda precisam do driver USB especifico do fabricante.

## Linux Debian/Ubuntu

Instale o JDK 17 e ferramentas basicas:

```bash
sudo apt update
sudo apt install -y openjdk-17-jdk curl unzip
```

Instale regras USB para detectar celulares fisicos:

```bash
sudo apt install -y android-sdk-platform-tools-common
```

Crie a estrutura minima do Android SDK:

```bash
export ANDROID_HOME="$HOME/Android/Sdk"
mkdir -p "$ANDROID_HOME/cmdline-tools/latest"
```

Baixe e instale as Android command-line tools:

```bash
curl -L \
  "https://dl.google.com/android/repository/commandlinetools-linux-14742923_latest.zip" \
  -o /tmp/cmdline-tools.zip

unzip -q /tmp/cmdline-tools.zip -d /tmp/android-cmdline-tools
cp -r /tmp/android-cmdline-tools/cmdline-tools/* "$ANDROID_HOME/cmdline-tools/latest/"
```

Persista as variaveis de ambiente:

```bash
cat >> ~/.bashrc <<'EOF'
export ANDROID_HOME="$HOME/Android/Sdk"
export PATH="$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools"
EOF

source ~/.bashrc
```

Instale os pacotes minimos do SDK:

```bash
sdkmanager "platform-tools" "platforms;android-36" "build-tools;36.0.0"
sdkmanager --licenses
```

Verifique a instalacao:

```bash
flutter doctor -v
adb devices
flutter devices
```

## Celular Android

No aparelho, ative:

```text
Opcoes do desenvolvedor -> Depuracao USB
```

Conecte por USB e aceite a autorizacao RSA no celular quando solicitado.

## Build e deploy

Rodar direto no celular conectado:

```bash
flutter run -d <device-id>
```

Gerar APK debug:

```bash
flutter build apk --debug
```

Instalar APK debug manualmente:

```bash
adb install -r build/app/outputs/flutter-apk/app-debug.apk
```

Gerar APK release:

```bash
flutter build apk --release
```

Instalar APK release manualmente:

```bash
adb install -r build/app/outputs/flutter-apk/app-release.apk
```

Nao e necessario instalar Gradle globalmente. Projetos Flutter usam o Gradle wrapper em `android/`.

## Fontes oficiais

- Android command-line tools: https://developer.android.com/studio#command-line-tools-only
- `sdkmanager`: https://developer.android.com/tools/sdkmanager
- Flutter install/setup: https://docs.flutter.dev/get-started/install

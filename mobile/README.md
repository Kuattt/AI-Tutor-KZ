# AI Tutor KZ — Mobile v0.1

Minimal Expo/React Native client for Backend v1.1. The app connects only to
FastAPI; it never connects to Ollama directly.

## Requirements

- Node.js 22.13+ (Node 24 LTS is used in this workspace)
- npm
- Android Studio emulator or equivalent Android SDK emulator
- Backend v1.1 and Ollama running locally

## Install and configure

```powershell
cd "C:\Users\parpi\OneDrive\Рабочий стол\sdhjshdhsud\ai-tutor-kz\mobile"
npm install
Copy-Item .env.example .env
```

The default development URL is:

```env
EXPO_PUBLIC_API_BASE_URL=http://10.0.2.2:8000
```

On the standard Android emulator, `10.0.2.2` maps to the host computer's
loopback interface. `127.0.0.1` inside the emulator points to the emulator
itself. Keep the backend as the only AI gateway; never configure port `11434`
in the mobile application.

## Start local services

In one PowerShell window:

```powershell
ollama serve
```

In a second window:

```powershell
cd "C:\Users\parpi\OneDrive\Рабочий стол\sdhjshdhsud\ai-tutor-kz\backend"
.\.venv\Scripts\python.exe -m app
```

In a third window, with an Android emulator already running:

```powershell
cd "C:\Users\parpi\OneDrive\Рабочий стол\sdhjshdhsud\ai-tutor-kz\mobile"
npx expo start --android
```

If this Windows environment resolves Metro's `localhost` listener to IPv6 only,
use the emulator gateway explicitly:

```powershell
$sdk = "$env:LOCALAPPDATA\Android\Sdk"
$env:ANDROID_HOME = $sdk
$env:ANDROID_SDK_ROOT = $sdk
$env:Path = "$sdk\platform-tools;$sdk\emulator;$env:Path"
$env:REACT_NATIVE_PACKAGER_HOSTNAME = "10.0.2.2"
npx expo start --host lan
```

Then open `exp://10.0.2.2:8081` in Expo Go. This does not require a firewall
rule or a tunnel.

Expo loads `.env` automatically. Restart Metro after changing the URL.

## Checks

```powershell
npm test
npm run typecheck
npx expo-doctor
```

## Common connection problems

- `Backend недоступен`: verify `/health` on the host and use `10.0.2.2`, not
  emulator `127.0.0.1`.
- Session expired: the app creates a fresh backend session, keeps visible chat
  locally, and explicitly warns that old server context is not preserved.
- Ollama/model unavailable: start Ollama and verify that `qwen3.5:9b` exists;
  the mobile client still talks only to FastAPI.
- A stopped response is intentionally not retried. Partial text remains marked
  as stopped, and another message can be sent immediately.

Sessions and visible messages are in memory for Mobile v0.1 and are not
restored after the application restarts.

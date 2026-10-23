# AI Tutor KZ

Local-first educational AI tutor for school students in Kazakhstan.

This repository contains **Backend v1.1** and the **Mobile v0.2** development
client.
FastAPI connects to the locally installed Ollama model `qwen3.5:9b`, while the
Expo/React Native app creates multi-turn tutor sessions and renders POST-SSE
responses progressively.

Mobile v0.2 adds local conversation persistence, honest server-session
recovery, connection diagnostics, and native Markdown/LaTeX rendering for
completed tutor responses. No cloud AI API or direct mobile-to-Ollama access is
used.

- Backend setup and commands: [backend/README.md](backend/README.md)
- Mobile setup and Android emulator commands: [mobile/README.md](mobile/README.md)
- Architecture notes: [docs/architecture.md](docs/architecture.md)

No account system, database, cloud AI API, RAG, or analytics service is included
in this milestone. The mobile client communicates only with FastAPI.


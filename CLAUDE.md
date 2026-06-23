# CLAUDE.md

## 📓 Knowledge vault — ВЕДИ ЗАПИСИ
Цей проєкт (ai-daily-report) — частина homelab klimnyk.dev. Важливі рішення, прогрес,
нотатки → пиши у **vault** (через MCP-сервер `vault`, шлях C:\Users\mklim\Vault):
- архітектурні рішення → `decisions/`
- нотатки по проєкту → `pages/` або `work/`
- ідеї на майбутнє → `ideas/`
Формат: українською, з frontmatter (tags, created) + [[wikilinks]].
Оновлюй записи після значущих змін.

## 🏗️ Контекст
- Docker-проєкт → деплой у LXC 204 (192.168.31.172), Portainer/SSH.
- Розробка локально F:\Projects\ai-daily-report → Syncthing Send Only → сервер.
- Ліби (node_modules/venv/...) НЕ синкаються — контейнер ставить сам.

## 🔐 Правила
- Секрети — у Vaultwarden / `.env` (НЕ комітити, не синкається).
- Перед великими змінами — короткий план.
# AI Daily Report Generator

Автоматичний генератор щоденних звітів на основі активності в GitLab, Jira та Clockify з використанням OpenAI.

## 🚀 Можливості

- **GitLab Integration**: Отримання комітів з усіх доступних проектів за сьогодні
- **Jira Integration**: 
  - Задачі в роботі (In Progress)
  - Задачі, закриті сьогодні (по кастомних полях дати)
  - Огляд дошок
- **Clockify Integration**: Записи відстеження часу
- **OpenAI Report Generation**: 
  - Підтримка `prompt_id` для збережених промптів
  - Responses API
- **Email Delivery**: Автоматична відправка звітів на email

## 📋 Формат звіту

Звіт пишеться простою мовою для нетехнічного читача. Ключі Jira автоматично
перетворюються на клікабельні посилання з назвою задачі, а лист надсилається у
форматі HTML (з plain-text запасним варіантом).

```
Що робив: Розробка та тестування VIN OCR
В рамках: AUTOMOTO-123 — OCR service integration   ← стає посиланням на Jira
Висновок: Провів тести та зафіксував результати в Confluence
Jira status: Done

---
*This report was generated using AI based on task statistics and monitoring metrics.*
Model used: OpenAI gpt-4o
```

> **Захист від «вигадування»:** кількість пунктів дорівнює реально підтвердженим
> даним (1–5). Якщо за день немає комітів і закритих задач, звіт будується ВИКЛЮЧНО
> із записів Clockify (один пункт на запис) і не доповнюється задачами з беклогу.

## 🔧 Встановлення

```bash
# Клонування репозиторію
git clone <repo-url>
cd ai-daily-report

# Створення віртуального середовища
python -m venv venv
.\venv\Scripts\activate  # Windows
source venv/bin/activate # Linux/Mac

# Встановлення залежностей
pip install -r requirements.txt

# Налаштування змінних середовища
cp .env.example .env
# Відредагуйте .env файл
```

## ⚙️ Конфігурація

Створіть `.env` файл з наступними змінними:

### Обов'язкові
```env
OPENAI_API_KEY=sk-...
```

### GitLab
```env
GITLAB_TOKEN=glpat-...
GITLAB_URL=https://gitlab.com  # або ваш self-hosted GitLab
```

### Jira
```env
JIRA_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-api-token
# Кастомні поля для дат (опціонально)
JIRA_CLOSED_DATE_FIELD=customfield_10100
JIRA_START_DATE_FIELD=customfield_10101
```

### Clockify
```env
CLOCKIFY_API_KEY=your-clockify-api-key
```

### OpenAI
```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
# OPENAI_PROMPT_ID=prompt_abc123  # ЗАСТАРІЛО: reusable prompt objects вимикають 30.11.2026, не використовується
```

> Промпт керується у коді й версіонується в git: `system_role.md` (правила/роль —
> передається як `instructions`) та `prompt.md` (постановка задачі — додається до `input`).
> Це відповідає офіційному гайду міграції OpenAI: reusable prompt objects
> (`OPENAI_PROMPT_ID`) **застаріли** — їх вимикають **30.11.2026**, тож параметр
> ігнорується (лише попередження в логах) і його можна прибрати з `.env`.

### Email
```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SENDER_EMAIL=your-email@gmail.com
RECIPIENT_EMAILS=recipient1@example.com,recipient2@example.com
```

### Інші
```env
REQUIRE_CLOCKIFY_ENTRIES=true  # Чи вимагати записи Clockify для генерації звіту
```

## 🏃 Запуск

```bash
python main.py
```

## 📁 Структура проекту

```
ai-daily-report/
├── main.py              # Головний файл
├── prompt.md            # Шаблон промпту (постановка задачі)
├── system_role.md       # Системна роль для OpenAI
├── requirements.txt     # Залежності
├── .env.example         # Приклад конфігурації
├── gitlab/
│   ├── __init__.py
│   └── client.py        # GitLab API клієнт
├── jira/
│   ├── __init__.py
│   └── client.py        # Jira API клієнт
├── clockify/
│   ├── __init__.py
│   └── client.py        # Clockify API клієнт
├── report/
│   └── generator.py     # Генератор звітів з OpenAI
└── mailer/
    ├── __init__.py
    └── sender.py        # Email відправка
```

## 🔑 Отримання API токенів

### GitLab Personal Access Token
1. Перейдіть до Settings → Access Tokens
2. Створіть токен з правами `read_api`, `read_repository`

### Jira API Token
1. Перейдіть до https://id.atlassian.com/manage-profile/security/api-tokens
2. Створіть новий API токен

### Clockify API Key
1. Перейдіть до Settings → API
2. Скопіюйте ваш API ключ

### OpenAI API Key
1. Перейдіть до https://platform.openai.com/api-keys
2. Створіть новий ключ

## 📝 Ліцензія

MIT

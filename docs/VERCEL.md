# FitControl целиком на Vercel (бесплатно)

Эта версия запускает **всё в одном бесплатном проекте Vercel**: Mini App, API,
Telegram-бот и ежедневные уведомления. Render не нужен.

```
Telegram ──webhook──► https://<проект>.vercel.app/api/v1/telegram/webhook ─┐
Mini App (React)  ──► https://<проект>.vercel.app/api/v1/...              ├─► api/index.py (FastAPI)
Vercel Cron 09:00 ──► https://<проект>.vercel.app/api/v1/ops/cron/...     ┘        │
                                                                                  ▼
                                                             Neon Postgres (бесплатно, через Vercel)
```

Чем отличается от версии на Render:

| | Render | Vercel |
|---|---|---|
| Бот | отдельный worker, long polling | webhook, отдельный процесс не нужен |
| Уведомления | worker-планировщик каждую минуту | Vercel Cron раз в день (09:00 по Ташкенту) |
| База | Render Postgres (бесплатная удаляется через 30 дней) | Neon Postgres (бесплатная не удаляется, 0.5 ГБ) |
| «Засыпание» | да, нужен keep-alive | нет: функция запускается на каждый запрос |
| Mini App и API | два разных домена | один домен, CORS не нужен |

## Шаг 1. Создать проект

1. Vercel → **Add New… → Project** → **Import** репозиторий `Sariofficial23/Fitcontrol`.
2. **Root Directory** оставьте пустым (корень репозитория, **не** `miniapp`).
   Framework Preset: **Other**. Остальное берётся из `vercel.json`.
3. Пока не нажимайте Deploy: сначала база и переменные.

## Шаг 2. База данных (бесплатно)

1. В проекте: **Storage → Create Database → Neon (Serverless Postgres)** →
   бесплатный план → **Connect** к этому проекту.
2. Vercel сам добавит переменную `DATABASE_URL`. Ничего менять не нужно:
   параметры `sslmode` и `channel_binding` код обрабатывает сам.

## Шаг 3. Переменные окружения

**Settings → Environment Variables** (окружение Production):

| Переменная | Значение |
|---|---|
| `TELEGRAM_BOT_TOKEN` | токен от @BotFather |
| `CRON_SECRET` | длинная случайная строка, 32+ символа (например, из генератора паролей) |
| `PLATFORM_ADMIN_IDS` | ваш Telegram ID (через запятую, если несколько) |

Больше ничего не нужно. На Vercel автоматически:
- бот работает через webhook, его секрет вычисляется из токена;
- `WEBAPP_URL`, `PUBLIC_API_URL` и `CORS_ORIGINS` = домен проекта;
- `ENVIRONMENT=production`, вход в dev-режиме заблокирован;
- keep-alive выключен.

Если подключите свой домен, задайте `WEBAPP_URL` и `PUBLIC_API_URL` вручную,
например `https://fit.example.uz`.

## Шаг 4. Deploy и настройка в один клик

1. Нажмите **Deploy** и дождитесь окончания сборки.
2. Откройте в браузере:
   ```
   https://<проект>.vercel.app/api/v1/ops/setup?key=<CRON_SECRET>
   ```
   Эта ссылка: применяет миграции БД, регистрирует webhook бота и ставит кнопку
   меню «FitControl», которая открывает Mini App.
   Ответ `{"ok": true, ...}` значит, что всё готово.
3. Напишите боту `/start`.

Ссылку можно открывать повторно после любого деплоя, это безопасно.
Не публикуйте её: в ней ваш `CRON_SECRET`.

## Шаг 5. Выключить старую версию на Render

**Обязательно остановите (Suspend) Render-сервис `fitcontrol-bot`.** Polling-бот
при запуске удаляет webhook, и тогда Vercel-версия перестанет получать сообщения.

Также отключите GitHub Action `keep-alive` (вкладка **Actions** → keep-alive →
**Disable workflow**): он пингует старый адрес на Render.

### Перенос данных с Render (если они нужны)

На своём компьютере, в папке `backend`:
```bash
# 1. Выгрузить из старой базы (External Database URL из Render)
DATABASE_URL="postgresql://...render..." python -m app.manage backup fitcontrol.json
# 2. Сначала выполните Шаг 4 (миграции), затем загрузите в новую базу Neon
DATABASE_URL="postgresql://...neon..." python -m app.manage restore fitcontrol.json
```
Бесплатная база Render удаляется через 30 дней после создания (и ещё 14 дней
grace-периода), поэтому сделайте это как можно раньше.

## Уведомления

`vercel.json` запускает `/api/v1/ops/cron/notifications` каждый день в 04:00 UTC
(09:00 по Ташкенту). На бесплатном плане Hobby cron срабатывает раз в день и в
пределах указанного часа, поэтому ежедневная сводка уходит при этом запуске
независимо от `DAILY_SUMMARY_HOUR`. Повторы исключены: каждое уведомление
отправляется не больше одного раза в день.

Запустить вручную:
```
https://<проект>.vercel.app/api/v1/ops/cron/notifications?key=<CRON_SECRET>
```

## Ограничения бесплатных планов

- **Vercel Hobby разрешён только для некоммерческого использования.** Когда
  начнёте продавать FitControl клубам, по условиям Vercel нужен план Pro.
- Neon Free: 0.5 ГБ на проект. Для одного-нескольких клубов этого хватит
  надолго.
- Время одного запроса ограничено 60 секундами (`maxDuration` в `vercel.json`).
  Для бота и API этого с запасом.
- Первый запрос после простоя может занять 1–2 секунды (cold start). Сообщения
  при этом не теряются: Telegram сам повторяет доставку webhook.

## Устранение проблем

| Симптом | Что проверить |
|---|---|
| `/ops/setup` → `ops_disabled` | не задан `CRON_SECRET`; после добавления переменной сделайте Redeploy |
| `migrations: error ...` | подключена ли база Neon (переменная `DATABASE_URL`) |
| бот молчит | остановлен ли бот на Render; откройте `/ops/setup` ещё раз |
| Mini App «нет сессии» | Mini App открыта не из Telegram; открывайте через кнопку бота |

Логи: Vercel → проект → **Logs**.

# MOEX Analyst

Веб-сервис по российским акциям MOEX (режим TQBR): графики, новости, макро и ИИ-сценарий на бесплатных источниках.

Это не торговый робот и не обещание доходности. ИИ даёт текстовый сценарий (вверх / вниз / боковик) на основе котировок, новостей и макрофона.

## Что внутри

| Часть | Назначение |
|--------|------------|
| PostgreSQL | Инструменты, свечи, новости, макро, прогнозы |
| FastAPI | REST API + синхронизация с MOEX ISS |
| Worker | Фоновая загрузка справочника, новостей и макро |
| React | Веб-интерфейс на порту 8080 |
| Hugging Face | LLM-аналитик (нужен бесплатный `HF_TOKEN`) |

Старый Telegram-бот лежит в `legacy/` и в этой версии не запускается.

## Требования

На машине нужен только **Docker Desktop** (с WSL2 на Windows). Postgres отдельно ставить не нужно — он поднимается контейнером.

### Windows, первый запуск

1. Docker Desktop ставится через `winget install Docker.DockerDesktop`.
2. Для движка контейнеров нужен **WSL2**. После установки WSL Windows почти всегда просит **перезагрузку**.
3. После ребута запустите Docker Desktop и дождитесь зелёного статуса, затем команды ниже.

## Запуск

```bash
copy .env.example .env
```

В `.env` укажите `HF_TOKEN` с https://huggingface.co/settings/tokens (тип Read достаточно).

```bash
docker compose up --build
```

Откройте http://localhost:8080

Первый запуск: worker подтянет список акций, новости и макро. Свечи по тикеру подгружаются при открытии карточки.

## Перенос на сервер

1. Скопируйте репозиторий и файл `.env` (токен не коммитится).
2. Установите Docker Engine + Compose.
3. `docker compose up -d --build`
4. Откройте порт **8080** (или поменяйте проброс в `docker-compose.yml`).

Данные Postgres живут в volume `postgres_data`. Чтобы уехать на другой сервер вместе с БД: `docker compose down` не удаляет volume; для переноса сделайте `docker compose exec db pg_dump -U moex moex > dump.sql`.

## Источники (все бесплатные)

- Котировки и справочник: [MOEX ISS](https://iss.moex.com)
- Макро: IMOEX, RTSI, RGBI, USD/RUB, CNY/RUB с ISS; ключевая ставка — XML ЦБ РФ
- Новости: RSS ТАСС, Интерфакс, РБК, Коммерсантъ, Ведомости, Лента, РИА; мир — BBC World; сайт MOEX
- ИИ: Hugging Face Inference Providers, модель задаётся в `HF_MODEL` (по умолчанию `Qwen/Qwen3.8-27B`, без локальной загрузки весов)

Платные API можно подменить позже в `backend/app/services/` — контракт сервисов от провайдера не зависит.

## Полезные URL

- UI: http://localhost:8080
- API docs (через nginx): http://localhost:8080/docs
- Health: http://localhost:8080/api/health

# MOEX Analyst

Веб-сервис по российскому рынку MOEX: акции и биржевые фонды TQBR, драгоценные металлы (золото, серебро, платина, палладий), графики, новости, макро и ИИ-сценарий на бесплатных источниках.

Это не торговый робот и не обещание доходности. Модель разбирает дневной график, сверяет его с новостями и даёт сценарий хода цены на 5 торговых сессий (ожидаемый %, коридор, траектория) — не точную целевую цену и не рекомендацию к сделке.

Старый Telegram-бот лежит в `legacy/` и в этой версии не запускается.

## Что поднимается

| Контейнер | Назначение |
|-----------|------------|
| `db` | PostgreSQL 16, данные в volume `postgres_data` |
| `backend` | FastAPI, миграции Alembic, REST `/api` |
| `worker` | Фоновая загрузка справочника, новостей и макро |
| `frontend` | nginx + React, порт **8080**, проксирует `/api` |

Postgres, Python и Node.js на хост ставить не нужно — всё внутри Docker.

---

## Требования

- **Git**
- **Docker** с Compose v2 (команда `docker compose`)
- **8+ ГБ RAM** желательно: сборка фронта и четыре контейнера
- Доступ в интернет: MOEX ISS, RSS, Hugging Face

| ОС | Что ставить |
|----|-------------|
| Windows 10/11 | Docker Desktop + **WSL2** |
| Linux | Docker Engine + плагин Compose |
| macOS | Docker Desktop |

Проверка после установки:

```bash
docker --version
docker compose version
docker info
```

`docker info` должен ответить без ошибки. Если пишет, что не может подключиться к движку — Docker не запущен.

---

## Windows: установка Docker

На Windows контейнеры работают через WSL2. Без него Desktop часто «не стартует».

1. Откройте **PowerShell от имени администратора**.
2. Поставьте Docker Desktop:

```powershell
winget install Docker.DockerDesktop
```

3. Включите WSL2, если ещё не включён:

```powershell
wsl --install
```

4. **Перезагрузите Windows**, если установщик WSL этого попросил. Без ребута движок контейнеров часто не поднимается.
5. Запустите **Docker Desktop** из меню Пуск и дождитесь зелёного статуса (Engine running). Первый запуск может занять несколько минут.
6. В Docker Desktop: Settings → General — должна быть включена **Use the WSL 2 based engine**.
7. Повторите `docker info` в обычном PowerShell.

Если `docker info` пишет `unable to start` / `cannot connect to the Docker engine` — откройте Docker Desktop и подождите, пока кит не станет зелёным. Команды ниже без работающего движка не сработают.

---

## Linux: установка Docker Engine

На сервере без Desktop достаточно Engine. Пример для Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker "$USER"
```

Выйдите из сессии и зайдите снова, чтобы группа `docker` применилась. Затем `docker info`.

---

## 1. Скачать код

```bash
git clone https://github.com/pssassa/moex_bot.git
cd moex_bot
git checkout version-2
```

Если репозиторий уже есть:

```bash
cd moex_bot
git pull
```

Рабочая папка — корень репозитория, где лежит `docker-compose.yml`.

---

## 2. Токен Hugging Face

ИИ-сценарий идёт через [Hugging Face Inference Providers](https://huggingface.co/docs/inference-providers). Нужен **бесплатный аккаунт** и **fine-grained** токен с правом **Make calls to Inference Providers**. Обычного Read-токена недостаточно: API вернёт 401.

1. Зарегистрируйтесь на https://huggingface.co
2. Создайте токен:  
   https://huggingface.co/settings/tokens/new?ownUserPermissions=inference.serverless.write&tokenType=fineGrained
3. Включите право **Make calls to Inference Providers** (`inference.serverless.write`).
4. Скопируйте значение токена (начинается с `hf_`). **Не коммитьте его в Git.**

Модель по умолчанию: `Qwen/Qwen3.8-27B`, провайдер `novita`. Веса локально не скачиваются.

Без токена интерфейс и котировки работают, кнопка «Построить сценарий» вернёт ошибку про `HF_TOKEN`.

---

## 3. Файл `.env`

В корне проекта:

**Windows (PowerShell):**

```powershell
copy .env.example .env
```

**Linux / macOS:**

```bash
cp .env.example .env
```

Откройте `.env` и заполните минимум так:

```env
HF_TOKEN=hf_ваш_токен
HF_MODEL=Qwen/Qwen3.8-27B
HF_PROVIDER=novita
```

Остальные поля можно не трогать. В Docker `DATABASE_URL` из `.env` всё равно переопределяется на внутренний хост `db`.

| Переменная | Смысл | По умолчанию |
|------------|--------|----------------|
| `HF_TOKEN` | Токен Hugging Face | пусто |
| `HF_MODEL` | Имя модели | `Qwen/Qwen3.8-27B` |
| `HF_PROVIDER` | Провайдер Inference | `novita` |
| `FORECAST_CACHE_HOURS` | Кэш сценария, часов | `6` |
| `FORECAST_HORIZON_DAYS` | Горизонт траектории | `5` |
| `CANDLE_HISTORY_DAYS` | Глубина свечей при первой загрузке | `500` |
| `NEWS_MAX_AGE_DAYS` | Новости в промпт, дней | `14` |

Файл `.env` в `.gitignore`. В Git уходит только `.env.example` без секрета.

---

## 4. Сборка и запуск

Из корня репозитория, при **запущенном** Docker:

```bash
docker compose up --build -d
```

- `--build` — собрать образы backend и frontend.
- `-d` — отправить контейнеры в фон.

Первая сборка качает базовые образы (Python, Node, nginx, Postgres) и может занять 5–15 минут. Повторные запуски быстрее.

Смотреть, что поднялось:

```bash
docker compose ps
```

Ожидаемое состояние: `db`, `backend`, `worker`, `frontend` в статусе running, у `backend` — healthy.

Логи первого синка справочника и новостей:

```bash
docker compose logs -f worker backend
```

Выход из логов: `Ctrl+C` (контейнеры продолжат работать).

Откройте http://localhost:8080

---

## 5. Что происходит при первом запуске

1. Postgres стартует, volume `postgres_data` создаётся автоматически.
2. Backend и worker выполняют `alembic upgrade head` (схема БД).
3. Worker тянет:
   - справочник: акции TQBR, биржевые фонды (ETF/БПИФ), металлы CETS;
   - макро: IMOEX, RTSI, RGBI, USD/RUB, CNY/RUB, ставка ЦБ (XML ЦБ иногда отвечает 404);
   - новости из RSS.
4. Свечи по бумаге грузятся **при открытии карточки**, не все сразу.

Пока worker не закончил справочник, таблица на главной может быть короткой. Подождите 1–2 минуты и обновите страницу.

Если страница открылась, а API отвечает 502 — фронт поднялся раньше бэкенда. Подождите healthy у backend или выполните:

```bash
docker compose restart frontend
```

---

## 6. Проверка, что всё живо

| Что | Адрес |
|-----|--------|
| Интерфейс | http://localhost:8080 |
| Health | http://localhost:8080/api/health |
| OpenAPI | http://localhost:8080/docs |

Health в норме выглядит так:

```json
{
  "status": "ok",
  "database": "ok",
  "hf_configured": true
}
```

`hf_configured: false` — в `.env` пустой `HF_TOKEN`, либо контейнеры подняли до сохранения файла. Исправьте `.env` и перезапустите backend:

```bash
docker compose up -d backend worker
```

Проверка сценария: откройте карточку (например SBER), нажмите **Построить сценарий**. Первый вызов Hugging Face может занять до минуты.

---

## Повседневные команды

Все из корня `moex_bot`.

```bash
# статус
docker compose ps

# логи
docker compose logs -f worker backend

# остановить, данные БД сохранить
docker compose stop

# запустить снова без пересборки
docker compose up -d

# пересобрать после изменения кода
docker compose up --build -d

# только фронт (после правок UI)
docker compose up --build -d frontend

# остановить и удалить контейнеры (volume с БД останется)
docker compose down
```

Обновление кода с GitHub:

```bash
git pull
docker compose up --build -d
```

---

## Типичные проблемы

**Docker не стартует на Windows**  
Нужны WSL2 и перезагрузка после `wsl --install`. Затем вручную открыть Docker Desktop и дождаться зелёного статуса.

**`error during connect` / `The system cannot find the file specified`**  
Движок Docker не запущен. Откройте Docker Desktop.

**Порт 8080 занят**  
Измените проброс в `docker-compose.yml`: `"8081:80"` вместо `"8080:80"`, затем `docker compose up -d frontend`.

**Пустая таблица бумаг**  
Смотрите `docker compose logs worker`. Синк идёт на старте worker. Повторить вручную:

```bash
docker compose restart worker
```

**502 Bad Gateway на сайте**  
Backend ещё не healthy. `docker compose ps`, затем `docker compose restart frontend`.

**Сценарий: «Hugging Face отклонил токен» / HTTP 401**  
Токен без права Inference Providers. Создайте fine-grained токен по ссылке в разделе 2, замените `HF_TOKEN` в `.env`, затем `docker compose up -d backend worker`.

**Сценарий: «Модель не вернула JSON»**  
Провайдер иногда отвечает текстом. Нажмите «Обновить сценарий» ещё раз. Модель и провайдер задаются `HF_MODEL` / `HF_PROVIDER`.

**График не грузится**  
ISS с контейнера иногда падает по SSL/DNS. В compose у backend и worker прописаны DNS `8.8.8.8` и `77.88.8.8`. Повторите открытие карточки; свечи кэшируются в Postgres.

**Ключевая ставка ЦБ пустая**  
XML ЦБ периодически отдаёт 404. На индексы и валюту это не влияет.

---

## Перенос на сервер

1. Скопируйте репозиторий и файл `.env` (токен не из git).
2. Поставьте Docker Engine + Compose, откройте порт **8080** (или смените проброс).
3. `docker compose up -d --build`
4. Сайт: `http://IP:8080`

Данные живут в volume `postgres_data`. `docker compose down` контейнеры удаляет, базу — нет.

Сброс базы (все котировки и прогнозы пропадут):

```bash
docker compose down -v
```

Перенос базы на другую машину:

```bash
docker compose exec db pg_dump -U moex moex > dump.sql
```

На новой машине после `docker compose up -d` дождитесь healthy и загрузите дамп в контейнер `db`.

---

## Источники (все бесплатные)

- Котировки и справочник: [MOEX ISS](https://iss.moex.com) — акции и фонды TQBR, металлы CETS (`GLDRUB_TOM` и др.)
- Макро: IMOEX, RTSI, RGBI, USD/RUB, CNY/RUB с ISS; ключевая ставка — XML ЦБ РФ
- Новости: RSS ТАСС, Интерфакс, РБК, Коммерсантъ, Ведомости, Лента, РИА; мир — BBC World; сайт MOEX
- ИИ: Hugging Face Inference Providers, модель в `HF_MODEL`

Платные API можно подменить позже в `backend/app/services/` — контракт сервисов от провайдера не зависит.

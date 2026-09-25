# Admin

## Dashboard

Показывать:

### Sources
- enabled;
- health;
- last successful request;
- success rate;
- requests/min;
- challenge rate.

### Queue
- pending;
- running;
- failed;
- oldest pending;
- jobs by source.

### Parser
- errors;
- unknown fields;
- parser version;
- sample raw payload.

### Data
- active listings;
- removed listings;
- snapshots;
- storage usage.

### Background jobs (не реализовано)

Нужен блок, где админ видит **все** фоновые задачи, а не только краулинг. Сейчас страница
"Задачи парсинга" показывает лишь `scrape_jobs` и `scheduled_scrapes` (`GET /api/v1/scrape/jobs`,
`/schedules`). Остальные периодические задачи — это arq-cron'ы, вшитые в `WorkerSettings.cron_jobs`
(`app/scraping/worker.py`), и в админке их не видно:

- `run_due_scheduled_scrapes`, `run_due_saved_search_scrapes` — порождают `ScrapeJob`, косвенно видны;
- `recompute_dirty_market_segments` — пересчёт рыночной цены (`06_SEARCH_MARKET.md`);
- `run_refresh_removal_stats` — витрина статистики снятых объявлений (`21_REMOVAL_STATS.md`),
  03:10/15:10 UTC и при старте воркера.

Для каждой задачи блок должен показывать: имя, расписание, время и итог последнего запуска
(успех/ошибка, длительность, сколько записей обработано), текст последней ошибки и время следующего
запуска. Без этого упавший пересчёт остаётся незамеченным, пока пользователи не увидят устаревшие
цифры на странице.

Варианты реализации (не выбраны): таблица журнала запусков (`background_job_runs`), в которую
каждый cron пишет старт/финиш через общую обёртку; либо чтение состояния из arq/Redis. Первое проще
и переживает рестарт Redis. Read-only на первом шаге — ручной запуск и включение/выключение
(см. Controls ниже) можно добавить позже. Переводить эти задачи на `ScheduledScrape`/`ScrapeJob`
не предполагается: они заточены под краулинг (`source_id`, лимит одной RUNNING-задачи на источник).

## Controls

Admin может:
- enable/disable source;
- change crawl limits;
- pause source;
- retry jobs;
- cancel jobs;
- trigger crawl;
- trigger listing refresh;
- reparse raw payload.

Любое ручное действие логируется в audit log.

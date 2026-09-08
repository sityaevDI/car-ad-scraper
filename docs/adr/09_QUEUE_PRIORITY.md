# Queue, priority и paid refresh

## 1. Почему нужна очередь

Scraping:
- медленный;
- ограничен источниками;
- может блокироваться;
- выполняется асинхронно.

HTTP request пользователя не должен ждать завершения crawl.

## 2. Job priority

Приоритет вычисляется из:

```text
priority =
    base_plan_weight
    + priority_credit_weight
    + freshness_urgency
    + job_type_weight
```

Но итоговый алгоритм должен защищать систему от starvation.

## 3. Fairness

Платный пользователь не должен иметь возможность бесконечно забить очередь.

Использовать:
- per-user concurrency limit;
- per-source concurrency limit;
- weighted fair scheduling;
- max jobs per minute;
- daily/monthly quota.

## 4. Priority credits

Лучше назвать это не "донат за следующие 250 объявлений", а:

**Priority Refresh Credits**

Один credit означает право повысить приоритет конкретного refresh job.

Credit не должен гарантировать обход CAPTCHA или мгновенное выполнение.

## 5. Supporter

Вариант:
- Supporter поддерживает проект;
- получает больший priority weight;
- получает больше saved searches;
- получает notifications;
- получает credits.

## 6. Free

Free:
- ограниченное число saved searches;
- ограниченная частота manual refresh;
- низкий priority;
- ограниченная history.

## 7. Pro

Pro:
- больше refresh;
- высокий priority;
- больше saved searches;
- extended analytics;
- больше history;
- priority credits.

## 8. Quota accounting

Каждый расход должен быть audit-able:

```text
user_id
operation
units
reason
created_at
```

Не изменять баланс без transaction.

## 9. Job deduplication

Если уже существует активный job для эквивалентного query/source:
- не создавать второй;
- присоединить пользователя к существующему job;
- учитывать entitlement пользователя отдельно.

Это критично для экономии scrape budget.

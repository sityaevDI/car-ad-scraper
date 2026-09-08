# Notifications

## Каналы MVP

- email;
- web/in-app notifications.

Будущее:
- Telegram;
- push;
- другие каналы.

## Events

### NEW_MATCH
Новое объявление соответствует saved search.

### PRICE_DROP
Цена listing снизилась.

### MARKET_CHANGE
Заметное изменение market price.

### LISTING_REMOVED
Отслеживаемое объявление исчезло.

## Notification rules

Не отправлять повторно одно и то же событие без cooldown.

Для price drop:
- сохранять previous price;
- current price;
- absolute change;
- percentage change.

## Digest

В будущем:
- daily digest;
- weekly market digest.

## Email

Email sending должен быть asynchronous через queue.

Ошибки SMTP/provider не должны ломать scrape jobs.

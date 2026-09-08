# Observability

## Metrics

### API
- request count;
- latency;
- error rate;
- status code.

### Queue
- queue length;
- waiting time;
- processing time;
- failed jobs;
- retries.

### Source
- requests;
- success;
- 403;
- 429;
- CAPTCHA/challenge;
- 5xx;
- parser errors;
- latency;
- listings discovered.

### Data
- listings total;
- active listings;
- snapshots/day;
- duplicate rate;
- parser field completeness.

## Logging

Structured JSON logs.

Fields:
- timestamp;
- service;
- environment;
- request_id;
- job_id;
- source;
- error_type.

Не логировать:
- passwords;
- proxy passwords;
- auth tokens;
- cookies.

## Tracing

OpenTelemetry-compatible tracing желательно добавить после базовых metrics/logging.

## Alerts

Минимум:
- source completely failing;
- 429/403 spike;
- parser error spike;
- queue stuck;
- DB unavailable;
- Redis unavailable;
- notification failures.

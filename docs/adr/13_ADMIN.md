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

# Alertmanager and Redis Research Notes

Prometheus Alertmanager is configured through a routing tree that determines alert grouping, notification timing, receivers, and inhibition. The configuration can be reloaded at runtime after validation. Primary source: https://prometheus.io/docs/alerting/latest/configuration/

PagerDuty’s Prometheus integration guide describes using Alertmanager routing/receiver configuration to send alerts to PagerDuty services. The PagerDuty Events API v2 ingests machine events using an integration/routing key attached to a PagerDuty service. Primary sources: https://www.pagerduty.com/docs/guides/prometheus-integration-guide/ and https://developer.pagerduty.com/docs/events-api-v2-overview

Redis cache-aside documentation recommends reading Redis first, loading the primary store only on a miss, and writing the result with a TTL. On canonical updates, write the primary source of truth then invalidate the cache key. The documentation notes TTL-bounded staleness and Redis/Lua primitives for atomic stampede mitigation. Primary source: https://redis.io/docs/latest/develop/use-cases/cache-aside/

The redis-py documentation provides an asyncio-compatible client under `redis.asyncio`, which is suitable for FastAPI lifespan connection reuse. Primary source: https://redis.io/docs/latest/develop/clients/redis-py/async/

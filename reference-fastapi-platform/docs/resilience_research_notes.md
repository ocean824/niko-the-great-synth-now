# Resilience Research Notes

Kubernetes HorizontalPodAutoscaler continuously adjusts a scalable workload’s desired replica count using resource, custom, or external metrics. Custom metrics need a metrics API adapter, while external metrics require an external metrics API provider. Scaling behavior supports explicit policies and stabilization windows, which are needed to limit surge-related flapping. Primary source: https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/

PostgreSQL continuous archiving combines a base backup with archived WAL segments. A complete archived WAL sequence from before the base backup enables point-in-time recovery, and continuously feeding the WAL stream to a machine loaded from the same base backup supports a warm standby. Primary source: https://www.postgresql.org/docs/current/continuous-archiving.html

PostgreSQL’s official documentation states that `pg_dump` and `pg_dumpall` are logical backups and cannot be used as part of a continuous-archiving / WAL-replay recovery solution. They remain useful as independent logical restore validation and portability artifacts. Primary source: https://www.postgresql.org/docs/current/continuous-archiving.html

Redis cache-aside is non-authoritative in Synth Now: canonical data and audit evidence remain in PostgreSQL. Redis loss should force misses and token/session re-projection, not loss of claims, vectors, or source records. Primary source: https://redis.io/docs/latest/develop/use-cases/cache-aside/

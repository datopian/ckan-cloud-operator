# Monitoring

## Alerts

Following alerts should be defined:

* Prometheus alertmanager - 
  * General kubernetes alerts
  * Can be configured to send to slack, see [Prometheus docs](https://prometheus.io/docs/alerting/alertmanager/)
  * Alertmanager web-UI can be used to silence and comment on alerts
* Periodical task that checks instance readyness
  * Use Jenkins to periodically (e.g. every 5 minutes) check readyness of each instances based on `ready` attributes in `ckan-cloud-operator deis-instance list --full`

## Prometheus + Grafana

### Deploy Prometheus

[Google click to deploy Prometheus & Grafana](https://console.cloud.google.com/marketplace/details/google/prometheus?q=prometheus)

### Expose services

Use ckan-cloud-operator routes to expose the service, for example:

```
ckan-cloud-operator routers create-backend-url-subdomain-route --wait-ready ROUTER_NAME grafana http://prometheus-grafana.prometheus
```

The following routes are required:

* grafana.example.com --> http://prometheus-grafana.prometheus
* prometheus.example.com --> http://prometheus-prometheus.prometheus:9090
* prometheus-alertmanager.example.com --> http://prometheus-alertmanager.prometheus:9093

Grafan can be exposed directly as it handles user authentication. Alertmanager and prometheus needs to be password protected (see ckan-cloud-operator routers create httpauth-secret flag)

Get the Grafana admin credentials

```
ckan-cloud-operator config get --secret-name prometheus-grafana --namespace prometheus
```

### Configure targets

Exporters expose an HTTP url which Prometheus scrapes

To Add a target:

* Edit configmap `prometheus-prometheus-config` under `prometheus` namespace
  * Edit `prometheus.yaml`
  * Add a value under `scrape_configs`, for example:

```
- job_name: 'postgres'
  static_configs:
  - targets: ['postgresql-prometheus-exporter.ckan-cloud:9187']
```

Restart Prometheus:

```
ckan-cloud-operator kubectl -- -n prometheus exec prometheus-prometheus-0 -- bash -c '"kill -HUP 1"' &&\
ckan-cloud-operator kubectl -- -n prometheus exec prometheus-prometheus-1 -- bash -c '"kill -HUP 1"' && echo Great Success!
```

Start a port forward to Prometheus and verify target is configured and up: http://localhost:9090/targets

### Configure alerts

* Edit configmap `prometheus-alertmanager-config` under `prometheus` namespace
  * Edit alertmanager.yml`
* Restart alertmanager:
  * Edit `prometheus-alertmanager` statefulset under `prometheus` namespace
  * Delete the pods ot recreate

## PostgreSQL monitoring

### Deploy postgresql prometheus exporter

Create a secret `postgresql-prometheus-exporter` in `ckan-cloud` namesapce:
* `DATA_SOURCE_NAME`: `postgresql://USER:PASSWORD@HOST:PORT/DB`

Deploy a workload `postgresql-prometheus-exporter` in `ckan-cloud` namespace:
* `image`: `wrouesnel/postgres_exporter`
* environment variables from secret `postgresql-prometheus-exporter`

Add a Prometheus target:

```
- job_name: 'postgres'
  static_configs:
  - targets: ['postgresql-prometheus-exporter.ckan-cloud:9187']
```

Copy grafana dashboards from other environment

### Deploy PgBouncer prometheus exporter

Deploy a workload `pgbouncer-prometheus-exporter` in `ckan-cloud` namespace:
* `image`: `spreaker/prometheus-pgbouncer-exporter`
* set environment variables:
  * `PGBOUNCER_PORT`: 5432
  * `PGBOUNCER_HOST`: `ckan-cloud-provider-db-proxy-pgbouncer.ckan-cloud`
  * `PGBOUNCER_EXPORTER_PORT`: 9127
  * `PGBOUNCER_EXPORTER_HOST`: 0.0.0.0
  * `PGBOUNCER_PASS` / `PGBOUNCER_USER`: set from secret `ckan-cloud-provider-db-gcloudsql-credentials`

Add a Prometheus target:

```
- job_name: 'pgbouncer'
  static_configs:
  - targets: ['pgbouncer-prometheus-exporter.ckan-cloud:9127']
```

Copy grafana dashboards from other environment

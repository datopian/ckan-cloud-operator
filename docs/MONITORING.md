# Monitoring

## Prometheus + Grafana

### Deploy Prometheus

[Google click to deploy Prometheus & Grafana](https://console.cloud.google.com/marketplace/details/google/prometheus?q=prometheus)

### Expose grafana

```
ckan-cloud-operator routers create-backend-url-subdomain-route --wait-ready ROUTER_NAME grafana http://prometheus-grafana.prometheus
```

Get the Grafana admin credentials

```
ckan-cloud-operator config get --secret-name prometheus-grafana --namespace prometheus
```

### Access Prometheus web-ui

```
KUBECONFIG=/path/to/cluster/kubeconfig kubectl -n prometheus port-forward prometheus-prometheus-0 9090
```

Access Prometheus at http://localhost:9090

### Access Alertmanager web-ui

```
KUBECONFIG=/path/to/cluster/kubeconfig kubectl -n prometheus port-forward prometheus-alertmanager-0 9093
```

Access alertmanager at http://localhost:9093

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
ckan-cloud-operator kubectl -- -n prometheus exec prometheus-prometheus-0 -- kill -HUP 1
```

  * Edit `prometheus-prometheus` statefulset under `prometheus` namespace
  * Delete the pods to recreate

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

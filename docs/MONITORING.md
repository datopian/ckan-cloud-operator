# Monitoring

## Deploy Prometheus

[Google click to deploy Prometheus & Grafana](https://console.cloud.google.com/marketplace/details/google/prometheus?q=prometheus)

## Access Prometheus web-ui

```
KUBECONFIG=/path/to/cluster/kubeconfig kubectl -n prometheus port-forward prometheus-prometheus-0 9090
```

Access Prometheus at http://localhost:9090

## Access Alertmanager web-ui

```
KUBECONFIG=/path/to/cluster/kubeconfig kubectl -n prometheus port-forward prometheus-alertmanager-0 9093
```

Access alertmanager at http://localhost:9093

## Configure targets

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

* Restart Prometheus:
  * Edit `prometheus-prometheus` statefulset under `prometheus` namespace
  * Delete the pods to recreate

## Configure alerts

* Edit configmap `prometheus-alertmanager-config` under `prometheus` namespace
  * Edit alertmanager.yml`
* Restart alertmanager:
  * Edit `prometheus-alertmanager` statefulset under `prometheus` namespace
  * Delete the pods ot recreate

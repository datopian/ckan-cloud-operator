# Logging

## Google Kubernetes Engine - Stackdriver

Get Stackdriver URLs to various cluster logs for the active ckan-cloud-operator environment:

```
echo &&\
echo cluster: &&\
ckan-cloud-operator config get --configmap-name ckan-cloud-provider-cluster-gcloud --template \
    'https://console.cloud.google.com/logs/viewer?project={project-id}&&resource=k8s_cluster%2Flocation%2F{cluster-compute-zone}%2Fcluster_name%2F{cluster-name}' &&\
echo &&\
echo nodes: &&\
ckan-cloud-operator config get --configmap-name ckan-cloud-provider-cluster-gcloud --template \
    'https://console.cloud.google.com/logs/viewer?project={project-id}&&resource=k8s_node%2Flocation%2F{cluster-compute-zone}%2Fcluster_name%2F{cluster-name}' &&\
echo &&\
echo pods: &&\
ckan-cloud-operator config get --configmap-name ckan-cloud-provider-cluster-gcloud --template \
    'https://console.cloud.google.com/logs/viewer?project={project-id}&&resource=k8s_pod%2Flocation%2F{cluster-compute-zone}%2Fcluster_name%2F{cluster-name}' &&\
echo &&\
echo containers: &&\
ckan-cloud-operator config get --configmap-name ckan-cloud-provider-cluster-gcloud --template \
    'https://console.cloud.google.com/logs/viewer?project={project-id}&&resource=k8s_container%2Flocation%2F{cluster-compute-zone}%2Fcluster_name%2F{cluster-name}' &&\
echo
```

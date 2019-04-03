# ckan-cloud-operator UI using Jenkins


## Prerequisites

* Jenkins server
* ckan-cloud-operator kubeconfig file


## Deploy Jenkins JNLP

Deploy a JNLP deployment on the Kubernetes cluster:

* image: use the image from Dockerfile.jenkins-jnlp
* env:
  * CKAN_CLOUD_USER_NAME: name of a ckan-cloud-operator user which the jenkins server will assume
  * HOME: /home/jenkins/agent
* envFrom:
  * secret containing:
    * JENKINS_AGENT_NAME: agent name, configured when adding a jnlp node
    * JENKINS_SECRET: agent secret token, can get it after adding a jnlp node
    * JENKINS_URL: public web endpoint for your jenkins server
* volumes:
  * /etc/ckan-cloud/.kubeconfig: mount from a secret


## Using Jenkins

Label the jnlp node accordingly and target jobs on it

The jobs can execute shell using either Bash or Python3

Example Bash job:

```
ckan-cloud-operator routers list
```

Example Python3 job:

```
#!/usr/bin/env python3
from ckan_cloud_operator import kubectl
print(kubectl.get('ckancloudckancinstance'))
```

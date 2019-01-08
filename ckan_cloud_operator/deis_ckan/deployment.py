import subprocess
import yaml
import datetime
import time
from ckan_cloud_operator import kubectl


class DeisCkanInstanceDeployment(object):

    def __init__(self, instance):
        self.instance = instance

    def update(self):
        if not self.instance.annotations.update_status('deployment', 'created', lambda: self._deploy()):
            self._deploy()

    def delete(self):
        print(f'Deleting instance {self.instance.id}')
        subprocess.check_call(f'kubectl -n {self.instance.id} delete deployment/{self.instance.id} --force --now', shell=True)

    def get(self):
        exitcode, output = subprocess.getstatusoutput(f'kubectl -n {self.instance.id} get deployment/{self.instance.id} -o yaml')
        if exitcode == 0:
            deployment = yaml.load(output)
            status = kubectl.get_item_detailed_status(deployment)
            ready = len(status.get('error', [])) == 0
            status['pods'] = []
            pods = kubectl.get('pods -l app=ckan', namespace=self.instance.id, required=False)
            image = None
            if pods:
                for pod in pods['items']:
                    pod_status = kubectl.get_item_detailed_status(pod)
                    status_code, output = subprocess.getstatusoutput(
                        f'kubectl -n {self.instance.id} logs {pod["metadata"]["name"]} -c ckan --tail 5',
                    )
                    if status_code == 0:
                        pod_status['logs'] = output
                    else:
                        ready = False
                        pod_status['logs'] = ''
                    if not image:
                        image = pod["spec"]["containers"][0]["image"]
                    else:
                        if image != pod["spec"]["containers"][0]["image"]:
                            ready = False
                            image = pod["spec"]["containers"][0]["image"]
                    status['pods'].append(pod_status)
            return dict(status, ready=ready, image=image)
        else:
            return {'ready': False, 'error': output}

    def _deploy(self):
        print(f'Deploying instance {self.instance.id}')
        ckanContainerSpec = dict(self.instance.spec.spec['ckanContainerSpec'],
                                 name='ckan',
                                 envFrom=[{'secretRef': {'name': 'ckan-envvars'}}])
        if 'imageFromGitlab' in ckanContainerSpec:
            ckanContainerSpec['image'] = 'registry.gitlab.com/{}:latest'.format(ckanContainerSpec.pop('imageFromGitlab'))
        ckanPodSpec = dict(self.instance.spec.spec['ckanPodSpec'],
                           serviceAccountName=f'ckan-{self.instance.id}-operator',
                           containers=[ckanContainerSpec],
                           imagePullSecrets=[{'name': f'{self.instance.id}-registry'}])
        deployment = {'apiVersion': 'apps/v1beta1',
                      'kind': 'Deployment',
                      'metadata': {
                          'name': self.instance.id,
                          'namespace': self.instance.id
                      },
                      'spec': {
                          'replicas': 1,
                          'revisionHistoryLimit': 5,
                          'template': {
                              'metadata': {
                                  'labels': {
                                      'app': 'ckan'
                                  },
                                  'annotations': {
                                      'ckan-cloud/operator-timestamp': str(datetime.datetime.now())
                                  }
                              },
                              'spec': ckanPodSpec
                          }
                      }}
        subprocess.run('kubectl apply -f -', input=yaml.dump(deployment).encode(), shell=True, check=True)

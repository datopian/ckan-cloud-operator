import subprocess
import yaml
from ckan_cloud_operator import kubectl


class DeisCkanInstanceNamespace(object):

    def __init__(self, instance):
        self.instance = instance

    def update(self):
        self.instance.annotations.update_status('namespace', 'created',
                                                lambda: self._initialize_instance_namespace())

    def delete(self):
        ns = self.instance.id
        print(f'Deleting instance namespace: {ns}')
        subprocess.check_call(
            f'kubectl delete -n {ns} rolebinding/ckan-{ns}-operator-rolebinding '
            f'                       role/ckan-{ns}-operator-role '
            f'                       serviceaccount/ckan-{ns}-operator',
            shell=True
        )
        subprocess.check_call(f'kubectl delete ns {ns}', shell=True)

    def get(self):
        exitcode, output = subprocess.getstatusoutput(f'kubectl -n {self.instance.id} get ns/{self.instance.id} -o yaml')
        events = [
            '{firstTimestamp} - {lastTimestamp} ({type}*{count}) {message}'.format(**e)
            for e in kubectl.get('events', namespace=self.instance.id)['items']
            if e['type'] != 'Normal'
        ]
        if exitcode == 0:
            return {'ready': yaml.load(output).get('status', {}).get('phase') == 'Active', 'events': events}
        else:
            return {'ready': False, 'error': output, 'events': events}

    def _initialize_instance_namespace(self):
        ns = self.instance.id
        print(f'initializing instance namespace: {ns}')
        subprocess.check_call(f'kubectl create ns {ns}', shell=True)
        kubectl_namespace = f'kubectl --namespace {ns}'
        subprocess.check_call(f'{kubectl_namespace} create serviceaccount ckan-{ns}-operator',
                              shell=True)
        subprocess.check_call(f'{kubectl_namespace} create role ckan-{ns}-operator-role '
                              f' --verb list,get,create --resource secrets,pods,pods/exec,pods/portforward',
                              shell=True)
        subprocess.check_call(f'{kubectl_namespace} create rolebinding ckan-{ns}-operator-rolebinding'
                              f' --role ckan-{ns}-operator-role'
                              f' --serviceaccount {ns}:ckan-{ns}-operator',
                              shell=True)

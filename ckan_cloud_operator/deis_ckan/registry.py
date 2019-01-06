import subprocess
import yaml
from ckan_cloud_operator import kubectl


class DeisCkanInstanceRegistry(object):

    def __init__(self, instance):
        self.instance = instance

    def update(self):
        self.instance.annotations.update_status('registry', 'created', lambda: self._create_instance_registry_secret())

    def delete(self):
        print('Deleting instance registry secret')
        subprocess.check_call(f'kubectl -n {self.instance.id} delete secret/{self.instance.id}-registry', shell=True)

    def get(self):
        exitcode, output = subprocess.getstatusoutput(f'kubectl -n {self.instance.id} get secret/{self.instance.id}-registry -o yaml')
        if exitcode == 0:
            return {'ready': len(kubectl.decode_secret(yaml.load(output))) > 0}
        else:
            return {'ready': False, 'error': output}

    def _create_instance_registry_secret(self):
        print('Creating instance registry secret')
        docker_server = self.instance.ckan_infra.DOCKER_REGISTRY_SERVER
        docker_username = self.instance.ckan_infra.DOCKER_REGISTRY_USERNAME
        docker_password = self.instance.ckan_infra.DOCKER_REGISTRY_PASSWORD
        docker_email = self.instance.ckan_infra.DOCKER_REGISTRY_EMAIL
        subprocess.check_call(f'kubectl -n {self.instance.id} create secret docker-registry {self.instance.id}-registry '
                              f'--docker-password={docker_password} '
                              f'--docker-server={docker_server} '
                              f'--docker-username={docker_username} '
                              f'--docker-email={docker_email}', shell=True)

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
        from ckan_cloud_operator.providers.ckan import manager as ckan_manager
        server, user, password, email = ckan_manager.get_docker_credentials()
        subprocess.call(f'kubectl -n {self.instance.id} create secret docker-registry {self.instance.id}-registry '
                              f'--docker-password={password} '
                              f'--docker-server={server} '
                              f'--docker-username={user} '
                              f'--docker-email={email}', shell=True)

import subprocess
from ckan_cloud_operator import kubectl


class DeisCkanInstanceCKAN(object):
    """Manage the CKAN app"""

    def __init__(self, instance):
        self.instance = instance

    def update(self):
        self.instance.annotations.update_status('ckan', 'created', lambda: self._create())

    def run(self, command, *args):
        assert command in ['paster', 'exec', 'logs', 'port-forward']
        command = command.replace('-', '_')
        getattr(self, command)(*args)

    def paster(self, paster_command=None, *paster_args):
        """Run ckan-paster commands on the first CKAN pod using relevant CKAN configuration file"""
        cmd = f'-it -- paster --plugin=ckan'
        if paster_command:
            cmd += f' {paster_command} -c /srv/app/production.ini ' + " ".join(paster_args)
        self.exec(cmd)

    def admin_credentials(self):
        data = kubectl.decode_secret(kubectl.get('secret', 'ckan-env-vars', namespace=self.instance.id))
        return {
            'sysadmin-name': data['CKAN_SYSADMIN_NAME'],
            'sysadmin-password': data['CKAN_SYSADMIN_PASSWORD'],
        }

    def _get_ckan_pod_name(self):
        deployment_data = self.instance.get('deployment')
        latest_pod_name = deployment_data['latest_pod_name']
        if latest_pod_name:
            latest_pods = [pod for pod in deployment_data.get('pods', []) if pod['name'] == latest_pod_name]
            if len(latest_pods) == 1 and len(latest_pods[0].get('errors', [])) == 0:
                return latest_pod_name
        return None

    def exec(self, *args, check_output=False):
        """Execute shell scripts on the first CKAN pod"""
        pod_name = self._get_ckan_pod_name()
        assert pod_name
        return self.instance.kubectl(f'exec {pod_name} ' + " ".join(args), check_output=check_output)

    def logs(self, *args):
        """Run kubectl logs on the first CKAN pod"""
        pod_name = self._get_ckan_pod_name()
        assert pod_name
        self.instance.kubectl(f'logs {pod_name} ' + " ".join(args))

    def port_forward(self, *args):
        """Start port forwarding to the CKAN deployment, using the CKAN varnish port 5000 by default"""
        if len(args) == 0:
            args = ['5000']
        pod_name = self._get_ckan_pod_name()
        self.instance.kubectl(f'port-forward {pod_name} ' + " ".join(args))
        subprocess.check_call(['kubectl', '-n', self.instance.id, 'port-forward', f'deployment/{self.instance.id}', *args])

    def _create(self):
        ckan_init = self.instance.spec.spec.get('ckan', {}).get('init')
        if ckan_init:
            for cmd in ckan_init:
                print('Running ckan init script')
                if cmd[0] == 'paster':
                    print(' '.join(cmd))
                    self.paster(*cmd[1:])
                else:
                    raise ValueError(f'Invalid ckan init cmd: {cmd}')

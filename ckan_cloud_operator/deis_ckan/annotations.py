import traceback
import subprocess
import base64
import yaml
import json
from ckan_cloud_operator import kubectl


FLAGS = [
    'forceCreateAnnotations',  # Set created annotations even if a component failed to create
    'skipDbPermissions', # Skip setting DB permissions on update
    'skipDatastorePermissions', # Skip setting Datastore permissions on update
]


STATUSES = {
    'db': ['created'],
    'datastore': ['created'],
    'deployment': ['created'],
    'envvars': ['created'],
    'instance': ['created'],
    'namespace': ['created'],
    'registry': ['created'],
    'solr': ['created'],
    'storage': ['created'],
    'ckan': ['created'],
}


# flexible annotations encoded to json and permitted using key prefixes
JSON_ANNOTATION_PREFIXES = [
    'router-traefik'
]


SECRET_ANNOTATIONS = [
    'databasePassword',
    'datastorePassword',
    'datastoreReadonlyUser',
    'datatastoreReadonlyPassword',
]


__NONE__ = object()


class DeisCkanInstanceAnnotations(object):
    """Manage annotations related to the instance which are used to store instance metadata"""

    def __init__(self, instance, override_flags=None, persist_overrides=False):
        self.instance = instance
        self._override_flags = override_flags
        if self._override_flags:
            for flag in self._override_flags:
                assert flag in FLAGS, f'invalid flag: {flag}'
            if persist_overrides and len(self._override_flags) > 0:
                self._annotate(*['{}={}'.format(k, 'true' if v else 'false')
                                 for k, v in self._override_flags.items()], overwrite=True)

    def set_status(self, key, status):
        assert status in STATUSES[key], f'invalid status: {key}={status}'
        self._annotate(f'{key}-{status}=true')

    def get_status(self, key, status):
        assert key in STATUSES.keys(), f'invalid status key: {key}'
        return bool(self._get_annotation(f'{key}-{status}'))

    def update_status(self, key, status, update_func, force_update=False):
        if self.get_status(key, status):
            if force_update:
                update_func()
                return True
            else:
                return False
        else:
            try:
                update_func()
            except:
                if self.get_flag('forceCreateAnnotations'):
                    traceback.print_exc()
                else:
                    raise
            self.set_status(key, status)
            return True

    def set_flag(self, flag):
        self._annotate(f'{flag}=true')

    def set_flags(self, *flags):
        self._annotate(*[f'{flag}=true' for flag in flags])

    def get_flag(self, flag):
        """flags  are boolean fields which can be added manually to modify operator functionality

        Flags can be set kubectl annotate on the DeisCkanInstance object, for example:

        kubectl -n ckan-cloud annotate DeisCkanInstance/atea32 ckan-cloud/forceCreateAnnotations=true
        """
        assert flag in FLAGS, f'invalid flag: {flag}'
        if self._override_flags and flag in self._override_flags:
            return self._override_flags[flag]
        else:
            value = self._get_annotation(flag)
            if type(value) == str:
                return False if value.lower().strip() in ['false', '0', 'no', ''] else bool(value)
            else:
                return bool(value)

    def get(self):
        data = {k.replace('ckan-cloud/', ''): v for k, v in self.instance.values['metadata'].get('annotations', {}).items()
                if k.startswith('ckan-cloud/')}
        data['ready'] = True
        return data

    def set_secrets(self, key_values):
        for key in key_values:
            assert key in SECRET_ANNOTATIONS, f'invalid secret key: {key}'
        secret = getattr(self, '_secret', None)
        cur_data = secret.get('data', {}) if secret and secret != __NONE__ else {}
        secret = kubectl.get(f'secret {self.instance.id}-annotations', namespace=self.instance.id, required=False)
        if not secret:
            secret = {'data': {}}
        secret['data'].update(**cur_data)
        for key, value in key_values.items():
            secret['data'][key] = base64.b64encode(value.encode()).decode()
        secret = {
            'apiVersion': 'v1',
            'kind': 'Secret',
            'metadata': {
                'name': f'{self.instance.id}-annotations',
                'namespace': self.instance.id
            },
            'type': 'Opaque',
            'data': secret['data']
        }
        subprocess.run(f'kubectl -n {self.instance.id} apply -f -',
                       input=yaml.dump(secret).encode(), shell=True, check=True)
        self._secret = secret

    def set_secret(self, key, value):
        self.set_secrets({key: value})

    def get_secret(self, key, default=None):
        assert key in SECRET_ANNOTATIONS, f'invalid secret key: {key}'
        secret = getattr(self, '_secret', None)
        if not secret:
            secret = kubectl.get(f'secret {self.instance.id}-annotations',
                                 namespace=self.instance.id, required=False)
            if not secret:
                secret = __NONE__
            self._secret = secret
        if secret and secret != __NONE__:
            value = secret.get('data', {}).get(key, None)
            return base64.b64decode(value).decode() if value else default
        else:
            return default

    def json_annotate(self, key, value, overwrite=True):
        ans = []
        assert any([key.startswith(prefix) for prefix in JSON_ANNOTATION_PREFIXES]), f'invalid json annotation key: {key}'
        value = json.dumps(value)
        ans.append(f"{key}='{value}'")
        self._annotate(*ans, overwrite=overwrite)

    def _annotate(self, *annotations, overwrite=True):
        cmd = f'kubectl -n ckan-cloud annotate {self.instance.kind} {self.instance.id}'
        for annotation in annotations:
            cmd += f' ckan-cloud/{annotation}'
        if overwrite:
            cmd += ' --overwrite'
        subprocess.check_call(cmd, shell=True)

    def _get_annotation(self, annotation, default=None):
        return self.instance.values['metadata'].get('annotations', {}).get(f'ckan-cloud/{annotation}', default)

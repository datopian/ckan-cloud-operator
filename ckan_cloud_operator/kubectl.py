import yaml
import base64
import traceback
import datetime
import json
import logging
import subprocess
from ckan_cloud_operator import yaml_config
from ckan_cloud_operator import logs


def check_call(cmd, namespace='ckan-cloud', use_first_pod=False):
    cmd = _parse_call_cmd(cmd, namespace, use_first_pod)
    logs.subprocess_check_call(f'kubectl -n {namespace} {cmd}', shell=True)


def get_deployment_pod_name(deployment_name, namespace='ckan-cloud', use_first_pod=False, required_phase=None):
    deployment = get(f'deployment {deployment_name}', namespace=namespace, required=True)
    match_labels = deployment['spec']['selector']['matchLabels']
    pods = get_items_by_labels('pod', match_labels, required=True, namespace=namespace)
    if use_first_pod:
        assert len(pods) > 0
    else:
        assert len(pods) == 1
    if required_phase:
        assert pods[0]['status']['phase'].lower() == required_phase.lower()
    return pods[0]['metadata']['name']


def check_output(cmd, namespace='ckan-cloud'):
    return logs.subprocess_check_output(f'kubectl -n {namespace} {cmd}', shell=True)


def call(cmd, namespace='ckan-cloud'):
    return subprocess.call(f'kubectl -n {namespace} {cmd}', shell=True)


def getstatusoutput(cmd, namespace='ckan-cloud', use_first_pod=False):
    cmd = _parse_call_cmd(cmd, namespace, use_first_pod)
    return subprocess.getstatusoutput(f'kubectl -n {namespace} {cmd}')


def get(what, *args, required=True, namespace='ckan-cloud', get_cmd='get', **kwargs):
    extra_args = ' '.join(args)
    extra_kwargs = ' '.join([f'{k} {v}' for k, v in kwargs.items()])
    try:
        return yaml.load(
            logs.subprocess_check_output(
                f'kubectl -n {namespace} {get_cmd} {what} {extra_args} -o yaml {extra_kwargs}', shell=True,
            )
        )
    except subprocess.CalledProcessError:
        if required:
            raise
        else:
            return None


def edit(what, *edit_args, namespace='ckan-cloud', **edit_kwargs):
    extra_edit_args = ' '.join(edit_args)
    extra_edit_kwargs = ' '.join([f'{k} {v}' for k, v in edit_kwargs.items()])
    res = get(what, namespace=namespace, required=True)
    items = res.get('items', [res])
    assert len(items) > 0, f'no items found to edit for: {what}'
    for item in items:
        name = item['metadata']['name']
        kind = item['kind']
        subprocess.check_call(f'kubectl -n {namespace} edit {kind}/{name} {extra_edit_args} {extra_edit_kwargs}', shell=True)


def get_items_by_labels(resource_kind, labels, required=True, namespace='ckan-cloud'):
    if labels:
        label_selector = ','.join([f'{k}={v}' for k,v in labels.items()])
        label_args = f'-l {label_selector}'
    else:
        label_args = ''
    res = get(f'{resource_kind} {label_args}', required=required, namespace=namespace)
    return res['items'] if res else None


def edit_items_by_labels(resource_kind, labels, namespace='ckan-cloud'):
    label_selector = ','.join([f'{k}={v}' for k,v in labels.items()])
    edit(f'{resource_kind} -l {label_selector}', namespace=namespace)


def delete_items_by_labels(resource_kinds, labels, namespace='ckan-cloud'):
    label_selector = ','.join([f'{k}={v}' for k,v in labels.items()])
    resource_kinds = ','.join(resource_kinds)
    check_call(f'delete --ignore-not-found  -l {label_selector} {resource_kinds}', namespace=namespace)


def decode_secret(secret, attr=None, required=False):
    if not secret:
        if required:
            raise Exception()
        else:
            return {}
    elif attr:
        if required:
            return base64.b64decode(secret['data'][attr]).decode()
        else:
            value = secret.get('data', {}).get(attr)
            if value:
                return base64.b64decode(value)
            else:
                return None
    else:
        return {
            k: base64.b64decode(v).decode() if v else None
            for k, v
            in secret.get('data', {}).items()
        }


def update_secret(name, values, namespace='ckan-cloud', labels=None, dry_run=False):
    for k, v in values.items():
        v_type = type(v)
        assert v_type == str, f'Invalid type ({v_type}) for {k}: {v}'
    if not labels:
        labels = {}
    secret = get(f'secret {name}', required=False, namespace=namespace)
    labels = dict(secret.get('metadata', {}).get('labels', {}), **labels) if secret else labels
    data = decode_secret(secret, required=False)
    data.update(**values)
    apply({
        'apiVersion': 'v1',
        'kind': 'Secret',
        'metadata': {
            'name': name,
            'namespace': namespace,
            'labels': labels,
        },
        'type': 'Opaque',
        'data': {k: base64.b64encode(v.encode()).decode() for k, v in data.items() if v}
    }, dry_run=dry_run)
    return data


def update_configmap(name, values, namespace='ckan-cloud', labels=None, dry_run=False):
    for k, v in values.items():
        v_type = type(v)
        assert v_type == str, f'Invalid type ({v_type}) for {k}: {v}'
    configmap = get(f'configmap {name}', required=False, namespace=namespace)
    data = configmap['data'] if configmap else {}
    data.update(**values)
    apply(get_configmap(name, labels, data, namespace=namespace), dry_run=dry_run)
    return data


def get_item_detailed_status(item):
    kind = item['kind']
    name = item['metadata']['name']
    item_status = {"name": name, "created_at": item["metadata"]["creationTimestamp"], "true_status_last_transitions": {}}
    if kind in ["Deployment", "ReplicaSet"]:
        item_status["generation"] = item["metadata"]["generation"]
    for condition in item["status"].get("conditions", []):
        assert condition["type"] not in item_status["true_status_last_transitions"]
        if condition["status"] == "True":
            item_status["true_status_last_transitions"][condition["type"]] = condition["lastTransitionTime"]
        else:
            item_status.setdefault("errors", []).append({
                "kind": "failed_condition",
                "status": condition["status"],
                "reason": condition["reason"],
                "message": condition["message"],
                "last_transition": condition["lastTransitionTime"]
            })
    return item_status


def get_deployment_detailed_status(deployment, pod_label_selector, main_container_name, namespace='ckan-cloud'):
    status = get_item_detailed_status(deployment)
    ready = len(status.get('error', [])) == 0
    status['pods'] = []
    pods = get(f'pods -l {pod_label_selector}', namespace=namespace, required=False)
    if pods:
        for pod in pods['items']:
            pod_status = get_item_detailed_status(pod)
            pod_status['other-containers'] = []
            for container in pod['spec']['containers']:
                container_name = container['name']
                container_status = {'name': container_name}
                status_code, output = subprocess.getstatusoutput(
                    f'kubectl -n {namespace} logs {pod["metadata"]["name"]} -c {main_container_name} --tail 5',
                )
                if status_code == 0:
                    container_status['logs'] = output
                else:
                    if container_name == main_container_name: ready = False
                    container_status['logs'] = ''
                container_status['image'] = container['image']
                if container_name == main_container_name:
                    pod_status['main-container'] = container_status
                else:
                    pod_status['other-containers'].append(container_status)
            status['pods'].append(pod_status)
    return dict(status, ready=ready, namespace=deployment['metadata']['namespace'])


def create(resource, is_yaml=False):
    if is_yaml: resource = yaml.load(resource)
    try:
        logs.subprocess_run('kubectl create -f -', input=yaml.dump(resource).encode())
    except:
        logging.exception('Failed to create resource\n%s', yaml.dump(resource, default_flow_style=False))
        raise



def apply(resource, is_yaml=False, reconcile=False, dry_run=False):
    if is_yaml: resource = yaml.load(resource)
    cmd = 'auth reconcile' if reconcile else 'apply'
    args = []
    if dry_run:
        args.append('--dry-run')
    args = " ".join(args)
    try:
        logs.subprocess_run(
            f'kubectl {cmd} {args} -f -',
            input=yaml.dump(resource).encode()
        )
    except:
        logging.exception('Failed to apply resource\n%s', yaml.dump(resource, default_flow_style=False))
        raise
    if dry_run:
        print(yaml.dump(resource, default_flow_style=False))


def install_crd(plural, singular, kind):
    crd = get(f'crd {plural}.stable.viderum.com', required=False)
    version = 'v1'
    if crd:
        assert crd['spec']['versions'][0]['name'] == version
        print(f'{kind} custom resource definitions are up-to-date')
    else:
        print(f'Creating {kind} {version} custom resource definition')
        crd = {'apiVersion': 'apiextensions.k8s.io/v1beta1',
               'kind': 'CustomResourceDefinition',
               'metadata': {
                   'name': f'{plural}.stable.viderum.com'
               },
               'spec': {
                   'versions': [{
                       'name': version,
                       'served': True,
                       'storage': True
                   }],
                   'group': 'stable.viderum.com',
                   'scope': 'Namespaced',
                   'names': {
                       'plural': plural,
                       'singular': singular,
                       'kind': kind
                   }
               }}
        logs.subprocess_run('kubectl create -f -', input=yaml.dump(crd).encode())


def get_resource(api_version, kind, name, labels, namespace='ckan-cloud', **kwargs):
    resource = {
        'apiVersion': api_version,
        'kind': kind,
        'metadata': {
            'name': name,
            'namespace': namespace,
            'labels': labels,
            'annotations': {},
        },
    }
    resource.update(**kwargs)
    add_operator_timestamp_annotation(resource['metadata'])
    return resource


def get_configmap(name, labels, data, namespace='ckan-cloud'):
    configmap = get_resource('v1', 'ConfigMap', name, labels, namespace)
    return dict(configmap, data=data)


def get_persistent_volume_claim(name, labels, spec, namespace='ckan-cloud'):
    pvc = get_resource('v1', 'PersistentVolumeClaim', name, labels, namespace)
    return dict(pvc, spec=spec)


def get_deployment(name, labels, spec, namespace='ckan-cloud', with_timestamp=True):
    deployment = get_resource('apps/v1', 'Deployment', name, labels, namespace)
    deployment = dict(deployment, spec=spec)
    if with_timestamp:
        add_operator_timestamp_annotation(deployment['spec']['template']['metadata'])
    return deployment


def get_service(name, labels, ports, selector, namespace='ckan-cloud'):
    service = get_resource('v1', 'Service', name, labels, namespace)
    service['spec'] = {
        'ports': [
            {'name': str(port), 'port': int(port)}
            for port in ports
        ],
        'selector': selector
    }
    return service


def now():
    return datetime.datetime.now().isoformat()


def timestamp():
    return str(int(datetime.datetime.timestamp(datetime.datetime.now())))


def add_operator_timestamp_annotation(metadata):
    metadata.setdefault('annotations', {})['ckan-cloud/operator-timestamp'] = now()


def remove_finalizers(resource_kind, resource_name, ignore_not_found=False):
    if ignore_not_found and not get(f'{resource_kind} {resource_name}', required=False):
        return True
    else:
        return call(f'patch {resource_kind} {resource_name} -p \'{{"metadata":{{"finalizers":[]}}}}\' --type=merge') == 0


def remove_resource_and_dependencies(resource_kind, resource_name, related_kinds, label_selector):
    kinds = ','.join(related_kinds)
    return all([
        call(f'delete --ignore-not-found -l {label_selector} {kinds}') == 0,
        call(f'delete --ignore-not-found {resource_kind}/{resource_name}') == 0,
        remove_finalizers(resource_kind, resource_name, ignore_not_found=True)
    ])


__NONE__ = object


class BaseAnnotations(object):
    """Base class for managing annotations related to a custom resource"""

    @property
    def FLAGS(self):
        """Boolean flags which are saved as annotations on the resource"""
        return ['forceCreateAnnotations']

    @property
    def STATUSES(self):
        """Predefined statuses which are saved as annotations on the resource"""
        return {}

    @property
    def SECRET_ANNOTATIONS(self):
        """Sensitive details which are saved in a secret related to the resource"""
        return []

    @property
    def JSON_ANNOTATION_PREFIXES(self):
        """flexible annotations encoded to json and permitted using key prefixes"""
        return []

    @property
    def RESOURCE_KIND(self):
        raise NotImplementedError()

    def get_secret_labels(self):
        return {'ckan-cloud/annotations-secret': self.resource_id}

    def __init__(self, resource_id, resource_values=None, override_flags=None, persist_overrides=False):
        """Initializes an annotations object, optionally specifying previously fetched resource values"""
        self.resource_id = resource_id
        self.resource_values = resource_values
        self.resource_kind = self.RESOURCE_KIND.lower()
        self._override_flags = override_flags
        if self._override_flags:
            for flag in self._override_flags:
                assert flag in self.FLAGS, f'unknown flag: {flag}'
            if persist_overrides and len(self._override_flags) > 0:
                self._annotate(*['{}={}'.format(k, 'true' if v else 'false')
                                 for k, v in self._override_flags.items()], overwrite=True)

    def set_status(self, key, status):
        assert status in self.STATUSES[key], f'unknown status/key: {status}/{key}'
        self._annotate(f'{key}-{status}=true')

    def get_status(self, key, status):
        assert key in self.STATUSES.keys(), f'unknown status key: {key}'
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
        self._annotate(f'{flag}=true', overwrite=True)

    def set_flags(self, *flags):
        self._annotate(*[f'{flag}=true' for flag in flags], overwrite=True)

    def update_flag(self, flag, update_func, force_update=False):
        if self.get_flag(flag):
            if force_update:
                update_func()
                return True
            else:
                return False
        else:
            update_func()
            self.set_flag(flag)
            return True

    def get_flag(self, flag):
        """flags  are boolean fields which can be added manually to modify operator functionality

        Flags can be set using kubectl annotate on the resource, for example:

        kubectl -n ckan-cloud annotate DeisCkanInstance/atea32 ckan-cloud/forceCreateAnnotations=true
        """
        assert flag in self.FLAGS, f'unknown flag: {flag}'
        if self._override_flags and flag in self._override_flags:
            return self._override_flags[flag]
        else:
            value = self._get_annotation(flag)
            if type(value) == str:
                return False if value.lower().strip() in ['false', '0', 'no', ''] else bool(value)
            else:
                return bool(value)

    def get(self):
        data = {k.replace('ckan-cloud/', ''): v for k, v in self.resource_values['metadata']['annotations'].items()
                if k.startswith('ckan-cloud/')}
        data['ready'] = True
        return data

    def set_secrets(self, key_values):
        for key in key_values:
            assert key in self.SECRET_ANNOTATIONS, 'unknown secret annotation: {key}'
        secret = getattr(self, '_secret', None)
        cur_data = secret.get('data', {}) if secret and secret != __NONE__ else {}
        secret = get(f'secret {self.resource_kind}-{self.resource_id}-annotations', required=False)
        if not secret:
            secret = {'data': {}}
        secret['data'].update(**cur_data)
        for key, value in key_values.items():
            secret['data'][key] = base64.b64encode(value.encode()).decode()
        secret = {
            'apiVersion': 'v1',
            'kind': 'Secret',
            'metadata': {
                'name': f'{self.resource_kind}-{self.resource_id}-annotations',
                'namespace': 'ckan-cloud',
                'labels': self.get_secret_labels()
            },
            'type': 'Opaque',
            'data': secret['data']
        }
        logs.subprocess_run(f'kubectl apply -f -', input=yaml.dump(secret).encode())
        self._secret = secret

    def set_secret(self, key, value):
        self.set_secrets({key: value})

    def get_secret(self, key, default=None):
        assert key in self.SECRET_ANNOTATIONS, f'unknown secret annotation: {key}'
        secret = getattr(self, '_secret', None)
        if not secret:
            secret = get(f'secret {self.resource_kind}-{self.resource_id}-annotations', required=False)
            if not secret:
                secret = __NONE__
            self._secret = secret
        if secret and secret != __NONE__:
            value = secret.get('data', {}).get(key, None)
            return base64.b64decode(value).decode() if value else default
        else:
            return default

    def get_pod_env_spec_from_secret(self, env_name, value_key):
        return {
            'name': env_name,
            'valueFrom': {
                'secretKeyRef': {
                    'name': f'{self.resource_kind}-{self.resource_id}-annotations',
                    'key': value_key
                }
            }
        }

    def json_annotate(self, key, value, overwrite=True):
        ans = []
        assert any([key.startswith(prefix) for prefix in self.JSON_ANNOTATION_PREFIXES]), f'invalid json annotation key: {key}'
        value = json.dumps(value)
        ans.append(f"{key}='{value}'")
        self._annotate(*ans, overwrite=overwrite)

    def get_json_annotation(self, key):
        return json.loads(self._get_annotation(key))

    def _annotate(self, *annotations, overwrite=False):
        cmd = f'kubectl -n ckan-cloud annotate {self.resource_kind} {self.resource_id}'
        for annotation in annotations:
            cmd += f' ckan-cloud/{annotation}'
        if overwrite:
            cmd += ' --overwrite'
        logs.subprocess_check_call(cmd, shell=True)

    def _get_annotation(self, annotation, default=None):
        return self.resource_values['metadata'].get('annotations', {}).get(f'ckan-cloud/{annotation}', default)


def _parse_call_cmd(cmd, namespace, use_first_pod):
    args = []
    for arg in cmd.split(' '):
        splitarg = arg.split(':')
        if splitarg[0] == 'deployment-pod':
            _, deployment_namespace, deployment_name = splitarg
            if not deployment_namespace:
                deployment_namespace = namespace
            arg = get_deployment_pod_name(deployment_name, namespace=deployment_namespace, use_first_pod=use_first_pod)
        args.append(arg)
    return ' '.join(args)

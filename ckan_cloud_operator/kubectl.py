import yaml
import subprocess
import base64
import json
import os


def check_call(cmd, namespace='ckan-cloud'):
    subprocess.check_call(f'kubectl -n {namespace} {cmd}', shell=True)


def get(what, required=True, namespace='ckan-cloud'):
    try:
        return yaml.load(subprocess.check_output(f'kubectl -n {namespace} get {what} -o yaml', shell=True))
    except subprocess.CalledProcessError:
        if required:
            raise
        else:
            return None


def decode_secret(secret, attr=None):
    if attr:
        return base64.b64decode(secret['data'][attr]).decode()
    else:
        return {k: base64.b64decode(v).decode() for k, v in secret['data'].items()}


def update_secret(name, values, namespace='ckan-cloud'):
    secret = get(f'secret {name}', required=False, namespace=namespace)
    data = secret['data'] if secret else {}
    for k, v in values.items():
        data[k] = base64.b64encode(v.encode()).decode()
    secret = {
        'apiVersion': 'v1',
        'kind': 'Secret',
        'metadata': {
            'name': name,
            'namespace': namespace
        },
        'type': 'Opaque',
        'data': data
    }
    subprocess.run('kubectl apply -f -', input=yaml.dump(secret).encode(), shell=True, check=True)

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

import yaml
import subprocess
import base64


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

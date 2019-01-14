import subprocess
import functools
from ckan_cloud_operator.infra import CkanInfra


@functools.lru_cache(maxsize=1)
def activate():
    subprocess.check_call('ckan-cloud-operator activate-gcloud-auth', shell=True)
    return True


def check_output(cmd, project=None, with_activate=True):
    if with_activate: activate()
    if not project:
        infra = CkanInfra()
        project = infra.GCLOUD_AUTH_PROJECT
    return subprocess.check_output(f'gcloud --project={project} {cmd}', shell=True)


def check_call(cmd, project=None, with_activate=True, gsutil=False):
    if with_activate: activate()
    if not project:
        infra = CkanInfra()
        project = infra.GCLOUD_AUTH_PROJECT
    bin = 'gsutil' if gsutil else f'gcloud --project={project}'
    return subprocess.check_call(f'{bin} {cmd}', shell=True)


def getstatusoutput(cmd, project=None, with_activate=True):
    if with_activate: activate()
    if not project:
        infra = CkanInfra()
        project = infra.GCLOUD_AUTH_PROJECT
    return subprocess.getstatusoutput(f'gcloud --project={project} {cmd}')

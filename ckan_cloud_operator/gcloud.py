import subprocess
import functools
from ckan_cloud_operator.infra import CkanInfra


@functools.lru_cache(maxsize=1)
def activate():
    subprocess.check_call('ckan-cloud-operator activate-gcloud-auth', shell=True)
    return True


def check_output(cmd, project=None, with_activate=True, ckan_infra=None, gsutil=False):
    if with_activate: activate()
    if not ckan_infra:
        ckan_infra = CkanInfra()
    if not project:
        project = ckan_infra.GCLOUD_AUTH_PROJECT
    compute_zone = ckan_infra.GCLOUD_COMPUTE_ZONE
    bin = 'gsutil' if gsutil else f'CLOUDSDK_COMPUTE_ZONE={compute_zone} gcloud --project={project}'
    return subprocess.check_output(f'{bin} {cmd}', shell=True)


def check_call(cmd, project=None, with_activate=True, gsutil=False, ckan_infra=None):
    if with_activate: activate()
    if not ckan_infra:
        ckan_infra = CkanInfra()
    if not project:
        project = ckan_infra.GCLOUD_AUTH_PROJECT
        compute_zone = ckan_infra.GCLOUD_COMPUTE_ZONE
    bin = 'gsutil' if gsutil else f'CLOUDSDK_COMPUTE_ZONE={compute_zone} gcloud --project={project}'
    return subprocess.check_call(f'{bin} {cmd}', shell=True)


def getstatusoutput(cmd, project=None, with_activate=True, gsutil=False, ckan_infra=None):
    if with_activate: activate()
    if not ckan_infra:
        ckan_infra = CkanInfra()
    if not project:
        project = ckan_infra.GCLOUD_AUTH_PROJECT
        compute_zone = ckan_infra.GCLOUD_COMPUTE_ZONE
    bin = 'gsutil' if gsutil else f'CLOUDSDK_COMPUTE_ZONE={compute_zone} gcloud --project={project}'
    return subprocess.getstatusoutput(f'{bin} {cmd}')

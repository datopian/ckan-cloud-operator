#!/usr/bin/env python3
import os
import shutil
import tarfile
import subprocess
from glob import glob
from ckan_cloud_operator import kubectl
from ckan_cloud_operator.gitlab import CkanGitlab


INSTANCE_NAME = os.environ.get('INSTANCE_NAME')
ALLOWED_INSTANCE_NAMES = os.environ.get('ALLOWED_INSTANCE_NAMES')


def get_instance_gitlab_project(instance_id):
    image = get_instance_image(instance_id)
    if image.startswith('registry.gitlab.com/viderum/cloud-'):
        return image.split('@')[0].replace('registry.gitlab.com/', '')
    else:
        return None


def get_instance_image(instance_id):
    return {
        n: c.get('image', c.get('imageFromGitlab'))
        for n, c in {
            i['metadata']['name']: i['spec'].get('ckanContainerSpec', {})
            for i in kubectl.get('ckancloudckaninstance')['items']
        }.items()
    }.get(instance_id)


def get_instance_id(instance_name, allowed_instance_names):
    if allowed_instance_names:
        assert instance_name in allowed_instance_names.splitlines(), f'invalid instance name: {instance_name}'
    instance_id = {
      route['spec']['sub-domain'].replace('cc-p-', ''): route['spec']['deis-instance-id']
      for route  in kubectl.get('ckancloudroute')['items']
      if (
        route['spec']['route-target-type'] == 'deis-instance'
        and route['spec']['root-domain'] == 'default'
        and route['spec']['sub-domain'].startswith('cc-p-')
      )
    }.get(instance_name)
    assert instance_id, f'Failed to find matching instance_id for name {instance_name}'
    return instance_id


def export_code(instance_id):
    gitlab_project = get_instance_gitlab_project(instance_id)
    assert gitlab_project, f'failed to find gitlab project for instance id {instance_id}'
    gitlab_project_urlencoded = gitlab_project.replace('/', '%2F')
    CkanGitlab()._curl(
        f'projects/{gitlab_project_urlencoded}/repository/archive',
        token_name='reporeader',
        download_filename='code_with_internal_secrets.tar.gz'
    )
    shutil.unpack_archive('code_with_internal_secrets.tar.gz', 'code_with_internal_secrets')


def export_storage(instance_id):
    storage_path = kubectl.get(f'ckancloudckaninstance {instance_id}')['spec']['storage']['path']
    subprocess.check_call(f"mc config host add prod `ckan-cloud-operator storage credentials --raw` && mc cp --recursive prod{storage_path} ./storage",
                          shell=True)


def export_instance(instance_name, allowed_instance_names):
    instance_id = get_instance_id(instance_name, allowed_instance_names)
    export_code(instance_id)
    export_storage(instance_id)
    with tarfile.open('code.tar.gz', 'w:gz') as tar:
        for filename in glob('code_with_internal_secrets/**/*'):
            fileparts = filename.split('/')
            assert fileparts.pop(0) == 'code_with_internal_secrets'
            tar.add(filename, '/'.join(fileparts))
    with tarfile.open('storage.tar.gz', 'w:gz') as tar:
        for filename in glob('storage/**/*'):
            fileparts = filename.split('/')
            assert fileparts.pop(0) == 'storage'
            tar.add(filename, '/'.join(fileparts))


if __name__ == '__main__':
    export_instance(INSTANCE_NAME, ALLOWED_INSTANCE_NAMES)

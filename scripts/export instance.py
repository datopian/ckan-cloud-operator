#!/usr/bin/env python3
import os
import shutil
import tarfile
import subprocess
import datetime
import tempfile
import yaml
from glob import glob
from ckan_cloud_operator import kubectl
from ckan_cloud_operator.gitlab import CkanGitlab
from ckan_cloud_operator.config import manager as config_manager
from ckan_cloud_operator.drivers.gcloud import driver as gcloud_driver
from ckan_cloud_operator.providers.cluster import manager as cluster_manager


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


def export_db(instance_id):
    instance_spec = kubectl.get(f'ckancloudckaninstance {instance_id}')['spec']
    db_name = instance_spec['db']['name']
    db_prefix = instance_spec['db'].get('dbPrefix')
    datastore_name = instance_spec['datastore']['name']
    datastore_prefix = instance_spec['datastore'].get('dbPrefix')
    gs_base_url = config_manager.get(secret_name='ckan-cloud-provider-db-gcloudsql-credentials',
                                     key='backups-gs-base-url')
    db_prefix_path = f'{db_prefix}/' if db_prefix else ''
    datastore_prefix_path = f'{datastore_prefix}/' if datastore_prefix else ''
    latest_gs_urls = {
        'db': None,
        'datastore': None
    }
    latest_gs_urls_datetimes = {
        'db': None,
        'datastore': None
    }
    for dbtype in ['db', 'datastore']:
        for minus_days in (0, 1, 2):
            dt = (datetime.datetime.now() - datetime.timedelta(days=minus_days))
            datepath = dt.strftime('%Y/%m/%d')
            datesuffix = dt.strftime('%Y%m%d')
            if dbtype == 'datastore':
                ls_arg = f'{gs_base_url}{datastore_prefix_path}/{datepath}/*/{datastore_name}_{datesuffix}*.gz'
            else:
                ls_arg = f'{gs_base_url}{db_prefix_path}/{datepath}/*/{db_name}_{datesuffix}*.gz'
            output = gcloud_driver.check_output(
                *cluster_manager.get_provider().get_project_zone(), f'ls -l "{ls_arg}"',
                gsutil=True
            )
            for line in output.decode().splitlines():
                gsurl = line.strip().split(' ')[-1].strip()
                if gsurl.startswith('gs://'):
                    gs_url_datetime = datetime.datetime.strptime(gsurl.split('/')[-1].split('.')[-2].split('_')[-1], '%Y%m%d%H%M')
                    if not latest_gs_urls[dbtype] or latest_gs_urls_datetimes[dbtype] < gs_url_datetime:
                        latest_gs_urls[dbtype], latest_gs_urls_datetimes[dbtype] = gsurl, gs_url_datetime
            if latest_gs_urls[dbtype]:
                break
    return latest_gs_urls['db'], latest_gs_urls['datastore']
    # for dbtype in ['db', 'datastore']:
    #     gsurl, gsurl_datetime = latest_gs_urls[dbtype], latest_gs_urls_datetimes[dbtype]
    #     filename = '{}-{}'.format(dbtype, gsurl.split('/')[-1])
    #     print(f'Downloading {gsurl} ({gsurl_datetime}) --> {filename}')
    #     gcloud_driver.check_call(
    #         *cluster_manager.get_provider().get_project_zone(),
    #         f'cp {gsurl} ./{filename}',
    #         gsutil=True
    #     )


def gsutil_publish(filename, gsurl, duration='7d'):
    if gsurl:
        if filename:
            subprocess.check_call(f'ls -lah {filename}', shell=True)
            gcloud_driver.check_call(
                *cluster_manager.get_provider().get_project_zone(),
                f'cp ./{filename} {gsurl}',
                gsutil=True
            )
        with tempfile.NamedTemporaryFile('w') as f:
            f.write(config_manager.get(key='service-account-json', secret_name='ckan-cloud-provider-cluster-gcloud'))
            f.flush()
            output = gcloud_driver.check_output(
                *cluster_manager.get_provider().get_project_zone(),
                f'signurl -d {duration} {f.name} {gsurl}',
                gsutil=True
            )
            signed_gsurls = [line for line in [line.strip().split('\t')[-1].strip() for line in output.decode().splitlines()] if len(line) > 20]
            assert len(signed_gsurls) == 1
        return signed_gsurls[0]
    else:
        return None


def export_instance(instance_name, allowed_instance_names):
    instance_id = get_instance_id(instance_name, allowed_instance_names)
    gs_base_url = config_manager.get(secret_name='ckan-cloud-provider-db-gcloudsql-credentials',
                                     key='backups-gs-base-url')
    backup_prefix = 'export/{}/{}'.format(instance_name, datetime.datetime.now().strftime('%Y%m%d%H%M'))
    export_code(instance_id)
    with tarfile.open('code.tar.gz', 'w:gz') as tar:
        for filename in glob('code_with_internal_secrets/**/*'):
            fileparts = filename.split('/')
            assert fileparts.pop(0) == 'code_with_internal_secrets'
            tar.add(filename, '/'.join(fileparts))
    code_signed_gsurl = gsutil_publish('code.tar.gz', f'{gs_base_url}/{backup_prefix}/code.tar.gz')
    code_with_secrets_signed_gsurl = gsutil_publish('code_with_internal_secrets.tar.gz', f'{gs_base_url}/{backup_prefix}/code_with_internal_secrets.tar.gz')
    export_storage(instance_id)
    with tarfile.open('storage.tar.gz', 'w:gz') as tar:
        for filename in glob('storage/**/*'):
            fileparts = filename.split('/')
            assert fileparts.pop(0) == 'storage'
            tar.add(filename, '/'.join(fileparts))
    storage_signed_gsurl = gsutil_publish('storage.tar.gz', f'{gs_base_url}/{backup_prefix}/storage.tar.gz')
    db_gs_url, datastore_gs_url = export_db(instance_id)
    db_signed_gsurl = gsutil_publish(None, db_gs_url)
    datastore_signed_gsurl = gsutil_publish(None, datastore_gs_url)
    return {
        'code': code_signed_gsurl,
        'code_with_secrets': code_with_secrets_signed_gsurl,
        'storage': storage_signed_gsurl,
        'db': db_signed_gsurl,
        'datastore': datastore_signed_gsurl
    }


if __name__ == '__main__':
    print(yaml.dump(export_instance(INSTANCE_NAME, ALLOWED_INSTANCE_NAMES), default_flow_style=False))
    exit(0)

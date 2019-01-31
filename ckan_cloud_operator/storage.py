import tempfile
import binascii
import os
import datetime

from ckan_cloud_operator import gcloud
from ckan_cloud_operator.infra import CkanInfra
from ckan_cloud_operator import kubectl
from ckan_cloud_operator.routers import manager as routers_manager
from ckan_cloud_operator import logs


PERMISSIONS_FUNCTION_PACKAGE_JSON = """
{
  "dependencies": {
    "@google-cloud/storage": "^2.3.4"
  }
}
"""


PERMISSIONS_FUNCTION_JS = lambda function_name, project_id, bucket_name: """
exports.""" + function_name + """ = (event, callback) => {
  const {Storage} = require('@google-cloud/storage');
  const projectId = '""" + project_id + """';
  const bucketName = '"""+ bucket_name +"""';
  const file_name = event.data.name;
  if (file_name === 'ckan') {
      callback();
  } else {
      console.log(`  File: ${file_name}`);
      const storage = new Storage();
      const bucket = storage.bucket(bucketName);
      const file = bucket.file(file_name)
      file.makePrivate().then(function(){
        callback();
      }).catch(function(err){
        callback(err);
      });
  };
};
"""


def deploy_storage_permissions_function():
    """Deploys a serverless function that sets all keys to private"""
    ckan_infra = CkanInfra()
    bucket_name = ckan_infra.GCLOUD_STORAGE_BUCKET
    project_id = ckan_infra.GCLOUD_AUTH_PROJECT
    function_name = bucket_name.replace('-', '') + 'permissions'
    function_js = PERMISSIONS_FUNCTION_JS(function_name, project_id, bucket_name)
    package_json = PERMISSIONS_FUNCTION_PACKAGE_JSON
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(f'{tmpdir}/package.json', 'w') as f:
            f.write(package_json)
        with open(f'{tmpdir}/index.js', 'w') as f:
            f.write(function_js)
        gcloud.check_call(
            f'functions deploy {function_name} '
                               f'--runtime nodejs6 '
                               f'--trigger-resource {bucket_name} '
                               f'--trigger-event google.storage.object.finalize '
                               f'--source {tmpdir} '
                               f'--retry '
                               f'--timeout 30s ',
            ckan_infra=ckan_infra
        )


def deploy_minio(minio_router_name, disk_size_gb):
    """Deploys a minio server backed by google persistent disk to provide centralized storage"""
    labels = {'app': 'ckan-cloud-minio'}
    if not kubectl.get('secret minio-credentials', required=False):
        print('Creating minio credentials')
        minio_access_key = binascii.hexlify(os.urandom(8)).decode()
        minio_secret_key = binascii.hexlify(os.urandom(12)).decode()
        kubectl.update_secret('minio-credentials', {
            'MINIO_ACCESS_KEY': minio_access_key,
            'MINIO_SECRET_KEY': minio_secret_key,
        })
    ckan_infra = CkanInfra()
    routers_env_id = ckan_infra.ROUTERS_ENV_ID
    disk_id = f'cc-{routers_env_id}-minio'
    returncode, output = gcloud.getstatusoutput(f'compute disks describe {disk_id}')
    if returncode == 0:
        logs.info(f'persistent disk already exists: {disk_id}')
    else:
        logs.info(f'creating persistent disk {disk_id}')
        gcloud.check_call(f'compute disks create {disk_id} --size={disk_size_gb}GB ')
    logs.info('updating minio deployment')
    kubectl.apply(kubectl.get_deployment('minio', labels, {
        'replicas': 1,
        'revisionHistoryLimit': 10,
        'strategy': {'type': 'Recreate', },
        'template': {
            'metadata': {
                'labels': labels,
                'annotations': {
                    'ckan-cloud/operator-timestamp': str(datetime.datetime.now())
                }
            },
            'spec': {
                'containers': [
                    {
                        'name': 'minio',
                        'image': 'minio/minio',
                        'args': ['server', '/export'],
                        'envFrom': [{'secretRef': {'name': 'minio-credentials'}}],
                        'ports': [{'containerPort': 9000}],
                        'volumeMounts': [
                            {
                                'name': 'minio-data',
                                'mountPath': '/export',
                            }
                        ],
                    }
                ],
                'volumes': [
                    {'name': 'minio-data', 'gcePersistentDisk': {'pdName': disk_id}}
                ]
            }
        }
    }))
    service = kubectl.get_resource('v1', 'Service', 'minio', labels)
    service['spec'] = {
        'ports': [
            {'name': '9000', 'port': 9000}
        ],
        'selector': labels
    }
    kubectl.apply(service)
    if not routers_manager.get_backend_url_routes('minio'):
        routers_manager.create_subdomain_route(minio_router_name, {
            'target-type': 'backend-url',
            'target-resource-id': 'minio',
            'backend-url': 'http://minio.ckan-cloud:9000',
            'sub-domain': 'default',
            'root-domain': 'default',
        })
    routers_manager.update(minio_router_name, wait_ready=True)


def deploy_gcs_minio_proxy(router_name):
    """Deploys a minio proxy (AKA gateway) for access to google storage"""
    labels = {'app': 'ckan-cloud-gcsminio-proxy'}
    if not kubectl.get('secret gcsminio-proxy-credentials', required=False):
        print('Creating minio credentials')
        minio_access_key = binascii.hexlify(os.urandom(8)).decode()
        minio_secret_key = binascii.hexlify(os.urandom(12)).decode()
        kubectl.update_secret('gcsminio-proxy-credentials', {
            'MINIO_ACCESS_KEY': minio_access_key,
            'MINIO_SECRET_KEY': minio_secret_key,
        })
    kubectl.apply(kubectl.get_deployment('gcsminio-proxy', labels, {
        'replicas': 1,
        'revisionHistoryLimit': 10,
        'strategy': {'type': 'RollingUpdate',},
        'template': {
            'metadata': {
                'labels': labels,
                'annotations': {
                    'ckan-cloud/operator-timestamp': str(datetime.datetime.now())
                }
            },
            'spec': {
                'containers': [
                    {
                        'name': 'minio',
                        'image': 'viderum/ckan-cloud-operator-gcsminio-proxy',
                        'env': [
                            {
                                'name': 'GOOGLE_APPLICATION_CREDENTIALS',
                                'value': '/gcloud-credentials/credentials.json'
                            }
                        ],
                        'envFrom': [{'secretRef': {'name': 'gcsminio-proxy-credentials'}}],
                        'ports': [{'containerPort': 9000}],
                        'volumeMounts': [
                            {'name': 'gcloud-credentials',
                             'mountPath': '/gcloud-credentials/credentials.json',
                             'subPath': 'GCLOUD_SERVICE_ACCOUNT_JSON'},
                        ],
                    }
                ],
                'volumes': [
                    {'name': 'gcloud-credentials', 'secret': {'secretName': 'ckan-infra'}},
                ]
            }
        }
    }))
    service = kubectl.get_resource('v1', 'Service','gcsminio-proxy', labels)
    service['spec'] = {
        'ports': [
            {'name': '9000', 'port': 9000}
        ],
        'selector': labels
    }
    kubectl.apply(service)
    if not routers_manager.get_backend_url_routes('gcs-minio'):
        routers_manager.create_subdomain_route(router_name, {
            'target-type': 'backend-url',
            'target-resource-id': 'gcs-minio',
            'backend-url': 'http://gcsminio-proxy.ckan-cloud:9000',
            'sub-domain': 'default',
            'root-domain': 'default',
        })
    routers_manager.update(router_name, wait_ready=True)

#### standard provider code ####

# import the correct PROVIDER_SUBMODULE and PROVIDER_ID constants for your provider
from .constants import PROVIDER_ID
from ..constants import PROVIDER_SUBMODULE

# define common provider functions based on the constants
from ckan_cloud_operator.providers import manager as providers_manager
def _get_resource_name(suffix=None): return providers_manager.get_resource_name(PROVIDER_SUBMODULE, PROVIDER_ID, suffix=suffix)
def _get_resource_labels(for_deployment=False): return providers_manager.get_resource_labels(PROVIDER_SUBMODULE, PROVIDER_ID, for_deployment=for_deployment)
def _get_resource_annotations(suffix=None): return providers_manager.get_resource_annotations(PROVIDER_SUBMODULE, PROVIDER_ID, suffix=suffix)
def _set_provider(): providers_manager.set_provider(PROVIDER_SUBMODULE, PROVIDER_ID)
def _config_set(key=None, value=None, values=None, namespace=None, is_secret=False, suffix=None): providers_manager.config_set(PROVIDER_SUBMODULE, PROVIDER_ID, key=key, value=value, values=values, namespace=namespace, is_secret=is_secret, suffix=suffix)
def _config_get(key=None, default=None, required=False, namespace=None, is_secret=False, suffix=None): return providers_manager.config_get(PROVIDER_SUBMODULE, PROVIDER_ID, key=key, default=default, required=required, namespace=namespace, is_secret=is_secret, suffix=suffix)
def _config_interactive_set(default_values, namespace=None, is_secret=False, suffix=None, from_file=False): providers_manager.config_interactive_set(PROVIDER_SUBMODULE, PROVIDER_ID, default_values, namespace, is_secret, suffix, from_file)

################################
# custom provider code starts here
#

import yaml
import json
import subprocess
import datetime
import os
import binascii
import collections

from ckan_cloud_operator import kubectl
from ckan_cloud_operator.drivers.kubectl import rbac
from ckan_cloud_operator import logs


def initialize(interactive=False):
    _set_provider()
    if interactive:
        print('\nEnter credentials for an AWS Access Key with relevant permissions\n')
        _config_interactive_set({'aws-access-key-id': None}, is_secret=True)
        _config_interactive_set({'aws-secret-access-key': None}, is_secret=True)
        print('\nEnter the AWS Region the Amazon Kubernets cluster is hosted on\n')
        _config_interactive_set({'aws-default-region': None}, is_secret=True)
        print('\nEnter the name of your Amazon EKS cluster\n')
        _config_interactive_set({'eks-cluster-name': None}, is_secret=True)
    print(yaml.dump(get_info(), default_flow_style=False))
    from ckan_cloud_operator.providers.storage.efs import manager as efs_manager
    efs_manager.initialize(interactive=interactive)
    _create_storage_classes()
    _update_service_account()


def _update_service_account():
    rbac.update_cluster_role_binding(
        name='default-admin-rbac',
        subject=dict(
            kind='ServiceAccount',
            name='default',
            namespace='default',
        ),
        cluster_role_name='cluster-admin',
        labels=_get_resource_labels()
    )


def _create_storage_classes():
    kubectl.apply({
        'apiVersion': 'storage.k8s.io/v1', 'kind': 'StorageClass',
        'metadata': {
            'name': 'cca-ckan',
        },
        'provisioner': 'example.com/aws-efs',
        'reclaimPolicy': 'Delete',
        'volumeBindingMode': 'Immediate'
    })
    kubectl.apply({
        'apiVersion': 'storage.k8s.io/v1', 'kind': 'StorageClass',
        'metadata': {
            'name': 'cca-storage',
        },
        'provisioner': 'kubernetes.io/aws-ebs',
        'reclaimPolicy': 'Delete',
        'volumeBindingMode': 'Immediate',
        'parameters': {
            'encrypted': 'false',
            'type': 'gp2',
        }
    })


def get_info(debug=False):
    cluster = _config_get('eks-cluster-name', is_secret=True)
    data = yaml.load(aws_check_output(f'eks describe-cluster --name {cluster}'))['cluster']
    if debug:
        return data
    else:
        return {
            'name': data['name'],
            'status': data['status'],
            # 'zone': data['zone'],
            # 'locations': data['locations'],
            'endpoint': data['endpoint'],
            # 'nodePools': [
            #     {
            #         'name': pool['name'],
            #         'status': pool['status'],
            #         'version': pool['version'],
            #         'config': {
            #             'diskSizeGb': pool['config']['diskSizeGb'],
            #             'machineType': pool['config']['machineType'],
            #         },
            #     } for pool in data['nodePools']
            # ],
            'createTime': datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc) + datetime.timedelta(seconds=float(data['createdAt'])),
            'currentMasterVersion': data['version'],
            # 'currentNodeCount': data['currentNodeCount'],
        }


def get_aws_credentials():
    return {
        'access': _config_get('aws-access-key-id', is_secret=True),
        'secret': _config_get('aws-secret-access-key', is_secret=True),
        'region': _config_get('aws-default-region', is_secret=True)
    }

def aws_process_cmd(cmd):
    access = _config_get('aws-access-key-id', is_secret=True)
    secret = _config_get('aws-secret-access-key', is_secret=True)
    region = _config_get('aws-default-region', is_secret=True)
    cmd = f"AWS_DEFAULT_REGION={region} aws {cmd}"
    if len(access) >= 20 and len(secret) >= 40:
        cmd = f"AWS_ACCESS_KEY_ID={access} AWS_SECRET_ACCESS_KEY={secret} " + cmd
    return cmd

def aws_check_output(cmd):
    return subprocess.check_output(aws_process_cmd(cmd), shell=True)


def exec(cmd):
    subprocess.check_call(aws_process_cmd(cmd), shell=True)


def create_volume(disk_size_gb, labels, use_existing_disk_name=None, zone=0):
    assert not use_existing_disk_name, 'using existing disk name is not supported yet'
    availability_zone = get_storage_availability_zone(zone)
    logs.info(f'creating persistent disk with size {disk_size_gb} in availability zone {availability_zone}')
    tags = 'ResourceType=volume,Tags=[{Key=Owner,Value=cco}]'
    data = json.loads(aws_check_output(f'ec2 create-volume -- --size {disk_size_gb} --availability-zone {availability_zone} --tag-specification "{tags}"'))
    volume_id = data['VolumeId']
    logs.info(f'volume_id={volume_id}')
    kubectl.apply({
        'apiVersion': 'v1', 'kind': 'PersistentVolume',
        'metadata': {'name': volume_id, 'namespace': 'ckan-cloud'},
        'spec': {
            'storageClassName': '',
            'capacity': {'storage': f'{disk_size_gb}G'},
            'accessModes': ['ReadWriteOnce'],
            'awsElasticBlockStore': {'volumeID': volume_id}
        }
    })
    kubectl.apply({
        'apiVersion': 'v1', 'kind': 'PersistentVolumeClaim',
        'metadata': {'name': volume_id, 'namespace': 'ckan-cloud'},
        'spec': {
            'storageClassName': '',
            'volumeName': volume_id,
            'accessModes': ['ReadWriteOnce'],
            'resources': {'requests': {'storage': f'{disk_size_gb}G'}}
        }
    })
    return {
        'persistentVolumeClaim': {
            'claimName': volume_id
        },
        'nodeSelector': {
            'failure-domain.beta.kubernetes.io/zone': availability_zone
        }
    }


def get_storage_availability_zone(zone):
    region = _config_get('aws-default-region', is_secret=True)
    region += 'abc'[zone % 3]
    return region


def get_name():
    name = _config_get('cluster-name')
    if not name:
        name = get_info()['name']
        _config_set('cluster-name', name)
    return name


def get_boto3_client(service_name):
    import boto3
    access = _config_get('aws-access-key-id', is_secret=True)
    secret = _config_get('aws-secret-access-key', is_secret=True)
    kwargs = {}
    if len(access) >= 20 and len(secret) >= 40:
        kwargs = dict(aws_access_key_id=access, aws_secret_access_key=secret)
    return boto3.client(service_name, **kwargs)


def get_dns_hosted_zone_id(root_domain):
    client = get_boto3_client('route53')
    return client.list_hosted_zones_by_name(DNSName=f'{root_domain}.', MaxItems='1')['HostedZones'][0]['Id']


def update_dns_record(sub_domain, root_domain, load_balancer_hostname):
    logs.info('updating Route53 DNS record', sub_domain=sub_domain, root_domain=root_domain, load_balancer_hostname=load_balancer_hostname)
    hosted_zone_id = get_dns_hosted_zone_id(root_domain)
    logs.info(hosted_zone_id=hosted_zone_id)
    response = get_boto3_client('route53').change_resource_record_sets(
        HostedZoneId=hosted_zone_id,
        ChangeBatch={
            'Comment': 'ckan-cloud-operator',
            'Changes': [
                {
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'Name': f'{sub_domain}.{root_domain}.',
                        'Type': 'CNAME',
                        'TTL': 300,
                        'ResourceRecords': [
                            {
                                'Value': load_balancer_hostname
                            },
                        ],
                    }
                },
            ]
        }
    )
    assert response['ResponseMetadata']['HTTPStatusCode'] == 200

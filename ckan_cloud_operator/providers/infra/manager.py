import subprocess
import time
import sys

from ckan_cloud_operator import logs
from ckan_cloud_operator import kubectl

def get_solr_pods(format=''):
    kubectl.call(f'get pods', 'ckan-cloud')

def get_container_logs(**kubectl_args):
    zk = kubectl_args.pop('zookeper_only', None)
    sc = kubectl_args.pop('solrcloud_only', None)
    suf = 'zk' if zk else 'sc'
    service = f'ckan-cloud-provider-solr-solrcloud-{suf}-headless'
    stream_logs = '-f ' if kubectl_args.pop('follow', None) else ''
    k_args = [f'--{k}={v}' for k,v in kubectl_args.items() if v is not None]
    full_args = stream_logs + ' '.join(k_args)
    _stream_logs(f'kubectl -n ckan-cloud logs service/{service} {full_args}')


def restart_solr_pods(zookeper_only, solrcloud_only, force=False):
    pod_name = '--all'
    force = '--force --grace-period=0' if force else ''
    if zookeper_only:
        kubectl.delete_items_by_labels(['pod'], {'app':'provider-solr-solrcloud-zk'}, 'ckan-cloud')
        return
    if solrcloud_only:
        kubectl.delete_items_by_labels(['pod'], {'app':'provider-solr-solrcloud-sc'}, 'ckan-cloud')
        return
    kubectl.call(f'delete pods {pod_name} {force}', 'ckan-cloud')


def _stream_logs(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
    for c in iter(lambda: process.stdout.read(1), b''):
        sys.stdout.buffer.write(c)


def _get_running_pod_name(instance_id, service='ckan'):
    pod_name = None
    while not pod_name:
        try:
            pod_name = kubectl.get_deployment_pod_name(service, instance_id, use_first_pod=True, required_phase='Running')
            break
        except Exception as e:
            logs.warning('Failed to find running ckan pod', str(e))
        time.sleep(20)
    return pod_name

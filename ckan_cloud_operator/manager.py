import subprocess
import yaml

from xml.etree import ElementTree

from ckan_cloud_operator.infra import CkanInfra
from ckan_cloud_operator import gcloud
from ckan_cloud_operator.deis_ckan.instance import DeisCkanInstance
import ckan_cloud_operator.routers.manager as routers_manager
import ckan_cloud_operator.users
import ckan_cloud_operator.datapushers
import ckan_cloud_operator.storage


def install_crds():
    DeisCkanInstance.install_crd()
    routers_manager.install_crds()
    ckan_cloud_operator.users.install_crds()
    ckan_cloud_operator.datapushers.install_crds()


def print_cluster_info(full=False):
    subprocess.check_call('kubectl cluster-info && '
                          '( kubectl -n ckan-cloud get secret ckan-infra || true ) && '
                          'kubectl config get-contexts $(kubectl config current-context) && '
                          'kubectl get nodes', shell=True)
    if full:
        infra = CkanInfra()
        output = gcloud.check_output(f'sql instances describe {infra.GCLOUD_SQL_INSTANCE_NAME} --format=json',
                                     ckan_infra=infra)
        data = yaml.load(output)
        print(yaml.dump({'gcloud_sql': {'connectionName': data['connectionName'],
                                        'databaseVersion': data['databaseVersion'],
                                        'gceZone': data['gceZone'],
                                        'ipAddresses': data['ipAddresses'],
                                        'name': data['name'],
                                        'project': data['project'],
                                        'region': data['region'],
                                        'selfLink': data['selfLink'],
                                        'state': data['state']}}))
        output = subprocess.check_output(f'curl {infra.SOLR_HTTP_ENDPOINT}/admin/collections?action=LIST', shell=True)
        if output:
            root = ElementTree.fromstring(output.decode())
            print('solr-collections:')
            for e in root.find('arr').getchildren():
                print(f'- {e.text}')
        else:
            raise Exception()

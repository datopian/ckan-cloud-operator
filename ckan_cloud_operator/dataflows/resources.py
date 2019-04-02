import os
import subprocess
import yaml
import json

from dataflows import Flow, update_resource, printer, checkpoint, dump_to_path


def get_kube_items(operator, what, spec_fields=None, metadata_fields=None, status_fields=None):
    for item in yaml.load(subprocess.check_output(
        f'{operator} kubectl -- get {what} -o yaml', shell=True
    ))['items']:
        yield {
            **{k: v for k, v
               in item.get('spec', {}).items()
               if spec_fields is None or k in spec_fields},
            **{k: v for k, v
               in item.get('metadata', {}).items()
               if metadata_fields is None or k in metadata_fields},
            **{k: v for k, v
               in item.get('status', {}).items()
               if status_fields is None or k in status_fields}
        }



def cluster_info(operator):
    output = subprocess.check_output(f'{operator} cluster info', shell=True)
    yield from (cluster for cluster in yaml.load(output))


def ckan_cloud_instances(operator):

    def _processor(package):
        package.pkg.add_resource({
            'name': 'ckan-cloud-instances',
            'path': 'ckan-cloud-instances.csv',
            'schema': {
                'fields': [
                    {'name': n, 'type': 'string'} for n in
                    ['name', 'url', 'image', 'datastore', 'db', 'solr',
                     'storage', 'creationTimestamp', 'generation']
                ]
            }
        })
        yield package.pkg

        def get_normalized():
            items = get_kube_items(
                operator, 'ckancloudckaninstance',
                spec_fields=[
                    'ckanContainerSpec', 'ckanPodSpec', 'datastore', 'db',
                    'envvars', 'solrCloudCollection', 'storage'
                ],
                metadata_fields=[
                    'creationTimestamp', 'generation', 'name', 'namespace', 'resourceVersion', 'uid'
                ],
                status_fields=[]
            )
            for row in items:
                dbs = {}
                for db_type in ['datastore', 'db']:
                    dbs[db_type] = row[db_type]['name']
                    if row[db_type].get('dbPrefix'):
                        dbs[db_type] += f" ({row[db_type]['dbPrefix']})"
                solr = f"{row['solrCloudCollection']['name']} ({row['solrCloudCollection']['configName']})"
                instance_id = row['name']
                try:
                    url = subprocess.check_output(
                        f"{operator} deis-instance ckan exec {instance_id} -- -- "
                          f"bash -c 'env | grep CKAN_SITE_URL='",
                        shell=True
                    ).decode().split('=')[1]
                except Exception:
                    url = ''
                yield {
                    'name': row['name'],
                    'url': url.strip(),
                    'image': (
                        row['ckanContainerSpec']['image']
                        if row['ckanContainerSpec'].get('image')
                        else f"{row['ckanContainerSpec']['imageFromGitlab']} (imageFromGitlab)"
                    ),
                    'datastore': dbs['datastore'],
                    'db': dbs['db'],
                    'solr': solr,
                    'storage': row['storage']['path'],
                    'creationTimestamp': str(row['creationTimestamp']),
                    'generation': str(row['generation']),
                }
            for row in add_non_ckan_instances():
                yield row

        for resource in package:
            yield resource
        yield get_normalized()

    def add_non_ckan_instances():
        non_ckan_instances = os.environ.get('NON_CKAN_INSTANCES')
        if non_ckan_instances:
            non_ckan_instances = json.loads(non_ckan_instances)
            for instance in non_ckan_instances:
                instance_name = instance['name']
                get_route_args = instance['get-route-args']
                deployment = yaml.load(
                    subprocess.check_output(
                        f'{operator} kubectl -- -n {instance_name} get deployment {instance_name} -o yaml',
                        shell=True)
                )
                yield {
                    'name': instance_name,
                    'url': 'https://' + yaml.load(subprocess.check_output(
                        f'{operator} routers get-routes {get_route_args} --one',
                        shell=True
                    ))['frontend-hostname'],
                    'image': deployment['spec']['template']['spec']['containers'][0]['image'],
                    'datastore': '',
                    'db': '',
                    'solr': '',
                    'storage': '',
                    'creationTimestamp': str(deployment['metadata']['creationTimestamp']),
                    'generation': '',
                }

    return _processor


def main_flow(prefix, operator):
    return Flow(
        cluster_info(operator),
        update_resource(['res_1'], name='cluster-info', path='cluster-info.csv'),
        checkpoint(f'{prefix}-cluster-info'),
        ckan_cloud_instances(operator),
        update_resource(['res_2'], name='ckan-cloud-instances', path='ckan-cloud-instances.csv'),
    )


if __name__ == '__main__':
    prefix = os.environ['DATAPACKAGE_PREFIX']
    operator = os.environ.get('CKAN_CLOUD_OPERATOR_BIN', 'ckan-cloud-operator')
    Flow(
        main_flow(prefix, operator),
        printer(num_rows=1),
        dump_to_path(f'data/{prefix}/resources')
    ).process()

import json
import os
from dataflows import Flow, dump_to_path, printer
from ckan_cloud_operator.providers.ckan.instance import manager as ckan_instance_manager
from ckan_cloud_operator import logs


def dump_to_json(data):

    def _dump_to_json(rows):
        for row in rows:
            yield row
            data.append(row)

    return _dump_to_json


def get_instance_row(instance):
    row = {
        'id': instance.get('id', ''),
        'name': instance.get('name', ''),
        'ready': instance.get('ready', ''),
        'deployment_ready': instance.get('deployment', {}).get('ready', ''),
        'latest_pod_image': instance.get('deployment', {}).get('image', ''),
        'latest_pod_name': instance.get('deployment', {}).get('latest_pod_name', ''),
    }
    return row


def list_instances():
    os.makedirs('data/list_instances', exist_ok=True)
    data = []
    Flow(
        (get_instance_row(instance) for instance in ckan_instance_manager.list_instances(full=True)),
        dump_to_json(data),
        dump_to_path('data/list_instances'),
        printer(num_rows=99999)
    ).process()
    with open('data/list_instances.json', 'w') as f:
        json.dump(data, f)


if __name__ == '__main__':
    list_instances()

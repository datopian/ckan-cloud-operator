#!/usr/bin/env python3
import json
import os
from dataflows import Flow, dump_to_path, printer

from ckan_cloud_operator.providers.ckan.instance import manager as ckan_instance_manager
from ckan_cloud_operator.routers import manager as routers_manager


def dump_to_json(rows):
    data = []
    for row in rows:
        yield row
        data.append(row)
    with open('data/list_instances.json', 'w') as f:
        json.dump(data, f)


def get_instance_row(instance):
    return {
        'id': instance['id'],
        'name': instance.get('name'),
        'ready': instance['ready'],
        'deployment_ready': instance.get('deployment', {}).get('ready'),
        'latest_pod_image': instance.get('deployment', {}).get('image'),
        'latest_pod_name': instance.get('deployment', {}).get('latest_pod_name'),
    }


def list_instances():
    os.makedirs('data/list_instances', exist_ok=True)
    Flow(
        (get_instance_row(instance) for instance in ckan_instance_manager.list_instances(full=True)),
        dump_to_json,
        dump_to_path('data/list_instances'),
        printer(num_rows=99999)
    ).process()


if __name__ == '__main__':
    list_instances()

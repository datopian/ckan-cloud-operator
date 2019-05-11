import json
import os
from dataflows import Flow, dump_to_path, printer
from ckan_cloud_operator.providers.apps import manager as apps_manager
from ckan_cloud_operator import logs


def dump_to_json(data):

    def _dump_to_json(rows):
        for row in rows:
            yield row
            data.append(row)

    return _dump_to_json


def get_instance_row(instance):
    row = {
        'id': str(instance.get('id') or ''),
        'name': str(instance.get('name') or ''),
        'ready': bool(instance.get('ready') or False),
    }
    return row


def list_instances():
    os.makedirs('data/apps/list_instances', exist_ok=True)
    data = []
    Flow(
        (get_instance_row(instance) for instance in apps_manager.list_instances(full=True)),
        dump_to_json(data),
        dump_to_path('data/apps/list_instances'),
        printer(num_rows=99999)
    ).process()
    with open('data/apps/list_instances.json', 'w') as f:
        json.dump(data, f)


if __name__ == '__main__':
    list_instances()

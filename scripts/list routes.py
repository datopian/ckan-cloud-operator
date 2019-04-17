#!/usr/bin/env python3

import subprocess, os, yaml
import ckan_cloud_operator.kubectl  # it fixes some yaml functionality (even if not used)
from contextlib import redirect_stdout
from dataflows import Flow, dump_to_path, printer, update_resource

routes = []


def get_routers():
    routers = subprocess.check_output(f'ckan-cloud-operator routers list --full | tee /dev/stderr', shell=True).decode()
    for router in yaml.load(routers):
        for route in router['routes']:
            routes.append({'router_name': router['name'], **route})
        yield {
            'name': router['name'],
            'ready': router['ready'],
            'routes': len(router['routes']),
            'deployment_created_at': router['deployment'].get('created_at'),
            'deployment_generation': router['deployment'].get('generation'),
            'deployment_namespace': router['deployment'].get('namespace'),
            'deployment_ready': router['deployment'].get('ready'),
            'type': router['type'],
            'dns': router['dns'],
        }


def get_routes():
    yield from routes


with open('output.html', 'w') as f:
    with redirect_stdout(f):
        Flow(
            get_routers(),
            update_resource('res_1', name='routers', path='routers.csv'),
            get_routes(),
            update_resource('res_2', name='routes', path='routes.csv'),
            dump_to_path(),
            printer(num_rows=9999999, tablefmt='html'),
        ).process()

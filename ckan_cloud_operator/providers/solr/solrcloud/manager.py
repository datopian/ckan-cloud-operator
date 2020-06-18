#### standard provider code ####

from .constants import PROVIDER_ID
from ..constants import PROVIDER_SUBMODULE
from ckan_cloud_operator.providers.cluster import manager as cluster_manager

# define common provider functions based on the constants
from ckan_cloud_operator.providers import manager as providers_manager
def _get_resource_name(suffix=None): return providers_manager.get_resource_name(PROVIDER_SUBMODULE, PROVIDER_ID, suffix=suffix)
def _get_resource_labels(for_deployment=False, suffix=None): return providers_manager.get_resource_labels(PROVIDER_SUBMODULE, PROVIDER_ID, for_deployment=for_deployment, suffix=suffix)
def _get_resource_annotations(suffix=None, with_timestamp=False): return providers_manager.get_resource_annotations(PROVIDER_SUBMODULE, PROVIDER_ID, suffix=suffix, with_timestamp=with_timestamp)
def _set_provider(): providers_manager.set_provider(PROVIDER_SUBMODULE, PROVIDER_ID)
def _config_set(key=None, value=None, values=None, namespace=None, is_secret=False, suffix=None): providers_manager.config_set(PROVIDER_SUBMODULE, PROVIDER_ID, key=key, value=value, values=values, namespace=namespace, is_secret=is_secret, suffix=suffix)
def _config_get(key=None, default=None, required=False, namespace=None, is_secret=False, suffix=None): return providers_manager.config_get(PROVIDER_SUBMODULE, PROVIDER_ID, key=key, default=default, required=required, namespace=namespace, is_secret=is_secret, suffix=suffix)
def _config_interactive_set(default_values, namespace=None, is_secret=False, suffix=None, from_file=False, interactive=True): providers_manager.config_interactive_set(PROVIDER_SUBMODULE, PROVIDER_ID, default_values, namespace, is_secret, suffix, from_file, interactive)

################################
# custom provider code starts here
#

import subprocess
import yaml
import json
import time
import os

from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs
from ckan_cloud_operator.config import manager as config_manager
from ckan_cloud_operator.providers.cluster import manager as cluster_manager

from .constants import LOG4J_PROPERTIES, SOLR_CONFIG_XML


def start_zoonavigator_port_forward():
    connection_string = ','.join(yaml.load(_config_get('zk-host-names')))
    print("\nStarting port forward to zoonavigator\n"
          "\nUse the following connection string:\n"
          f"\n  {connection_string}\n"
          "\nhttp://localhost:8000/\n")
    namespace = cluster_manager.get_operator_namespace_name()
    deployment_name = _get_resource_name('zoonavigator')
    subprocess.check_call(f'kubectl -n {namespace} port-forward deployment/{deployment_name} 8000', shell=True)


def start_solrcloud_port_forward(suffix='sc-0'):
    namespace = cluster_manager.get_operator_namespace_name()
    deployment_name = _get_resource_name(suffix)
    subprocess.check_call(f'kubectl -n {namespace} port-forward deployment/{deployment_name} 8983', shell=True)


def get_internal_http_endpoint():
    solrcloud_host_name = _config_get('sc-main-host-name', required=True)
    namespace = cluster_manager.get_operator_namespace_name()
    return f'http://{solrcloud_host_name}.{namespace}.svc.cluster.local:8983/solr'


def solr_curl(path, required=False, debug=False, max_retries=15):
    deployment_name = _get_resource_name(_get_sc_suffixes()[0])
    if debug:
        kubectl.check_call(f'exec deployment-pod::{deployment_name} -- curl \'localhost:8983/solr{path}\'',
                           use_first_pod=True)
    else:
        exitcode, output = kubectl.getstatusoutput(f'exec deployment-pod::{deployment_name} -- curl -s -f \'localhost:8983/solr{path}\'',
                           use_first_pod=True)
        if exitcode == 0:
            return output
        elif required:
            if max_retries > 0:
                logs.info(f'Failed to run solr curl: localhost:8983/solr{path} - retring in 30 seconds')
                time.sleep(30)
                solr_curl(path, required=required, debug=debug, max_retries=max_retries-1)
            logs.critical(output)
            raise Exception(f'Failed to run solr curl: localhost:8983/solr{path}')
        else:
            logs.warning(output)
            return False


def initialize(interactive=False, dry_run=False):
    if cluster_manager.get_provider_id() == 'minikube':
        config_manager.set('container-spec-overrides', '{"resources":{"limits":{"memory":"1Gi"}}}',
            configmap_name='ckan-cloud-provider-solr-solrcloud-sc-config')

    solr_resources = config_manager.interactive_set(
        {
            'sc-cpu': '1',
            'sc-mem': '1Gi',
            'zk-cpu': '0.2',
            'zk-mem': '200Mi',
            'zn-cpu': '0.01',
            'zn-mem': '0.01Gi',
            'sc-cpu-limit': '2.5',
            'sc-mem-limit': '8Gi',
            'zk-cpu-limit': '0.5',
            'zk-mem-limit': '200Mi',
            'zn-cpu-limit': '0.5',
            'zn-mem-limit': '0.5Gi',
        },
        secret_name='solr-config',
        interactive=interactive
    )

    zk_host_names = initialize_zookeeper(interactive, dry_run=dry_run)

    _config_set('zk-host-names', yaml.dump(zk_host_names, default_flow_style=False))
    logs.info(f'Initialized zookeeper: {zk_host_names}')

    zoonavigator_deployment_name = _apply_zoonavigator_deployment(dry_run=dry_run)
    logs.info(f'Initialized zoonavigator: {zoonavigator_deployment_name}')

    sc_host_names = initialize_solrcloud(zk_host_names, pause_deployment=False, interactive=interactive, dry_run=dry_run)
    _config_set('sc-host-names', yaml.dump(sc_host_names, default_flow_style=False))
    logs.info(f'Initialized solrcloud: {sc_host_names}')

    solrcloud_host_name = _apply_solrcloud_service(dry_run=dry_run)
    _config_set('sc-main-host-name', solrcloud_host_name)
    logs.info(f'Initialized solrcloud service: {solrcloud_host_name}')

    expected_running = len(sc_host_names) + len(zk_host_names) + 1
    RETRIES = 40 # ~20 minutes
    for retry in range(RETRIES):
        pods = kubectl.get('pods')
        running = len([x for x in pods['items']
                       if x['status']['phase'] == 'Running' and x['metadata']['labels']['app'].startswith(_get_resource_labels(for_deployment=True)['app'])])
        time.sleep(45)
        logs.info('Waiting for SolrCloud to start... %d/%d' % (running, expected_running))
        for x in pods['items']:
            logs.info('  - %-10s | %s: %s' % (x['metadata'].get('labels', {}).get('app'), x['metadata']['name'], x['status']['phase']))

        if running == expected_running:
            break
        assert retry < RETRIES - 1, 'Gave up on waiting for SolrCloud'

    _set_provider()


def initialize_zookeeper(interactive=False, dry_run=False):
    headless_service_name = _apply_zookeeper_headless_service(dry_run=dry_run)
    zk_instances = {suffix: {
        'host_name': suffix,
        'volume_spec': _get_or_create_volume(suffix, disk_size_gb=20, dry_run=dry_run, zone=zone),
    } for zone, suffix in enumerate(_get_zk_suffixes())}
    zk_host_names = [zk['host_name'] for zk in zk_instances.values()]
    zk_configmap_name = _apply_zookeeper_configmap(zk_host_names)
    for zk_suffix, zk in zk_instances.items():
        _apply_zookeeper_deployment(zk_suffix, zk['volume_spec'], zk_configmap_name, headless_service_name, dry_run=dry_run)
    namespace = cluster_manager.get_operator_namespace_name()
    return [f'{h}.{headless_service_name}.{namespace}.svc.cluster.local:2181' for h in zk_host_names]


def initialize_solrcloud(zk_host_names, pause_deployment, interactive=False, dry_run=False):
    sc_logs_configmap_name = _apply_solrcloud_logs_configmap()
    headless_service_name = _apply_solrcloud_headless_service(dry_run=dry_run)
    sc_instances = {suffix: {
        'host_name': suffix,
        'volume_spec': _get_or_create_volume(suffix, disk_size_gb=100, dry_run=dry_run, zone=zone)
    } for zone, suffix in enumerate(_get_sc_suffixes())}
    sc_host_names = [sc['host_name'] for sc in sc_instances.values()]
    sc_configmap_name = _apply_solrcloud_configmap(zk_host_names)
    for sc_suffix, sc in sc_instances.items():
        _apply_solrcloud_deployment(sc_suffix, sc['volume_spec'], sc_configmap_name, sc_logs_configmap_name, headless_service_name,
                                    pause_deployment, dry_run=dry_run)
    return sc_host_names


def _get_zk_suffixes():
    if cluster_manager.get_provider_id() != 'minikube':
        return ['zk-0', 'zk-1', 'zk-2']
    else:
        return ['zk-0']


def _get_sc_suffixes():
    if cluster_manager.get_provider_id() != 'minikube':
        return ['sc-3', 'sc-4', 'sc-5']
    else:
        return ['sc-3']


def _apply_zookeeper_configmap(zk_host_names):
    zk_configmap_suffix = 'zk-config'
    _config_set(
        values={
            'ZK_REPLICAS': str(len(zk_host_names)),
            'ZK_ENSEMBLE': ';'.join(zk_host_names),
            'ZK_HEAP_SIZE': '2G',
            'ZK_TICK_TIME': '2000',
            'ZK_INIT_LIMIT': '10',
            'ZK_SYNC_LIMIT': '2000',
            'ZK_MAX_CLIENT_CNXNS': '60',
            'ZK_SNAP_RETAIN_COUNT': '3',
            'ZK_PURGE_INTERVAL': '1',
            'ZK_CLIENT_PORT': '2181',
            'ZK_SERVER_PORT': '2888',
            'ZK_ELECTION_PORT': '3888',
            'ZK_LOG_LEVEL': 'WARN',
        },
        suffix=zk_configmap_suffix
    )
    return _get_resource_name(suffix=zk_configmap_suffix)


def _apply_solrcloud_configmap(zk_host_names):
    sc_configmap_suffix = 'sc-config'
    _config_set(
        values={
            'ZK_HOST': ','.join(zk_host_names),
            'SOLR_HOME': '/data/solr',
            'SOLR_OPTS': '-Dlog4j.configuration=file:///logconfig/log4j.properties -Ddisable.configEdit=true',
        },
        suffix=sc_configmap_suffix
    )
    return _get_resource_name(suffix=sc_configmap_suffix)


def _apply_solrcloud_logs_configmap():
    configmap_suffix = 'sc-logs-config'
    _config_set(
        values={
            'log4j.properties': LOG4J_PROPERTIES,
        },
        suffix=configmap_suffix
    )
    return _get_resource_name(suffix=configmap_suffix)


def _get_volume_pod_scheduling(volume_spec, app_in):
    node_selector = volume_spec.pop('nodeSelector', None)
    return {
        **({'nodeSelector': node_selector} if node_selector else {}),
        'affinity': {
            'podAntiAffinity': {
                'requiredDuringSchedulingIgnoredDuringExecution': [
                    {
                        'labelSelector': {'matchExpressions': [
                            {'key': 'app', 'operator': 'In', 'values': [app_in]}
                        ]},
                        'topologyKey': 'kubernetes.io/hostname'
                    }
                ]
            }
        }
    }


def _apply_zookeeper_deployment(suffix, volume_spec, zookeeper_configmap_name, headless_service_name, dry_run=False):
    cpu_req = config_manager.get('zk-cpu', secret_name='solr-config')
    mem_req = config_manager.get('zk-mem', secret_name='solr-config')
    cpu_lim = config_manager.get('zk-cpu-limit', secret_name='solr-config')
    mem_lim = config_manager.get('zk-mem-limit', secret_name='solr-config')
    kubectl.apply(kubectl.get_deployment(
        _get_resource_name(suffix),
        _get_resource_labels(for_deployment=True, suffix='zk'),
        {
            'replicas': 1,
            'revisionHistoryLimit': 2,
            'strategy': {'type': 'Recreate', },
            'selector': {
                'matchLabels': _get_resource_labels(for_deployment=True, suffix='zk'),
            },
            'template': {
                'metadata': {
                    'labels': _get_resource_labels(for_deployment=True, suffix='zk'),
                    'annotations': _get_resource_annotations()
                },
                'spec': {
                    'hostname': suffix,
                    'subdomain': headless_service_name,
                    **_get_volume_pod_scheduling(
                        volume_spec,
                        _get_resource_labels(for_deployment=True, suffix='zk')['app']
                    ),
                    'containers': [
                        {
                            'name': 'zk',
                            'command': ['sh', '-c', 'zkGenConfig.sh && zkServer.sh start-foreground'],
                            'envFrom': [{'configMapRef': {'name': zookeeper_configmap_name}}],
                            'env': [
                                {'name': 'SOLR_HOST', 'valueFrom': {'fieldRef': {'apiVersion': 'v1', 'fieldPath': 'status.podIP'}}}
                            ],
                            'image': 'gcr.io/google_samples/k8szk:v3',
                            'livenessProbe': {
                                'exec': {'command': ['zkOk.sh']},
                                'failureThreshold': 3, 'initialDelaySeconds': 15, 'periodSeconds': 10,
                                'successThreshold': 1, 'timeoutSeconds': 5
                            },
                            'ports': [
                                {'containerPort': 2181, 'name': 'client', 'protocol': 'TCP'},
                                {'containerPort': 2888, 'name': 'server', 'protocol': 'TCP'},
                                {'containerPort': 3888, 'name': 'leader-election', 'protocol': 'TCP'}
                            ],
                            'readinessProbe': {
                                'exec': {'command': ['zkOk.sh']},
                                'failureThreshold': 3, 'initialDelaySeconds': 15, 'periodSeconds': 10,
                                'successThreshold': 1, 'timeoutSeconds': 5
                            },
                            'resources': {'requests': {'cpu': cpu_req, 'memory': mem_req}, 'limits': {'cpu': cpu_lim, 'memory': mem_lim}},
                            'volumeMounts': [
                                {'mountPath': '/var/lib/zookeeper', 'name': 'datadir'},
                            ],
                        }
                    ],
                    'volumes': [
                        dict(volume_spec, name='datadir')
                    ]
                }
            }
        },
        with_timestamp=False
    ), dry_run=dry_run)


def _apply_zoonavigator_deployment(dry_run=False):
    cpu_req = config_manager.get('zn-cpu', secret_name='solr-config')
    mem_req = config_manager.get('zn-mem', secret_name='solr-config')
    cpu_lim = config_manager.get('zn-cpu-limit', secret_name='solr-config')
    mem_lim = config_manager.get('zn-mem-limit', secret_name='solr-config')

    suffix = 'zoonavigator'
    deployment_name = _get_resource_name(suffix)
    kubectl.apply(kubectl.get_deployment(
        deployment_name,
        _get_resource_labels(for_deployment=True, suffix=suffix),
        {
            'replicas': 1,
            'revisionHistoryLimit': 2,
            'selector': {
                'matchLabels': _get_resource_labels(for_deployment=True, suffix=suffix),
            },
            'template': {
                'metadata': {
                    'labels': _get_resource_labels(for_deployment=True, suffix=suffix),
                    'annotations': _get_resource_annotations()
                },
                'spec': {
                    'containers': [
                        {
                            'env': [
                                {'name': 'API_HOST', 'value': 'localhost'},
                                {'name': 'API_PORT', 'value': '9000'},
                                {'name': 'WEB_HTTP_PORT', 'value': '8000'}
                            ],
                            'image': 'elkozmon/zoonavigator-web:0.5.0',
                            'name': 'zoonavigator-web',
                            'ports': [
                                {'containerPort': 8000, 'name': '8000tcp02', 'protocol': 'TCP'}
                            ],
                            'resources': {}
                        }, {
                            'env': [
                                {'name': 'API_HTTP_PORT', 'value': '9000'}
                            ],
                            'image': 'elkozmon/zoonavigator-api:0.5.0',
                            'name': 'zoonavigator-api',
                            'resources': {'requests': {'cpu': cpu_req, 'memory': mem_req}, 'limits': {'memory': mem_lim, 'cpu': cpu_lim}},
                        }
                    ]
                }
            }
        }
    ), dry_run=dry_run)
    return deployment_name


def _apply_solrcloud_deployment(suffix, volume_spec, configmap_name, log_configmap_name, headless_service_name, pause_deployment, dry_run=False):
    cpu_req = config_manager.get('sc-cpu', secret_name='solr-config')
    mem_req = config_manager.get('sc-mem', secret_name='solr-config')
    cpu_lim = config_manager.get('sc-cpu-limit', secret_name='solr-config')
    mem_lim = config_manager.get('sc-mem-limit', secret_name='solr-config')

    namespace = cluster_manager.get_operator_namespace_name()
    container_spec_overrides = config_manager.get('container-spec-overrides', configmap_name='ckan-cloud-provider-solr-solrcloud-sc-config',
                                                  required=False, default=None)
    resources = {'requests': {'cpu': cpu_req, 'memory': mem_req}, 'limits': {'cpu': cpu_lim, 'memory': mem_lim}} if not container_spec_overrides else {}
    kubectl.apply(kubectl.get_deployment(
        _get_resource_name(suffix),
        _get_resource_labels(for_deployment=True, suffix='sc'),
        {
            'replicas': 1,
            'revisionHistoryLimit': 2,
            'strategy': {'type': 'Recreate', },
            'selector': {
                'matchLabels': _get_resource_labels(for_deployment=True, suffix='sc'),
            },
            'template': {
                'metadata': {
                    'labels': _get_resource_labels(for_deployment=True, suffix='sc'),
                    'annotations': _get_resource_annotations()
                },
                'spec': {
                    'hostname': suffix,
                    'subdomain': headless_service_name,
                    **_get_volume_pod_scheduling(
                        volume_spec,
                        _get_resource_labels(for_deployment=True, suffix='sc')['app']
                    ),
                    'initContainers': [
                        {
                            'name': 'init',
                            'image': 'alpine',
                            'command': [
                                "sh", "-c",
                                f"""
                                    if [ -e /data/solr/solr.xml ]; then
                                        echo /data/solr/solr.xml already exists, will not recreate
                                    else
                                        echo creating /data/solr/solr.xml &&\
                                        mkdir -p /data/solr &&\
                                        echo \'{SOLR_CONFIG_XML}\' > /data/solr/solr.xml
                                    fi &&\
                                    echo Setting permissions to solr user/group 8983:8983 on /data/solr &&\
                                    chown -R 8983:8983 /data/solr &&\
                                    echo init completed successfully
                                """
                            ],
                            'securityContext': {
                                'runAsUser': 0
                            },
                            'volumeMounts': [
                                {'mountPath': '/data', 'name': 'datadir'},
                            ]
                        }
                    ],
                    'containers': [
                        {
                            'name': 'sc',
                            'envFrom': [{'configMapRef': {'name': configmap_name}}],
                            'env': [
                                {'name': 'SOLR_HOST', 'value': f'{suffix}.{headless_service_name}.{namespace}.svc.cluster.local'}
                            ],
                            **({
                                'command': ['sh', '-c', 'sleep 86400']
                            } if pause_deployment else {
                                'livenessProbe': {
                                    'exec': {'command': ['/opt/solr/bin/solr', 'status']},
                                    'failureThreshold': 3, 'initialDelaySeconds': 15, 'periodSeconds': 10,
                                    'successThreshold': 1, 'timeoutSeconds': 5
                                },
                                'readinessProbe': {
                                    'exec': {'command': ['/opt/solr/bin/solr', 'status']},
                                    'failureThreshold': 3, 'initialDelaySeconds': 15, 'periodSeconds': 10,
                                    'successThreshold': 1, 'timeoutSeconds': 5
                                },
                            }),
                            'image': 'solr:5.5.5',
                            'ports': [
                                {'containerPort': 8983, 'name': 'solr', 'protocol': 'TCP'},
                                {'containerPort': 7983, 'name': 'stop', 'protocol': 'TCP'},
                                {'containerPort': 18983, 'name': 'rmi', 'protocol': 'TCP'}
                            ],
                            'volumeMounts': [
                                {'mountPath': '/data', 'name': 'datadir'},
                                {'mountPath': '/logconfig', 'name': 'logconfig'}
                            ],
                            **({'resources': resources} if resources else {}),
                            **(json.loads(container_spec_overrides) if container_spec_overrides else {})
                        }
                    ],
                    'volumes': [
                        {'configMap': {'defaultMode': 420, 'name': log_configmap_name}, 'name': 'logconfig'},
                        dict(volume_spec, name='datadir')
                    ]
                }
            }
        },
        with_timestamp=False
    ), dry_run=dry_run)


def _apply_zookeeper_headless_service(dry_run=False):
    headless_service_name = _get_resource_name('zk-headless')
    kubectl.apply(kubectl.get_resource(
        'v1', 'Service',
        headless_service_name,
        _get_resource_labels(suffix='zk-headless'),
        spec={
            'clusterIP': 'None',
            'ports': [
                {'name': 'client', 'port': 2181, 'protocol': 'TCP', 'targetPort': 2181},
                {'name': 'server', 'port': 2888, 'protocol': 'TCP', 'targetPort': 2888},
                {'name': 'leader-election', 'port': 3888, 'protocol': 'TCP', 'targetPort': 3888}
            ],
            'selector': {
                'app': _get_resource_labels(for_deployment=True, suffix='zk')['app']
            }
        }
    ), dry_run=dry_run)
    return headless_service_name


def _apply_solrcloud_headless_service(dry_run=False):
    headless_service_name = _get_resource_name('sc-headless')
    kubectl.apply(kubectl.get_resource(
        'v1', 'Service',
        headless_service_name,
        _get_resource_labels(suffix='sc-headless'),
        spec={
            'clusterIP': 'None',
            'ports': [
                {'name': 'solr', 'port': 8983, 'protocol': 'TCP', 'targetPort': 8983},
                {'name': 'stop', 'port': 7983, 'protocol': 'TCP', 'targetPort': 7983},
                {'name': 'rmi', 'port': 18983, 'protocol': 'TCP', 'targetPort': 18983}
            ],
            'selector': {
                'app': _get_resource_labels(for_deployment=True, suffix='sc')['app']
            }
        }
    ), dry_run=dry_run)
    return headless_service_name


def _apply_solrcloud_service(dry_run=False):
    service_name = _get_resource_name('sc')
    kubectl.apply(kubectl.get_resource(
        'v1', 'Service',
        service_name,
        _get_resource_labels(suffix='sc'),
        spec={
            'ports': [
                {'name': 'solr', 'port': 8983, 'protocol': 'TCP', 'targetPort': 8983},
            ],
            'selector': {
                'app': _get_resource_labels(for_deployment=True, suffix='sc')['app']
            }
        }
    ), dry_run=dry_run)
    return service_name


def _get_or_create_volume(suffix, disk_size_gb, dry_run=False, zone=0):
    volume_spec_config_key = f'volume-spec-{suffix}'
    volume_spec = _config_get(volume_spec_config_key, required=False)
    if volume_spec:
        volume_spec = yaml.load(volume_spec)
    else:
        assert not dry_run, 'creating a new volume is not supported for dry_run'
        from ckan_cloud_operator.providers.cluster import manager as cluster_manager
        volume_spec = cluster_manager.create_volume(disk_size_gb, _get_resource_labels(suffix=suffix), zone=zone)
        _config_set(volume_spec_config_key, yaml.dump(volume_spec, default_flow_style=False))
    if dry_run:
        print(yaml.dump(volume_spec, default_flow_style=False))
    return volume_spec

import sys
import json
from ckan_cloud_operator.DeisCkanInstance import DeisCkanInstance


HELP = """
Usage: ckan-cloud-operator <COMMAND> [ARGUMENTS..]

Available commands:

install-crds
  Install ckan-cloud-operator custom resource definitions

deis-instance <SUBCOMMAND>
  Manage Deis CKAN instance resources
  
  Available subcommands:
  
    envvars-gcloud-import <PATH_TO_INSTANCE_ENV_YAML> <IMAGE> <SOLR_CONFIG> <GCLOUD_DB_URL> <GCLOUD_DATASTORE_URL> <NEW_INSTANCE_ID>
      Import and deploy an instance
  
    update <INSTANCE_ID> [OVERRIDE_SPEC_JSON]
      Update an instance to the latest resource spec, optionally applying the given json override to the resource spec
  
    ckan-paster <INSTANCE_ID> [PASTER_ARGUMENTS..]
      Run CKAN Paster commands, run without PASTER_ARGUMENTS to get the list of available commands from the CKAN instance.
      Examples:
        ckan-cloud-operator deis-instance ckan-paster <INSTANCE_ID> search-index rebuild
        ckan-cloud-operator deis-instance ckan-paster <INSTANCE_ID> sysadmin add admin name=admin email=admin@ckan
    
    port-forward <INSTANCE_ID> [PORT:5000]
      Start a port-forward to the CKAN instance pod
  
    exec <INSTANCE_ID> [KUBECTL_EXEC_ARGS..]
      Run kubectl exec on the CKAN instance pod
"""


def great_success():
    print('Great Success!')
    exit(0)


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help']:
        print(HELP)
        exit(1)
    elif sys.argv[1] == 'install-crds':
        DeisCkanInstance.install_crd()
        great_success()
    elif sys.argv[1] == 'deis-instance':
        if sys.argv[2] == 'envvars-gcloud-import':
            DeisCkanInstance.envvars_gcloud_import(*sys.argv[3:]).update()
            great_success()
        elif sys.argv[2] == 'update':
            override_spec = json.loads(sys.argv[4]) if len(sys.argv) > 4 else None
            DeisCkanInstance(sys.argv[3], override_spec=override_spec).update()
            great_success()
        elif sys.argv[2] == 'ckan-paster':
            DeisCkanInstance(sys.argv[3]).run_ckan_paster(*sys.argv[4:])
        elif sys.argv[2] == 'port-forward':
            DeisCkanInstance(sys.argv[3]).port_forward(*sys.argv[4:])
        elif sys.argv[2] == 'exec':
            DeisCkanInstance(sys.argv[3]).exec(*sys.argv[4:])
        else:
            raise NotImplementedError(f'Invalid deis-instance subcommand: {sys.argv[2:]}')
    else:
        raise NotImplementedError(f'Invalid command: {sys.argv[1:]}')

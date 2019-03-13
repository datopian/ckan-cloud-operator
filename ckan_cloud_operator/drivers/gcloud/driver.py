import yaml
import subprocess
import tempfile
import traceback
import os
import time


def activate_auth(project, compute_zone, service_account_email, service_account_json):
    """Authenticate with gcloud"""
    args = [project, compute_zone, service_account_email, service_account_json]
    assert all(args), f'missing gcloud auth details: {args}'
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        f.write(service_account_json.encode())
    try:
        check_call(
            project, compute_zone,
            f'auth activate-service-account {service_account_email} --key-file={f.name}'
            ' && '
            f'gcloud --project={project} config set compute/zone {compute_zone}'
        )
    except Exception:
        traceback.print_exc()
    os.unlink(f.name)


def check_output(project, compute_zone, cmd, gsutil=False):
    bin = 'gsutil' if gsutil else f'CLOUDSDK_COMPUTE_ZONE={compute_zone} gcloud --project={project}'
    return subprocess.check_output(f'{bin} {cmd}', shell=True)


def run(project, compute_zone, cmd, gsutil=False, **kwargs):
    bin = 'gsutil' if gsutil else f'CLOUDSDK_COMPUTE_ZONE={compute_zone} gcloud --project={project}'
    return subprocess.run(f'{bin} {cmd}', shell=True, **kwargs)


def call(project, compute_zone, cmd, gsutil=False, **kwargs):
    bin = 'gsutil' if gsutil else f'CLOUDSDK_COMPUTE_ZONE={compute_zone} gcloud --project={project}'
    return subprocess.call(f'{bin} {cmd}', shell=True, **kwargs)


def check_call(project, compute_zone, cmd, gsutil=False):
    bin = 'gsutil' if gsutil else f'CLOUDSDK_COMPUTE_ZONE={compute_zone} gcloud --project={project}'
    return subprocess.check_call(f'{bin} {cmd}', shell=True)


def getstatusoutput(project, compute_zone, cmd, gsutil=False):
    bin = 'gsutil' if gsutil else f'CLOUDSDK_COMPUTE_ZONE={compute_zone} gcloud --project={project}'
    return subprocess.getstatusoutput(f'{bin} {cmd}')


def _set_gcloud_storage_sql_permissions(project, compute_zone, sql_instance_name, import_url):
    print('setting permissions to cloud storage for import to sql')
    gcloud_sql_instance = yaml.load(check_output(
        project, compute_zone,
        f'sql instances describe {sql_instance_name}',
    ))
    gcloud_sql_service_account_email = gcloud_sql_instance['serviceAccountEmailAddress']
    check_call(
        project, compute_zone,
        f'acl ch -u {gcloud_sql_service_account_email}:R {import_url}',
        gsutil=True
    )

def _import_gcloud_sql_db(project, compute_zone, sql_instance_name, import_url, db_name, import_user):
    print(f'Importing Gcloud SQL from: {import_url}')
    _set_gcloud_storage_sql_permissions(project, compute_zone, sql_instance_name, import_url)
    while True:
        proc = run(
            project, compute_zone,
            f'--quiet sql import sql --async {sql_instance_name} {import_url} --database={db_name} --user={import_user} ',
            capture_output=True
        )
        error = proc.stderr.decode()
        print(error)
        if 'HTTPError 409:' in error:
            print('Waiting for other operation to complete...')
            time.sleep(60)
            continue
        break
    output = proc.stdout.decode()
    if proc.returncode == 0:
        print(output)
        operation_id = output.strip().split('/')[-1]
        print(f'Waiting for sql import operation {operation_id} to complete...')
        while True:
            time.sleep(5)
            operation = None
            try:
                operation = yaml.load(check_output(project, compute_zone, f'sql operations describe {operation_id}'))
                print(operation['status'])
                if operation['status'] == 'DONE':
                    if operation.get('error'):
                        print(yaml.dump(operation['error'], default_flow_style=False))
                        raise Exception('sql import operation failed')
                    else:
                        print('operation completed successfully')
                        print(operation)
                        break
            except Exception:
                print(operation)
                raise
    else:
        print(f'returncode={proc.returncode}')
        print(output)
        raise Exception(f'failed to import: {import_url} --> {db_name}   ({import_user})')

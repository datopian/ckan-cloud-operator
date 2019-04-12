import subprocess
import json

from ckan_cloud_operator import logs


def get_zone_id(auth_email, auth_key, zone_name):
    data = curl(auth_email, auth_key, 'zones')
    zones = [zone['id'] for zone in data['result'] if zone['name'] == zone_name]
    return zones[0] if len(zones) > 0 else None


def get_zone_rate_limits(auth_email, auth_key, zone_name):
    zone_id = get_zone_id(auth_email, auth_key, zone_name)
    return curl(auth_email, auth_key, f'zones/{zone_id}/rate_limits?page=1&per_page=1000')


def get_record_id(auth_email, auth_key, zone_id, record_name):
    data = curl(auth_email, auth_key, f'zones/{zone_id}/dns_records?name={record_name}')
    records = [record['id'] for record in data['result'] if record['name'] == record_name]
    return records[0] if len(records) > 0 else None


def is_ip(target_ip):
    return all([c in '0123456789.' for c in target_ip.strip()])


def update_a_record(auth_email, auth_key, zone_name, record_name, target_ip):
    zone_id = get_zone_id(auth_email, auth_key, zone_name)
    assert zone_id is not None, f'Invalid zone name: {zone_name}'
    record_id = get_record_id(auth_email, auth_key, zone_id, record_name)

    cf_record = {'type': 'A' if is_ip(target_ip) else 'CNAME',
                 'name': record_name, 'content': target_ip, 'ttl': 120, 'proxied': False}

    if record_id:
        print(f'Updating existing record {record_name}')
        data = curl(auth_email, auth_key, f'zones/{zone_id}/dns_records/{record_id}', cf_record, 'PUT')
    else:
        print(f'Creating new record: {record_name}')
        data = curl(auth_email, auth_key, f'zones/{zone_id}/dns_records', cf_record, 'POST')
    assert data.get('success')


def curl(auth_email, auth_key, urlpart, data=None, method='GET'):
    logs.info(f'Running Cloudflare curl: {urlpart} {data} {method}')
    logs.debug(f'{auth_email} / {auth_key}')
    cmd = ['curl', '-s', '-X', method, f'https://api.cloudflare.com/client/v4/{urlpart}']
    cmd += [
        '-H', f'X-Auth-Email: {auth_email}',
        '-H', f'X-Auth-Key: {auth_key}',
        '-H', 'Content-Type: application/json'
    ]
    if data:
        cmd += ['--data', json.dumps(data)]
    logs.debug(*cmd)
    output = subprocess.check_output(cmd)
    try:
        return json.loads(output)
    except Exception:
        logs.critical(f'Got invalid data from cloudflare curl: {output}')
        raise

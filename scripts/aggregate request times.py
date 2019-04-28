import os
import datetime
import collections
import yaml

import tabulator
from dataflows import Flow, printer, dump_to_path

from ckan_cloud_operator.drivers.jenkins import driver as jenkins_driver
from ckan_cloud_operator.providers.ckan import manager as ckan_manager
from ckan_cloud_operator import logs


# https://jenkins.example.com/job/get%20instance%20request%20time/api/json
REQUEST_TIMES_API_URL = os.environ.get('REQUEST_TIMES_API_URL')


def process_build(build, jenkins_user_token):
    build_url = '{}api/json'.format(build['url'])
    build = jenkins_driver.curl(*jenkins_user_token, build_url)
    try:
        build_timestamp = datetime.datetime.utcfromtimestamp(build["timestamp"]/1000)
    except Exception:
        build_timestamp = None
    if build_timestamp:
        output_url = '{}artifact/output.csv'.format(build['url'])
        try:
            with tabulator.Stream(output_url, headers=1, http_session=jenkins_driver.get_session(*jenkins_user_token)) as stream:
                for row in stream.iter(keyed=True):
                    row['timestamp'] = build_timestamp
                    yield row
        except tabulator.exceptions.HTTPError:
            print('failed to get build artifact', build)
    else:
        print('failed to get build timestamp', build)


def get_builds(request_times_api_url, stats):
    jenkins_user_token = ckan_manager.get_jenkins_token('ckan-cloud-operator-jenkins-creds')
    builds = jenkins_driver.curl(*jenkins_user_token, request_times_api_url)['builds']
    for build in builds:
        stats['builds'] += 1
        for row in process_build(build, jenkins_user_token):
            stats['rows'] += 1
            yield row
        # if stats['builds'] > 2:
        #     break


def aggregate_instance_stats(instance_stats, metadata):

    def _aggregate_instance_stats(row):
        instance_id = row['instance_id']
        metadata.setdefault('all-instance-ids', set()).add(instance_id)
        # pod_name = row['pod_name']
        # test_url = row['test_url']
        # measurement_num = row['measurement_num']
        status_code = int(row['status_code'])
        minutes = float(row['minutes'])
        seconds = float(row['seconds'])
        # comments = row['comments']
        timestamp = row['timestamp']
        if not metadata.get(f'{instance_id}-first-timestamp') or metadata[f'{instance_id}-first-timestamp'] > timestamp:
            metadata[f'{instance_id}-first-timestamp'] = timestamp
        if not metadata.get(f'{instance_id}-last-timestamp') or metadata[f'{instance_id}-last-timestamp'] < timestamp:
            metadata[f'{instance_id}-last-timestamp'] = timestamp
        instance_stats[f'{instance_id}-total-requests'] += 1
        if status_code != 200:
            instance_stats[f'{instance_id}-invalid-status-{status_code}'] += 1
        instance_stats[f'{instance_id}-total-seconds'] += minutes*60 + seconds
        if instance_stats[f'{instance_id}-total-requests'] <= 30:
            instance_stats[f'{instance_id}-first-30-requests-seconds'] += minutes * 60 + seconds
        if instance_stats[f'{instance_id}-total-requests'] <= 90:
            instance_stats[f'{instance_id}-first-90-requests-seconds'] += minutes * 60 + seconds
        if minutes > 0 or seconds > 10:
            instance_stats[f'{instance_id}-requests-exceed-10-seconds'] += 1
        elif seconds > 5:
            instance_stats[f'{instance_id}-requests-exceed-5-seconds'] += 1
        elif seconds > 3:
            instance_stats[f'{instance_id}-requests-exceed-3-seconds'] += 1

    return _aggregate_instance_stats


def get_instance_stats_data(instance_stats, metadata):
    keys = set()
    instances = {}
    for instance_id in metadata['all-instance-ids']:
        total_requests = instance_stats[f'{instance_id}-total-requests']
        total_seconds = instance_stats[f'{instance_id}-total-seconds']
        first_30_requests_seconds = instance_stats[f'{instance_id}-first-30-requests-seconds']
        first_90_requests_seconds = instance_stats[f'{instance_id}-first-90-requests-seconds']
        avg_total = total_seconds / total_requests
        avg_first_30_requests = first_30_requests_seconds / 30 if total_requests > 30 else 0
        avg_first_90_requests = first_90_requests_seconds / 90 if total_requests > 90 else 0
        invalid_status_codes = {k.replace(f'{instance_id}-', ''): v for k, v in instance_stats.items() if k.startswith(f'{instance_id}-invalid-status-')}
        invalid_request_times = {k.replace(f'{instance_id}-', ''): v for k, v in instance_stats.items() if k.startswith(f'{instance_id}-requests-exceed-')}
        [keys.add(k) for k in invalid_status_codes]
        [keys.add(k) for k in invalid_request_times]
        first_timestamp = metadata[f'{instance_id}-first-timestamp']
        last_timestamp = metadata[f'{instance_id}-last-timestamp']
        total_seconds = (last_timestamp - first_timestamp).total_seconds()
        instances[instance_id] = {
            'total-requests': total_requests,
            'total-seconds': total_seconds,
            'total-requests-per-second': total_requests / total_seconds,
            'avg_response_seconds': avg_total,
            'avg_first_30_requests': avg_first_30_requests,
            'avg_first_90_requests': avg_first_90_requests,
            **invalid_status_codes,
            **invalid_request_times
        }
    for instance_id, instance in instances.items():
        row = {k: 0 for k in keys}
        row.update(**instance)
        row['instance_id'] = instance_id
        yield row


def main(request_times_api_url):
    metadata = {}
    stats = collections.defaultdict(int)
    instance_stats = collections.defaultdict(int)
    Flow(
        get_builds(request_times_api_url, stats),
        aggregate_instance_stats(instance_stats, metadata),
        dump_to_path('data/aggregate_request_times')
    ).process()
    Flow(
        get_instance_stats_data(instance_stats, metadata),
        dump_to_path('data/aggregate_request_times_stats'),
        printer(num_rows=1)
    ).process()


if __name__ == '__main__':
    main(REQUEST_TIMES_API_URL)

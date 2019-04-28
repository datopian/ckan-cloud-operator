import os
import collections

import httpagentparser
from dataflows import Flow, load, printer, dump_to_path, checkpoint

from ckan_cloud_operator import logs
from ckan_cloud_operator.providers.ckan import manager as ckan_manager


TRAEFIK_READ_LOGS_ARTIFACT_PACKAGE_URL = os.environ.get('TRAEFIK_READ_LOGS_ARTIFACT_PACKAGE_URL')


def aggregate_stats(stats_rows):

    host_stats = {}
    host_metadata = {}
    all_stats_keys = set()
    all_metadata_keys = set()

    def _aggregate_stats(row):
        request_host = row['RequestHost']
        stats = host_stats.setdefault(request_host, collections.defaultdict(int))
        metadata = host_metadata.setdefault(row['RequestHost'], {})
        stats['total-requests'] += 1
        status_code = row['DownstreamStatus']
        stats[f'status-{status_code}'] += 1
        duration_seconds = int(row['Duration'])/1000000000
        if duration_seconds > 10:
            duration_tag = 'more_then_10s'
        elif duration_seconds > 5:
            duration_tag = 'more_then_5s'
        elif duration_seconds > 3:
            duration_tag = 'more_then_3s'
        else:
            duration_tag = None
        if duration_tag:
            stats[f'duration-{duration_tag}'] += 1
        start_time = row['StartUTC']
        if not metadata.get('first-start-time') or metadata['first-start-time'] > start_time:
            metadata['first-start-time'] = start_time
        if not metadata.get('last-start-time') or metadata['last-start-time'] < start_time:
            metadata['last-start-time'] = start_time
        referer = row['request_Referer']
        referer = referer.strip() if referer else None
        if not referer:
            referer_tag = None
        elif referer.startswith(f'https://{request_host}'):
            referer_tag = 'self'
        else:
            referer_tag = 'external'
        if referer_tag:
            stats[f'referer-{referer_tag}'] += 1
        user_agent = row['request_User-Agent']
        try:
            user_agent = httpagentparser.detect(user_agent)
            user_agent_os = user_agent.get('os', {}).get('name')
            user_agent_browser = user_agent.get('browser', {}).get('name')
        except Exception:
            user_agent_os, user_agent_browser = None, None
        if user_agent_os:
            stats[f'ua-os-{user_agent_os}'] += 1
        if user_agent_browser:
            stats[f'ua-browser-{user_agent_browser}'] += 1
        [all_stats_keys.add(k) for k in stats]
        [all_metadata_keys.add(k) for k in metadata]
        return row

    def _process_rows(rows):
        for row in rows:
            yield _aggregate_stats(row)
        for request_host, stats in host_stats.items():
            metadata = host_metadata[request_host]
            row = {k: 0 for k in all_stats_keys}
            row.update({k: None for k in all_metadata_keys})
            row.update(**stats, **metadata)
            row['request_host'] = request_host
            stats_rows.append(row)

    return _process_rows


def main(package_url):
    jenkins_user_token = ckan_manager.get_jenkins_token('ckan-cloud-operator-jenkins-creds')
    package_url = package_url.replace('https://', 'https://{}:{}@'.format(*jenkins_user_token))
    stats_rows = []
    Flow(
        load(package_url),
        aggregate_stats(stats_rows),
        dump_to_path('data/aggregate_access_logs')
    ).process()
    Flow(
        (row for row in stats_rows),
        dump_to_path('data/aggregate_access_logs_stats'),
        printer()
    ).process()


if __name__ == '__main__':
    main(TRAEFIK_READ_LOGS_ARTIFACT_PACKAGE_URL)

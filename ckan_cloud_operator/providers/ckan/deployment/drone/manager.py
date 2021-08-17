import requests
from urllib.parse import urljoin

from ...env import manager as env_manager


class Drone(object):

    def initialize(self, force_prompt=False):
        self.conf = env_manager._read_yaml().get('cicd', {})
        self.server_url = self.conf.get('serverUrl')
        self.api_token = self.conf.get('token')
        self.org = self.conf.get('organization')
        self.repo = self.conf.get('repo')
        if force_prompt or not self.conf:
            self.server_url = input('Please enter Drone Server URL: ')
            self.api_token = input(f'Please enter Drone API Token. See {self. server_url} acount: ')
            self.org = input('Please enter Github organization name: ')
            self.repo = input('Please enter Github repository name: ')
            self.conf['cicd'] = {
                 'serverUrl': self.server_url,
                 'token': self.api_token,
                 'organization': self.org,
                 'repo': self.repo
            }
            env_manager._write_yaml(self.conf)
        self.api_url = urljoin(self.server_url, '/'.join(['api/repos', f'{self.org}/{self.repo}', 'builds/']))
        self.header = {'Authorization': f'Bearer {self.api_token}'}
        print('CCO is configured for Drone ')


    def builds_list(self):
        resp = requests.get(self.api_url, headers=self.header)
        if not _check_for_200(resp):
            return []
        return resp.json()


    def builds_info(self, branch='develop'):
        build_number = self.get_build_number(branch=branch)
        if build_number is None:
            print(f'Build {build_number} not found')
            return None
        url = urljoin(self.api_url, build_number)
        builds_info_resp = requests.get(url, headers=self.header)
        if not _check_for_200(builds_info_resp):
            return {}
        return builds_info_resp.json()


    def builds_logs(self, branch='develop'):
        build_info = self.builds_info(branch=branch)
        if build_info is None:
            return None
        stages = build_info.get('stages', [])
        for stage in stages:
            steps = stage.get('steps', [])
            stage_name = stage.get('name')
            for step in steps:
                step_name = step.get('name')
                print(f'--- Build Stage: {stage_name} | Builds Step: {step_name}')
                url = urljoin(self.api_url, '/'.join([
                    self.build_number,
                    'logs',
                    str(stage.get('number')),
                    str(step.get('number'))])
                )
                log_resp = requests.get(url, headers=self.header)
                log_list = log_resp.json()
                for _log in log_list:
                    print(_log.get('out').rstrip('\n'))
        print(f'Showing logs for "{branch}" Branch')


    def get_build_number(self, branch='develop'):
        for build in self.builds_list():
            if build.get('source') == branch:
                self.build_number = str(build.get('number'))
                return str(build.get('number'))
        print(f'No build found for branch {branch}')
        return None


def _check_for_200(resp):
    if resp.status_code == 200:
        return True
    if resp.status_code == 401:
        print("Seems like you are not authorized")
        print("Please run `cco ckan deployment drone initialize --force-update` and rerun")
        return False
    return False

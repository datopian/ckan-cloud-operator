import requests
from urllib.parse import urljoin

class Drone:

    def __init__(self, server_url, api_token, repo_slug):
        self.server_url = server_url
        self.api_token = api_token
        self.repo_slug = repo_slug
        self.api_url = urljoin(server_url, '/'.join(['api/repos', repo_slug, 'builds']))
        self.header = {'Authorization': f'Bearer {api_token}'}

    def builds_list(self):
        resp = requests.get(self.api_url)
        if resp.status_code != 200:
            print('Something went wrong')
            print(resp)

        return resp.json()


    def builds_info(self):
        pass

    def builds_logs(self):
        pass

    def get_build_number(self):
        for build in self.builds_list():
            print(build)

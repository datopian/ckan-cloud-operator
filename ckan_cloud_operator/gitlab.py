import json
import subprocess
import re
import functools
import traceback


class CkanGitlab(object):

    def __init__(self, ckan_infra):
        self.ckan_infra = ckan_infra

    def initialize(self, project):
        for fname in ['.env', 'Dockerfile', '.gitlab-ci.yml']:
            data = self._get_file(project, fname, required=False)
            if data:
                size_b = len(data)
                assert size_b > 0
                print(f'{project}/{fname}: {size_b} bytes')
            elif fname == '.gitlab-ci.yml':
                print(f'Creating {project}/.gitlab-ci.yml')
                project_id = self._get_project_id(project)
                self._curl(f'projects/{project_id}/repository/files/.gitlab-ci.yml', postjson={
                    'branch': 'master', 'author_email': 'admin@ckan-cloud-operator',
                    'author_name': 'ckan-cloud-operator',
                    'content': self._get_gitlab_ci_yml(), 'commit_message': 'Add .gitlab-ci.yml'
                })
            else:
                print(f'Repository is missing {project}/{fname}')
                exit(1)

    def get_envvars(self, project):
        return self._parse_dotenv(self._get_file(project, '.env'))

    def _get_file(self, project, file, ref='master', required=True):
        try:
            project_id = self._get_project_id(project)
            file = file.replace('/', '%2F')
            return self._curl(f'projects/{project_id}/repository/files/{file}/raw?ref={ref}')
        except Exception:
            if required:
                raise
            else:
                traceback.print_exc()
                return None

    def _curl(self, urlpart, postjson=None):
        gitlab_token = self.ckan_infra.GITLAB_TOKEN_PASSWORD
        if postjson:
            postjson = json.dumps(postjson)
            return subprocess.check_output(
                f'curl -f -s --request POST --header "PRIVATE-TOKEN: {gitlab_token}" '
                f'--header "Content-Type: application/json" --data \'{postjson}\' '
                f'"https://gitlab.com/api/v4/{urlpart}"',
                shell=True
            ).decode()
        else:
            return subprocess.check_output(
                f'curl -f -s --header "PRIVATE-TOKEN: {gitlab_token}" '
                f'"https://gitlab.com/api/v4/{urlpart}"',
                shell=True
            ).decode()

    @functools.lru_cache()
    def _get_project_id(self, project):
        gitlab_project_encoded = project.replace('/', '%2F')
        return json.loads(self._curl(f'projects/{gitlab_project_encoded}'))['id']

    def _parse_dotenv(self, content, overrides=None):
        # https://github.com/joke2k/django-environ/blob/develop/environ/environ.py
        env = {}
        for line in content.splitlines():
            m1 = re.match(r'\A(?:export )?([A-Za-z_0-9]+)=(.*)\Z', line)
            if m1:
                key, val = m1.group(1), m1.group(2)
                m2 = re.match(r"\A'(.*)'\Z", val)
                if m2:
                    val = m2.group(1)
                m3 = re.match(r'\A"(.*)"\Z', val)
                if m3:
                    val = re.sub(r'\\(.)', r'\1', m3.group(1))
                env.setdefault(key, str(val))
        if overrides:
            for key, value in overrides.items():
                env.setdefault(key, value)
        return env

    def _get_gitlab_ci_yml(self):
        return """image: docker:latest

services:
  - docker:dind

before_script:
  - docker login -u "$CI_REGISTRY_USER" -p "$CI_REGISTRY_PASSWORD" $CI_REGISTRY

build-master:
  stage: build
  script:
    - docker build --pull -t "$CI_REGISTRY_IMAGE" .
    - docker push "$CI_REGISTRY_IMAGE"
  only:
    - master

build:
  stage: build
  script:
    - docker build --pull -t "$CI_REGISTRY_IMAGE:$CI_COMMIT_REF_SLUG" .
    - docker push "$CI_REGISTRY_IMAGE:$CI_COMMIT_REF_SLUG"
  except:
    - master"""


import json
import subprocess
import re
import functools
import traceback
import requests


from ckan_cloud_operator import logs


class CkanGitlab(object):

    def initialize(self, project, git_branch='master'):
        project_id = self._get_project_id(project)
        print({k: v for k, v in json.loads(self._curl(
            f'projects/{project_id}',
            postjson={'container_registry_enabled': True},
            method='PUT'
        )).items() if k in ['id', 'path_with_namespace', 'container_registry_enabled']})
        for fname in ['.env', 'Dockerfile', '.gitlab-ci.yml']:
            data = self._get_file(project, fname, ref=git_branch, required=False)
            if fname == 'Dockerfile':
                self._update_dockerfile(project_id, data, git_branch)
            if data:
                size_b = len(data)
                assert size_b > 0
                print(f'{project}/{fname}: {size_b} bytes')
            elif fname == '.gitlab-ci.yml':
                print(f'Creating {project}/.gitlab-ci.yml')
                project_id = self._get_project_id(project)
                self._curl(f'projects/{project_id}/repository/files/.gitlab-ci.yml', postjson={
                    'branch': git_branch, 'author_email': 'admin@ckan-cloud-operator',
                    'author_name': 'ckan-cloud-operator',
                    'content': self._get_gitlab_ci_yml(git_branch=git_branch), 'commit_message': 'Add .gitlab-ci.yml'
                })
            else:
                print(f'Repository is missing {project}/{fname}')

    def is_ready(self, project):
        project_id = self._get_project_id(project)
        project_pipelines = json.loads(self._curl(
            f'projects/{project_id}/pipelines'
        ))
        print(project_pipelines)
        success =  [p for p in project_pipelines if p['status'] == 'success']
        pending =  [p for p in project_pipelines if p['status'] == 'pending']
        failed =  [p for p in project_pipelines if p['status'] == 'failed']
        running =  [p for p in project_pipelines if p['status'] == 'running']
        others = [p for p in project_pipelines if p['status'] not in ['failed', 'success', 'pending', 'running']]
        assert len(others) == 0, f'unknown status: {others}'
        if len(success) > 0 and len(pending) == 0:
            print(f'successful pipelines: {success}')
            print(f'pending pipelines: {pending}')
            print(f'failed pipelines: {failed}')
            print(f'running pipelines: {running}')
            return True
        else:
            return False

    def get_envvars(self, project, git_branch='master'):
        return self._parse_dotenv(self._get_file(project, '.env', ref=git_branch))

    def _get_updated_dockerfile(self, data):
        needs_update = False
        got_upgraded = False
        lines = []
        for line in data.splitlines():
            if 'pip install --upgrade pip' in line:
                got_upgraded = True
            elif not got_upgraded and line.startswith('RUN pip install '):
                logs.warning('please add pip install --upgrade pip manually to the Dockerfile (if needed)')
                # needs_update = True
                # line = 'RUN pip install --upgrade pip==18.1 && pip install {}'.format(line[15:])
            lines.append(line)
        from ckan_cloud_operator.providers.ckan import manager as ckan_manager
        search_replace_needs_update, lines = ckan_manager.gitlab_search_replace(lines)
        if needs_update or search_replace_needs_update:
            return needs_update, search_replace_needs_update, '{}\n'.format('\n'.join(lines))
        else:
            return False, False, None

    def _update_dockerfile(self, project_id, data, git_branch='master'):
        pip_update, gitlab_search_replace_update, updated_data = self._get_updated_dockerfile(data)
        if updated_data:
            commit_messages = []
            if pip_update: commit_messages.append('Add pip install --upgrade pip to Dockerfile')
            if gitlab_search_replace_update: commit_messages.append('replace values for migration')
            self._curl(f'projects/{project_id}/repository/files/Dockerfile', postjson={
                'branch': git_branch, 'author_email': 'admin@ckan-cloud-operator',
                'author_name': 'ckan-cloud-operator',
                'content': updated_data, 'commit_message': ', '.join(commit_messages)
            }, method='PUT')

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

    def _curl(self, urlpart, postjson=None, method='POST', token_name=None, download_filename=None):
        from ckan_cloud_operator.providers.ckan import manager as ckan_manager
        gitlab_token = ckan_manager.gitlab_token(token_name)
        if postjson:
            r = requests.request(
                method,
                f'https://gitlab.com/api/v4/{urlpart}',
                headers={
                    'PRIVATE-TOKEN': gitlab_token
                },
                json=postjson
            )
            assert r.status_code in [200, 201], r.text
            return r.text
        elif download_filename:
            cmd = f'curl -f -s --header "PRIVATE-TOKEN: {gitlab_token}" https://gitlab.com/api/v4/{urlpart} > {download_filename}'
            subprocess.check_call(cmd, shell=True)
        else:
            cmd = ['curl', '-f', '-s',
                   '--header', f'PRIVATE-TOKEN: {gitlab_token}',
                   f'https://gitlab.com/api/v4/{urlpart}']
            return subprocess.check_output(cmd).decode()

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

    def _get_gitlab_ci_yml(self, git_branch='master'):
        return """image: docker:latest

services:
  - docker:dind

before_script:
  - docker login -u "$CI_REGISTRY_USER" -p "$CI_REGISTRY_PASSWORD" $CI_REGISTRY

build-{git_branch}:
  stage: build
  script:
    - docker build --pull -t "$CI_REGISTRY_IMAGE" .
    - docker push "$CI_REGISTRY_IMAGE"
  only:
    - {git_branch}

build:
  stage: build
  script:
    - docker build --pull -t "$CI_REGISTRY_IMAGE:$CI_COMMIT_REF_SLUG" .
    - docker push "$CI_REGISTRY_IMAGE:$CI_COMMIT_REF_SLUG"
  except:
    - {git_branch}""".format(git_branch=git_branch)

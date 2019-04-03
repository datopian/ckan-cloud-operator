import os
from dataflows import Flow, load, printer, checkpoint, dump_to_path, add_field
from ckan_cloud_operator.gitlab import CkanGitlab


def get_gitlab_repo(rows):
    if rows.res.name == 'ckan-cloud-instances':
        for row in rows:
            image = row['image']
            if image.endswith(' (imageFromGitlab)'):
                gitlab_repo = image.replace(' (imageFromGitlab)', '')
            elif image.startswith('registry.gitlab.com/viderum/cloud-'):
                gitlab_repo = image.replace('registry.gitlab.com/', '').split('@')[0]
            else:
                gitlab_repo = None
            yield dict(row, gitlab_repo=gitlab_repo)
    else:
        yield from rows


def parse_dockerfiles():
    gitlab_repos = {}

    def _parse_gitlab_repos(rows):
        if rows.res.name == 'ckan-cloud-instances':
            for row in rows:
                gitlab_repo = row['gitlab_repo']
                if gitlab_repo in gitlab_repos:
                    gitlab_repos[gitlab_repo]['instances'].append(row)
                else:
                    gitlab_repos[gitlab_repo] = {'instances': [row]}
                yield row
        else:
            yield from rows

    def _get_dockerfile_from(dockerfile):
        if dockerfile:
            return [line.replace('FROM ', '') for line in dockerfile.split('\n') if line.startswith('FROM')][0]
        else:
            return None

    def _parse_ckan_extensions(rows):
        if rows.res.name == 'dockerfiles':
            for row in rows:
                row['ckan_exts'] = []
                if row['dockerfile']:
                    for line in row['dockerfile'].split('\n'):
                        if 'https://github.com/' in line and '.git@' in line and '#egg=' in line:
                            ext = line.split('https://github.com/')[1].split('#egg=')[0].replace('.git@', '@')
                            row['ckan_exts'].append(ext)
                            if 'ckanext-s3filestore' in ext:
                                row['ckanext-s3filestore'] = ext
                yield row
        else:
            yield from rows

    def _get_dockerfile_row(gitlab_repo_name, gitlab_repo):
        try:
            dockerfile = CkanGitlab()._get_file(gitlab_repo_name, 'Dockerfile')
        except Exception:
            dockerfile = None
        return {
            'gitlab_repo': gitlab_repo_name,
            'instances': [i['name'] for i in gitlab_repo['instances']],
            'from': _get_dockerfile_from(dockerfile),
            'dockerfile': dockerfile
        }

    def _parse_dockerfiles(package):
        package.pkg.add_resource({'name': 'dockerfiles', 'path': 'dockerfiles.csv', 'schema': {'fields': [
            {'name': 'gitlab_repo', 'type': 'string'},
            {'name': 'instances', 'type': 'array'},
            {'name': 'from', 'type': 'string'},
            {'name': 'dockerfile', 'type': 'string'}
        ]}})
        yield package.pkg
        yield from package
        yield (_get_dockerfile_row(gitlab_repo_name, gitlab_repo) for gitlab_repo_name, gitlab_repo in
               gitlab_repos.items())

    return Flow(
        _parse_gitlab_repos,
        _parse_dockerfiles,
        checkpoint('ckan_images_dockerfiles'),
        add_field('ckan_exts', 'array'),
        add_field('ckanext-s3filestore', 'string'),
        _parse_ckan_extensions,
    )


def main_flow(prefix, operator):
    return Flow(
        load(f'data/{prefix}/resources/datapackage.json', resources=['ckan-cloud-instances']),
        add_field('gitlab_repo', 'string'),
        get_gitlab_repo,
        parse_dockerfiles(),
    )


if __name__ == '__main__':
    prefix = os.environ['DATAPACKAGE_PREFIX']
    operator = os.environ.get('CKAN_CLOUD_OPERATOR_BIN', 'ckan-cloud-operator')
    Flow(
        main_flow(prefix, operator),
        printer(num_rows=1, fields=['name', 'image', 'gitlab_repo', 'from']),
        dump_to_path(f'data/{prefix}/ckan_images')
    ).process()

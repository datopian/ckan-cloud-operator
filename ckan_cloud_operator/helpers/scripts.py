import os
import tempfile
from ruamel import yaml
from ckan_cloud_operator import logs


# Functions to support automation scripts (usually under scripts/ directory)


def check_file_based_approval_code(approve_code, expected_content, delete=True):
    if approve_code:
        approval_filename = f'data/approval_files/{approve_code}'
        assert os.path.isfile(approval_filename), 'invalid approval code'
        with open(approval_filename) as f:
            assert yaml.safe_load(f) == expected_content, 'invalid approval code or expected content was changed'
        if delete:
            os.unlink(approval_filename)
        return True
    else:
        return False


def create_file_based_approval_code(content):
    os.makedirs('data/approval_files', exist_ok=True)
    with tempfile.NamedTemporaryFile('w', prefix='cca', dir='data/approval_files', delete=False) as f:
        logs.yaml_dump(content, f)
        return os.path.relpath(f.name, os.path.join(os.path.curdir, 'data/approval_files'))


def get_env_vars(*args):
    return [os.environ.get(e, '') for e in args]

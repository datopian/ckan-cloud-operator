from setuptools import setup, find_packages
from os import path
from time import time

here = path.abspath(path.dirname(__file__))

if path.exists("VERSION.txt"):
    # this file can be written by CI tools (e.g. Travis)
    with open("VERSION.txt") as version_file:
        version = version_file.read().strip().strip("v")
else:
    version = str(time())

setup(
    name='ckan_cloud_operator',
    version=version,
    description='''CKAN Cloud Kubernetes operator''',
    url='https://github.com/datopian/ckan-cloud-operator',
    author='''Viderum''',
    license='MIT',
    packages=find_packages(exclude=['examples', 'tests', '.tox']),
    install_requires=[
        'httpagentparser',
        'boto3',
        'coverage',
        'psycopg2',
        'pyyaml<5.3,>=5',
        'kubernetes',
        'click',
        'toml',
        # 'dataflows>=0.0.37',
        # 'dataflows-shell>=0.0.8',
        # 'jupyterlab',
        'awscli',
        'urllib3<1.25',
        'ruamel.yaml<1',
        'requests==2.21',
        'python-dateutil<3',
        'botocore',
    ],
    entry_points={
      'console_scripts': [
        'ckan-cloud-operator = ckan_cloud_operator.cli:main',
      ]
    },
)

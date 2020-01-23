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

with open('requirements.in') as requirements_file:
    install_requires = requirements_file.read().strip().split('\n')
    
setup(
    name='ckan_cloud_operator',
    version=version,
    description='''CKAN Cloud Kubernetes operator''',
    url='https://github.com/datopian/ckan-cloud-operator',
    author='''Viderum''',
    license='MIT',
    packages=find_packages(exclude=['examples', 'tests', '.tox']),
    install_requires=install_requires,
    entry_points={
      'console_scripts': [
        'ckan-cloud-operator = ckan_cloud_operator.cli:main',
      ]
    },
)

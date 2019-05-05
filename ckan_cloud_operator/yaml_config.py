import yaml
import datetime


### disable yaml load warnings
# see https://github.com/yaml/pyyaml/wiki/PyYAML-yaml.load(input)-Deprecation

if hasattr(yaml, 'warnings'):
    yaml.warnings({'YAMLLoadWarning': False})


### global fix for yaml handling of datetime formats with compatibility for kubectl


datetime_format = '%Y-%m-%dT%H:%M:%SZ'


def datetime_representer(dumper, data):
    return dumper.represent_data(data.strftime(datetime_format))


def datetime_constructor(loader, node):
    value = loader.construct_scalar(node)
    return datetime.datetime.strptime(value, datetime_format)


yaml.add_representer(datetime.datetime, datetime_representer)
yaml.add_constructor(u'!datetime', datetime_constructor)

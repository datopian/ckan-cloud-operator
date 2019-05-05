from logging import CRITICAL, ERROR, WARNING, INFO, DEBUG, getLevelName
import datetime
from distutils.util import strtobool
import os
from ruamel import yaml
from ruamel.yaml.serializer import Serializer as ruamelSerializer
from ruamel.yaml.emitter import Emitter as ruamelEmitter
import sys


def info(*args, **kwargs):
    log(INFO, *args, **kwargs)


def debug(*args, **kwargs):
    log(DEBUG, *args, **kwargs)


def debug_verbose(*args, **kwargs):
    if strtobool(os.environ.get('CKAN_CLOUD_OPERATOR_DEBUG_VERBOSE', 'n')):
        debug(yaml.dump([args, kwargs], default_flow_style=False))


def warning(*args, **kwargs):
    log(WARNING, *args, **kwargs)


def error(*args, **kwargs):
    log(ERROR, *args, **kwargs)


def critical(*args, **kwargs):
    log(CRITICAL, *args, **kwargs)


def log(level, *args, **kwargs):
    if level == DEBUG and not strtobool(os.environ.get('CKAN_CLOUD_OPERATOR_DEBUG', 'n')): return
    msg = datetime.datetime.now().strftime('%Y-%m-%d %H:%M') + ' ' + getLevelName(level) + ' '
    if len(kwargs) > 0:
        msg += '(' + ','.join([f'{k}="{v}"' for k, v in kwargs.items()]) + ') '
    msg += ' '.join(args)
    print(msg)


def important_log(level, *args, **kwargs):
    if level == DEBUG and not strtobool(os.environ.get('CKAN_CLOUD_OPERATOR_DEBUG', 'n')): return
    header = datetime.datetime.now().strftime('%Y-%m-%d %H:%M') + ' ' + getLevelName(level)
    print(f'\n{header}')
    if len(kwargs) > 0:
        metadata = '(' + ','.join([f'{k}="{v}"' for k, v in kwargs.items()]) + ')'
        print(metadata)
    print('\n')
    if len(args) > 0:
        title = args[0]
        print(f'== {title}')
        if len(args) > 1:
            msg = ' '.join(args[1:])
            print(msg)


def exit_great_success(quiet=False):
    if not quiet:
        info('Great Success!')
    exit(0)


def exit_catastrophic_failure(exitcode=1, quiet=False):
    if not quiet:
        critical('Catastrophic Failure!')
    exit(exitcode)


def debug_yaml_dump(*args, **kwargs):
    if len(args) == 1:
        debug(yaml.dump(args[0], Dumper=YamlSafeDumper, default_flow_style=False), **kwargs)
    else:
        debug(yaml.dump(args, Dumper=YamlSafeDumper, default_flow_style=False), **kwargs)


def print_yaml_dump(data, exit_success=False):
    yaml.dump(data, sys.stdout, Dumper=YamlSafeDumper, default_flow_style=False)
    if exit_success:
        exit_great_success(quiet=True)


def yaml_dump(data, *args, **kwargs):
    return yaml.dump(data, *args, Dumper=YamlSafeDumper, default_flow_style=False, **kwargs)


class YamlSafeDumper(yaml.SafeDumper):

    def ignore_aliases(self, data):
        return True

    def represent_undefined(self, data):
        return None

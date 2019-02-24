from logging import CRITICAL, ERROR, WARNING, INFO, DEBUG, getLevelName
import datetime
from distutils.util import strtobool
import os
import yaml


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
        debug(yaml.dump(args[0], default_flow_style=False), **kwargs)
    else:
        debug(yaml.dump(args, default_flow_style=False), **kwargs)


def print_yaml_dump(data):
    print(yaml.dump(data, default_flow_style=False))

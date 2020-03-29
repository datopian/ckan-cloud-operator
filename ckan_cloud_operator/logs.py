from logging import CRITICAL, ERROR, WARNING, INFO, DEBUG, getLevelName
import datetime
from distutils.util import strtobool
import os
from ruamel import yaml
from ruamel.yaml.serializer import Serializer as ruamelSerializer
from ruamel.yaml.emitter import Emitter as ruamelEmitter
import sys
import subprocess

CKAN_CLOUD_OPERATOR_DEBUG = strtobool(os.environ.get('CKAN_CLOUD_OPERATOR_DEBUG', 'n'))
CKAN_CLOUD_OPERATOR_DEBUG_FILE = os.environ.get('CKAN_CLOUD_OPERATOR_DEBUG_FILE', '').strip()
CKAN_CLOUD_OPERATOR_DEBUG_VERBOSE = strtobool(os.environ.get('CKAN_CLOUD_OPERATOR_DEBUG_VERBOSE', 'n'))

DEBUG_VERBOSE = 'verbose debug'


def info(*args, **kwargs):
    log(INFO, *args, **kwargs)


def debug(*args, **kwargs):
    log(DEBUG, *args, **kwargs)


def debug_verbose(*args, **kwargs):
    log(DEBUG_VERBOSE, yaml.dump([args, kwargs], default_flow_style=False))


def warning(*args, **kwargs):
    log(WARNING, *args, **kwargs)


def error(*args, **kwargs):
    log(ERROR, *args, **kwargs)


def critical(*args, **kwargs):
    log(CRITICAL, *args, **kwargs)


def log(level, *args, **kwargs):
    if not _skip_log_level(level):
        _print_log_msg(level, _get_log_msg(level, *args, **kwargs))


def important_log(level, *args, **kwargs):
    if not _skip_log_level(level):
        _print_log_msg(level, _get_important_log_msg(level, *args, **kwargs))


def exit_great_success(quiet=False):
    if not quiet:
        info('Great Success!')
    exit(0)


def exit_catastrophic_failure(exitcode=1, quiet=False):
    if not quiet:
        critical('Catastrophic Failure!')
    exit(exitcode)

# subprocess

def log_subprocess_output(stdout, stderr):
    for line in stderr.decode('utf8').split('\n'):
        if line:
            warning(line)
    for line in stdout.decode('utf8').split('\n'):
        if line:
            info(line)


def subprocess_run(command, input=None):
    completed = subprocess.run(
        command, input=input, 
        shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    log_subprocess_output(completed.stdout, completed.stderr)
    completed.check_returncode()

def subprocess_check_output(*args, **kw):
    try:
        return subprocess.check_output(*args, stderr=subprocess.PIPE, **kw)
    except subprocess.CalledProcessError as e:
        log_subprocess_output(e.stdout, e.stderr)
        raise

def subprocess_check_call(*args, **kw):
    try:
        return subprocess.check_call(*args, stderr=subprocess.PIPE, stdout=subprocess.PIPE, **kw)
    except subprocess.CalledProcessError as e:
        log_subprocess_output(e.stdout, e.stderr)
        raise

# yaml dumping


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


# private functions


def _get_log_msg(level, *args, **kwargs):
    msg = datetime.datetime.now().strftime('%Y-%m-%d %H:%M') + ' ' + _get_level_name(level) + ' '
    if len(kwargs) > 0:
        msg += '(' + ','.join([f'{k}="{v}"' for k, v in kwargs.items()]) + ') '
    msg += ' '.join(args)
    return msg


def _get_important_log_msg(level, *args, **kwargs):
    msg = ''
    header = datetime.datetime.now().strftime('%Y-%m-%d %H:%M') + ' ' + _get_level_name(level)
    msg += f'\n{header}\n'
    if len(kwargs) > 0:
        metadata = '(' + ','.join([f'{k}="{v}"' for k, v in kwargs.items()]) + ')'
        msg += metadata + '\n'
    msg += '\n\n'
    if len(args) > 0:
        title = args[0]
        msg += f'== {title}\n'
        if len(args) > 1:
            msg += ' '.join(args[1:])
            msg += '\n'
    return msg


def _get_level_name(level):
    if level == DEBUG_VERBOSE:
        return getLevelName(DEBUG)
    else:
        return getLevelName(level)


def _skip_log_level(level):
    return (
           (level == DEBUG and not CKAN_CLOUD_OPERATOR_DEBUG and not CKAN_CLOUD_OPERATOR_DEBUG_FILE)
        or (level == DEBUG_VERBOSE and not CKAN_CLOUD_OPERATOR_DEBUG_VERBOSE and not CKAN_CLOUD_OPERATOR_DEBUG_FILE)
    )


def _print_log_msg(level, msg):
    if CKAN_CLOUD_OPERATOR_DEBUG_FILE:
        with open(CKAN_CLOUD_OPERATOR_DEBUG_FILE, 'a') as f:
            print(msg, file=f)
    if (
        (level == DEBUG and (CKAN_CLOUD_OPERATOR_DEBUG or CKAN_CLOUD_OPERATOR_DEBUG_VERBOSE))
        or (level == DEBUG_VERBOSE and CKAN_CLOUD_OPERATOR_DEBUG_VERBOSE)
        or level not in [DEBUG, DEBUG_VERBOSE]
    ):
        print(msg, file=sys.stderr)
        sys.stderr.flush()

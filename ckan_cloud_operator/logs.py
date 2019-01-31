from logging import CRITICAL, ERROR, WARNING, INFO, DEBUG, getLevelName
import datetime


def info(*args, **kwargs):
    log(INFO, *args, **kwargs)

def debug(*args, **kwargs):
    log(DEBUG, *args, **kwargs)


def warning(*args, **kwargs):
    log(WARNING, *args, **kwargs)


def error(*args, **kwargs):
    log(ERROR, *args, **kwargs)


def critical(*args, **kwargs):
    log(CRITICAL, *args, **kwargs)


def log(level, *args, **kwargs):
    msg = datetime.datetime.now().strftime('%Y-%m-%d %H:%M') + ' ' + getLevelName(level) + ' '
    if len(kwargs) > 0:
        msg += '(' + ','.join([f'{k}="{v}"' for k, v in kwargs.items()]) + ') '
    msg += ' '.join(args)
    print(msg)

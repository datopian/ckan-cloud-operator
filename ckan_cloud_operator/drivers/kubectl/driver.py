from ckan_cloud_operator import kubectl


def get(what, *args, required=True, namespace=None, get_cmd=None, **kwargs):
    return kubectl.get(what, *args, required=required, namespace=namespace, get_cmd=get_cmd, **kwargs)

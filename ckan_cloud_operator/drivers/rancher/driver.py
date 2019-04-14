import requests

from ckan_cloud_operator import logs


def post_json(api_endpoint, access_key, secret, path, data):
    if access_key or secret:
        assert api_endpoint.startswith('https://'), f'invalid endpoint: {api_endpoint}'
        endpoint = api_endpoint.replace('https://', '')
        url = f'https://{access_key}:{secret}@{endpoint}{path}'
    else:
        url = f'{api_endpoint}{path}'
    res = requests.post(url, json=data)
    assert res.status_code in [200, 201], f'invalid status_code: {res.status_code}\n{res.text}'
    return res.json()


def create_user(api_endpoint, access_key, secret, username, password):
    return post_json(
        api_endpoint, access_key, secret,
        '/user',
        {
            "enabled": True, "me": False, "mustchangePassword": False,
            "password": password, "type": "user", "username": username
        }
    )


def create_cluster_role_template_binding(api_endpoint, access_key, secret, cluster_id, user_principal_id):
    return post_json(
        api_endpoint, access_key, secret,
        '/clusterroletemplatebinding',
        {
            "type": "clusterRoleTemplateBinding",
            "clusterId":cluster_id,
            "userPrincipalId": user_principal_id,
            "roleTemplateId": "cluster-owner"
        }
    )


def create_global_role_binding(api_endpoint, access_key, secret, user_id):
    return post_json(
        api_endpoint, access_key, secret,
        '/globalrolebinding',
        {
            "type": "globalRoleBinding",
            "globalRoleId": "admin",
            "userId": user_id,
            "subjectKind": "User"
        }
    )


def login(api_endpoint, username, password):
    return post_json(
        api_endpoint, None, None,
        '-public/localProviders/local?action=login', {
            "username": username,
            "password": password
        }
    )


def create_user_token(api_endpoint, user_login_token, token_description):
    access_key, secret = user_login_token.split(':')
    return post_json(
        api_endpoint, access_key, secret,
        '/token',
        {
            "current": False,
            "description": token_description,
            "expired": False,
            "isDerived": False,
            "ttl": 0,
            "type": "token"
        }
    )

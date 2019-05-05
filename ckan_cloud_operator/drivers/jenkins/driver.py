import requests


def curl(jenkins_user, jenkins_token, jenkins_url, post_json_data=None, raw=False):
    res = requests.post(jenkins_url, auth=(jenkins_user, jenkins_token), json=post_json_data)
    if raw:
        return res.text
    else:
        return res.json()


def get_session(jenkins_user, jenkins_token):
    session = requests.session()
    session.auth = (jenkins_user, jenkins_token)
    return session

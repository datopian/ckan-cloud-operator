import requests
from dataflows import load


def curl(jenkins_user, jenkins_token, jenkins_url, post_json_data=None):
    return requests.post(jenkins_url, auth=(jenkins_user, jenkins_token), json=post_json_data).json()


def get_session(jenkins_user, jenkins_token):
    session = requests.session()
    session.auth = (jenkins_user, jenkins_token)
    return session

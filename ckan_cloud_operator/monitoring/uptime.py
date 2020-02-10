import requests
from requests.adapters import HTTPAdapter
import six
from six.moves.urllib.parse import urlencode
from ckan_cloud_operator.config import manager as config_manager

class StatusCakeError(Exception):
    pass

class StatusCakeAuthError(StatusCakeError):
    pass

class StatusCakeNotLinkedError(StatusCakeError):
    pass

class StatusCakeFieldMissingError(StatusCakeError):
    pass

class StatusCakeFieldError(StatusCakeError):
    pass

class StatusCakeResponseError(StatusCakeError):
    pass


def to_comma_list(value):
    if isinstance(value, (list, tuple, set, frozenset)):
        value = ','.join(value)
    return value


class DeisCkanInstanceUptime(object):
    URL_ALL_TESTS = "https://app.statuscake.com/API/Tests/"
    URL_DETAILS_TEST = "https://app.statuscake.com/API/Tests/Details/?TestID=%s"
    URL_UPDATE_TEST = "https://app.statuscake.com/API/Tests/Update"
    URL_ALL_GROUPS = "https://app.statuscake.com/API/ContactGroups/"

    TESTS_FIELDS = {
        'TestID': (int, None, None),
        'WebsiteName': (six.string_types, None, None),
        'WebsiteURL': (six.string_types, None, None),
        'CheckRate': (int, range(0, 24001), None),
        'TestType': (six.string_types, ("HTTP", "TCP", "PING", "PUSH"), None),
        'ContactGroup': (six.string_types, None, to_comma_list)
    }

    def __init__(self, instance):
        config = config_manager.get(secret_name='uptime-statuscake-api')
        self.statuscake_api_user = config['user']
        self.statuscake_api_key = config['key']
        self.statuscake_group = config['group']
        self.instance_id = instance.id
        self.instance = instance
        self.timeout = 10

        self.session = requests.Session()
        self.session.mount('https://www.statuscake.com', HTTPAdapter(max_retries=5))

    def _request(self, method, url, data=None, auth_headers=True, check_errors=True, **kwargs):
        headers = {}
        if auth_headers:
            headers.update({
                'API': self.statuscake_api_key,
                'Username': self.statuscake_api_user,
            })

        if isinstance(data, dict):
            data = urlencode(data)

        kwargs.setdefault('timeout', self.timeout)
        print_json = kwargs.pop('print_json', False)
        print_raw = kwargs.pop('print_raw', False)
        response = getattr(self.session, method)(url, headers=headers, data=data, **kwargs)
        if print_raw:
            print(response.text)
        if print_json:
            print(response.json())
        if check_errors:
            json_resp = response.json()
            if isinstance(json_resp, dict) and (json_resp.get('Success', True) is False or json_resp.get('Error', None) is not None):
                errno = json_resp.get('ErrNo', -1)
                error_message = json_resp.get('Error')
                if not error_message:
                    error_message = json_resp.get('Message')
                if errno == 0:
                    raise StatusCakeAuthError(error_message or 'Authentication Failed')
                elif errno == 1:
                    raise StatusCakeNotLinkedError(error_message or 'Authentication Failed')
                raise StatusCakeResponseError(error_message or 'API Call Failed')
        return response

    def _check_fields(self, data, check_map):
        for field_name, (field_type, field_values, field_conv) in six.iteritems(check_map):
            if field_name not in data:
                continue
            if field_conv:
                try:
                    data[field_name] = field_conv(data[field_name])
                except TypeError as exc:
                    raise StatusCakeFieldError("Field %s: %s" % (field_name, str(exc)))
            if not isinstance(data[field_name], field_type):
                raise StatusCakeFieldError("Field %s must be of type %s" % (field_name, field_type))
            if field_values is not None and data[field_name] not in field_values:
                raise StatusCakeFieldError("Field %s value %s does not match one of: %s" % (field_name, field_type, field_values))

    def get_contact_groups(self, **kwargs):
        return self._request('get', self.URL_ALL_GROUPS, **kwargs).json()

    def get_all_tests(self, **kwargs):
        return self._request('get', self.URL_ALL_TESTS, **kwargs).json()

    def get_details_test(self, test_id, **kwargs):
        return self._request('get', self.URL_DETAILS_TEST % test_id, **kwargs).json()

    def delete_test(self, test_id, **kwargs):
        return self._request('delete', self.URL_DETAILS_TEST % test_id, **kwargs).json()

    def insert_test(self, data, **kwargs):
        if not isinstance(data, dict):
            raise StatusCakeError("data argument must be a dict")
        if 'WebsiteName' not in data:
            raise StatusCakeFieldMissingError("WebsiteName missing")
        if 'WebsiteURL' not in data:
            raise StatusCakeFieldMissingError("WebsiteURL missing")
        if 'TestType' not in data:
            raise StatusCakeFieldMissingError("TestType missing")
        if 'CheckRate' not in data:
            data['CheckRate'] = 300
        self._check_fields(data, self.TESTS_FIELDS)
        return self._request('put', self.URL_UPDATE_TEST, data=data, **kwargs).json()

    def update_test(self, data, **kwargs):
        if not isinstance(data, dict):
            raise StatusCakeError("data argument must be a dict")
        if 'TestID' not in data:
            raise StatusCakeFieldMissingError("TestID missing")
        # if CheckRate not passed it will be reset to the account plan default (either 30 or 300)
        if 'CheckRate' not in data:
            raise StatusCakeFieldMissingError("CheckRate missing")
        self._check_fields(data, self.TESTS_FIELDS)
        return self._request('put', self.URL_UPDATE_TEST, data=data, **kwargs).json()

    def get_test_id(self, website_name):
        test = list(filter(lambda x: x.get('WebsiteName') == website_name, self.get_all_tests()))
        if not len(test):
            return None
        return test[0]['TestID']

    def update(self, site_url):
        from ckan_cloud_operator.providers.routers import manager as routers_manager
        env_id = routers_manager.get_env_id()
        website_name = f'{env_id}-{self.instance_id}'
        data = {
            "WebsiteName": website_name,
            "WebsiteURL": site_url,
            "CheckRate": 300,
            "TestType": "HTTP",
            "ContactGroup": self.statuscake_group
        }
        test_id = self.get_test_id(website_name)
        if test_id is None:
            try:
                self.insert_test(data)
            except Exception as e:
                print('Failed to create StatusCake test, skipping')
                print(e)
        else:
            data['TestID'] = test_id
            try:
                self.update_test(data)
            except Exception as e:
                print('Failed to update StatusCake test, skipping')
                print(e)


    def delete(self, site_id):
        try:
            test_id = self.get_test_id(self.instance_id)
            self.delete_test(test_id)
        except Exception as e:
            print('Failed to delete StatusCake test, skipping')
            print(e)

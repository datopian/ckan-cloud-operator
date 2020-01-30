import json
import os
import unittest

import requests

INSTANCE_URL = os.getenv('INSTANCE_URL')


@unittest.skipIf(not INSTANCE_URL, 'CI test')
class InstanceTestCase(unittest.TestCase):
    def setUp(self):
        self.session = requests.Session()
        data = {
            'login': os.getenv('CKAN_LOGIN'),
            'password': os.getenv('CKAN_PASSWORD'),
            'remember': 63072000
        }
        resp = self.session.post(INSTANCE_URL + '/login_generic?came_from=/user/logged_in', data=data)
        self.assertEqual(resp.status_code, 200)

    def _create_org(self):
        data = {
            'name': 'datopian',
            'title': 'Datopian',
            'state': 'active'
        }
        self.session.post(INSTANCE_URL + '/api/3/action/organization_create', data=data)

    def test_instance_is_accessible_via_external_domain(self):
        resp = requests.get(INSTANCE_URL)
        self.assertEqual(resp.status_code, 200)

    def test_create_dataset_search_and_download(self):
        self._create_org()

        csv_data = 'useful,data,to,send\nanother,data,to,send\n'

        # create_dataset
        data = {
            'name': 'new-dataset',
            'title': 'New dataset',
            'state': 'active',
            'owner_org': 'datopian'
        }
        resp = self.session.post(INSTANCE_URL + '/api/3/action/package_create', data=data)
        resp_json = json.loads(resp.content.decode())
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp_json['success'])

        # create resource (file upload)
        files = {'upload': ('report.csv', csv_data)}
        data = {
            'package_id': 'new-dataset',
            'name': 'test data'
        }
        resp = self.session.post(INSTANCE_URL + '/api/3/action/resource_create', data=data, files=files)
        resource_json = json.loads(resp.content.decode())
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resource_json['success'])

        # test dataset search
        resp = self.session.get(INSTANCE_URL + '/api/3/action/package_search?q=new')
        resp_json = json.loads(resp.content.decode())
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp_json['success'])
        self.assertEqual(resp_json['result']['count'], 1)

        # download data
        resp = requests.get(resource_json['result']['url'])
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(csv_data, resp.content.decode())

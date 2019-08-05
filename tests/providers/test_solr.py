import json
import unittest
from unittest.mock import patch

from ckan_cloud_operator.providers.solr import manager


class SolrManagerTestCase(unittest.TestCase):
    @patch('ckan_cloud_operator.providers.solr.manager.get_replication_factor')
    @patch('ckan_cloud_operator.providers.solr.manager.get_num_shards')
    @patch('ckan_cloud_operator.providers.solr.manager.solr_curl')
    def test_create_collection(self, solr_curl, get_num_shards, get_replication_factor):
        get_replication_factor.return_value = 2
        get_num_shards.return_value = 1
        solr_curl.return_value = ''

        manager.create_collection('montreal', 'config_27_default')
        solr_curl.assert_called_once_with('/admin/collections?action=CREATE&name=montreal&collection.configName=config_27_default&replicationFactor=2&numShards=1', required=True)

    @patch('ckan_cloud_operator.providers.solr.manager.solr_curl')
    @patch('ckan_cloud_operator.providers.solr.manager.get_internal_http_endpoint')
    def test_get_collection_status(self, http_endpoint, solr_curl):
        http_endpoint.return_value = '192.168.0.101'
        solr_curl.return_value = json.dumps({
            'schema': {
                'version': '27',
                'name': 'ckan_27_default'
            }
        })
        expected_status = {
            'ready': True,
            'collection_name': 'montreal',
            'solr_http_endpoint': '192.168.0.101',
            'schemaVersion': '27',
            'schemaName': 'ckan_27_default'
        }
        self.assertEqual(manager.get_collection_status('montreal'), expected_status)

    @patch('ckan_cloud_operator.providers.solr.manager.solr_curl')
    @patch('ckan_cloud_operator.providers.solr.manager.get_internal_http_endpoint')
    def test_get_collection_status_not_ready(self, http_endpoint, solr_curl):
        http_endpoint.return_value = '192.168.0.101'
        solr_curl.return_value = False
        expected_status = {
            'ready': False,
            'collection_name': 'montreal',
            'solr_http_endpoint': '192.168.0.101'
        }
        self.assertEqual(manager.get_collection_status('montreal'), expected_status)

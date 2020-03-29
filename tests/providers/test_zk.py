import json
import unittest
from unittest.mock import patch, call

from ckan_cloud_operator.providers.solr import manager


class ZooKeeperTestCase(unittest.TestCase):
    @patch('ckan_cloud_operator.providers.solr.manager.kubectl.get')
    @patch('ckan_cloud_operator.providers.solr.manager.kubectl.check_output')
    def test_put_configs(self, kubectl_check_output, kubectl_get):
        kubectl_get.return_value = {
            'items': [
                {
                    'metadata': {
                        'name': 'zk-default-pod'
                    }
                }
            ]
        }
        manager.zk_put_configs('tests/test_data/schema')
        self.assertEqual(kubectl_check_output.call_count, 3)
        expected_calls = [
            call('exec zk-default-pod zkCli.sh create /configs null'),
            call('cp tests/test_data/schema/schema.xml zk-default-pod:/tmp/zk_input'),
            call('exec zk-default-pod bash -- -c \'zkCli.sh create /configs/schema.xml "$(cat /tmp/zk_input)"\'')
        ]
        self.assertEqual(kubectl_check_output.call_args_list, expected_calls)

import unittest
from unittest.mock import patch, MagicMock

from ckan_cloud_operator.routers.annotations import CkanRoutersAnnotations
from ckan_cloud_operator.routers.traefik import manager


class RoutersManagerTestCase(unittest.TestCase):
    @patch('ckan_cloud_operator.providers.cluster.manager.get_provider_id')
    @patch('ckan_cloud_operator.kubectl.apply')
    @patch.object(CkanRoutersAnnotations, 'update_flag')
    def test_create_with_cloudflare(self, update_flag, apply, get_provider_id):
        get_provider_id.return_value = 'gcp'
        router = {
            'metadata': {
                'name': 'datapusher',
            },
            'spec': {
                'default-root-domain': 'default',
                'type': 'traefik',
                'cloudflare': {
                    'email': 'admin@localhost',
                    'api-key': 'apikey'
                },
            }
        }
        manager.create(router)
        apply.assert_called_once_with(router)

    @patch('ckan_cloud_operator.providers.cluster.manager.get_provider_id')
    @patch.object(CkanRoutersAnnotations, 'update_flag')
    def test_create_with_cloudflare_without_credentials(self, update_flag, get_provider_id):
        get_provider_id.return_value = 'gcp'
        router = {
            'metadata': {
                'name': 'datapusher',
            },
            'spec': {
                'default-root-domain': None,
                'type': 'traefik',
                'dns-provider': 'cloudflare',
                'cloudflare': {
                },
            }
        }
        with self.assertRaisesRegex(AssertionError, 'invalid traefik router spec'):
            manager.create(router)

    @patch('ckan_cloud_operator.providers.cluster.manager.get_provider_id')
    @patch('ckan_cloud_operator.kubectl.apply')
    @patch.object(CkanRoutersAnnotations, 'update_flag')
    def test_create_with_route53(self, update_flag, apply, get_provider_id):
        get_provider_id.return_value = 'aws'
        router = {
            'metadata': {
                'name': 'datapusher',
            },
            'spec': {
                'default-root-domain': 'default',
                'type': 'traefik',
            }
        }
        manager.create(router)
        apply.assert_called_once_with(router)

    @patch('ckan_cloud_operator.kubectl.call')
    @patch('ckan_cloud_operator.kubectl.get_items_by_labels')
    @patch('ckan_cloud_operator.kubectl.get')
    def test_delete(self, get, get_items_by_labels, call):
        get_items_by_labels.return_value = []
        get.return_value = False
        call.return_value = 0
        manager.delete('datapushers')
        self.assertEqual(call.call_count, 7)
        get_items_by_labels.assert_called_once_with('CkanCloudRoute', {'ckan-cloud/router-name': 'datapushers'}, required=False)

    @patch('ckan_cloud_operator.kubectl.call')
    def test_delete_failed(self, call):
        call.return_value = 1
        with self.assertRaisesRegex(Exception, 'Deletion failed'):
            manager.delete('datapushers')
        self.assertEqual(call.call_count, 7)

    @patch('ckan_cloud_operator.routers.traefik.manager.traefik_deployment')
    def test_get_with_default_params(self, traefik_deployment):
        traefik_deployment.get_dns_data.return_value = {'root-domain': 'ckan.io'}
        traefik_deployment.get.return_value = {'router-type': 'traefik'}
        self.assertEqual(manager.get('datapushers'), {'router-type': 'traefik'})

    @patch('ckan_cloud_operator.routers.traefik.manager.traefik_deployment')
    def test_get_dns_attr(self, traefik_deployment):
        traefik_deployment.get_dns_data.return_value = {'root-domain': 'ckan.io'}
        traefik_deployment.get.return_value = {'router-type': 'traefik'}
        self.assertEqual(manager.get('datapushers', attr='dns'), {'root-domain': 'ckan.io'})

    @patch('ckan_cloud_operator.routers.traefik.manager.traefik_deployment')
    def test_get_all_attr(self, traefik_deployment):
        traefik_deployment.get_dns_data.return_value = {'root-domain': 'ckan.io'}
        traefik_deployment.get.return_value = {'router-type': 'traefik'}
        self.assertEqual(manager.get('datapushers', attr='all'), {'dns': {'root-domain': 'ckan.io'}, 'deployment': {'router-type': 'traefik'}})

    @patch('ckan_cloud_operator.kubectl.get')
    def test_update_new_deployment(self, get):
        get.return_value = None
        annotations = MagicMock()

        manager.update('datapushers', False, {'router-type': 'traefik'}, annotations, {'root-domain': 'ckan.io'})
        get.assert_called_once_with('deployment router-traefik-datapushers', required=False)
        self.assertEqual(annotations.update_status.call_count, 1)

    @patch('ckan_cloud_operator.kubectl.get')
    def test_update_old_deployment(self, get):
        get.side_effect = [
            {
                'metadata': {
                    'generation': 1
                }
            },
            {
                'metadata': {
                    'generation': 2
                }
            }
        ]
        annotations = MagicMock()

        manager.update('datapushers', False, {'router-type': 'traefik'}, annotations, {'root-domain': 'ckan.io'})
        self.assertEqual(get.call_count, 2)
        self.assertEqual(annotations.update_status.call_count, 1)

    @patch('ckan_cloud_operator.kubectl.get')
    def test_update_old_deployment_wrong_generation(self, get):
        get.side_effect = [
            {
                'metadata': {
                    'generation': 1
                }
            },
            {
                'metadata': {
                    'generation': 4
                }
            }
        ]
        annotations = MagicMock()

        with self.assertRaisesRegex(Exception, 'Invalid generation: 4 \(expected: 2\)'):
            manager.update('datapushers', False, {'router-type': 'traefik'}, annotations, {'root-domain': 'ckan.io'})
        self.assertEqual(get.call_count, 2)
        self.assertEqual(annotations.update_status.call_count, 1)

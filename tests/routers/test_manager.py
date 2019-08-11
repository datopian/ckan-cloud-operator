import unittest
from unittest.mock import patch, MagicMock

from ckan_cloud_operator.routers.annotations import CkanRoutersAnnotations
from ckan_cloud_operator.routers import manager


class RoutersManagerTestCase(unittest.TestCase):
    @patch('ckan_cloud_operator.routers.manager.get')
    @patch('ckan_cloud_operator.kubectl.get_resource')
    @patch('ckan_cloud_operator.routers.traefik.manager.create')
    @patch('ckan_cloud_operator.providers.cluster.manager.get_or_create_multi_user_volume_claim')
    @patch.object(CkanRoutersAnnotations, 'json_annotate')
    def test_create_with_traefik_router(self, json_annotate, muvc, create, get_resource, get):
        spec = {
            'type': 'traefik',
            'default-root-domain': 'test.local'
        }
        manager.create('datapusher', spec)

        get.assert_called_once_with('datapusher', only_dns=True, failfast=True)
        get_resource.assert_called_once_with(
            'stable.viderum.com/v1',
            'CkanCloudRouter',
            'datapusher',
            {'ckan-cloud/router-name': 'datapusher', 'ckan-cloud/router-type': 'traefik'},
            spec=spec
        )
        muvc.assert_called_once_with({'router-name': 'datapusher', 'router-type': 'traefik'})
        json_annotate.assert_called_once_with('default-root-domain', 'test.local')

    def test_create_with_unsupported_router(self):
        spec = {
            'type': 'wildtraefik',
            'default-root-domain': 'test.local'
        }
        with self.assertRaisesRegex(AssertionError, 'Invalid router spec'):
            manager.create('datapusher', spec)

    def test_create_without_default_root_domain(self):
        spec = {'type': 'traefik'}
        with self.assertRaisesRegex(AssertionError, 'Invalid router spec'):
            manager.create('datapusher', spec)

    def test_get_traefik_router_spec(self):
        expected_spec = {
            'type': 'traefik',
            'default-root-domain': 'default',
            'cloudflare': {
                'email': 'default',
                'api-key': 'default'
            },
            'wildcard-ssl-domain': None,
            'external-domains': False,
            'dns-provider': None
        }
        self.assertEqual(manager.get_traefik_router_spec(), expected_spec)

        expected_spec = {
            'type': 'traefik',
            'default-root-domain': 'test.local',
            'cloudflare': {
                'email': 'admin@test.local',
                'api-key': 'my-super-secret-api-key'
            },
            'wildcard-ssl-domain': 'test.local',
            'external-domains': True,
            'dns-provider': 'CloudFlare'
        }
        options = {
            'default_root_domain': 'test.local',
            'cloudflare_email': 'admin@test.local',
            'cloudflare_api_key': 'my-super-secret-api-key',
            'wildcard_ssl_domain': 'test.local',
            'external_domains': True,
            'dns_provider': 'CloudFlare'
        }
        self.assertEqual(manager.get_traefik_router_spec(**options), expected_spec)

    @patch('ckan_cloud_operator.routers.manager._init_router')
    @patch('ckan_cloud_operator.routers.traefik.manager')
    @patch('ckan_cloud_operator.routers.manager.routes_manager.list')
    def test_update(self, list, traefik_manager, _init_router):
        _init_router.return_value = 'router', {'update': True}, 'traefik', {}, {}, {'manager': traefik_manager}
        list.return_value = 'router'
        manager.update('datapusher', wait_ready=True)
        _init_router.assert_called_once_with('datapusher')
        list.assert_called_once_with({})
        traefik_manager.update.assert_called_once_with('datapusher', True, {'update': True}, {}, 'router', dry_run=False)

    @patch('ckan_cloud_operator.kubectl.get')
    def test_list(self, get):
        get.return_value = {
            'items': [
                {
                    'metadata': {
                        'name': 'datapusher',
                    },
                    'spec': {
                        'type': 'traefik'
                    }
                },
                {
                    'metadata': {
                        'name': 'infra-1',
                    },
                    'spec': {
                        'type': 'traefik'
                    }
                },
                {
                    'metadata': {
                        'name': 'prod',
                    },
                    'spec': {
                        'type': 'traefik'
                    }
                }
            ]
        }
        expected_list = [
            {'name': 'datapusher', 'type': 'traefik'},
            {'name': 'infra-1', 'type': 'traefik'},
            {'name': 'prod', 'type': 'traefik'}
        ]
        self.assertEqual(manager.list(values_only=True, async_print=False), expected_list)

    @patch('ckan_cloud_operator.kubectl.get')
    @patch('ckan_cloud_operator.routers.manager._init_router')
    @patch('ckan_cloud_operator.routers.traefik.manager')
    @patch('ckan_cloud_operator.routers.manager.routes_manager.list')
    def test_get(self, list, traefik_manager, _init_router, get):
        get.return_value = {'metadata': {'annotations': 'annotations'}, 'spec': {'type': 'test'}}
        _init_router.return_value = 'router', {'update': True}, 'traefik', {}, {}, {'manager': traefik_manager}
        list.return_value = [{'spec': {'type': 'CkanCloudRouter'}}]
        traefik_manager.get.return_value = {'type': 'CkanCloudRouter'}

        expected_result = {
            'name': 'datapusher',
            'annotations': 'annotations',
            'routes': [{'type': 'CkanCloudRouter'}],
            'type': 'traefik',
            'deployment': {'type': 'CkanCloudRouter'},
            'ready': False,
            'dns': {'type': 'CkanCloudRouter'},
            'spec': {'ready': True, 'type': 'test'}
        }
        self.assertEqual(manager.get('datapusher'), expected_result)

        expected_result = {
            'name': 'datapusher',
            'dns': {'type': 'CkanCloudRouter'}
        }
        self.assertEqual(manager.get('datapusher', only_dns=True), expected_result)

    @patch('ckan_cloud_operator.routers.manager.get_env_id')
    @patch('ckan_cloud_operator.routers.manager._init_router')
    @patch('ckan_cloud_operator.kubectl.get_resource')
    @patch('ckan_cloud_operator.kubectl.apply')
    @patch('ckan_cloud_operator.routers.traefik.manager')
    @patch('ckan_cloud_operator.routers.manager.hashlib')
    def test_create_subdomain_route(self, hashlib, traefik_manager, apply, get_resource, _init_router, get_env_id):
        get_env_id.return_value = 'p'
        _init_router.return_value = 'router', {'update': True}, 'traefik', {}, {}, {'manager': traefik_manager}
        hashmock = MagicMock()
        hashmock.hexdigest = lambda: '123123123hashed'
        hashlib.sha3_224.return_value = hashmock
        route_spec = {
            'target-type': 'datapusher',
            'sub-domain': 'www',
            'root-domain': 'example.com',
            'datapusher-name': 'datapusher-1'
        }
        manager.create_subdomain_route('datapusher', route_spec)

        spec = {
            'name': 'cc123123123hashed',
            'type': 'datapusher-subdomain',
            'root-domain': 'example.com',
            'sub-domain': 'www',
            'router_name': 'datapusher',
            'router_type': 'traefik',
            'route-target-type': 'datapusher',
            'route-target-resource-id': 'datapusher-1',
            'datapusher-name': 'datapusher-1'
        }
        labels = {
            'ckan-cloud/route-type': 'datapusher-subdomain',
            'ckan-cloud/route-root-domain': 'example.com',
            'ckan-cloud/route-sub-domain': 'www',
            'ckan-cloud/route-target-type': 'datapusher',
            'ckan-cloud/route-target-resource-id': 'datapusher-1',
            'ckan-cloud/route-datapusher-name': 'datapusher-1'
        }
        get_resource.assert_called_once_with('stable.viderum.com/v1', 'CkanCloudRoute', 'cc123123123hashed', labels, spec=spec)

    def test_create_subdomain_route_with_invalid_spec(self):
        route_spec = {
            'target-type': 'infra-1'
        }
        with self.assertRaisesRegex(Exception, 'Invalid route spec'):
            manager.create_subdomain_route('datapusher', route_spec)

    @patch('ckan_cloud_operator.kubectl.install_crd')
    @patch('ckan_cloud_operator.routers.manager.routes_manager.install_crds')
    def test_install_crds(self, install_crds, install_crd):
        manager.install_crds()
        install_crd.assert_called_once_with('ckancloudrouters', 'ckancloudrouter', 'CkanCloudRouter')
        install_crds.assert_called_once()

    @patch('ckan_cloud_operator.routers.manager._init_router')
    @patch('ckan_cloud_operator.routers.traefik.manager')
    def test_delete(self, traefik_manager, _init_router):
        _init_router.return_value = 'router', {'update': True}, 'traefik', {}, {}, {'manager': traefik_manager}
        manager.delete('datapusher')
        traefik_manager.delete.assert_called_once_with('datapusher')

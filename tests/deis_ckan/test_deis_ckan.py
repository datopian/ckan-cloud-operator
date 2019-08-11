import unittest
from unittest.mock import patch, Mock, MagicMock, call

from ckan_cloud_operator.deis_ckan.ckan import DeisCkanInstanceCKAN
from ckan_cloud_operator.deis_ckan.instance import DeisCkanInstance
from ckan_cloud_operator.deis_ckan.db import DeisCkanInstanceDb, postgres_driver, db_manager, DATASTORE_PERMISSIONS_SQL_TEMPLATE


class CkanTestCase(unittest.TestCase):
    def setUp(self):
        self.ckan = DeisCkanInstanceCKAN(DeisCkanInstance('montreal'))

    def test_run_exec_command(self):
        self.ckan._get_ckan_pod_name = lambda: 'montreal-asd-qwe'
        self.ckan.instance.kubectl = MagicMock()
        self.ckan.run('exec', 'ls', '-lrt')
        self.ckan.instance.kubectl.assert_called_once_with('exec montreal-asd-qwe ls -lrt', check_output=False)

    def test_run_paster_command(self):
        self.ckan._get_ckan_pod_name = lambda: 'montreal-asd-qwe'
        self.ckan.instance.kubectl = MagicMock()
        self.ckan.run('paster', 'initdb')
        self.ckan.instance.kubectl.assert_called_once_with('exec montreal-asd-qwe -it -- paster --plugin=ckan initdb -c /srv/app/production.ini ', check_output=False)

    def test_run_logs_command(self):
        self.ckan._get_ckan_pod_name = lambda: 'montreal-asd-qwe'
        self.ckan.instance.kubectl = MagicMock()
        self.ckan.run('logs')
        self.ckan.instance.kubectl.assert_called_once_with('logs montreal-asd-qwe ')

    @patch('ckan_cloud_operator.deis_ckan.ckan.subprocess.check_call')
    def test_run_port_forward_command(self, check_call):
        self.ckan._get_ckan_pod_name = lambda: 'montreal-asd-qwe'
        self.ckan.instance.kubectl = MagicMock()
        self.ckan.run('port-forward', '5001')
        self.ckan.instance.kubectl.assert_called_once_with('port-forward montreal-asd-qwe 5001')
        check_call.assert_called_once_with(['kubectl', '-n', 'montreal', 'port-forward', 'deployment/montreal', '5001'])

    def test_run_with_unsupported_command(self):
        with self.assertRaises(AssertionError):
            self.ckan.run('delete', 'everything')

    def test_init_creation_command(self):
        self.ckan._get_ckan_pod_name = lambda: 'montreal-asd-qwe'
        self.ckan.instance.kubectl = MagicMock()
        self.ckan.instance._spec = MagicMock()
        self.ckan.instance.spec.spec = {
            'ckan': {
                'init': [
                    ['paster', 'initdb'],
                    ['paster', 'test', '-v']
                ]
            }
        }
        self.ckan._create()
        self.assertEqual(self.ckan.instance.kubectl.call_count, 2)
        self.ckan.instance.kubectl.assert_has_calls([
            call('exec montreal-asd-qwe -it -- paster --plugin=ckan initdb -c /srv/app/production.ini ', check_output=False),
            call('exec montreal-asd-qwe -it -- paster --plugin=ckan test -c /srv/app/production.ini -v', check_output=False)
        ])

    def test_init_creation_with_non_paster_command(self):
        self.ckan._get_ckan_pod_name = lambda: 'montreal-asd-qwe'
        self.ckan.instance.kubectl = MagicMock()
        self.ckan.instance._spec = MagicMock()
        self.ckan.instance.spec.spec = {
            'ckan': {
                'init': [
                    ['paster', 'initdb'],
                    ['ls', '-lrt']
                ]
            }
        }
        with self.assertRaisesRegex(ValueError, "Invalid ckan init cmd: ['ls', '-lrt']"):
            self.ckan._create()
        self.ckan.instance.kubectl.assert_called_once_with('exec montreal-asd-qwe -it -- paster --plugin=ckan initdb -c /srv/app/production.ini ', check_output=False)


class DbTestCase(unittest.TestCase):
    def setUp(self):
        self.instance = DeisCkanInstance('montreal')
        self.instance._spec = Mock(datastore={'name': 'test'})
        self.db = DeisCkanInstanceDb(self.instance, 'db')
        self.datastore = DeisCkanInstanceDb(self.instance, 'datastore')

    def test_set_datastore_readonly_permissions(self):
        postgres_driver.connect = MagicMock()
        db_manager.get_external_admin_connection_string = MagicMock()
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cursor
        postgres_driver.connect.return_value.__enter__.return_value = conn
        self.instance.annotations.get_secret = lambda x: 'postgres_ro'

        self.datastore.set_datastore_readonly_permissions()

        self.assertEqual(cursor.execute.call_count, 5)
        cursor.execute.assert_has_calls([
            call("GRANT CONNECT ON DATABASE \"test\" TO \"postgres_ro\";"),
            call("GRANT USAGE ON SCHEMA public TO \"postgres_ro\";"),
            call("GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"postgres_ro\";"),
            call("ALTER DEFAULT PRIVILEGES FOR USER \"test\" IN SCHEMA public GRANT SELECT ON TABLES TO \"postgres_ro\";"),
            call(DATASTORE_PERMISSIONS_SQL_TEMPLATE.replace('{{SITE_USER}}', 'test').replace('{{DS_RO_USER}}', 'postgres_ro'))
        ])

    def test_set_datastore_readonly_permissions_for_db(self):
        with self.assertRaises(AssertionError):
            self.db.set_datastore_readonly_permissions()

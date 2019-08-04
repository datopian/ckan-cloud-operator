from unittest.mock import patch

from ckan_cloud_operator.cli import deis_instance
from ckan_cloud_operator.deis_ckan.instance import DeisCkanInstance, DeisCkanInstanceCKAN
from tests.bases import BaseCliTestCase


class DeisInstanceCliTestCase(BaseCliTestCase):
    @patch.object(DeisCkanInstance, 'get')
    def test_get(self, get):
        self.runner.invoke(deis_instance, ['get', 'montreal', 'deployment'])
        get.assert_called_once_with('deployment')

    @patch.object(DeisCkanInstance, 'create')
    def test_create_from_gitlab(self, create):
        self.runner.invoke(deis_instance, ['create', 'from-gitlab', 'viderum/cloud-demo2', 'ckan_27_default', 'montreal', '--db-prefix=prod2'])
        create.assert_called_once_with(
            'from-gitlab',
            'viderum/cloud-demo2',
            'ckan_27_default',
            'montreal',
            no_db_proxy=False,
            storage_path=None,
            from_db_backups=None,
            solr_collection=None,
            rerun=False,
            force=False,
            recreate_dbs=False,
            db_prefix='prod2',
            use_private_gitlab_repo=False
        )

    @patch.object(DeisCkanInstance, 'update')
    @patch('ckan_cloud_operator.deis_ckan.instance.ckan_manager')
    @patch('ckan_cloud_operator.deis_ckan.instance.subprocess.call')
    def test_edit(self, subprocess_call, ckan_manager, update):
        ckan_manager.instance_kind.return_value = 'ckancloudckaninstance'
        self.runner.invoke(deis_instance, ['edit', 'montreal', 'vim'])
        subprocess_call.assert_called_with('EDITOR=vim kubectl -n ckan-cloud edit ckancloudckaninstance/montreal', shell=True)
        self.assertEqual(update.call_count, 1)

    @patch.object(DeisCkanInstance, 'delete')
    def test_delete(self, delete):
        self.runner.invoke(deis_instance, ['delete', 'montreal'])
        self.assertEqual(delete.call_count, 1)

    @patch.object(DeisCkanInstance, 'delete')
    def test_delete_multiple(self, delete):
        self.runner.invoke(deis_instance, ['delete', 'montreal', 'another_instance', 'new_instance'])
        self.assertEqual(delete.call_count, 3)

    @patch.object(DeisCkanInstance, 'list')
    def test_list(self, deis_list):
        self.runner.invoke(deis_instance, ['list', '-f', '-q'])
        deis_list.assert_called_once_with(True, True)

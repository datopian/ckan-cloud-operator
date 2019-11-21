import json
import unittest
from unittest.mock import patch, call

from ckan_cloud_operator.providers.storage.s3 import manager


class S3ManagerTestCase(unittest.TestCase):
    @patch('ckan_cloud_operator.providers.storage.s3.manager.get_aws_credentials')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.list_s3_buckets')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.aws_check_output')
    def test_create_bucket(self, aws_check_output, list_s3_buckets, get_aws_credentials):
        aws_check_output.return_value = ''
        list_s3_buckets.return_value = []
        get_aws_credentials.return_value = {'region': 'us-west-1'}

        result = manager.create_bucket('new-instance')

        get_aws_credentials.assert_called_once()
        list_s3_buckets.assert_called_once()
        aws_check_output.assert_called_once_with('s3 mb s3://new-instance --region us-west-1')
        self.assertEqual(result, 's3://new-instance')

    @patch('ckan_cloud_operator.providers.storage.s3.manager.get_aws_credentials')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.list_s3_buckets')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.aws_check_output')
    def test_create_bucket_that_already_exists(self, aws_check_output, list_s3_buckets, get_aws_credentials):
        aws_check_output.return_value = ''
        list_s3_buckets.return_value = ['new-instance']
        get_aws_credentials.return_value = {'region': 'us-west-1'}

        with self.assertRaisesRegex(Exception, 'Bucket for this instance already exists'):
            manager.create_bucket('new-instance')

        self.assertEqual(manager.create_bucket('new-instance', exists_ok=True), 's3://new-instance')
        aws_check_output.assert_not_called()

    @patch('ckan_cloud_operator.providers.storage.s3.manager.get_aws_credentials')
    def test_create_bucket_without_region(self, get_aws_credentials):
        get_aws_credentials.return_value = {}
        with self.assertRaisesRegex(AssertionError, 'No default region set for the cluster'):
            manager.create_bucket('new-instance')

    @patch('ckan_cloud_operator.providers.storage.s3.manager.get_aws_credentials')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.list_s3_buckets')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.aws_check_output')
    def test_create_bucket_dry_run(self, aws_check_output, list_s3_buckets, get_aws_credentials):
        aws_check_output.return_value = ''
        list_s3_buckets.return_value = []
        get_aws_credentials.return_value = {'region': 'us-west-1'}

        result = manager.create_bucket('new-instance', dry_run=True)

        get_aws_credentials.assert_called_once()
        list_s3_buckets.assert_called_once()
        aws_check_output.assert_not_called()
        self.assertEqual(result, 's3://new-instance')

    @patch('ckan_cloud_operator.providers.storage.s3.manager.list_s3_buckets')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.aws_check_output')
    def test_delete_bucket(self, aws_check_output, list_s3_buckets):
        list_s3_buckets.return_value = ['new-instance']

        manager.delete_bucket('new-instance')

        expected_calls = [
            call('s3 rm s3://new-instance --recursive'),
            call('s3 rb s3://new-instance')
        ]
        self.assertEqual(aws_check_output.call_count, 2)
        self.assertEqual(aws_check_output.mock_calls, expected_calls)

    @patch('ckan_cloud_operator.providers.storage.s3.manager.list_s3_buckets')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.aws_check_output')
    def test_delete_bucket_that_does_not_exist(self, aws_check_output, list_s3_buckets):
        list_s3_buckets.return_value = []

        manager.delete_bucket('new-instance')

        aws_check_output.assert_not_called()

    @patch('ckan_cloud_operator.providers.storage.s3.manager.list_s3_buckets')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.aws_check_output')
    def test_delete_bucket_dry_run(self, aws_check_output, list_s3_buckets):
        list_s3_buckets.return_value = ['new-instance']

        manager.delete_bucket('new-instance', dry_run=True)

        aws_check_output.assert_called_once_with('s3 rm s3://new-instance --recursive --dryrun')

    @patch('ckan_cloud_operator.providers.storage.s3.manager.list_s3_buckets')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.kubectl.get')
    def test_get_bucket(self, kubectl_get, list_s3_buckets):
        list_s3_buckets.return_value = ['new-instance']
        kubectl_get.return_value = {
            'spec': {
                'bucket': {
                    's3': 's3://new-instance'
                }
            }
        }

        expected_result = {
            'instance_id': 'new-instance',
            'bucket': 's3://new-instance'
        }
        self.assertEqual(manager.get_bucket('new-instance'), expected_result)

    @patch('ckan_cloud_operator.providers.storage.s3.manager.list_s3_buckets')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.kubectl.get')
    def test_get_bucket_that_does_not_present_in_s3(self, kubectl_get, list_s3_buckets):
        list_s3_buckets.return_value = ['old-instance']

        self.assertIsNone(manager.get_bucket('new-instance'))
        kubectl_get.assert_not_called()

    @patch('ckan_cloud_operator.providers.storage.s3.manager.list_s3_buckets')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.kubectl.get')
    def test_get_bucket_when_instance_has_no_s3_buckets(self, kubectl_get, list_s3_buckets):
        list_s3_buckets.return_value = ['new-instance']
        kubectl_get.return_value = {
            'spec': {
                'bucket': {
                    'gcloud': 'new-instance'
                }
            }
        }

        self.assertIsNone(manager.get_bucket('new-instance'))

    @patch('ckan_cloud_operator.providers.storage.s3.manager.kubectl.get')
    def test_list_buckets(self, kubectl_get):
        kubectl_get.return_value = {
            'items': [
                {
                    'spec': {
                        'id': 'new-instance',
                        'bucket': {
                            's3': 's3://new-instance'
                        }
                    }
                },
                {
                    'spec': {
                        'id': 'old-instance',
                        'bucket': {
                            's3': 's3://old-instance'
                        }
                    }
                },
                {
                    'spec': {
                        'id': 'gcloud-instance',
                        'bucket': {
                            'gcloud': 'gcloud-instance'
                        }
                    }
                },
                {
                    'spec': {
                        'no-data': 'invalid spec'
                    }
                }
            ]
        }

        expected_result = [
            {
                'instance_id': 'new-instance',
                'bucket': 's3://new-instance'
            },
            {
                'instance_id': 'old-instance',
                'bucket': 's3://old-instance'
            }
        ]
        self.assertEqual(manager.list_buckets(), expected_result)
        kubectl_get.assert_called_once_with('ckancloudckaninstance')

    @patch('ckan_cloud_operator.providers.storage.s3.manager.aws_check_output')
    def test_list_s3_buckets(self, aws_check_output):
        aws_check_output.return_value = b"""
2019-11-10 21:37:53 new-instance
2019-11-10 21:32:57 old-instance
2019-11-10 21:32:57 another-instance"""

        expected_result = [
            ['2019-11-10 21:37:53', 'new-instance'],
            ['2019-11-10 21:32:57', 'old-instance'],
            ['2019-11-10 21:32:57', 'another-instance']
        ]
        self.assertEqual(manager.list_s3_buckets(), expected_result)

        expected_result = ['new-instance', 'old-instance', 'another-instance']
        self.assertEqual(manager.list_s3_buckets(names_only=True), expected_result)

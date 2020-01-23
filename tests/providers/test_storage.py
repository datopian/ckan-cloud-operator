import json
import unittest
from unittest.mock import patch, call

from ckan_cloud_operator.providers.storage.gcloud import manager as gcloud_manager
from ckan_cloud_operator.providers.storage.s3 import manager as s3_manager


class S3ManagerTestCase(unittest.TestCase):
    @patch('ckan_cloud_operator.providers.storage.s3.manager.get_aws_credentials')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.list_s3_buckets')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.aws_check_output')
    @patch('ckan_cloud_operator.providers.storage.s3.manager._generate_password')
    def test_create_bucket(self, _generate_password, aws_check_output, list_s3_buckets, get_aws_credentials):
        aws_check_output.return_value = ''
        list_s3_buckets.return_value = []
        get_aws_credentials.return_value = {'region': 'us-west-1'}
        _generate_password.return_value = 'abcdefabcdefabcdef'

        result = s3_manager.create_bucket('new-instance')

        get_aws_credentials.assert_called_once()
        list_s3_buckets.assert_called_once()
        aws_check_output.assert_called_once_with('s3 mb s3://new-instance-ccabcdefabcdefabcdef --region us-west-1')
        expected_result = {
            'BUCKET_NAME': 's3://new-instance-ccabcdefabcdefabcdef',
            'BUCKET_ACCESS_KEY': None,
            'BUCKET_ACCESS_SECRET': None
        }
        self.assertEqual(result, expected_result)

    @patch('ckan_cloud_operator.providers.storage.s3.manager.get_aws_credentials')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.list_s3_buckets')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.aws_check_output')
    @patch('ckan_cloud_operator.providers.storage.s3.manager._generate_password')
    def test_create_bucket_that_already_exists(self, _generate_password, aws_check_output, list_s3_buckets, get_aws_credentials):
        aws_check_output.return_value = ''
        list_s3_buckets.return_value = ['new-instance']
        get_aws_credentials.return_value = {'region': 'us-west-1'}
        _generate_password.return_value = 'abcdefabcdefabcdef'

        with self.assertRaisesRegex(Exception, 'Bucket for this instance already exists'):
            s3_manager.create_bucket('new-instance')

        expected_result = {
            'BUCKET_NAME': 's3://new-instance-ccabcdefabcdefabcdef',
            'BUCKET_ACCESS_KEY': None,
            'BUCKET_ACCESS_SECRET': None
        }
        self.assertEqual(s3_manager.create_bucket('new-instance', exists_ok=True), expected_result)
        aws_check_output.assert_not_called()

    @patch('ckan_cloud_operator.providers.storage.s3.manager.get_aws_credentials')
    def test_create_bucket_without_region(self, get_aws_credentials):
        get_aws_credentials.return_value = {}
        with self.assertRaisesRegex(AssertionError, 'No default region set for the cluster'):
            s3_manager.create_bucket('new-instance')

    @patch('ckan_cloud_operator.providers.storage.s3.manager.get_aws_credentials')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.list_s3_buckets')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.aws_check_output')
    @patch('ckan_cloud_operator.providers.storage.s3.manager._generate_password')
    def test_create_bucket_dry_run(self, _generate_password, aws_check_output, list_s3_buckets, get_aws_credentials):
        aws_check_output.return_value = ''
        list_s3_buckets.return_value = []
        get_aws_credentials.return_value = {'region': 'us-west-1'}
        _generate_password.return_value = 'abcdefabcdefabcdef'

        result = s3_manager.create_bucket('new-instance', dry_run=True)

        get_aws_credentials.assert_called_once()
        list_s3_buckets.assert_called_once()
        aws_check_output.assert_not_called()

        expected_result = {
            'BUCKET_NAME': 's3://new-instance-ccabcdefabcdefabcdef',
            'BUCKET_ACCESS_KEY': None,
            'BUCKET_ACCESS_SECRET': None
        }
        self.assertEqual(result, expected_result)

    @patch('ckan_cloud_operator.providers.storage.s3.manager.list_s3_buckets')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.aws_check_output')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.kubectl.get')
    def test_delete_bucket(self, kubectl_get, aws_check_output, list_s3_buckets):
        list_s3_buckets.return_value = ['new-instance-ccabcdefabcdefabcdef']
        kubectl_get.return_value = {
            'spec': {
                'ckanStorageBucket': {
                    's3': {
                        'BUCKET_NAME': 's3://new-instance-ccabcdefabcdefabcdef'
                    }
                }
            }
        }

        s3_manager.delete_bucket('new-instance')

        expected_calls = [
            call('s3 rm s3://new-instance-ccabcdefabcdefabcdef --recursive'),
            call('s3 rb s3://new-instance-ccabcdefabcdefabcdef')
        ]
        self.assertEqual(aws_check_output.call_count, 2)
        self.assertEqual(aws_check_output.mock_calls, expected_calls)

    @patch('ckan_cloud_operator.providers.storage.s3.manager.list_s3_buckets')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.aws_check_output')
    def test_delete_bucket_that_does_not_exist(self, aws_check_output, list_s3_buckets):
        list_s3_buckets.return_value = []

        s3_manager.delete_bucket('new-instance')

        aws_check_output.assert_not_called()

    @patch('ckan_cloud_operator.providers.storage.s3.manager.list_s3_buckets')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.aws_check_output')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.kubectl.get')
    def test_delete_bucket_dry_run(self, kubectl_get, aws_check_output, list_s3_buckets):
        list_s3_buckets.return_value = ['new-instance-ccabcdefabcdefabcdef']
        kubectl_get.return_value = {
            'spec': {
                'ckanStorageBucket': {
                    's3': {
                        'BUCKET_NAME': 's3://new-instance-ccabcdefabcdefabcdef'
                    }
                }
            }
        }

        s3_manager.delete_bucket('new-instance', dry_run=True)

        aws_check_output.assert_called_once_with('s3 rm s3://new-instance-ccabcdefabcdefabcdef --recursive --dryrun')

    @patch('ckan_cloud_operator.providers.storage.s3.manager.list_s3_buckets')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.kubectl.get')
    def test_get_bucket(self, kubectl_get, list_s3_buckets):
        list_s3_buckets.return_value = ['new-instance-ccabcdefabcdefabcdef']
        kubectl_get.return_value = {
            'spec': {
                'ckanStorageBucket': {
                    's3': 's3://new-instance-ccabcdefabcdefabcdef'
                }
            }
        }

        expected_result = {
            'instance_id': 'new-instance',
            'ckanStorageBucket': 's3://new-instance-ccabcdefabcdefabcdef'
        }
        self.assertEqual(s3_manager.get_bucket('new-instance'), expected_result)

    @patch('ckan_cloud_operator.providers.storage.s3.manager.list_s3_buckets')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.kubectl.get')
    def test_get_bucket_that_does_not_present_in_s3(self, kubectl_get, list_s3_buckets):
        list_s3_buckets.return_value = ['old-instance']

        self.assertIsNone(s3_manager.get_bucket('new-instance'))
        kubectl_get.assert_not_called()

    @patch('ckan_cloud_operator.providers.storage.s3.manager.list_s3_buckets')
    @patch('ckan_cloud_operator.providers.storage.s3.manager.kubectl.get')
    def test_get_bucket_when_instance_has_no_s3_buckets(self, kubectl_get, list_s3_buckets):
        list_s3_buckets.return_value = ['new-instance']
        kubectl_get.return_value = {
            'spec': {
               'ckanStorageBucket': {
                    'gcloud': 'new-instance'
                }
            }
        }

        self.assertIsNone(s3_manager.get_bucket('new-instance'))

    @patch('ckan_cloud_operator.providers.storage.s3.manager.kubectl.get')
    def test_list_buckets(self, kubectl_get):
        kubectl_get.return_value = {
            'items': [
                {
                    'spec': {
                        'id': 'new-instance',
                        'ckanStorageBucket': {
                            's3': 's3://new-instance'
                        }
                    }
                },
                {
                    'spec': {
                        'id': 'old-instance',
                        'ckanStorageBucket': {
                            's3': 's3://old-instance'
                        }
                    }
                },
                {
                    'spec': {
                        'id': 'gcloud-instance',
                        'ckanStorageBucket': {
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
                'ckanStorageBucket': 's3://new-instance'
            },
            {
                'instance_id': 'old-instance',
                'ckanStorageBucket': 's3://old-instance'
            }
        ]
        self.assertEqual(s3_manager.list_buckets(), expected_result)
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
        self.assertEqual(s3_manager.list_s3_buckets(), expected_result)

        expected_result = ['new-instance', 'old-instance', 'another-instance']
        self.assertEqual(s3_manager.list_s3_buckets(names_only=True), expected_result)


class GCloudManagerTestCase(unittest.TestCase):
    @patch('ckan_cloud_operator.providers.storage.gcloud.manager.cluster_config_get')
    @patch('ckan_cloud_operator.providers.storage.gcloud.manager.list_gcloud_buckets')
    @patch('ckan_cloud_operator.providers.storage.gcloud.manager.gcloud_check_output')
    def test_create_bucket(self, gcloud_check_output, list_s3_buckets, cluster_config_get):
        gcloud_check_output.return_value = ''
        list_s3_buckets.return_value = []
        cluster_config_get.return_value = 'europe-west2-c'

        result = gcloud_manager.create_bucket('new-instance')
        expected_result = {
            'BUCKET_NAME': 'gs://new-instance'
        }

        cluster_config_get.assert_called_once()
        list_s3_buckets.assert_called_once()
        gcloud_check_output.assert_called_once_with('mb gs://new-instance -l europe-west2-c', gsutil=True)
        self.assertEqual(result, expected_result)

    @patch('ckan_cloud_operator.providers.storage.gcloud.manager.cluster_config_get')
    @patch('ckan_cloud_operator.providers.storage.gcloud.manager.list_gcloud_buckets')
    @patch('ckan_cloud_operator.providers.storage.gcloud.manager.gcloud_check_output')
    def test_create_bucket_that_already_exists(self, gcloud_check_output, list_gcloud_buckets, cluster_config_get):
        gcloud_check_output.return_value = ''
        list_gcloud_buckets.return_value = ['new-instance']
        cluster_config_get.return_value = 'europe-west2-c'

        with self.assertRaisesRegex(Exception, 'Bucket for this instance already exists'):
            gcloud_manager.create_bucket('new-instance')

        expected_result = {
            'BUCKET_NAME': 'gs://new-instance'
        }
        self.assertEqual(gcloud_manager.create_bucket('new-instance', exists_ok=True), expected_result)
        gcloud_check_output.assert_not_called()

    @patch('ckan_cloud_operator.providers.storage.gcloud.manager.cluster_config_get')
    def test_create_bucket_without_region(self, cluster_config_get):
        cluster_config_get.return_value = {}
        with self.assertRaisesRegex(AssertionError, 'No default region set for the cluster'):
            gcloud_manager.create_bucket('new-instance')

    @patch('ckan_cloud_operator.providers.storage.gcloud.manager.cluster_config_get')
    @patch('ckan_cloud_operator.providers.storage.gcloud.manager.list_gcloud_buckets')
    @patch('ckan_cloud_operator.providers.storage.gcloud.manager.gcloud_check_output')
    def test_create_bucket_dry_run(self, gcloud_check_output, list_gcloud_buckets, cluster_config_get):
        gcloud_check_output.return_value = ''
        list_gcloud_buckets.return_value = []
        cluster_config_get.return_value = 'europe-west2-c'

        expected_result = {
            'BUCKET_NAME': 'gs://new-instance'
        }
        result = gcloud_manager.create_bucket('new-instance', dry_run=True)

        cluster_config_get.assert_called_once()
        list_gcloud_buckets.assert_called_once()
        gcloud_check_output.assert_not_called()
        self.assertEqual(result, expected_result)

    @patch('ckan_cloud_operator.providers.storage.gcloud.manager.list_gcloud_buckets')
    @patch('ckan_cloud_operator.providers.storage.gcloud.manager.gcloud_check_output')
    def test_delete_bucket(self, gcloud_check_output, list_gcloud_buckets):
        list_gcloud_buckets.return_value = ['new-instance']

        gcloud_manager.delete_bucket('new-instance')

        expected_calls = [
            call('rm -r gs://new-instance', gsutil=True),
        ]
        self.assertEqual(gcloud_check_output.call_count, 1)
        self.assertEqual(gcloud_check_output.mock_calls, expected_calls)

    @patch('ckan_cloud_operator.providers.storage.gcloud.manager.list_gcloud_buckets')
    @patch('ckan_cloud_operator.providers.storage.gcloud.manager.gcloud_check_output')
    def test_delete_bucket_that_does_not_exist(self, gcloud_check_output, list_gcloud_buckets):
        list_gcloud_buckets.return_value = []

        gcloud_manager.delete_bucket('new-instance')

        gcloud_check_output.assert_not_called()

    @patch('ckan_cloud_operator.providers.storage.gcloud.manager.list_gcloud_buckets')
    @patch('ckan_cloud_operator.providers.storage.gcloud.manager.gcloud_check_output')
    def test_delete_bucket_dry_run(self, gcloud_check_output, list_gcloud_buckets):
        list_gcloud_buckets.return_value = ['new-instance']

        gcloud_manager.delete_bucket('new-instance', dry_run=True)

        gcloud_check_output.assert_not_called()

    @patch('ckan_cloud_operator.providers.storage.gcloud.manager.list_gcloud_buckets')
    @patch('ckan_cloud_operator.providers.storage.gcloud.manager.kubectl.get')
    def test_get_bucket(self, kubectl_get, list_gcloud_buckets):
        list_gcloud_buckets.return_value = ['new-instance']
        kubectl_get.return_value = {
            'spec': {
                'ckanStorageBucket': {
                    'gcloud': 'gs://new-instance'
                }
            }
        }

        expected_result = {
            'instance_id': 'new-instance',
            'ckanStorageBucket': 'gs://new-instance'
        }
        self.assertEqual(gcloud_manager.get_bucket('new-instance'), expected_result)

    @patch('ckan_cloud_operator.providers.storage.gcloud.manager.list_gcloud_buckets')
    @patch('ckan_cloud_operator.providers.storage.gcloud.manager.kubectl.get')
    def test_get_bucket_that_is_not_present_in_gcp(self, kubectl_get, list_gcloud_buckets):
        list_gcloud_buckets.return_value = ['old-instance']

        self.assertIsNone(gcloud_manager.get_bucket('new-instance'))
        kubectl_get.assert_not_called()

    @patch('ckan_cloud_operator.providers.storage.gcloud.manager.list_gcloud_buckets')
    @patch('ckan_cloud_operator.providers.storage.gcloud.manager.kubectl.get')
    def test_get_bucket_when_instance_has_no_gcp_buckets(self, kubectl_get, list_gcloud_buckets):
        list_gcloud_buckets.return_value = ['new-instance']
        kubectl_get.return_value = {
            'spec': {
                'ckanStorageBucket': {
                    's3': 'new-instance'
                }
            }
        }

        self.assertIsNone(gcloud_manager.get_bucket('new-instance'))

    @patch('ckan_cloud_operator.providers.storage.gcloud.manager.kubectl.get')
    def test_list_buckets(self, kubectl_get):
        kubectl_get.return_value = {
            'items': [
                {
                    'spec': {
                        'id': 'new-instance',
                        'ckanStorageBucket': {
                            'gcloud': 'gs://new-instance'
                        }
                    }
                },
                {
                    'spec': {
                        'id': 'old-instance',
                        'ckanStorageBucket': {
                            'gcloud': 'gs://old-instance'
                        }
                    }
                },
                {
                    'spec': {
                        'id': 's3-instance',
                        'ckanStorageBucket': {
                            's3': 's3-bucket'
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
                'ckanStorageBucket': 'gs://new-instance'
            },
            {
                'instance_id': 'old-instance',
                'ckanStorageBucket': 'gs://old-instance'
            }
        ]
        self.assertEqual(gcloud_manager.list_buckets(), expected_result)
        kubectl_get.assert_called_once_with('ckancloudckaninstance')

    @patch('ckan_cloud_operator.providers.storage.gcloud.manager.gcloud_check_output')
    def test_list_gcloud_buckets(self, gcloud_check_output):
        gcloud_check_output.return_value = b"""
gs://new-instance/
gs://old-instance/
gs://another-instance/"""

        expected_result = [
            'new-instance',
            'old-instance',
            'another-instance'
        ]
        self.assertEqual(gcloud_manager.list_gcloud_buckets(), expected_result)

from ckan_cloud_operator import kubectl


class CkanRoutersAnnotations(kubectl.BaseAnnotations):
    """Manage router annotations"""

    @property
    def FLAGS(self):
        """Boolean flags which are saved as annotations on the resource"""
        return [
            'forceCreateAnnotations',
            'letsencryptCloudflareEnabled'
        ]

    @property
    def STATUSES(self):
        """Predefined statuses which are saved as annotations on the resource"""
        return {
            'router': ['created']
        }

    @property
    def SECRET_ANNOTATIONS(self):
        """Sensitive details which are saved in a secret related to the resource"""
        return [
            'LETSENCRYPT_CLOUDFLARE_EMAIL',
            'LETSENCRYPT_CLOUDFLARE_API_KEY'
        ]

    @property
    def JSON_ANNOTATION_PREFIXES(self):
        """flexible annotations encoded to json and permitted using key prefixes"""
        return ['default-root-domain']

    @property
    def RESOURCE_KIND(self):
        return 'CkanCloudRouter'

    def get_secret_labels(self):
        return {'ckan-cloud/annotations-secret': self.resource_id,
                'ckan-cloud/router-name': self.resource_id}

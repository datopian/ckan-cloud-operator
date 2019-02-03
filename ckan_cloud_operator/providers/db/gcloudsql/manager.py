from ckan_cloud_operator.infra import CkanInfra
from ckan_cloud_operator.providers.service import set_provider
from ckan_cloud_operator.providers.db.gcloudsql.constants import PROVIDER_ID
from ckan_cloud_operator.providers.db.constants import PROVIDER_SUBMODULE


def initialize():
    ckan_infra = CkanInfra()
    assert (
        ckan_infra.POSTGRES_HOST and
        ckan_infra.POSTGRES_USER and
        ckan_infra.POSTGRES_PASSWORD and
        ckan_infra.GCLOUD_SQL_INSTANCE_NAME and
        ckan_infra.GCLOUD_SQL_PROJECT
    )


def set_as_main_db():
    set_provider(PROVIDER_SUBMODULE, PROVIDER_ID)


def get_postgres_host_port():
    ckan_infra = CkanInfra()
    return ckan_infra.POSTGRES_HOST, 5432


def get_postgres_admin_credentials():
    ckan_infra = CkanInfra()
    return ckan_infra.POSTGRES_USER, ckan_infra.POSTGRES_PASSWORD, 'postgres'

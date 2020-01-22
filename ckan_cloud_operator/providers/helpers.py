def get_provider_functions(PROVIDER_SUBMODULE, PROVIDER_ID):
    from ckan_cloud_operator.providers import manager as providers_manager

    def _get_resource_name(suffix=None):
        return providers_manager.get_resource_name(PROVIDER_SUBMODULE, PROVIDER_ID,
                                                   suffix=suffix)

    def _get_resource_labels(for_deployment=False):
        return providers_manager.get_resource_labels(PROVIDER_SUBMODULE, PROVIDER_ID,
                                                     for_deployment=for_deployment)

    def _get_resource_annotations(suffix=None):
        return providers_manager.get_resource_annotations(PROVIDER_SUBMODULE, PROVIDER_ID,
                                                          suffix=suffix)

    def _set_provider():
        providers_manager.set_provider(PROVIDER_SUBMODULE, PROVIDER_ID)

    def _config_set(key=None, value=None, values=None, namespace=None, is_secret=False, suffix=None):
        providers_manager.config_set(PROVIDER_SUBMODULE, PROVIDER_ID,
                                     key=key, value=value,
                                     values=values, namespace=namespace, is_secret=is_secret,
                                     suffix=suffix)

    def _config_get(key=None, default=None, required=False, namespace=None, is_secret=False, suffix=None):
        return providers_manager.config_get(PROVIDER_SUBMODULE, PROVIDER_ID,
                                            key=key, default=default, required=required,
                                            namespace=namespace, is_secret=is_secret,
                                            suffix=suffix)

    def _config_interactive_set(default_values, namespace=None, is_secret=False, suffix=None, from_file=False):
        providers_manager.config_interactive_set(PROVIDER_SUBMODULE, PROVIDER_ID,
                                                 default_values, namespace, is_secret, suffix, from_file)

    return (_config_interactive_set, _config_get, _config_set, _set_provider, _get_resource_annotations,
            _get_resource_labels, _get_resource_name)

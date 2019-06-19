import yaml
import copy
from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs


class DeisCkanInstanceSpec(object):

    def __init__(self, spec, override_spec):
        self.spec = copy.deepcopy(spec)
        self.num_applied_overrides = 0
        if override_spec:
            for k, v in override_spec.items():
                if k == 'envvars':
                    logs.info('Applying overrides to instance spec envvars')
                    logs.debug(f"spec['envvars']['overrides'] = {v}")
                    self.spec['envvars']['overrides'] = v
                    self.num_applied_overrides += 1
                elif k in ['db', 'datastore', 'solrCloudCollection']:
                    for kk, vv in v.items():
                        if kk == 'name':
                            print(f'Overriding instance {k} spec name')
                            self.spec.setdefault(k)[kk] = vv
                            self.num_applied_overrides += 1
                        elif k == 'solrCloudCollection' and kk == 'configName':
                            print(f'Overriding instance solr spec config name')
                            self.spec.setdefault(k)[kk] = vv
                            self.num_applied_overrides += 1
                        elif k in ['db', 'datastore'] and kk == 'no-db-proxy':
                            print(f'Overriding instance {k} spec {kk}={vv}')
                            self.spec[k][kk] = vv
                            self.num_applied_overrides += 1
                        else:
                            raise NotImplementedError(f'Unsupported {k} spec override: {kk}={vv}')
                else:
                    raise NotImplementedError(f'Unsupported instance spec override: {k}: {v}')
        self._validate()
        self.envvars = self.spec['envvars']
        self.db = self.spec['db']
        self.datastore = self.spec['datastore']
        self.solrCloudCollection = self.spec['solrCloudCollection']
        self.storage = self.spec['storage']

    def _validate(self):
        spec = self.spec
        for k, v in spec.items():
            if k == 'ckanPodSpec':
                assert type(v) == dict
            elif k == 'ckanContainerSpec':
                assert type(v) == dict
                if v.get('image'):
                    assert not v.get('imageFromGitlab')
                elif v.get('imageFromGitlab'):
                    assert not v.get('image')
                else:
                    raise ValueError(f'Invalid ckanContainerSpec: {v}')
            elif k in ['db', 'datastore']:
                assert type(v) == dict
                assert v['name']
                for kk, vv in v.items():
                    if kk == 'name':
                        assert type(vv) == str
                    elif kk == 'importGcloudSqlDumpUrl':
                        assert type(vv) == str
                    elif kk == 'fromDeisInstance':
                        assert type(vv) == str
                    elif kk == 'fromDbMigration':
                        assert type(vv) == str
                    elif kk == 'no-db-proxy':
                        assert vv in ['yes', 'no', ''], 'only valid values for no-db-proxy are: "yes", "no", ""'
                    elif kk == 'dbPrefix':
                        assert not vv or type(vv) == str
                    else:
                        raise ValueError(f'Invalid db spec attribute: {kk}={vv}')
            elif k == 'solrCloudCollection':
                assert type(v) == dict
                assert v['name']
                for kk, vv in v.items():
                    if kk == 'name':
                        assert type(vv) == str
                    elif kk == 'configName':
                        assert type(vv) == str and not v.get('configFromDeisInstance')
                    elif kk == 'configFromDeisInstance':
                        assert type(vv) == str and not v.get('configName')
                    else:
                        raise ValueError(f'Invalid solr cloud collection spec attribute: {kk}={vv}')
            elif k == 'envvars':
                assert type(v) == dict
                for kk, vv in v.items():
                    if kk == 'fromSecret':
                        assert type(vv) == str and not v.get('fromGitlab')
                    elif kk == 'overrides':
                        assert type(vv) == dict
                    elif kk == 'fromGitlab':
                        assert type(vv) == str and not v.get('fromSecret')
                    else:
                        raise ValueError(f'Invalid envvars spec attribute: {kk}={vv}')
                assert v.get('fromSecret') or v.get('fromGitlab')
            elif k == 'ckan':
                assert type(v) == dict
                for kk, vv in v.items():
                    if kk == 'init':
                        assert type(vv) == list
                    else:
                        raise ValueError(f'Invalid ckan spec attribute: {kk}={vv}')
            elif k == 'storage':
                assert type(v) == dict
                for kk, vv in v.items():
                    if kk == 'path':
                        assert type(vv) == str and len(vv) > 6, f'Invalid storage path: {vv}'
                    else:
                        raise ValueError(f'Invalid storage spec attribute: {kk}={vv}')
            elif k == 'routes':
                assert type(v) == dict
                for kk, vv in v.items():
                    if kk == 'target-port':
                        assert type(vv) == int and vv > 0, f'invalid target-port: {vv}'
                    else:
                        raise ValueError(f'Invalid routers spec attribute: {kk}={vv}')
            elif k == 'imagePullSecrets':
                assert type(v) == list
            else:
                raise ValueError(f'Invalid spec attribute: {k}={v}')
        assert spec['db']['name'] != spec['datastore']['name']

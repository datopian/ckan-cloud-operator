import yaml
import copy
from ckan_cloud_operator import kubectl


class DeisCkanInstanceSpec(object):

    def __init__(self, spec, override_spec):
        self.spec = copy.deepcopy(spec)
        self.num_applied_overrides = 0
        if override_spec:
            for k, v in override_spec.items():
                if k == 'envvars':
                    print('Applying overrides to instance spec envvars')
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
                        else:
                            raise NotImplementedError(f'Unsupported {k} spec override: {kk}={vv}')
                else:
                    raise NotImplementedError(f'Unsupported instance spec override: {k}: {v}')
        self._validate()
        self.envvars = spec['envvars']
        self.db = spec['db']
        self.datastore = spec['datastore']
        self.solrCloudCollection = spec['solrCloudCollection']

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
                        assert type(vv) == str and not v.get('fromDeisInstance')
                    elif kk == 'fromDeisInstance':
                        assert type(vv) == str and not v.get('importGcloudSqlDumpUrl')
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
            else:
                raise ValueError(f'Invalid spec attribute: {k}={v}')
        assert spec['db']['name'] != spec['datastore']['name']

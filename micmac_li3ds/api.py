import requests
import os
import json
import getpass

os.environ['NO_PROXY'] = 'localhost'


class Api(object):

    def __init__(self, api_url, api_key, log, indent):
        self.api_url = None
        self.headers = None
        self.staging = None
        self.log = log
        self.indent = indent
        self.ids = {
            'transfo': ['name', 'source', 'target'],
            'transfos/type': ['name'],
            'transfotree': ['name', 'transfos'],
            'referential': ['name', 'sensor'],
            'sensor': ['name'],
            'platform': ['name'],
            'project': ['name'],
            'session': ['name', 'project', 'platform'],
            'datasource': ['session', 'referential'],
            'platforms/{id}/config': ['name'],
        }

        if api_url:
            if not api_key:
                err = 'Error: no api key provided'
                raise ValueError(err)
            self.api_url = api_url.rstrip('/')
            self.headers = {
                'Accept': 'application/json',
                'X-API-KEY': api_key
                }
        else:
            self.log.info("# Staging mode")
            self.log.info("use -u/-k options to provide an api url and key).")
            self.staging = {
                'transfo': [],
                'transfos/type': [],
                'transfotree': [],
                'referential': [],
                'sensor': [],
                'platform': [],
                'project': [],
                'session': [],
                'datasource': [],
                'platforms/{id}/config': [],
            }

    def create_object(self, typ, obj, parent={}):
        if self.staging:
            obj['id'] = len(self.staging[typ])
            self.staging[typ].append(obj)
            return obj

        url = self.api_url + '/{}s/'.format(typ.format(**parent))
        resp = requests.post(url, json=obj, headers=self.headers)
        if resp.status_code == 201:
            objs = resp.json()
            return objs[0]
        err = 'Adding object failed (status code: {})'.format(
              resp.status_code)
        raise RuntimeError(err)

    def get_object_by_id(self, typ, obj_id, parent={}):
        if self.staging:
            objs = self.staging[typ]
            return objs[obj_id] if obj_id < len(objs) else None

        url = self.api_url + '/{}s/{:d}/'.format(typ.format(**parent), obj_id)
        resp = requests.get(url, headers=self.headers)
        if resp.status_code == 200:
            objs = resp.json()
            return objs[0]
        if resp.status_code == 404:
            return None
        err = 'Getting object failed (status code: {})'.format(
              resp.status_code)
        raise RuntimeError(err)

    def get_object_by_name(self, typ, obj_name, parent={}):
        if self.staging:
            objs = self.staging[typ]
            obj = [obj for obj in objs if obj.name == obj_name]
            return obj[0] if obj else None

        url = self.api_url + '/{}s/'.format(typ.format(**parent))
        resp = requests.get(url, headers=self.headers)
        if resp.status_code == 200:
            objs = resp.json()
            try:
                obj = next(o for o in objs if o['name'] == obj_name)
            except StopIteration:
                return None
            return obj
        err = 'Getting object failed (status code: {})'.format(
              resp.status_code)
        raise RuntimeError(err)

    def get_object_by_dict(self, typ, dict_, parent={}):
        if self.staging:
            objs = self.staging[typ]
            obj = [o for o in objs if all(
                    o[k] == v for k, v in dict_.items() if k in o)]
            return obj[0] if obj else None

        url = self.api_url + '/{}s/'.format(typ.format(**parent))
        resp = requests.get(url, headers=self.headers)
        if resp.status_code == 200:
            objs = resp.json()
            try:
                obj = next(o for o in objs if all(
                    o[k] == v for k, v in dict_.items() if k in o))
            except StopIteration:
                return None
            return obj
        err = 'Getting object failed (status code: {})'.format(
              resp.status_code)
        raise RuntimeError(err)

    def get_objects(self, typ, parent={}):
        if self.staging:
            return self.staging[typ]

        url = self.api_url + '/{}s/'.format(typ.format(**parent))
        resp = requests.get(url, headers=self.headers)
        if resp.status_code == 200:
            objs = resp.json()
            return objs
        err = 'Getting object failed (status code: {})'.format(
              resp.status_code)
        raise RuntimeError(err)

    def get_or_create_object(self, typ, obj, parent={}):
        if 'id' in obj:
            # look up by id, raise an error upon lookup failure
            # or value mismatch for specified keys
            got = self.get_object_by_id(typ, obj['id'], parent)
            if not got:
                err = 'Error: {} with id {:d} not in db'.format(typ, obj['id'])
                raise RuntimeError(err)

            all_keys = set(obj.keys()).intersection(got.keys())
            for key in all_keys:
                if obj[key] != got[key]:
                    err = 'Error: "{}" mismatch in {} with id {:d} ' \
                          '("{}" vs "{}")' \
                          .format(key, typ, obj['id'], obj[key], got[key])
                    raise RuntimeError(err)

            return got, '='

        if not all(k in obj for k in self.ids[typ]):
            err = 'Error: {} objects should specify ' \
                  'either their (id) or ({}) {}' \
                  .format(typ, ','.join(self.ids[typ]), obj)
            raise RuntimeError(err)

        # look up by dict, and raise an error upon mismatch
        dict_ = {k: obj[k] for k in self.ids[typ]}
        got = self.get_object_by_dict(typ, dict_, parent)
        if got:
            # raise an error upon value mismatch for specified keys
            all_keys = set(obj.keys()).intersection(got.keys())
            for key in all_keys:
                if obj[key] != got[key]:
                    err = 'Error: "{}" mismatch in {} "{}" ' \
                          '("{}" vs "{}")' \
                          .format(key, typ, obj['name'], obj[key], got[key])
                    raise RuntimeError(err)

            return got, '?'

        # no successfull lookup by id or by name, create a new object
        got = self.create_object(typ, obj, parent)
        return got, '+'

    def get_or_create(self, typ, obj, parent={}):
        obj = {k: v for k, v in obj.items() if v is not None}
        self.log.debug("\n-->"+json.dumps(obj, indent=self.indent))
        obj, code = self.get_or_create_object(typ, obj, parent)
        self.log.debug("<--"+json.dumps(obj, indent=self.indent))
        info = '{} ({}) {} [{}] {}'.format(
            code, obj['id'], typ.format(**parent),
            ', '.join([str(obj[k]) for k in self.ids[typ] if k in obj]),
            obj.get('uri', ''))
        self.log.info(info)
        return obj

    def get_or_create_sensor(self, name, sensor_type, *, sensor_id=None,
                             description='', serial='', specs={}):
        sensor = {
            'id': sensor_id,
            'name': name,
            'type': sensor_type,
            'description': description,
            'serial_number': serial,
            'specifications': {k: v for k, v in specs.items() if v is not None}
        }
        return self.get_or_create('sensor', sensor)

    def get_or_create_referential(self, name, sensor, *, referential_id=None,
                                  description='', root=False, srid=0):
        referential = {
            'id': referential_id,
            'name': name,
            'sensor': sensor['id'],
            'description': description,
            'root': root,
            'srid': srid,
        }
        return self.get_or_create('referential', referential)

    def get_or_create_transfo(self, name, type_name, source, target,
                              parameters, *, transfo_id=None, type_id=None,
                              description='', reverse=False, tdate=None,
                              validity_start=None, validity_end=None):
        transfo_type = {
            'id': type_id,
            'name': type_name,
            'description': type_name,
            'func_signature': sorted(list(parameters.keys())),
        }
        transfo_type = self.get_or_create('transfos/type', transfo_type)
        transfo = {
            'id': transfo_id,
            'name': name,
            'source': target['id'] if reverse else source['id'],
            'target': source['id'] if reverse else target['id'],
            'transfo_type': transfo_type['id'],
            'description': description,
            'parameters': parameters,
            'tdate': tdate,
            'validity_start': validity_start,
            'validity_end': validity_end,
        }
        return self.get_or_create('transfo', transfo)

    def get_or_create_transfotree(self, name, transfos,
                                  *, transfotree_id=None, owner=None,
                                  isdefault=True, sensor_connections=False):
        transfotree = {
            'id': transfotree_id,
            'name': name,
            'transfos':  sorted([t['id'] for t in transfos]),
            'owner': owner or getpass.getuser(),
            'isdefault': isdefault,
            'sensor_connections': sensor_connections,
        }
        return self.get_or_create('transfotree', transfotree)

    def get_or_create_project(self, name,
                              *, project_id=None, extent=None, timezone=None):
        project = {
            'id': project_id,
            'name': name,
            'extent': extent,
            'timezone': timezone or "Europe/Paris",
        }
        return self.get_or_create('project', project)

    def get_or_create_platform(self, name,
                               *, platform_id=None, description='',
                               start_time=None, end_time=None):
        platform = {
            'id': platform_id,
            'name': name,
            'description': description,
            'start_time': start_time,
            'end_time': end_time,
        }
        return self.get_or_create('platform', platform)

    def get_or_create_session(self, name, project, platform,
                              *, session_id=None,
                              start_time=None, end_time=None):
        session = {
            'id': session_id,
            'name': name,
            'project': project['id'],
            'platform': platform['id'],
            'start_time': start_time,
            'end_time': end_time,
        }
        return self.get_or_create('session', session)

    def get_or_create_datasource(self, session, referential, uri,
                                 *, datasource_id=None):
        datasource = {
            'id': datasource_id,
            'session': session['id'],
            'referential': referential['id'],
            'uri': uri.strip(),
        }
        return self.get_or_create('datasource', datasource)

    def get_or_create_config(self, name, platform, transfotrees,
                             *, config_id=None, owner=None):
        config = {
            'id': config_id,
            'name': name,
            'owner': owner or getpass.getuser(),
            'transfo_trees':  sorted([t['id'] for t in transfotrees]),
        }
        return self.get_or_create('platforms/{id}/config', config, platform)

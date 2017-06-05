import requests
import json
import getpass


def add_arguments(parser):
    group = parser.add_argument_group(
        'API arguments',
        'API connection settings, dry run in staging mode if not provided')
    group.add_argument(
        '--api-url', '-u',
        help='the li3ds API URL (optional)')
    group.add_argument(
        '--api-key', '-k',
        help='the li3ds API key (required if --api-url is provided)')
    group.add_argument(
        '--no-proxy', action='store_true',
        help='disable all proxy settings')
    parser.add_argument(
       '--indent', type=int,
       help='number of spaces for pretty print indenting')
    parser.add_argument(
       '--owner', '-o',
       help='the data owner (optional, default is unix username)')


class ApiServer(object):

    def __init__(self, args, log):
        self.api_url = args.api_url
        self.headers = None
        self.proxies = None
        self.staging = None
        self.log = log
        self.indent = args.indent
        self.ids = {
            'transfo': ('name', 'source', 'target'),
            'transfos/type': ('name',),
            'transfotree': ('name', 'transfos'),
            'referential': ('name', 'sensor'),
            'sensor': ('name',),
            'platform': ('name',),
            'project': ('name',),
            'session': ('name', 'project', 'platform'),
            'datasource': ('uri', 'session', 'referential'),
            'platforms/{id}/config': ('name',),
        }

        if args.api_url:
            if not args.api_key:
                err = 'Error: no api key provided'
                raise ValueError(err)
            self.api_url = args.api_url.rstrip('/')
            self.headers = {
                'Accept': 'application/json',
                'X-API-KEY': args.api_key
                }
            self.proxies = {'http': None} if args.no_proxy else None
        else:
            self.log.info('! Staging mode (use -u/-k options '
                          'to provide an api url and key)')
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
        resp = requests.post(
            url, json=obj, headers=self.headers, proxies=self.proxies)
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
        resp = requests.get(url, headers=self.headers, proxies=self.proxies)
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
        resp = requests.get(url, headers=self.headers, proxies=self.proxies)
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
        resp = requests.get(url, headers=self.headers, proxies=self.proxies)
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
        resp = requests.get(url, headers=self.headers, proxies=self.proxies)
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
            all_keys.discard('description')
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
            all_keys.discard('description')
            for key in all_keys:
                if obj[key] != got[key]:
                    display_name = obj.get('name', got.get('id'))
                    err = 'Error: "{}" mismatch in {} "{}" ' \
                          '("{}" vs "{}")' \
                          .format(key, typ, display_name, obj[key], got[key])
                    raise RuntimeError(err)

            return got, '?'

        # no successfull lookup by id or by name, create a new object
        got = self.create_object(typ, obj, parent)
        return got, '+'

    def get_or_create(self, typ, obj, parent={}):
        self.log.debug('')
        if not self.staging:
            self.log.debug("-->"+json.dumps(obj, indent=self.indent))
        obj, code = self.get_or_create_object(typ, obj, parent)
        self.log.debug("<--"+json.dumps(obj, indent=self.indent))
        info = '{} ({}) {} [{}] {}'.format(
            code, obj.get('id', '?'), typ.format(**parent),
            ', '.join([str(obj[k]) for k in self.ids[typ] if k in obj]),
            obj.get('uri', ''))
        self.log.info(info)
        return obj


class ApiObjs:
    def get_or_create(self, api):
        for obj in self.__dict__.values():
            if isinstance(obj, ApiObj):
                obj.get_or_create(api)


class ApiObj:
    def __init__(self, type_, keys, obj=None, **kwarg):
        self.published = False
        self.type_ = type_
        self.keys = keys
        self.obj = {}
        self.objs = {}
        self.arrays = {}
        self.parent = noobj
        if obj:
            self.update(**obj)
        self.update(**kwarg)

    def get_or_create(self, api):
        if self.published:
            return self

        for key in self.objs:
            self.obj[key] = self.objs[key].get_or_create(api).obj['id']

        for key in self.arrays:
            ids = [obj.get_or_create(api).obj['id'] for obj in self.arrays[key]
                   if obj is not noobj]
            self.obj[key] = sorted(ids)

        obj = api.get_or_create(self.type_, self.obj, self.parent.obj)
        self.obj = obj
        self.published = True
        return self

    def update(self, **kwarg):
        obj = ApiObj.normalize_obj(kwarg)
        for key in obj:
            if key not in self.keys:
                err = 'Error: {} is invalid in {}'.format(key, self.type_)
                raise RuntimeError(err)
        self.obj.update(obj)
        return self

    def normalize_obj(obj):
        if isinstance(obj, dict):
            return {k: ApiObj.normalize_obj(v) for k, v in obj.items()
                    if v is not None}
        return {} if obj is None else obj

    def __bool__(self):
        return True


class _NoObj(ApiObj):
    obj = {}
    type_ = 'noobj'

    def __init__(self):
        pass

    def get_or_create(self, api):
        return self

    def __bool__(self):
        return False


noobj = _NoObj()


class Sensor(ApiObj):
    def __init__(self, obj=None, **kwarg):
        keys = ('id', 'name', 'type', 'description',
                'serial_number', 'specifications')
        super().__init__('sensor', keys, obj, **kwarg)
        self.obj.setdefault('serial_number', '')


class Referential(ApiObj):
    def __init__(self, sensor, obj=None, **kwarg):
        keys = ('id', 'name', 'description', 'srid')
        super().__init__('referential', keys, obj, **kwarg)
        self.objs = {'sensor': sensor}


class TransfoType(ApiObj):
    def __init__(self, obj=None, **kwarg):
        keys = ('id', 'name', 'description', 'func_signature')
        super().__init__('transfos/type', keys, obj, **kwarg)

    def update(self, **kwarg):
        func_signature = kwarg.get('func_signature')
        if func_signature:
            kwarg['func_signature'] = sorted(func_signature)
        return super().update(**kwarg)


class Transfo(ApiObj):
    def __init__(self, source, target, obj=None, reverse=False,
                 transfo_type=noobj, type_id=None, type_name=None,
                 type_description=None, func_signature=None, **kwarg):
        if func_signature and transfo_type:
            transfo_type.obj = transfo_type.obj.copy()
            transfo_type.obj['func_signature'] = func_signature

        keys = ('id', 'name', 'description', 'parameters', 'tdate',
                'validity_start', 'validity_end')
        if reverse:
            source, target = target, source
        super().__init__('transfo', keys, obj, **kwarg)

        if transfo_type is noobj:
            parameters = self.obj.get('parameters')
            keys = list(parameters.keys()) if parameters else None
            keys = func_signature or keys
            transfo_type = TransfoType(
                id=type_id,
                name=type_name,
                description=type_description,
                func_signature=keys,
            )
        self.objs = {
            'source': source,
            'target': target,
            'transfo_type': transfo_type
        }


class Transfotree(ApiObj):
    def __init__(self, transfos, obj=None, **kwarg):
        keys = ('id', 'name', 'owner', 'sensor_connections')
        super().__init__('transfotree', keys, obj, **kwarg)
        self.obj.setdefault('sensor_connections', False)
        self.obj.setdefault('owner', getpass.getuser())
        self.arrays = {'transfos': transfos}


class Project(ApiObj):
    def __init__(self, obj=None, **kwarg):
        keys = ('id', 'name', 'extent', 'timezone')
        super().__init__('project', keys, obj, **kwarg)
        self.obj.setdefault('timezone', 'Europe/Paris')


class Platform(ApiObj):
    def __init__(self, obj=None, **kwarg):
        keys = ('id', 'name', 'description', 'start_time', 'end_time')
        super().__init__('platform', keys, obj, **kwarg)


class Session(ApiObj):
    def __init__(self, project, platform, obj=None, **kwarg):
        keys = ('id', 'name', 'start_time', 'end_time')
        super().__init__('session', keys, obj, **kwarg)
        self.objs = {'project': project, 'platform': platform}


class Datasource(ApiObj):
    def __init__(self, session, referential, obj=None, **kwarg):
        keys = ('id', 'type', 'uri', 'bounds', 'capture_start', 'capture_end')
        super().__init__('datasource', keys, obj, **kwarg)
        self.objs = {'session': session, 'referential': referential}

    def update(self, **kwarg):
        uri = kwarg.get('uri')
        if uri:
            kwarg['uri'] = uri.strip()
        super().update(**kwarg)


class Config(ApiObj):
    def __init__(self, platform, transfotrees, obj=None, **kwarg):
        keys = ('id', 'name', 'description', 'root', 'srid')
        super().__init__('platforms/{id}/config', keys, obj, **kwarg)
        self.objs = {'platform': platform}
        self.arrays = {'transfo_trees': transfotrees}
        self.obj.setdefault('owner', getpass.getuser())
        self.parent = platform


def update_obj(args, metadata, obj, type_):
    noname = ('datasource',)
    nodesc = ('datasource', 'transfotree', 'project', 'session')
    if all(not type_.startswith(s) for s in noname):
        obj.setdefault('name', '{basename}')
    if all(not type_.startswith(s) for s in nodesc):
        obj.setdefault('description', 'Imported from "{basename}"')
    if type_ in args:
        obj.update({k: v for k, v in args[type_].items() if v})
    metadata_no_none = {k: v for k, v in metadata.items() if v is not None}
    for key in list(obj.keys()):
        if obj[key] and isinstance(obj[key], str):
            try:
                obj[key] = obj[key].format(**metadata_no_none)
            except KeyError as e:
                # obj[key] contain replacements fields that have no
                # corresponding keys in metadata_no_none, raise an
                # error if key is not in the original metadata,
                # otherwise just delete the key from the object
                # and continue
                if e.args[0] not in metadata:
                    err = 'metadata {} not available for {}/{}="{}"'
                    raise KeyError(err.format(e.args[0], type_, key, obj[key]))
                del obj[key]


def isoformat(date):
    return date.isoformat() if date else None

import os
import logging

from cliff.command import Command

from . import api
from . import xmlutil


class ImportBlinis(Command):
    """ import a blinis file

        Create a sensor group and corresponding referentials and transfos.
    """

    log = logging.getLogger(__name__)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_parser(self, prog_name):
        self.log.debug(prog_name)
        parser = super().get_parser(prog_name)
        api.add_arguments(parser)
        parser.add_argument(
            '--sensor-id', '-i',
            type=int,
            help='the camera sensor id (optional)')
        parser.add_argument(
            '--sensor', '-s',
            help='the camera sensor name (optional)')
        parser.add_argument(
            '--transfotree',
            help='the transfotree name (optional)')
        parser.add_argument(
            '--transfo', '-t',
            help='the transfo basename (optional)')
        parser.add_argument(
            '--calibration', '-d',
            help='the calibration datetime (optional')
        parser.add_argument(
            '--validity-start',
            help='validity start date for transfos (optional, '
                 'default is valid since always)')
        parser.add_argument(
            '--validity-end',
            help='validity end date for transfos (optional, '
                 'default is valid until forever)')
        parser.add_argument(
            'filename', nargs='+',
            help='the list of blinis filenames')
        return parser

    def take_action(self, parsed_args):
        """
        Create or update sensor groups.
        """
        server = api.ApiServer(parsed_args, self.log)

        args = {
            'sensor': {
                'name': parsed_args.sensor,
                'id': parsed_args.sensor_id,
            },
            'transfo': {
                'name': parsed_args.transfo,
                'tdate': parsed_args.calibration,
                'validity_start': parsed_args.validity_start,
                'validity_end': parsed_args.validity_end,
            },
            'transfotree': {
                    'name': parsed_args.transfotree,
                    'owner': parsed_args.owner,
            },
        }
        for filename in parsed_args.filename:
            self.log.info('Importing {}'.format(filename))
            ApiObjs(args, filename).get_or_create(server)
            self.log.info('Success!\n')


class ApiObjs(api.ApiObjs):
    def __init__(self, args, filename):
        root = xmlutil.root(filename, 'StructBlockCam')
        nodes = xmlutil.children(root, 'LiaisonsSHC/ParamOrientSHC')

        metadata = {
            'basename': os.path.basename(filename),
            'KeyIm2TimeCam': xmlutil.findtext(root, 'KeyIm2TimeCam'),
        }

        sensor = {'type': 'group'}
        referential = {'name': 'base'}
        transfotree = {}
        api.update_obj(args, metadata, sensor, 'sensor')
        api.update_obj(args, metadata, referential, 'referential')
        api.update_obj(args, metadata, transfotree, 'transfotree')
        self.sensor = api.Sensor(sensor)
        self.base = api.Referential(self.sensor, referential)

        self.referentials = []
        self.transfos = []
        for node in nodes:
            metadata['IdGrp'] = xmlutil.findtext(node, 'IdGrp')
            referential = {'name': '{IdGrp}'}
            transfo = {'name': '{IdGrp}'}
            api.update_obj(args, metadata, referential, 'referential')
            api.update_obj(args, metadata, transfo, 'transfo')
            referential = api.Referential(self.sensor, referential)
            transfo = transfo_grp(self.base, referential, transfo, node)
            self.transfos.append(transfo)
            self.referentials.append(referential)

        self.transfotree = api.Transfotree(self.transfos, transfotree)
        super().__init__()


def transfo_grp(source, target, transfo, node):
    matrix = []
    p = xmlutil.child_floats_split(node, 'Vecteur')
    for i, l in enumerate(('Rot/L1', 'Rot/L2', 'Rot/L3')):
        matrix.extend(xmlutil.child_floats_split(node, l))
        matrix.append(p[i])

    return api.Transfo(
        source, target, transfo,
        type_name='affine_mat4x3',
        parameters={'mat4x3': matrix},
    )

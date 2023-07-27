import json
import subprocess

from common import types, utils
from deploy.node_base import Node
from flask_restful import reqparse, Resource


class DeployCount(Node):
    def get_nodes_from_request(self):
        parser = reqparse.RequestParser()
        fields = [
            ('cephCopyNumDefault', int, True,
             'The cephCopyNumDefault field does not exist'),
            ('cephServiceFlag', bool, True,
             'The cephServiceFlag field does not exist'),
            ('localServiceFlag', bool, True,
             'The localServiceFlag field does not exist'),
            ('nodes', list, True, 'The nodes field does not exist'),
            ('serviceType', list, True, 'The serviceType field does not exist'),
            ('storages', list, False, 'The storages field does not exist')
        ]

        for field, field_type, required, error_msg in fields:
            parser.add_argument(field, required=required,
                                location='json', type=field_type, help=error_msg)

        return parser.parse_args()


# 通用pg计算
class ReckRecommendConfigCommon(Resource, DeployCount):
    def __init__(self):
        self.ceph_cache_storage = []
        self.ceph_data_storage = []
        self.local_storage = []
        self.share_storage = []
        self.sys_storage = None

    def post(self):
        nodes_info = self.get_nodes_from_request()
        ceph_copy_num_default = nodes_info['cephCopyNumDefault']
        ceph_service_flag = nodes_info['cephServiceFlag']
        local_service_flag = nodes_info['localServiceFlag']

        service_type = nodes_info['serviceType']
        nodes = nodes_info['nodes']
        storage_list = nodes_info.get('storages', [])
        self.classify_disks(storage_list)

        data = {}
        node_num = len(nodes)
        if ceph_service_flag:
            if node_num == 1 and len(self.ceph_data_storage) == 1:
                ceph_copy_num_default = 1
            pg_all = len(nodes) * len(self.ceph_data_storage) * 100
            data = self.calculate_ceph_storage(
                node_num, service_type, ceph_copy_num_default, pg_all)

        if local_service_flag:
            local_storage_data = self.calculate_local_storage()
            data['shareSizeMax'] = local_storage_data['share_size_max']
            data['localSizeMax'] = local_storage_data['local_size_max']

        if len(service_type) >= 2:
            total_memory = nodes[0]['memTotal']
            osd_num = len(self.ceph_data_storage) / node_num
            data['memorySizeMax'] = self.calculate_memory_free_size(
                total_memory, osd_num)

        return types.DataModel().model(code=0, data=data)

    def classify_disks(self, storage_list):
        for storage in storage_list:
            purpose = storage['purpose']
            if purpose == 'CEPH_CACHE':
                self.ceph_cache_storage.append(storage)
            elif purpose == 'CEPH_DATA':
                self.ceph_data_storage.append(storage)
            elif purpose == 'LOCAL_DATA':
                self.local_storage.append(storage)
            elif purpose == 'LOCAL_SHARE_DATA':
                self.local_storage.append(storage)
            elif purpose == 'SHARE_DATA':
                self.share_storage.append(storage)
            elif purpose == 'SYSTEM':
                self.sys_storage = storage

    def calculate_ceph_storage(self, node_num, service_type, ceph_copy_num_default, pg_all):
        volume_pgp = 0.45
        cephfs_pgp = 0.45

        if len(service_type) == 1 and service_type[0] == "VDI":
            volume_pgp = 0.8
            cephfs_pgp = 0.1

        image_pgp = 0.1
        images_pool = utils.get_near_power(
            int(pg_all * image_pgp / ceph_copy_num_default))
        volume_pool = utils.get_near_power(
            int(pg_all * volume_pgp / ceph_copy_num_default))
        cephfs_pool = utils.get_near_power(
            int(pg_all * cephfs_pgp / ceph_copy_num_default))
        ceph_data_sum = sum(utils.storage_type_format(
            storage['size']) for storage in self.ceph_data_storage)
        ceph_max_size = f'{str(round(ceph_data_sum * 0.8 * node_num / ceph_copy_num_default, 2) )}GB'

        return {
            "commonCustomCeph": {
                "cephCopyNumDefault": ceph_copy_num_default
            },
            "commonCustomPool": {
                "cephfsPoolPgNum": cephfs_pool,
                "cephfsPoolPgpNum": cephfs_pool,
                "imagePoolPgNum": images_pool,
                "imagePoolPgpNum": images_pool,
                "volumePoolPgNum": volume_pool,
                "volumePoolPgpNum": volume_pool
            },
            "cephSizeMax": ceph_max_size
        }

    def calculate_local_storage(self):
        local_data_sum = 0
        share_data_sum = 0

        if self.local_storage:
            local_data_sum = sum(utils.storage_type_format(
                storage['size']) for storage in self.local_storage)

        if self.share_storage:
            share_data_sum = sum(utils.storage_type_format(
                storage['size']) for storage in self.share_storage)

        if local_data_sum == 0 and share_data_sum == 0:
            local_data_sum = self.get_system_disk_free_size()

        return {
            'share_size_max': f'{share_data_sum}GB',
            'local_size_max': f'{local_data_sum}GB',
        }

    def calculate_memory_free_size(self, total_memory, osd_num):
        reserves = 32768
        osd_reserves = (osd_num + 2) * 2048 if osd_num > 0 else 0

        if total_memory >= 61440:
            available_memory = total_memory - reserves - osd_reserves
        elif total_memory >= 30720:
            available_memory = 16384
        elif total_memory >= 10240:
            available_memory = 8192
        elif total_memory > 8000:
            available_memory = 4096
        else:
            available_memory = 2048

        available_memory_gb = round(available_memory / 1024, 2)

        return f'{available_memory_gb}GB'

    def get_system_disk_free_size(self):
        root_size = utils.storage_type_format(self.get_root_mountpoint_size())
        sys_storage_size = utils.storage_type_format(self.sys_storage['size'])

        return round(sys_storage_size - root_size - 10, 2)

    def get_root_mountpoint_size(self):
        command = ['lsblk', '--output', 'SIZE,MOUNTPOINT', '--json', '--paths']
        output = subprocess.check_output(command).decode('utf-8')
        parsed_output = json.loads(output)

        devices = parsed_output['blockdevices']
        for device in devices:
            if device.get('mountpoint') == '/':
                return device['size']

        return '200G'


# 个性化pg计算
class ShowRecommendConfig(ReckRecommendConfigCommon):
    def post(self):
        nodes_info = self.get_nodes_from_request()
        ceph_copy_num_default = nodes_info["cephCopyNumDefault"]
        ceph_service_flag = nodes_info['cephServiceFlag']
        local_service_flag = nodes_info['localServiceFlag']
        service_type = nodes_info["serviceType"]
        nodes = nodes_info["nodes"]
        for node in nodes:
            self.classify_disks(node['storages'])

        data = {}
        if ceph_service_flag:
            if len(nodes) == 1 and len(self.ceph_data_storage) == 1:
                ceph_copy_num_default = 1
            pg_all = len(nodes) * len(self.ceph_data_storage) * 100
            data = self.calculate_ceph_storage(
                len(nodes), service_type, ceph_copy_num_default, pg_all)

        if local_service_flag:
            local_storage_data = self.calculate_node_local_storage(nodes)
            data['shareSizeMax'] = local_storage_data['share_size_max']
            data['localSizeMax'] = local_storage_data['local_size_max']

        if len(service_type) >= 2:
            data['memorySizeMax'] = self.get_node_memory_free_size(nodes)

        return types.DataModel().model(code=0, data=data)

    def calculate_node_local_storage(self, nodes):
        local_data_sum = []
        share_data_sum = []

        local_size = 0
        share_size = 0

        if self.local_storage:
            for node in nodes:
                local_size = sum(
                    utils.storage_type_format(storage['size'])
                    for storage in node['storages']
                    if storage['purpose'] == 'LOCAL_DATA' or storage['purpose'] == 'LOCAL_SHARE_DATA'
                )
                local_data_sum.append(f'{local_size}GB')
        else:
            for node in nodes:
                local_data_sum.append('0GB')

        if self.share_storage:
            for node in nodes:
                share_size = sum(
                    utils.storage_type_format(storage['size'])
                    for storage in node['storages']
                    if storage['purpose'] == 'SHARE_DATA')

                share_data_sum.append(f'{share_size}GB')
        else:
            for node in nodes:
                share_data_sum.append('0GB')

        if self.local_storage == [] and self.share_storage == []:
            for node in nodes:
                local_data_sum.append(self.get_system_disk_free_size())
                share_data_sum.append('0GB')

        return {
            'share_size_max': share_data_sum,
            'local_size_max': local_data_sum
        }

    def get_node_memory_free_size(self, nodes):
        node_memory_free_info = []
        for node in nodes:
            total_memory = node['memTotal']
            osd_num = 0
            if self.ceph_data_storage:
                for storage in node['storages']:
                    if storage['purpose'] == 'CEPH_DATA':
                        osd_num += 1

            node_memory_free_info.append(
                self.calculate_memory_free_size(total_memory, osd_num))

        return node_memory_free_info

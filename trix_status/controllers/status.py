from trix_status import AbstractStatus
from trix_status.out import Out
from trix_status.utils import run_cmd
from trix_status.config import category
import os
import logging
import xml.etree.ElementTree as ET


class Status(AbstractStatus):

    def __init__(self, args):
        module_name = self.__module__ + "." + type(self).__name__
        self.log = logging.getLogger(module_name)
        self.args = args
        self.hosts = [os.uname()[1]]
        self.services = []

    def _get_ha(self):
        rc, stdout, stderr, exc = run_cmd("crm_mon -r -1 -X")
        if rc == 127:  # command not found
            return False
        if rc == 107:  # stopped?
            return False
        try:
            xml_root = ET.fromstring(stdout)
        except ET.ParseError:
            return False
        if xml_root.tag != 'crm_mon':
            return False
        ha_status = {'nodes': [], 'resources': []}
        xml_nodes = xml_root.find('nodes')
        for container  in xml_root.find('resources'):
            for resource in container.findall('resource'):
                xml_running_on = resource.findall('node')
                running_on = []
                for node in xml_running_on:
                    running_on.append(node.attrib)
                res = resource.attrib.copy()
                res['running_on'] = running_on
                ha_status['resources'].append(res)

        if xml_nodes is None:
            return False
        for elem in xml_nodes:
            attr = elem.attrib
            ha_status['nodes'].append(attr)
            hostname = attr['name']
            if hostname not in self.hosts:
                self.hosts.append(hostname)
        return ha_status

    def out_ha_status(self, ha):
        answers = []
        for elem in ha['nodes']:
            answer = {
                'check': elem['name'],
                'status': 'UNKN',
                'category': category.UNKN,
                'checks': [],
                'failed check': '',
                'details': ''
            }
            n_res = elem['resources_running']

            if elem['maintenance'] == 'true':
                answer['status'] = 'MAINT'
                answer['category'] = category.WARN

            if elem['standby'] == 'true':
                answer['status'] = 'STNDBY'
                answer['category'] = category.WARN

            if elem['online'] == 'true':
                answer['status'] = 'OK'
                if int(n_res) > 0:
                    answer['category'] = category.GOOD
                else:
                    answer['category'] = category.WARN
            else:
                answer['status'] = 'DOWN'

            # FIXME not a proper (logically) field to put details to show
            # but for the sake of aestetic
            answer['failed check'] = n_res
            answers.append(answer)

        self.out.line('HA', answers)

    def out_ha_resources(self, ha):
        node_ids = {e['id']: e['name'] for e in ha['nodes']}
        for res in ha['resources']:
            self.log.debug('Resource dic: {}'.format(res))
            service = "{}({})".format(res['id'], res['role'])
            service = res['id']
            answers = []
            for node_id in node_ids:
                answer = {
                    'check': node_ids[node_id],
                    'status': 'UNKN',
                    'category': category.UNKN,
                    'checks': [],
                    'failed check': '',
                    'details': str(res)
                }

                if len(res['running_on']) < 1 or res['role'] == 'Stopped':
                    answer['status'] = 'DOWN'
                    answer['category'] = category.ERROR
                    answer['details'] = 'Service active on 0 nodes'

                if len(res['running_on']) > 1:
                    answer['status'] = 'WARN'
                    answer['category'] = category.WARN
                    answer['details'] = 'Service active on mode than 1 nodes'

                if len(res['running_on']) == 1:
                    active_node = res['running_on'][0]['id']
                    if node_id == active_node:
                        answer['status'] = res['role'].upper()
                        answer['category'] = category.GOOD
                    else:
                        answer['status'] = "-"
                        answer['category'] = category.PASSIVE

                if res['managed'] != 'true':
                    answer['status'] = 'UNMANAGED'
                    answer['category'] = category.WARN

                if res['orphaned'] != 'false':
                    answer['status'] = 'ORPHANED'
                    answer['category'] = category.WARN

                if res['failed'] != 'false':
                    answer['status'] = 'FAILED'
                    answer['category'] = category.ERROR

                if res['active'] != 'true':
                    answer['status'] = 'NOT_ACTIVE'
                    answer['category'] = category.WARN

                if res['blocked'] != 'false':
                    answer['status'] = 'BLOCKED'
                    answer['category'] = category.ERROR


                answers.append(answer)
            self.out.line(service, answers)


    def get(self):
        ha = self._get_ha()
        if ha:
            max_len = len(
                max(
                    [e['id'] for e in ha['resources']],
                    key=len
                )
            )
        else:
            max_len = 10
        self.out = Out(
            max_node_name=max_len,
            total=1,
            args=self.args,
            index_col='Checks',
            columns=[{'key': e, 'column': e} for e in self.hosts]
        )
        self.out.header()
        if ha:
            self.out_ha_status(ha)
            self.out_ha_resources(ha)
        self.out.separator()

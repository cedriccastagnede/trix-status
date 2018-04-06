from trix_status import AbstractStatus
from trix_status.out import Out
from trix_status.utils import run_cmd
from trix_status.config import category
import os
import logging
import xml.etree.ElementTree as ET
from multiprocessing.pool import ThreadPool
from multiprocessing import Lock
from trix_status.nodes.zabbixstatus import ZabbixStatus


class Status(AbstractStatus):

    def __init__(self, args):
        module_name = self.__module__ + "." + type(self).__name__
        self.log = logging.getLogger(module_name)
        self.args = args
        self.hosts = [os.uname()[1]]
        self.downed_hosts = set([])
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
        for container in xml_root.find('resources'):
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

    def analyse_pcs_output(self, answer, res, node_id):
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
            answer['status'] = 'DOWN'
            answer['category'] = category.ERROR

        if res['blocked'] != 'false':
            answer['status'] = 'BLOCKED'
            answer['category'] = category.ERROR

        return answer

    def check_systemd_unit(self, answer, res, host):
        if host in self.downed_hosts:
            return answer
        unit_name = res['resource_agent'].split(':')[-1]
        cmd_prefix = (
            "ssh -o ConnectTimeout={} -o StrictHostKeyChecking=no {} "
        ).format(self.args.timeout, host)
        cmd = cmd_prefix + "systemctl is-enabled " + unit_name
        rc, stdout, stderr, exc = run_cmd(cmd)

        if stdout.strip() != "disabled":
            answer['status'] = 'ERR'
            answer['category'] = category.ERROR
            answer['failed check'] = 'systemd'
            answer['details'] = 'Unit expecting to be disabled in pacemaker'

        cmd = cmd_prefix + "systemctl status {}".format(unit_name)
        rc, stdout, stderr, exc = run_cmd(cmd)
        if answer['category'] == category.GOOD:
            self.log.debug(
                (
                    "Service {} is expected to be running on host {}"
                ).format(unit_name, host)
            )
            if rc != 0:
                answer['status'] = 'DOWN'
                answer['category'] = category.ERROR
                answer['failed check'] = 'systemd'
                answer['details'] = 'Unit is expecting to be running'

            return answer

        self.log.debug(
            (
                "Service {} is expected to be stopped on host {}"
            ).format(unit_name, host)
        )
        if rc == 0:
            answer['status'] = 'ERR'
            answer['category'] = category.ERROR
            answer['failed check'] = 'systemd'
            answer['details'] = 'Unit is expecting to be stopped'

        return answer

    def get_downed_hosts(self, hosts):
        downed = []
        answers = []
        for host in hosts:
            answer = {
                'check': host,
                'status': 'UNKN',
                'category': category.UNKN,
                'checks': [],
                'failed check': '',
                'details': ''
            }
            cmd = (
                "ssh -o ConnectTimeout={} -o StrictHostKeyChecking=no {} uname"
            ).format(self.args.timeout, host)
            rc, stdout, stderr, exc = run_cmd(cmd)
            if rc:
                answer['status'] = 'DOWN'
                answer['category'] = category.BAD
                downed.append(host)
            if rc == 0:
                answer['status'] = 'OK'
                answer['category'] = category.GOOD
            answers.append(answer)
        self.log.debug("Hosts: '{}' are down".format(str(downed)))
        self.out.line('ssh', answers)
        return set(downed)

    def process_ha_resources(self, ha):
        self.node_ids = {e['id']: e['name'] for e in ha['nodes']}
        self.downed_hosts = self.get_downed_hosts(self.hosts)
        self.log.debug('Start thread pool')
        thread_pool = ThreadPool(processes=self.args.fanout)
        self.lock = Lock()
        self.log.debug('Map main workers to threads')

        workers_return = thread_pool.map(
            self.ha_resources_worker, ha['resources']
        )

        return workers_return

    def ha_resources_worker(self, res):
        self.log.debug('Resource dic: {}'.format(res))
        service = "{}({})".format(res['id'], res['role'])
        service = res['id']
        answers = []
        for node_id in self.node_ids:
            answer = {
                'check': self.node_ids[node_id],
                'status': 'UNKN',
                'category': category.UNKN,
                'checks': [],
                'failed check': '',
                'details': str(res)
            }

            answer = self.analyse_pcs_output(answer, res, node_id)

            res_agent = ":".join(res['resource_agent'].split(':')[:-1])

            if res_agent == 'systemd':
                answer = self.check_systemd_unit(
                    answer, res, self.node_ids[node_id]
                )

            answers.append(answer)

        with self.lock:
            self.out.line(service, answers)
            self.out.statusbar()

    def check_zabbix_events(self):
        answers = []
        for host in self.hosts:
            zabbixstat = ZabbixStatus(host)
            answer = zabbixstat.status()
            answer['check'] = host
            answers.append(answer)
        self.out.line('Zabbix', answers)

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
            total=len(ha['resources']) + 2,
            args=self.args,
            index_col='Checks',
            columns=[{'key': e, 'column': e} for e in self.hosts]
        )
        self.out.header()
        self.check_zabbix_events()
        if ha:
            self.out_ha_status(ha)
            self.process_ha_resources(ha)

        self.out.separator()

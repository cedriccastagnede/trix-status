from trix_status.utils import run_cmd, get_config
from trix_status.config import category
from trix_status.controllers.systemdchecks import SystemdChecks
import os
import logging
import xml.etree.ElementTree as ET
from multiprocessing.pool import ThreadPool
from multiprocessing import Lock
from trix_status.config import default_service_list


class HAStatus(SystemdChecks):

    def __init__(self, ha_status=None, out=None, args=None):
        module_name = self.__module__ + "." + type(self).__name__
        self.log = logging.getLogger(module_name)
        self.hosts = [os.uname()[1]]
        self.downed_hosts = set([])
        self.services = []
        self.ha_status = ha_status
        self.out = out
        self.args = args
        if self.ha_status is None:
            self.ha_status = self.if_ha()
            self.node_ids = [self.hosts]
        else:
            self.node_ids = {
                e['id']: e['name'] for e in self.ha_status['nodes']
            }

    def _get_res(self, resource):
        xml_running_on = resource.findall('node')
        running_on = []
        res = None
        for node in xml_running_on:
            running_on.append(node.attrib)
            res = resource.attrib.copy()
            res['running_on'] = running_on
        return res

    def if_ha(self):
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
            if container.tag == 'resource':
                res = self._get_res(container)
                if res is not None:
                    ha_status['resources'].append(res)
            else:
                for resource in container.findall('resource'):
                    res = self._get_res(resource)
                    if res is not None:
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

    def out_ha_status(self):
        if self.out is None:
            return
        answers = []
        for elem in self.ha_status['nodes']:
            answer = {
                'column': elem['name'],
                'status': 'UNKN',
                'category': category.UNKN,
                'history': [],
                'info': '',
                'details': ''
            }
            n_res = elem['resources_running']

            if elem['online'] == 'true':
                answer['status'] = 'OK'
                if int(n_res) > 0:
                    answer['category'] = category.GOOD
                else:
                    answer['category'] = category.WARN

                if elem['maintenance'] == 'true':
                    answer['status'] = 'MAINT'
                    answer['category'] = category.WARN

                if elem['standby'] == 'true':
                    answer['status'] = 'STANDBY'
                    answer['category'] = category.WARN

            else:
                answer['status'] = 'DOWN'

            answer['info'] = n_res
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
                if res['role'] == 'Started':
                    answer['status'] = 'UP'
                else:
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

    def check_drbd(self, answer, res, host):
        cmd = 'ssh -o ConnectTimeout={} -o StrictHostKeyChecking=no {} '
        cmd = cmd.format(self.args.timeout, host)
        cmd += 'drbd-overview | grep trinity'
        rc, stdout, stderr, exc = run_cmd(cmd)

        if rc:
            answer['status'] = 'ERR'
            answer['category'] = category.ERROR
            answer['details'] = "{} returned non-zero exit code".format(cmd)
            return answer

        stdout = stdout.strip()
        stdout = stdout.split()

        if len(stdout) < 4 or stdout[3] < 7 or stdout[3][:6] != 'UpToDa':
            answer['status'] = 'ERR'
            answer['category'] = category.ERROR
            answer['details'] = 'DRBD status is not UpToDate'
            return answer

        return answer

    def check_zfs(self, answer, res, host):
        running_on = [e['name'] for e in res['running_on']]
        if not running_on:
            answer['status'] = 'ERR'
            answer['category'] = category.ERROR
            answer['details'] = "ZFS is not running anywhere"
            return answer

        if len(running_on) > 1:
            answer['status'] = 'ERR'
            answer['category'] = category.ERROR
            answer['details'] = "pcs reported ZFS is mounted on 2 nodes"
            return answer

        running_on = running_on[0]

        cmd = 'ssh -o ConnectTimeout={} -o StrictHostKeyChecking=no {} '
        cmd = cmd.format(self.args.timeout, host)
        cmd += 'zpool list -H -o name,health'
        rc, stdout, stderr, exc = run_cmd(cmd)

        if rc:
            answer['status'] = 'ERR'
            answer['category'] = category.ERROR
            answer['details'] = "'{}' returned non-zero exit code".format(cmd)
            return answer

        if stdout and host != running_on:
            answer['status'] = 'ERR'
            answer['category'] = category.ERROR
            answer['details'] = (
                "'{}' returned some output on passive node"
            ).format(cmd)
            return answer

        if host != running_on:
            return answer

        stdout = stdout.strip().split('\n')
        for line in stdout:
            name, status = line.split()
            if status != "ONLINE":
                answer['status'] = 'ERR'
                answer['category'] = category.ERROR
                answer['details'] += (
                    "Status of '{}' is '{}'"
                ).format(name, status)
        if answer['category'] != category.GOOD:
            return answer

        answer['status'] = 'ONLINE'
        return answer

    def get_downed_hosts(self, hosts):
        if self.out is None:
            return
        downed = []
        answers = []
        for host in hosts:
            answer = {
                'column': host,
                'status': 'UNKN',
                'category': category.UNKN,
                'history': [],
                'info': '',
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

    def process_ha_resources(self):
        self.downed_hosts = self.get_downed_hosts(self.hosts)
        self.log.debug('Start thread pool')
        thread_pool = ThreadPool(processes=self.args.fanout)
        self.lock = Lock()
        self.log.debug('Map main workers to threads')

        workers_return = thread_pool.map(
            self.ha_resources_worker, self.ha_status['resources']
        )

        return workers_return

    def ha_resources_worker(self, res):
        if self.out is None:
            return
        self.log.debug('Resource dic: {}'.format(res))
        service = "{}({})".format(res['id'], res['role'])
        service = res['id']
        answers = []
        for node_id in self.node_ids:
            answer = {
                'column': self.node_ids[node_id],
                'status': 'UNKN',
                'category': category.UNKN,
                'history': [],
                'info': '',
                'details': str(res)
            }

            answer = self.analyse_pcs_output(answer, res, node_id)

            res_agent = ":".join(res['resource_agent'].split(':')[:-1])

            if res_agent == 'systemd':
                service = res['resource_agent'].split(':')[-1]
                host = self.node_ids[node_id]
                need_started = host in [e['name'] for e in res['running_on']]
                answer = self.check_systemd_unit(
                    answer, service, host,
                    need_enabled=False, need_started=need_started
                )

            if res['resource_agent'].split(':')[-1] == 'drbd':
                answer = self.check_drbd(
                    answer, res, self.node_ids[node_id]
                )

            if res['resource_agent'].split(':')[-1] == 'ZFS':
                answer = self.check_zfs(
                    answer, res, self.node_ids[node_id]
                )

            answers.append(answer)

        with self.lock:
            self.out.line(service, answers)
            self.out.statusbar()

    def process_default_services(self):
        services = get_config(
            'controllers', {'services': default_service_list}
        )['services']
        ha_services = [
            e['resource_agent'] for e in self.ha_status['resources']
        ]
        ha_services = filter(lambda x: x[:8] == 'systemd:', ha_services)
        ha_services = [e[8:] for e in ha_services]
        # nfs is special
        services = [e for e in services if e not in ha_services and e != 'nfs']

        thread_pool = ThreadPool(processes=self.args.fanout)
        self.lock = Lock()
        self.log.debug('Map main workers to threads')

        workers_return = thread_pool.map(
            self.default_services_worker, services
        )

        return workers_return

    def default_services_worker(self, service):
        answers = []
        for node_id, host in self.node_ids.items():
            answer = {
                'column': host,
                'status': 'UNKN',
                'category': category.UNKN,
                'history': [],
                'info': '',
                'details': ''
            }
            answer = self.check_systemd_unit(
                answer, service, host=host,
            )
            answers.append(answer)

        with self.lock:
            self.out.line(service, answers)

        return answers

    def check_fencing(self):
        stonith_conf = []
        rc, stdout, stderr, exc = run_cmd("pcs property")
        stonith_enabled = 'false'
        if rc == 0:
            stdout = stdout.split('\n')
            for line in stdout:
                find = ' stonith-enabled:'
                if len(line) > len(find) and line[:len(find)] == find:
                    stonith_enabled = line.split(':')[1].strip()

        for res in self.ha_status['resources']:
            agent = res['resource_agent']
            find = 'stonith:'
            if len(agent) > len(find) and agent[:len(find)] == find:
                stonith_conf.append(res)
        answers = []
        for node_id, host in self.node_ids.items():
            answer = {
                'column': host,
                'status': 'UNCONFIG',
                'category': category.UNKN,
                'history': [],
                'info': '',
                'details': ''
            }
            node_stonith = None
            for res in stonith_conf:
                nodes = [e['name'] for e in res['running_on']]
                if host in nodes:
                    node_stonith = res
                    break
            if node_stonith is not None:
                if stonith_enabled == 'true':
                    answer['status'] = 'CONFIGURED'
                    answer['category'] = category.GOOD
                else:
                    answer['status'] = 'DISABLED'
            answers.append(answer)

        self.out.line('STONITH', answers)

        return answers

    def get(self):
        self.out_ha_status()
        self.check_fencing()
        self.process_ha_resources()
        self.process_default_services()

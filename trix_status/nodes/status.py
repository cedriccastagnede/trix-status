'''
Created by ClusterVision <infonl@clustervision.com>
This file is part of trix-status tool
https://github.com/clustervision/trix-status
trix-status is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
trix-status is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
You should have received a copy of the GNU General Public License
along with slurm_health_checker.  If not, see <http://www.gnu.org/licenses/>.
'''


from trix_status import AbstractStatus
import logging
from multiprocessing.pool import ThreadPool
from multiprocessing import Lock

from trix_status.out import Out
from healthstatus import HealthStatus
from ipmistatus import IPMIStatus
from slurmstatus import SlurmStatus
from lunastatus import LunaStatus
from zabbixstatus import ZabbixStatus


luna_present = True
try:
    import luna
except ImportError:
    luna_present = False

hostlist_present = True
try:
    import hostlist
except ImportError:
    hostlist_present = False

if luna_present and luna.__version__ != '1.2':
    luna_present = False


class Status(AbstractStatus):

    def __init__(self, args):

        self.nodes = self._get_nodes(args.group, args.hosts)
        self.args = args

        self.fanout = args.fanout
        self.checks = args.checks
        self.timeout = args.timeout
        self.sorted_output = args.sorted_output

        module_name = self.__module__ + "." + type(self).__name__
        self.log = logging.getLogger(module_name)

    def _get_nodes(self, group=None, nodelist=None):

        def transform_node_dict(nodes, node):
            node_dict = nodes[node]
            ret_dict = {'node': node, 'BOOTIF': '', 'BMC': ''}
            if 'interfaces' in node_dict:
                if 'BOOTIF' in node_dict['interfaces']:
                    ret_dict['BOOTIF'] = node_dict['interfaces']['BOOTIF'][4]
                if 'BMC' in node_dict['interfaces']:
                    ret_dict['BMC'] = node_dict['interfaces']['BMC'][4]

            return ret_dict

        if not luna_present:
            log.error("Luna 1.2 is not installed")
            return []
        nodes = []
        av_groups = luna.list('group')
        if group is None:
            groups = av_groups
        else:
            if group not in av_groups:
                self.log.error("No such group '{}'".format(group))
                return []
            groups = [group]

        for group_name in groups:
            group = luna.Group(group_name)
            domain = group.boot_params['domain']
            group_nodes = group.list_nodes()
            sorted_keys = group_nodes.keys()
            sorted_keys.sort()
            ipmi_username = ''
            ipmi_password = ''

            if 'bmcsetup' in group.install_params:
                bmcsetup = group.install_params['bmcsetup']
                if 'user' in bmcsetup:
                    ipmi_username = bmcsetup['user']
                if 'password' in bmcsetup:
                    ipmi_password = bmcsetup['password']

            for node_name in sorted_keys:
                node_dict = transform_node_dict(group_nodes, node_name)
                node_dict['ipmi_username'] = ipmi_username
                node_dict['ipmi_password'] = ipmi_password
                node_dict['hostname'] = node_name
                if domain:
                    node_dict['hostname'] += "." + domain
                nodes.append(node_dict)

        if not nodelist:
            return nodes

        nodelist = ",".join(nodelist)

        if not hostlist_present:
            self.log.info(
                "hostlist is not installed. List of nodes will not be expanded")
            nodelist = nodelist.split(",")
        else:
            nodelist = hostlist.expand_hostlist(nodelist)

        return filter(lambda x: x['node'] in nodelist, nodes)

    def get(self):
        if self.nodes == []:
            self.log.debug('Nodelist is empty')
            return None

        # get max node name lenght
        max_node_name = 0
        for elem in self.nodes:
            l = len(elem['node'])
            if l > max_node_name:
                max_node_name = l

        if 'slurm' in self.checks:
            # in order not to run sinfo in every thread
            self.sinfo = SlurmStatus().get_sinfo()
            if not self.sinfo:
                self.checks.remove('slurm')

        if 'zabbix' in self.checks:
            # otherwise we will read creds files in every thread
            self.zabbix_creds = ZabbixStatus().get_credentials()

        self.out = Out(
            max_node_name=max_node_name,
            total=len(self.nodes),
            args=self.args
        )

        if not self.sorted_output:
            self.out.header()
            self.out.statusbar(update=False)

        self.log.debug('Start thread pool')
        thread_pool = ThreadPool(processes=self.fanout)
        self.lock = Lock()

        self.log.debug('Map main workers to threads')

        workers_return = thread_pool.map(self.main_worker, self.nodes)
        self.log.debug('Retuned from workers: {}'.format(workers_return))

        if self.sorted_output:
            workers_return.sort(key=lambda x: x[0])
            self.out.header()
            for node, status in workers_return:
                self.out.line(node, status)

        self.out.separator()
        return True

    def main_worker(self, node_dict):
        self.log.debug(
            "Starting worker thread for dict '{}'".format(node_dict))

        checks = []
        node = node_dict['node']

        if 'health' in self.checks:

            checks.append(
                HealthStatus(
                    node=node,
                    timeout=self.timeout
                )
            )

        if 'ipmi' in self.checks:

            checks.append(
                IPMIStatus(
                    node=node,
                    ip=node_dict['BMC'],
                    username=node_dict['ipmi_username'],
                    password=node_dict['ipmi_password'],
                    timeout=self.timeout
                )
            )

        if 'slurm' in self.checks:
            checks.append(
                SlurmStatus(
                    node=node,
                    statuses=self.sinfo
                )
            )

        if 'luna' in self.checks:
            checks.append(LunaStatus(node=node))

        if 'zabbix' in self.checks:
            checks.append(
                ZabbixStatus(
                    node=node,
                    hostname=node_dict['hostname'],
                    timeout=self.timeout,
                    username=self.zabbix_creds[0],
                    password=self.zabbix_creds[1]
                )
            )

        thread_pool = ThreadPool(processes=5)
        self.log.debug('{}:Map check workers to threads'.format(node))
        workers_return = thread_pool.map(self.check_worker, checks)
        self.log.debug(
            '{}:Retuned from check workers: {}'.format(node, workers_return))

        with self.lock:
            if not self.sorted_output:
                self.out.line(node, workers_return)
                self.out.statusbar()
            else:
                self.out.statusbar()

        return (node, workers_return)

    def check_worker(self, check):
        return check.status()

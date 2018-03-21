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


import logging
from multiprocessing.pool import ThreadPool
from multiprocessing import Lock

from out import Out
from healthstatus import HealthStatus
from ipmistatus import IPMIStatus
from slurmstatus import SlurmStatus


class TrixStatus(object):

    def __init__(self, nodes, args):

        self.nodes = nodes

        self.verbose = args.verbose
        self.fanout = args.fanout
        self.status_col = args.status_column
        self.detail_col = args.details_column
        self.sorted_output = args.sorted_output
        self.show_color = not args.no_color
        self.show_table = not args.no_table

        module_name = self.__module__ + "." + type(self).__name__
        self.log = logging.getLogger(module_name)

    def get(self, timeout=10):
        if self.nodes == []:
            self.log.debug('Nodelist is empty')
            return None

        # get max node name lenght
        max_node_name = 0
        for elem in self.nodes:
            l = len(elem['node'])
            if l > max_node_name:
                max_node_name = l

        self.sinfo = SlurmStatus().get_sinfo()

        checks = ['Health', 'IPMI']
        if self.sinfo:
            checks.append("SLURM")

        self.out = Out(
            max_node_name=max_node_name,
            status_col=self.status_col,
            detail_col=self.detail_col,
            verbose=self.verbose,
            order=checks,
            total=len(self.nodes),
            color=self.show_color,
            table=self.show_table,
        )

        if not self.sorted_output:
            self.out.header()
            self.out.statusbar(update=False)

        self.timeout = timeout
        self.log.debug('Start thread pool')
        thread_pool = ThreadPool(processes=self.fanout)
        self.lock = Lock()

        self.log.debug('Map main workers to threads')

        try:
            workers_return = thread_pool.map(self.main_worker, self.nodes)
        except KeyboardInterrupt:
            self.log.info('KeyboardInterrupt. Canceled')
            thread_pool.terminate()
            return False
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

        checks.append(
            HealthStatus(
                node=node,
                timeout=self.timeout
            )
        )

        checks.append(
            IPMIStatus(
                node=node,
                ip=node_dict['BMC'],
                username=node_dict['ipmi_username'],
                password=node_dict['ipmi_password'],
                timeout=self.timeout
            )
        )

        if self.sinfo:
            checks.append(
                SlurmStatus(
                    node=node,
                    statuses=self.sinfo
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

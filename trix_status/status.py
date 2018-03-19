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
import subprocess as sp
from multiprocessing.pool import ThreadPool
import socket
import time

class colors:
    RED = "\033[31m"
    YELLOW = "\033[31m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    DEFAULT = "\033[39m"


class Out(object):

    def __init__(self, max_node_name, status_col=10, detail_col=20,
            verbose=False, order=[], spaces=4):

        module_name = self.__module__ + "." + type(self).__name__
        self.log = logging.getLogger(module_name)

        self.max_node_name = max_node_name
        self.status_col = status_col
        self.detail_col = detail_col
        self.verbose = verbose
        self.order = order

        self.spaces = 2

        self.lengths = [max_node_name] + [self.status_col] * len(order)
        if self.verbose:
            self.lengths = ([max_node_name]
                + [self.status_col, self.detail_col] * len(order))

        self.sep = (
            "+"
            + "+".join(
                ["-" * (i + spaces) for i in self.lengths]
            )
            + "+"
        )

    def separator(self):
        print(self.sep)

    def header(self):
        self.separator()
        first_col = "Node"
        out = "|" + " " * self.spaces
        out += first_col[:self.max_node_name].ljust(self.max_node_name)
        out += " " * self.spaces + "|"
        for elem in self.order:

            out += " " * self.spaces
            out += elem.capitalize().ljust(self.status_col)
            out += " " * self.spaces

            if self.verbose:
                out += "|"
                out += " " * self.spaces
                out += "Details".ljust(self.detail_col)
                out += " " * self.spaces

            out += "|"

        print(out)
        self.separator()

    def line(self, node, json):
        fields = {}

        for elem in json:
            if 'check' not in elem or elem['check'] not in self.order:
                self.log.debug("Fields does not match")
                return None
            fields[elem['check']] = elem

        if len(fields) != len(self.order):
            self.log.debug("Fields does not match")
            return None

        if len(self.order) == 0:
            return None

        out = "|" + " " * self.spaces
        out += node.ljust(self.max_node_name)
        out += " " * self.spaces + "|"
        for elem in self.order:
            node_status = fields[elem]['status']
            color = fields[elem]['color']

            if fields[elem]['failed check']:
                node_status += "({})".format(fields[elem]['failed check'])

            if len(node_status) > self.status_col:
                node_status = node_status[:(self.status_col - 3)] + "..."


            node_status = node_status.ljust(self.status_col)

            node_status = (
                color + fields[elem]['status']
                + colors.DEFAULT
                + node_status[len(fields[elem]['status']):]
                + colors.DEFAULT
            )

            node_details = fields[elem]['details']

            if len(node_details) > self.detail_col:
                node_details = node_details[:(self.detail_col - 3)] + "..."

            node_details = node_details.ljust(self.detail_col)

            out += " " * self.spaces
            out += node_status
            out += " " * self.spaces

            if self.verbose:
                out += "|"
                out += " " * self.spaces
                out += node_details
                out += " " * self.spaces

            out += "|"

        print(out)


class TrixStatus(object):

    def __init__(self, nodes, fanout=30,
            status_col=15, detail_col=30,
            verbose=False):

        self.status_col = status_col
        self.detail_col = detail_col
        self.verbose = verbose

        self.nodes = nodes
        self.fanout = fanout
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

        self.out = Out(
            max_node_name=max_node_name,
            status_col=self.status_col,
            detail_col=self.detail_col,
            verbose=self.verbose,
            order=['health', 'ipmi']
        )

        self.out.header()

        self.timeout = timeout
        self.log.debug('Start thread pool')
        thread_pool = ThreadPool(processes=self.fanout)

        self.log.debug('Map main workers to threads')
        workers_return = thread_pool.map(self.main_worker, self.nodes)
        self.log.debug('Retuned from workers: {}'.format(workers_return))
        self.out.separator()
        return True

    def main_worker(self, node_dict):
        self.log.debug(
            "Starting worker thread for dict '{}'".format(node_dict))

        checks = []
        node = node_dict['node']

        checks.append(
            HealthChecker(
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

        thread_pool = ThreadPool(processes=5)
        self.log.debug('{}:Map check workers to threads'.format(node))
        workers_return = thread_pool.map(self.check_worker, checks)
        self.log.debug(
            '{}:Retuned from check workers: {}'.format(node, workers_return))

        self.out.line(node, workers_return)
        return True

    def check_worker(self, check):
        return check.status()



class NodeStatus(object):

    def __init__(self, node, timeout=10):
        self.node = node
        self.timeout = timeout
        module_name = self.__module__ + "." + type(self).__name__
        self.log = logging.getLogger(module_name)

    def tagged_log_debug(self, line):
        tag = self.node
        self.log.debug("{}:{}".format(tag, line))

    def cmd(self, cmd):
        self.tagged_log_debug("Command to run: '{}'".format(cmd))
        try:
            proc = sp.Popen(
                cmd, shell=True,
                stdout=sp.PIPE, stderr=sp.PIPE
            )
            stdout, stderr = proc.communicate()
            proc.wait()
            rc = proc.returncode
        except Exception as e:
            self.tagged_log_debug(
                "Exception on running '{}': '{}'".format(cmd, e)
            )
            rc = 255
            stdout, stderr = '', ''

        stdout_lines = []
        stdout_lines = filter(
            lambda x: True if x else False,
            stdout.split('\n')
        )

        oneline = lambda x: "\\n".join(x.split("\n"))
        self.tagged_log_debug(
            (
                "cmd = '{}', rc = {}, stdout = '{}', stderr = '{}'"
            ).format(cmd, rc, oneline(stdout), oneline(stderr))
        )

        return rc, stdout, stdout_lines, stderr


class HealthChecker(NodeStatus):


    def check_resolv(self):
        self.tagged_log_debug("Check if we can resolve hostname")
        self.answer['checks'].append('resolve')

        rc, stdout, stdout_lines, stderr = self.cmd(
            "host -W {} {}".format(self.timeout, self.node))

        self.tagged_log_debug("Check resolve rc = {}".format(rc))

        if rc:
            self.answer['details'] = stdout

        return not rc

    def check_ping(self):
        self.tagged_log_debug("Check if node is pingable")
        self.answer['checks'].append('ping')

        rc, stdout, stdout_lines, stderr = self.cmd(
            "ping -c1 -w{} {}".format(self.timeout, self.node)
        )

        self.tagged_log_debug("Check ping rc = {}".format(rc))

        if rc:
            self.answer['details'] = stdout

        return not rc

    def check_ssh_port(self):
        self.tagged_log_debug("Check if ssh port is open")
        self.answer['checks'].append('ssh port')

        try:
            rc = 1
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            rc = sock.connect_ex((self.node, 22))
        except Exception as e:
            msg = (
                 "Exception on checking if ssh port is open on node: '{}'"
            ).format(e)
            self.tagged_log_debug(msg)
            rc = 1
        finally:
            sock.close()

        if rc:
            self.answer['details'] = "Port 22 is closed"


        self.tagged_log_debug("Check ssh port rc = {}".format(rc))
        return not rc

    def check_ssh(self):
        self.tagged_log_debug("Check if node available via ssh")
        self.answer['checks'].append('ssh')

        rc, stdout, stdout_lines, stderr = self.cmd(
            (
                "ssh -o ConnectTimeout={} -o StrictHostKeyChecking=no {} uname"
            ).format(self.timeout, self.node)
        )

        self.tagged_log_debug("Check ssh rc = {}".format(rc))
        return not rc

    def check_mounts(self):
        self.tagged_log_debug("Check if node have healthy mountpoints")
        self.answer['checks'].append('mounts')

        # get mountpoints
        cmd = (
            "ssh -o ConnectTimeout={} -o StrictHostKeyChecking=no {} "
            + "systemctl --type mount --all --no-legend"
        ).format(self.timeout, self.node)
        rc, stdout, stdout_lines, stderr = self.cmd(cmd)
        if rc:
            return not rc
        fs_mounts = []
        standart_mounts = ['-.mount', 'run-user-0.mount']
        for line in stdout_lines:
            line = line.split()
            fs, unit_name = line[4], line[0]
            if fs[0] == '/' and unit_name not in standart_mounts:
                fs_mounts.append(fs)

        self.tagged_log_debug(
            "Discovered mounts: {}".format(fs_mounts)
        )

        thread_pool = ThreadPool(10)

        self.tagged_log_debug("Map check_mount workers to threads")
        workers_return = thread_pool.map(
            self.mount_worker,
            fs_mounts
        )

        self.tagged_log_debug(
            "Returned from mount workers: '{}'".format(workers_return)
        )
        broken_fs = []
        for fs, details, status_ok in workers_return:
            if not status_ok:
                rc = 1
                broken_fs.append(fs)
        if broken_fs:
            self.answer['details'] = "FAIL:" + ",".join(broken_fs)

        return not rc

    def mount_worker(self, fs):

        ssh_cmd = (
            "ssh -o ConnectTimeout={} -o StrictHostKeyChecking=no {} "
        ).format(self.timeout, self.node)

        self.tagged_log_debug(
            "Mount worker is spawned for {}".format(fs)
        )

        # check if fs mounted
        cmd = ssh_cmd + "cat /proc/mounts | grep -q '{}'".format(fs)
        rc, stdout, stdout_lines, stderr = self.cmd(cmd)
        if rc:
            return (fs, 'Not mounted', False)

        cmd = ssh_cmd + "stat -t {}".format(fs)

        self.tagged_log_debug(
            "Stat cmd: '{}'".format(cmd)
        )

        stat_proc = sp.Popen(
            cmd, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
        i = 0
        while True:
            if stat_proc.poll() is None:
                time.sleep(1)
            else:
                break
            i += 1
            if i > self.timeout:
                stat_proc.kill()
                msg = 'Stat timeout for {}'.format(fs)
                self.tagged_log_debug(msg)
                return (fs, 'Stat timeout', False)

        stdout, stderr = stat_proc.communicate()

        if stat_proc.returncode != 0:
            msg = 'Stat for {} returned non-zero code: {}'.format(
                fs, stat_proc.returncode
            )
            self.tagged_log_debug(msg)
            return (fs, "Stat rc = {}".format(stat_proc.returncode), False)

        return (fs, "", True)

    def status(self):
        self.tagged_log_debug("Health checker started")
        self.answer = {
            'check': 'health',
            'status': 'UNKN',
            'color': colors.RED,
            'checks': [],
            'failed check': '',
            'details': ''
        }

        if not self.check_resolv():
            self.answer['failed check'] = self.answer['checks'][-1]
            return self.answer

        if not self.check_ping():
            self.answer['failed check'] = self.answer['checks'][-1]
            return self.answer

        if not self.check_ssh_port():
            self.answer['failed check'] = self.answer['checks'][-1]
            return self.answer

        self.answer['color'] = colors.CYAN

        if not self.check_ssh():
            self.answer['failed check'] = self.answer['checks'][-1]
            return self.answer

        self.answer['status'] = 'AVAIL'
        self.answer['color'] = colors.YELLOW

        if not self.check_mounts():
            self.answer['failed check'] = self.answer['checks'][-1]
            self.answer['status'] = 'NO_FS'
            return self.answer

        self.answer['status'] = 'OK'
        self.answer['color'] = colors.GREEN

        return self.answer


class IPMIStatus(NodeStatus):

    def __init__(self, node, ip, username, password, timeout=10):
        self.node = node
        self.timeout = timeout
        module_name = self.__module__ + "." + type(self).__name__
        self.log = logging.getLogger(module_name)
        self.ip = ip
        self.username = username
        self.password = password

    def check_udp_ping(self):
        self.answer['checks'].append('udp_ping')
        ipmi_message = (
            "0600ff07000000000000000000092018c88100388e04b5").decode('hex')
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self.timeout)
        sock.sendto(ipmi_message, (self.ip, 623))

        try:
            data, addr = sock.recvfrom(1024)
            udp_pingable = True
        except:
            udp_pingable

        return udp_pingable

    def check_ping(self):

        self.tagged_log_debug("Check if IPMI IP is pingable")
        self.answer['checks'].append('ping')

        rc, stdout, stdout_lines, stderr = self.cmd(
            "ping -c1 -w{} {}".format(self.timeout, self.ip)
        )
        self.tagged_log_debug("Check ping rc = {}".format(rc))

        return not rc

    def check_power(self):
        self.tagged_log_debug("Check power status of the node")
        self.answer['checks'].append('power')

        rc, stdout, stdout_lines, stderr = self.cmd(
            (
                "ipmitool -I lanplus -H {} -U {} -P {} chassis status"
            ).format(self.ip, self.username, self.password)
        )
        self.tagged_log_debug("Check ping rc = {}".format(rc))
        for line in stdout_lines:
            if line[:12] == 'System Power':
                self.answer['status'] = line.split(" ")[-1].upper()

        return not rc

    def status(self):
        self.tagged_log_debug("Health checker started")
        self.answer = {
            'check': 'ipmi',
            'status': 'UNKN',
            'color': colors.DEFAULT,
            'checks': [],
            'failed check': '',
            'details': ''
        }
        if not self.check_udp_ping():
            self.answer['failed check'] = self.answer['checks'][-1]
            return self.answer

        if not self.check_ping():
            self.answer['failed check'] = self.answer['checks'][-1]
            return self.answer

        self.answer['color'] = colors.CYAN

        if not self.check_power():
            self.answer['failed check'] = self.answer['checks'][-1]
            return self.answer

        if self.answer['status'] == 'ON':
            self.answer['color'] = colors.GREEN

        if self.answer['status'] == 'OFF':
            self.answer['color'] = colors.RED

        return self.answer

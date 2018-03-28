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


import subprocess as sp
from multiprocessing.pool import ThreadPool
import socket
import time

from config import category
from nodestatus import NodeStatus


class HealthStatus(NodeStatus):

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
            if len(stdout_lines) > 1:
                self.answer['details'] = stdout_lines[-2]

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
            'category': category.UNKN,
            'checks': [],
            'failed check': '',
            'details': ''
        }

        if not self.check_resolv():
            self.answer['failed check'] = self.answer['checks'][-1]
            return self.answer

        self.answer['status'] = 'DOWN'

        if not self.check_ping():
            self.answer['failed check'] = self.answer['checks'][-1]
            return self.answer

        if not self.check_ssh_port():
            self.answer['failed check'] = self.answer['checks'][-1]
            return self.answer

        self.answer['category'] = category.DOWN

        if not self.check_ssh():
            self.answer['failed check'] = self.answer['checks'][-1]
            return self.answer

        self.answer['status'] = 'AVAIL'
        self.answer['category'] = category.WARN

        if not self.check_mounts():
            self.answer['failed check'] = self.answer['checks'][-1]
            self.answer['status'] = 'NO_FS'
            return self.answer

        self.answer['status'] = 'OK'
        self.answer['category'] = category.GOOD

        return self.answer

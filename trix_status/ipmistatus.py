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
import socket

from out import colors
from nodestatus import NodeStatus


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

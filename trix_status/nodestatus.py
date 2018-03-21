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
import utils
from multiprocessing.pool import ThreadPool
from abc import ABCMeta, abstractmethod



class NodeStatus(object):

    __metaclass__ = ABCMeta

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
        rc, stdout, stderr, e = utils.run_cmd(cmd)

        if e:
            self.tagged_log_debug(
                "Exception on running '{}': '{}'".format(cmd, e)
            )

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

    @abstractmethod
    def status(self):
        pass

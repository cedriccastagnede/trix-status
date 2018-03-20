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
import sys


class colors:
    RED = "\033[31m"
    YELLOW = "\033[31m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    DEFAULT = "\033[39m"


class Out(object):

    def __init__(self, max_node_name, status_col=10, detail_col=20,
                 verbose=False, order=[], spaces=4, total=0):

        module_name = self.__module__ + "." + type(self).__name__
        self.log = logging.getLogger(module_name)

        self.max_node_name = max_node_name
        self.status_col = status_col
        self.detail_col = detail_col
        self.done = 0
        self.total = total
        self.verbose = verbose
        self.order = order

        self.spaces = 2

        self.lengths = [max_node_name] + [self.status_col] * len(order)
        if self.verbose:
            self.lengths = (
                [max_node_name]
                + [self.status_col, self.detail_col] * len(order)
            )

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

    def statusbar(self, update=True, width=30):
        if update:
            self.done += 1
        progress_perc = (100.*self.done)/self.total
        out = "{: 5.2f}%".format(progress_perc)
        nbars = int((progress_perc/100)*width)
        out += " [" + "|" * nbars + "." * (width - nbars) + "]"
        sys.stdout.write(out)
        sys.stdout.write('\r')
        sys.stdout.flush()

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
import config


class colors:
    RED = "\033[31m"
    LIGHTRED = "\033[91m"
    YELLOW = "\033[33m"
    LIGHTYELLOW = "\033[93m"
    CYAN = "\033[36m"
    LIGHTCYAN = "\033[96m"
    GREEN = "\033[32m"
    LIGHTGREEN = "\033[92m"
    DEFAULT = "\033[39m"
    BGLIGHGRAY = "\033[47m"
    BGBLACK = "\033[40m"
    BGDEFAULT = "\033[49m"

class Out(object):

    def __init__(self, max_node_name, total, args, spaces=4):
        module_name = self.__module__ + "." + type(self).__name__
        self.log = logging.getLogger(module_name)

        self.max_node_name = max_node_name
        self.status_col = args.status_column
        self.detail_col = args.details_column
        self.done = 0
        self.total = total
        self.verbose = args.verbose
        self.column_names = args.checks
        self.no_statusbar = args.no_statusbar

        self.spaces = 2

        self.table = not args.no_table
        self.col_sep = " "
        if self.table:
            self.col_sep = "|"

        self.color = False

        if not args.no_color and sys.stdout.isatty():
            self.color = True

        self.lengths = (
            [max_node_name]
            + [self.status_col] * len(self.column_names)
        )
        if self.verbose:
            self.lengths = (
                [max_node_name]
                + [self.status_col, self.detail_col] * len(self.column_names)
            )

        self.sep = (
            "+"
            + "+".join(
                ["-" * (i + spaces) for i in self.lengths]
            )
            + "+"
        )

    def separator(self):
        if self.table:
            print(self.sep)

    def header(self):
        self.separator()
        first_col = "Node"
        out = self.col_sep + " " * self.spaces
        out += first_col[:self.max_node_name].ljust(self.max_node_name)
        out += " " * self.spaces + self.col_sep
        for elem in self.column_names:

            col_name = config.available_checks[elem]
            out += " " * self.spaces
            out += col_name.ljust(self.status_col)
            out += " " * self.spaces

            if self.verbose:
                out += self.col_sep
                out += " " * self.spaces
                out += "Details".ljust(self.detail_col)
                out += " " * self.spaces

            out += self.col_sep

        print(out)
        self.separator()

    def line(self, node, json):
        fields = {}

        for elem in json:
            if 'check' not in elem or elem['check'] not in self.column_names:
                self.log.debug("Fields does not match")
                return None
            fields[elem['check']] = elem

        if len(fields) != len(self.column_names):
            self.log.debug("Fields does not match")
            return None

        if len(self.column_names) == 0:
            return None

        out = self.col_sep + " " * self.spaces
        out += node.ljust(self.max_node_name)
        out += " " * self.spaces + self.col_sep

        for elem in self.column_names:

            node_status = fields[elem]['status']
            failed_check = ""

            if fields[elem]['failed check']:
                failed_check = "({})".format(fields[elem]['failed check'])

            color = fields[elem]['color']

            status_len = len(node_status) + len(failed_check)
            out_status = node_status + failed_check

            # if status+failed_check do not fir into column
            # cut and add '...' on the end
            if status_len > self.status_col:
                out_status = out_status[:(self.status_col - 3)] + "..."

            if self.color:
                # Several cases here. It depends on column width
                # 1. STATUS(failed_check)
                # 2. STATUS(faile...
                # 3. STA...
                # start with 3
                if len(out_status) - 3 < len(node_status):
                    out_status = color + out_status + colors.DEFAULT
                else:
                    # 1 and 2
                    tmp = out_status[len(node_status):]
                    out_status = color + node_status + colors.DEFAULT
                    out_status += tmp

            # cant use ljust here, as coloring symbols
            # are counted in lenght, but do not use position on screen
            out_status += " " * (self.status_col - status_len)

            node_details = fields[elem]['details']

            if len(node_details) > self.detail_col:
                node_details = node_details[:(self.detail_col - 3)] + "..."

            node_details = node_details.ljust(self.detail_col)

            out += " " * self.spaces
            out += out_status
            out += " " * self.spaces

            if self.verbose:
                out += self.col_sep
                out += " " * self.spaces
                out += node_details
                out += " " * self.spaces

            out += self.col_sep

        print(out)

    def statusbar(self, update=True):
        if self.no_statusbar:
            return
        width = len(self.sep) - 12
        if update:
            self.done += 1
        progress_perc = (100.*self.done)/self.total
        out = "{: 7.2f}%".format(progress_perc)
        nbars = int((progress_perc/100)*width)
        out += " ["
        out += "#" * nbars
        out +=  " " * (width - nbars)
        out += "]"
        sys.stdout.write(out)
        sys.stdout.write('\r')
        sys.stdout.flush()

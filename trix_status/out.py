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


class Out(object):

    def __init__(self, max_node_name, total, args, spaces=4):
        #status_col=10, detail_col=20,
        #         verbose=False, columns=[], spaces=4, total=0,
        #         table=True, color=True):

        module_name = self.__module__ + "." + type(self).__name__
        self.log = logging.getLogger(module_name)

        self.max_node_name = max_node_name
        self.status_col = args.status_column
        self.detail_col = args.details_column
        self.done = 0
        self.total = total
        self.verbose = args.verbose

        # preserve order of specified columns,
        # but remove duplicates:
        # [1, 4, 2, 2, 4, 3, 5, 5, 5, 6] -> [1, 4, 2, 3, 5, 6]
        self.column_names = []
        [self.column_names.append(e)
            for e in args.checks if e not in self.column_names]

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
            color = fields[elem]['color']

            if fields[elem]['failed check']:
                node_status += "({})".format(fields[elem]['failed check'])

            if len(node_status) > self.status_col:
                node_status = node_status[:(self.status_col - 3)] + "..."

            node_status = node_status.ljust(self.status_col)

            if self.color:

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
                out += self.col_sep
                out += " " * self.spaces
                out += node_details
                out += " " * self.spaces

            out += self.col_sep

        print(out)

    def statusbar(self, update=True):
        width = len(self.sep) - 12
        if update:
            self.done += 1
        progress_perc = (100.*self.done)/self.total
        out = "{: 7.2f}%".format(progress_perc)
        nbars = int((progress_perc/100)*width)
        out += " [" + "|" * nbars + "." * (width - nbars) + "]"
        sys.stdout.write(out)
        sys.stdout.write('\r')
        sys.stdout.flush()

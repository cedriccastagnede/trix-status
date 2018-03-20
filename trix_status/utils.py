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


import argparse
import logging

luna_present = True
try:
    import luna
except ImportError:
    luna_present = False

if luna_present and luna.__version__ != '1.2':
    luna_present = False


def get_nodes():
    if not luna_present:
        return []
    nodes = []
    groups = luna.list('group')
    for group_name in groups:
        group = luna.Group(group_name)
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
            nodes.append(node_dict)

    return nodes


def transform_node_dict(nodes, node):
    node_dict = nodes[node]
    ret_dict = {'node': node, 'BOOTIF': '', 'BMC': ''}
    if 'interfaces' in node_dict:
        if 'BOOTIF' in node_dict['interfaces']:
            ret_dict['BOOTIF'] = node_dict['interfaces']['BOOTIF'][4]
        if 'BMC' in node_dict['interfaces']:
            ret_dict['BMC'] = node_dict['interfaces']['BMC'][4]

    return ret_dict


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="""
        Show status of nodes and controllers for TrinityX cluster
        """
    )

    parser.add_argument(
        "--sorted-output", "-s", action="store_true",
        help="Sort output by node name"
    )

    parser.add_argument(
        "--fanout", "-w", type=int, default=10,
        help="Number of checks running simultaneously"
    )

    parser.add_argument(
        "--status-column", "-S", type=int, default=15,
        help="Width of status column"
    )

    parser.add_argument(
        "--details-column", "-D", type=int, default=30,
        help="Width of details' column"
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show details of failed checks"
    )

    parser.add_argument(
        "--debug", "-d", action="store_const",
        dest="loglevel", const=logging.DEBUG, default=logging.INFO,
        help="Debug output")

    args = parser.parse_args()
    return args

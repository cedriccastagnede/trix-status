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

import luna
from trix_status.config import category
from nodestatus import NodeStatus


class LunaStatus(NodeStatus):

    def __init__(self, node):
        self.node = node

    def status(self):
        self.answer = {
            'column': 'luna',
            'status': 'UNKN',
            'category': category.UNKN,
            'history': [],
            'info': '',
            'details': ''
        }
        node = luna.Node(self.node)
        node_status = node.get_status()
        if node_status is None:
            return self.answer
        status = node_status['status']
        self.answer['status'] = status
        if status == "install.success":
            self.answer['category'] = category.GOOD
        else:
            self.answer['category'] = category.BUSY
        return self.answer

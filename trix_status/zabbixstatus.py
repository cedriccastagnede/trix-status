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

from config import category
from nodestatus import NodeStatus
from utils import get_config
import os
import yaml
import config
import logging
import json
import urllib2

default_username = "Admin"
default_password = "zabbix"
trinity_password_file = "/etc/trinity/passwords/zabbix/admin.txt"
z_url = "http://localhost/zabbix/api_jsonrpc.php"

def print_json(j):
    print json.dumps(j, indent=4, sort_keys=True)

class ZabbixStatus(NodeStatus):

    def __init__(self, node=None, hostname=None,
                 timeout=10, username=None, password=None):

        self.node = node
        self.username = username
        self.password = password
        self.timeout = timeout
        module_name = self.__module__ + "." + type(self).__name__
        self.log = logging.getLogger(module_name)
        if hostname is None:
            self.hostname = node
        else:
            self.hostname = hostname
        conf = {'url': z_url}
        conf = get_config('zabbix', conf)
        self.z_url = conf['url']


    def get_credentials(self):
        if self.username is not None and self.password is not None:
            return self.username, self.password
        creds = {
            'password_file': trinity_password_file,
            'username': default_username,
        }
        # overwrite default creds from above
        creds = get_config('zabbix', creds)
        if os.path.isfile(creds['password_file']):
            with open(creds['password_file']) as f:
                creds['password'] = f.readline().strip()
        else:
            creds['password'] = default_password

        # overwrite password from config
        creds = get_config('zabbix', creds)

        self.username = creds['username']
        self.password = creds['password']

        return self.username, self.password

    def _do_request(self, j):
        if 'method' in j:
            method = j['method']
        else:
            method = j
        try:
            self.tagged_log_debug("Talking to zabbix API")
            req = urllib2.Request(self.z_url)
            req.add_header('Content-Type', 'application/json')
            r = next(urllib2.urlopen(
                req, json.dumps(j), timeout=self.timeout))
            r = json.loads(r)
        except Exception as exc:
            self.tagged_log_debug(exc)
            return False, str(exc)

        if not r:
            msg = (
                'Zabbix API returned wrong answer on ' +
                '{}: {}'.format(method, str(r))
            )
            self.tagged_log_debug(msg)
            return False, msg

        if not 'result' in r:
            msg = (
                'Zabbix API returned no result on ' +
                '{}: {}'.format(method, str(r))
            )
            self.log.debug(msg)
            return False, msg

        return r['result'], ""

    def do_request(self, j):
        self.answer['checks'].append(j['method'])
        data, details = self._do_request(j)
        if details:
            self.answer['details'] += " |{}: ".format(j['method'])
            self.answer['details'] += details
        return data

    def get_token(self):
        j = {
            'jsonrpc': '2.0',
            'method': 'user.login',
            'auth': None,
            'id': 1,
            'params': {
                'user': self.username,
                'password': self.password
            }
        }
        return self.do_request(j)

    def get_hostid(self, token):
        j = {
            "jsonrpc": "2.0",
            "method": "host.get",
            "auth": token,
            "id": 2,
            "params": {
                "filter": {
                    "host": [
                        self.hostname,
                    ]
                }
            }
        }
        z_answer = self.do_request(j)
        if not z_answer:
            self.answer['details'] = (
                "Zabbix did not return hostid for this host"
            )
            return False
        latest_record = max(z_answer, key=lambda x: x['hostid'])
        self.answer['details'] = latest_record['error']
        return latest_record['hostid']

    def get_events(self, token, hostid):
        j = {
            'jsonrpc': '2.0',
            'method': 'problem.get',
            'auth': token,
            'id': 3,
            'params': {
                "hostids": hostid,
                "acknowledged": False,
                "severities": list(range(0, 6)),
                "output": "extend",
                "sortfield": ["eventid"],
                "sortorder": "DESC",

            },
        }

        z_answer = self.do_request(j)

        if not z_answer:
            return -1  # no events

        self.tagged_log_debug("Problems for node: {}".format(z_answer))
        objectsids = [e['objectid'] for e in z_answer]

        j = {
            'jsonrpc': '2.0',
            "method": "trigger.get",
            'auth': token,
            'id': 4,
            'params': {
                "triggerids": objectsids,
                'hostids': hostid,
                'output': ["priority", "description"],
                'sortfield': ['priority'],
                "sortorder": "DESC",

            },
        }
        z_answer = self.do_request(j)
        self.tagged_log_debug("Triggers for node: {}".format(z_answer))
        self.answer["details"] =  " / ".join(
            [e["description"] for e in z_answer ]
        )
        return int(z_answer[0]["priority"])

    def status(self):
        self.answer = {
            'check': 'zabbix',
            'status': 'UNKN',
            'category': category.UNKN,
            'checks': [],
            'failed check': '',
            'details': ''
        }

        if self.node is None:
            return self.answer

        if self.username is None or self.username is None:
            self.username, self.password = self.get_credentials()

        token = self.get_token()
        if not token:
            self.answer['failed check'] = self.answer['checks'][-1]
            return self.answer

        hostid = self.get_hostid(token)
        if not hostid:
            self.answer['failed check'] = self.answer['checks'][-1]
            return self.answer

        max_event_priority = self.get_events(token, hostid)

        if max_event_priority > 2:
            self.answer["category"] = category.ERROR
            self.answer["status"] = "ERR"
            return self.answer

        if max_event_priority > 1:
            self.answer["category"] = category.WARN
            self.answer["status"] = "WARN"
            return self.answer

        self.answer["category"] = category.GOOD
        self.answer["status"] = "OK"

        return self.answer


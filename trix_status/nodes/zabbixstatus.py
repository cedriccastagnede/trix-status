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

from trix_status.config import category
from nodestatus import NodeStatus
from trix_status.utils import get_config
import os
import logging
import json
import urllib2
import ssl
from cryptography import x509
from _socket import error as SocketError
from ssl import SSLError
from cryptography.hazmat.backends import default_backend
from cryptography.x509.extensions import ExtensionNotFound

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
        conf = {}
        conf = get_config('zabbix', conf)
        self.z_url = None
        self.answer = {}

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

    def get_https_zabbix_hosts(self):
        hosts = []
        try:
            pem_data = str(ssl.get_server_certificate(("localhost", 443)))
        except SocketError, SSLError:
            return hosts, "https is not configured"
        cert = x509.load_pem_x509_certificate(pem_data, default_backend())
        cn = x509.ObjectIdentifier("2.5.4.3")
        attrs = cert.subject.get_attributes_for_oid(cn)
        if len(attrs) == 0:
            return hosts, "No commonName is configured for the certicate"
        hostname = attrs[0].value
        hosts.append(hostname)
        subjectAltName = x509.ObjectIdentifier("2.5.29.17")
        try:
            alt_hosts = (
                cert
                .extensions
                .get_extension_for_oid(subjectAltName)
                .value
                .get_values_for_type(x509.DNSName)
            )
        except ExtensionNotFound:
            alt_hosts = []
        hosts.extend(alt_hosts)
        return ["https://{}".format(h) for h in hosts], ""

    def get_sabbix_url(self):
        errors = []
        servers, https_err = self.get_https_zabbix_hosts()
        if https_err:
            errors.append(errors)
        servers.append("http://localhost")
        doc = "/zabbix/api_jsonrpc.php"
        possible_urls = [u + doc for u in servers if u is not None]
        valid_urls = []
        for url in possible_urls:
            try:
                req = urllib2.Request(url)
                req.add_header('Content-Type', 'application/json')
                r = next(urllib2.urlopen(
                    req, json.dumps({}), timeout=self.timeout))
                r = json.loads(r)
                valid_urls.append(url)
            except Exception as exc:
                errors.append(str(exc))
        if len(valid_urls) == 0:
            return None, "|".join(errors)
        return valid_urls[0], ""


    def _do_request(self, j):
        err = ""
        if self.z_url is None:
            self.z_url, err = self.get_sabbix_url()
        if self.z_url is None:
            return False, err
        else:
            conf = {'url': self.z_url}
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
        if self.answer:
            self.answer['history'].append(j['method'])
        data, details = self._do_request(j)
        if details and self.answer:
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

    def get_most_important_event(self, token, hostid=None):
        triggers = self.get_triggers(token, hostid)
        if len(triggers) == 0:
            return -1
        self.tagged_log_debug("Triggers for node: {}".format(triggers))
        self.answer["details"] = " / ".join(
            [e["description"] for e in triggers]
        )
        return int(triggers[0]["priority"])

    def get_triggers(self, token, hostid=None):
        j = {
            'jsonrpc': '2.0',
            'method': 'problem.get',
            'auth': token,
            'id': 3,
            'params': {
                "acknowledged": False,
                "severities": list(range(0, 6)),
                "output": "extend",
                "sortfield": ["eventid"],
                "sortorder": "DESC",

            },
        }

        if hostid is not None:
            j['params']['hostids'] = hostid

        z_answer = self.do_request(j)

        if not z_answer:
            return []  # no events

        self.tagged_log_debug("Problems for node: {}".format(z_answer))
        objectsids = [e['objectid'] for e in z_answer]

        j = {
            'jsonrpc': '2.0',
            "method": "trigger.get",
            'auth': token,
            'id': 4,
            'params': {
                "triggerids": objectsids,
                'output': ["priority", "description"],
                'sortfield': ['priority'],
                "sortorder": "DESC",
                "selectHosts": "extend",

            },
        }

        if hostid is not None:
            j['params']['hostids'] = hostid

        z_answer = self.do_request(j)
        return z_answer

    def status(self):
        self.answer = {
            'column': 'zabbix',
            'status': 'UNKN',
            'category': category.UNKN,
            'history': [],
            'info': '',
            'details': ''
        }

        if self.node is None:
            return self.answer

        if self.username is None or self.username is None:
            self.username, self.password = self.get_credentials()

        token = self.get_token()
        if not token:
            self.answer['info'] = self.answer['history'][-1]
            return self.answer

        hostid = self.get_hostid(token)
        if not hostid:
            self.answer['info'] = self.answer['history'][-1]
            return self.answer

        max_event_priority = self.get_most_important_event(token, hostid)

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

    def get_cluster_events(self):
        self.answer = {
            'column': 'zabbix',
            'status': 'UNKN',
            'category': category.UNKN,
            'history': [],
            'info': '',
            'details': ''
        }

        if self.username is None or self.username is None:
            self.username, self.password = self.get_credentials()

        token = self.get_token()
        if not token:
            self.answer['info'] = self.answer['history'][-1]
            return self.answer

        triggers = []
        for event in self.get_triggers(token):
            for host in event['hosts']:
                triggers.append({
                    'priority': int(event['priority']),
                    'host': host['host'],
                    'description': event['description']
                })


        trigger_counts = [0] * 6
        for e in triggers:
            trigger_counts[e['priority']] += 1

        if len(triggers) == 0:
            worst_issue = 0
        else:
            worst_issue = int(
                max(triggers, key=lambda x: int(x['priority']))['priority']
            )

        # 0 - (default) not classified;
        # 1 - information;
        # 2 - warning;
        # 3 - average;
        # 4 - high;
        # 5 - disaster.
        priority_map = {
            0: 'NA',
            1: 'INF',
            2: 'WARN',
            3: 'AVE',
            4: 'HIGH',
            5: 'DISA',
        }

        if worst_issue < 2:
            self.answer['status'] = 'OK'
            self.answer['category'] = category.GOOD

        if worst_issue == 2:
            self.answer['status'] = 'WARN'
            self.answer['category'] = category.WARN

        if worst_issue > 2:
            self.answer['status'] = 'ERR'
            self.answer['category'] = category.ERROR

        self.answer['info'] = '/'.join(
            [str(e) for e in trigger_counts[::-1]]
        )

        self.answer['details'] = (
            "disaster/high/average/warn/inform/non-class\n"
        )

        self.answer['details'] += "Events:\n"

        self.answer['details'] += "\n".join([
            "{}/{}/{};".format(
                priority_map[e['priority']],
                e['host'],
                e['description']
            ) for e in triggers
        ])

        triggers.sort(key=lambda x: x['priority'])

        return self.answer

    def get_all_events(self):
        if self.username is None or self.username is None:
            self.username, self.password = self.get_credentials()

        token = self.get_token()
        if not token:
            self.log.error("Unable to get auth token")
            return None

        triggers = []
        for event in self.get_triggers(token):
            for host in event['hosts']:
                triggers.append({
                    'priority': int(event['priority']),
                    'host': host['host'],
                    'description': event['description']
                })

        return triggers


import os
import logging
from multiprocessing.pool import ThreadPool
from multiprocessing import Lock
from trix_status.utils import get_config, run_cmd
from trix_status.config import category

default_service_list = [
    'named', 'dhcpd', 'chronyd', 'sshd', 'fail2ban', 'firewalld', 'nginx',
    'lweb', 'ltorrent', 'mariadb', 'mongod', 'nfs', 'slapd', 'zabbix-server',
    'zabbix-agent', 'sssd', 'slurmctld', 'munge', 'rsyslog',
]

class NonHAStatus(object):

    def __init__(self, out=None, args=None):
        module_name = self.__module__ + "." + type(self).__name__
        self.log = logging.getLogger(module_name)
        self.out = out
        self.args = args
        self.host = os.uname()[1]
        self.services = get_config(
            'controllers', {'services': default_service_list}
        )['services']

    def check_systemd_unit(self, service):
        answer = {
            'check': self.host,
            'status': 'UNKN',
            'category': category.UNKN,
            'checks': [],
            'failed check': '',
            'details': ''
        }

        cmd = "systemctl is-enabled " + service
        rc, stdout, stderr, exc = run_cmd(cmd)

        if stdout.strip() != "enabled":
            answer['details'] = 'Autostart is disabled for the unit'

        cmd = "systemctl status {}".format(service)
        rc, stdout, stderr, exc = run_cmd(cmd)

        if rc != 0:
            answer['status'] = 'DOWN'
            answer['category'] = category.ERROR
            answer['failed check'] = 'systemd'
            answer['details'] = 'Unit is expecting to be running'

            return answer

        answer['status'] = 'OK'
        answer['category'] = category.GOOD
        return answer

    def systemd_worker(self, service):
        answer = self.check_systemd_unit(service)
        with self.lock:
            self.out.line(service, [answer])
        return [answer]

    def get(self):
        self.log.debug('Start thread pool')
        thread_pool = ThreadPool(processes=self.args.fanout)
        self.lock = Lock()
        self.log.debug('Map main workers to threads')
        workers_return = thread_pool.map(
            self.systemd_worker, self.services
        )


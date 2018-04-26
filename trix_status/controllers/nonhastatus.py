import os
import logging
from trix_status.controllers.systemdchecks import SystemdChecks
from multiprocessing.pool import ThreadPool
from multiprocessing import Lock
from trix_status.utils import get_config, run_cmd
from trix_status.config import category
import importlib
from trix_status.config import default_service_list


class NonHAStatus(SystemdChecks):

    def __init__(self, out=None, args=None):
        module_name = self.__module__ + "." + type(self).__name__
        self.log = logging.getLogger(module_name)
        self.out = out
        self.args = args
        self.host = os.uname()[1]
        self.services = get_config(
            'controllers', {'services': default_service_list}
        )['services']

    def systemd_worker(self, service):
        answer = {
			'column': self.host,
			'status': 'UNKN',
			'category': category.UNKN,
			'history': [],
			'info': '',
			'details': ''
        }
        answer = self.check_systemd_unit(answer, service)
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


from trix_status import AbstractStatus
from trix_status.out import Out
from trix_status.utils import run_cmd
from trix_status.config import category
import os
import logging
import xml.etree.ElementTree as ET
from multiprocessing.pool import ThreadPool
from multiprocessing import Lock
from trix_status.nodes.zabbixstatus import ZabbixStatus
from trix_status.controllers.hastatus import HAStatus
from trix_status.controllers.nonhastatus import NonHAStatus


class Status(AbstractStatus):

    def __init__(self, args):
        module_name = self.__module__ + "." + type(self).__name__
        self.log = logging.getLogger(module_name)
        self.args = args
        self.hosts = [os.uname()[1]]
        self.downed_hosts = set([])
        self.services = []

    def check_zabbix_events(self):
        answers = []
        for host in self.hosts:
            zabbixstat = ZabbixStatus(host)
            answer = zabbixstat.status()
            answer['check'] = host
            answers.append(answer)
        return answers

    def check_zabbix_cluster_events(self):
        zabbixstat = ZabbixStatus()
        answer = zabbixstat.get_cluster_events()
        answers = []
        for host in self.hosts:
            answer['check'] = host
            answers.append(answer.copy())
        return answers

    def get(self):
        ha_obj = HAStatus()
        ha = ha_obj.if_ha()

        if ha:
            self.hosts = ha_obj.hosts
            max_len = len(
                max(
                    [e['id'] for e in ha['resources']],
                    key=len
                )
            )
            n_res = len(ha['resources'])
        else:
            service_names = NonHAStatus().services
            max_len = max([len(e) for e in service_names])
            n_res = len(service_names)

        if max_len < len('Zabbix-total'):
            max_len =  len('Zabbix-total')

        out = Out(
            max_node_name=max_len,
            total=n_res + 2,
            args=self.args,
            index_col='Checks',
            columns=[{'key': e, 'column': e} for e in self.hosts]
        )

        out.header()
        out.line('Zabbix-node', self.check_zabbix_events())
        out.line('Zabbix-total', self.check_zabbix_cluster_events())

        if ha:
            HAStatus(ha, out, self.args).get()
        else:
            NonHAStatus(out, self.args).get()


        out.separator()

import logging
from trix_status import AbstractStatus
from trix_status.nodes.zabbixstatus import ZabbixStatus
from trix_status.config import category
from trix_status.out import Out

class Status(AbstractStatus):

    def __init__(self, args):
        self.args = args
        module_name = self.__module__ + "." + type(self).__name__
        self.log = logging.getLogger(module_name)
        self.args.verbose = True

    def get(self):
        events = ZabbixStatus().get_all_events()
        if not events:
            return None
        events.sort(key=lambda x: x['host'])
        node_lenths = [len(e['host']) for e in events]
        out = Out(
            max_node_name=max(node_lenths),
            total=len(events),
            args=self.args,
            index_col='Nodes',
            columns=[{
                'key': 'prio',
                'column': 'Priority'
            }]
        )

        out.header()

        priority_map = {
            0: 'NA',
            1: 'INF',
            2: 'WARN',
            3: 'AVE',
            4: 'HIGH',
            5: 'DISA',
        }

        for event in events:

            self.log.debug(event)

            cat = category.UNKN

            if event['priority'] < 2:
                cat = category.GOOD

            if event['priority'] == 2:
                cat = category.WARN

            if event['priority'] > 2:
                cat = category.ERROR

            line = {
                'column': 'prio',
                'status': priority_map[event['priority']],
                'category': cat,
                'history': [],
                'info': '',
                'details': event['description']
            },
            out.line(event['host'], line)

        out.separator()



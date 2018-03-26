import luna
from nodestatus import NodeStatus, category

class LunaStatus(NodeStatus):

    def __init__(self, node):
        self.node = node

    def status(self):
        self.answer = {
            'check': 'luna',
            'status': 'UNKN',
            'category': category.UNKN,
            'checks': [],
            'failed check': '',
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


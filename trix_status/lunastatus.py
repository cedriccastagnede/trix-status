import luna
from out import colors

class LunaStatus(object):

    def __init__(self, node):
        self.node = node

    def status(self):
        self.answer = {
            'check': 'luna',
            'status': 'UNKN',
            'color': colors.RED,
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
            self.answer['color'] = colors.GREEN
        else:
            self.answer['color'] = colors.YELLOW
        return self.answer


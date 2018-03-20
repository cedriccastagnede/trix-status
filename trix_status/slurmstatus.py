import utils
from out import colors

class SlurmStatus(object):

    def __init__(self, node=None, statuses=None):

        self.node = node
        self.statuses = statuses

    def status(self):
        self.answer = {
            'check': 'SLURM',
            'status': 'UNKN',
            'color': colors.RED,
            'checks': [],
            'failed check': '',
            'details': ''
        }

        if (self.node is None
                or self.statuses is None
                or self.node not in self.statuses):
            return self.answer

        status = "/".join(self.statuses[self.node])
        self.answer['status'] = status

        idle_statuses = ["IDLE"]
        working_statuses = [
            "ALLOCATED", "ALLOCATED+", "COMPLETING", "MIXED", "RESERVED"
        ]

        error_tags = ["*", "~", "#", "$", "@"]

        if status.upper() in idle_statuses:
            self.answer['color'] = colors.GREEN

        if status.upper() in working_statuses:
            self.answer['color'] = colors.YELLOW

        if len(status) > 1 and status[-1] in error_tags:
            self.answer['color'] = colors.RED

        return self.answer


    def get_sinfo(self):
        """
        Returns stdout for
        sinfo -N -o "%N %6T"
        """
        self.statuses = {}
        cmd = 'sinfo -N -o "%N %6T"'
        rc, stdout, _, _ = utils.run_cmd(cmd)

        if rc:
            return self.statuses

        for line in stdout.split("\n"):
            line = line.split()
            if len(line) < 2:
                continue
            nodename = line[0]
            status = line[1]
            if nodename not in self.statuses:
                self.statuses[nodename] = set()
            self.statuses[nodename].add(status)

        return self.statuses


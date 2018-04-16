from trix_status.utils import run_cmd
from trix_status.controllers.services.checker import Checker


class Sshd(Checker):

    def status(self):
        res, comment = True, ""

        cmd = self.cmd_prefix
        cmd += 'ssh localhost uptime'
        rc, stdout, stderr, exc = run_cmd(cmd)

        if rc or len(stdout.strip().split('\n')) < 1:
            res = False
            comment = "'{}' returned unexpected result".format(cmd)
            return res, comment

        return res, comment

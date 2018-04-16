from trix_status.utils import run_cmd
from trix_status.controllers.services.checker import Checker


class Mongod(Checker):

    def status(self):
        res, comment = True, ""

        ping = "111222333"
        cmd = self.cmd_prefix
        if self.cmd_prefix:
            cmd += '"'
        cmd += "mongo --eval '{ping: " + ping + "}'"
        if self.cmd_prefix:
            cmd += '"'
        rc, stdout, stderr, exc = run_cmd(cmd)

        stdout = stdout.strip().split('\n')

        if rc or len(stdout) < 1 or stdout[-1] != ping:
            res = False
            comment = "'{}' returned no ping".format(cmd)
            return res, comment

        return res, comment

from trix_status.utils import run_cmd
from trix_status.controllers.services.checker import Checker


class Named(Checker):

    def status(self):
        res, comment = True, ""
        cmd = self.cmd_prefix
        cmd += (
            "dig +tries=1 +time={} +short @localhost localhost"
        ).format(self.timeout)
        expected = "127.0.0.1"
        rc, stdout, stderr, exc = run_cmd(cmd)
        if rc or stdout.strip() != "127.0.0.1":
            comment = "'{}' did not return '{}'".format(
                cmd, expected
            )
            res = False
        return res, comment

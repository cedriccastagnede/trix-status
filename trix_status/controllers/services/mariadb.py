from trix_status.utils import run_cmd
from trix_status.controllers.services.checker import Checker


class Mariadb(Checker):

    def status(self):
        res, comment = True, ""

        num = "123"
        cmd = self.cmd_prefix
        if self.cmd_prefix:
            cmd += '"'
        cmd += "mysql -e 'select " + num + ";' -s -r"
        if self.cmd_prefix:
            cmd += '"'
        rc, stdout, srderr, exc = run_cmd(cmd)
        stdout = stdout.strip()
        if rc or stdout != num:
            res = False
            comment = '{} returned unexpected result'.format(cmd)
            return res, comment

        return res, comment

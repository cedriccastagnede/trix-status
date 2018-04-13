from trix_status.utils import run_cmd
from trix_status.controllers.services.checker import Checker


class Munge(Checker):

    def status(self):
        res, comment = True, ""

        cmd = 'munge -n | unmunge'
        rc, stdout, stderr, exc = run_cmd(cmd)

        stdout = stdout.strip().split('\n')

        if len(stdout) < 1 or len(stdout[0].split()) < 2:
            res = False
            comment = "'{}' returned no status".format(cmd)
            return res, comment

        status = stdout[0].split()[1]
        if rc or status != 'Success':
            res = False
            comment = "'{}' returned error".format(cmd)
            return res, comment

        return res, comment

from trix_status.utils import run_cmd
from trix_status.controllers.services.checker import Checker


class Slurmdbd(Checker):

    def status(self):
        res, comment = True, ""

        cmd = 'sacctmgr -n list cluster'
        rc, stdout, stderr, exc = run_cmd(cmd)

        stdout = stdout.strip().split('\n')

        if rc or len(stdout) < 1 or len(stdout[0].split()) < 2:
            res = False
            comment = "'{}' returned no clusters configured".format(cmd)
            return res, comment

        return res, comment

from trix_status.utils import run_cmd
from trix_status.controllers.services.checker import Checker


class Slurmctld(Checker):

    def status(self):
        res, comment = True, ''

        cmd = (
            'scontrol ping'
        )

        rc, stdout, stderr, exc = run_cmd(cmd, timeout=self.timeout)
        expected1 = 'Slurmctld(primary/backup) at '
        expected2 = ' are UP/DOWN'

        if rc != 0:
            res = False
            comment = "'{}' exit code is not 0".cormat(cmd)
            return res, comment

        stdout = stdout.strip()

        if (len(stdout) < len(expected1) + len(expected2)
                or stdout[:len(expected1)] != expected1
                or stdout[-len(expected2):] != expected2):

            res = False

            comment = "Stdout of '{}' is not matching '{}...{}'".format(
                cmd, expected1, expected2
            )

            return res, comment

        return res, comment

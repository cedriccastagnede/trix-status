from trix_status.utils import run_cmd
from trix_status.controllers.services.checker import Checker


class Chronyd(Checker):

    def status(self):
        res, comment = True, ''

        cmd = self.cmd_prefix
        cmd += 'chronyc tracking'
        rc, stdout, stderr, exc = run_cmd(cmd)

        if rc != 0:
            res = False
            comment = "'{}' exit code is not 0".cormat(cmd)
            return res, comment

        stdout = stdout.split('\n')

        if len(stdout) < 1:
            res = False
            comment = "'{}' returned no output".format(cmd)
            return res, comment

        line1 = stdout[0]
        line1 = line1.split()

        # Magic number is from man chronyc
        if line1[3] == '7F7F0101':
            res = False
            comment = 'Computer is not synchronised to any external source.'
            return res, comment

        cmd = self.cmd_prefix
        cmd += 'chronyc sources'
        rc, stdout, stderr, exc = run_cmd(cmd)

        if rc != 0:
            res = False
            comment = "'{}' exit code is not 0".cormat(cmd)
            return res, comment

        stdout = stdout.strip().split('\n')
        if len(stdout) < 1:
            res = False
            comment = "'{}' returned no output".format(cmd)
            return res, comment

        try:
            n_sources = int(stdout[0].split()[-1])
        except (IndexError, ValueError):
            n_sources = 0

        if n_sources < 1:
            res = False
            comment = "'{}' did not return numnber of sources".format(cmd)
            return res, comment

        try:
            is_current_synced = bool(
                [True for e in stdout[-n_sources:] if e[1] == '*']
            )
        except IndexError:
            is_current_synced = False

        if not is_current_synced:
            res = False
            comment = "'{}' returned no currenly synced servers".format(cmd)
            return res, comment

        return res, comment

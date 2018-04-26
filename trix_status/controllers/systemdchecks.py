from trix_status.utils import run_cmd
from trix_status.config import category
import importlib

class SystemdChecks(object):

    def check_systemd_unit(self, answer, service, host=None,
                           need_started=True, need_enabled=True):

        if host is not None:
            cmd_prefix = (
                "ssh -o ConnectTimeout={} -o StrictHostKeyChecking=no {} "
            ).format(self.args.timeout, host)

        else:
            cmd_prefix = ""

        cmd = cmd_prefix
        cmd += "systemctl is-enabled " + service
        rc, stdout, stderr, exc = run_cmd(cmd)

        is_enabled = stdout.strip()

        if need_enabled and is_enabled != "enabled":
            answer['status'] = 'ERR'
            answer['category'] = category.ERROR
            answer['info'] = 'systemd'
            answer['details'] = 'Autostart is disabled for the unit.'

        if not need_enabled and is_enabled != "disabled":
            answer['status'] = 'ERR'
            answer['category'] = category.ERROR
            answer['info'] = 'systemd'
            answer['details'] = 'Autostart is enabled for the unit.'

        cmd = cmd_prefix
        cmd += "systemctl status {}".format(service)
        rc, stdout, stderr, exc = run_cmd(cmd)

        if rc:
            is_started = False
        else:
            is_started = True

        if need_started and not is_started:
            answer['status'] = 'ERR'
            answer['category'] = category.ERROR
            answer['info'] = 'systemd'
            answer['details'] = 'Unit should run on this host.'
            return answer

        if not need_started and is_started:
            answer['status'] = 'ERR'
            answer['category'] = category.ERROR
            answer['info'] = 'systemd'
            answer['details'] = 'Unit should not run on this host.'
            return answer

        if not is_started:
            return answer

        answer['status'] = 'UP'
        answer['category'] = category.GOOD
        answer['info'] = ''

        answer = self.service_checker(answer, service, host)
        return answer

    def service_checker(self, answer, service, host=None):
        class_path = "trix_status.controllers.services." + service
        class_name = service.capitalize()
        try:
            checker_module = importlib.import_module(class_path)
            checker_class = getattr(checker_module, class_name)
        except ImportError:
            answer['details'] += " No checker module for " + service
            return answer
        except AttributeError:
            answer['details'] += " No checker class " + class_name
            return answer

        checker = checker_class(args=self.args, host=host)
        res, comment = checker.status()
        if not res:
            answer['status'] = "DOWN"
            answer['category'] = category.ERROR
            answer['info'] = 'functional checker'
            answer['details'] += " "
            answer['details'] += comment
            return answer

        answer['status'] = "WORKS"
        answer['category'] = category.GOOD

        return answer

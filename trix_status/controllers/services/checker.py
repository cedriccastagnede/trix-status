from abc import ABCMeta, abstractmethod
import logging


class Checker(object):

    __metaclass__ = ABCMeta

    def __init__(self, args, host=None):
        self.timeout = args.timeout
        if host is None:
            self.cmd_prefix = ""
        else:
            self.cmd_prefix = (
                "ssh -o ConnectTimeout={} -o StrictHostKeyChecking=no {} "
            ).format(self.timeout, host)
        module_name = self.__module__ + "." + type(self).__name__
        self.log = logging.getLogger(module_name)

    @abstractmethod
    def status(self):
        res, comment = True, ""
        return res, comment

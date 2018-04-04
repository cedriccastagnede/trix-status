from abc import ABCMeta, abstractmethod


class AbstractStatus(object):

    __metaclass__ = ABCMeta

    @abstractmethod
    def get(self):
        pass

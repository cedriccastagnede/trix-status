from trix_status.controllers.services.checker import Checker
import requests
import logging

try:
    import luna
except:
    luna = None


class Lweb(Checker):

    def status(self):
        res, comment = True, ""
        if luna is None:
            res = False
            comment = "Luna is not installed"
            return res, comment

        logging.getLogger("requests").setLevel(logging.WARNING)

        port = int(luna.Cluster().get('frontend_port'))
        addr = luna.Cluster().get('frontend_address')

        url = 'http://{}:{}/luna?step=boot'.format(addr, port)
        r = requests.get(url)
        content = r.content.split('\n')
        if r.ok and len(content) > 0 and content[0] == '#!ipxe':
            return res, comment

        res = False
        comment = "Answer from '{}' is wrong".format(url)

        return res, comment

from trix_status.controllers.services.checker import Checker
import ldap
import ConfigParser


class Slapd(Checker):

    def status(self):
        res, comment = True, ""

        config = ConfigParser.ConfigParser()
        if not config.read("/etc/obol.conf"):
            res = False
            comment = 'No /etc/obol.conf found'
            return res, comment

        host = self.load_param(config, "ldap", "host")
        bind_dn = self.load_param(config, "ldap", "bind_dn")
        bind_pass = self.load_param(config, "ldap", "bind_pass")
        b = self.load_param(config, "ldap", "base_dn")

        if host is None or bind_dn is None or bind_pass is None or b is None:
            res = False
            comment = 'Unable to find all parameters to connect to LDAP'
            return res, comment

        try:

            conn = ldap.initialize(host)
            conn.simple_bind_s(bind_dn, bind_pass)
        except ldap.LDAPError:
            res = False
            comment = 'LDAP returned an error on connect'
            return res, comment

        base_dn = 'ou=People,' + b
        filt = '(objectclass=person)'
        attrs = ['uid']

        users = len(conn.search_s(base_dn, ldap.SCOPE_SUBTREE, filt, attrs))
        if users < 1:
            res = False
            comment = 'No users found'
            return res, comment

        return res, comment

    def load_param(self, config, group, param):
        try:
            return config.get(group, param)
        except Exception:
            return None


#!/usr/bin/env python3
import re
import time
import pprint

class BaseProfile:
    def __init__(self, local_realm, debug=False):
        self.parent_realm = local_realm
        self.halt_on_error = False
        self.exit_on_error = False
        self.debug = debug or local_realm.debug
        self.profiles = []


    def json_get(self, _req_url, debug_=False):
        return self.parent_realm.json_get(_req_url, debug_=False)

    def json_post(self, req_url=None, data=None, debug_=False, suppress_related_commands_=None):
        return self.parent_realm.json_post(_req_url=req_url,
                                           _data=data,
                                           suppress_related_commands_=suppress_related_commands_,
                                           debug_=debug_)

    def parse_time(self, time_string):
        return self.parent_realm.parse_time(time_string)

    def stopping_cx(self, name):
        return self.parent_realm.stop_cx(name)

    def cleanup_cxe_prefix(self, prefix):
        return self.parent_realm.cleanup_cxe_prefix(prefix)

    def rm_cx(self, cx_name):
        return self.parent_realm.rm_cx(cx_name)

    def rm_endp(self, ename, debug_=False, suppress_related_commands_=True):
        self.parent_realm.rm_endp(ename, debug_=False, suppress_related_commands_=True)

    def name_to_eid(self, eid):
        return self.parent_realm.name_to_eid(eid)

    def set_endp_tos(self, ename, _tos, debug_=False, suppress_related_commands_=True):
        return self.parent_realm.set_endp_tos(ename, _tos, debug_=False, suppress_related_commands_=True)

    def wait_until_endps_appear(self, these_endp, debug=False):
        return self.parent_realm.wait_until_endps_appear(these_endp, debug=False)

    def wait_until_cxs_appear(self, these_cx, debug=False):
        return self.parent_realm.wait_until_cxs_appear(these_cx, debug=False)

    def logg(self, message=None):
        self.parent_realm.logg(message)

    def add_to_profiles(self, profile):
        self.profiles.append(profile)

    def get_current_profiles(self):
        return self.profiles
    
#!/usr/bin/env python3

"""
    This script will create a variable number of layer3 stations each with their own set of cross-connects and endpoints.
    The connections are not started, nor are stations set admin up in this script.

    Example script:
    './tele2_rvr.py --radio wiphy0 --ssid lanforge --password password --security wpa2'
    './tele2_rvr.py --station_list sta00,sta01 --radio wiphy0 --ssid lanforge --password password --security wpa2'
    './tele2_rvr.py --station_list sta00 sta01 --radio wiphy0 --ssid lanforge --password password --security wpa2'
"""

import os
import importlib
import logging
import sys
import argparse
import time
if 'py-json' not in sys.path:
    sys.path.append('../py-json')
from LANforge import LFUtils
from LANforge import lfcli_base
from LANforge.lfcli_base import LFCliBase
from LANforge.LFUtils import *
import realm
from realm import Realm

if sys.version_info[0] != 3:
    logger.critical("This script requires Python 3")
    exit(1)

if 'py-json' not in sys.path:
    sys.path.append(os.path.join(os.path.abspath('..'), 'py-json'))

# sys.path.append(os.path.join(os.path.abspath(__file__ + "../../../")))
# lf_logger_config = importlib.import_module("py-scripts.lf_logger_config")
# logger = logging.getLogger(__name__)

class CreateAttenuator(Realm):
    def __init__(self, host, port, serno, idx, val,
                 _debug_on=False,
                 _exit_on_error=False,
                 _exit_on_fail=False):
        super().__init__(host, port, debug_=_debug_on, _exit_on_fail=_exit_on_fail)
        self.host = host
        self.serno = serno
        self.idx = idx
        self.val = val
        self.attenuator_profile = self.new_attenuator_profile()
        self.attenuator_profile.atten_idx = self.idx
        self.attenuator_profile.atten_val = self.val
        self.attenuator_profile.atten_serno = self.serno
        
        self.defaults = self.new_attenuator_profile()
        self.defaults.atten_serno = 'all'
        self.defaults.atten_idx = 'all'
        self.defaults.atten_val = 955

    def _build(self):
        self.attenuator_profile.create()
        # self.attenuator_profile.show()

    def _configure(self, serno=None, idx=None, val=None):
        # self.attenuator_profile = self.new_attenuator_profile()
        self.attenuator_profile.atten_serno = serno
        self.attenuator_profile.atten_idx = idx
        self.attenuator_profile.atten_val = val
        self._apply()
    
    def _apply(self):
        self._build()
    
    def _print(self, iteration, db):
        print('[DB_ATTEN_LOG] {} - {}'.format(datetime.now().isoformat(), json.dumps({'iteration': iteration, 'timestamp': datetime.utcnow().isoformat(), 'db': db})))
    
    def _attenuate(self, val):
        self.attenuator_profile.atten_val = val
        self._build()

    def reset_all(self):
        self.defaults.create()
    
    def base_profile(self, iteration=0):
        self.attenuator_profile = self.new_attenuator_profile()
        self._configure('3066', 'all', 955)
        self._configure('3067', 'all', 955)        # Throttlers chamber (Node2) (Air)
        self._configure('3068', 'all', 955)
        self._configure('3070', 'all', 0)          # Client running service (Node1)
        self._configure('3073', 0, 500)            # Conducted Node2 - Needs to be open for throttlers
        self._configure('3073', 1, 500)            # Conducted Node2 - Needs to be open for throttlers
        self._configure('3073', 2, 955)            # Conducted Node1 - Needs to be completely attenuated
        self._configure('3073', 3, 955)            # Conducted Node1 - Needs to be completely attenuated
        self._configure('3076', 'all', 955)
        self._configure('3084', 'all', 955)
        self._apply()
        self._print(iteration, 0)

    def disabled_attenuation_profile(self, iteration):
        self._configure('3070', 'all', 0)
        self._apply()
        self._print(iteration, 0)
    def low_attenuation_profile(self, iteration):
        self._configure('3070', 'all', 100)
        self._apply()
        self._print(iteration, 10)
    def mid_attenuation_profile(self, iteration):
        self._configure('3070', 'all', 200)
        self._apply()
        self._print(iteration, 20)
    def high_attenuation_profile(self, iteration):
        self._configure('3070', 'all', 300)
        self._apply()
        self._print(iteration, 30)


class Tele2RateVersusRange(LFCliBase):
    def __init__(self, lfclient_host, lfclient_port, ssid, paswd, security, radio, sta_list=None, name_prefix="T2RvR", upstream="eth1", traffic_direction='downstream'):
        super().__init__(lfclient_host, lfclient_port)
        self.host = lfclient_host
        self.port = lfclient_port
        self.ssid = ssid
        self.paswd = paswd
        self.security = security
        self.radio = radio
        self.sta_list = sta_list
        self.name_prefix = name_prefix
        self.upstream = upstream
        self.traffic_direction = traffic_direction

        self.local_realm = realm.Realm(lfclient_host=self.host, lfclient_port=self.port)
        self.station_profile = self.local_realm.new_station_profile()
        self.station_profile.ssid = self.ssid
        self.station_profile.ssid_pass = self.paswd
        self.station_profile.security = self.security
        self.cx_profile = self.local_realm.new_l3_cx_profile()
        self.cx_profile.host = self.host
        self.cx_profile.port = self.port
        self.cx_profile.name_prefix = self.name_prefix

        if self.traffic_direction == 'downstream':
            self.cx_profile.side_a_min_bps = 1e10
            self.cx_profile.side_a_max_bps = 1e10
            self.cx_profile.side_b_min_bps = 0
            self.cx_profile.side_b_max_bps = 0
        elif self.traffic_direction == 'upstream':
            self.cx_profile.side_b_min_bps = 1e10
            self.cx_profile.side_b_max_bps = 1e10
            self.cx_profile.side_a_min_bps = 0
            self.cx_profile.side_a_max_bps = 0


    def precleanup(self):
        self.cx_profile.cleanup_prefix()
        for sta in self.sta_list:
            self.local_realm.rm_port(sta, check_exists=True)
        LFUtils.wait_until_ports_disappear(base_url=self.lfclient_url,
                                           port_list=self.sta_list,
                                           debug=self.debug)
        time.sleep(1)
        print('sta_list:', self.sta_list)

    def load_blank_database(self):
        print('Loading blank database...')
        data = {
            "name": "BLANK",
            "action":"overwrite",
            "clean_dut":"yes",
            "clean_chambers": "yes"
        }
        self.json_post("/cli-json/load", data)
        time.sleep(5)

    def build(self):
        self.load_blank_database()
        resource = 1
        # LFUtils.(self.host, self.sta_list)
        try:
            data = LFUtils.port_dhcp_up_request(resource, self.upstream)
            print("set_port request data: {}".format(data))
            self.json_post("/cli-json/set_port", data)
        except:
            print("LFUtils.port_dhcp_up_request didn't complete ")
            print("or the json_post failed either way {} did not set up dhcp so test may not pass data ".format(self.side_b))

        print("password: {}".format(self.paswd))
        self.station_profile.use_security(self.security, self.ssid, self.paswd)
        self.station_profile.create(radio=self.radio, sta_names_=self.sta_list)
        print('sta_names_: {}, station_profile.station_names: {}'.format(self.sta_list, self.station_profile.station_names))
        self.cx_profile.create(endp_type="lf_tcp", side_a=self.station_profile.station_names, side_b=self.upstream,
                               sleep_time=0)

    def start(self):
        self.station_profile.admin_up()
        temp_stas = self.station_profile.station_names.copy()
        # temp_stas = sta_list
        print('station_profile.station_names:', temp_stas)
        if self.local_realm.wait_for_ip(temp_stas):
            self._pass("All stations got IPs")
        else:
            self._fail("Stations failed to get IPs")
            self.exit_fail()
        self.cx_profile.start_cx()


    def stop(self):
        # Bring stations down
        self.station_profile.admin_down()
        self.cx_profile.stop_cx()


def main():
    parser = argparse.ArgumentParser(description="Tele2 RvR Script")
    parser.add_argument('-hst', '--host', type=str, help='host name')
    parser.add_argument('-s', '--ssid', type=str, help='ssid for client')
    parser.add_argument('-pwd', '--passwd', type=str, help='password to connect to ssid')
    parser.add_argument('-sec', '--security', type=str, help='security')
    parser.add_argument('-rad', '--radio', type=str, help='radio at which client will be connected')
    #parser.add_argument()
    args = parser.parse_args()
    num_sta = 1
    station_list = LFUtils.port_name_series(prefix="sta",
                                            start_id=0,
                                            end_id=num_sta - 1,
                                            padding_number=10000,
                                            radio=args.radio)
    obj = Tele2RateVersusRange(lfclient_host= args.host, lfclient_port=8080, ssid=args.ssid , paswd=args.passwd, security=args.security, radio=args.radio, sta_list=station_list)
    obj.precleanup()
    obj.build()
    obj.start()


if __name__ == '__main__':
    main()

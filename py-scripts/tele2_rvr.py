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
from datetime import datetime
import json

if sys.version_info[0] != 3:
    logger.critical("This script requires Python 3")
    exit(1)

if 'py-json' not in sys.path:
    sys.path.append(os.path.join(os.path.abspath('..'), 'py-json'))

# sys.path.append(os.path.join(os.path.abspath(__file__ + "../../../")))
# lf_logger_config = importlib.import_module("py-scripts.lf_logger_config")
# logger = logging.getLogger(__name__)

class CreateRvRAttenuator(Realm):
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
        self.ddb_step_size = 50  # Example: 50 = 0.5 dB attenuation added for each step in the RvR test

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
        self._configure('3067', 'all', 955)        # Node2 (Air)
        self._configure('3068', 'all', 955)
        self._configure('3070', 'all', 955)        # Node1
        self._configure('3073', 0, 955)            # Conducted Node2
        self._configure('3073', 1, 955)            # Conducted Node2
        self._configure('3073', 2, 955)            # Conducted Node1
        self._configure('3073', 3, 955)            # Conducted Node1
        self._configure('3076', 'all', 955)
        self._configure('3084', 'all', 955)        # RvR client in MobileStations chamber
        self._apply()
        self._print(iteration, 0)

    def increase_attenuation(self, iteration):
        self._configure('3084', 'all', self.ddb_step_size)
        self._apply()
        self._print(iteration, 0)


class Tele2RateVersusRange(LFCliBase):
    def __init__(self, lfclient_host, lfclient_port, ssid, paswd, security, radio, duts, sta_list=None, name_prefix="T2RvR", upstream="eth1", traffic_direction='downstream'):
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
        self.duts = duts

        self.local_realm = realm.Realm(lfclient_host=self.host, lfclient_port=self.port)
        self.station_profile = self.local_realm.new_station_profile()
        self.station_profile.ssid = self.ssid
        self.station_profile.ssid_pass = self.paswd
        self.station_profile.security = self.security
        self.cx_profile = self.local_realm.new_l3_cx_profile()
        self.cx_profile.host = self.host
        self.cx_profile.port = self.port
        self.cx_profile.name_prefix = self.name_prefix
        self.attenuator = CreateRvRAttenuator(host=self.host, port=self.port, serno='all', idx='all', val=955)

        # RvR settings
        self.num_iterations = 1  # Number of full iterations (0 -> 95 dB) to perform before quitting.
        self.step_length_sec = 15  # Number of seconds to run traffic per attenuation step

        requested_tput = 10000000000  # 10 Gbit/s
        if self.traffic_direction == 'downstream':
            self.cx_profile.side_a_min_bps = requested_tput
            self.cx_profile.side_a_max_bps = self.cx_profile.side_a_min_bps
            self.cx_profile.side_b_min_bps = 0
            self.cx_profile.side_b_max_bps = 0
        elif self.traffic_direction == 'upstream':
            self.cx_profile.side_b_min_bps = requested_tput
            self.cx_profile.side_b_max_bps = self.cx_profile.side_b_max_bps
            self.cx_profile.side_a_min_bps = 0
            self.cx_profile.side_a_max_bps = 0

    def next_rvr_step(self):
       pass

    def wait_for_cx_to_start(self, cxs=None, timeout=300):
        for x in cxs:
            give_up_ts = time.time() + timeout
            while True:
                cx_state = self.json_get("/cx/{}".format(x), debug_=self.debug)
                # print('CX {} state: {}'.format(x, cx_state))
                if cx_state[x]['state'] == 'Run':
                    print('Cross-endpoint {} has started: {}'.format(x, cx_state[x]['state']))
                    break
                else:
                    if time.time() > give_up_ts:
                        print('Error: Cross-endpoint never started after {} sec: {}. State: {}'.format(timeout, x, cx_state[x]['state']))
                        break
                    print('Waiting for Cross-endpoint {} to start.. State: {}'.format(x, cx_state[x]['state']))
                    time.sleep(1)

    # Create stations and l3 endpoints
    def create_station(self, autostart=False):
        self.station_profile.use_security(self.security, self.ssid, self.paswd)
        self.station_profile.create(radio=self.radio, sta_names_=self.sta_list)
        print('sta_names_: {}, station_profile.station_names: {}'.format(self.sta_list, self.station_profile.station_names))
        self.cx_profile.create(endp_type="lf_tcp", side_a=self.station_profile.station_names, side_b=self.upstream, sleep_time=1)
        if autostart:
            self.start_station_traffic()

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
        # self.load_blank_database()
        resource = 1

        # Initiate the upstream port
        try:
            data = LFUtils.port_dhcp_up_request(resource, self.upstream)
            print("set_port request data: {}".format(data))
            self.json_post("/cli-json/set_port", data)
        except:
            print("LFUtils.port_dhcp_up_request didn't complete ")
            print("or the json_post failed either way {} did not set up dhcp so test may not pass data ".format(self.side_b))

        # Set up attenuators
        if self.attenuator is not None:
            print('Configuring attenuators.......')
            # self.attenuator.base_profile()
            print('Finished configuring attenuators!')
        else:
            exit('Error: No attenuator detected')

    def start_station_traffic(self):
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
        print('Waiting for these cross endpoints to appear:', self.cx_profile.get_cx_names())
        self.local_realm.wait_until_cxs_appear(self.cx_profile.get_cx_names())
        self.wait_for_cx_to_start(self.cx_profile.get_cx_names())
        time.sleep(1)
 
    def start(self):
        print('Starting RvR test for {} iterations...'.format(self.num_iterations))
        self.precleanup()
        self.create_station() 
        for i in range(self.num_iterations):
            for dut in self.duts:
                for step, ddb in enumerate(range(0, 1000, self.attenuator.ddb_step_size)):
                    if step != 0:
                        self.attenuator.increase_attenuation(i)
                    self.start_station_traffic()
                    print('[Iteration={}|DUT={}|atten={}] Running traffic on stations for {} seconds..'.format(self.num_iterations, dut, ddb, self.step_length_sec))
                    time.sleep(self.step_length_sec)
                    self.stop()

    def stop(self):
        # Bring stations down
        print('Bringing stations down..')
        self.station_profile.admin_down()
        self.cx_profile.stop_cx()


def main():
    parser = argparse.ArgumentParser(description="Tele2 RvR Script")
    parser.add_argument('-hst', '--host', type=str, help='host name')
    parser.add_argument('-prt', '--port', type=int, help='host port')
    parser.add_argument('-s', '--ssid', type=str, help='ssid for client')
    parser.add_argument('-pwd', '--passwd', type=str, help='password to connect to ssid')
    parser.add_argument('-sec', '--security', type=str, help='security')
    parser.add_argument('-rad', '--radio', type=str, help='radio at which client will be connected')
    #parser.add_argument()
    args = parser.parse_args()
    num_sta = 1
    duts = ['L2']
    station_list = LFUtils.port_name_series(prefix="sta",
                                            start_id=0,
                                            end_id=num_sta - 1,
                                            padding_number=10000,
                                            radio=args.radio)
    obj = Tele2RateVersusRange(lfclient_host= args.host, lfclient_port=args.port, ssid=args.ssid , paswd=args.passwd, security=args.security, radio=args.radio, sta_list=station_list, duts=duts)
    obj.precleanup()
    obj.build()
    obj.start()


if __name__ == '__main__':
    main()

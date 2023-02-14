#!/usr/bin/env python3

"""
    This script will create a streamed RvR test on multiple DUTs. For each DUT, a non-standard RvR test is performed on the configured radios and traffic directions.
    The test results are collected from the LANForge API and streamed to the telemetry API.

    Example script:
    python3 tele2_rvr.py --host 192.168.0.10 --port 8080 --ssid "DUT-CPELAB" --passwd x --security wpa2 --duts x,y --radios wiphy0,wiphy1 --traffic_direction downstream
"""

import os
# import importlib
# import logging
import sys
import argparse
import time
if 'py-json' not in sys.path:
    sys.path.append('../py-json')
from LANforge import LFUtils, LFRequest
from LANforge import lfcli_base
from LANforge.lfcli_base import LFCliBase
from LANforge.LFUtils import *
import realm
from realm import Realm
from datetime import datetime
import json
import uuid
import subprocess

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
        self.iteration = 0

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
    
    def _print(self, db):
        print('[DB_ATTEN_LOG] {} - {}'.format(datetime.now().isoformat(), json.dumps({'iteration': self.iteration, 'timestamp': datetime.utcnow().isoformat(), 'db': db})))
    
    def _attenuate(self, val):
        self.attenuator_profile.atten_val = val
        self._build()

    def reset_all(self):
        self.defaults.create()
    
    def base_profile(self, minimal=False):
        self.attenuator_profile = self.new_attenuator_profile()
        if minimal:
            self._configure('3084', 'all', 0)
        else:    
            self._configure('3066', 'all', 955)
            self._configure('3067', 'all', 955)        # Node2 (Air)
            self._configure('3068', 'all', 955)
            self._configure('3070', 'all', 955)        # Node1
            self._configure('3073', 0, 955)            # Conducted Node2
            self._configure('3073', 1, 955)            # Conducted Node2
            self._configure('3073', 2, 955)            # Conducted Node1
            self._configure('3073', 3, 955)            # Conducted Node1
            self._configure('3076', 'all', 955)
            self._configure('3084', 'all', 0)        # RvR client in MobileStations chamber
        self._apply()
        self._print(0)

    def increase_attenuation(self, attenuation_ddb):
        self._configure('3084', 'all', attenuation_ddb)
        self._apply()
        self._print(0)


class DUTController():
    """
    # Basic power on/off loop
    #!/bin/bash
    #zap right
    for ((i = 0 ; i < 200 ; i++)); do
        echo $i
        echo "$(mono net-pwrctrl.exe 192.168.0.54,75,77,rel,1,off,admin,anel >/dev/null)"
        sleep 30
        echo "$(mono net-pwrctrl.exe 192.168.0.54,75,77,rel,1,on,admin,anel >/dev/null)"
        sleep 300
    done
    """
    def __init__(self, ip):
        self.ip = ip
        # Connections matching powerctl panel per DUT
        self.dut_to_port = {
                'L2': 1,
                'C4': 2,
                }

    def power_ctl(self, cmd):
        if cmd not in ['on', 'off']:
            raise(TypeError)
        if self.port is None:
            print('Must run set_dut(dut_name) first.')
            raise(TypeError)
        subprocess.Popen(f'mono /usr/local/bin/net-pwrctrl.exe {self.ip},75,77,rel,{self.port},{cmd},admin,anel >/dev/null', shell=True)

    def power_off(self):  # Pwr off only selected DUT
        self.power_ctl('off')

    def power_on(self):  # Pwr on only selected DUT
        self.power_ctl('on')

    def set_dut(self, dut):
        try:
            self.port = self.dut_to_port[dut]
        except KeyError as ke:
            print(f'Invalid DUT: {dut}')
            raise(ke)

    def power_off_all_duts():
        for port in self.dut_to_port.values():
            self.power_ctl('off')


class Tele2RateVersusRange(LFCliBase):
    def __init__(self, lfclient_host, lfclient_port, ssid, paswd, security, radios, duts, name_prefix="T2RvR", upstream="eth1", traffic_direction='downstream'):
        super().__init__(lfclient_host, lfclient_port)
        self.host = lfclient_host
        self.port = lfclient_port
        self.ssid = ssid
        self.paswd = paswd
        self.security = security
        self.name_prefix = name_prefix
        self.upstream = upstream
        self.shelf = "1"
        self.resource = "1"
        # "1.1.eth1" = MobileStations eth1
        self.full_upstream_path = self.shelf + "." + self.resource + "." + self.upstream 
        self.local_realm = realm.Realm(lfclient_host=self.host, lfclient_port=self.port)
        self.attenuator = CreateRvRAttenuator(host=self.host, port=self.port, serno='all', idx='all', val=955)
        self.num_sta = 1
        self.scenario_id = uuid.uuid4().hex[:8]
        self.dut_ctl = DUTController('192.168.0.54')

        # Set to locally track currently running endpoints
        self._running_endpoints = set()

        # Cross endpoints for each client traffic direction
        self.traffic_direction = traffic_direction
        if self.traffic_direction == 'both':
            self.endpoints = {'downstream': self.create_cx('downstream'), 'upstream': self.create_cx('upstream')}
        else:
            self.endpoints = {self.traffic_direction: self.create_cx(self.traffic_direction)}

        # Where to dump all the l2/l3 stats
        self.telemetry_stats_host = 'http://127.0.0.1:8082'
        self.telemetry_stats_endpoint = '/lanforge_stats'

        # RvR settings
        self.duts = [item for item in duts.split(',')]
        self.radios = [item for item in radios.split(',')]
        if len(self.duts) == 0 or len(self.radios) == 0:
            raise ValueError("No DUTs or radios specified: {} -> {}".format(self.duts, self.radios))
        
        #### Station or radio capabilites
        ## NSS enums
        ## Diversity/All  | 0
        ## Fixed-A (1x1)  | 1
        ## AB (2x2)       | 4
        ## ABC (3x3)      | 7
        ## ABCD (4x4)     | 8
        ## 8x8 (8x8)      | 9
        self.nss = 4

        self.create_station_profiles()
        self.num_iterations = 5  # Number of full iterations (0 -> 95 dB) to perform before quitting.
        self.step_length_sec = 15  # Number of seconds to run traffic per attenuation step
        self.max_attempts_on_fail = 3  # Number of times to retry an attenuation step before going to the next DUT or iteration
        self.total_fail_threshold = 0.90  # Percentage of tests in total that needs to fail before going to the next DUT or iteration

    
    def create_station_profiles(self):
        self.sta_list = {radio: [] for radio in self.radios}
        self.station_profiles = dict()
        for radio in self.radios:
            if radio == 'wiphy0':
                padding = 10000
            elif radio == 'wiphy1':
                padding = 11000
            self.sta_list[radio].append(LFUtils.port_name_series(prefix="sta", start_id=0, end_id=self.num_sta - 1, padding_number=padding, radio=radio))
            self.sta_list[radio] = [item for sublist in self.sta_list[radio] for item in sublist]

            self.station_profiles[radio] = self.local_realm.new_station_profile()
            self.station_profiles[radio].ssid = self.ssid
            self.station_profiles[radio].ssid_pass = self.paswd
            self.station_profiles[radio].security = self.security
            # self.station_profiles[radio].wifi_txo_data['txo_nss'] = self.sta_nss

    # Fetch all the active running CX from the LF API
    def get_all_running_cx(self):
        running_cx = list()
        endpoints = self.get_endpoint_stats()
        for endpoint in endpoints.values():
            if endpoint['endpoint']['run']:
                endpoints.append(endpoint['endpoint']['name'][:-2])
        return running_cx
    
    def cleanup_running_cxes(self):
        running_cx = self.get_running_cx()
        for cx_profile in self.endpoints.values():
            for cx_name in cx_profile.get_cx_name():
                if cx_name in running_cx:
                    cx_profile.cleanup_prefix()

    def configure_radio(self, radio):
        lf_r = LFRequest.LFRequest("http://" + self.host + ":" + str(self.port) + "/cli-json/set_wifi_radio")
        lf_r.addPostData({
            "shelf":self.shelf,
            "resource":self.resource,
            "radio":radio,
            "mode":"NA",  # Can be overridden on each station_profile
            "txpower": "auto",
            "suppress_preexec_method": "true",
            "antenna": self.nss,
        })  
        lf_r.jsonPost()

    def get_port_stats(self):
        port_map = dict()
        ports = self.json_get('/port/list')
        if ports is None:
            raise("No data")
        for record in ports['interfaces']:
            for full_port_name, entry in record.items():
                
                # Ignore other ports or stations not defined in the test
                if full_port_name == self.full_upstream_path:
                    urlEntry = entry['port'].replace('.', '/')
                    port_data = self.json_get('/port/' + urlEntry)
                    port_map[entry['port']] = port_data
                for radio in self.radios:
                    if full_port_name in self.station_profiles[radio].station_names.copy():
                        urlEntry = entry['port'].replace('.', '/')
                        port_data = self.json_get('/port/' + urlEntry)
                        port_map[entry['port']] = port_data


        return port_map

    def telemetry_post(self, data, debug=False):
        lf_r = LFRequest.LFRequest(url=self.telemetry_stats_host,
                                       uri=self.telemetry_stats_endpoint,
                                       debug_=debug,
                                       die_on_error_=self.exit_on_error)
        lf_r.addPostData(data)
        json_response = lf_r.json_post(show_error=debug,
                                           debug=debug,
                                           die_on_error_=self.exit_on_error)
        if json_response is None:
            self.add_event_and_print(name='T2RvR_TelemetryError', message='Failed to post data to telemetry cache')
        return json_response

    def add_stats_metadata(self, data):
        data['metadata'] = {
            # Unique ID for this run and 24h window
            'scenario_iteration_id': datetime.now().strftime("%Y%m%d") + "_" + self.scenario_id,
            'duts': self.duts,
            'radios': self.radios,
            'ssid': self.ssid,
            'security': self.security,
            'num_sta': self.num_sta,
            'num_iterations': self.num_iterations,
            'step_length_sec': self.step_length_sec,
            'max_attempts_on_fail': self.max_attempts_on_fail,
            'total_fail_threshold': self.total_fail_threshold,
            'traffic_direction': self.traffic_direction,
            'upstream': self.full_upstream_path,
        }
        return data

    def get_endpoint_stats(self):
        endpoint_map = dict()
        endpoints = self.json_get('/endp/list')
        if endpoints is None:
            raise('No endpoint data')
        for record in endpoints['endpoint']:
            for alias, entry in record.items():
                port = '.'.join(entry['entity id'].split('.')[:3])
                endpoint = self.json_get('/endp/' + alias)
                endpoint_map[port] = endpoint
        return endpoint_map

    def collect_stats(self):
        try:
            l2_data = self.get_port_stats()
            l3_data = self.get_endpoint_stats()
        except KeyError as key_err:
            self.add_event_and_print(name='T2RvR_APIError', message='KeyError in collect_stats: {}'.format(key_err))
        except Exception as err:
            self.add_event_and_print(name='T2RvR_UnknownStatsError', message='Exceptionin collect_stats: {}'.format(err))
        else:
            report = {
                'test_name': 'Tele2RateVersusRange',
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'layer2': [l2_data],
                'layer3': [l3_data],
            }
            report = self.add_stats_metadata(report)
            self.telemetry_post(report)

    def add_event_and_print(self, **args):
        if 'message' not in args or 'name' not in args:
            raise("Invalid event. Must have 'name' and 'message' args")
        # args['debug_'] = True
        print("[T2RvR] {}".format(args['message']))
        self.add_event(**args)

    def wait_for_cx_to_start(self, cxs=None, timeout=300):
        for x in cxs:
            give_up_ts = time.time() + timeout
            while True:
                cx_state = self.json_get("/cx/{}".format(x), debug_=self.debug)
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
    def create_station(self, radio='wiphy0'):
        self.station_profiles[radio].use_security(self.security, self.ssid, self.paswd)

        # Force 11n mode for 2.4 GHz radio tests to avoid non-standard 11ac usage
        # Also 20MHz (0 == 20, 1 == 40, 2 == 80, 3 == 160, 4 == 80+80)
        if radio == 'wiphy0':
            self.station_profiles[radio].mode = 5
            self.station_profiles[radio].wifi_txo_data['txo_bw'] = 2
        print(f'Calling create on station_profiles[{radio}] with sta_names: {self.sta_list[radio]}')
        self.station_profiles[radio].create(radio=radio, sta_names_=self.sta_list[radio])
        print(f'Called create on station_profiles[{radio}] with sta_names: {self.sta_list[radio]}')
        print('sta_names_: {}, station_profile.station_names: {}'.format(self.sta_list[radio], self.station_profiles[radio].station_names))

        # self.reset_cxes()  # Assumes that any unwanted cxes have been cleaned up already using self.stop() or something else
        for cx_profile in self.endpoints.values():
            cx_profile.create(endp_type="lf_tcp", side_a=self.station_profiles[radio].station_names, side_b=self.upstream, sleep_time=1)
            # self.add_running_cxes(cx_profile.get_cx_names())

    def precleanup(self):
        self.attenuator.base_profile(minimal=True)
        # self.cleanup_running_cxes()
        for cx_profile in self.endpoints.values():
                cx_profile.cleanup()
        for radio in self.radios:
            for sta in self.sta_list[radio]:
                self.local_realm.rm_port(sta, check_exists=True)
            LFUtils.wait_until_ports_disappear(base_url=self.lfclient_url,
                                            port_list=self.sta_list[radio],
                                            debug=self.debug)
        time.sleep(1)
        self.create_station_profiles()
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

        # Initiate the upstream port
        try:
            data = LFUtils.port_dhcp_up_request(self.resource, self.upstream)
            print("set_port request data: {}".format(data))
            self.json_post("/cli-json/set_port", data)
        except:
            print("LFUtils.port_dhcp_up_request didn't complete ")
            print("or the json_post failed either way {} did not set up dhcp so test may not pass data ".format(self.side_b))

        if self.attenuator is None:
            exit('Error: No attenuator detected')

    def create_cx(self, traffic_direction='downstream'):
        requested_tput = 10000000000  # 10 Gbit/s
        cx_profile = self.local_realm.new_l3_cx_profile()
        cx_profile.host = self.host
        cx_profile.port = self.port
        cx_profile.name_prefix = self.name_prefix + '_' + traffic_direction.upper() + '_'
        if traffic_direction == 'downstream':
            cx_profile.side_b_min_bps = requested_tput
            cx_profile.side_b_max_bps = cx_profile.side_b_max_bps
            cx_profile.side_a_min_bps = 0
            cx_profile.side_a_max_bps = 0
        elif traffic_direction == 'upstream':
            cx_profile.side_a_min_bps = requested_tput
            cx_profile.side_a_max_bps = cx_profile.side_a_min_bps
            cx_profile.side_b_min_bps = 0
            cx_profile.side_b_max_bps = 0
        return cx_profile

    def start_station_traffic(self, radio="wiphy0", timeout_sec=30, cx_direction='downstream'):
        self.station_profiles[radio].admin_up()
        cx_profile = self.endpoints[cx_direction]
        temp_stas = self.station_profiles[radio].station_names.copy()
        # temp_stas = sta_list
        print('station_profile.station_names:', temp_stas)
        if self.local_realm.wait_for_ip(temp_stas, timeout_sec=timeout_sec):
            self._pass("All stations got IPs")
        else:
            self._fail("Stations failed to get IPs")
            # This will ultimately happen when attenuation is high enough
            raise(ConnectionError("Stations failed to get IPs"))
        cx_profile.start_cx()
        print('Waiting for these cross endpoints to appear:', cx_profile.get_cx_names())
        self.local_realm.wait_until_cxs_appear(cx_profile.get_cx_names())
        self.wait_for_cx_to_start(cx_profile.get_cx_names(), timeout=timeout_sec)
        time.sleep(1)
 
    def start(self):
        self.add_event_and_print(name='T2RvR_Status', message='<<<<<<<<<<< Starting T2RvR test for {} iterations on DUTs: {} on radios: {} >>>>>>>>>>>>'.
            format(self.num_iterations, self.duts, self.radios))
        for i in range(self.num_iterations):
            iteration = i + 1
            self.attenuator.iteration = iteration
            skip_dut = False
            for dut in self.duts:
                self.dut_ctl.set_dut(dut)
                if skip_dut:
                    self.dut_ctl.power_off()
                    continue
                self.dut_ctl.power_on()
                dut_total_counter, dut_fail_counter, dut_total_fails = 0, 0, 0
                for radio in self.radios:
                    self.configure_radio(radio)
                    self.precleanup()
                    self.add_event_and_print(name='T2RvR_Status', message='Starting T2RvR test for DUT={} and Radio={}'.format(dut, radio))
                    self.create_station(radio)
                    if skip_dut:
                        break

                    for step, ddb in enumerate(range(0, 50, self.attenuator.ddb_step_size)):
                        if skip_dut:
                            break
                        if step != 0:
                            self.attenuator.increase_attenuation(ddb)
                        
                        self.add_event_and_print(name='T2RvR_Status', message='[Iteration={}|DUT={}|atten={}] Starting traffic on stations for {} seconds..'.
                            format(iteration, dut, ddb, self.step_length_sec))
                        
                        cx_fail = 0
                        for cx_direction in self.endpoints.keys():
                            try:
                                if dut_total_counter > 5 and dut_total_fails/dut_total_counter > self.total_fail_threshold:
                                    self.add_event_and_print(name='T2RvR_DUTError', message='[Iteration={}|DUT={}|atten={}] Skipping DUT due to too many failures in total (>{}%)'.
                                        format(iteration, dut, ddb, self.total_fail_threshold*100))
                                    skip_dut = True
                                    break
                                else:
                                    # Increase timeout for first step
                                    if step == 0:
                                        self.start_station_traffic(radio=radio, timeout_sec=360, cx_direction=cx_direction)
                                    else:
                                        self.start_station_traffic(radio=radio, cx_direction=cx_direction)
                            except ConnectionError:
                                self.add_event_and_print(name='T2RvR_DUTError', message="Stations failed to get IPs")
                                dut_fail_counter += 1
                                dut_total_fails += 1
                                cx_fail += 1

                                # Give up this DUT if we've failed too many times in a row
                                # If both directions are tested, only fail if at least both directions failed
                                # For the very first step, retries are ignored
                                if (cx_fail == 2 and len(self.endpoints.keys()) == 2) or (cx_fail == 1 and len(self.endpoints.keys()) == 1):
                                    if step == 0:
                                        self.add_event_and_print(name='T2RvR_DUTError', message='[Iteration={}|DUT={}|atten={}] Skipping DUT due to failure on first step'.
                                            format(iteration, dut, ddb))
                                        skip_dut = True
                                        break
                                    if dut_fail_counter > self.max_attempts_on_fail:
                                        self.add_event_and_print(name='T2RvR_DUTError', message='[Iteration={}|DUT={}|atten={}] Skipping DUT due to too many failures in a row ({})'.
                                            format(iteration, dut, ddb, self.max_attempts_on_fail))
                                        skip_dut = True
                                        break
                            else:  # Reset non-total fail counter if we succeed
                                dut_fail_counter = 0
                                step_end_ts = time.time() + self.step_length_sec + 5
                                while True:
                                    print('Collecting stats...')
                                    self.collect_stats()
                                    time.sleep(0.5)
                                    if time.time() > step_end_ts:
                                        break
                            finally:
                                dut_total_counter += 1
                                self.stop(radio=radio, cx_direction=cx_direction)

                self.dut_ctl.power_off()

    def stop(self, radio="wiphy0", cx_direction='downstream'):
        # Bring stations down
        print('Bringing stations down..')
        if cx_direction == 'all':
            for cx_profile in self.cx_profiles:
                cx_profile.quiesce_cx()
                cx_profile.stop_cx()
        else:
            self.endpoints[cx_direction].quiesce_cx()
            self.endpoints[cx_direction].stop_cx()
        time.sleep(1)
        self.station_profiles[radio].admin_down()


def main():
    parser = argparse.ArgumentParser(description="Tele2 RvR Script")
    parser.add_argument('-hst', '--host', type=str, help='host name')
    parser.add_argument('-prt', '--port', type=int, help='host port')
    parser.add_argument('-s', '--ssid', type=str, help='ssid for client')
    parser.add_argument('-pwd', '--passwd', type=str, help='password to connect to ssid')
    parser.add_argument('-sec', '--security', type=str, help='security')
    parser.add_argument('-td', '--traffic_direction', type=str, help='traffic direction to test, must one of: "downstream", "upstream" or "both"')
    parser.add_argument('-d', '--duts', help='comma-delimited list input of DUTs to test, use friendly names (e.g: L2, ASUS-AX58 etc)', type=str)
    parser.add_argument('-r', '--radios', help='comma-delimited list input of radios to test on each DUT (wiphy0 and/or wiphy1)', type=str)
    args = parser.parse_args()
    rvr = Tele2RateVersusRange(lfclient_host= args.host, lfclient_port=args.port, ssid=args.ssid, paswd=args.passwd,
        security=args.security, radios=args.radios, duts=args.duts, traffic_direction=args.traffic_direction)
    rvr.precleanup()
    rvr.build()
    rvr.start()
    return rvr


if __name__ == '__main__':
    rvr = main()

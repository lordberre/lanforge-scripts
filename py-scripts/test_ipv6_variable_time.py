#!/usr/bin/env python3

import os
import sys

if sys.version_info[0] != 3:
    print("This script requires Python 3")
    exit(1)

if 'py-json' not in sys.path:
    sys.path.append(os.path.join(os.path.abspath('..'), 'py-json'))

import argparse
from LANforge.lfcli_base import LFCliBase
from LANforge import LFUtils
import realm
import time
import math
import pprint
import datetime


class IPV6VariableTime(LFCliBase):
    def __init__(self,
                 _host="localhost",
                 _port=8080,
                 _ssid=None,
                 _security=None,
                 _password=None,
                 _sta_list=None,
                 _name_prefix="sta",
                 _upstream="1.1.eth1",
                 _radio="wiphy0",
                 _side_a_min_rate=256000,
                 _side_a_max_rate=0, # same
                 _side_b_min_rate=256000,
                 _side_b_max_rate=0, # same
                 _number_template="00000",
                 _test_duration="5m",
                 _use_ht160=False,
                 _cx_type=None,
                 _first_sta=None,
                 _debug_on=False,
                 _exit_on_error=False,
                 _exit_on_fail=False):
        super().__init__(_host,
                         _port,
                         _local_realm=realm.Realm(lfclient_host=_host,
                                                  lfclient_port=_port,
                                                  debug_=_debug_on,
                                                  _exit_on_error=_exit_on_error,
                                                  _exit_on_fail=_exit_on_fail),
                         _debug=_debug_on,
                         _halt_on_error=_exit_on_error,
                         _exit_on_fail=_exit_on_fail)
        self.upstream = _upstream
        self.ssid = _ssid
        self.sta_list = _sta_list
        self.security = _security
        self.password = _password
        self.radio = _radio
        self.number_template = _number_template
        self.debug = _debug_on
        self.name_prefix = _name_prefix
        self.test_duration = _test_duration
        self.cx_type = _cx_type

        self.station_profile = self.local_realm.new_station_profile()
        self.cx_profile = self.local_realm.new_l3_cx_profile()

        self.station_profile.lfclient_url = self.lfclient_url
        self.station_profile.ssid = self.ssid
        self.station_profile.ssid_pass = self.password
        self.station_profile.security = self.security
        self.station_profile.number_template_ = self.number_template
        self.station_profile.debug = self.debug
        self.station_profile.use_ht160 = _use_ht160
        if self.station_profile.use_ht160:
            self.station_profile.mode = 9

        self.cx_profile.host = _host
        self.cx_profile.port = _port
        self.cx_profile.name_prefix = _name_prefix
        self.cx_profile.first_sta = _first_sta
        self.cx_profile.side_a_min_bps = _side_a_min_rate
        self.cx_profile.side_a_max_bps = _side_a_max_rate
        self.cx_profile.side_b_min_bps = _side_b_min_rate
        self.cx_profile.side_b_max_bps = _side_b_max_rate


    def __get_rx_values(self):
        cx_list = self.json_get("endp?fields=name,rx+bytes", debug_=self.debug)
        # print(self.cx_profile.created_cx.values())
        # print("==============\n", cx_list, "\n==============")
        cx_rx_map = {}
        for cx_name in cx_list['endpoint']:
            if cx_name != 'uri' and cx_name != 'handler':
                for item, value in cx_name.items():
                    for value_name, value_rx in value.items():
                        if value_name == 'rx bytes' and item in self.cx_profile.created_cx.values():
                            cx_rx_map[item] = value_rx
        return cx_rx_map

    def __compare_vals(self, old_list, new_list):
        passes = 0
        expected_passes = 0
        if len(old_list) == len(new_list):
            for item, value in old_list.items():
                expected_passes += 1
                if new_list[item] > old_list[item]:
                    passes += 1
                # print(item, new_list[item], old_list[item], passes, expected_passes)

            if passes == expected_passes:
                return True
            else:
                return False
        else:
            return False

    def start(self, print_pass=False, print_fail=False):
        self.station_profile.admin_up()
        temp_stas = self.station_profile.station_names.copy()
        # temp_stas.append(self.upstream)
        if self.local_realm.wait_for_ip(temp_stas, ipv4=False, ipv6=True):
            self._pass("All stations got IPs", print_pass)
        else:
            self._fail("Stations failed to get IPs", print_fail)
            exit(1)
        cur_time = datetime.datetime.now()
        old_cx_rx_values = self.__get_rx_values()
        end_time = self.local_realm.parse_time(self.test_duration) + cur_time
        self.cx_profile.start_cx()
        passes = 0
        expected_passes = 0
        while cur_time < end_time:
            interval_time = cur_time + datetime.timedelta(minutes=1)
            while cur_time < interval_time:
                cur_time = datetime.datetime.now()
                time.sleep(1)

            new_cx_rx_values = self.__get_rx_values()
            # print(old_cx_rx_values, new_cx_rx_values)
            # print("\n-----------------------------------")
            # print(cur_time, end_time, cur_time + datetime.timedelta(minutes=1))
            # print("-----------------------------------\n")
            expected_passes += 1
            if self.__compare_vals(old_cx_rx_values, new_cx_rx_values):
                passes += 1
            else:
                self._fail("FAIL: Not all stations increased traffic", print_fail)
                break
            old_cx_rx_values = new_cx_rx_values
            cur_time = datetime.datetime.now()

        if passes == expected_passes:
            self._pass("PASS: All tests passed", print_pass)

    def stop(self):
        self.cx_profile.stop_cx()
        self.station_profile.admin_down()

    def pre_cleanup(self):
        print("pre_cleanup")
        zta_list = self.sta_list
        if isinstance(self.sta_list, dict):
            zta_list=[]
            for radio,stations in self.sta_list.items():
                zta_list = zta_list + stations

        # self.cx_profile.cleanup_prefix()
        print("sta_list")
        pprint.pprint(self.sta_list)
        for sta in zta_list:
            print("station %s" % sta)
            if isinstance(sta, list) or isinstance(sta, dict):
                pprint.pprint(sta)
                raise ValueError("Misconfigured list: %s" % zta_list )
            self.local_realm.rm_port(sta, check_exists=True, debug_=self.debug)

        if self.debug:
            print("zta_list....")
            pprint.pprint(zta_list)
            print("wait until disappear")
        LFUtils.wait_until_ports_disappear(base_url=self.lfclient_url,
                                           port_list=zta_list,
                                           debug=self.debug)

    def cleanup(self):
        self.cx_profile.cleanup()
        self.station_profile.cleanup()
        LFUtils.wait_until_ports_disappear(base_url=self.lfclient_url,
                                           port_list=self.station_profile.station_names,
                                           debug=self.debug)

    def build(self):
        self.station_profile.use_security(self.security, self.ssid, self.password)
        self.station_profile.set_number_template(self.number_template)
        print("Creating stations")
        self.station_profile.set_command_flag("add_sta", "create_admin_down", 1)
        self.station_profile.set_command_param("set_port", "report_timer", 1500)
        self.station_profile.set_command_flag("set_port", "rpt_timer", 1)
        # todo use first_sta= argument
        radio_list = [ self.radio ]
        if self.radio.find(","):
            radio_list = self.radio.split(",")
        for radio in radio_list:
            self.station_profile.create(radio=radio,
                                        sta_names_=self.sta_list[radio],
                                        debug=self.debug)
        self.cx_profile.create(endp_type=self.cx_type, side_a=self.station_profile.station_names, side_b=self.upstream,
                               sleep_time=0)
        self._pass("PASS: Station build finished")


def main():
    parser = LFCliBase.create_basic_argparse(
        prog='test_ipv6_variable_time.py',
        # formatter_class=argparse.RawDescriptionHelpFormatter,
        formatter_class=argparse.RawTextHelpFormatter,
        epilog='''\
Create stations to test IPV6 connection and traffic on VAPs of varying security types (WEP, WPA, WPA2, WPA3, Open)
''',
        description='''\
test_ipv6_variable_time.py:
--------------------
Generic command example:
./test_ipv6_connection.py --upstream_port eth1 \\
    --radio wiphy0 \\
    --num_stations 3 \\
    --security {open|wep|wpa|wpa2|wpa3} \\
    --ssid netgear \\
    --passwd admin123 \\
    --upstream 10.40.0.1 \\
    --test_duration 2m \\
    --monitor_interval 1s \\
    --a_min 256000 \\
    --b_min 256000 \\
    --debug
''')
    required_args=None
    for group in parser._action_groups:
        if group.title == "required arguments":
            required_args=group
            break;
    if required_args is not None:
        required_args.add_argument('--a_min', help='minimum bps rate for side_a', default=256000)
        required_args.add_argument('--b_min', help='minimum bps rate for side_b', default=256000)
        required_args.add_argument('--cx_type', help='tcp6 or udp6')
        required_args.add_argument('--test_duration', help='--test_duration sets the duration of the test', default="5m")

    optional_args=None
    for group in parser._action_groups:
        if group.title == "optional arguments":
            optional_args=group
            break;
    if optional_args is not None:
        optional_args.add_argument('--mode',    help='Used to force mode of stations')
        optional_args.add_argument('--ap',      help='Used to force a connection to a particular AP')
        optional_args.add_argument("--a_max",   help="Maximum side_a bps speed", default=0)
        optional_args.add_argument("--b_max",   help="Maximum side_b bps speed", default=0)
        optional_args.add_argument("--first_sta", help="begins the station name series with this number")

    args = parser.parse_args()

    CX_TYPES=("tcp6", "udp6", "lf_tcp6", "lf_udp6")

    if (args.cx_type is None) or (args.cx_type not in CX_TYPES):
        print("cx_type needs to be lf_tcp6 or lf_udp6, bye")
        exit(1)
    if args.cx_type == "tcp6":
        args.cx_type = "lf_tcp6"
    if args.cx_type == "udp6":
        args.cx_type = "lf_udp6"


    radio_list = [args.radio]
    if args.radio.find(",") > 1:
        radio_list = args.radio.split(",")

    num_sta = len(radio_list)
    if args.num_stations is not None:
        if (type(args.num_stations) == int) or isinstance(args.num_stations, int):
            num_sta = math.floor(args.num_stations / len(radio_list))
        else:
            if (args.num_stations.endswith("/r")):
                hunk = args.num_stations[0, args.num_stations.find("/")]
                num_sta = int(hunk)
            else:
                try:
                    num_sta = int(args.num_stations)
                    num_sta = math.floor(num_sta / len(radio_list))
                except:
                    raise ValueError("Unable to convert num_stations %s into %s sta per radio" % (args.num_stations, len(radio_list)))

    start_id=0
    station_list = {}
    for radio in radio_list:
        print("start_id %s end_id %s radio %s" % (start_id, (num_sta-1), radio))
        station_list[radio] = LFUtils.port_name_series(prefix="sta",
                                                       start_id=start_id,
                                                       end_id=start_id + num_sta - 1,
                                                       padding_number=10000,
                                                       radio=radio)
        start_id += 1000

    ip_var_test = IPV6VariableTime(_host=args.mgr,
                                   _port=args.mgr_port,
                                   _number_template="00",
                                   _sta_list=station_list,
                                   _name_prefix="VT",
                                   _upstream=args.upstream_port,
                                   _ssid=args.ssid,
                                   _password=args.passwd,
                                   _radio=args.radio,
                                   _security=args.security,
                                   _test_duration=args.test_duration,
                                   _use_ht160=False,
                                   _side_a_min_rate=args.a_min,
                                   _side_b_min_rate=args.b_min,
                                   _side_a_max_rate=args.a_max,
                                   _side_b_max_rate=args.b_max,
                                   _cx_type=args.cx_type,
                                   _first_sta=args.first_sta,
                                   _debug_on=args.debug)

    ip_var_test.pre_cleanup()
    ip_var_test.build()
    if not ip_var_test.passes():
        print(ip_var_test.get_fail_message())
        exit(1)
    ip_var_test.start(False, False)
    ip_var_test.stop()
    if not ip_var_test.passes():
        print(ip_var_test.get_fail_message())
        exit(1)
    time.sleep(30)
    ip_var_test.cleanup()
    if ip_var_test.passes():
        print("Full test passed, all connections increased rx bytes")


if __name__ == "__main__":
    main()

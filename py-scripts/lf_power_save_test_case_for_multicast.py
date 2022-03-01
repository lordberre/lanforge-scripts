#!/usr/bin/env python3
import sys
import os
import importlib
import time
import datetime
import argparse
from pprint import pprint

if sys.version_info[0] != 3:
    print("This script requires Python 3")
    exit(1)

sys.path.append(os.path.join(os.path.abspath(__file__ + "../../../")))

LFUtils = importlib.import_module("py-json.LANforge.LFUtils")
realm = importlib.import_module("py-json.realm")
Realm = realm.Realm
l3_cxprofile = importlib.import_module("py-json.l3_cxprofile")
multicast_profile = importlib.import_module("py-json.multicast_profile")
station_profile = importlib.import_module("py-json.station_profile")
wifi_monitor = importlib.import_module("py-json.wifi_monitor_profile")
cv_test_reports = importlib.import_module("py-json.cv_test_reports")
lf_rpt = cv_test_reports.lanforge_reports

import pyshark as ps


class MulticastandUnicastPowersaveTraffic(Realm):

    def __init__(self, host, port, ssid, security, password, station_list, min_rate_multi_cast=56,
                 max_rate_multi_cast=56,
                 side_a_unicast_min_rate=56, side_b_unicast_min_rate=56, side_a_unicast_max_rate=0,
                 side_b_unicast_max_rate=0, pdu_size=1000,
                 upstream="1.1.eth1", interface_to_capture=None,
                 prefix="00000", test_duration="5m",report_path="",
                 station_radio="wiphy0", monitor_radio="wiphy0", remote_host_cap_ip=None,
                 output_file_for_cap="",
                 remote_host_cap_interface=None,
                 _debug_on=False, _exit_on_error=False, _exit_on_fail=False):
        super().__init__(lfclient_host=host, lfclient_port=port, debug_=_debug_on)
        self.host = host
        self.port = port
        self.ssid = ssid
        self.security = security
        self.password = password
        self.sta_list = station_list
        self.prefix = prefix
        self.station_radio = station_radio
        self.monitor_radio = monitor_radio
        self.debug = _debug_on
        self.upstream = upstream
        self.min_rate = min_rate_multi_cast
        self.max_rate = max_rate_multi_cast
        self.output_file = output_file_for_cap
        self.enable_multicast_testing = False
        self.enable_unicast_testing = False
        self.filter = ""
        self.report_dir = report_path
        self.captured_file_name = ""
        if interface_to_capture is not None:
            self.live_cap_timeout = interface_to_capture
        else:
            self.live_cap_timeout = station_radio
        if remote_host_cap_ip and remote_host_cap_interface is not None:
            self.remote_cap_host = remote_host_cap_ip
            self.remote_cap_interface = remote_host_cap_interface

        self.test_duration = test_duration
        # upload
        self.cx_prof_upload = l3_cxprofile.L3CXProfile(self.host, self.port, local_realm=self,
                                                       side_a_min_bps=side_a_unicast_min_rate, side_b_min_bps=0,
                                                       side_a_max_bps=side_a_unicast_max_rate, side_b_max_bps=0,
                                                       side_a_min_pdu=pdu_size, side_a_max_pdu=pdu_size,
                                                       side_b_min_pdu=0, side_b_max_pdu=0, debug_=self.debug)

        # download
        self.cx_prof_download = l3_cxprofile.L3CXProfile(self.host, self.port, local_realm=self,
                                                         side_a_min_bps=0, side_b_min_bps=side_b_unicast_min_rate,
                                                         side_a_max_bps=0, side_b_max_bps=side_b_unicast_max_rate,
                                                         side_a_min_pdu=0, side_a_max_pdu=0,
                                                         side_b_min_pdu=pdu_size, side_b_max_pdu=pdu_size,
                                                         debug_=self.debug)
        self.multi_cast_profile = multicast_profile.MULTICASTProfile(self.host, self.port, local_realm=self)

        self.station_profile = station_profile.StationProfile(self.lfclient_url, local_realm=self, ssid=self.ssid,
                                                              ssid_pass=self.password,
                                                              security=self.security, number_template_=self.prefix,
                                                              mode=5,
                                                              up=True,
                                                              dhcp=True,
                                                              debug_=self.debug)
        self.new_monitor = wifi_monitor.WifiMonitor(self.lfclient_url, local_realm=self, debug_=self.debug)

    def build_station_profile(self):
        self.station_profile.use_security(self.security, ssid=self.ssid, passwd=self.password)
        self.station_profile.set_number_template(self.prefix)
        self.station_profile.set_command_flag("add_sta", "create_admin_down", 1)
        self.station_profile.set_command_param("set_port", "report_timer", 1500)
        self.station_profile.set_command_flag("set_port", "rpt_timer", 1)
        self.station_profile.set_command_flag("add_sta", "power_save_enable", 1)
        self.station_profile.create(radio=self.station_radio, sta_names_=self.sta_list)
        self._pass("PASS: Station builds finished")

    def build_monitor(self):
        self.new_monitor.create(resource_=1, channel=6, radio_=self.monitor_radio, name_="moni0")

    def build_multi_cast_profile(self):
        self.multi_cast_profile.create_mc_tx("mc_udp", self.upstream, min_rate=self.min_rate, max_rate=self.max_rate)
        self.multi_cast_profile.create_mc_rx("mc_udp", self.sta_list)

    def build_layer3_upload(self):
        self.cx_prof_upload.name_prefix = "UDP_up"
        print("Creating upload cx profile ")
        self.cx_prof_upload.create(endp_type="lf_tcp", side_a=self.station_profile.station_names, side_b=self.upstream,
                                   sleep_time=.05)

    def build_layer3_download(self):
        self.cx_prof_download.name_prefix = "TCP_down"
        print("Creating download cx profile")
        self.cx_prof_download.create(endp_type="lf_tcp", side_a=self.station_profile.station_names,
                                     side_b=self.upstream,
                                     sleep_time=.05)

        # channel = self.json_get("/port/1/%s/%s/"%(1,"wiphy0"))
        # rint("The channel name is...")

        # station_channel = self.json_get("/port/1/%s/%s")
        # pprint.pprint(station_channel)

    def get_captured_file_and_location(self):
        return self.captured_file_name, self.report_dir, self.filter

    def start(self):
        # start one test, measure
        # start second test, measure
        cur_time = datetime.datetime.now()
        end_time = self.parse_time(self.test_duration) + cur_time
        # admin up on new monitor
        self.new_monitor.admin_up()
        now = datetime.datetime.now()
        date_time = now.strftime("%Y-%m-%d-%H%M%S")
        curr_mon_name = self.new_monitor.monitor_name
        # ("date and time: ",date_time)
        self.captured_file_name = curr_mon_name + "-" + date_time + ".pcap"
        self.new_monitor.start_sniff(capname=self.output_file + "/" + curr_mon_name + "-" + date_time + ".pcap",
                                     duration_sec=100)
        # admin up on station

        print("station profile got admin up")
        self.station_profile.admin_up()
        # self.new_monitor.set_flag()
        # print(self.station_profile.station_names)
        if self.wait_for_ip(self.station_profile.station_names):
            self._pass("All stations got IPs")
        else:
            self._fail("Stations failed to get IPs")
            exit(1)

        if self.enable_multicast_testing:
            print("started multicast traffic")
            self.multi_cast_profile.start_mc()
        elif self.enable_unicast_testing:
            print("started unicast traffic")
            self.start_layer3()

        # print station + MAC, AP
        temp = []
        for station in self.station_profile.station_names:
            temp.append(self.name_to_eid(station)[2])
        port_info = self.json_get("port/1/1/%s?fields=alias,ap,mac" % ','.join(temp))
        print("port_info.........",port_info)
        if port_info is not None:
            if 'interfaces' in port_info:
                for item in port_info['interfaces']:
                    for k, v in item.items():
                        print("sta_name %s" % v['alias'])
                        print("mac      %s" % v['mac'])
                        print("ap       %s\n" % v['ap'])
            elif 'interface' in port_info:
                print("sta_name %s" % port_info['interface']['alias'])
                print("mac      %s" % port_info['interface']['mac'])
                print("ap       %s\n" % port_info['interface']['ap'])
                self.filter = "wlan.addr==" + port_info['interface']['mac'] + " || " + "wlan.addr==" + \
                              port_info['interface']['ap']
                print("self.filter=", self.filter)
            else:
                print('interfaces and interface not in port_mgr_response')
                exit(1)

        while cur_time < end_time:
            # DOUBLE CHECK
            interval_time = cur_time + datetime.timedelta(minutes=1)
            while cur_time < interval_time:
                cur_time = datetime.datetime.now()
                time.sleep(1)

        # pulls report from lanforge to specified location in self.report_dir
        lf_rpt.pull_reports(hostname="192.168.200.229", port=22, username="lanforge", password="lanforge",
                            report_location=self.output_file + "/" + curr_mon_name + "-" + date_time + ".pcap",
                            report_dir=self.report_dir)

    '''
    def capture_live_pcap(self):
        try:
            self.live_pcap = ps.LiveCapture(interface=self.live_pcap_interface, output_file=self.output_file)
            self.live_pcap.sniff(timeout=300)
        except ValueError:
            raise "Capture Error"
        return self.live_pcap

    def capture_remote_pcap(self):
        try:
            self.remote_pcap = ps.RemoteCapture(remote_host=self.remote_cap_host,
                                                remote_interface=self.remote_cap_interface)
        except ValueError:
            raise "Host error"
        return self.remote_pcap
    '''

    def verify_dtim_multicast_pcap(self, pcap_file, apply_filter=None):
        self.pcap_file = pcap_file
        if apply_filter is not None:
            self.apply_filter = apply_filter
        try:
            self.pcap = ps.FileCapture(input_file=self.pcap_file, display_filter=self.apply_filter)
        except Exception as error:
            raise error
        check_mcast_val = False
        for pkt in self.pcap:  # traversing through all packets one by one
            if 'wlan.mgt' in pkt:
                dtim_multicast_bit = pkt['wlan.mgt'].get_field_value('wlan_tim_bmapctl_multicast',
                                                                     raw=True)  # reading Multicast bit to verify whether it is set or not
                frame_num = str(pkt.number)
                print(f"PACKET NUMBER : {frame_num}, dtim_multicast_bit : {dtim_multicast_bit}")
                if dtim_multicast_bit == "1":  # verifying whether multicast bit is set i.e True
                    dtim_count = pkt['wlan.mgt'].get_field_value('wlan_tim_dtim_count',
                                                                 raw=True)  # here i'm checking the dtim count of the frame to which MUlticast bit which is set
                    print(f"PACKET NUMBER : {frame_num}, dtim_count : {dtim_count}")
                    if dtim_count == "00":
                        print("dtim_multicast_bit_frame_num :", frame_num)
                        check_mcast_val = True
                        continue  # if dtim count is zero im going for next packet to verify whether multicast frame is transmitted or not
                else:
                    continue

            elif check_mcast_val:
                mcast_frame_num = str(pkt.number)
                frame_type = pkt[
                    'wlan'].DATA_LAYER  # here i'm verifying the type of frame to identify multicast packet right after beacon.
                print(f"Multi cast frame number right after beacon : {mcast_frame_num}")
                time_delta_from_prev_frame_in_microsec = str(pkt.frame_info.time_delta)
                time_delta_from_prev_frame_in_millisec = round(float(time_delta_from_prev_frame_in_microsec) * 1000)
                print("time_delta_from_prev_frame_in_microsec :", time_delta_from_prev_frame_in_microsec)
                print("time_delta_from_prev_frame_in_millisec :",
                      str(time_delta_from_prev_frame_in_millisec) + "" + 'ms')
                if frame_type == 'data':  # if it is data packet it checks for power mgt bit and verify multicast frames are transmitted
                    pwr_mgt_bit = pkt['wlan'].get_field_value('fc_pwrmgt', raw=True)
                    receiver_addr_mcast = str(pkt.wlan.ra)
                    threshold_time_for_mcast_to_transmit = 5

                    if time_delta_from_prev_frame_in_millisec < threshold_time_for_mcast_to_transmit:
                        print(
                            f"PASSED:Frame transmitted in less than {threshold_time_for_mcast_to_transmit} milli seconds, PACKET NUMBER:{mcast_frame_num}")
                    else:
                        print(
                            f"FAILED:Packet transmitted in more than {threshold_time_for_mcast_to_transmit} milli seconds, PACKET NUMBER:{mcast_frame_num}")

                    if receiver_addr_mcast.split(':')[0][-1] == '1':  # check to know multicast or unicast packet
                        print(
                            f"PASSED:Multicast bit set in receiver address,receiver_addr_mcast : {receiver_addr_mcast}, PACKET NUMBER:{mcast_frame_num}")

                    else:
                        print(
                            f"FAILED:Multicast bit is not set in receiver address,receiver_addr_mcast : {receiver_addr_mcast},PACKET NUMBER:{mcast_frame_num}")

                    if pwr_mgt_bit == "0":
                        print(f"PASSED:Multicast Traffic Transmitted, Packet Number:{mcast_frame_num}")
                        break
            else:
                receiver_addr_mcast = str(pkt.wlan.ra)
                rcv_addr = "ff:ff:ff:ff:ff:ff"
                if receiver_addr_mcast.split(':')[0][-1] == '1':  # receiver MAC address multicast bit check
                    print(
                        f"PACKET NUMBER : {str(pkt.number)}, FAILED:unexpected multicast data packet without previous beacon")
                if receiver_addr_mcast == rcv_addr:
                    print(
                        f"PACKET NUMBER : {str(pkt.number)}, FAILED:Unexpected broadcast packet without multicast bit set in previous beacon")
                continue
        return self.pcap

    def start_station_profile(self):
        self.station_profile.admin_up()

    def stop_station_profile(self):
        self.station_profile.admin_down()

    def stop_monitor(self):
        # switch off new monitor
        self.new_monitor.admin_down()

    def start_multicast(self):
        self.multi_cast_profile.start_mc()

    def start_layer3(self):
        # self.cx_prof_upload.start_cx()
        self.cx_prof_download.start_cx()

    def stop_multi_cast(self):
        self.multi_cast_profile.stop_mc()

    def stop_layer3(self):
        # self.cx_prof_upload.stop_cx()
        self.cx_prof_download.stop_cx()

    def cleanup_station_profile(self):
        self.station_profile.cleanup(desired_stations=self.sta_list)

    def cleanup_layer3(self):
        self.cx_prof_download.cleanup()
        self.cx_prof_upload.cleanup()

    def cleanup_monitor(self):
        self.new_monitor.cleanup()

    def cleanup_multicast(self):
        self.multi_cast_profile.cleanup()

    def multicast_testing(self):
        self.enable_multicast_testing = True
        self.build_station_profile()  # function to build station profile
        self.build_monitor()  # function to create monitor
        self.build_multi_cast_profile()  # function to build multi_cast_profile

        self.start()  # function to start sniff by admin up station and /
        # starting the multicast traffic for some duration

        self.new_monitor.admin_down()
        self.stop_multi_cast()
        self.station_profile.admin_down()

        self.new_monitor.cleanup()
        self.cleanup_multicast()
        self.station_profile.cleanup(desired_stations=self.sta_list)

    def unicast_testing(self):
        self.enable_unicast_testing = True
        self.build_station_profile()  # function to build station profile
        self.build_monitor()  # function to create monitor
        # self.build_layer3_upload()
        self.build_layer3_download()  # function to build unicast download traffic

        self.start()  # function to start sniff by admin up station followed by /
        # starting the unicast traffic with desired pdu size for some duration

        self.new_monitor.admin_down()
        # self.cx_prof_upload.stop_cx()
        self.cx_prof_download.stop_cx()
        self.station_profile.admin_down()

        self.new_monitor.cleanup()
        self.cx_prof_download.cleanup()
        # self.cx_prof_upload.cleanup()
        self.station_profile.cleanup(desired_stations=self.sta_list)


def main():
    # Realm.create_basic_argparse defined in lanforge-scripts/py-json/LANforge/lfcli_base.py
    parser = Realm.create_basic_argparse(
        prog='lf_power_save_test_cases_cisco.py',
        formatter_class=argparse.RawTextHelpFormatter,
        epilog='''\
        lf_power_save_test_cases_cisco.py

            ''',
        description='''\
Example of creating traffic on an l3 connection
        ''')

    parser.add_argument('--monitor_radio', help="--monitor_radio radio to be used in monitor creation",
                        default="wiphy1")
    parser.add_argument('--report_path', help="desired path to save your pcap file fetched from lanforge through ssh",
                        default="/home/mahesh/Desktop/lanforge-scripts/lanforge-scripts/py-scripts")
    args = parser.parse_args()

    lfjson_host = args.mgr
    lfjson_port = 8080
    station_list = LFUtils.portNameSeries(prefix_="sta", start_id_=0, end_id_=0, padding_number_=10000)
    ip_powersave_test = MulticastandUnicastPowersaveTraffic(lfjson_host, lfjson_port, ssid=args.ssid,
                                                            security=args.security,
                                                            password=args.passwd, station_list=station_list,
                                                            min_rate_multi_cast=9000,
                                                            max_rate_multi_cast=128000, side_a_unicast_min_rate=9000,
                                                            side_b_unicast_min_rate=9000,
                                                            side_a_unicast_max_rate=128000,
                                                            side_b_unicast_max_rate=128000, pdu_size=1400,
                                                            station_radio=args.radio,
                                                            upstream=args.upstream_port,
                                                            monitor_radio=args.monitor_radio, test_duration="1m",
                                                            interface_to_capture=None,
                                                            _debug_on=args.debug, remote_host_cap_ip=None,
                                                            remote_host_cap_interface=None,
                                                            report_path=args.report_path,
                                                            output_file_for_cap="/home/lanforge/html-reports",
                                                            _exit_on_error=True, _exit_on_fail=True)

    ip_powersave_test.multicast_testing()  # function to run multicast test
    # ip_powersave_test.unicast_testing()   # function to run unicast test

    captured_file_name, local_dir, filter = ip_powersave_test.get_captured_file_and_location()  # function returns captured_file_name along \
    # with location of local directory where the \
    # captured file is pulled

    # below function should be executed along with multicast_testing or unicast_testing if we wish to disect captured file.
    ip_powersave_test.verify_dtim_multicast_pcap(local_dir + '/' + captured_file_name,
                                                 apply_filter=filter)

    # below function can be run solely without calling above functions to disect multicast packets \
    # if we have ready packet captured file to test dtim_multicast
    # ip_powersave_test.verify_dtim_multicast_pcap("/home/mahesh/Documents/bad-bcast-powersave.pcapng",
    #                                             apply_filter="wlan.addr== 68:7d:b4:5f:5c:3e || wlan.addr==04:f0:21:64:bb:69")

    # ip_powersave_test.verify_dtim_multicast_pcap("/home/mahesh/Documents/moni0-2022-02-17-170018.pcap",
    #                                              apply_filter="wlan.addr==04:f0:21:94:1e:4d || wlan.addr==3C:37:86:13:81:60")


if __name__ == "__main__":
    main()

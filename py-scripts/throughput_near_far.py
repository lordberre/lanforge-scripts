#!/usr/bin/env python3

"""throughput_near_far.py will create stations and layer-3 traffic to calculate the throughput of AP.

This script will create a VAP and apply some load by creating stations in AP's channel under VAP in order to make the channel
utilized after the channel utilized to specific level again create specific number of stations each with their own set of cross-connects and endpoints.
It will then create layer 3 traffic over a specified amount of time, testing for increased traffic at regular intervals.
This test will pass if all stations increase traffic over the full test duration.

Use './throughput_near_far.py --help' to see command line usage and options
Copyright 2021 Candela Technologies Inc
License: Free to distribute and modify. LANforge systems must be licensed.
"""

import sys
import os, paramiko, pprint
if sys.version_info[0] != 3:
    print("This script requires Python 3")
    exit(1)

if 'py-json' not in sys.path:
    sys.path.append(os.path.join(os.path.abspath('..'), 'py-json'))

import argparse
from LANforge import LFUtils
from realm import Realm
from lf_report import lf_report
from lf_graph import lf_line_graph
#import create_vap
import time
from datetime import datetime

# this class create VAP, station, and traffic
class NearFar(Realm):
    def __init__(self, ssid=None, security=None,   password=None,   sta_list=[], name_prefix=None,   upstream=None,
                 radio=None,        host="localhost",    port=8080,    mode=0,   ap=None, side_a_min_rate= 56,
                 side_a_max_rate=0, side_b_min_rate=56,  side_b_max_rate=0,      number_template="00000",
                 test_duration = 5, use_ht160=False,    _debug_on=False,       _exit_on_error=False,
                 _exit_on_fail=False, _dhcp = True, _serno = '2222' ):
        super().__init__(lfclient_host=host, lfclient_port=port),
        self.upstream = upstream
        self.host = host
        self.port = port
        self.ssid = ssid
        self.sta_list = sta_list
        self.security = security
        self.password = password
        self.radio = radio
        self.mode = mode
        self.ap = ap
        self.number_template = number_template
        self.debug = _debug_on
        self.name_prefix = name_prefix
        self.test_duration = test_duration
        self._dhcp = _dhcp
        self.serno = _serno

        self.station_profile = self.new_station_profile()
        self.station_profile.debug = self.debug
        if self.station_profile.use_ht160:
            self.station_profile.mode = 9
        self.station_profile.mode = mode

        # initializing traffic profile
        self.cx_profile = self.new_l3_cx_profile()
        self.cx_profile.host = self.host
        self.cx_profile.port = self.port
        self.cx_profile.name_prefix = self.name_prefix
        #self.cx_profile.side_a_min_bps = side_a_min_rate
        #self.cx_profile.side_b_min_bps = side_b_min_rate
        self.side_a_min_bps = side_a_min_rate
        self.side_b_min_bps = side_b_min_rate
        self.cx_profile.side_a_max_bps = side_a_max_rate
        self.cx_profile.side_b_max_bps = side_b_max_rate
        self.attenuator_profile = self.new_attenuator_profile()
        self.atten_initial()

    def atten_initial(self):
        self.attenuator_profile.atten_serno = self.serno
        self.attenuator_profile.atten_idx = "all"
        self.attenuator_profile.atten_val = '0'
        self.attenuator_profile.create()

    def start_station(self, print_pass=False, print_fail=False):
        self.station_profile.admin_up() # admin up the stations
        # to-do- check here if upstream port got IP
        temp_stas = self.station_profile.station_names.copy()

        if self.wait_for_ip(temp_stas):
            print("admin-up....")
            self._pass("All stations got IPs")
        else:
            self._fail("Stations failed to get IPs")
            self.exit_fail()
        #self.cx_profile.start_cx()  # run the traffic

    def start_l3_stop(self,tmp,start = True, stop = True):
        if start:
            self.json_post("/cli-json/clear_cx_counters", {
                "cx_name": 'all'})
            time.sleep(10)
            print("Starting CXs...", tmp)
            for cx_name in tmp:
                if self.debug:
                    print("cx-name: %s" % (cx_name))
                self.json_post("/cli-json/set_cx_state", {
                    "test_mgr": "default_tm",
                    "cx_name": cx_name,
                    "cx_state": "RUNNING"
                }, debug_=self.debug)
                if self.debug:
                    print(".", end='')
            time.sleep(self.test_duration)

        if stop:
            print("Stopping CXs...")
            for cx_name in tmp:
                self.stop_cx(cx_name)
                print(".", end='')

    def start_l3(self,_sta_cnt= [1],idx=0, val=0):
        print(f"-------side_a_min_bps  {self.side_a_min_bps}\n-------side_b_min_bps  {self.side_b_min_bps}")
        tot_sta = sum(_sta_cnt)
        '''if _sta_cnt[-1] < tot_sta:
            _sta_cnt.append(tot_sta)'''
        atn_thrp_a,atn_thrp_b = [],[]
        #count = 0
        for atn_val in val: #[0,10,20,30]
            #count += 1
            bps_rx_a, bps_rx_b = [], []
            try:  # if attenuator value and index is not configurable then execute the default case by setting all modules of attenuator to 0
                #if len(atn_val):
                #valu = atn_val.split(',')
                #if len(atn_val) == 1:
                self.build_atten(idx=idx, val=[atn_val]*len(idx)) # val= [0]
                #elif len(atn_val) == len(idx):
                #self.build_atten(idx=idx, val=atn_val.split(','))
                #print(f"not setting attenuator with \n{idx} and {valu}")
            except Exception as e:
                print(f"### {e} ###\n{idx} and {val}")
            start = 0
            for i in range(len(_sta_cnt)):
                if _sta_cnt[i] < tot_sta:
                    tmp = list(self.cx_profile.created_cx.keys())[start:(start + _sta_cnt[i])]
                elif _sta_cnt[i] == tot_sta:
                    start = 0
                    tmp = list(self.cx_profile.created_cx.keys())[start:]
                self.start_l3_stop(tmp)
                time.sleep(15)
                a,b  = self.throughput(tmp)
                bps_rx_a.append(a)
                #bps_rx_a[f'sta:{start}-{start+_sta_cnt[i]}'] = a
                bps_rx_b.append(b)
                #bps_rx_b[f'sta:{start}-{start+_sta_cnt[i]}'] = b
                start = _sta_cnt[i]
            print(f"(download-atten-val--{atn_val})bps_rx_a {bps_rx_a}\n(upload-atten-val--{atn_val})bps_rx_b {bps_rx_b}")
            atn_thrp_a.append(bps_rx_a)
            #atn_thrp_a[f'({atn_val})-{count}'] = bps_rx_a
            atn_thrp_b.append(bps_rx_b)
            #atn_thrp_b[f'({atn_val})-{count}'] = bps_rx_b
        print(f"download throughput (side-a) --{atn_thrp_a}\ndownload throughput (side-b) --{atn_thrp_b}")
        #self.report(atn_thrp_a = atn_thrp_a, atn_thrp_b = atn_thrp_b,station_count = _sta_cnt,attn_val = val)
        return atn_thrp_a, atn_thrp_b



    def stop(self,trf = True, ad_dwn = True):
        if trf:
            self.cx_profile.stop_cx()   # stop the traffic
        if ad_dwn:
            self.station_profile.admin_down()   # admin down the stations

    def pre_cleanup(self):
        # deleting the previously created traffic, stations
        print("clearing...")
        self.cx_profile.cleanup_prefix()
        for sta in self.sta_list:
            self.rm_port(sta, check_exists=True)

    def cleanup(self):
        self.cx_profile.cleanup()   # clearing the traffic
        self.station_profile.cleanup()
        LFUtils.wait_until_ports_disappear(base_url=self.lfclient_url, port_list=self.station_profile.station_names,
                                           debug=self.debug)

    def build(self,_sta_cnt = None):
        # creating stations using static IP and DHCP enabled stations
        self.station_profile.use_security(self.security, self.ssid, self.password)
        self.station_profile.set_number_template(self.number_template)
        self.station_profile.set_command_flag("add_sta", "create_admin_down", 1)
        self.station_profile.set_command_param("set_port", "report_timer", 1500)
        self.station_profile.set_command_flag("set_port", "rpt_timer", 1)
        print("Creating stations")
        try:
            start = 0
            #create stations if num_stations [10,40] create 10 on radio-1 and 40 on radio-2
            for i in range(len(_sta_cnt)):
                self.station_profile.create(radio=self.radio[i], sta_names_=self.sta_list[start:(start+_sta_cnt[i])],
                                    debug=self.debug)
                self.cx_profile.side_a_min_bps = self.side_a_min_bps[i]
                self.cx_profile.side_b_min_bps = self.side_b_min_bps[i]
                self.cx_profile.create(endp_type="lf_udp", side_a=self.station_profile.station_names[start:(start+_sta_cnt[i])],
                                       side_b=self.upstream, sleep_time=0)
                start = _sta_cnt[i]
        except IndexError as e: #if radio len is less then sta_count length
            print(f"###{e}####\n no.fo.stations: {_sta_cnt}\nradio: {self.radio}\n")
            exit(1)
            '''if len(self.radio) < len(_sta_cnt):
                print(f"\nRadio-- {self.radio}---{len(self.radio)}\n Station count--- {_sta_cnt}---{len(_sta_cnt)}")
                self.station_profile.create(radio=self.radio[0], sta_names_=self.sta_list[start:],
                                                debug=self.debug)
                self.cx_profile.create(endp_type="lf_udp", side_a=self.station_profile.station_names, side_b=self.upstream, sleep_time=0)'''
        self._pass("PASS: Station build finished")

    def build_atten(self,idx,val):
        #setting attenuators values # idx = [4,5] val = [0,0,0,0]
        #val = val.split(",")
        self.attenuator_profile.atten_serno = self.serno
        for i in range(len(idx)):
            self.attenuator_profile.atten_idx = idx[i]
            self.attenuator_profile.atten_val = val[i]
            self.attenuator_profile.create()
        self.attenuator_profile.show()

    def throughput(self,tmp, sta_list=None):
        # bps-rx-a (download) and bps-rx-b(upload) values are taken
        bps_rx_a, bps_rx_b = [],[]
        #for sta in list(self.cx_profile.created_cx.keys():
        if self.cx_profile.side_a_min_bps != '0' and self.cx_profile.side_a_min_bps != 0:
            bps_rx_b.extend(list(map(lambda i : float(f"{i['bps rx b']/(1000000):.2f}"),
                             list((self.json_get('/cx/%s?fields=bps+rx+b' % (','.join(tmp)))).values())[2:])))

        if self.cx_profile.side_b_min_bps != '0' and self.cx_profile.side_b_min_bps != 0:
            bps_rx_a.extend(list(map(lambda i : float(f"{i['bps rx a']/(1000000):.2f}"),
                             list((self.json_get('/cx/%s?fields=bps+rx+a' % (','.join(tmp)))).values())[2:])))

        print(f"\nbps_rx_a:{bps_rx_a}\nbps_rx_b:{bps_rx_b}")
        return bps_rx_a,bps_rx_b

    def grph_commn(self,graph_ob, report_ob):
        graph_png = graph_ob.build_line_graph()
        print("graph name {}".format(graph_png))
        report_ob.set_graph_image(graph_png)
        report_ob.move_graph_image()
        report_ob.build_graph()

    def report(self,atn_thrp_a=None, atn_thrp_b=None,station_count = 0,attn_value=0):
        # report generation
        '''atn_thrp_a -- download values (bps_rx_a)  atn_thrp_b -- upload values (bps_rx_b)'''
        '''[[[29.95, 29.94, 29.94, 29.96, 29.96, 29.68, 29.71, 29.71, 29.72, 29.68],
        [1.57, 1.91, 2.73, 0.0, 2.43, 2.38, 0.0, 0.0, 2.17, 0.0, 0.0, 2.23, 2.19, 2.18, 2.2, 2.13, 2.09, 2.2, 2.11, 2.07,
             2.05, 1.39, 1.67, 1.5, 1.59, 1.56, 1.58, 1.49, 1.5, 1.61, 1.42, 0.0, 1.63, 0.0, 0.0, 1.75, 0.0, 1.76, 0.0, 1.6]],
         [[20.26, 20.05, 20.27, 20.19, 20.87, 20.41, 19.71, 20.61, 20.77, 20.26], [2.0, 2.08, 2.36, 0.0, 2.16, 2.12, 0.0, 0.0, 2.02, 0.0, 0.0, 1.86, 1.92, 1.71, 1.91, 1.78, 1.63, 1.75, 1.73, 1.78, 1.73, 1.59, 1.62, 1.58, 1.65, 1.74, 1.63, 1.63, 1.7, 1.66, 1.69, 0.0, 1.76, 0.0, 0.0, 1.83, 0.0, 1.83, 0.0, 1.98]]]'''
        test_setup_info = {
            "AP Name": self.ap,
            "SSID": self.ssid,
            "No.of stations": station_count,
            #"Total Test Duration": datetime.datetime.strptime(test_end, '%b %d %H:%M:%S') - datetime.datetime.strptime(
            #    test_time, '%b %d %H:%M:%S')
        }
        input_setup_info = {
            "Contact": "support@candelatech.com"
        }
        attn_val =  [f"{i} dm" for i in attn_value]
        report = lf_report(_results_dir_name = "Thrpughput_Near_Far",_output_html="throughput_near_far.html",
                           _output_pdf="throughput_near_far.pdf",)
        report.set_title("Throughput Near Far Scenario")
        report.build_banner()
        report.set_obj_html(_obj_title="Objective",
                            _obj=f"This test is designed to measure tany change in speed between clients having good and low rssi ")
        report.build_objective()
        report.test_setup_table(test_setup_data=test_setup_info, value="Device Under Test")
        # upload throughput
        if len(self.side_a_min_bps) == self.side_a_min_bps.count(0):
            print("upload rate",self.side_a_min_bps)
        else:
            up_thrp_1 = [sum(b[0]) for b in atn_thrp_b]
            up_thrp_2 = [sum(b[1]) for b in atn_thrp_b]
            report.set_obj_html(_obj_title=f"Upload Throughput",
                                _obj=f"This graph represents the upload throughput with and without attenuator.")
            report.build_objective()
            graph = lf_line_graph(_data_set=[up_thrp_1,up_thrp_2], _xaxis_name="Attenuation", _yaxis_name="Throughput(Mbps)",
                                 _xaxis_categories= attn_val, _label=[f"{station_count[0]} stations with attenuator",
                                                                     f"{station_count[1]} stations without attenuator"],
                                 _graph_image_name=f"Upload-throughput", _figsize=(10, 5), _graph_title="Near far scenario",
                                 _marker='o' )
            self.grph_commn(graph_ob = graph,report_ob = report)

        # download throughput
        if len(self.side_b_min_bps) == self.side_b_min_bps.count(0):
            print("download rate", self.side_b_min_bps)
        else:
            dn_thrp_1 = [sum(a[0]) for a in atn_thrp_a]
            dn_thrp_2 = [sum(a[1]) for a in atn_thrp_a]
            report.set_obj_html(_obj_title=f"Download Throughput",
                                _obj=f"This graph represents the download throughput with and without attenuator.")
            report.build_objective()
            graph = lf_line_graph(_data_set=[dn_thrp_1, dn_thrp_2], _xaxis_name="Attenuation", _yaxis_name="Throughput(Mbps)",
                                  _xaxis_categories=attn_val, _label=[f"{station_count[0]} stations with attenuator",
                                                                 f"{station_count[1]} stations without attenuator"],
                                  _graph_image_name=f"Download-throughput", _figsize=(10, 5), _graph_title="Near far scenario",
                                  _marker='o')
            self.grph_commn(graph_ob = graph,report_ob = report)

        report.test_setup_table(test_setup_data=input_setup_info, value="Information")
        report.build_footer()
        html_file = report.write_html()
        print("returned file {}".format(html_file))
        print(html_file)
        report.write_pdf()

        report.generate_report()

def calculate_duration(test_duration = 1):
    # calculate duration to seconds
    if test_duration.endswith('s') or test_duration.endswith('S'):
        test_dur = int(test_duration[0:-1])
    elif test_duration.endswith('m') or test_duration.endswith('M'):
        test_dur = int(test_duration[0:-1]) * 60
    elif test_duration.endswith('h') or test_duration.endswith('H'):
        test_dur = int(test_duration[0:-1]) * 60 * 60
    elif test_duration.endswith(''):
        test_dur = int(test_duration)
    return test_dur

def main():
    parser = argparse.ArgumentParser(description='''\
    throughput_near_far.py:
    --------------------
    Generic command layout:
    ===============================================================================
    sudo python3 throughput_near_far.py --mgr localhost --mgr_port 8080 --upstream eth1 --num_stations 10 40
    --security open --ssid testchannel --passwd [BLANK] --radio wiphy0 wiphy2 --atten_serno 2222 --atten_idx 0 1 5 6
    --atten_val 0,0,0,0 40,40,0,0 --duration 2 --ap_name WAC505 ''')
    optional = parser.add_argument_group('optional arguments')
    required = parser.add_argument_group('required arguments')
    optional.add_argument('--mgr', help='Hostname for where LANforge GUI is running', default='localhost')
    optional.add_argument('--mgr_port', help='port LANforge GUI HTTP service is running on', default=8080)
    optional.add_argument('--upstream', help='Non-station port that generates traffic: <resource>.<port>, '
                                                  'e.g: eth1', default='eth1')
    optional.add_argument('--num_stations', type = int, nargs="+", help='number of stations to create', default=[10,40])
    required.add_argument('--security', help='WiFi Security protocol: {open|wep|wpa2|wpa3')
    required.add_argument('--ssid', help='WiFi SSID for script object to associate to')
    required.add_argument('--passwd', help='WiFi passphrase/password/key')
    required.add_argument('--radio', nargs="+", help="provide the radio eg: --radio wiphy0 wiphy2")
    optional.add_argument('--mode', help= '''Used to force mode of stations: {auto : 0 || a : 1 || b : 2 ||
                        g : 3 || abg : 4 || abgn : 5 || bgn : 6 || bg : 7 || abgnAC : 8 || anAC : 9 || 
                        an : 10 || bgnAC : 11 || abgnAX : 12 || bgnAX  : 13}  eg: --mode 9''',default= 9)
    optional.add_argument('--ap_name', help= 'AP name',default= "Access Point")
    optional.add_argument('-t', '--test_duration', help= 'Sets the duration of each test eg: 2s --> two seconds || 2m --> two minutes '
                                                         '|| 2h --> two hours', default= '1m')
    optional.add_argument('--upload', help= 'Total minimum upload rate in Mbps for side_a of netgear', default= 0)
    optional.add_argument('--download', help= 'Total minimum download rate in Mbps for side_b of netgear', default= 0)
    optional.add_argument('-as','--atten_serno', help='Serial number for requested Attenuator', default='2222')
    optional.add_argument('-ai','--atten_idx', nargs = "+",help='Attenuator index eg. For module 1 = 1,module 2 = 2 --> --atten_idx 1 2 3' ,
                          default='all')
    optional.add_argument('-av','--atten_val', help='Requested attenuation in 1/10ths of dB (ddB) eg:--> --atten_val 0 10 20',
                          nargs="+")

    args = parser.parse_args()
    test_time = datetime.now().strftime("%b %d %H:%M:%S") # test start time
    print("Test started at ", test_time)
    station_list = LFUtils.portNameSeries(prefix_="sta", padding_number_=10000, radio=args.radio[0],
                                          start_id_=0, end_id_= sum(args.num_stations)-1,)
    print(f"Total list of stations:--\n{station_list}")
    atten_idx = [f"{int(i)-1}" for i in args.atten_idx] # attenuator module
    test_dur = calculate_duration(test_duration=args.test_duration) # test_duration
    upload = [int((float(args.upload) * 1000000)/i) for i in args.num_stations]
    download= [int((float(args.download) * 1000000)/i) for i in args.num_stations]
    # Initialize NearFar class
    near_far = NearFar(host=args.mgr,          port=args.mgr_port,         number_template="0000",  sta_list=station_list,
                       name_prefix="Thrp",         upstream=args.upstream,  ssid= args.ssid,   password=args.passwd,
                       radio=args.radio,    security=args.security,     test_duration = test_dur,   use_ht160=False,
                       side_a_min_rate=upload,    side_b_min_rate=download, mode=args.mode,       ap=args.ap_name, _serno = args.atten_serno)

    near_far.pre_cleanup() # clear existing clients
    near_far.build(_sta_cnt= args.num_stations)     # create Stations and traffic
    near_far.start_station()  # admin-up the sta

    if not near_far.passes():
        print(near_far.get_fail_message())
        near_far.exit_fail()

    atn_thrp_a, atn_thrp_b = near_far.start_l3(_sta_cnt= args.num_stations,idx=atten_idx, val=args.atten_val)
    near_far.report(atn_thrp_a=atn_thrp_a, atn_thrp_b=atn_thrp_b, station_count=args.num_stations, attn_value=args.atten_val)

    #near_far.stop()
    near_far.cleanup()

    if near_far.passes():
        near_far.exit_success()


if __name__ == "__main__":
    main()



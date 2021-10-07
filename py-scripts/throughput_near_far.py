#!/usr/bin/env python3

"""throughput_near_far.py will create stations and layer-3 traffic to calculate the throughput of AP with two different types of stations
 where some stations connected with attenuator and rest of the stations are without attenuation.

This script will create specific number of stations each with their own set of cross-connects and endpoints.
It will then create layer 3 traffic over a specified amount of time, testing for increased attenuation at regular intervals.

Use './throughput_near_far.py --help' to see command line usage and options
Copyright 2021 Candela Technologies Inc
License: Free to distribute and modify. LANforge systems must be licensed."""

import sys, os, traceback, argparse, time, datetime
if sys.version_info[0] != 3:
    print("This script requires Python 3")
    exit(1)

if 'py-json' not in sys.path:
    sys.path.append(os.path.join(os.path.abspath('..'), 'py-json'))

from LANforge import LFUtils
from realm import Realm
from lf_report import lf_report
from lf_graph import lf_line_graph
from lf_csv import lf_csv


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
        self.test_duration = self.calculate_duration(test_duration)
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

    def monitor(self, duration_sec, monitor_interval, created_cx, col_names, iterations):
        try:
            duration_sec = Realm.parse_time(duration_sec).seconds
        except:
            if (duration_sec is None) or (duration_sec <= 1):
                raise ValueError("L3CXProfile::monitor wants duration_sec > 1 second")
            if (duration_sec <= monitor_interval):
                raise ValueError("L3CXProfile::monitor wants duration_sec > monitor_interval")
        if created_cx == None:
            raise ValueError("Monitor needs a list of Layer 3 connections")
        if (monitor_interval is None) or (monitor_interval < 1):
            raise ValueError("L3CXProfile::monitor wants monitor_interval >= 1 second")

        # monitor columns
        start_time = datetime.datetime.now()
        end_time = start_time + datetime.timedelta(seconds=duration_sec)
        # bps-rx-a (download) and bps-rx-b(upload) values are taken
        self.bps_rx_a, self.bps_rx_b, self.bps_rx, index = [], [], {}, -1
        bps_rx_a_avg, bps_rx_b_avg = [], []
        [(self.bps_rx_a.append([]), self.bps_rx_b.append([])) for i in range(len(created_cx))]
        for test in range(1 + iterations):
            while datetime.datetime.now() < end_time:
                index += 1
                response = list(
                    self.json_get('/cx/%s?fields=%s' % (','.join(created_cx), ",".join(col_names))).values())[2:]
                self.bps_rx[index] = list(map(lambda i: [float(f"{x / (1000000):.2f}") for x in i.values()], response))
                time.sleep(monitor_interval)
        # bps_rx list is calculated
        print("rx rate values are ", self.bps_rx)
        for index, key in enumerate(self.bps_rx):
            for i in range(len(self.bps_rx[key])):
                if self.cx_profile.side_b_min_bps != '0' and self.cx_profile.side_b_min_bps != 0:
                    self.bps_rx_a[i].append(self.bps_rx[key][i][0])
                if self.cx_profile.side_a_min_bps != '0' and self.cx_profile.side_a_min_bps != 0:
                    self.bps_rx_b[i].append(self.bps_rx[key][i][1])
        print(f"bps-rx-a-: {self.bps_rx_a}\nbps-rx-b-: {self.bps_rx_b}")
        if self.cx_profile.side_a_min_bps != '0' and self.cx_profile.side_a_min_bps != 0:
            bps_rx_b_avg = [float(f"{sum(i) / len(i): .2f}") for i in self.bps_rx_b]
        if self.cx_profile.side_b_min_bps != '0' and self.cx_profile.side_b_min_bps != 0:
            bps_rx_a_avg = [float(f"{sum(i) / len(i): .2f}") for i in self.bps_rx_a]
        return bps_rx_a_avg, bps_rx_b_avg, self.bps_rx

    def start_l3_stop(self,tmp,start = True, stop = True):
        if start:
            self.json_post("/cli-json/clear_cx_counters", {
                "cx_name": 'all'})
            time.sleep(5)
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
            time.sleep(20)
            bps_rx_a_avg, bps_rx_b_avg, bps_rx = self.monitor(duration_sec=self.test_duration,monitor_interval=1,
                                                          created_cx=tmp,col_names=['bps rx a','bps rx b'],iterations=0)

        if stop:
            print("Stopping CXs...")
            for cx_name in tmp:
                self.stop_cx(cx_name)
                print(".", end='')
        return bps_rx_a_avg, bps_rx_b_avg, bps_rx

    def start_l3(self,_sta_cnt= [1],idx=0, val=0):
        print(f"-------side_a_min_bps  {self.side_a_min_bps}\n-------side_b_min_bps  {self.side_b_min_bps}")
        tot_sta = sum(_sta_cnt)
        atn_thrp_a,atn_thrp_b,bps_rx = [],[],[]
        for atn_val in val: #[0,10,20,30]
            try:  # if attenuator value and index is not configurable then execute the default case by setting all modules of attenuator to 0
                self.build_atten(idx=idx, val=[atn_val]*len(idx))

            except Exception as e:
                print(f"### {e} ###\n{idx} and {atn_val}")
            bps_rx_a,bps_rx_b,bps_rx_a_b = self.start_l3_stop(list(self.cx_profile.created_cx.keys()))
            print(f"\nThroughput value for-- {atn_val}dbm {bps_rx_a_b}\n\n(download-atten-val--{atn_val} dbm) bps_rx_a {bps_rx_a}"
                  f"\n(upload-atten-val--{atn_val} dbm) bps_rx_b {bps_rx_b}\n")
            atn_thrp_a.append(bps_rx_a)
            atn_thrp_b.append(bps_rx_b)
            bps_rx.append(bps_rx_a_b)
        print(f"download throughput (side-a) --{atn_thrp_a}\ndownload throughput (side-b) --{atn_thrp_b}")
        return atn_thrp_a, atn_thrp_b,bps_rx

    def stop(self,trf = True, ad_dwn = True):
        if trf:
            self.cx_profile.stop_cx()   # stop the traffic
        if ad_dwn:
            self.station_profile.admin_down()   # admin down the stations

    def pre_cleanup(self):
        # deleting the previously created stations
        print("clearing...")

        exist_sta = []
        for u in self.json_get("/port/?fields=port+type,alias")['interfaces']:
            if list(u.values())[0]['port type'] not in ['Ethernet', 'WIFI-Radio', 'NA']:
                exist_sta.append(list(u.values())[0]['alias'])
        self.station_profile.cleanup(desired_stations = exist_sta)
        # deleting the previously created traffic
        try:
            exist_l3 = list(filter(lambda cx_name: cx_name if (cx_name != 'handler' and cx_name != 'uri') else False,
                                   self.json_get("/cx/?fields=name")))
            list(map(lambda i: self.rm_cx(cx_name=i),exist_l3))
            list(map(lambda cx_name: [self.rm_endp(ename=i) for i in [f"{cx_name}-A",f"{cx_name}-B"]], exist_l3))
        except Exception as e:
            print("###",e,'###')

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

        self._pass("PASS: Station build finished")

    def build_atten(self,idx,val):
        #setting attenuators values # idx = [4,5] val = [0,0,0,0]
        self.attenuator_profile.atten_serno = self.serno
        for i in range(len(idx)):
            self.attenuator_profile.atten_idx = idx[i]
            self.attenuator_profile.atten_val = val[i]
            self.attenuator_profile.create()
        self.attenuator_profile.show()

    def throughput(self,tmp, sta_list=None):
        # bps-rx-a (download) and bps-rx-b(upload) values are taken
        bps_rx_a, bps_rx_b = [],[]
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

    def report(self,atn_thrp_a=None, atn_thrp_b=None,station_count = 0,attn_value=0,test_dur = None,traff_direction=None,
               data = None):
        # report generation
        '''atn_thrp_a -- download values (bps_rx_a)  atn_thrp_b -- upload values (bps_rx_b)'''
        '''[[[29.95, 29.94, 29.94, 29.96, 29.96, 29.68, 29.71, 29.71, 29.72, 29.68],
        [1.57, 1.91, 2.73, 0.0, 2.43, 2.38, 0.0, 0.0, 2.17, 0.0, 0.0, 2.23, 2.19, 2.18, 2.2, 2.13, 2.09, 2.2, 2.11, 2.07,
             2.05, 1.39, 1.67, 1.5, 1.59, 1.56, 1.58, 1.49, 1.5, 1.61, 1.42, 0.0, 1.63, 0.0, 0.0, 1.75, 0.0, 1.76, 0.0, 1.6]],
         [[20.26, 20.05, 20.27, 20.19, 20.87, 20.41, 19.71, 20.61, 20.77, 20.26], [2.0, 2.08, 2.36, 0.0, 2.16, 2.12, 0.0, 0.0, 2.02, 0.0, 0.0, 1.86, 1.92, 1.71, 1.91, 1.78, 1.63, 1.75, 1.73, 1.78, 1.73, 1.59, 1.62, 1.58, 1.65, 1.74, 1.63, 1.63, 1.7, 1.66, 1.69, 0.0, 1.76, 0.0, 0.0, 1.83, 0.0, 1.83, 0.0, 1.98]]]'''
        test_setup_info = {
            "AP Name": self.ap,
            "SSID": self.ssid,
            "No.of stations with attenuator": station_count[0],
            "No.of stations without attenuator": station_count[1],
            'Intended throughput': traff_direction,
            "Total Test Duration": test_dur,
        }
        input_setup_info = {
            "Contact": "support@candelatech.com"
        }
        attn_val =  [f"{int((float(i))/10):.1f} db" for i in attn_value]
        report = lf_report(_results_dir_name = "Thrpughput_Near_Far",_output_html="throughput_near_far.html",
                           _output_pdf="throughput_near_far.pdf",)
        report.set_title("Throughput Near Far Scenario")
        report.build_banner()
        report.set_obj_html(_obj_title="Objective",
                            _obj=f"This test is designed to verify the throughput for N(Number of Clients) connected near to"
                                 f" the AP with good RSSI while there are other clients connected with active data-traffic "
                                 f"at low RSSI levels")
        report.build_objective()
        # test setup information
        report.set_table_title("Test Setup Information")
        report.build_table_title()
        report.test_setup_table(test_setup_data=test_setup_info, value="Device Under Test")
        # upload throughput
        if len(self.side_a_min_bps) == self.side_a_min_bps.count(0):
            print("upload rate",self.side_a_min_bps)
        else:
            up_thrp_1,up_thrp_2 = [],[]
            for b in atn_thrp_b:
                up_thrp_1.append(sum(b[0:station_count[0]]))
                up_thrp_2.append(sum(b[station_count[0]:]))
            report.set_obj_html(_obj_title=f"Upload Throughput",
                                _obj=f"The below graph represents attenuation values on X-axis and overall throughput in Mbps "
                                     f" for all connected stations on Y-axis.")
            report.build_objective()
            graph = lf_line_graph(_data_set=[up_thrp_1,up_thrp_2], _xaxis_name="Attenuation(db)", _yaxis_name="Throughput(Mbps)",
                                 _xaxis_categories= attn_val,_label=[f"{station_count[0]} stations with attenuator",
                                                                 f"{station_count[1]} stations without attenuator"],
                                 _graph_image_name=f"Upload-throughput", _figsize=(10, 5), _graph_title="Near far scenario",
                                 _marker='o', _legend_loc="best", _legend_box=None, _legend_ncol=1,
                                  _color=['forestgreen','c'])
            self.grph_commn(graph_ob = graph,report_ob = report)

        # download throughput
        if len(self.side_b_min_bps) == self.side_b_min_bps.count(0):
            print("download rate", self.side_b_min_bps)
        else:
            dn_thrp_1 = [sum(a[0:station_count[0]]) for a in atn_thrp_a]
            dn_thrp_2 = [sum(a[station_count[0]:]) for a in atn_thrp_a]
            report.set_obj_html(_obj_title=f"Download Throughput",
                                _obj=f"The below graph represents attenuation values on X-axis and overall throughput in Mbps "
                                     f" for all connected stations on Y-axis.")
            report.build_objective()
            graph = lf_line_graph(_data_set=[dn_thrp_1, dn_thrp_2], _xaxis_name="Attenuation(db)", _yaxis_name="Throughput(Mbps)",
                                  _xaxis_categories=attn_val, _label=[f"{station_count[0]} stations with attenuator",
                                                                 f"{station_count[1]} stations without attenuator"],
                                  _graph_image_name=f"Download-throughput", _figsize=(10, 5), _graph_title="Near far scenario",
                                  _marker='o', _legend_loc="best", _legend_box=None, _legend_ncol=1,
                                  _color=['forestgreen','c'])
            self.grph_commn(graph_ob = graph,report_ob = report)

        # input setup information
        report.set_table_title("Input Setup Information")
        report.build_table_title()
        report.test_setup_table(test_setup_data=input_setup_info, value="Information")
        report.build_footer()
        html_file = report.write_html()
        print("returned file {}".format(html_file))
        print(html_file)
        report.write_pdf()
        csv_col_head = [f'{attn_value[i]}dbm-bps_rx(a,b)-sec{j+1}' for i in range(len(data)) for j in range(len(data[i]))]
        csv_col_head.insert(0,'Stations')
        csv_dataset = []
        list(map(lambda i : csv_dataset.extend(list(i.values())),data))
        csv_dataset.insert(0, self.sta_list)
        csv = lf_csv(_columns=csv_col_head, _rows=csv_dataset, _filename='throughput_near_far.csv')
        csv.generate_csv()
        report.csv_file_name = "throughput_near_far.csv"
        report.move_csv_file()

    def calculate_duration(self,test_duration = 1):
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
    try:
        parser = argparse.ArgumentParser(description='''\
        throughput_near_far.py:
        --------------------
        Generic command layout:
        ===============================================================================
        sudo python3 throughput_near_far.py --mgr localhost --mgr_port 8080 --upstream eth1 --num_stations 10 40
        --security open --ssid testchannel --passwd [BLANK] --radio wiphy0 wiphy2 --atten_serno 2222 --atten_idx 0 1 5 6
        --atten_val 0 40 50 --duration 2 --ap_name WAC505 ''')
        optional = parser.add_argument_group('optional arguments')
        required = parser.add_argument_group('required arguments')
        optional.add_argument('--mgr', help='Hostname for where LANforge GUI is running', default='localhost')
        optional.add_argument('--mgr_port', help='port LANforge GUI HTTP service is running on', default=8080)
        optional.add_argument('--upstream', help='Non-station port that generates traffic: <resource>.<port>, '
                                                      'e.g: eth1', default='eth1')
        optional.add_argument('--num_stations', type = int, nargs="+", help='Provide the no.of stations to create with attenuator'
                                                'then no.of sttaions without attenuator eg: --num_stations 10 40', default=[10,40])
        required.add_argument('--security', help='WiFi Security protocol: {open|wep|wpa2|wpa3')
        required.add_argument('--ssid', help='WiFi SSID for script object to associate to')
        required.add_argument('--passwd', help='WiFi passphrase/password/key')
        required.add_argument('--radio', nargs="+", help="Provide radio with attenuator then radio without attenuator eg: --radio wiphy0 wiphy2")
        optional.add_argument('--mode', help= '''Used to force mode of stations: {auto : 0 || a : 1 || b : 2 ||
                            g : 3 || abg : 4 || abgn : 5 || bgn : 6 || bg : 7 || abgnAC : 8 || anAC : 9 || 
                            an : 10 || bgnAC : 11 || abgnAX : 12 || bgnAX  : 13}  eg: --mode 9''',default= 9)
        optional.add_argument('--ap_name', help= 'AP name',default= "Access Point")
        optional.add_argument('-t', '--test_duration', help= 'Sets the duration of each test eg: 2s --> two seconds || 2m --> two minutes '
                                                             '|| 2h --> two hours', default= '1m')
        optional.add_argument('--upload', help= 'Total minimum upload rate in Mbps for side_a', default= 0)
        optional.add_argument('--download', help= 'Total minimum download rate in Mbps for side_b', default= 0)
        optional.add_argument('-as','--atten_serno', help='Serial number for requested Attenuator', default='2222')
        optional.add_argument('-ai','--atten_idx', nargs = "+",help='Attenuator index eg. For module 1 = 1,module 2 = 2 --> '
                                                                    '--atten_idx 1 2 3', default='all')
        optional.add_argument('-av','--atten_val', help='Requested attenuation in 1/10ths of dB (ddB) eg:--> --atten_val 0 10 20',
                              nargs="+")

        args = parser.parse_args()
        test_time = datetime.datetime.now().strftime("%b %d %H:%M:%S") # test start time
        print("\nTest started at ", test_time,'\n')
        station_list = LFUtils.portNameSeries(prefix_="sta", padding_number_=10000, radio=args.radio[0],
                                              start_id_=0, end_id_= sum(args.num_stations)-1,)
        print(f"Total list of stations:--\n{station_list}")
        atten_idx = [f"{int(i)-1}" for i in args.atten_idx] # attenuator module
        upload = [int((float(args.upload) * 1000000)/i) for i in args.num_stations]
        download= [int((float(args.download) * 1000000)/i) for i in args.num_stations]
        # Initialize NearFar class
        near_far = NearFar(host=args.mgr,          port=args.mgr_port,         number_template="0000",  sta_list=station_list,
                           name_prefix="Thrp",         upstream=args.upstream,  ssid= args.ssid,   password=args.passwd,
                           radio=args.radio,    security=args.security,     test_duration = args.test_duration,   use_ht160=False,
                           side_a_min_rate=upload,    side_b_min_rate=download, mode=args.mode,       ap=args.ap_name, _serno = args.atten_serno)
        near_far.pre_cleanup() # clear existing clients and l3 traffic
        near_far.build(_sta_cnt= args.num_stations)     # create Stations and traffic
        near_far.start_station()  # admin-up the sta

        if not near_far.passes():
            print(near_far.get_fail_message())
            near_far.exit_fail()

        atn_thrp_a, atn_thrp_b, bps_rx = near_far.start_l3(_sta_cnt= args.num_stations,idx=atten_idx, val=args.atten_val)

        test_end = datetime.datetime.now().strftime("%b %d %H:%M:%S")
        print("\nTest ended at ", test_end,'\n')
        up_down,intended_thrp = '',''
        if int(args.upload) != 0:
            up_down += f'Upload({args.upload} Mbps)  \t '
        if int(args.download) != 0:
            up_down += f'Download({args.download} Mbps)'

        near_far.report(atn_thrp_a=atn_thrp_a, atn_thrp_b=atn_thrp_b, station_count=args.num_stations, attn_value=args.atten_val,
                        test_dur = datetime.datetime.strptime(test_end, '%b %d %H:%M:%S') - datetime.datetime.strptime(test_time, '%b %d %H:%M:%S'),
                        traff_direction = up_down, data = bps_rx)
        near_far.pre_cleanup()
        if near_far.passes():
            near_far.exit_success()

    except Exception as e:
        print("###",e,"###\nUnable to run the script...\nProvide the right values with the help of --help command\n"
                      "OR Re-run the script if the script stopped by some unexpected behavior..")
        print(traceback.format_exc())

if __name__ == "__main__":
    main()



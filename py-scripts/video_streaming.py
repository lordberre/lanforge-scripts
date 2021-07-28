""" how to run - python3 lf_webpage.py --mgr localhost --upstream_port eth1 --num_stations 40
    --security open --ssid Nikita --passwd [BLANK]
 --target_per_ten 1 --url 192.168.212.225/webpagetesting.html  --bands 5G"""
import sys,functools
if 'py-json' not in sys.path:
    sys.path.append('../py-json')
from LANforge import LFUtils
from LANforge import lfcli_base
from LANforge.lfcli_base import LFCliBase
from LANforge.LFUtils import *
import realm
from realm import Realm
from realm import PortUtils
import argparse, time, os, paramiko, datetime
#from datetime import datetime
from itertools import groupby
#from webpage_report import *
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from lf_report import lf_report
from lf_graph import lf_bar_graph
import random
class VideoStreaming(Realm):
    def __init__(self, lfclient_host, lfclient_port, upstream, num_sta, security, ssid, password, url,
                 target_per_ten, max_speed,file_size, bands,start_id=0, _debug_on=False, _exit_on_error=False,
                 _exit_on_fail=False, _radio = None):
        self.host = lfclient_host
        self.port = lfclient_port
        self.lfclient_url = "http://%s:%s" % (lfclient_host, lfclient_port)
        self.proxy = {}
        self.exit_on_error = _exit_on_error
        self.exit_on_fail = _exit_on_fail
        self.upstream = upstream
        self.num_sta = num_sta
        self.security = security
        self.ssid = ssid
        self.sta_start_id = start_id
        self.password = password
        self.url = url
        self.target_per_ten = target_per_ten
        self.max_speed = max_speed
        self.file_size = file_size
        self.bands = bands
        print("in",bands)
        self.debug = _debug_on
        self.radio = _radio

        self.local_realm = realm.Realm(lfclient_host=self.host, lfclient_port=self.port)
        self.station_profile = self.local_realm.new_station_profile()
        self.station_profile.debug = self.debug
        self.http_profile = self.local_realm.new_http_profile()
        self.http_profile.requests_per_ten = self.target_per_ten
        self.http_profile.max_speed = self.max_speed

        self.http_profile.url = self.url
        self.port_util = PortUtils(self.local_realm)
        self.http_profile.debug = _debug_on
        self.created_cx = {}


    def precleanup(self):
        self.count = 0
        try:
            pass
            #self.local_realm.load("BLANK") #no need to load
        except:
            print("couldn't load 'BLANK' Test Configuration")

        for rad in self.radio:
            if self.bands == "5G":
                # select an mode
                self.station_profile.mode = 9
            elif self.bands == "2.4G":
                # select an mode
                self.station_profile.mode = 11
            # check Both band if both band then for 5G and 2G bands split stations equaly
            if self.bands == '5G/2.4G':
                self.count += 1
                if self.count == 2:
                    self.sta_start_id = self.num_sta
                    self.num_sta = 2 * (self.num_sta)
                    self.http_profile.cleanup()
                    # create station list with sta_id 20

                    self.station_list1 = LFUtils.portNameSeries(prefix_="sta", start_id_=self.sta_start_id,
                                                                end_id_=self.num_sta - 1, padding_number_=10000,
                                                                radio=rad)
                    # cleanup station list which started sta_id 20
                    self.station_profile.cleanup(self.station_list1, debug_=self.local_realm.debug)
                    LFUtils.wait_until_ports_disappear(base_url=self.local_realm.lfclient_url,
                                                       port_list=self.station_list1,
                                                       debug=self.local_realm.debug)
                    return
                else:
                    self.station_profile.mode = 9
            # clean dlayer4 ftp traffic
            self.http_profile.cleanup()
            self.station_list = LFUtils.portNameSeries(prefix_="sta", start_id_=self.sta_start_id,
                                                       end_id_=self.num_sta - 1, padding_number_=10000,
                                                       radio=rad)
            # cleans stations
            self.station_profile.cleanup(self.station_list, delay=1, debug_=self.local_realm.debug)
            LFUtils.wait_until_ports_disappear(base_url=self.local_realm.lfclient_url,
                                               port_list=self.station_list,
                                               debug=self.local_realm.debug)
            time.sleep(1)
        print("precleanup done")

    def build(self):
        self.port_util.set_http(port_name=self.local_realm.name_to_eid(self.upstream)[2], resource=1, on=True)
        '''data = {
            "shelf": 1,
            "resource": 1,
            "port": "eth1",
            "current_flags": 2147483648,
            "interest": 16384
        }
        url = "/cli-json/set_port"
        self.local_realm.json_post(url, data, debug_=True)
        time.sleep(5)'''

        for rad in self.radio:
            # station build
            self.station_profile.use_security(self.security, self.ssid, self.password)
            self.station_profile.set_command_flag("add_sta", "create_admin_down", 1)
            self.station_profile.set_command_param("set_port", "report_timer", 1500)
            self.station_profile.set_command_flag("set_port", "rpt_timer", 1)
            self.station_profile.create(radio=rad, sta_names_=self.station_list, debug=self.local_realm.debug)
            self.local_realm.wait_until_ports_appear(sta_list=self.station_list)
            self.station_profile.admin_up()
            if self.local_realm.wait_for_ip(self.station_list):
                self.local_realm._pass("All stations got IPs")
            else:
                self.local_realm._fail("Stations failed to get IPs")
            # building layer4
            self.http_profile.direction = 'dl'
            self.http_profile.dest = '/dev/null'
            self.http_profile.create(ports=self.station_list,
                                     sleep_time=.5,
                                     suppress_related_commands_=None, http=True,
                                     http_ip=self.url)

            if self.count == 2:
                self.station_profile.mode = 11
                self.station_list = self.station_list1
        for cx_name in self.http_profile.created_cx.keys():
            req_url = "cli-json/set_endp_report_timer"
            data = {
                "endp_name": cx_name,
                "milliseconds": 1000
            }
            self.json_post(req_url, data)
        print("Test Build done")

    def start(self, print_pass=False, print_fail=False):
        print("Test Started")

        self.http_profile.start_cx()
        try:
            for i in self.http_profile.created_cx.keys():
                while self.local_realm.json_get("/cx/" + i).get(i).get('state') != 'Run':
                    continue
        except Exception as e:
            pass
        print("Test Started")

    def monitor(self,
                duration_sec,
                monitor_interval,
                created_cx,
                col_names,
                iterations):

        try:
            duration_sec = Realm.parse_time(duration_sec).seconds
        except:
            if (duration_sec is None) or (duration_sec <= 1):
                raise ValueError("L4CXProfile::monitor wants duration_sec > 1 second")
            if (duration_sec <= monitor_interval):
                raise ValueError("L4CXProfile::monitor wants duration_sec > monitor_interval")
        if created_cx == None:
            raise ValueError("Monitor needs a list of Layer 4 connections")
        if (monitor_interval is None) or (monitor_interval < 1):
            raise ValueError("L4CXProfile::monitor wants monitor_interval >= 1 second")

        #assign column names
        if col_names is not None and len(col_names) > 0:
            print(col_names)
            header_row=col_names
        else:
            header_row=list((list(self.json_get("/layer4/all")['endpoint'][0].values())[0].keys()))
            print(header_row)

        #monitor columns
        start_time = datetime.datetime.now()
        end_time = start_time + datetime.timedelta(seconds=duration_sec)

        rx_rate = []
        for test in range(1 + iterations):
            while datetime.datetime.now() < end_time:
                if col_names is None:
                    response = self.json_get("/layer4/all")
                else:
                    fields = ",".join(col_names)
                    created_cx_ = ",".join(created_cx)

                    response = self.json_get("/layer4/%s?fields=%s" % (created_cx_, fields))
                    endpt = response['endpoint']
                    if len(self.station_list) > 1:
                        for i in endpt:
                            name = list(i.keys())[0]
                            rx_rate.append(i[name]['rx rate'])
                    else:
                        rx_rate.append(endpt['rx rate'])

                time.sleep(monitor_interval)

        #rx_rate list is calculated
        print("rx rate values are ", rx_rate)
        return rx_rate

    def postcleanup(self):
        # for rad in self.radio
        exist_sta = list(filter(lambda c: True if c[0:3] =='sta' else False,
                [i[list(i.keys())[0]]['alias'] for i in self.json_get("/port/?fields=alias")['interfaces']]))

        exist_l4 = self.json_get("/layer4/?fields=name")
        if 'endpoint' in list(exist_l4.keys()):
            self.http_profile.created_cx = {}
            if len(exist_l4['endpoint']) > 1:
                for i in exist_l4['endpoint']:
                    self.http_profile.created_cx[list(i.keys())[0]] = 'CX_'+i[list(i.keys())[0]]['name']
            else:
                self.http_profile.created_cx[exist_l4['endpoint']['name']] = 'CX_'+exist_l4['endpoint']['name']

        self.http_profile.cleanup()
        self.station_profile.cleanup(desired_stations = exist_sta)
        #LFUtils.wait_until_ports_disappear(base_url=self.lfclient_url, port_list=exist_sta,
        #                                   debug=self.debug)
        self.http_profile.created_cx.clear()

    def file_create(self):
        change_path = os.path.dirname(os.path.abspath(__file__))
        os.chdir('/usr/local/lanforge/nginx/html/')
        #192.168.208.92/video.txt
        if os.path.isfile("/usr/local/lanforge/nginx/html"+self.url[self.url.index('/'):]):
            os.system("sudo rm /usr/local/lanforge/nginx/html"+self.url[self.url.index('/'):])
        os.system("sudo fallocate -l " + self.file_size + " /usr/local/lanforge/nginx/html"+self.url[self.url.index('/'):])
        print("File creation done", self.file_size)
        os.chdir(change_path)

class AP_automate:
    def __init__(self, ap_ip, user, pswd):
            self.ap_ip = ap_ip
            self.user = user
            self.pswd = pswd

    def get_ap_model(self, ap_ip, user, pswd):
        self.ap_ip = ap_ip
        self.user = user
        self.pswd = pswd
        ssh = paramiko.SSHClient()  # creating shh client object we use this object to connect to router
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # automatically adds the missing host key
        ssh.connect(ap_ip, port=22, username=user, password=pswd)
        stdin, stdout, stderr = ssh.exec_command('printmd')
        output = stdout.readlines()
        ssh.close()
        return output

def grph_commn(graph_ob,report_ob):
    graph_png = graph_ob.build_bar_graph()
    print("graph name {}".format(graph_png))
    report_ob.set_graph_image(graph_png)
    report_ob.move_graph_image()
    report_ob.build_graph()

def report(buffer1,test_setup_info,input_setup_info,threshold,duration,bands,expt_stal = 6,avg_rxrate = None,
           sta_cnt=0, emu_rate = None):
    buffer = {}
    for i in range(len(bands)): #making list as dict format
        buffer[bands[i]] = buffer1[i]
    print(buffer)
    def emu(emu_rate):
        for i in emu_rate:
            if i in ["Disabled" , "disabled" , "DISABLED"]:
                yield f"{i}({0} Mbps)"
            elif i in ["216 p4" , "216 P4"]:
                yield f"{i}({300e-3} Mbps)"
            elif i in ["240 p4" , "240 P4"]:
                yield f"{i}({500e-3} Mbps)"
            elif i in ["SD 360p" , "sd 360p" , "SD 360P" , "sd 360P"]:
                yield f"{i}({700e-3} Mbps)"
            elif i in ["SD 480p" , "sd 480p" , "SD 480P" , "sd 480P"]:
                yield f"{i}({1.1} Mbps)"
            elif i in ["HD 720p" , "hd 720p" , "HD 720P" , "hd 720P"]:
                yield f"{i}({2.5} Mbps)"
            elif i in ["HD 1080p" , "hd 1080p" , "HD 1080P" , "hd 1080P"]:
                yield f"{i}({5} Mbps)"
            elif i == "4K" or i == "4k":
                yield f"{i}({20} Mbps)"
            else:
                yield f"{i} Mbps"
    speeds = list(buffer[bands[0]].keys())
    data_rate = list(emu(emu_rate))
    pass_fail,info,pas_fail_disp = [],[],[]
    for bnds in buffer:
        for spd in buffer[bnds]:
            if max(buffer[bnds][spd].values()) <= expt_stal:
                pass_fail.append('Pass')
                info.append(f"Station Pass : {sta_cnt}")
                pas_fail_disp.append("All the stations got buffer less than or equal to expected stalls")
            elif min(buffer[bnds][spd].values()) > expt_stal:
                pass_fail.append('Fail')
                info.append(f"Station Fail : {sta_cnt}")
                pas_fail_disp.append("One or more stations got buffer greater than expected stalls")
            else:
                tmp = list(buffer[bnds][spd].values())
                tmp.sort()  # sort the values to check whether any of the value is above the expected stalls or not
                c = 0
                '''split the tmp list into two and if the mid value is below the expected_stall then search in 2nd part of list
                and get the count of failed stations
                in case the mid value is above the expected_Stall then take the length of list's 2nd part consider this as no.of failed stations
                also check in 1st part of list to find the failed stations'''
                if tmp[int(len(tmp)/2)] <= expt_stal:
                    ttmp = tmp[int(len(tmp)/2)+1 :]
                    while ttmp:
                        #pop all the vaues below expected_stall and take count of remaing values
                        t = ttmp.pop(ttmp.index(min(ttmp)))
                        if t > expt_stal:
                            c += (len(ttmp)+1)
                            break
                elif tmp[int(len(tmp)/2)] > expt_stal:
                    c = len(tmp[int(len(tmp)/2):])
                    ttmp = tmp[:int(len(tmp) / 2)]
                    while ttmp:
                        # pop all the values above the expected_stalls and count each values break once u get values below expected_stall and then break loop
                        t = ttmp.pop(ttmp.index(max(ttmp)))
                        if t > expt_stal:
                            c += 1
                        else:
                            break

                pass_fail.append('Fail')
                info.append(f'Station Fail : {c}')
                pas_fail_disp.append("One or more stations got buffer greater than expected stalls")

    mode_spd = [f"{i} - {j}" for i in bands for j in data_rate]
    pasfail_tab = pd.DataFrame({
        #getting no.of stations form buffer
        'No.of stations': [sta_cnt]*len(mode_spd),#buffer[list(buffer.keys())[0]][list(buffer[list(buffer.keys())[0]].keys())[0]].values(),
        'Mode-speed': mode_spd,
        'Pass/Fail': pass_fail,
        'Info':info,
        'Description': pas_fail_disp})
    print("Pass/fail",pasfail_tab)

    report = lf_report(_results_dir_name = "Video_Streaming",_alt_path = "")
    report.set_title("Video Streaming")
    report.build_banner()
    report.set_obj_html(_obj_title="Objective", _obj=f"This test is designed to measure video streaming quality of experience on connected "
                             f"stations over a 2.4/5Ghz Wi-Fi bands by calculating initial buffer timers for the "
                             f"individual stations")
    report.build_objective()
    report.set_table_title("Test Setup Information")
    report.build_table_title()
    report.test_setup_table(test_setup_data=test_setup_info, value = "Device Under Test")
    #report.build_custom()
    report.set_obj_html(_obj_title="", _obj=f"This table briefs about overall Pass/Fail criteria of stations where "
                        f"the no.of video stalls of {sta_cnt} stations should be less than or equal to expected stall {expt_stal} "
                        f"then it is considered to be as a Pass. If one or more stations got video stall greater than the expected stall "
                        f"{expt_stal} then it is considered to be a Fail")
    report.set_table_title("Pass/Fail Criteria")
    report.build_table_title()
    report.build_objective()
    report.set_table_dataframe(pasfail_tab)
    report.build_table()
    if sta_cnt <= 40:
        step = 1
    elif 40 < sta_cnt <= 80:
        step = 3
    elif 80 < sta_cnt <= 100:
        step = 5
    else:
        step = 10
    #plotting graph
    for band in bands:
        i = -1
        for speed in speeds:
            i += 1
            report.set_obj_html(_obj_title="", _obj=f"The below graph explains, how many stalls the individual station "
                                                    f"is experiencing when the traffic is running for {duration} "
                                                    f"minutes with expected stalls and threshold is {expt_stal} and {threshold}% "
                                                    f"per station respectively. The X-axis represents the number of stations,"
                                                    f" Y-axis represents stall count")
            label = f"{data_rate[i]}"
            report.set_graph_title(f"{band}-Stations Emulation rate {label} per Station")
            report.build_graph_title()
            report.build_objective()
            graph = lf_bar_graph(_data_set=[list(buffer[band][speed].values())], _xaxis_name="Stations",
                     _yaxis_name="No.of video stalls",
                     _xaxis_categories=range(1,sta_cnt+1,step), _label=["buffer"], _xticks_font=8,
                     _graph_image_name=f"{band.replace('/','-')}-Stations-Emulation-rate-{label.replace(' ','-')}-per-Station",
                     _color=['forestgreen', 'darkorange', 'blueviolet'], _color_edge='black', _figsize=(18, 6),
                     _grp_title="No.of stalls for each clients", _xaxis_step = step,_show_bar_value=True, _text_font=8, _text_rotation=45)
            grph_commn(graph_ob = graph,report_ob = report)
            report.set_obj_html(_obj_title="", _obj=f"The below graph shows the number of connected stations on the X-axis and "
                                                    f"the average throughput of each station on the Y-axis, with a traffic duration "
                                                    f"of {duration} minutes when the threshold is {threshold}% ")
            report.set_graph_title(f"Throughput for {band}-Stations of speed {label} per Station")
            report.build_graph_title()
            report.build_objective()
            graph = lf_bar_graph(_data_set=[avg_rxrate[band][speed]], _xaxis_name="Stations",
                     _yaxis_name="Throughput (Mbps)",_xaxis_categories=range(1, sta_cnt+1,step),
                     _label=["rx-rate"],_xticks_font=8,_figsize=(18, 6),
                     _graph_image_name=f"Rx-rate-{band.replace('/','-')}-Stations-Max-speed-{label.replace(' ','-')}-per-Station",
                     _color=['blueviolet', 'darkorange', 'forestgreen'], _color_edge='black',
                     _grp_title="Throughput for each clients", _xaxis_step=step, _show_bar_value=True,_text_font=8,_text_rotation=45)
            grph_commn(graph_ob = graph,report_ob = report)

    report.set_table_title("Input Setup Information")
    report.build_table_title()
    report.test_setup_table(test_setup_data =input_setup_info, value = "Information")
    #report.build_custom()
    html_file = report.write_html()
    print("returned file {}".format(html_file))
    print(html_file)
    report.write_pdf()


def main():
    parser = argparse.ArgumentParser(description="Netgear Video streaming Test Script \n"
                                     "sudo python3 video_stream.py --mgr localhost --mgr_port 8080 --upstream_port eth1 "
                                     "--num_stations 40 --security open --ssid testchannel --passwd [BLANK] "
                                     "--url 192.168.208.92/video.txt --emulation_rate 1 2 --bands_with_radio 5G-wiphy0 2.4G-wiphy1 5G/2.4G-wiphy0,wiphy1"
                                     " --threshold 70 --file_size 30Mb --duration 2 --ap_name WAC505 --buffer_interval 5 --expected_stalls 5")
    optional = parser.add_argument_group('optional arguments')
    required = parser.add_argument_group('required arguments')
    optional.add_argument('--mgr', help='hostname for where LANforge GUI is running', default='localhost')
    optional.add_argument('--mgr_port', help='port LANforge GUI HTTP service is running on', default=8080)
    optional.add_argument('--upstream_port', help='non-station port that generates traffic: eg: eth1', default='eth1')
    optional.add_argument('--num_stations', type=int, help='number of stations to create', default=40)
    required.add_argument('--security', help='WiFi Security protocol: {open|wep|wpa2|wpa3')
    required.add_argument('--ssid', help='WiFi SSID for script object to associate to')
    required.add_argument('--passwd', help='WiFi passphrase/password/key')
    required.add_argument('--url', type=str, help='url on eth1 to test HTTP')
    optional.add_argument('--target_per_ten', help='number of request per 10 minutes', default=100)
    optional.add_argument('-emu','--emulation_rate', nargs="+", help='(Example : --emulation_rate 6.5 4k "HD 720p")  \n-------Video Emulation Rate-------\n'
                         '"Disbaled" = 0 bps  ||  "216 p4" = 300 Kbps  ||  "240 p4" = 500 Kbps  ||  "SD 360p" = 700 Kpbs  || '
                         ' "SD 480p" = 1.1 Mbps  || "HD 720p" = 2.5 Mbps  ||  "HD 1080p" = 5 Mbps  ||  "4K" = 20 Mbps',
                        default=['HD 720p', '4K', '3', '4', '5'])
    required.add_argument('-b_r','--bands_with_radio', nargs="+",
                        help='eg:5G-wiphy0 2.4G-wiphy1 5G/2.4G-wiphy0,wiphy1 -- for Both provide 5G '
                             'radio and 2.4G radio')
    optional.add_argument('--file_size',type=str, help='specify the size of file you want to download', default='30Mb')
    optional.add_argument('--duration', type=str, help='mention the time interval you want to check the '
                                                     'values for cx in minutes', default=2)
    optional.add_argument('--ap_name', type=str, help="mention th AP name ", default="Access Point")
    optional.add_argument( '-bi','--buffer_interval', type=int, help='buffer size', default=5)
    optional.add_argument( '--threshold', type=int, help='threshold in percentage', default=70)
    optional.add_argument( '-s','--expected_stalls', type=int, help='expected no.of stalls per station', default=6)

    args = parser.parse_args()
    #ap = AP_automate(args.ap_ip, args.user, args.pswd) #needed when automate the AP
    print(args.bands_with_radio)
    band_rad = [b.split("-") for b in args.bands_with_radio]
    vs_bands, vs_radio = [],[]
    list(map(lambda b : (vs_bands.append(b[0].title()),vs_radio.append(b[1])),band_rad))
    band_dict = []
    avg_rxrate_bands = {}
    print(f"Video Emulation rate {args.emulation_rate}")

    band_type = ['5G','2.4G','5G/2.4G']
    num = lambda ars : ars if ars % 2 == 0 else ars + 1
    max_speed = []
    for i in args.emulation_rate:
        if i in ["Disabled", "disabled" , "DISABLED"]:
            max_speed.append(0)
        elif i in ["216 p4" , "216 P4"]:
            max_speed.append(300e-3)
        elif i in ["240 p4" , "240 P4"]:
            max_speed.append(500e-3)
        elif i in ["SD 360p" , "sd 360p" , "SD 360P" , "sd 360P"]:
            max_speed.append(700e-3)
        elif i in ["SD 480p" , "sd 480p" , "SD 480P" , "sd 480P"]:
            max_speed.append(1.1)
        elif i in ["HD 720p" , "hd 720p" , "HD 720P" , "hd 720P"]:
            max_speed.append(2.5)
        elif i in ["HD 1080p" , "hd 1080p" , "HD 1080P" , "hd 1080P"]:
            max_speed.append(5)
        elif i in ["4K" , "4k"]:
            max_speed.append(20)
        else:
            try:
                max_speed.append(float(i))
            except Exception as e:
                print(f"###{e}###\n provide correct video emulation rate with help command \n user's value: {args.emulation_rate}")
                exit(1)

    print("video emulation rate in Mbps", max_speed)
    test_time = datetime.datetime.now().strftime("%b %d %H:%M:%S")
    print("Test started at ", test_time)

    for bands in vs_bands:
        speed_dict = {}
        avg_rxrate_speed = {}
        print("bands--",bands)
        num_stas = args.num_stations
        if bands == '5G':
            radio = [vs_radio[vs_bands.index(bands)]]
        elif bands == '2.4G':
            radio = [vs_radio[vs_bands.index(bands)]]
        elif bands == '5G/2.4G':
            num_stas = num(args.num_stations) // 2
            radio = vs_radio[vs_bands.index(bands)].split(",")
        if bands not in band_type:
            raise ValueError("--bands_with_radio should be like 5G-wiphy0 2.4G-wiphy1 5G/2.4G-wiphy0,wiphy1")
        for speed in max_speed:
            speed = int(speed * 1000000) #from mbps convert to bps
            http = VideoStreaming(lfclient_host=args.mgr, lfclient_port=args.mgr_port,
                                    upstream=args.upstream_port, num_sta=num_stas,
                                    security=args.security,
                                    ssid=args.ssid, password=args.passwd,
                                    url=args.url, target_per_ten=args.target_per_ten, max_speed=speed,
                                    file_size=args.file_size,bands=bands, _debug_on=False, _radio = radio)
            http.postcleanup()

            # calculate threshold
            number = speed
            print('speed-----' ,number,f"{args.threshold}% percent of given speed------",
                  int((args.threshold/100) * float(number)))
            threshold = int((args.threshold/100) * float(number))
            print("threshold is-----", threshold)

            http.file_create()
            #http.set_values()
            http.precleanup()

            #time.sleep(6)
            http.build() #build stations and traffic
            time.sleep(2)
            http.start() # start running
            time.sleep(20)
            layer4connections = []
            if num_stas > 1:
                for i in http.json_get('/layer4/')['endpoint']:
                    layer4connections.append(list(i.keys())[0])
            elif num_stas == 1:
                layer4connections.append(http.json_get('/layer4/')['endpoint']['name'])
            print("layer4connections",layer4connections)

            rx_rate = http.monitor(duration_sec=float(args.duration) * 60, # converting to seconds
                                   monitor_interval=1,
                                   col_names=['rx rate'],
                                   created_cx=layer4connections,
                                   iterations=0)
            #rx_rate = random.sample(range(0,1000000),int((float(args.duration) * 60) * num_stas)) #sample data
            while "" in rx_rate:
                rx_rate.pop(rx_rate.index(""))
            # divide the list into number of endpoints, Yield successive n-sized chunks from l.
            def divide_chunks(l, n):
                # looping till length l
                for i in range(0, len(l), n):
                    if i+n < len(rx_rate):
                        yield l[i:i + n]
                    else:
                        extra = (i+n) - len(rx_rate)
                        yield l[i:] + [0]* extra

            # How many elements each list should have
            if bands == "5G/2.4G":
                n = num_stas * 2
            else:
                n = num_stas

            divided_list= list(divide_chunks(rx_rate, n))
            print(divided_list,"\nno.of times rx-rate calculated",len(divided_list))

            #creating number of endpoints name  list
            num_sta = n
            endp_name_lst = []
            for i in range(0, num_sta):
                var = "endp" + str(i)
                endp_name_lst.append(var)

            print(endp_name_lst)
            #dictionary of name list
            endp_dict = dict.fromkeys(endp_name_lst)
            print(endp_dict)
            for i in endp_dict:
                endp_dict[i] = []
            #try:
            for i in divided_list:
                for index, key in enumerate(endp_dict):
                        endp_dict[key].append(i[index])
            #except Exception as e:

            print("endp_dict----",endp_dict)

            final_data = dict.fromkeys(endp_dict.keys())

            #sample data
            #{'endp0': [1005140, 1007393, 1005140, 1007393, 1005140, 1007393], 'endp1': [1, 1, 1, 1, 1, 1],
            #'endp2': [1005140, 1005154, 1005140, 1005154, 1005140, 1005154],'endp3': [197, 997, 997, 997, 997, 997], 'endp4': [88, 1005140, 1005388, 1005140, 1005388, 1005140],
            #'endp5':[258,1004315,1005258,1004315,1005258,1004315],'endp6':[212,1004132,1005212,1004132,1005212, 1004132],
            # 'endp7': [157, 1005212, 1005257, 1005212, 1005257, 1005212],
            # 'endp8': [1005015, 1005257, 1005015, 1005257, 1005015, 1005257],
            # 'endp9': [1004524, 1005015, 1004524, 1005015, 1004524, 1005015]}
            loop = True
            sta_avg = []
            for k in endp_dict.keys():
                sta_avg.append(float(f"{((sum(endp_dict[k])/1000000)/len(endp_dict[k])):.2f}"))
                iter,flag = 0,0
                while loop:
                    flg = 0
                    if iter >= len(endp_dict[k]):
                        break
                    try:
                        #threshold = 700000 #for example
                        if min(endp_dict[k]) > threshold:
                            break
                        if min(endp_dict[k][iter:iter + args.buffer_interval]) > threshold:
                            iter += args.buffer_interval
                        if endp_dict[k][iter] < threshold :
                            iter += 1
                            tmp = endp_dict[k][iter:iter + (args.buffer_interval - 1)]
                            if len(tmp) < (args.buffer_interval - 1):
                                break
                            for j in tmp:
                                iter += 1
                                if j < threshold:
                                    flg += 1
                                else:
                                    break
                            if flg == (args.buffer_interval - 1):    # add buffer
                                flag += 1
                        else:
                            iter += 1
                    except IndexError as e:
                        print(e)
                        break
                final_data[k] = flag
            print("number of buffers in all endpoints",final_data)
            speed_dict[speed] = final_data
            avg_rxrate_speed[speed] = sta_avg
        print(speed_dict,"\navarage:-",avg_rxrate_speed)
        band_dict.append(speed_dict)
        avg_rxrate_bands[bands] = avg_rxrate_speed
    print(band_dict,"\n avarage-with-bands",avg_rxrate_bands)
    test_end = datetime.datetime.now().strftime("%b %d %H:%M:%S")
    print("Test ended at ", test_end)
    http.postcleanup()
    test_setup_info = {
        "AP Name": args.ap_name,
        "SSID": args.ssid,
        "No.of stations": args.num_stations,
        "Buffer interval": args.buffer_interval,
        "File size": args.file_size,
        "Expected stalls" : args.expected_stalls,
        "Total Test Duration": datetime.datetime.strptime(test_end, '%b %d %H:%M:%S') - datetime.datetime.strptime(test_time, '%b %d %H:%M:%S')
    }

    input_setup_info = {
        "Contact": "support@candelatech.com"
    }
    report(band_dict,test_setup_info,input_setup_info,args.threshold,args.duration,vs_bands,
           expt_stal = args.expected_stalls, avg_rxrate = avg_rxrate_bands,sta_cnt=args.num_stations,emu_rate = args.emulation_rate)


if __name__ == '__main__':
    main()
    '''band_dict = [{'1000000': {'endp0': 23, 'endp1': 23, 'endp2': 23, 'endp3': 23, 'endp4': 23}},
                {'1000000': {'endp0': 23, 'endp1': 23, 'endp2': 23, 'endp3': 23, 'endp4': 23}},
                {'1000000': {'endp0': 23, 'endp1': 23, 'endp2': 23, 'endp3': 23, 'endp4': 23}}]
    test_setup_info = {
        "AP Name": "access point",
        "SSID": "two",
        "Test Duration": "three"
    }
    input_setup_info = {
        "Contact": "support@candelatech.com"
    }
    report(band_dict, test_setup_info, input_setup_info,70,5,['5G','2.4G','Both'],expt_stal = 6)'''
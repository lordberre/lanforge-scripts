#!/usr/bin/env python3
import re
import time
import pprint
from pprint import pprint
import os
import datetime
import base64
import xlsxwriter
import pandas as pd
import requests
import ast
import csv

# LFData class actions:
# - Methods to collect data/store data (use from monitor instance) - used by Profile class.
    # - file open/save
    # - save row (rolling) - to CSV (standard)
    # - headers
    # - file to data-storage-type conversion and vice versa  (e.g. dataframe (or datatable) to file type and vice versa)
    # - other common util methods related to immediate data storage
    # - include compression method
    # - monitoring truncates every 5 mins and sends to report? --- need clarification. truncate file and rewrite to same file? 
    # - large data collection use NFS share to NAS. 
# Websocket class actions:
    #reading data from websockets

class LFDataCollection:
    def __init__(self, local_realm, debug=False):
        self.parent_realm = local_realm
        self.halt_on_error = False
        self.exit_on_error = False
        self.debug = debug or local_realm.debug

    def json_get(self, _req_url, debug_=False):
        return self.parent_realm.json_get(_req_url, debug_=False)
    
    
    def monitor_interval(self,):

        #instantiate csv file here, add specified column headers 
        csvfile=open(str(report_file),'w')
        csvwriter = csv.writer(csvfile,delimiter=",")      
        csvwriter.writerow(header_row)

        #wait 10 seconds to get proper port data
        time.sleep(10)
        start_time = datetime.datetime.now()
        end_time = start_time + datetime.timedelta(seconds=duration_sec)
        while datetime.datetime.now() < end_time:
            t = datetime.datetime.now()
            timestamp= t.strftime("%m/%d/%Y %I:%M:%S")
            t_to_millisec_epoch= int(self.get_milliseconds(t))
            time_elapsed=int(self.get_seconds(t))-int(self.get_seconds(start_time))
        
            layer_3_response = self.json_get("/endp/%s?fields=%s" % (created_cx, layer3_fields))
            if port_mgr_cols is not None:
                port_mgr_response=self.json_get("/port/1/1/%s?fields=%s" % (sta_list, port_mgr_fields))
            #get info from port manager with list of values from cx_a_side_list
            if "endpoint" not in layer_3_response or layer_3_response is None:
                print(layer_3_response)
                raise ValueError("Cannot find columns requested to be searched. Exiting script, please retry.")
            if debug:
                    print("Json layer_3_response from LANforge... " + str(layer_3_response))
            if port_mgr_cols is not None:
                if "interfaces" not in port_mgr_response or port_mgr_response is None:
                    print(port_mgr_response)
                    raise ValueError("Cannot find columns requested to be searched. Exiting script, please retry.")
            if debug:
                    print("Json port_mgr_response from LANforge... " + str(port_mgr_response))
         
            temp_list=[]
            for endpoint in layer_3_response["endpoint"]:
                if debug:
                    print("Current endpoint values list... ")
                    print(list(endpoint.values())[0])
                temp_endp_values=list(endpoint.values())[0] #dict
                temp_list.extend([timestamp,t_to_millisec_epoch,time_elapsed]) 
                current_sta = temp_endp_values['name']
                merge={}
                if port_mgr_cols is not None:
                    for sta_name in sta_list_edit:
                        if sta_name in current_sta:
                            for interface in port_mgr_response["interfaces"]:
                                if sta_name in list(interface.keys())[0]:
                                    merge=temp_endp_values.copy()
                                    #rename keys (separate port mgr 'rx bytes' from layer3 'rx bytes')
                                    port_mgr_values_dict =list(interface.values())[0]
                                    renamed_port_cols={}
                                    for key in port_mgr_values_dict.keys():
                                        renamed_port_cols['port mgr - ' +key]=port_mgr_values_dict[key]
                                    merge.update(renamed_port_cols)
                for name in header_row[3:-3]:
                    temp_list.append(merge[name])
                csvwriter.writerow(temp_list)
                temp_list.clear()
            new_cx_rx_values = self.__get_rx_values()
            if debug:
                print(old_cx_rx_values, new_cx_rx_values)
                print("\n-----------------------------------")
                print(t)
                print("-----------------------------------\n")
            expected_passes += 1
            if self.__compare_vals(old_cx_rx_values, new_cx_rx_values):
                passes += 1
            else:
                self.fail("FAIL: Not all stations increased traffic")
                self.exit_fail()
            old_cx_rx_values = new_cx_rx_values
            time.sleep(monitor_interval_ms)
        csvfile.close()



#class WebSocket():
     
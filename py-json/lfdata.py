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
    
    def check_json_validity(self, keyword=None, json_response=None):
        if json_response is None:
            raise ValueError("Cannot find columns requested to be searched in port manager. Exiting script, please retry.")
        if keyword is not None and keyword not in json_response:
            raise ValueError("Cannot find proper information from json. Please check your json request. Exiting script, please retry.")
    #------------------------------from LFCLiBase (below) ----------------------------


    def get_milliseconds(self,
                         timestamp):
        return (timestamp - datetime.datetime(1970,1,1)).total_seconds()*1000
    def get_seconds(self,
                    timestamp):
        return (timestamp - datetime.datetime(1970,1,1)).total_seconds()


    #------------------------------from Realm for Layer 3 loop (below) ----------------------------

    def __get_rx_values(self):
        cx_list = self.json_get("endp?fields=name,rx+bytes")
        if self.debug:
            print(self.created_cx.values())
            print("==============\n", cx_list, "\n==============")
        cx_rx_map = {}
        for cx_name in cx_list['endpoint']:
            if cx_name != 'uri' and cx_name != 'handler':
                for item, value in cx_name.items():
                    for value_name, value_rx in value.items():
                        if value_name == 'rx bytes' and item in self.created_cx.values():
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

            if passes == expected_passes:
                return True
            else:
                return False
        else:
            return False


    #------------------------------------------------------------------


    #only for layer 3 tests at the moment
    def monitor_interval(self,report_file_=None,header_row_=None,sta_list_=None,created_cx_=None,layer3_fields_=None,port_mgr_fields_=None,duration_sec_=None, monitor_interval_ms_=None):
        self.created_cx=created_cx_
        passes = 0
        expected_passes = 0
        #old_cx_rx_values = self.__get_rx_values()

        #instantiate csv file here, add specified column headers 
        csvfile=open(str(report_file_),'w')
        csvwriter = csv.writer(csvfile,delimiter=",")      
        csvwriter.writerow(header_row_)

        #wait 10 seconds to get IPs
        time.sleep(10)
        start_time = datetime.datetime.now()
        end_time = start_time + datetime.timedelta(seconds=duration_sec_)

        while datetime.datetime.now() < end_time:

            #time calculations for while loop and writing to csv
            t = datetime.datetime.now()
            timestamp= t.strftime("%m/%d/%Y %I:%M:%S")
            t_to_millisec_epoch= int(self.get_milliseconds(t))
            time_elapsed=int(self.get_seconds(t))-int(self.get_seconds(start_time))
        
            #get responses from json
            layer_3_response = self.json_get("/endp/%s?fields=%s" % (created_cx_, layer3_fields_),debug_=self.debug)
            if port_mgr_fields_ is not None:
                port_mgr_response=self.json_get("/port/1/1/%s?fields=%s" % (sta_list_, port_mgr_fields_), debug_=self.debug)
                
            #check json response validity
            self.check_json_validity(keyword="endpoint",json_response=layer_3_response)
            self.check_json_validity(keyword="interfaces",json_response=port_mgr_response)
               
            #dict manipulation
            temp_list=[]
            for endpoint in layer_3_response["endpoint"]:
                if self.debug:
                    print("Current endpoint values list... ")
                    print(list(endpoint.values())[0])
                temp_endp_values=list(endpoint.values())[0] #dict
                temp_list.extend([timestamp,t_to_millisec_epoch,time_elapsed]) 
                current_sta = temp_endp_values['name']
                merge={}
                if port_mgr_fields_ is not None:
                    for sta_name in sta_list_:
                        if sta_name in current_sta:
                            for interface in port_mgr_response["interfaces"]:
                                if sta_name in list(interface.keys())[0]:
                                    merge=temp_endp_values.copy()
    
                                    port_mgr_values_dict =list(interface.values())[0]
                                    renamed_port_cols={}
                                    for key in port_mgr_values_dict.keys():
                                        renamed_port_cols['port mgr - ' +key]=port_mgr_values_dict[key]
                                    merge.update(renamed_port_cols)
                for name in header_row_[3:-3]:
                    temp_list.append(merge[name])
                csvwriter.writerow(temp_list)
            #     temp_list.clear()
            # new_cx_rx_values = self.__get_rx_values()
            # if self.debug:
            #     print(old_cx_rx_values, new_cx_rx_values)
            #     print("\n-----------------------------------")
            #     print(t)
            #     print("-----------------------------------\n")
            # expected_passes += 1
            # if not self.__compare_vals(old_cx_rx_values, new_cx_rx_values):
            #    exit(1)
            # old_cx_rx_values = new_cx_rx_values
            time.sleep(monitor_interval_ms_)
        csvfile.close()



#class WebSocket():
     
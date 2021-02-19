#!/usr/bin/env python3
import re
import time
import pprint
from pprint import pprint
from LANforge import LFRequest
from LANforge import LFUtils
from LANforge import lfcli_base
from LANforge.lfcli_base import LFCliBase
from LANforge import add_monitor
from LANforge.add_monitor import *
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

class LFDataCollection(LFCliBase):
    def __init__(self,
                 lfclient_host="localhost",
                 lfclient_port=8080,
                 debug_=False,
                 halt_on_error_=False, # remove me
                 _exit_on_error=False,
                 _exit_on_fail=False,
                 _proxy_str=None,
                 _capture_signal_list=[]):
        super().__init__(_lfjson_host=lfclient_host,
                         _lfjson_port=lfclient_port,
                         _debug=debug_,
                         _halt_on_error=halt_on_error_,
                         _exit_on_error=_exit_on_error,
                         _exit_on_fail=_exit_on_fail,
                         _proxy_str=_proxy_str,
                         _capture_signal_list=_capture_signal_list)
        self.debug = debug_
    



#class WebSocket():
     
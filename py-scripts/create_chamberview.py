#!/usr/bin/env python3

"""
Note: Script for creating a chamberview scenario.
    Run this script to set/create a chamber view scenario.
    ex. on how to run this script:
    create_chamberview.py -m "192.168.200.15" -o "8080" -cs "scenario_name" -l 1 -p "STA-AC" -n 10 -d "DUT_NAME"
        -dr "Radio-1" -t "tcp-dl-6m-vi" -r "wiphy0" -l 2 -p "upstream" -n 1  -d "DUT_NAME" -dr "Radio-1" -t "UDP" -r
        "eth1"
"""

import sys
import os
import argparse
import time

if sys.version_info[0] != 3:
    print("This script requires Python 3")
    exit(1)

if 'py-json' not in sys.path:
    sys.path.append(os.path.join(os.path.abspath('..'), 'py-json'))

from cv_commands import chamberview as cv

def main():

    parser = argparse.ArgumentParser(
        description="""use build_chamberview to create a lanforge chamberview scenario
        create_chamberview.py -m "localhost" -o "8080" -cs "scenario_updated" -l 1 -p "STA-AC" -n 7 -d "DUT_Name" 
        -dr "Radio-1" -t "tcp-dl-6m-vi" -r "wiphy0" -l 2 -p "upstream" -n 1  -d "ASUS" -dr "Radio-1" -t "UDP" -r "eth1"
        """)
    parser.add_argument("-m", "--lfmgr", type=str,
                        help="address of the LANforge GUI machine (localhost is default)")
    parser.add_argument("-o", "--port", type=int,
                        help="IP Port the LANforge GUI is listening on (8080 is default)")
    parser.add_argument("-cs", "--create_scenario", "--create_lf_scenario", type=str,
                        help="name of scenario to be created")
    parser.add_argument("-l", "--line", action='append', nargs='+', type=str, required=True,
                        help="line number")
    parser.add_argument("-p", "--profile", action='append', nargs='+', type=str, required=True,
                        help="name of profile")
    parser.add_argument("-n", "--no_stations", action='append', nargs='+', type=str, required=True,
                        help="Number of stations")
    parser.add_argument("-d", "--dut", "--DUT", action='append', nargs='+', type=str, required=True,
                        help="Name of the DUT")
    parser.add_argument("-dr", "--dr", "--dut_radio", action='append', nargs='+', type=str, required=True,
                        help="Select DUT Radio ex. \"Radio-1\", \"Radio-2\"")
    parser.add_argument("-t", "--t", "--traffic", action='append', nargs='+', type=str, required=True,
                        help="Select traffic ex. \"tcp-dl-6m-vi\"")
    parser.add_argument("-r", "--r", "--radio", action='append', nargs='+', type=str, required=True,
                        help="Select traffic ex. \"wiphy0\"")


    args = parser.parse_args()
    if args.lfmgr is not None:
        lfjson_host = args.lfmgr
    if args.port is not None:
        lfjson_port = args.port

    createCV = cv(lfjson_host, lfjson_port);  # Create a object

    try:
        scenario_name = args.create_scenario
        line = args.line
        profile_name = args.profile
        create_stations = args.no_stations
        dut_name = args.dut
        dut_radio = args.dr
        traffic_type = args.t
        radio = args.r
    except:
        print("Wrong arguments entered")
        exit(1)

    for i in range(len(line)):

        createCV.manage_cv_scenario(scenario_name, profile_name[i][0], create_stations[i][0], dut_name[i][0],
                                    dut_radio[i][0], traffic_type[i][0], radio[i][0]); #To manage scenario
        time.sleep(1)


    createCV.sync_cv() #chamberview sync
    time.sleep(2)
    createCV.apply_cv_scenario(scenario_name) #Apply scenario
    time.sleep(2)
    createCV.sync_cv()
    time.sleep(2)
    createCV.apply_cv_scenario(scenario_name)  # Apply scenario

    time.sleep(2)
    createCV.build_cv_scenario() #build scenario
    print("End")


if __name__ == "__main__":
    main()

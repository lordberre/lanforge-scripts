"""
use to run WiFi Capacity test.
"""
import sys
import os
import argparse
import time
import json
from os import path

if sys.version_info[0] != 3:
    print("This script requires Python 3")
    exit(1)

if 'py-json' not in sys.path:
    sys.path.append(os.path.join(os.path.abspath('..'), 'py-json'))

from cv_test_manager import cv_test as cvtest
from chamberview import chamberview as cv
from cvtest_reports import lanforge_reports as lf_rpt

def main():
    parser = argparse.ArgumentParser(description="""use run_test to run tests""")
    parser.add_argument("-m", "--lfmgr", type=str,
                        help="address of the LANforge GUI machine (localhost is default)")
    parser.add_argument("-o", "--port", type=int,
                        help="IP Port the LANforge GUI is listening on (8080 is default)")
    parser.add_argument("-t", "--test_name", type=str,
                        help="name of test to be run ex. \"WiFi Capacity\"")
    parser.add_argument("-i", "--instance_name", type=str, required=True,
                        help="name of test instance (by default: test_ref)")
    parser.add_argument("-c", "--config_name", type=str, required=True,
                        help="Test config name (by default: DEFAULT)")
    parser.add_argument("-r", "--pull_report", type=str, required=True,
                        help="pull reports from lanforge (by default: y)")
    parser.add_argument("-b", "--batch_size", type=str, required=True,
                        help="config batch size (by default: 1)")
    parser.add_argument("-l", "--loop_iter", type=str, required=True,
                        help="config loop iter (by default: 1)")
    parser.add_argument("-p", "--protocol", type=str, required=True,
                        help="config protocol (by default: TCP-IPv4)")
    parser.add_argument("-d", "--duration", type=str, required=True,
                        help="config duration (by default: 5000)")

    args = parser.parse_args()

    # This is user config.
    config_name = "config_wifi_capacity"  # Test Config Name (new)
    instance_name = "test_ref"  # Test Instance name
    test_name = "WiFi Capacity"  # Test name
    lf_host = "192.168.200.21"
    lf_hostport = "8080"
    pull_report = "y"
    # Test Config
    batch_size = "1"
    loop_iter = "1"
    protocol = "TCP-IPv4"
    duration = " 5000"

    if args.lfmgr is not None:
        lf_host = args.lfmgr
    if args.port is not None:
        lf_hostport = args.port
    if args.test_name is not None:
        test_name = args.test_name
    if args.instance_name is not None:
        instance_name = args.instance_name
    if args.config_name is not None:
        config_name = args.config_name
    if args.batch_size is not None:
        batch_size = args.batch_size
    if  args.loop_iter is not  None:
        loop_iter = args.loop_iter
    if args.protocol is not None:
        protocol = args.protocol
    if args.duration is not None:
        duration = args.duration
    if args.pull_report is not None:
        pull_report = args.pull_report



    # Test related settings
    dict = {"batch_size": "batch_size:" + " " + str(batch_size),
            "loop_iter": "loop_iter:" + " " + str(loop_iter),
            "protocol": "protocol:" + " " + str(protocol),
            "duration": "duration:" + " " + str(duration)}

    run_test = cvtest(lf_host, lf_hostport)
    createCV = cv(lf_host, lf_hostport);  # Create a object

    port_list = []

    response = run_test.check_ports();
    port_size = json.dumps(len(response["interfaces"]))

    for i in range(int(port_size)):
        list_val = json.dumps(response["interfaces"][i])
        list_val_ = json.loads(list_val).keys()
        list_val_ = str(list_val_).replace("dict_keys(['", "")
        list_val_ = str(list_val_).replace("'])", "")
        if (list_val_.__contains__("sta") or list_val_.__contains__("eth1")):
            port_list.append(list_val_)

    for i in range(len(port_list)):
        add_port = "sel_port-" + str(i) + ":" + " " + port_list[i]
        run_test.create_test_config(config_name,"Wifi-Capacity-",add_port)
        time.sleep(0.2)

    for key, value in dict.items():
        run_test.create_test_config(config_name,"Wifi-Capacity-",value)
        time.sleep(0.2)

    run_test.create_test(test_name, instance_name)
    time.sleep(5)
    createCV.sync_cv()
    time.sleep(2)
    run_test.load_test_config(config_name, instance_name)
    time.sleep(2)
    run_test.auto_save_report(instance_name)
    time.sleep(4)
    run_test.start_test(instance_name)

    while (True):
        check = run_test.get_report_location(instance_name)
        location = json.dumps(check[0]["LAST"]["response"])
        print("WiFi Capacity Test Running...")
        if location != "\"Report Location:::\"":
            location = location.replace("Report Location:::", "")
            print(location)
            time.sleep(1)
            run_test.close_instance(instance_name)
            time.sleep(1)
            run_test.cancel_instance(instance_name)
            time.sleep(4)
            location = location.strip("\"")
            report = lf_rpt()
            print(location)
            if (pull_report == "yes" ) or (pull_report == "y") or (pull_report == "Y"):
                report.pull_reports(hostname=lf_host, username="lanforge", password="lanforge",
                                    report_location=location)
            break


if __name__ == "__main__":
    main()

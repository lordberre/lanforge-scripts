#!/bin/bash
#This bash script aims to automate the test process of all Candela Technologies's test_* scripts in the lanforge-scripts directory. The script can be run 2 ways and may include (via user input) the "start_num" and "stop_num" variables to select which tests should be run.
# OPTION ONE: ./test_all_scripts.sh : this command runs all the scripts in the array "testCommands"
# OPTION TWO: ./test_all_scripts.sh 4 5 :  this command runs py-script commands (in testCommands array) that include the py-script options beginning with 4 and 5 (inclusive) in case function ret_case_num.
#Variables
NUM_STA=4
SSID_USED="jedway-wpa2-x2048-5-3"
PASSWD_USED="jedway-wpa2-x2048-5-3"
RADIO_USED="wiphy1"
SECURITY="wpa2"
COL_NAMES="name,tx_bytes,rx_bytes,dropped"

START_NUM=0
CURR_TEST_NUM=0
CURR_TEST_NAME="BLANK"
STOP_NUM=9

DATA_DIR="${TEST_DIR}"
REPORT_DIR="/home/lanforge/html-reports"

#set -vex

#Test array
testCommands=(
    "./example_security_connection.py --num_stations $NUM_STA --ssid jedway-r8000-36 --passwd jedway-r8000-36 --radio $RADIO_USED --security wpa"
    "./example_security_connection.py --num_stations $NUM_STA --ssid $SSID_USED --passwd $SSID_USED --radio $RADIO_USED --security wpa2"
    "./example_security_connection.py --num_stations $NUM_STA --ssid jedway-wep-48 --passwd jedway-wep-48 --radio $RADIO_USED --security wep"
    "./example_security_connection.py --num_stations $NUM_STA --ssid jedway-wpa3-1 --passwd jedway-wpa3-1 --radio $RADIO_USED --security wpa3"
    "./test_ipv4_connection.py --radio $RADIO_USED --num_stations $NUM_STA --ssid $SSID_USED --passwd $PASSWD_USED --security $SECURITY"
    "./test_generic.py --radio $RADIO_USED --ssid $SSID_USED --passwd $PASSWD_USED --num_stations $NUM_STA --type lfping --dest 10.40.0.1 --security $SECURITY"
    "./test_generic.py --radio $RADIO_USED --ssid $SSID_USED --passwd $PASSWD_USED --num_stations $NUM_STA --type speedtest --speedtest_min_up 20 --speedtest_min_dl 20 --speedtest_max_ping 150 --security $SECURITY"
    "./test_ipv4_l4_urls_per_ten.py --radio $RADIO_USED --num_stations $NUM_STA --security $SECURITY --ssid $SSID_USED --passwd $PASSWD_USED --num_tests 1 --requests_per_ten 600 --target_per_ten 600"
    "./test_ipv4_l4_wifi.py --radio $RADIO_USED --num_stations $NUM_STA --security $SECURITY --ssid $SSID_USED --passwd $PASSWD_USED --test_duration 15s"
    "./test_ipv4_l4.py --radio $RADIO_USED --num_stations 4 --security $SECURITY --ssid $SSID_USED --passwd $PASSWD_USED --test_duration 15s"
    "./test_ipv4_variable_time.py --radio $RADIO_USED --ssid $SSID_USED --passwd $PASSWD_USED --security $SECURITY --test_duration 15s --output_format excel --col_names $COL_NAMES"
    "./test_ipv4_variable_time.py --radio $RADIO_USED --ssid $SSID_USED --passwd $PASSWD_USED --security $SECURITY --test_duration 15s --output_format csv --col_names $COL_NAMES"
    #"./create_bridge.py --radio wiphy1 --upstream_port eth1 --target_device sta0000"NAME
    #"./create_l3.py --radio wiphy1 --ssid $SSID_USED --passwd $PASSWD_USED --security $SECURITY"
    #"./create_l4.py --radio wiphy1 --ssid $SSID_USED --passwd $PASSWD_USED --security $SECURITY"
    #"./create_macvlan.py --radio wiphy1"
    #"./create_station.py --radio wiphy1 --ssid $SSID_USED --passwd $PASSWD_USED --security $SECURITY"
    #"./create_vap.py --radio wiphy1 --ssid $SSID_USED --passwd $PASSWD_USED --security $SECURITY"
)
declare -A name_to_num
name_to_num=(
    ["example_security_connection"]=1
    ["test_ipv4_connection"]=2
    ["test_generic"]=3
    ["test_ipv4_l4_urls_per_ten"]=4
    ["test_ipv4_l4_wifi"]=5
    ["test_ipv4_l4"]=6
    ["test_ipv4_variable_time"]=7
    ["create_bridge"]=8
    ["create_l3"]=9
    ["create_l4"]=10
    ["create_macvlan"]=10
    ["create_station"]=11
    ["create_vap"]=12
)

function blank_db() {
    echo "Loading blank scenario..." >>~/test_all_output_file.txt
    ./scenario.py --load BLANK >>~/test_all_output_file.txt
    #check_blank.py
}
function echo_print() {
    echo "Beginning $CURR_TEST_NAME test..." >>~/test_all_output_file.txt
}
results=()
detailedresults=()
NOW=$(date +"%Y-%m-%d-%H-%M")
NOW="${NOW/:/-}"
TEST_DIR="/home/lanforge/report-data/${NOW}"
mkdir "$TEST_DIR"
function run_test() {
    for i in "${testCommands[@]}"; do
        NAME=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1)
        CURR_TEST_NAME=${i%%.py*}
        CURR_TEST_NAME=${CURR_TEST_NAME#./*}
        CURR_TEST_NUM="${name_to_num[$CURR_TEST_NAME]}"

        if (( $CURR_TEST_NUM > $STOP_NUM )) || (( $STOP_NUM == $CURR_TEST_NUM )) && (( $STOP_NUM != 0 )); then
            exit 1
        fi
        echo ""
        echo "Test $CURR_TEST_NUM: $CURR_TEST_NAME"

        if (( $CURR_TEST_NUM > $START_NUM )) || (( $CURR_TEST_NUM == $START_NUM )); then
            echo_print
            echo "$i"
            $i > "${TEST_DIR}/${NAME}.txt" 2> "${TEST_DIR}/${NAME}_stderr.txt"
            retval=$?
            grep -i fail "${TEST_DIR}/${NAME}.txt" && retval=1
            chmod 664 "${TEST_DIR}/${NAME}.txt"
            if (( $retval == 0 )); then
                results+=("<tr><td>${CURR_TEST_NAME}</td><td class='scriptdetails'>${i}</td>
                          <td class='success'>Success</td>
                          <td><a href=\"${TEST_DIR}/${NAME}.txt\" target=\"_blank\">STDOUT</a></td>
                          <td></td></tr>")
            else
                results+=("<tr><td>${CURR_TEST_NAME}</td><td class='scriptdetails'>${i}</td>
                          <td class='failure'>Failure</td>
                          <td><a href=\"${TEST_DIR}/${NAME}.txt\" target=\"_blank\">STDOUT</a></td>
                          <td><a href=\"${TEST_DIR}/${NAME}_stderr.txt\" target=\"_blank\">STDERR</a></td></tr>")

            fi
        fi
    done
    echo $results
}
function check_args() {
    if [ ! -z $1 ]; then
        START_NUM=$1
    fi
    if [ ! -z $2 ]; then
        STOP_NUM=$2
    fi
}
function html_generator() {
    header="<html>
		<head>
		<title>Test All Scripts Results $NOW</title>
		<style>
		.success {
			background-color:green;
		}
		.failure {
			background-color:red;
		}
		table {
			border: 1px solid gray;
		}
		td {
			margin: 0;
			padding: 2px;
			font-family: 'Courier New',courier,sans-serif;
		}
		h1, h2, h3, h4 {
			font-family: 'Century Gothic',Arial,sans,sans-serif;
		}
		.scriptdetails {
			font-size: 10px;
		}
		</style>
		</head>
		<body>
		<h1>Test All Scripts Results</h1>
		<h4>$NOW</h4>
		<table border ='1'>
		"
    tail="</body>
		</html>"

    fname="/home/lanforge/html-reports/test_all_output_file-${NOW}.html"
    echo "$header"  >> $fname
    echo "${results[@]}"  >> $fname
    echo "</table>" >> $fname
    echo "$tail" >> $fname
}

#true >~/test_all_output_file.txt
check_args $1 $2
run_test
echo "${detailedresults}"
html_generator
#test generic and fileio are for macvlans

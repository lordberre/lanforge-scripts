#!/usr/bin/env python3
"""
Tele2 LANForge script.
NAME: test_wifiproblems_db.py

PURPOSE:
test_wifiproblems_db.py

Use './test_wifiproblems_db.py --help' to see command line usage and options
"""
import sys
import os
import importlib
import argparse
import logging
import time
import json
from time import sleep
from pprint import pprint
from datetime import datetime

# For GNURadio flow
from gnuradio import analog
from gnuradio import gr
from gnuradio.filter import firdes
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
import limesdr


if sys.version_info[0] != 3:
    print("This script requires Python 3")
    exit(1)

sys.path.append(os.path.join(os.path.abspath(__file__ + "../../../")))

LFUtils = importlib.import_module("py-json.LANforge.LFUtils")
realm = importlib.import_module("py-json.realm")
Realm = realm.Realm
lf_logger_config = importlib.import_module("py-scripts.lf_logger_config")

logger = logging.getLogger(__name__)

SERVICE_TYPES = {
    "slow-ds-stream": {
         "active": False
    },
    "medium-ds-stream": {
        "active": True,
        "bitrate_ds_min": 10000000,
        "bitrate_ds_max": 10000000,
        "bitrate_us_min": 56000,
        "bitrate_us_max": 56000
    },
    "high-ds-stream": {
        "active": False
    },
    "gamer": {
        "active": False
    },
    "tput": {
        "active": False
    }
}


class WiFiProblemsTest(Realm):
    def __init__(self,
                 host="localhost",
                 port=8008,
                 _debug_on=False,
                 _exit_on_error=False,
                 _exit_on_fail=False, attenuator=None, noise_generator=None):
        super().__init__(lfclient_host=host,
                         lfclient_port=port,
                         debug_=_debug_on),
        self.host = host
        self.port = port
        self.lanforge_db = 'qow-wifiproblems-v1'
        self.debug = _debug_on
        self.local_realm = realm.Realm(lfclient_host=self.host, lfclient_port=self.port)
        self.attenuator = attenuator
        self.noise_generator = noise_generator  # gnuradio_op_block_cls
        self.desired_services = []
        self.stations_with_endpoints = dict()
        self.configured_endpoints, self.configured_cx = [], []
        self.stations_with_services, self.stations_with_desired_services = [], []
        self.desired_cx = []
        self.all_wifi_stations = []
        self.uplink_port = "1.1.01"  # Normally eth1 in MobileStations
        self.excluded_stations = []  # Endpoints to exclude from disconnects/connects
        self.excluded_cx = ['hogger']

        # Config
        self.seconds_per_atten_step = 30  # If no noise generator is present
        self.seconds_per_noise_step = 60

    # Return dict with key(port) -> port data for all ports
    def get_ports(self):
        port_map = dict()
        ports = self.json_get('/port/list')
        if ports is None:
            raise("No data")
        for record in ports['interfaces']:
            for entry in record.values():
                urlEntry = entry['port'].replace('.', '/')
                port_data = self.json_get('/port/' + urlEntry)
                port_map[entry['port']] = port_data
        return port_map

    # Return dict with key(port) -> endpoint data for all ports
    def get_all_endpoints(self):
        endpoint_map = dict()
        endpoints = self.json_get('/endp/list')
        if endpoints is None:
            raise('No endpoint data')
        for record in endpoints['endpoint']:
            for alias, entry in record.items():
                port = '.'.join(entry['entity id'].split('.')[:3])
                endpoint = self.json_get('/endp/' + alias)
                endpoint_map[port] = endpoint
        return endpoint_map

    def get_clients_and_cx_for_service(self, service):
        return self.stations_with_desired_services, [x for x in self.configured_cx if service.lower() in x.lower()]

    def flip_uplink(self):
        print('Flipping uplink port: {} ..'.format(self.uplink_port))
        self.local_realm.admin_down(self.uplink_port)
        sleep(1)
        self.local_realm.admin_up(self.uplink_port)
    
    def disconnect_stations(self, ports=[]):
        self.refresh_configured_endpoints()
        for port, data in self.stations_with_endpoints.items():
            if port not in ports:
                continue
            if not data['interface']['down']:
                interface = data['interface']
                print('Taking station {}({}) with L3-endpoint: {} down...'.format(port, interface['alias'], interface['l3_endpoint']['name']))
                self.local_realm.admin_down(port)

    def connect_stations(self, ports=[]):
        self.refresh_configured_endpoints()
        for port, data in self.stations_with_endpoints.items():
            if port not in ports:
                continue
            if not data['interface']['down']:
                interface = data['interface']
                print('Taking station {}({}) with L3-endpoint: {} up...'.format(port, interface['alias'], interface['l3_endpoint']['name']))
                self.local_realm.admin_up(port)

    def start_endpoints(self, cx=None):
        if cx is None:
            cxs = self.desired_cx
        else:
            cxs = cx
        print("Starting these services: {}".format(cxs))
        for x in cxs:
            self.json_post("/cli-json/set_cx_state", {
                    "test_mgr": "default_tm",
                    "cx_name": x,
                    "cx_state": "RUNNING"
                }, debug_=self.debug)

    def stop_endpoints(self, cx=None):
        if cx is None:
            cxs = self.desired_cx
        else:
            cxs = cx 
        print("Stopping these services: {}".format(cxs))
        for x in cxs:
            self.json_post("/cli-json/set_cx_state", {
                    "test_mgr": "default_tm",
                    "cx_name": x,
                    "cx_state": "STOPPED"
                }, debug_=self.debug)
    
    def start_test_for_service(self, service):
        self.stop_endpoints(self.configured_cx)
        self.disconnect_stations(self.all_wifi_stations)
        service_clients, service_cx = self.get_clients_and_cx_for_service(service)
        if len(service_clients) == 0 or len(service_cx) == 0:
            logger.error("Missing client or CX for this service: {}. Data: {}, {}".format(service, service_clients, service_cx))
            raise(ValueError)
        self.connect_stations(service_clients)
        self.start_endpoints(service_cx)
        self.start_environment_traffic()

    def start_environment_traffic(self):
        print('[start_environment_traffic] Starting environment stations/traffic..')
        self.connect_stations(self.excluded_stations)
        self.start_endpoints(['hogger-stream-1', 'hogger-stream-2'])

    # Get a list of all stations running the provided "services"
    def get_stations_with_services(self, services=dict(), update_db=False):
        stations, active_stations, active_cx = [], [], []
        if update_db:
            self.create_clienttable()
        for service_name, service in services.items():
            for port, data in self.stations_with_endpoints.items():
                if 'l3_endpoint' not in data['interface'].keys():
                    continue  # No endpoint for this particular sta
                else:
                    cx = data['interface']['l3_endpoint']['name']
                    if service_name.lower() in cx.lower():
                        if service['active']:  # Add this station if it should have an active service
                            self.desired_services.append(service_name)
                            print('Storing {}({}) because it should be running {}'.format(port, data['interface']['device'], data['interface']['l3_endpoint']['name']))
                            active_stations.append(port)
                            active_cx.append(cx)
                    elif 'hogger' in cx.lower():
                        self.excluded_stations.append(port)

                        stations.append(port)
        self.stations_with_services = stations

        # These are the configured stations and endpoints we want to start/stop, based on the desired config from services dict
        self.stations_with_desired_services = active_stations
        self.desired_cx = list(set([e.rstrip('-B').rstrip('-A') for e in active_cx]))

    def refresh_configured_endpoints(self):
        self.get_stations_with_services(self.services, update_db=True)
        if len(self.stations_with_endpoints) == 0:
            logger.error("Found no stations matching services types: {}".format(self.services.keys()))
            return
        else:
            configured_endpoints = []
            for data in self.stations_with_endpoints.values():
                configured_endpoints.append(data['interface']['l3_endpoint']['name'])
            self.configured_endpoints = configured_endpoints
            self.configured_cx = list(set([e.rstrip('-B').rstrip('-A') for e in self.configured_endpoints]))
            
        return
                        

    # Update stations_with_endpoints dict with new data from API
    def create_clienttable(self):
        ports = self.get_ports()
        endpoints = self.get_all_endpoints()
        for port, data in ports.items():
            if data is None:
                continue
            if port in endpoints:
                self.stations_with_endpoints[port] = data
                self.stations_with_endpoints[port]['interface']['l3_endpoint'] = endpoints[port]['endpoint']
            if data['interface']['port type'] == 'WIFI-STA': # and data['interface']['alias'] not in self.excluded_stations:
                self.all_wifi_stations.append(port)

    
    def populate_all_tables(self):
        self.refresh_configured_endpoints()

    def start(self, services):
        self.services = services
        self.build()

        print("Waiting for clients to connect...")
        sleep(5)  # Temp
        # TODO:
        #if self.wait_for_ip(['sta0001'], ipv4=not self.ipv6, ipv6=self.ipv6, debug=self.debug):
        #    self._pass("All stations got IPs")
        #else:
        #    self._fail("Stations failed to get IPs")
        #    self.exit_fail()
        print("Done!")
        
    def stop(self):
        if self.noise_generator is not None:
            self.noise_generator.stop()
            self.noise_generator.wait()

    def cleanup(self):
        self.cx_profile.cleanup()
        if not self.use_existing_sta:
            self.station_profile.cleanup()
            LFUtils.wait_until_ports_disappear(base_url=self.lfclient_url, port_list=self.station_profile.station_names,
                                               debug=self.debug)

    # Loads a predefined lanforge database
    def build(self):
        data = {
            "name": "BLANK",
            "action": "overwrite",
            "clean_dut": "yes",
            "clean_chambers": "yes"
        }
        self.json_post("/cli-json/load", data)
        sleep(1)
        port_counter = 0
        attempts = 6
        while (attempts > 0) and (port_counter > 0):
            sleep(1)
            attempts -= 1
            print("looking for ports like vap+")
            port_list = self.localrealm.find_ports_like("vap+")
            alias_map = LFUtils.portListToAliasMap(port_list)
            port_counter = len(alias_map)

            port_list = self.localrealm.find_ports_like("sta+")
            alias_map = LFUtils.portListToAliasMap(port_list)
            port_counter += len(alias_map)
            if port_counter == 0:
                break

        if (port_counter != 0) and (attempts == 0):
            print("There appears to be a vAP in this database, quitting.")
            pprint(alias_map)
            exit(1)

        data = {
            "name": self.lanforge_db,
            "action": "overwrite",
            "clean_dut": "yes",
            "clean_chambers": "yes"
        }
        self.json_post("/cli-json/load", data)
        sleep(5)
        self._pass("Loaded scenario %s" % self.lanforge_db, True)
        return True


    def run(self):
        
        # Load database and fetch the client and endpoints
        self.start(SERVICE_TYPES)

        # Set up attenuators
        if self.attenuator is not None:
            print('Configuring attenuators.......')
            self.attenuator.base_profile()
            print('Finished configuring attenuators!')
        else:
            sleep(30)  # Need to wait more anyway
        self.flip_uplink()
        
        self.populate_all_tables()
        print('Configured services: {}.'.format(self.desired_services))
        print('Configured stations matching these services: {}.'.format(self.stations_with_desired_services))
        print('Configured cross endpoints matching these services and stations: {}.'.format(self.desired_cx))

        # Load noise generator
        if self.noise_generator is not None:
            tb = self.noise_generator
            def gnuradio_tb_sig_handler(sig=None, frame=None):
                tb.stop()
                tb.wait()

                sys.exit(0)

            signal.signal(signal.SIGINT, gnuradio_tb_sig_handler)
            signal.signal(signal.SIGTERM, gnuradio_tb_sig_handler)
            try:
                tb.start()
            except Exception as e:
                raise(e)
            else:
                print('Successfully loaded NoiseGenerator')

        #### Start the test
        test_duration_sec = 86400
        error_count, iteration = 0, 0
        start = time.time()

        print('Starting WiFiProblems Test with duration: {} at {}'.format(test_duration_sec, start))
        while time.time()-start < test_duration_sec:
            iteration += 1
            try:
                self.start_test_for_service('medium-ds-stream')
            except ValueError:
                if error_count > 3:
                    print("Still no station or cx.. Giving up after 3 retries.")
                    break
                error_count += 1
                print("Couldn't find the endpoint or station. Refreshing LanForge data..")
                self.refresh_configured_endpoints()
                continue

            # Apply each attenuation profile
            if self.attenuator is None:
                print('Attenuator is needed for this test. Aborting.')
                break

            for atten_label, atten_profile in [('disabled attenuation profile', self.attenuator.disabled_attenuation_profile), ('low attenuation profile', self.attenuator.low_attenuation_profile),
                    ('mid attenuation profile', self.attenuator.mid_attenuation_profile), ('high attenuation profile', self.attenuator.high_attenuation_profile)]:
                print('{} Applying: {}. Iteration: {}. Time elapsed: {}'.format(datetime.utcnow().isoformat(), atten_label, iteration, time.time()-start))
                atten_profile(iteration)

                # For each profile, run the interference steps
                if self.noise_generator is not None:
                    for g in self.noise_generator.db_steps:
                        tb.limesdr_sink_1.set_gain(g, 0)  # Node1 / LF2
                        tb.limesdr_sink_1.set_gain(g, 1)  # ROOT CHAMBER
                        print('[DB_NOISEGENERATOR_LOG][ATTEN_PROFILE={}] {} - {}'.format(
                            atten_label, datetime.now().isoformat(), json.dumps({'iteration': iteration, 'timestamp': datetime.utcnow().isoformat(), 'db': g, 'sleep': self.seconds_per_noise_step})))
                        sleep(self.seconds_per_noise_step)
                else:
                    sleep(self.seconds_per_atten_step)
            self.refresh_configured_endpoints()

        self.stop()

        # if not self.no_cleanup:
        #     self.cleanup()
        #     logger.info("Leaving existing stations...")



class CreateAttenuator(Realm):
    def __init__(self, host, port, serno, idx, val,
                 _debug_on=False,
                 _exit_on_error=False,
                 _exit_on_fail=False):
        super().__init__(host, port, debug_=_debug_on, _exit_on_fail=_exit_on_fail)
        self.host = host
        self.serno = serno
        self.idx = idx
        self.val = val
        self.attenuator_profile = self.new_attenuator_profile()
        self.attenuator_profile.atten_idx = self.idx
        self.attenuator_profile.atten_val = self.val
        self.attenuator_profile.atten_serno = self.serno
        
        self.defaults = self.new_attenuator_profile()
        self.defaults.atten_serno = 'all'
        self.defaults.atten_idx = 'all'
        self.defaults.atten_val = 955

    def _build(self):
        self.attenuator_profile.create()
        # self.attenuator_profile.show()

    def _configure(self, serno=None, idx=None, val=None):
        # self.attenuator_profile = self.new_attenuator_profile()
        self.attenuator_profile.atten_serno = serno
        self.attenuator_profile.atten_idx = idx
        self.attenuator_profile.atten_val = val
        self._apply()
    
    def _apply(self):
        self._build()
    
    def _print(self, iteration, db):
        print('[DB_ATTEN_LOG] {} - {}'.format(datetime.now().isoformat(), json.dumps({'iteration': iteration, 'timestamp': datetime.utcnow().isoformat(), 'db': db})))
    
    def _attenuate(self, val):
        self.attenuator_profile.atten_val = val
        self._build()

    def reset_all(self):
        self.defaults.create()
    
    def base_profile(self, iteration=0):
        self.attenuator_profile = self.new_attenuator_profile()
        self._configure('3066', 'all', 955)
        self._configure('3067', 'all', 955)        # Throttlers chamber (Node2) (Air)
        self._configure('3068', 'all', 955)
        self._configure('3070', 'all', 0)          # Client running service (Node1)
        self._configure('3073', 0, 500)            # Conducted Node2 - Needs to be open for throttlers
        self._configure('3073', 1, 500)            # Conducted Node2 - Needs to be open for throttlers
        self._configure('3073', 2, 955)            # Conducted Node1 - Needs to be completely attenuated
        self._configure('3073', 3, 955)            # Conducted Node1 - Needs to be completely attenuated
        self._configure('3076', 'all', 955)
        self._configure('3084', 'all', 955)
        self._apply()
        self._print(iteration, 0)

    def disabled_attenuation_profile(self, iteration):
        self._configure('3070', 'all', 0)
        self._apply()
        self._print(iteration, 0)
    def low_attenuation_profile(self, iteration):
        self._configure('3070', 'all', 100)
        self._apply()
        self._print(iteration, 10)
    def mid_attenuation_profile(self, iteration):
        self._configure('3070', 'all', 200)
        self._apply()
        self._print(iteration, 20)
    def high_attenuation_profile(self, iteration):
        self._configure('3070', 'all', 300)
        self._apply()
        self._print(iteration, 30)


class NoiseGenerator(gr.top_block):

    def __init__(self, db_steps=None):
        gr.top_block.__init__(self, "Dualchan Ampjammer")

        ##################################################
        # Variables
        ##################################################
        self.target_freq = target_freq = 2.437e9
        self.samp_rate = samp_rate = 20e6

        ##################################################
        # Blocks
        ##################################################
        self.limesdr_sink_1 = limesdr.sink('', 2, '/root/sdr/limesdr_2437mhz_20mhz_channelB_7db_mimo_calibrated_best_exportconf.ini', '')
        self.analog_noise_source_x_0 = analog.noise_source_c(analog.GR_GAUSSIAN, 100, -42)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.analog_noise_source_x_0, 0), (self.limesdr_sink_1, 0))
        self.connect((self.analog_noise_source_x_0, 0), (self.limesdr_sink_1, 1))
        self.db_steps = db_steps


    def get_target_freq(self):
        return self.target_freq

    def set_target_freq(self, target_freq):
        self.target_freq = target_freq
        self.limesdr_sink_1.set_center_freq(self.target_freq, 0)

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.limesdr_sink_1.set_digital_filter(self.samp_rate, 0)
        self.limesdr_sink_1.set_digital_filter(self.samp_rate, 1)


def main():
    parser = argparse.ArgumentParser(
        prog='xyz',
        formatter_class=argparse.RawTextHelpFormatter,
        epilog='''\
            ye
            ''',
        description='')

    optional = parser.add_argument_group('optional arguments')
    optional.add_argument('--mgr', '--lfmgr', default='localhost',
                          help='hostname for where LANforge GUI is running')
    optional.add_argument('--mgr_port', '--port', default=8008,
                          help='port LANforge GUI HTTP service is running on')
    optional.add_argument('-u', '--upstream_port', nargs="+", default=['eth1'],
                          help='non-station port that generates traffic: <resource>.<port>, e.g: --u eth1 eth2')


    optional.add_argument('-d', '--debug', action="store_true",
                          help='Enable debugging')
    optional.add_argument('--log_level', default=None,
                          help='Set logging level: debug | info | warning | error | critical')

    optional.add_argument('--debugging', nargs="+", action="append",
                          help="Indicate what areas you would like express debug output:\n"
                               + " - digest - print terse indications of lanforge_api calls\n"
                               + " - json - print url and json data\n"
                               + " - http - print HTTP headers\n"
                               + " - gui - ask the GUI for extra debugging in responses\n"
                               + " - method:method_name - enable by_method() debugging (if present)\n"
                               + " - tag:tagname - enable matching by_tag() debug output\n"
                          )
    optional.add_argument('--debug_log', default=None,
                          help="Specify a file to send debug output to")

    optional.add_argument('--no_cleanup', help='Do not cleanup before exit', action='store_true')


    args = parser.parse_args()

    # Run
    attenuator = CreateAttenuator(host=args.mgr, port=args.mgr_port, serno='all', idx='all', val=955, _debug_on=args.debug)
    # attenuator = None
    noise_generator = NoiseGenerator([1, 10, 30, 35, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50])
    # noise_generator = None
    wifi_problems_test = WiFiProblemsTest(host=args.mgr, port=args.mgr_port, _debug_on=args.debug, attenuator=attenuator, noise_generator=noise_generator)
    # wifi_problems_test.run()
    return wifi_problems_test

if __name__ == "__main__":
    w = main()
    try:
        w.run()
    except Exception as e:
        raise(e)
    finally:
        w.stop()
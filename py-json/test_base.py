#!/usr/bin/env python3
import lfdata
import lfreporting

class TestBase:

    def pre_clean_up(self):
        pass

    def clean_up(self):
        pass

    def start(self):
        pass

    def stop(self):
        pass

    def build(self):
        self.station_profile.use_security(self.security, self.ssid, self.password)
        self.station_profile.set_number_template(self.number_template)
        print("Creating stations")
        self.station_profile.set_command_flag("add_sta", "create_admin_down", 1)
        self.station_profile.set_command_param("set_port", "report_timer", 1500)
        self.station_profile.set_command_flag("set_port", "rpt_timer", 1)
        self.station_profile.create(radio=self.radio, sta_names_=self.sta_list, debug=self.debug)
        self.cx_profile.create(endp_type="lf_udp", side_a=self.station_profile.station_names, side_b=self.upstream,
                               sleep_time=0)
        self._pass("PASS: Station build finished")
      
    def passes(self):
        for profile in profiles:
            do profile.check_passes()
        
    def run_duration(self):
        #here check if monitor is enabled or not, then run loop accordingly
        self.check_for_halt()
        for profile in profiles:
            do profile.monitor_record()
        for profile in profiles:
            do profile.grade()
        if self.exit_on_fail:
            if self.fails():
                self.exit_fail()
        self.check_for_quit()
         
        

    def report(self):
        #here check if monitor is enabled or not, then run loop accordingly with lfreporting
        pass

    def begin(self):
        self.pre_clean_up()
        self.build()
        self.start()    
        self.run_duration()
        self.stop() 
        self.report()   
#add to confluence
# ---------------------------------   
#script to avoid collisions :
    #check valid names already in LANforge - generate next available name

#ability to run tests in different tabs in GUI at the same time
#    
#!/usr/bin/env python3
import lfdata
import lfreporting

class TestBase:

    
    def pre_clean_up(self):
        for profile in profiles:
            do profile.precleanup()

    def clean_up(self):
        for profile in profiles:
            do profile.cleanup()

    def start(self):
         for profile in profiles:
            do profile.start()

    def stop(self):
        for profile in profiles:
            do profile.stop()

    def build(self):
        for profile in profiles:
            do profile.check_passes()
    def passes(self):
        for profile in profiles:
            do profile.check_passes()
        
    def run_duration(self):
        #here check if monitor is enabled or not, then run loop accordingly
        self.check_for_halt()
        for profile in profiles:
            do profile.monitor_record() #check for halt in monitor record? 
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
        self.clean_up()  


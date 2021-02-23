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
        pass
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
         
        pass
    def report(self):
        #here check if monitor is enabled or not, then run loop accordingly
        pass

    def begin(self):
        self.pre_clean_up()
        self.build()
        self.start()    
        self.run_duration()
        self.stop() 
        self.report()   
       
#csv transformation to requested format
import re
import time
import pprint
from pprint import pprint
import os
import datetime


import pandas as pd


class Reporting():

    def change_formats(self):
        # if compared_report is not None:
        #     compared_df = self.compare_two_df(dataframe_one=self.file_to_df(report_file), dataframe_two=self.file_to_df(compared_report))
        #     exit(1)

        #     #append compared df to created one
        #     if output_format.lower() != 'csv':
        #         self.df_to_file(dataframe=pd.read_csv(report_file), output_f=output_format, save_path=report_file)
        # else:
        #     if output_format.lower() != 'csv':
        #         self.df_to_file(dataframe=pd.read_csv(report_file), output_f=output_format, save_path=report_file)
        pass
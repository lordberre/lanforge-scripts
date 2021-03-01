#csv transformation to requested format
import re
import time
import pprint
from pprint import pprint
import os
import datetime


import pandas as pd


class LFReporting:

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

   #import datatable as dt
     #takes any dataframe and returns the specified file extension of it
    def df_to_file(self, output_f=None,dataframe=None, save_path=None):
        if output_f.lower() == 'hdf': 
            import tables
            dataframe.to_hdf(save_path.replace('csv','h5',1), 'table', append=True)
        if output_f.lower() == 'parquet':
            import pyarrow as pa
            dataframe.to_parquet(save_path.replace('csv','parquet',1), engine='pyarrow')
        if output_f.lower() == 'png':
            fig = dataframe.plot().get_figure()
            fig.savefig(save_path.replace('csv','png',1))
        if output_f.lower() == 'xlsx':
            dataframe.to_excel(save_path.replace('csv','xlsx',1))
        if output_f.lower() == 'json':
            dataframe.to_json(save_path.replace('csv','json',1))
        if output_f.lower() == 'stata':
            dataframe.to_stata(save_path.replace('csv','dta',1))
        if output_f.lower() == 'pickle':
            dataframe.to_pickle(save_path.replace('csv','pkl',1))
        if output_f.lower() == 'html':
            dataframe.to_html(save_path.replace('csv','html',1))
          
    #takes any format of a file and returns a dataframe of it
    #here, use datables fread
    def file_to_df(self,file_name):
        if file_name.split('.')[-1] == 'csv':
            return pd.read_csv(file_name)
        
   
    def compare_two_df(self,dataframe_one=None,dataframe_two=None):
        pd.set_option("display.max_rows", None, "display.max_columns", None)
        #get all of common columns besides Timestamp, Timestamp milliseconds 
        common_cols = set(dataframe_one.columns).intersection(set(dataframe_two.columns))
        if common_cols is not None:
            cols_to_remove=['Timestamp milliseconds epoch','Timestamp','LANforge GUI Build: 5.4.3']
            #drop unwanted cols from df
            dataframe_one = dataframe_one.drop(list(cols_to_remove), axis=1)
            dataframe_two = dataframe_two.drop(list(cols_to_remove), axis=1)
            #for time elapsed section and endpoint name combo
            #
            print(dataframe_one)
            print(dataframe_two)
    
        
        #take those columns and separate those columns from others in DF.


        pass    
        #return compared_df

    def append_df_to_file(self,dataframe, file_name):
        pass

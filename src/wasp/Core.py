import sys
import os
import datetime
import argparse
import jdatetime
from collections import defaultdict










class WaspHandeler:
    """
        Weighted Average Synthesis Processor (WASP)
    """

    def __init__(self, args) -> None:


        self.rep_l2, self.rep_l3, self.wasp = args.input, args.out, args.wasp
        self.l2_products = dict(self.__get_all_available_products())
        self.fl2_products = dict(self.__filter_products())
        self.args = args


        return None
    

    def __get_all_available_products(self):
        repL2_dirs = os.listdir(self.rep_l2)
        l2 = defaultdict(list)
        for tile in repL2_dirs:
            dir_1st = os.path.join(self.rep_l2, tile)
            group_by_date = defaultdict(list)
            for root, dirs, files in os.walk(dir_1st, topdown=False):
                for name in files:
                    if name.endswith('MTD_ALL.xml'):

                        # Get year and month from file name
                        dt_string = name.split('_')[1].split('-')[0]

                        timestamp = datetime.datetime.strptime(dt_string, '%Y%m%d').timestamp()
                        dt_jalali = jdatetime.datetime.fromtimestamp(timestamp).strftime("%Y%m")

                        # Group by same month
                        group_by_date[dt_jalali].append(os.path.join(root, name))
            if any(dict(group_by_date)):
                l2[tile].append(dict(group_by_date))

        return l2


    def __filter_products(self):
        
        filtered_l2_products = defaultdict(list)
        for tile in self.l2_products.keys():
            for month, l2_products in dict(self.l2_products[tile][0]).items():

                l3_out_path = os.path.join(self.rep_l3, tile)
                
                if not os.path.exists(l3_out_path):
                    os.makedirs(l3_out_path)

                # Get all infiles that match tile and file pattern
                dir_list = os.listdir(l3_out_path)
                
                previous_image_date = list()
                for l3 in dir_list:
                    # Get year and month from file name
                    dt_string = l3.split('_')[1].split('-')[0]

                    timestamp = datetime.datetime.strptime(dt_string, '%Y%m%d').timestamp()
                    dt_jalali = jdatetime.datetime.fromtimestamp(timestamp).strftime("%Y%m")
                    previous_image_date.append(dt_jalali)

                if not str(month) in previous_image_date:
                    filtered_l2_products[tile].append([l2_products, l3_out_path])
                
        return filtered_l2_products


    def execute(self):
        sys.path.append(self.wasp)
        import WASP
        for tile in dict(self.fl2_products).keys():
            for l2_products, l3_out_path in self.fl2_products[tile]:
                self.args.input = l2_products
                self.args.out = l3_out_path
                ts = WASP.TemporalSynthesis(self.args)
                ts.run()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-e", "--wasp", help="Path to WASP application. Required.", 
                        required=True, type=str)
    parser.add_argument("-i", "--input", help="The Metadata input products in MUSCATE format. Required.", 
                        required=True, type=str)
    parser.add_argument("-o", "--out", help="Output directory. Required.", 
                        required=True, type=str)
    parser.add_argument("-t", "--tempout", help="Temporary output directory. If none is given, it is set to the value of --out", 
                        required=False, type=str)
    parser.add_argument("-v", "--version", help="Parameter version. Default is 1.0", 
                        required=False, default="1.0", type=str)
    parser.add_argument("-log", "--logging", help="Path to log-file. Default is in the current directory. If none is given, no log-file will be created.", 
                        required=False, default="", type=str,)
    parser.add_argument("-d" ,"--date", help="L3A synthesis date in the format 'YYYYMMDD'. If none, then the middle date between all products is used", 
                        required=False, type=str)
    parser.add_argument("-r", "--removeTemp", help="Removes the temporary created files after use. Default is true", 
                        required=False)
    parser.add_argument("--verbose", help="Verbose output of the processing. Default is True", 
                        default="True", type=str)
    parser.add_argument("--synthalf", help="Half synthesis period in days. Default for S2 is 23, for Venus is 9", 
                        required=False, type=int)
    parser.add_argument("--pathprevL3A", help="Path to the previous L3A product folder. Does not have to be set.", 
                        required=False, type=str)
    parser.add_argument("--cog", help="Write the product conform to the CloudOptimized-Geotiff format. Default is false", 
                        required=False, default="Flase")
    parser.add_argument("--weightaotmin", help="AOT minimum weight. Default is 0.33", 
                        required=False, type=float)
    parser.add_argument("--weightaotmax", help="AOT maximum weight. Default is 1", 
                        required=False, type=float)
    parser.add_argument("--aotmax", help="AOT Maximum value. Default is 0.8", 
                        required=False, type=float)
    parser.add_argument("--coarseres", help="Resolution for Cloud weight resampling. Default is 240" , 
                        required=False, type=int)
    parser.add_argument("--kernelwidth", help="Kernel width for the Cloud Weight Calculation. Default is 801", 
                        required=False, type=int)
    parser.add_argument("--sigmasmallcld", help="Sigma for small Clouds. Default is 2", 
                        required=False, type=float)
    parser.add_argument("--sigmalargecld",  help="Sigma for large Clouds. Default is 10", 
                        required=False, type=float)
    parser.add_argument("--weightdatemin", help="Minimum Weight for Dates. Default is 0.5", 
                        required=False, type=float)
    parser.add_argument("--nthreads", help="Number of threads to be used for running the chain. Default is 8.", 
                        required=False, type=int)
    parser.add_argument("--scatteringcoeffpath", help="Path to the scattering coefficients files. If none, it will be searched for using the OTB-App path. Only has to be set for testing-purposes", 
                        required=False, type=str)

    args = parser.parse_args()
    wasp = WaspHandeler(args)
    wasp.execute()
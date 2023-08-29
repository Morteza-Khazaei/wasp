import os
import glob
import datetime
import argparse
import jdatetime
import numpy as np
from osgeo import gdal
from collections import defaultdict

import zipfile
import requests
import json


from wasp.base_comparison import BaseComparison







class WASP(BaseComparison):
    """
        Weighted Average Synthesis Processor (WASP)
    """
    def __init__(self, repL2:str, repL3:str, NRGB:bool=True, url:str='http://192.168.66.66:9090', username:str='mortezakhazaei1370@gmail.com', password:str='m3541532') -> None:
        self.repL2 = repL2
        self.repL3 = repL3
        if NRGB:
            self.repNRGB = '/'.join(repL3.split('/')[:-2].append('composite'))
        self.l2_products = self.__get_all_available_products()
        self.fl2_products = self.__filter_products()

        self.url = url
        auth_token = self.__get_token(username, password)
        self.headers = {
            'Accept': 'application/json',
            'Authorization': 'Token {}'.format(auth_token)
        }

        return None


    def __get_token(self, username, password):
        token_url = f'{self.url}/gcms/accounts/api/auth/login'
        headers = {'Content-type': 'application/json', 'Accept': 'application/json'}
        auth_data = {
            'email': username,
            'password': password
        }
        resp = requests.post(token_url, data=json.dumps(auth_data), headers=headers).json()

        return resp['token']


    def __get_all_available_products(self):
        repL2_dirs = os.listdir(self.repL2)
        l2 = defaultdict(list)
        for tile in repL2_dirs:
            dir_1st = os.path.join(self.repL2, tile)
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
            l2[tile].append(group_by_date)

        return l2


    def __filter_products(self):
        
        filtered_l2_products = defaultdict(list)
        for tile in dict(self.l2_products).keys():
            for month, l2_products in dict(self.l2_products[tile]).items():

                l3_out_path = os.path.join(self.repL3, tile)
                
                if not os.path.exists(l3_out_path):
                    os.makedirs(l3_out_path)
                
                l3_out_path_NRGB = os.path.join(self.repNRGB, tile)

                if not os.path.exists(l3_out_path_NRGB):
                    os.makedirs(l3_out_path_NRGB)

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
                    filtered_l2_products[tile].append(l2_products, l3_out_path, l3_out_path_NRGB)
                
        return filtered_l2_products


    def execute(self):
        for tile in dict(self.fl2_products).keys():
            for l2_products, l3_out_path, l3_out_path_NRGB in dict(self.fl2_products[tile]).items():
                ts = WASP.TemporalSynthesis(self.createArgs(l2_products, l3_out_path))
                ts.run()
            if self.repNRGB:
                # Get all infiles that match tile and file pattern
                out_dir_list = os.listdir(l3_out_path_NRGB)
                for pid in out_dir_list:
                    platform, date_obj, product, tile_number, c, version = pid.split('_')

                    # Get year and month from file name
                    dt_string = date_obj.split('-')[0]

                    timestamp = datetime.datetime.strptime(dt_string, '%Y%m%d').timestamp()
                    dt_jalali = jdatetime.datetime.fromtimestamp(timestamp)
                    yyyymm = str(dt_jalali.strftime("%Y%m")) + '01'
                    product_name = ''.join(['_'.join(['SENTINEL2X', '-'.join([yyyymm, '000000', '000']), 
                                                         product, tile_number, c, version])])
                    fname = product_name + '.tif'
                    zfname = product_name + '.zip'
                    out_file_path = os.path.join(l3_out_path_NRGB, fname)
                    out_zipfile_path = os.path.join(l3_out_path_NRGB, zfname)
                    
                    if not os.path.exists(out_zipfile_path):
                        
                        out_sub_path = os.path.join(l3_out_path, pid)
                        mask_path = os.path.join(out_sub_path, 'MASKS')
                        mask_files = glob.glob('%s/*.tif' % (mask_path))

                        # Where no data
                        if len(mask_files) == 0:
                            print('WARNING: No products found to merge.')
                            continue
                        
                        mask_names = ['0_WGT_R1',]
                        selected_mask_file = [f for f in mask_files if os.path.splitext(f)[0].split('/')[-1].split('-')[-1] in mask_names][0]

                        mask_ds = gdal.Open(selected_mask_file)
                        geotransform = mask_ds.GetGeoTransform()
                        x_size = mask_ds.RasterXSize
                        y_size = mask_ds.RasterYSize
                        srs = mask_ds.GetProjectionRef()

                        infiles = glob.glob('%s/*.tif' % (out_sub_path))
                        band_names = ['B2', 'B3', 'B4', 'B8']
                        selected_files = [f for f in infiles if os.path.splitext(f)[0].split('/')[-1].split('_')[-1] in band_names]

                        arrayList = [gdal.Open(infile).ReadAsArray() for infile in selected_files]

                        B = np.stack(arrayList)

                        driver = gdal.GetDriverByName('GTiff')
                        dataset_out = driver.Create(out_file_path, x_size, y_size, 4, gdal.GDT_Int16)

                        # Set transform/proj from those found above
                        dataset_out.SetGeoTransform(geotransform)
                        dataset_out.SetProjection(srs)
                        for band in range(dataset_out.RasterCount):
                            band += 1
                            dataset_out.GetRasterBand(band).SetNoDataValue(-10000)

                        # Write Raster To TIFF File
                        dataset_out.WriteRaster(0, 0, x_size, y_size, B.tobytes(), x_size, y_size, band_list=[1, 2, 3, 4])

                        
                        gdal.Warp(out_file_path, dataset_out, dstSRS='EPSG:3857', xRes=10, yRes=10, 
                                  creationOptions=['COMPRESS=LZW', 'PREDICTOR=2'])
                        
                        print ("Save File is ok!")
                        dataset_out.FlushCache()
                        
                        zf = zipfile.ZipFile(out_zipfile_path, "w", zipfile.ZIP_DEFLATED)
                        zf.write(out_file_path, fname)
                        zf.close()

                        data = {
                            'year': dt_jalali.year,
                            'month': dt_jalali.month,
                            'scene_name': tile_number
                        }

                        files = {'zip_file': open(os.path.join(out_zipfile_path, zfname), 'rb')}
                        resp =  requests.post(f'{self.url}/gcms/api/Sentinel2Raster/', data=data, headers=self.headers, files=files)
                        print(resp.status_code)
                        print(resp.json())

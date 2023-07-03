# -*- coding: utf-8 -*-
"""
Created on Sun Jul  2 20:31:25 2023

@author: 23962
"""
import geopandas as gpd
from shapely.geometry import Point,shape
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import time
from urllib import parse
import hashlib
import requests
import pandas as pd
from osgeo import gdal,ogr,osr,gdalconst
import numpy as np
from scipy.stats import gaussian_kde
import urllib
import math
from urllib.request import urlopen,quote
import matplotlib.pyplot as plt
import streamlit as st
#自定义一个实时更新网页总页数并爬取数据的函数并形成dataframe,需要输入区名district


def get_info(district):
    options=webdriver.ChromeOptions()
    prefs={
        'profile.default_content_setting_values':
        {
            'images': 2,
            'javascript':2
            }
        }
    options.add_experimental_option('prefs',prefs)#设置网页加载选项，限制加载图片和javascript
    options.add_argument('--headless')
    path =  Service('chromedriver.exe')
    driver = webdriver.Chrome(service = path,options=options)
    driver.get('https://sh.lianjia.com/ershoufang/rs'+district+'/')#利用chrome驱动打开网页
    totalPages=json.loads(driver.find_element(By.CSS_SELECTOR, "[class='page-box house-lst-page-box']").get_attribute("page-data"))['totalPage']
    #使用json语句获取页数
    location = []
    houseinfo = []
    priceinfo = []#三个空列表分别对应三项信息
    flag = 1
    my_bar = st.progress(0)
    progress = 0
    path =  Service('chromedriver.exe')
    driver = webdriver.Chrome(service = path,options=options)
    for flag in range(1,totalPages+1):#利用循环实现自动翻页
        driver.get('https://sh.lianjia.com/ershoufang/pg'+str(flag)+'rs'+district+'/')#通过F12获得的网页分析中发现分页面路径格式，按格式进行跳转
        time.sleep(2)#睡眠2秒，防止访问频率过高
        List1 = driver.find_elements(By.CSS_SELECTOR, "[class='clear LOGCLICKDATA']") #查找每个页面上的头条房屋
        List2 = driver.find_elements(By.CSS_SELECTOR, "[class='clear LOGVIEWDATA LOGCLICKDATA']")#查找每个页面上的次条至末条
        for item in List1:
            location.append(item.find_elements(By.CSS_SELECTOR,"[class='positionInfo']").text)#获取位置信息并封装
            houseinfo.append(item.find_element(By.CSS_SELECTOR, "[class='houseInfo']").text)#获取房屋信息并封装
            priceinfo.append(item.find_element(By.CSS_SELECTOR,  "[class='priceInfo']").text.replace("\n",''))#获取价格信息去除换行符并封装
        for item in List2:
            location.append(item.find_element(By.CSS_SELECTOR,  "[class='positionInfo']").text)
            houseinfo.append(item.find_element(By.CSS_SELECTOR,  "[class='houseInfo']").text)
            priceinfo.append(item.find_element(By.CSS_SELECTOR,  "[class='priceInfo']").text.replace("\n",''))
        progress+= 1/totalPages
        if progress > 1:
            progress = 1
        my_bar.progress(progress)
    driver.close()#关闭网页驱动
    info = gpd.GeoDataFrame()
    info["位置"]=location
    info["房屋信息"]=houseinfo
    info["价格信息"]=priceinfo#录入信息
    my_bar.progress(0)
    return info#返回封装得到的GeoDataFrame

#第二部分空间标注
#需要首先在百度地图开放平台创建应用，获取AK和SK
def get_location(addtress):
     AK = '7EVTL1Yh8NRc5BUU5wGjEVZjgezXLI96'
     SK = 'vRja8RZCYVqvgHX2z7gRUzsTSn6asKMB'#从百度云平台获取的AK和SK
     queryStr = '/geocoding/v3/?address=%s&output=json&ak=%s' % (addtress,AK)
     # 对queryStr进行转码，safe内的保留字符不转换
     encodedStr = parse.quote(queryStr, safe="/:=&?#+!$,;'@()*[]")
     # 在最后直接追加上yoursk
     rawStr = encodedStr + SK
     #计算sn
     sn = (hashlib.md5(parse.quote_plus(rawStr).encode("utf8")).hexdigest())
     #由于URL里面含有中文，所以需要用parse.quote进行处理，然后返回最终可调用的url
     url = parse.quote("http://api.map.baidu.com"+queryStr+"&sn="+sn, safe="/:=&?#+!$,;'@()*[]")
     res = requests.get(url)
     temp = json.loads(res.text)
     location = temp['result']['location']
     return location

def locate_info(info):
   info['lng'] = ("上海"+ district +info['位置']).apply(lambda x: get_location(x)['lng'])
   info['lat'] = ("上海"+ district +info['位置']).apply(lambda x: get_location(x)['lat'])#执行操作，写入info（GeoDataFrame对象）
   return info


def get_html(Data):
    var_point = []
    var_marker = []
    addOverlay = []
    for i in range(len(Data)):
        point = 'new BMap.Point(' + str(Data.loc[i, 'lng']) + ',' + str(Data.loc[i, 'lat']) + ')'
        marker = 'var marker' + str(i) + '=new BMap.Marker(points[' + str(i) + '],{icon:myIcon});'
        overlay = 'map.addOverlay(marker' + str(i) + ');'
        var_point.append(point)
        var_marker.append(marker)
        addOverlay.append(overlay)
    points = ','.join(var_point)
    markers = '\n        '.join(var_marker)
    overlays = '\n        '.join(addOverlay)
    message1 = '''
    <!DOCTYPE html>
    <html xmlns:asp="">
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
        <meta name="viewport" content="initial-scale=1.0, user-scalable=no" />
        <style type="text/css">
            body, html,#allmap {width: 100%;height: 100%;overflow: hidden;margin:0;font-family:"微软雅黑";}
        </style>
        <script type="text/javascript" src="https://api.map.baidu.com/api?type=webgl&v=1.0&ak=7EVTL1Yh8NRc5BUU5wGjEVZjgezXLI96&sn=10a379d477eea870ce7dee8e4e03edae"></script>
        <title>添加信息窗口</title>
    </head>
    <body>
    <div id="allmap"></div>
    </body>
    <script>
        // An highlighted block
        //百度地图API功能
        function loadJScript() {
            var script = document.createElement("script");
            script.type = "text/javascript";
            script.src = "https://api.map.baidu.com/api?v=2.0&ak=7EVTL1Yh8NRc5BUU5wGjEVZjgezXLI96&sn=10a379d477eea870ce7dee8e4e03edae&callback=init";
            document.body.appendChild(script);
        }
        window.init = function() {
            var map = new BMap.Map("allmap");            // 创建Map实例
            //var point = new BMap.Point(109.18592,34.36912); // 创建点坐标
            map.centerAndZoom(new BMap.Point(121.487899486,31.24916171), 10);  // 设置中心点,地图初始化
            //map.centerAndZoom(points,20);
            map.setCurrentCity("上海");          //设置当前城市
            map.clearOverlays();
            map.addControl(new BMap.MapTypeControl());
            map.enableScrollWheelZoom(true);                 //启用滚轮放大缩小
            map.addEventListener('click', function(e) {
                alert('点击的经纬度：' + e.latlng.lng + ', ' + e.latlng.lat);
                var mercator = map.lnglatToMercator(e.latlng.lng, e.latlng.lat);
                alert('点的墨卡托坐标：' + mercator[0] + ', ' + mercator[1]);
            });
            //向地图中添加缩放控件
            var ctrlNav = new window.BMap.NavigationControl({
                anchor: BMAP_ANCHOR_TOP_LEFT,
                type: BMAP_NAVIGATION_CONTROL_LARGE
            });
            map.addControl(ctrlNav);
            //向地图中添加标记点
            var myIcon =new BMap.Icon("http://api.map.baidu.com/img/markers.png", new BMap.Size(23, 25), {    //小车图片
                offset: new BMap.Size(0, -5),    //相当于CSS精灵
                imageOffset: new BMap.Size(0, 0)    //图片的偏移量。为了是图片底部中心对准坐标点。
            });
    '''
    message2 = points
    message3 = markers
    message4 = overlays
    message5 = '''
            //map.setViewport(points);         //调整地图的最佳视野为显示标注数组point
        }
        loadJScript()
    </script>
    <script>
        layui.use('theme/settings/earth', layui.factory('theme/settings/earth'));
    </script>
    <!--<script type="text/javascript" src="js\jquery-2.1.1.min.js"></script>-->
    </html>
    '''
    message = message1 + '\n' + '        var points = [' + message2 + '];' + '\n        ' + message3 + '\n        ' + message4 + '\n' + message5
    return message




#坐标转换模块
x_pi = 3.14159265358979324 * 3000.0 / 180.0
pi = 3.1415926535897932384626  # π
a = 6378245.0  # 长半轴
ee = 0.00669342162296594323  # 偏心率平方
def gcj02_to_bd09(lng, lat):
    z = math.sqrt(lng * lng + lat * lat) + 0.00002 * math.sin(lat * x_pi)
    theta = math.atan2(lat, lng) + 0.000003 * math.cos(lng * x_pi)
    bd_lng = z * math.cos(theta) + 0.0065
    bd_lat = z * math.sin(theta) + 0.006
    return [bd_lng, bd_lat]
def bd09_to_gcj02(bd_lon, bd_lat):
    x = bd_lon - 0.0065
    y = bd_lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * x_pi)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * x_pi)
    gg_lng = z * math.cos(theta)
    gg_lat = z * math.sin(theta)
    return [gg_lng, gg_lat]
def gcj02_to_wgs84(lng, lat):
    dlat = _transformlat(lng - 105.0, lat - 35.0)
    dlng = _transformlng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * pi)
    mglat = lat + dlat
    mglng = lng + dlng
    return [lng * 2 - mglng, lat * 2 - mglat]
def bd09_to_wgs84(bd_lon, bd_lat):
    lon, lat = bd09_to_gcj02(bd_lon, bd_lat)
    return gcj02_to_wgs84(lon, lat)
def _transformlat(lng, lat):
    ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + \
          0.1 * lng * lat + 0.2 * math.sqrt(math.fabs(lng))
    ret += (20.0 * math.sin(6.0 * lng * pi) + 20.0 *
            math.sin(2.0 * lng * pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * pi) + 40.0 *
            math.sin(lat / 3.0 * pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * pi) + 320 *
            math.sin(lat * pi / 30.0)) * 2.0 / 3.0
    return ret
 
def _transformlng(lng, lat):
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + \
          0.1 * lng * lat + 0.1 * math.sqrt(math.fabs(lng))
    ret += (20.0 * math.sin(6.0 * lng * pi) + 20.0 *
            math.sin(2.0 * lng * pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * pi) + 40.0 *
            math.sin(lng / 3.0 * pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * pi) + 300.0 *
            math.sin(lng / 30.0 * pi)) * 2.0 / 3.0
    return ret
 
def out_of_china(lng, lat):
    """
    判断是否在国内，不在国内不做偏移
    :param lng:
    :param lat:
    :return:
    """
    return not (lng > 73.66 and lng < 135.05 and lat > 3.86 and lat < 53.55)

def Pixel_to_world(geoTransform, line, column):
    originX = geoTransform[0]
    originY = geoTransform[3]
    pixelWidth = geoTransform[1]
    pixelHeight = -geoTransform[5]
    x = column*pixelWidth + originX - pixelWidth/2
    y = line*pixelHeight + originY - pixelHeight/2
    return(x,y)


#以下为网页构建程序
#网页初始化
st.title('上海市分区二手房实时查询定位和密度分析:house:')
st.header('使用说明')
text = """
该系统使用selenium库实时获取链家平台在售的二手房信息，使用百度地图开放平台和阿里云
进行地理信息获取，利用GDAL库进行地理处理和分析，输出结果以WGS84作为地理坐标系，以
EPSG102025作为投影坐标系。
"""
st.markdown(text)

#准备工作
working_space = st.text_input('请输入您想要存放过程文件的路径,例如C:\\Users\\23962\\Desktop\\working')
results_space = st.text_input('请输入您想要存放结果文件的路径,例如C:\\Users\\23962\\Desktop\\results')
text = """
请确保您输入的文件夹路径可用，尽量不要出现汉字
"""
st.markdown(text)
#第一部分：实时二手房数据获取
districts = ['浦东','闵行','宝山','徐汇','普陀','杨浦','长宁','松江','嘉定','黄浦','静安','虹口','青浦','奉贤','金山','崇明','吴泾']
district =st.selectbox("选择一个区(吴泾为测试用，请勿选择)",districts)
text = """
依次点击按钮实现相应功能，您无需实现全部功能才可离开网页
"""
st.markdown(text)
if st.button('搜索并导出为Excel'):
    info = get_info(district)
    st.title('搜索结果')
    st.dataframe(info)
    path = results_space+'\\'+district+'在售二手房信息.xlsx'
    info.to_excel(path, sheet_name='Sheet1')
    path = working_space+'\\'+'info.xlsx'
    info.to_excel(path, sheet_name='Sheet1')
    
if st.button('开始自动获取二手房地址'):
   path = working_space+'\\'+'info.xlsx'
   info=pd.read_excel(path, sheet_name='Sheet1')
   st.write('正在从百度API获取地址，此过程需要几分钟，请耐心等待')
   locate_info(info)
   st.write('二手房地址获取完毕,请点击生成按钮进行定位或点击地理处理进行密度分析')
   path = working_space+'\\'+'info.xlsx'
   info.to_excel(path, sheet_name='Sheet1')
   
if st.button('生成百度地图动态API'):
    st.write('正在生成百度地图动态API，请耐心等待完成提示')
    path = working_space+'\\'+'info.xlsx'
    info=pd.read_excel(path, sheet_name='Sheet1')
    geometry = [Point(xy) for xy in zip(info['lng'], info['lat'])]
    geoinfo = gpd.GeoDataFrame(info, geometry=geometry)
    path = working_space+'\\'+'geoinfo.shp'
    geoinfo.to_file(path,encoding='gbk')
    path = results_space+'\\'+district+'二手房地理信息.shp'
    geoinfo.to_file(path,encoding='gbk')
    point = geoinfo['geometry']
    message = get_html(geoinfo)
    path = results_space+'\\'+district+'二手房所在小区定位（建议使用Edge浏览器打开）' + '.html'
    with open(path, 'w', encoding="utf-8")as f:
        f.write(message)
        f.close()    
    st.write('百度地图动态API已生成，请在您自定义的结果文件夹中查看')
    
if st.button('地理处理'):
    path = working_space+'\\'+'geoinfo.shp'
    geoinfo = gpd.read_file(path)
    dict = {'浦东':'310104','闵行':'310112','宝山':'310113','徐汇':'310104','普陀':'310107','杨浦':'310110',
            '长宁':'310105','松江':'310117','嘉定':'310114','黄浦':'310101','静安':'310106','虹口':'310109',
            '青浦':'310118','奉贤':'310120','金山':'310116','崇明':'310151','吴泾':'310112'}#创建一个区名和adcode对应的索引字典
    adcode = dict[district]
    url = 'https://geo.datav.aliyun.com/areas_v3/bound/geojson?code='+adcode
    
    response = requests.get(url)
    geojson = response.json()#获取geojson数据
    for i in range(len(geojson['features'][0]['geometry']['coordinates'][0][0])):#进行坐标转换到WGS84
        geojson['features'][0]['geometry']['coordinates'][0][0][i] = gcj02_to_wgs84(geojson['features'][0]['geometry']['coordinates'][0][0][i][0],geojson['features'][0]['geometry']['coordinates'][0][0][i][1])
    bound = shape(geojson['features'][0]['geometry'])#使用shapely创建边界
    #计算点的核密度值
    house_point = pd.DataFrame()
    lng = []
    lat = []
    for i in range(len(geoinfo)):
        add = bd09_to_wgs84(geoinfo.loc[i, 'lng'],geoinfo.loc[i, 'lat'] )
        lng.append(add[0])
        lat.append(add[1])
    house_point['lng'] = lng
    house_point['lat'] = lat
    geometry = [Point(xy) for xy in zip(house_point['lng'], house_point['lat'])]
    house_point = gpd.GeoDataFrame(house_point, geometry=geometry)
    point = house_point['geometry']
    path = working_space + '\\' + 'house_point.shp'
    point.to_file(path,encoding='utf-8', crs="EPSG:4326")
    driver = ogr.GetDriverByName('ESRI Shapefile')
    house_point = driver.Open(path, 0)
    layer = house_point.GetLayer()
    points = layer.GetNextFeature()
    
    x = []
    y = []
    while points:
        geom = points.GetGeometryRef()
        x.append(geom.GetX())
        y.append(geom.GetY())
        points = layer.GetNextFeature()
        
    xy = np.vstack([x,y])
    z = gaussian_kde(xy)(xy)#获得每一个点的核密度值
    path = working_space+'\\'+'house_point.shp'
    house_point = gpd.read_file(path,encoding = "utf8")
    house_point['kde'] = z
    path = results_space+'\\'+'gaussian_kde.shp'
    house_point.to_file(path,encoding='utf-8', crs="EPSG:4326",allow_override=True)

        #按照行政区边界新建一个空白栅格并插值

    bound = gpd.GeoSeries(bound)
    bound_co = bound.set_crs("EPSG:4326",allow_override=True)
    bound_project = bound_co.to_crs("EPSG:3857")
    bound_shape = shape(bound_project[0])
    LU_X = bound_shape.bounds[0]
    LU_Y = bound_shape.bounds[3]
    width = bound_shape.bounds[2]-bound_shape.bounds[0]
    height = bound_shape.bounds[3]-bound_shape.bounds[1]
    cols = int(width/500)+1
    rows = int(height/500)+1
    
    pixel_width = width / cols
    pixel_height = height / rows
    geoTransform = (LU_X, pixel_width, 0.0, LU_Y, 0.0, -pixel_height)
    a = np.zeros((rows,cols))
    house_point = house_point.to_crs("EPSG:3857")
    #进行IDW空间插值
    st.write('正在进行IDW插值，此过程耗时较长，完成后会弹出提示，您可以起身走动走动喝杯咖啡:coffee:')
    for i in range(rows):
        for j in range(cols):
            x,y = Pixel_to_world(geoTransform, i, j)
            target = Point((x,y))
            dist = house_point.distance(target)
            i_dist = 1/(dist**2)
            i_dist_sum = sum(i_dist)
            weight = i_dist/i_dist_sum
            kde = house_point['kde']
            a[i][j] = sum(kde*weight)
    driver = gdal.GetDriverByName('GTiff')
    path = results_space +'\\'+'house_density.tif'
    outdata = driver.Create(path, xsize=cols, ysize=rows, bands=1, eType=gdalconst.GDT_Float32)
    outband = outdata.GetRasterBand(1)
    outband.WriteArray(a)
    outdata.SetGeoTransform(geoTransform)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(3857)
    outdata.SetProjection(srs.ExportToWkt())
    outdata.FlushCache()
    geojson = bound_project.to_json()
    outdata = None
    st.write('已完成IDW插值并导出为tif请在您定义的结果文件夹中查看:coffee:')
    #同时保存矢量边界用于客户叠置分析
    path = results_space + '\\'+'boundary.shp'
    bound_gpd = gpd.GeoDataFrame(geometry=bound_project)
    bound_gpd.columns = ["geometry"]
    bound_gpd.index = ["multipolygon"]
    bound_gpd.to_file(path)
    st.write('已将边界导出为shp文件，请在您定义的结果文件夹中查看:coffee:')
    st.write('地理处理已经完成，您可以点击\“预览\”在线查看输出栅格或直接退出')
    st.write('谢谢')
if st.button('预览栅格'):
    st.header('密度预览仅供参考，精确信息请您在在ArcGIS中对密度和边界进行叠加查看，可能需要进行重分类才能达到所示或更直观的效果')
    path = results_space +'\\'+'house_density.tif'
    ds = gdal.Open(path)
    band1 = ds.GetRasterBand(1)
    array = band1.ReadAsArray()
    fig, ax = plt.subplots()
    ax = plt.imshow(array)
    plt.colorbar(ax)
    st.pyplot(fig)
    ds = None
    st.write('所有功能已经完成，您可以直接退出网站或刷新后重新使用全部功能')
    st.write('谢谢')
    



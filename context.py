from app import app, mongo
from datetime import datetime,timedelta
import calendar
import googlemaps
from bson.json_util import dumps
from bson.objectid import ObjectId
from flask import jsonify, request,Response
import ast
import json
import recommend
import numpy as np
import pandas as pd
from sklearn import cluster,metrics
from sklearn.tree import DecisionTreeClassifier # Import Decision Tree Classifier
from sklearn.model_selection import train_test_split # Import train_test_split function 
#from sklearn.tree.export import export_text
from sklearn.tree import _tree
from geopy.geocoders import Nominatim
gmaps = googlemaps.Client(key = 'AIzaSyBlUJmvjnGDlcV7WDYVLns8J85hnu7X_90') 

#'convenient_store', 'mall', 'gas_station', 'theater', 'parking_lot', 'restuarant', 'hypermarket'
#1便利 2百貨 3加油 4電影 5停車 6餐廳 7賣場
# 紅利 現金 電影 停車 加油
# 百貨：[現金 紅利] (停車)
# 加油戰：加油 [紅利 現金]
# 停車場：停車 [現金 紅利]
# 電影院：電影 [現金 紅利]
# 餐廳：[現金 紅利]
#----------------------------------------------------------------------------------------
# place type
# 便利商店: convenience_store
# 百貨公司: department_store, shopping_mall
# 加油站: gas_station
# 電影院: movie_theater
# 停車場: parking
# 餐廳: cafe, restaurant
# 大賣場: supermarket

#==============================================================用卡推薦==============================================================#

#--------------------------------------------------------------更新版本--------------------------------------------------------------#

#kmean分群，計算每群每個地點類型的百分比並排序，由大而小給個地點類型加分
#回傳：[[各地點類型該加上的分數],[1,2,3,4,5],[]...]
def kmean_score_and_tree():
    df = pd.read_csv('/Users/peggy/Desktop/Tweet_CARD_code/prefer2.0.csv')
    x = df[['age', 'sex', 'annualIncome', 'expenseMonth','mall', 'gas_station', 'theater', 'parking_lot',
       'restuarant']][0:239]
    #k-means++的方法就是讓初始中心之間的距離盡可能地遠使得加速 迭代過程的收斂
    kmeans_fit = cluster.KMeans(n_clusters=16, algorithm='auto', init='k-means++', random_state=10).fit(x)
    cluster_labels = kmeans_fit.labels_

    result=[] #16個[5欄]
    for i in range(16):
        n=np.where(cluster_labels == i)
        m_tmp=0
        g_tmp=0
        t_tmp=0
        p_tmp=0
        r_tmp=0
        for j in range(len(n[0])):
            y=df[['mall', 'gas_station', 'theater', 'parking_lot','restuarant']][n[0][j]:(n[0][j]+1)]
            m_tmp+=y['mall'].sum()
            g_tmp+=y['gas_station'].sum()
            t_tmp+=y['theater'].sum()
            p_tmp+=y['parking_lot'].sum()
            r_tmp+=y['restuarant'].sum()
        result.append({0:m_tmp/len(n[0]),1:g_tmp/len(n[0]),2:t_tmp/len(n[0]),3:p_tmp/len(n[0]),4:r_tmp/len(n[0])})
    group_place_score=[]
    for i in range(16):
        tmp_result=sorted(result[i].items(),key = lambda i: i[1],reverse=True)
        cur_max=-1
        num=[0,0,0,0,0]
        length=5
        for j in tmp_result:
            if tmp_result.index(j)==0:
                num[j[0]]+=length
                cur_max=j[1]
            else:
                if j[1]==cur_max:
                    num[j[0]]+=length
                    length-=1
                else:
                    length-=1
                    num[j[0]]+=length
                    cur_max=j[1]
        group_place_score.append(num)

    #classification tree
    feature_cols = ['age', 'sex', 'annualIncome','expenseMonth']
    X = x[feature_cols] # Features
    y = cluster_labels
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=1)
    clf = DecisionTreeClassifier(criterion='entropy')
    # Train Decision Tree Classifer
    clf = clf.fit(X_train,y_train)
    return [clf,group_place_score,feature_cols]


def classification_(clf,group_place_score,feature_value,feature_cols,context_sum):
    group=tree_to_code(clf,feature_cols,feature_value)
    score_list=group_place_score[group]
    for i in range(len(score_list)):
        context_sum[i]+=score_list[i]
    return context_sum


#feature_value:{age,income,avg_cost,sex}
def tree_to_code(tree, feature_names,feature_value):
    tree_ = tree.tree_
    feature_name = [
        feature_names[i] if i != _tree.TREE_UNDEFINED else "undefined!"
        for i in tree_.feature
    ]
    #print("def tree({}):".format(", ".join(feature_names)))

    def recurse(node, depth):
        #indent = "  " * depth
        if tree_.feature[node] != _tree.TREE_UNDEFINED:
            name = feature_name[node] #str
            threshold = tree_.threshold[node] #float
            #print("{}if {} <= {}:".format(indent, name, threshold))
            if feature_value[name]<=threshold:
                group=recurse(tree_.children_left[node], depth + 1)
                return group
            #print("{}else:  # if {} > {}".format(indent, name, threshold))
            else:
                group=recurse(tree_.children_right[node], depth + 1)
                return group
        else:
            #print("{}return {}".format(indent, tree_.value[node][0]))
            group=np.where(tree_.value[node][0]>0)[0][0]          
            return group
        
    group=recurse(0, 1)
    return group
 
#--------------------------------------------------------------更新版本end--------------------------------------------------------------#

# version1:單純用出現頻率判斷地點類型偏好
# 記帳紀錄 db:google location
# 0便利 1百貨 2加油 3電影 4停車 5餐廳 6賣場
# 記帳類別->地點類別
def book_keeping_record_by_freq(auth_id, context_sum, weight):
    records = mongo.db.googleLocation.find({'id': auth_id}) #Bson
    resp_tmp = dumps(records) #Json
    tmp_dict = json.loads(resp_tmp) #dict
    place_count = {0:0,1:0,2:0,3:0,4:0,5:0,6:0}
    for record in tmp_dict:
        if(record['locationType']=='百貨公司'):
            place_count[0]+=1
        if(record['locationType']=='加油站'):
            place_count[1]+=1
        if(record['locationType']=='電影院'):
            place_count[2]+=1
        if(record['locationType']=='停車場'):
            place_count[3]+=1
        if(record['locationType']=='餐廳'):
            place_count[4]+=1
    result = sorted(place_count,key = place_count.get, reverse=True) #由大到小->頻率高到低 #list
    b_count=len(result) #5
    tmp_value=0
    for i in range(len(result)):
        key=result[i] #int
        value= place_count[result[i]]#int
        if(i==0):
            tmp_value=value
            context_sum[key]+=len(result)
        elif(i>=0):
            if(tmp_value==value):
                context_sum[key]+=b_count
            else:
                b_count-=1
                context_sum[key]+=b_count
                tmp_value=value
    return context_sum

# version2:兩個月內，同一個星期幾，前後兩小時，與現在時間點最近的一種地點類型分數最高(記帳類型->地點類型)
# 記帳紀錄 db:google location
# 0便利 1百貨 2加油 3電影 4停車 5餐廳 6賣場
# 記帳類別->地點類別
def book_keeping_record_by_time(auth_id, context_sum, weight):
    now=datetime.now()
    two_hour_later = now + timedelta(hours=2)
    two_hour_before = now - timedelta(hours=2)
    place_count = {0:0,1:0,2:0,3:0,4:0}
    convert={'百貨公司':0, '加油站':1, '電影院':2,'停車場':3,'餐廳':4}
    for i in range(7,57,7):
        compare={'百貨公司':-1,'加油站':-1,'電影院':-1,'停車場':-1,'餐廳':-1} #用來記錄該地點類型目前距離tmp_now最近的秒數
        tmp_now=now-timedelta(days=i)
        tmp_later=two_hour_later-timedelta(days=i)
        #tmp_later=tmp_later.strftime('%Y-%m-%dT%X')+'.000Z' #轉為str
        tmp_before=two_hour_before-timedelta(days=i)
        #tmp_before=tmp_before.strftime('%Y-%m-%dT%X')+'.000Z' #轉為str

        #只取前後兩個小時內的資料
        limit_records = mongo.db.googleLocation.find({'id': auth_id,'locationTime': {
            '$gte': tmp_before,
            '$lte': tmp_later
        }}) #Bson
        limit_resp_tmp = dumps(limit_records) #Json
        limit_tmp_dict = json.loads(limit_resp_tmp) #dict

        #記錄該地點類型目前距離tmp_now最近的秒數
        for rec in limit_tmp_dict:
            tmp_dis=rec['locationTime']-tmp_now
            tmp_dis=abs(tmp_dis.total_seconds())
            if(compare[rec['locationType']]==-1):
                compare[rec['locationType']]=tmp_dis
            elif(compare[rec['locationType']]>tmp_dis): #取差距小的存入
                compare[rec['locationType']]=tmp_dis
        result = sorted(compare,key = compare.get, reverse=True) #由小到大 #list['停車場','加油站'...]
        #若值為-1就表示該時間區間內沒有有關該地點類型的交易紀錄->place_count不加
        b_count=len(result) #5
        tmp_value=0
        for i in range(len(result)):
            key=convert[result[i]] #int
            value= compare[result[i]]#int
            if(value!=-1):
                if(tmp_value==0):
                    tmp_value=value
                    place_count[key]+=b_count
                else:
                    if(tmp_value==value):
                        place_count[key]+=b_count
                    else:
                        b_count-=1
                        place_count[key]+=b_count
                        tmp_value=value
    new_result = sorted(place_count,key = place_count.get, reverse=True) #由大到小
    n_count=len(new_result)
    for i in range(len(new_result)):
        context_sum[new_result[i]]+=n_count
        n_count-=1
    return context_sum 
        
#與所有地點類型最近的那個點比較
#destinations=[五個地點的座標] (按照01234)
def distance(origin, destinations, context_sum, weight):
    duration_result=[]
    count=0
    for destination in destinations:
        #回傳走到目的地所需的秒數(越大越遠)
        result = gmaps.distance_matrix(origin, destination, mode='walking')['rows'][0]['elements'][0] ['duration']['value']
        duration_result.append({'id':count,'duration_time':result})
        count+=1
    result = sorted(duration_result,key = lambda i: i['duration_time']) #由小到大->由近到遠
    dis_count=len(result)
    tmp_value=0
    for i in range(len(result)):
        #key=int(list(result[i].keys())[0]) #int
        #value=int(list(result[i].values())[0]) #int
        key=result[i]['id']
        value=result[i]['duration_time']
        if(i==0):
            tmp_value=value
            context_sum[key]+=len(result)
        elif(i>=0):
            if(tmp_value==value):
                context_sum[key]+=dis_count
            else:
                dis_count-=1
                context_sum[key]+=dis_count
                tmp_value=value
    return context_sum

# 地點類型偏好
# 0百貨 1加油 2電影 3停車 4餐廳 
# 待修改
def place_preference(auth_id, context_sum,weight):
    records = mongo.db.customer.find_one({'id': auth_id}) #Bson
    resp_tmp = dumps(records) #Json
    tmp_dict = json.loads(resp_tmp) #dict
    if(tmp_dict['mall'] is not None):
        context_sum[0]+=1
    if(tmp_dict['gas_station'] is not None):
        context_sum[1]+=1
    if(tmp_dict['parking_lot'] is not None):
        context_sum[2]+=1
    if(tmp_dict['restaurant'] is not None):
        context_sum[3]+=1
    if(tmp_dict['theater'] is not None):
        context_sum[4]+=1
    return context_sum

# 0百貨 1加油 2電影 3停車 4餐廳 
# (1)會開車&時速>30
# (2)會開車&時速<30
# (3)不會開車 -> 不加分
def speed(speed_now, auth_id, context_sum, weight):
    if(can_drive_or_not(auth_id)=='yes'):
        speed_now=int(speed_now)
        if(speed_now>=30):
            context_sum[1]+=3
            context_sum[3]+=3
        else:
            context_sum[1]+=1
            context_sum[3]+=1
    return context_sum

#==============================================================辦卡推薦(常去地點)==============================================================#

#db['!all'].aggregate([
#  {$match:
#    {'GENDER': 'F',
#     'DOB':
#      { $gte: 19400801,
#        $lte: 20131231 } } },
#  {$group : {_id : "$by_user", num_tutorial : {$sum : 1}}}
#])
# 計算最常去的地點名稱
# 回傳最常去的地點名稱、地點類別、經緯度：{'name':地點名稱,'type':地點類別,'lat','lng'}
def find_freq_place(auth_id):
    count_dict=dict()
    resp=dict()
    records = mongo.db.googleLocation.find({'id': auth_id}) #Bson
    resp_tmp = dumps(records) #Json
    tmp_dict = json.loads(resp_tmp) #dict
    for record in tmp_dict:
        if record['locationName'] in count_dict.keys():
            count_dict[record['locationName']]+=1
        else: #新地點
            count_dict[record['locationName']]=1
    result=sorted(count_dict.items(), key=lambda x: x[1], reverse=True) #由大到小 回傳：[(地點名稱,筆數),(地點名稱,筆數)...]
    #print('freq place result:',result)
    # 找出最常去的地點，並回傳{'name':地點名稱,'type':地點類別,'lat','lng'}
    records = mongo.db.googleLocation.find_one({'locationName': result[0][0]}) #Bson
    resp_tmp = dumps(records) #Json
    tmp_dict = json.loads(resp_tmp) #dict
    resp['name']=result[0][0]
    resp['type']=tmp_dict['locationType']
    resp['lat']=tmp_dict['latitude']
    resp['lng']=tmp_dict['longitude']
    #print('resp: ',resp)
    return resp

#find_similar
def find_similar_(auth_id,feature_value):
    df = pd.read_csv('/Users/peggy/Desktop/Tweet_CARD_code/prefer2.0.csv')
    x = df[['age', 'sex', 'annualIncome', 'expenseMonth','mall', 'gas_station', 'theater', 'parking_lot',
       'restuarant']][0:239]
    #k-means++的方法就是讓初始中心之間的距離盡可能地遠使得加速 迭代過程的收斂
    kmeans_fit = cluster.KMeans(n_clusters=16, algorithm='auto', init='k-means++', random_state=10).fit(x)
    cluster_labels = kmeans_fit.labels_

    #classification tree
    feature_cols = ['age', 'sex', 'annualIncome','expenseMonth']
    X = x[feature_cols] # Features
    y = cluster_labels
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=1)
    clf = DecisionTreeClassifier(criterion='entropy')
    # Train Decision Tree Classifer
    clf = clf.fit(X_train,y_train)

    pre_list=tree_to_compare(clf,feature_cols,feature_value)
    less_pre=pre_list[0]
    grt_pre=pre_list[1]
    records = mongo.db.customer.find({'id': auth_id})#Bson
    resp_tmp = dumps(records) #Json
    i = json.loads(resp_tmp) #dict
    d=dict()
    for i in grt_pre.keys():
        if i in d.keys():
            d[i].append(grt_pre[i])
        else:
            d[i]=[]
            d[i].append(grt_pre[i])
    for j in less_pre.keys():
        if j in d.keys():
            d[j].append(less_pre[j])
        else:
            d[j]=[0]
            d[j].append(less_pre[j])
    find_string='{"status":"old",'
    for name, value in d.items(): #value:list
        if list(d.keys()).index(name) ==0:
            if(len(value)==1): #只有les
            	find_string=find_string+'"'+str(name)+'":{"$lte":'+str(value[0])+'}'
            else:
            	find_string=find_string+'"'+str(name)+'":{"$gt":'+str(value[0])+',"$lte":'+str(value[1])+'}'
        else:
            if(len(value)==1): #只有les
            	find_string=find_string+',"'+str(name)+'":{"$lte":'+str(value[0])+'}'
            else:
            	find_string=find_string+',"'+str(name)+'":{"$gt":'+str(value[0])+',"$lte":'+str(value[1])+'}'
    find_string=find_string+'}'
    find_string = json.loads(find_string) #dict
    
    records = mongo.db.customer.find(find_string).sort('tagID',-1) #Bson
    resp_tmp = dumps(records) #Json
    person = json.loads(resp_tmp) #dict

    return person

def tree_to_compare(tree, feature_names,feature_value):
    tree_ = tree.tree_
    feature_name = [
        feature_names[i] if i != _tree.TREE_UNDEFINED else "undefined!"
        for i in tree_.feature
    ]
    #print("def tree({}):".format(", ".join(feature_names)))

    def recurse(node, depth, less_pre, grt_pre): #less_pre:{'income':430000,'age':40}
        #indent = "  " * depth
        if tree_.feature[node] != _tree.TREE_UNDEFINED:
            name = feature_name[node] #str
            threshold = tree_.threshold[node] #float
            #print("{}if {} <= {}:".format(indent, name, threshold))
            if feature_value[name]<=threshold:
                less_pre[name]=threshold
                pre_list=recurse(tree_.children_left[node], depth + 1,less_pre,grt_pre)
                return pre_list
            #print("{}else:  # if {} > {}".format(indent, name, threshold))
            else:
                grt_pre[name]=threshold
                pre_list=recurse(tree_.children_right[node], depth + 1,less_pre,grt_pre)
                return pre_list
        else:
            #print("{}return {}".format(indent, tree_.value[node][0]))        
            return [less_pre,grt_pre]
        
    pre_list=recurse(0, 1,{},{})
    return pre_list   

#==============================================================辦卡推薦(當下地點)==============================================================#

# 找出目前定位地點名稱，若此經緯度並非特定地點，就會找選離他最近的那個地點，且是我們有做的地點類別
# radius=5000公尺=5公里
# 回傳：{'name':地點名稱,'type':地點類別,'lat','lng':(str)}
def find_place_nearby(lat,lng):
    resp=dict()
    destinations=[]
    count=0
    not_match=1
    lat_lng=lat+", "+lng
    geolocator = Nominatim(user_agent="tweet card")
    location = geolocator.reverse(lat_lng)
    print(location.raw)
    if location.raw['osm_type']=='node' or location.raw['osm_type']=='way' or location.raw['osm_type']=='relation':
        not_match=0
        if 'amenity' in location.raw['address'].keys():
            location_name = location.raw['address']['amenity']
        elif 'shop' in location.raw['address'].keys():
            location_name = location.raw['address']['shop']
        print('location name: ',location_name)
        find_place_result=gmaps.find_place(input=location_name, input_type="textquery",fields=['place_id','formatted_address','types','geometry/location/lat','geometry/location/lng'])
        print('find_place_result',find_place_result)
        node_type=find_place_result['candidates'][0]['types']
        resp['name']=location_name
        resp['lat']=lat
        resp['lng']=lng
        #node_type=location1.raw['type']
        if 'cafe' in node_type or 'restaurant' in node_type:
            resp['type']='餐廳'
            return resp
        elif 'parking' in node_type:
            resp['type']='停車場'
            return resp
        elif 'movie_theater' in node_type:
            resp['type']='電影院'
            return resp
        elif 'gas_station' in node_type:
            resp['type']='加油站'
            return resp
        elif 'department_store' in node_type or 'shopping_mall' in node_type:
            resp['type']='百貨公司'
            return resp
        else:
            not_match=1
    if not_match==1: #not a certain node
        c_radar_results = gmaps.places_nearby(location =lat+','+lng, radius = 5000, type='cafe')
        c_new_radar_results = c_radar_results['results']
        for i in c_new_radar_results:
            location=(str(i['geometry']['location']['lat']),str(i['geometry']['location']['lng']))
            destinations.append({'count':count,'coordinate':location, 'name':i['name'], 'type':'餐廳'})
            count+=1
                
        r_radar_results = gmaps.places_nearby(location =lat+','+lng, radius = 5000, type='restaurant')
        r_new_radar_results = r_radar_results['results']
        for i in r_new_radar_results:
            location=(str(i['geometry']['location']['lat']),str(i['geometry']['location']['lng']))
            destinations.append({'count':count,'coordinate':location, 'name':i['name'], 'type':'餐廳'})
            count+=1
            
        p_radar_results = gmaps.places_nearby(location =lat+','+lng, radius = 5000, type='parking')
        p_new_radar_results = p_radar_results['results']
        for i in p_new_radar_results:
            location=(str(i['geometry']['location']['lat']),str(i['geometry']['location']['lng']))
            destinations.append({'count':count,'coordinate':location, 'name':i['name'], 'type':'停車場'})
            count+=1
            
        m_radar_results = gmaps.places_nearby(location =lat+','+lng, radius = 5000, type='movie_theater')
        m_new_radar_results = m_radar_results['results']
        for i in m_new_radar_results:
            location=(str(i['geometry']['location']['lat']),str(i['geometry']['location']['lng']))
            destinations.append({'count':count,'coordinate':location, 'name':i['name'], 'type':'電影院'})
            count+=1
            
        g_radar_results = gmaps.places_nearby(location =lat+','+lng, radius = 5000, type='gas_station')
        g_new_radar_results = g_radar_results['results']
        for i in g_new_radar_results:
            location=(str(i['geometry']['location']['lat']),str(i['geometry']['location']['lng']))
            destinations.append({'count':count,'coordinate':location, 'name':i['name'], 'type':'加油站'})
            count+=1
            
        s_radar_results = gmaps.places_nearby(location =lat+','+lng, radius = 5000, type='shopping_mall')
        s_new_radar_results = s_radar_results['results']
        for i in s_new_radar_results:
            location=(str(i['geometry']['location']['lat']),str(i['geometry']['location']['lng']))
            destinations.append({'count':count,'coordinate':location, 'name':i['name'], 'type':'百貨公司'})
            count+=1
            
        d_radar_results = gmaps.places_nearby(location =lat+','+lng, radius = 5000, type='department_store')
        d_new_radar_results = d_radar_results['results']
        for i in d_new_radar_results:
            location=(str(i['geometry']['location']['lat']),str(i['geometry']['location']['lng']))
            destinations.append({'count':count,'coordinate':location, 'name':i['name'], 'type':'百貨公司'})
            count+=1
                
        origin=(lat+','+lng)
        duration_result=[]
        for destination in destinations:
            #回傳走到目的地所需的秒數(越大越遠)
            tmp_result = gmaps.distance_matrix(origin, destination['coordinate'], mode='walking')['rows'][0]['elements'][0] ['duration']['value']
            duration_result.append({'id':destination['count'],'name':destination['name'],'coordinate':destination['coordinate'],'type':destination['type'],'duration_time':tmp_result}) 
        result = sorted(duration_result,key = lambda i: i['duration_time'])
        resp['name']=result[0]['name']
        resp['lat']=result[0]['coordinate'][0]
        resp['lng']=result[0]['coordinate'][1]
        resp['type']=result[0]['type']
        return resp

#==============================================================辦卡推薦==============================================================#

# for 辦卡推薦
# 針對最常去的地點(或一個地點)來做推薦
# 回傳：{'recommend_result':{'緯度':,'經度':,'地點名稱':,'fir_recommend_cardID':...}}
def recommend_discount_for_place(auth_id, place, is_sim_auth):
    resp=dict()
    #百貨公司
    if place['type']=='百貨公司':
        print('mall')
        resp_cash=recommend.cash_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id, is_sim_auth,1)
        resp_point=recommend.point_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],'百貨',auth_id, is_sim_auth,1)   
        resp_park=recommend.parking_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id, is_sim_auth,1)
        # 現金回饋優先
        if(recommend.cash_or_point(auth_id)=='cash'):
            resp['recommed_result']=resp_cash
            resp['recommed_result'].update(resp_point) 
            resp['recommed_result'].update(resp_park)
        # 紅利回饋優先
        else:
            resp['recommed_result']=resp_point
            resp['recommed_result'].update(resp_cash)
            resp['recommed_result'].update(resp_park)
    #加油站    
    elif place['type']=='加油站':
        print('gas station')
        # 加油 [現金 紅利]
        resp_gas=recommend.gas_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id, is_sim_auth,1)
        resp_cash=recommend.cash_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id, is_sim_auth,1)
        resp_point=recommend.point_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],'加油',auth_id, is_sim_auth,1)
        if(recommend.cash_or_point(auth_id)=='cash'):
            resp['recommed_result']=resp_gas 
            resp['recommed_result'].update(resp_cash)
            resp['recommed_result'].update(resp_point)
        # 加油 [紅利 現金]
        else:
            resp['recommed_result']=resp_gas 
            resp['recommed_result'].update(resp_point)
            resp['recommed_result'].update(resp_cash)
    #電影院    
    elif place['type']=='電影院':
        print('theater')
        # 電影 [現金 紅利]
        resp_mov=recommend.movie_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id, is_sim_auth,1)
        resp_cash=recommend.cash_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id, is_sim_auth,1)
        resp_point=recommend.point_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],'電影',auth_id, is_sim_auth,1)
        if(recommend.cash_or_point(auth_id)=='cash'):
            resp['recommed_result']=resp_mov
            resp['recommed_result'].update(resp_cash)
            resp['recommed_result'].update(resp_point)
        # 電影 [紅利 現金]
        else:
            resp['recommed_result']=resp_mov
            resp['recommed_result'].update(resp_point)
            resp['recommed_result'].update(resp_cash)

    #停車場    
    elif place['type']=='停車場':
        print('i am park')
        # 停車 [現金 紅利]
        resp_park=recommend.parking_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id, is_sim_auth,1)
        resp_cash=recommend.cash_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id, is_sim_auth,1)
        resp_point=recommend.point_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],'停車',auth_id, is_sim_auth,1)    
        if(recommend.cash_or_point(auth_id)=='cash'):
            resp['recommed_result']=resp_park
            resp['recommed_result'].update(resp_cash)
            resp['recommed_result'].update(resp_point)
        # 停車 [紅利 現金]
        else:
            resp['recommed_result']=resp_park
            resp['recommed_result'].update(resp_point)
            resp['recommed_result'].update(resp_cash)
            
    #餐廳    
    elif place['type']=='餐廳': 
        print('restuarant')
        resp_cash=recommend.cash_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id, is_sim_auth,1)
        resp_point=recommend.point_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],'百貨',auth_id, is_sim_auth,1)     
        # 現金回饋優先
        if(recommend.cash_or_point(auth_id)=='cash'):
            resp['recommed_result']=resp_cash
            resp['recommed_result'].update(resp_point)   
        # 紅利回饋優先
        else:
            resp['recommed_result']=resp_point 
            resp['recommed_result'].update(resp_cash)
    return resp

#==============================================================通用功能==============================================================# 

#判斷用戶是老手還是新手->可用來改變用戶身份狀態
#判斷他有沒有三個月以上的記帳紀錄且筆數有250筆以上
#回傳str(novice,senior)
#目前先暫時寫在這，到時候再移到context那邊，之後用import的方式來main這邊用
def user_status(auth_id):
    records = mongo.db.bookkeepingRecord.find({'id':auth_id}) #Bson
    resp_tmp = dumps(records) #Json
    tmp_dict = json.loads(resp_tmp) #dict
    count=len(tmp_dict)
    #先比較筆數有無超過250，再比較有沒有滿三個月
    if(count>=200):
        today=datetime.today()
        three_months_before=add_months(today,-3)
        fir_records = mongo.db.bookkeepingRecord.find({'id':auth_id}).limit(1) #Bson
        fir_resp_tmp = dumps(fir_records) #Json
        fir_tmp_dict = json.loads(fir_resp_tmp) #dict
        dd=int(fir_tmp_dict[0]['consumeTime']['$date'])
        dt_obj = datetime.fromtimestamp(dd/1000.0)
        if(dt_obj<three_months_before): #有更早的紀錄
            return 'old'
        return 'new'
        #第二種比法(考慮到可能會不照時間順序記帳)
        #today=datetime.today()
        #three_months_before=add_months(today,-3)
        #for record in tmp_dict:
        #    if(fir_tmp_dict['consumeTime']<three_months_before): #有更早的紀錄
        #        return 'old'
        #    return 'new'
    else:
        return 'new'

#用來增減month(return date)
def add_months(sourcedate, months):
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, calendar.monthrange(year,month)[1])
    return datetime(year, month, day,sourcedate.time().hour,sourcedate.time().minute,sourcedate.time().second)

# 判斷是否會開車
# (1)透過記帳紀錄有無加油跟停車來判斷(google location那個table)
# (2)透過勾選優惠偏好(停車、加油)與地點偏好(停車場、加油站)
# 回傳'yes','no'
def can_drive_or_not(auth_id):
    #目前還在找怎麼直接用資料庫指令來篩選
    #records = mongo.db.googleLocation.find({'身分證字號': 身分證字號,'地點類型':{ '$in': ['加油站', '停車場'] }}) #Bson
    #記帳紀錄
    records = mongo.db.googleLocation.find({'id': auth_id})
    resp_tmp = dumps(records) #Json
    tmp_dict = json.loads(resp_tmp) #dict
    for i in tmp_dict:
        if(i['locationType'] in ['加油站','停車場']):
            return 'yes'
    
    #地點偏好和優惠偏好
    c_records = mongo.db.customer.find_one({'id': auth_id})
    c_resp_tmp = dumps(c_records) #Json
    c_tmp_dict = json.loads(c_resp_tmp) #dict
    if(c_tmp_dict['parking_lot']==1 or c_tmp_dict['gas_station']==1 or c_tmp_dict['parkingRewPref']==1 or c_tmp_dict['gasRewPref']==1):
        return 'yes'
    else:
        return 'no'

#==============================================================備案們==============================================================#
# for真小白
# 找與他相似的人們
# 回傳該人在Customer表裡的所有欄位(dict)
def find_similar(auth_id):
    records = mongo.db.customer.find_one({'id': auth_id}) #Bson
    resp_tmp = dumps(records) #Json
    i = json.loads(resp_tmp) #dict
    if(i['income']<=435000):
        if(i['income']<=165000):
            records = mongo.db.customer.find({'income':{'$lte': 165000}}) #Bson
            resp_tmp = dumps(records) #Json
            person = json.loads(resp_tmp) #dict
        else:
            if(i['income']<=315000):
                records = mongo.db.customer.find({'income':{'$gt': 165000, '$lte': 315000}}) #Bson
                resp_tmp = dumps(records) #Json
                person = json.loads(resp_tmp) #dict
            else:
                records = mongo.db.customer.find({'income':{'$gt': 315000, '$lte': 435000}}) #Bson
                resp_tmp = dumps(records) #Json
                person = json.loads(resp_tmp) #dict
    else:
        if(i['income']<=760000):
            if(i['income']<=555000):
                if(i['avg_cost']<=170000):
                    records = mongo.db.customer.find({'income':{'$gt': 435000, '$lte': 555000},'avg_cost':{'$lte': 170000}}) #Bson
                    resp_tmp = dumps(records) #Json
                    person = json.loads(resp_tmp) #dict
                else:
                    records = mongo.db.customer.find({'income':{'$gt': 435000, '$lte': 555000},'avg_cost':{'$gt': 170000}}) #Bson
                    resp_tmp = dumps(records) #Json
                    person = json.loads(resp_tmp) #dict
            else:
                if(i['income']<=625000):
                    records = mongo.db.customer.find({'income':{'$gt': 555000, '$lte': 625000}}) #Bson
                    resp_tmp = dumps(records) #Json
                    person = json.loads(resp_tmp) #dict
                else:
                    if(i['avg_cost']<145000):
                        records = mongo.db.customer.find({'income':{'$gt': 625000, '$lte': 760000},'avg_cost':{'$lt': 145000}}) #Bson
                        resp_tmp = dumps(records) #Json
                        person = json.loads(resp_tmp) #dict
                    else:
                        records = mongo.db.customer.find({'income':{'$gt': 625000, '$lte': 760000},'avg_cost':{'$gte': 145000}}) #Bson
                        resp_tmp = dumps(records) #Json
                        person = json.loads(resp_tmp) #dict
        else: 
            if(i['income']<=1150000):
                if(i['income']<=935000):
                    records = mongo.db.customer.find({'income':{'$gt': 760000, '$lte': 935000}}) #Bson
                    resp_tmp = dumps(records) #Json
                    person = json.loads(resp_tmp) #dict
                else:
                    if(i['avg_cost']<280000):
                        records = mongo.db.customer.find({'income':{'$gt': 935000, '$lte': 1150000},'avg_cost':{'$lt': 280000}}) #Bson
                        resp_tmp = dumps(records) #Json
                        person = json.loads(resp_tmp) #dict
                    else:
                        records = mongo.db.customer.find({'income':{'$gt': 935000, '$lte': 1150000},'avg_cost':{'$gte': 280000}}) #Bson
                        resp_tmp = dumps(records) #Json
                        person = json.loads(resp_tmp) #dict
            else: 
                if(i['income']<=1300000):
                    records = mongo.db.customer.find({'income':{'$gt': 1150000, '$lte': 1300000}}) #Bson
                    resp_tmp = dumps(records) #Json
                    person = json.loads(resp_tmp) #dict
                else: 
                    if(i['income']<=1750000):
                        if(i['avg_cost']<=300000):
                            records = mongo.db.customer.find({'income':{'$gt': 1300000, '$lte': 1750000},'avg_cost':{'$lte': 300000}}) #Bson
                            resp_tmp = dumps(records) #Json
                            person = json.loads(resp_tmp) #dict
                        else:
                            records = mongo.db.customer.find({'income':{'$gt': 1300000, '$lte': 1750000},'avg_cost':{'$gt': 300000}}) #Bson
                            resp_tmp = dumps(records) #Json
                            person = json.loads(resp_tmp) #dict
                    else:
                        if(i['income']<=2250000):
                            records = mongo.db.customer.find({'income':{'$gt': 1750000, '$lte': 225000}}) #Bson
                            resp_tmp = dumps(records) #Json
                            person = json.loads(resp_tmp) #dict
                        else:
                            if(i['income']<=4250000):
                                records = mongo.db.customer.find({'income':{'$gt': 2250000, '$lte': 4250000}}) #Bson
                                resp_tmp = dumps(records) #Json
                                person = json.loads(resp_tmp) #dict
                            else:
                                records = mongo.db.customer.find({'income':{'$gt': 4250000}}) #Bson
                                resp_tmp = dumps(records) #Json
                                person = json.loads(resp_tmp) #dict
    return person

# version2:不包含大賣場和便利商店
# for假小白與真小白
def classification(auth_id, context_sum, weight):
    # personal context
    # ['age', 'sex', 'income', 'avg_cost'] 
    # 0百貨 1加油 2電影 3停車 4餐廳 
    records = mongo.db.customer.find_one({'id': auth_id}) #Bson
    resp_tmp = dumps(records) #Json
    tmp_dict = json.loads(resp_tmp) #dict
    i=tmp_dict
    if(i['income']<=435000):
        if(i['income']<=165000):
            #4: 4>2>0>1=3
            context_sum[4]+=5
            context_sum[2]+=4
            context_sum[0]+=3
            context_sum[1]+=2
            context_sum[3]+=2
        else:
            if(i['income']<=315000):
                #15: 4>0=1=3>2
                context_sum[4]+=5
                context_sum[0]+=4
                context_sum[1]+=4
                context_sum[3]+=4
                context_sum[2]+=1
            else:
                #0: 1=3>4>0>2
                context_sum[1]+=5
                context_sum[3]+=5
                context_sum[4]+=3
                context_sum[0]+=2
                context_sum[2]+=1
    else:
        if(i['income']<=760000):
            if(i['income']<=555000):
                if(i['avg_cost']<=170000):
                    #13: 1=3>4>0>2
                    context_sum[1]+=5
                    context_sum[3]+=5
                    context_sum[4]+=3
                    context_sum[0]+=2
                    context_sum[2]+=1
                else:
                    #7: 1=3>4>0>2
                    context_sum[1]+=5
                    context_sum[3]+=5
                    context_sum[4]+=3
                    context_sum[0]+=2
                    context_sum[2]+=1
            else:
                if(i['income']<=625000):
                    #8: 1=3>4>0>2
                    context_sum[1]+=5
                    context_sum[3]+=5
                    context_sum[4]+=3
                    context_sum[0]+=2
                    context_sum[2]+=1
                else:
                    if(i['avg_cost']<145000):
                        #14: 4>1=3>0>2
                        context_sum[4]+=5
                        context_sum[1]+=4
                        context_sum[3]+=4
                        context_sum[0]+=2
                        context_sum[2]+=1
                    else:
                        #7: 1=3>4>0>2
                        context_sum[1]+=5
                        context_sum[3]+=5
                        context_sum[4]+=3
                        context_sum[0]+=2
                        context_sum[2]+=1
        else:
            if(i['income']<=1150000):
                if(i['income']<=935000):
                    #3: 1=3>4>0>2
                    context_sum[1]+=5
                    context_sum[3]+=5
                    context_sum[4]+=3
                    context_sum[0]+=2
                    context_sum[2]+=1
                else:
                    if(i['avg_cost']<280000):
                        #10: 2=4>5>6>1>0>3
                        context_sum[1]+=5
                        context_sum[3]+=5
                        context_sum[4]+=3
                        context_sum[0]+=2
                        context_sum[2]+=1
                    else:
                        #12: 1=3=4>0=2
                        context_sum[1]+=5
                        context_sum[3]+=5
                        context_sum[4]+=5
                        context_sum[0]+=2
                        context_sum[2]+=2
            else:
                if(i['income']<=1300000):
                    #5: 1=3>0>4>2
                    context_sum[1]+=5
                    context_sum[3]+=5
                    context_sum[0]+=3
                    context_sum[4]+=2
                    context_sum[2]+=1
                else:
                    if(i['income']<=1750000):
                        if(i['avg_cost']<=300000):
                            #1: 2=4>5>0>1=6>3
                            context_sum[1]+=5
                            context_sum[3]+=5
                            context_sum[4]+=3
                            context_sum[0]+=2
                            context_sum[2]+=1
                        else:
                            #11: 1=3>0=4>2
                            context_sum[1]+=5
                            context_sum[3]+=5
                            context_sum[0]+=3
                            context_sum[4]+=3
                            context_sum[2]+=1
                    else:
                        if(i['income']<=2250000):
                            #6: 1=2=3>4>0
                            context_sum[1]+=5
                            context_sum[2]+=5
                            context_sum[3]+=5
                            context_sum[4]+=2
                            context_sum[0]+=1
                        else:
                            if(i['income']<=4250000):
                                #9: 1=3=4>0=2
                                context_sum[1]+=5
                                context_sum[3]+=5
                                context_sum[4]+=5
                                context_sum[0]+=2
                                context_sum[2]+=2
                            else:
                                #2: 0=1=3=4>2
                                context_sum[0]+=5
                                context_sum[1]+=5
                                context_sum[3]+=5
                                context_sum[4]+=5
                                context_sum[2]+=1
    return context_sum

# 紅利 現金 電影 停車 加油
# 百貨：[現金 紅利] (停車)
# 加油站：加油 [紅利 現金]
# 停車場：停車 [現金 紅利]
# 電影院：電影 [現金 紅利]
# 餐廳：[現金 紅利]
# 0百貨 1加油 2電影 3停車 4餐廳 
# 優惠偏好(待商討要要怎麼用)
# 待修改(要理解勾選表單回傳的格式是什麼)
def dicount_preference(auth_id, context_sum, weight):
    records = mongo.db.customer.find({'id': auth_id}) #Bson
    resp_tmp = dumps(records) #Json
    tmp_dict = json.loads(resp_tmp) #dict
    if(tmp_dict[0]['現金回饋優惠'] is not None):
        context_sum[0]+=1
        context_sum[1]+=1
        context_sum[2]+=1
        context_sum[3]+=1
        context_sum[4]+=1
    if(tmp_dict[0]['紅利回饋優惠'] is not None):
        context_sum[0]+=1
        context_sum[1]+=1
        context_sum[2]+=1
        context_sum[3]+=1
        context_sum[4]+=1
    if(tmp_dict[0]['停車優惠'] is not None):
        context_sum[0]+=1
        context_sum[3]+=1
    if(tmp_dict[0]['加油優惠'] is not None):
        context_sum[1]+=1
    if(tmp_dict[0]['電影優惠'] is not None):
        context_sum[2]+=1
    return context_sum

# version1:包含大賣場和便利商店
# for假小白與真小白
def classification_v1(auth_id, context_sum):
    # personal context
    # ['age', 'sex', 'income', 'avg_cost'] 
    # 0便利 1百貨 2加油 3電影 4停車 5餐廳 6大賣場
    records = mongo.db.customer.find({'id': auth_id}) #Bson
    resp_tmp = dumps(records) #Json
    tmp_dict = json.loads(resp_tmp) #dict
    i=tmp_dict[0]
    if(i['income']<=435000):
        if(i['income']<=165000):
            #4: 5>0>6>3>1>2=4
            context_sum[5]+=7
            context_sum[0]+=6
            context_sum[6]+=5
            context_sum[3]+=4
            context_sum[1]+=3
            context_sum[2]+=2
            context_sum[4]+=2
        else:
            if(i['income']<=315000):
                #15: 6>0=5>1=2=4>3
                context_sum[6]+=7
                context_sum[0]+=6
                context_sum[5]+=6
                context_sum[1]+=4
                context_sum[2]+=4
                context_sum[4]+=4
                context_sum[3]+=1
            else:
                #0: 6>2=4>0=5>1>3
                context_sum[6]+=7
                context_sum[2]+=6
                context_sum[4]+=6
                context_sum[0]+=4
                context_sum[5]+=4
                context_sum[1]+=2
                context_sum[3]+=1
    else:
        if(i['income']<=760000):
            if(i['income']<=555000):
                if(i['avg_cost']<=170000):
                    #13: 6>2=4>5>1>0>3
                    context_sum[6]+=7
                    context_sum[2]+=6
                    context_sum[4]+=6
                    context_sum[5]+=4
                    context_sum[1]+=3
                    context_sum[0]+=2
                    context_sum[3]+=1
                else:
                    #7: 0=2=4>6>5>1>3
                    context_sum[0]+=7
                    context_sum[2]+=7
                    context_sum[4]+=7
                    context_sum[6]+=4
                    context_sum[5]+=3
                    context_sum[1]+=2
                    context_sum[3]+=1
            else:
                if(i['income']<=625000):
                    #8: 2=4=6>5>1>3>0
                    context_sum[2]+=7
                    context_sum[4]+=7
                    context_sum[6]+=7
                    context_sum[5]+=4
                    context_sum[1]+=3
                    context_sum[3]+=2
                    context_sum[0]+=1
                else:
                    if('age'<56):
                        #14: 5>6>0>2=4>1>3
                        context_sum[5]+=7
                        context_sum[6]+=6
                        context_sum[0]+=5
                        context_sum[2]+=4
                        context_sum[4]+=4
                        context_sum[1]+=2
                        context_sum[3]+=1
                    else:
                        #7: 0=2=4>6>5>1>3
                        context_sum[0]+=7
                        context_sum[2]+=7
                        context_sum[4]+=7
                        context_sum[6]+=4
                        context_sum[5]+=3
                        context_sum[1]+=2
                        context_sum[3]+=1
        else:
            if(i['income']<=1150000):
                if(i['income']<=935000):
                    #3: 2=4>5=6>0=1>3
                    context_sum[2]+=7
                    context_sum[4]+=7
                    context_sum[5]+=5
                    context_sum[6]+=5
                    context_sum[0]+=3
                    context_sum[1]+=3
                    context_sum[3]+=1
                else:
                    if(i['avg_cost']<280000):
                        #10: 2=4>5>6>1>0>3
                        context_sum[2]+=7
                        context_sum[4]+=7
                        context_sum[5]+=5
                        context_sum[6]+=4
                        context_sum[1]+=3
                        context_sum[0]+=2
                        context_sum[3]+=1
                    else:
                        #12: 2=4=5=6>0=1=3
                        context_sum[2]+=7
                        context_sum[4]+=7
                        context_sum[5]+=7
                        context_sum[6]+=7
                        context_sum[0]+=3
                        context_sum[1]+=3
                        context_sum[3]+=3
            else:
                if(i['income']<=1300000):
                    #5: 2=4>0=1=6>5>3
                    context_sum[2]+=7
                    context_sum[4]+=7
                    context_sum[0]+=5
                    context_sum[1]+=5
                    context_sum[6]+=5
                    context_sum[5]+=2
                    context_sum[3]+=1
                else:
                    if(i['income']<=1750000):
                        if(i['avg_cost']<=300000):
                            #1: 2=4>5>0>1=6>3
                            context_sum[2]+=7
                            context_sum[4]+=7
                            context_sum[5]+=5
                            context_sum[0]+=4
                            context_sum[1]+=3
                            context_sum[6]+=3
                            context_sum[3]+=1
                        else:
                            #11: 2=4>0=1=5=6>3
                            context_sum[2]+=7
                            context_sum[4]+=7
                            context_sum[0]+=5
                            context_sum[1]+=5
                            context_sum[5]+=5
                            context_sum[6]+=5
                            context_sum[3]+=1
                    else:
                        if(i['income']<=2250000):
                            #6: 2=3=4>5=6>0=1
                            context_sum[2]+=7
                            context_sum[3]+=7
                            context_sum[4]+=7
                            context_sum[5]+=4
                            context_sum[6]+=4
                            context_sum[0]+=2
                            context_sum[1]+=2
                        else:
                            if(i['income']<=4250000):
                                #9: 9: 2=4=5=6>0=1=3
                                context_sum[2]+=7
                                context_sum[4]+=7
                                context_sum[5]+=7
                                context_sum[6]+=7
                                context_sum[0]+=3
                                context_sum[1]+=3
                                context_sum[3]+=3
                            else:
                                #2: 0=1=2=4=5=6>3
                                context_sum[0]+=7
                                context_sum[1]+=7
                                context_sum[2]+=7
                                context_sum[6]+=7
                                context_sum[4]+=7
                                context_sum[5]+=7
                                context_sum[3]+=1
    return context_sum

#version1:只用place type來判斷他到底是哪個地點類型
#將某人的記帳紀錄轉為google location所需的欄位，並insert(只把屬於我們有做的地點類別的紀錄作轉換)
#google location:(身分證字號，手機號碼，地點名稱，地點類別，地址，經度，緯度，消費時間)
def bookkeeping_to_gLocation(auth_id, phoneNum):
    dict_place={'百貨公司':['department_store', 'shopping_mall'],'加油站': ['gas_station'],'電影院': ['movie_theater'],'停車場': ['parking'],'餐廳': ['cafe', 'restaurant']}
    records = mongo.db.bookkeepingRecord.find({'id': auth_id}) #Bson
    resp_tmp = dumps(records) #Json
    tmp_dict = json.loads(resp_tmp) #dict
    for record in tmp_dict:
        include=0 #判斷是否包含在我們要做的地點類型裡面，若無就不轉換也不存入
        resp_dict={}
        find_place_result=gmaps.find_place(input=record['消費商家'], input_type="textquery",fields=['place_id','formatted_address','types'])
        tmp_type=find_place_result['candidates'][0]['types'] #list
        for name, place_type in dict_place.items():
            for i in tmp_type:
                if(i in place_type):
                    resp_dict['locationType']=name
                    include=1
        if(include==1):
            resp_dict['身份證字號']=auth_id
            resp_dict['手機號碼']=phoneNum
            resp_dict['locationName']=record['消費商家']
            resp_dict['地址']=find_place_result['candidates'][0]['formatted_address']
            geocode_result = gmaps.geocode(find_place_result['candidates'][0]['formatted_address'])
            resp_dict['latitude']=geocode_result[0]['geometry']['location']['lat']
            resp_dict['longitude']=geocode_result[0]['geometry']['location']['lng']
            resp_dict['locationTime']=record['consumeTime']
            id = mongo.db.googleLocation.insert(resp_dict) # insert()會返回ObjectId類型的_id屬性
    resp = jsonify('Converted successfully!')
    resp.status_code = 200
    return resp

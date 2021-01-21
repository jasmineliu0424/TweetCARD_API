from app import app, mongo
import context
import recommend
from bson.json_util import dumps
from bson.objectid import ObjectId
from flask import jsonify, request,Response
import ast
import json
from datetime import datetime,timedelta
import googlemaps
gmaps = googlemaps.Client(key = 'AIzaSyBlUJmvjnGDlcV7WDYVLns8J85hnu7X_90')

# 取得更多資訊
@app.route('/get_card_inform/<cardID>', methods=['GET'])
def get_one_star(cardID):
    result = mongo.db.creditCard
    s = result.find_one({'cardID' : cardID})
    if s:
        
        output = {'cardName' : s['cardName'],
                    'ageLimit' : s['ageLimit'],
                    'annIncomeLimit' : s['annIncomeLimit'],
                    'annualFee' : s['annualFee'],
                    'annualFeeDes' : s['annualFeeDes']}

    else:
        output = "No such name"
    return jsonify({'result' : output})

# 用卡推薦(前面按鈕的部分)
# 計算出用戶對各地點類型的喜好程度並排序
# 判斷用戶是哪個身份(舊用戶/假小白(有信用卡無記帳紀錄)/真小白(無信用卡無記帳紀錄))->使用哪些情境
# 回傳: {'auth_id':auth:id,'recommend_order':['餐廳','加油站'....]}
# origin=('25.041583,121.543776')
# destinations=[('25.0418665', '121.5449721'),('25.0443825', '121.5368178'),('25.0460629', '121.5441717'),('25.0410177', '121.5442342'),('25.0404935', '121.5465572')]
@app.route('/api/recommend/use/<auth_id>/<speed_now>', methods=['GET'])
def recommend_place_for_use(auth_id, speed_now):
    place_name=['百貨公司','加油站','電影院','停車場','餐廳']
    context_sum=[0,0,0,0,0] #5個地點類型
    resp=dict()
    resp['result']=[]
    resp_result=dict()
    origin=('25.041583,121.543776')
    destinations=[('25.0418665', '121.5449721'),('25.0443825', '121.5368178'),('25.0460629', '121.5441717'),('25.0410177', '121.5442342'),('25.0404935', '121.5465572')]
    
    kmean_result=context.kmean_score_and_tree() #[clf,group_place_score,feature_cols]
    clf=kmean_result[0]
    group_place_score=kmean_result[1]
    feature_cols=kmean_result[2]

    feature_value=dict()
    records = mongo.db.customer.find_one({'id':auth_id}) #Bson
    resp_tmp = dumps(records) #Json
    tmp_dict = json.loads(resp_tmp) #dict
    feature_value['age']=tmp_dict['age']
    feature_value['sex']=tmp_dict['sex']
    feature_value['annualIncome']=tmp_dict['annualIncome']
    feature_value['expenseMonth']=tmp_dict['expenseMonth'] #要再寫一個計算的

    #真假小白
    if(context.user_status(auth_id)=='new'):
        records = mongo.db.cusCreditCard.find_one({'id':auth_id}) #Bson
        resp_tmp = dumps(records) #Json
        tmp_dict = json.loads(resp_tmp) #dict
        #真小白
        if(tmp_dict['cardID'] is None):
            context_sum=context.classification_(clf,group_place_score,feature_value,feature_cols,context_sum)
            context_sum=context.distance(origin, destinations, context_sum,1)
            context_sum=context.place_preference(auth_id, context_sum,1)
        #假小白
        else:
            context_sum=context.classification_(clf,group_place_score,feature_value,feature_cols,context_sum)
            context_sum=context.distance(origin, destinations, context_sum,1)
            context_sum=context.place_preference(auth_id, context_sum,1)
            context_sum=context.speed(speed_now, auth_id, context_sum,1)
    #舊用戶
    else:
        context_sum=context.book_keeping_record_by_time(auth_id, context_sum,1)
        context_sum=context.distance(origin, destinations, context_sum,1)
        context_sum=context.place_preference(auth_id, context_sum,1)
        context_sum=context.speed(speed_now, auth_id, context_sum,1)
    result_dict = dict(zip(place_name, context_sum))
    result = sorted(result_dict,key = result_dict.get, reverse=True) #由大到小
    resp_result['auth_id']=auth_id
    resp_result['recommend_order']=result
    resp['result'].append(resp_result)
    return resp             

# 用卡推薦
# 真小白->同辦卡推薦
# post 因為要取得app回傳的半徑五公里的地點名稱與經緯度{'destinations':[{'name':地點名稱,'lat','lng'},{'name':地點名稱,'lat','lng'}]}
# 百貨：[現金 紅利] (停車)
# 回傳：{'recommed_result':[{一個地點的三個推薦},{}]}
# 當用戶按下‘百貨公司’按鈕後
@app.route('/api/recommend/use/place/mall/<auth_id>', methods=['POST'])
def mall_recommend(auth_id):
    _json = request.data
    _dict = ast.literal_eval(_json.decode('utf-8')) #將json格式轉為string(decode)，再將string轉為dict(ast.literal_eval)

    records = mongo.db.cusCreditCard.find_one({'id':auth_id}) #Bson
    resp_tmp = dumps(records) #Json
    tmp_dict = json.loads(resp_tmp) #dict

    resp=dict()
    resp['recommed_result']=[]
    # 現金回饋優先
    if(recommend.cash_or_point(auth_id)=='cash'):
        # 真小白->同辦卡推薦
        if(context.user_status(auth_id)=='new' and tmp_dict['cardID'] is None):
            for place in _dict['destinations']:
                resp_cash=recommend.cash_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id,0,0)
                if resp_cash['thr_recommend_cardID'] is None: #推薦結果不足三個 -> 加上紅利回饋
                    resp_point=recommend.point_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],'百貨',auth_id,0,0)
                    new_resp=recommend.return_enough(resp_cash,resp_point)
                    #if new_resp['thr_recommend_cardID'] is None: # -> 加上停車優惠
                    #    resp_park=recommend.parking_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id)
                    #    new_resp=recommend.return_enough(new_resp,resp_park)
                    #    resp['recommed_result'].append(new_resp) 
                    #else:
                    #    resp['recommed_result'].append(new_resp) 
                    resp['recommed_result'].append(new_resp) 
                else:
                    resp['recommed_result'].append(resp_cash)  
        # 假小白和舊用戶
        else:
            for place in _dict['destinations']:
                resp_cash=recommend.cash_return_discount(place['lat'],place['lng'],place['name'],auth_id)
                if resp_cash['thr_recommend_cardID'] is None: #推薦結果不足三個 -> 加上紅利回饋
                    resp_point=recommend.point_return_discount(place['lat'],place['lng'],place['name'],'百貨',auth_id)
                    new_resp=recommend.return_enough(resp_cash,resp_point)
                    #if new_resp['thr_recommend_cardID'] is None: # -> 加上停車優惠
                    #    resp_park=recommend.parking_discount(place['lat'],place['lng'],place['name'],auth_id)
                    #    new_resp=recommend.return_enough(new_resp,resp_park)
                    #    resp['recommed_result'].append(new_resp) 
                    #else:
                    #    resp['recommed_result'].append(new_resp) 
                    resp['recommed_result'].append(new_resp) 
                else:
                    resp['recommed_result'].append(resp_cash)    
    # 紅利回饋優先
    else:
        # 真小白->同辦卡推薦
        if(context.user_status(auth_id)=='new' and tmp_dict['cardID'] is None):
            for place in _dict['destinations']:
                resp_point=recommend.point_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],'百貨',auth_id,0,0)
                if resp_point['thr_recommend_cardID'] is None: #推薦結果不足三個 -> 加上現金回饋
                    resp_cash=recommend.cash_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id,0,0)
                    new_resp=recommend.return_enough(resp_point,resp_cash)
                    #if new_resp['thr_recommend_cardID'] is None: # -> 加上停車優惠
                    #    resp_park=recommend.parking_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id)
                    #    new_resp=recommend.return_enough(new_resp,resp_park)
                    #    resp['recommed_result'].append(new_resp) 
                    #else:
                    #    resp['recommed_result'].append(new_resp) 
                    resp['recommed_result'].append(new_resp) 
                else:
                    resp['recommed_result'].append(resp_point) 
        # 假小白和舊用戶
        else: 
            for place in _dict['destinations']:
                resp_point=recommend.point_return_discount(place['lat'],place['lng'],place['name'],'百貨',auth_id)
                if resp_point['thr_recommend_cardID'] is None: #推薦結果不足三個 -> 加上現金回饋
                    resp_cash=recommend.cash_return_discount(place['lat'],place['lng'],place['name'],auth_id)
                    new_resp=recommend.return_enough(resp_point,resp_cash)
                    #if new_resp['thr_recommend_cardID'] is None: # -> 加上停車優惠
                    #    resp_park=recommend.parking_discount(place['lat'],place['lng'],place['name'],auth_id)
                    #    new_resp=recommend.return_enough(new_resp,resp_park)
                    #    resp['recommed_result'].append(new_resp) 
                    #else:
                    #    resp['recommed_result'].append(new_resp) 
                    resp['recommed_result'].append(new_resp) 
                else:
                    resp['recommed_result'].append(resp_point) 
    return resp

# 加油站：加油 [紅利 現金]
#當用戶按下‘加油站’按鈕後
@app.route('/api/recommend/use/place/gas_station/<auth_id>', methods=['POST'])
def gas_recommend(auth_id):
    _json = request.data
    _dict = ast.literal_eval(_json.decode('utf-8')) #將json格式轉為string(decode)，再將string轉為dict(ast.literal_eval)
    
    records = mongo.db.cusCreditCard.find_one({'id':auth_id}) #Bson
    resp_tmp = dumps(records) #Json
    tmp_dict = json.loads(resp_tmp) #dict

    resp=dict()
    resp['recommed_result']=[]
    # 加油 [現金 紅利]
    if(recommend.cash_or_point(auth_id)=='cash'):
        # 真小白->同辦卡推薦
        if(context.user_status(auth_id)=='new' and tmp_dict['cardID'] is None):
            for place in _dict['destinations']:
                resp_gas=recommend.gas_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id,0,0)
                if(resp_gas['thr_recommend_cardID'] is None): # 加上現金
                    resp_cash=recommend.cash_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id,0,0)
                    new_resp=recommend.return_enough(resp_gas,resp_cash)
                    if resp_cash['thr_recommend_cardID'] is None: # 加上紅利回饋
                        resp_point=recommend.point_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],'加油',auth_id,0,0)
                        new_resp=recommend.return_enough(new_resp,resp_point)
                        resp['recommed_result'].append(new_resp) 
                    else:
                        resp['recommed_result'].append(new_resp) 
                else:
                    resp['recommed_result'].append(resp_gas) 
        # 假小白和舊用戶
        else:
            for place in _dict['destinations']:
                resp_gas=recommend.gas_discount(place['lat'],place['lng'],place['name'],auth_id)
                if(resp_gas['thr_recommend_cardID'] is None): # 加上現金
                    resp_cash=recommend.cash_return_discount(place['lat'],place['lng'],place['name'],auth_id)
                    new_resp=recommend.return_enough(resp_gas,resp_cash)
                    if resp_cash['thr_recommend_cardID'] is None: # 加上紅利回饋
                        resp_point=recommend.point_return_discount(place['lat'],place['lng'],place['name'],'加油',auth_id)
                        new_resp=recommend.return_enough(new_resp,resp_point)
                        resp['recommed_result'].append(new_resp) 
                    else:
                        resp['recommed_result'].append(new_resp) 
                else:
                    resp['recommed_result'].append(resp_gas) 
    # 加油 [紅利 現金]
    else:
        # 真小白->同辦卡推薦
        if(context.user_status(auth_id)=='new' and tmp_dict['cardID'] is None):
            for place in _dict['destinations']:
                resp_gas=recommend.gas_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id,0,0)
                if(resp_gas['thr_recommend_cardID'] is None): # 加上紅利
                    resp_point=recommend.point_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],'加油',auth_id,0,0)
                    new_resp=recommend.return_enough(resp_gas,resp_point)
                    if resp_cash['thr_recommend_cardID'] is None: # 加上現金回饋
                        resp_cash=recommend.cash_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id,0,0)
                        new_resp=recommend.return_enough(new_resp,resp_cash)
                        resp['recommed_result'].append(new_resp) 
                    else:
                        resp['recommed_result'].append(new_resp) 
                else:
                    resp['recommed_result'].append(resp_gas) 
        # 假小白和舊用戶
        else:
            for place in _dict['destinations']:
                resp_gas=recommend.gas_discount(place['lat'],place['lng'],place['name'],auth_id)
                if(resp_gas['thr_recommend_cardID'] is None): # 加上紅利
                    resp_point=recommend.point_return_discount(place['lat'],place['lng'],place['name'],'加油',auth_id)
                    new_resp=recommend.return_enough(resp_gas,resp_point)
                    if resp_cash['thr_recommend_cardID'] is None: # 加上現金回饋
                        resp_cash=recommend.cash_return_discount(place['lat'],place['lng'],place['name'],auth_id)
                        new_resp=recommend.return_enough(new_resp,resp_cash)
                        resp['recommed_result'].append(new_resp) 
                    else:
                        resp['recommed_result'].append(new_resp) 
                else:
                    resp['recommed_result'].append(resp_gas) 
    return resp

# 電影院：電影 [現金 紅利]
#當用戶按下‘電影院’按鈕後
@app.route('/api/recommend/use/place/theater/<auth_id>', methods=['POST'])
def theater_recommend(auth_id):
    _json = request.data
    _dict = ast.literal_eval(_json.decode('utf-8')) #將json格式轉為string(decode)，再將string轉為dict(ast.literal_eval)
    
    records = mongo.db.cusCreditCard.find_one({'id':auth_id}) #Bson
    resp_tmp = dumps(records) #Json
    tmp_dict = json.loads(resp_tmp) #dict

    resp=dict()
    resp['recommed_result']=[]
    # 電影 [現金 紅利]
    if(recommend.cash_or_point(auth_id)=='cash'):
        # 真小白->同辦卡推薦
        if(context.user_status(auth_id)=='new' and tmp_dict['cardID'] is None):
            for place in _dict['destinations']:
                resp_mov=recommend.movie_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id,0,0)
                if(resp_mov['thr_recommend_cardID'] is None): # 加上現金
                    resp_cash=recommend.cash_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id,0,0)
                    new_resp=recommend.return_enough(resp_mov,resp_cash)
                    if resp_cash['thr_recommend_cardID'] is None: # 加上紅利回饋
                        resp_point=recommend.point_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],'電影',auth_id,0,0)
                        new_resp=recommend.return_enough(new_resp,resp_point)
                        resp['recommed_result'].append(new_resp) 
                    else:
                        resp['recommed_result'].append(new_resp) 
                else:
                    resp['recommed_result'].append(resp_mov) 
        # 假小白和舊用戶
        else:
            for place in _dict['destinations']:
                resp_mov=recommend.movie_discount(place['lat'],place['lng'],place['name'],auth_id)
                if(resp_mov['thr_recommend_cardID'] is None): # 加上現金
                    resp_cash=recommend.cash_return_discount(place['lat'],place['lng'],place['name'],auth_id)
                    new_resp=recommend.return_enough(resp_mov,resp_cash)
                    if resp_cash['thr_recommend_cardID'] is None: # 加上紅利回饋
                        resp_point=recommend.point_return_discount(place['lat'],place['lng'],place['name'],'電影',auth_id)
                        new_resp=recommend.return_enough(new_resp,resp_point)
                        resp['recommed_result'].append(new_resp) 
                    else:
                        resp['recommed_result'].append(new_resp) 
                else:
                    resp['recommed_result'].append(resp_mov) 
    # 電影 [紅利 現金]
    else:
        # 真小白->同辦卡推薦
        if(context.user_status(auth_id)=='new' and tmp_dict['cardID'] is None):
            for place in _dict['destinations']:
                resp_mov=recommend.movie_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id,0,0)
                if(resp_mov['thr_recommend_cardID'] is None): # 加上紅利
                    resp_point=recommend.point_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],'電影',auth_id,0,0)
                    new_resp=recommend.return_enough(resp_mov,resp_point)
                    if resp_cash['thr_recommend_cardID'] is None: # 加上現金回饋
                        resp_cash=recommend.cash_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id,0,0)
                        new_resp=recommend.return_enough(new_resp,resp_cash)
                        resp['recommed_result'].append(new_resp) 
                    else:
                        resp['recommed_result'].append(new_resp) 
                else:
                    resp['recommed_result'].append(resp_mov) 
        # 假小白和舊用戶
        else:
            for place in _dict['destinations']:
                resp_mov=recommend.movie_discount(place['lat'],place['lng'],place['name'],auth_id)
                if(resp_mov['thr_recommend_cardID'] is None): # 加上紅利
                    resp_point=recommend.point_return_discount(place['lat'],place['lng'],place['name'],'電影',auth_id)
                    new_resp=recommend.return_enough(resp_mov,resp_point)
                    if resp_cash['thr_recommend_cardID'] is None: # 加上現金回饋
                        resp_cash=recommend.cash_return_discount(place['lat'],place['lng'],place['name'],auth_id)
                        new_resp=recommend.return_enough(new_resp,resp_cash)
                        resp['recommed_result'].append(new_resp) 
                    else:
                        resp['recommed_result'].append(new_resp) 
                else:
                    resp['recommed_result'].append(resp_mov) 
    return resp

# 停車場：停車 [現金 紅利]
#當用戶按下‘停車場’按鈕後
@app.route('/api/recommend/use/place/parking_lot/<auth_id>', methods=['POST'])
def parking_recommend(auth_id):
    _json = request.data
    _dict = ast.literal_eval(_json.decode('utf-8')) #將json格式轉為string(decode)，再將string轉為dict(ast.literal_eval)
    
    records = mongo.db.cusCreditCard.find_one({'id':auth_id}) #Bson
    resp_tmp = dumps(records) #Json
    tmp_dict = json.loads(resp_tmp) #dict

    resp=dict()
    resp['recommed_result']=[]
    # 停車 [現金 紅利]
    if(recommend.cash_or_point(auth_id)=='cash'):
        # 真小白->同辦卡推薦
        if(context.user_status(auth_id)=='new' and tmp_dict['cardID'] is None):
            for place in _dict['destinations']:
                resp_park=recommend.parking_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id,0,0)
                if(resp_park['thr_recommend_cardID'] is None): # 加上現金
                    resp_cash=recommend.cash_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id,0,0)
                    new_resp=recommend.return_enough(resp_park,resp_cash)
                    if resp_cash['thr_recommend_cardID'] is None: # 加上紅利回饋
                        resp_point=recommend.point_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],'停車',auth_id,0,0)
                        new_resp=recommend.return_enough(new_resp,resp_point)
                        resp['recommed_result'].append(new_resp) 
                    else:
                        resp['recommed_result'].append(new_resp) 
                else:
                    resp['recommed_result'].append(resp_park) 
        # 假小白和舊用戶
        else:
            for place in _dict['destinations']:
                resp_park=recommend.parking_discount(place['lat'],place['lng'],place['name'],auth_id)
                if(resp_park['thr_recommend_cardID'] is None): # 加上現金
                    resp_cash=recommend.cash_return_discount(place['lat'],place['lng'],place['name'],auth_id)
                    new_resp=recommend.return_enough(resp_park,resp_cash)
                    if resp_cash['thr_recommend_cardID'] is None: # 加上紅利回饋
                        resp_point=recommend.point_return_discount(place['lat'],place['lng'],place['name'],'停車',auth_id)
                        new_resp=recommend.return_enough(new_resp,resp_point)
                        resp['recommed_result'].append(new_resp) 
                    else:
                        resp['recommed_result'].append(new_resp) 
                else:
                    resp['recommed_result'].append(resp_park)
    # 停車 [紅利 現金]
    else:
        # 真小白->同辦卡推薦
        if(context.user_status(auth_id)=='new' and tmp_dict['cardID'] is None):
            for place in _dict['destinations']:
                resp_park=recommend.parking_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id,0,0)
                if(resp_park['thr_recommend_cardID'] is None): # 加上紅利
                    resp_point=recommend.point_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],'停車',auth_id,0,0)
                    new_resp=recommend.return_enough(resp_park,resp_point)
                    if resp_cash['thr_recommend_cardID'] is None: # 加上現金回饋
                        resp_cash=recommend.cash_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id,0,0)
                        new_resp=recommend.return_enough(new_resp,resp_cash)
                        resp['recommed_result'].append(new_resp) 
                    else:
                        resp['recommed_result'].append(new_resp) 
                else:
                    resp['recommed_result'].append(resp_park) 
        # 假小白和舊用戶
        else:
            for place in _dict['destinations']:
                resp_park=recommend.parking_discount(place['lat'],place['lng'],place['name'],auth_id)
                if(resp_park['thr_recommend_cardID'] is None): # 加上紅利
                    resp_point=recommend.point_return_discount(place['lat'],place['lng'],place['name'],'停車',auth_id)
                    new_resp=recommend.return_enough(resp_park,resp_point)
                    if resp_cash['thr_recommend_cardID'] is None: # 加上現金回饋
                        resp_cash=recommend.cash_return_discount(place['lat'],place['lng'],place['name'],auth_id)
                        new_resp=recommend.return_enough(new_resp,resp_cash)
                        resp['recommed_result'].append(new_resp) 
                    else:
                        resp['recommed_result'].append(new_resp) 
                else:
                    resp['recommed_result'].append(resp_park) 
    return resp

# 餐廳：[現金 紅利]
#當用戶按下‘餐廳’按鈕後
@app.route('/api/recommend/use/place/restaurant/<auth_id>', methods=['POST'])
def restaurant_recommend(auth_id):
    _json = request.data
    _dict = ast.literal_eval(_json.decode('utf-8')) #將json格式轉為string(decode)，再將string轉為dict(ast.literal_eval)
    
    records = mongo.db.cusCreditCard.find_one({'id':auth_id}) #Bson
    resp_tmp = dumps(records) #Json
    tmp_dict = json.loads(resp_tmp) #dict

    resp=dict()
    resp['recommed_result']=[]
    # 現金回饋優先
    if(recommend.cash_or_point(auth_id)=='cash'):
        # 真小白->同辦卡推薦
        if(context.user_status(auth_id)=='new' and tmp_dict['cardID'] is None):
            for place in _dict['destinations']:
                resp_cash=recommend.cash_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id,0,0)
                if resp_cash['thr_recommend_cardID'] is None: #推薦結果不足三個 -> 加上紅利回饋
                    resp_point=recommend.point_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],'餐廳',auth_id,0,0)
                    new_resp=recommend.return_enough(resp_cash,resp_point)
                    resp['recommed_result'].append(new_resp) 
                else:
                    resp['recommed_result'].append(resp_cash)    
        # 假小白和舊用戶
        else:
            for place in _dict['destinations']:
                resp_cash=recommend.cash_return_discount(place['lat'],place['lng'],place['name'],auth_id)
                if resp_cash['thr_recommend_cardID'] is None: #推薦結果不足三個 -> 加上紅利回饋
                    resp_point=recommend.point_return_discount(place['lat'],place['lng'],place['name'],'餐廳',auth_id)
                    new_resp=recommend.return_enough(resp_cash,resp_point)
                    resp['recommed_result'].append(new_resp) 
                else:
                    resp['recommed_result'].append(resp_cash) 
    # 紅利回饋優先
    else:
        # 真小白->同辦卡推薦
        if(context.user_status(auth_id)=='new' and tmp_dict['cardID'] is None):
            for place in _dict['destinations']:
                resp_point=recommend.point_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],'餐廳',auth_id,0,0)
                if resp_point['thr_recommend_cardID'] is None: #推薦結果不足三個 -> 加上現金回饋
                    resp_cash=recommend.cash_return_discount_for_apply_withLocation(place['lat'],place['lng'],place['name'],auth_id,0,0)
                    new_resp=recommend.return_enough(resp_point,resp_cash)
                    resp['recommed_result'].append(new_resp) 
                else:
                    resp['recommed_result'].append(resp_point) 
        # 假小白和舊用戶
        else: 
            for place in _dict['destinations']:
                resp_point=recommend.point_return_discount(place['lat'],place['lng'],place['name'],'餐廳',auth_id)
                if resp_point['thr_recommend_cardID'] is None: #推薦結果不足三個 -> 加上現金回饋
                    resp_cash=recommend.cash_return_discount(place['lat'],place['lng'],place['name'],auth_id)
                    new_resp=recommend.return_enough(resp_point,resp_cash)
                    resp['recommed_result'].append(new_resp) 
                else:
                    resp['recommed_result'].append(resp_point)
    return resp

#------------------------------------------------辦卡推薦(無地點因素)------------------------------------------------#

# 辦卡推薦(沒有地點因素)(用最常去的地點)
# find_freq_place：{'name':地點名稱,'type':地點類別,'lat','lng'}
# 對該用戶最常去的地點做推薦(真小白會找跟他同群的某人最常去的地點)
@app.route('/api/recommend/apply/no_place/<auth_id>', methods=['GET'])
def recommend_place_for_apply(auth_id):
    #真假小白
    print(context.user_status(auth_id))
    if(context.user_status(auth_id)=='new'):
        records = mongo.db.cusCreditCard.find_one({'id':auth_id}) #Bson
        resp_tmp = dumps(records) #Json
        tmp_dict = json.loads(resp_tmp) #dict
        #真小白->用同群中的某人最常去的地點來推薦
        if(tmp_dict['cardID'] is None):
            print('if')
            cus_records = mongo.db.customer.find_one({'id':auth_id}) #Bson
            cus_resp_tmp = dumps(cus_records) #Json
            cus_tmp_dict = json.loads(cus_resp_tmp) #dict
            feature_value=dict()
            feature_value['age']=cus_tmp_dict['age']
            feature_value['sex']=cus_tmp_dict['sex']
            feature_value['annualIncome']=cus_tmp_dict['annualIncome']
            feature_value['expenseMonth']=cus_tmp_dict['expenseMonth'] #要再寫一個計算的
            similar_persons=context.find_similar_(auth_id,feature_value)
            #print('similar person: ',similar_persons)
            sim_auth_id=similar_persons[0]['id']
            print('sim_auth_id: ',sim_auth_id)
            place=context.find_freq_place(sim_auth_id)
            print('place: ',place)
            resp=context.recommend_discount_for_place(auth_id, place,0)
        #假小白#有卡且有少量記帳紀錄
        else:
            print('if else')
            place=context.find_freq_place(auth_id)
            print(place)
            resp=context.recommend_discount_for_place(auth_id, place,1)
    #舊用戶
    else:
        print('else')
        place=context.find_freq_place(auth_id)
        print('place result: ',place)
        resp=context.recommend_discount_for_place(auth_id, place,0)
    return resp

#------------------------------------------------辦卡推薦(有地點因素)------------------------------------------------#

# 辦卡推薦(有地點因素)(對當下這一個位置做推薦)
# post接收當下位置經緯度:{'current_place':{'lat':(str),'lng':(str)}}
@app.route('/api/recommend/apply/with_place/<auth_id>', methods=['POST'])
def recommend_place_for_apply_withPlace(auth_id):
    _json = request.data
    _dict = ast.literal_eval(_json.decode('utf-8'))
    place = context.find_place_nearby(_dict['current_place']['lat'],_dict['current_place']['lng'])
    #真假小白
    if(context.user_status(auth_id)=='new'):
        records = mongo.db.cusCreditCard.find_one({'id':auth_id}) #Bson
        resp_tmp = dumps(records) #Json
        tmp_dict = json.loads(resp_tmp) #dict
        if(tmp_dict['cardID'] is None):
            resp=context.recommend_discount_for_place(auth_id, place,0)
        #假小白#有卡且有少量記帳紀錄
        else:
            resp=context.recommend_discount_for_place(auth_id, place,1)
    #舊用戶
    else:
        resp=context.recommend_discount_for_place(auth_id, place,0)
    return resp

#------------------------------------------------勾選畫面------------------------------------------------#
#用戶基本資料->偏好地點類型->偏好優惠類型

#接收使用者填寫的用戶基本資料
#post接收後再存到資料庫(Customer)
@app.route('/api/customer/<auth_id>/api/personal_data/add', methods=['POST'])
def add_personal_data(auth_id):
    _json = request.data
    _dict = ast.literal_eval(_json.decode('utf-8')) #將json格式轉為string(decode)，再將string轉為dict(ast.literal_eval)
    insert_dict=dict()
    insert_dict['id']=auth_id
    insert_dict['phoneNum']=_dict['phoneNum']
    insert_dict['email']=_dict['email']
    insert_dict['age']=_dict['age']
    insert_dict['birthday']=_dict['birthday']
    insert_dict['annualIncome']=_dict['annualIncome']
    insert_dict['sex']=_dict['sex']
    insert_dict['occupation']=_dict['occupation']
    insert_dict['chiName']=_dict['chiName']
    insert_dict['engName']=_dict['engName']
    insert_dict['residenceAdd']=_dict['residenceAdd']
    insert_dict['mailingAdd']=_dict['mailingAdd']
    insert_dict['nation']=_dict['nation']
    insert_dict['status']='new' #剛加入的狀態一定都是菜鳥
    insert_dict['expenseMonth']=_dict['expenseMonth']
    insert_dict['convenient_store']=None
    insert_dict['mall']=None
    insert_dict['gas_station']=None
    insert_dict['parking_lot']=None
    insert_dict['restaurant']=None
    insert_dict['theater']=None
    insert_dict['hypermarket']=None
    insert_dict['cashRewPref']=None
    insert_dict['pointRewPref']=None
    insert_dict['parkingRewPref']=None
    insert_dict['gasRewPref']=None
    insert_dict['movieRewPref']=None
    if request.method == 'POST':
        id = mongo.db.customer.insert(_dict) # insert()會返回ObjectId類型的_id屬性
        resp = jsonify('added successfully!')
        resp.status_code = 200
        return resp
    else:
        return jsonify('error')

#接收使用者勾選的偏好地點類型
#post接收後再存到資料庫(Customer)
@app.route('/api/customer/<auth_id>/api/prefer_place', methods=['POST'])
def add_prefer_place(auth_id):
    _json = request.data
    _dict = ast.literal_eval(_json.decode('utf-8')) #將json格式轉為string(decode)，再將string轉為dict(ast.literal_eval)
    if request.method == 'POST':
        WriteResult = mongo.db.customer.update({'id':auth_id},{'$set':{"convenient_store":_dict['convenient_store'],"mall":_dict['mall'],"gas_station":_dict['gas_station'],"parking_lot":_dict['parking_lot'],"restaurant":_dict['restaurant']}}) # update()會返回WriteResult document that contains the status of the operation.
        resp = jsonify('added successfully!')
        resp.status_code = 200
        return resp
    else:
        return jsonify('error')

#接收使用者勾選的偏好優惠類型
#post接收後再存到資料庫(Customer)
@app.route('/api/customer/<auth_id>/api/prefer_discount', methods=['POST'])
def add_prefer_discount(auth_id):
    _json = request.data
    _dict = ast.literal_eval(_json.decode('utf-8')) #將json格式轉為string(decode)，再將string轉為dict(ast.literal_eval)
    if request.method == 'POST':
        WriteResult = mongo.db.customer.update({'id':auth_id},{'$set':{"現金回饋優惠":_dict['現金回饋優惠'],"紅利回饋優惠":_dict['紅利回饋優惠'],"停車優惠":_dict['停車優惠'],"加油優惠":_dict['加油優惠'],"電影優惠":_dict['電影優惠']}}) # update()會返回WriteResult document that contains the status of the operation.
        resp = jsonify('added successfully!')
        resp.status_code = 200
        return resp
    else:
        return jsonify('error')

#------------------------------------------------修改畫面------------------------------------------------#

#修改用戶基本資料與偏好優惠
#目前假設這兩個都在同一個畫面裡
@app.route('/api/customer/<auth_id>/api/personal_data/update', methods=['PUT'])
def change_personal_data(auth_id):
    _json = request.data
    _dict = ast.literal_eval(_json.decode('utf-8')) #將json格式轉為string(decode)，再將string轉為dict(ast.literal_eval)
    _dict['IDnumber']=auth_id
    _dict['使用軟體狀態']=context.user_status(auth_id)
    if request.method == 'PUT':
        id = mongo.db.customer.update(_dict) # insert()會返回ObjectId類型的_id屬性
        resp = jsonify('changed successfully!')
        resp.status_code = 200
        return resp
    else:
        return jsonify('error')

#------------------------------------------------轉換資料------------------------------------------------#

#這個應該在他每記一筆記帳紀錄的時候轉換一次？->只取最新加入的一筆資料作轉換
#將某人的記帳紀錄轉為google location所需的欄位，並insert(只把屬於我們有做的地點類別的紀錄作轉換)
#只用place type來判斷他到底是哪個地點類型
@app.route('/api/bookkeeping/api/convert', methods=['GET'])
def bookkeeping_to_gLocation():
    id_=[
    'E127082107',
    'E178566103',
    'E189424472',
    'E173411750',
    'E165410847',
    'E123712483',
    'E175816480',
    'E151979094',
    'E166454596',
    'E187014409',
    'E164315259',
    'E176943862',
    'E194088655',
    'E130945360',
    'E182875124',
    'E125774324',
    'E139065023',
    'E126596994',
    'E142292144',
    'E154035908',
    'E169006239',
    'E182011191',
    'E172971843',
    'E190632374',
    'E168212001',
    'E181398160',
    'E123467998',
    'E136180235',
    'E194807617',
    'E185858870',
    'E127280552',
    'E161828007',
    'E139114919',
    'E153764656',
    'E173223297',
    'E132978769',
    'E150039928',
    'E162710348',
    'E180503298',
    'E161950958',
    'E197551072',
    'E127020185',
    'E147461517',
    'E123723925',
    'E139495739',
    'E148758109',
    'E164076911',
    'E141440487',
    'E154563920',
    'E167074043',
    'E167478546',
    'E175319153',
    'E190296453',
    'E127529508',
    'E181835846',
    'E194861706',
    'E127055866',
    'E127920353',
    'E139928675',
    'E154912947']
    phoneNum=[
    '0902842298',
    '0906641028',
    '0902556156',
    '0902771109',
    '0908517740',
    '0901855922',
    '0905517716',
    '0902728674',
    '0908597384',
    '0904297586',
    '0902882944',
    '0906740584',
    '0905294596',
    '0908195281',
    '0908505950',
    '0903988404',
    '0906019686',
    '0904763967',
    '0904669405',
    '0908308058',
    '0902116238',
    '0906568231',
    '0907741242',
    '0905301322',
    '0901773532',
    '0908640023',
    '0902720821',
    '0904916910',
    '0901887906',
    '0906056539',
    '0906582958',
    '0905309777',
    '0906397421',
    '0907838410',
    '0907728077',
    '0904527037',
    '0902537483',
    '0905229028',
    '0903668534',
    '0901605504',
    '0901560339',
    '0908663408',
    '0906324836',
    '0902999351',
    '0904228401',
    '0907029409',
    '0908970948',
    '0903886762',
    '0908830376',
    '0907665466',
    '0908455363',
    '0901831705',
    '0903079958',
    '0908427133',
    '0903333814',
    '0907501059',
    '0906039617',
    '0904089837',
    '0905480710',
    '0906158329']
    #for i,j in zip(id_,phoneNum): #要轉朋友的話把#去掉，下面auth_id=i, phoneNum=j
    auth_id= 'A101498569'
    phoneNum= '0906056539'
    #print('auth id: ',i)
    #print('phoneNum: ',j)
    dict_place={'百貨公司':['department_store', 'shopping_mall'],'加油站': ['gas_station'],'電影院': ['movie_theater'],'停車場': ['parking'],'餐廳': ['cafe', 'restaurant']}
    records = mongo.db.bookkeepingRecord.find({'id': auth_id}) #Bson #只取最後一筆(最新的一筆)
    resp_tmp = dumps(records) #Json
    tmp_dict = json.loads(resp_tmp) #dict 
    #print('tmp_dict:',tmp_dict)
    for record in tmp_dict:
        include=0 #判斷是否包含在我們要做的地點類型裡面，若無就不轉換也不存入
        resp_dict={}
        find_place_result=gmaps.find_place(input=record['consumeStore'], input_type="textquery",fields=['place_id','formatted_address','types'])
        if len(find_place_result['candidates'])==0:
            pass
        else:
            tmp_type=find_place_result['candidates'][0]['types'] #list
            for name, place_type in dict_place.items():
                for i in tmp_type:
                    if(i in place_type):
                        resp_dict['locationType']=name
                        include=1
            if(include==1):
                #print('insert')
                dd=int(record['consumeTime']['$date'])
                dt_obj = datetime.fromtimestamp(dd/1000.0)  
                resp_dict['id']=auth_id
                resp_dict['phoneNum']=phoneNum
                resp_dict['locationName']=record['consumeStore']
                resp_dict['address']=find_place_result['candidates'][0]['formatted_address']
                geocode_result = gmaps.geocode(find_place_result['candidates'][0]['formatted_address'])
                resp_dict['latitude']=geocode_result[0]['geometry']['location']['lat']
                resp_dict['longitude']=geocode_result[0]['geometry']['location']['lng']
                resp_dict['locationTime']=dt_obj
                id = mongo.db.googleLocation.insert_one(resp_dict) # insert()會返回ObjectId類型的_id屬性
                print(resp_dict)
        # #對用戶狀態做檢查
        # u_records = mongo.db.customer.find_one({'id':auth_id}) #Bson
        # u_resp_tmp = dumps(u_records) #Json
        # u_tmp_dict = json.loads(u_resp_tmp) #dict
        # if(u_tmp_dict['status']!='old'):
        #     WriteResult = mongo.db.customer.update({'id':auth_id},{'$set':{"status":context.user_status(auth_id)}}) # update()會返回WriteResult document that contains the status of the operation.
    
    resp = jsonify('Converted successfully!')
    resp.status_code = 200
    return resp
'''
@app.route('/api/bookkeeping/<auth_id>/<phoneNum>/api/convert', methods=['GET'])
def bookkeeping_to_gLocation(auth_id, phoneNum):
    dict_place={'百貨公司':['department_store', 'shopping_mall'],'加油站': ['gas_station'],'電影院': ['movie_theater'],'停車場': ['parking'],'餐廳': ['cafe', 'restaurant']}
    records = mongo.db.bookkeepingRecord.find({'id': auth_id}).sort('consumeTime',-1).limit(1) #Bson #只取最後一筆(最新的一筆)
    resp_tmp = dumps(records) #Json
    tmp_dict = json.loads(resp_tmp) #dict
    for record in tmp_dict:
        include=0 #判斷是否包含在我們要做的地點類型裡面，若無就不轉換也不存入
        resp_dict={}
        find_place_result=gmaps.find_place(input=record['consumeStore'], input_type="textquery",fields=['place_id','formatted_address','types'])
        tmp_type=find_place_result['candidates'][0]['types'] #list
        for name, place_type in dict_place.items():
            for i in tmp_type:
                if(i in place_type):
                    resp_dict['locationType']=name
                    include=1
        if(include==1):
            resp_dict['id']=auth_id
            resp_dict['phoneNum']=phoneNum
            resp_dict['locationName']=record['consumeStore']
            resp_dict['address']=find_place_result['candidates'][0]['formatted_address']
            geocode_result = gmaps.geocode(find_place_result['candidates'][0]['formatted_address'])
            resp_dict['latitude']=geocode_result[0]['geometry']['location']['lat']
            resp_dict['longitude']=geocode_result[0]['geometry']['location']['lng']
            resp_dict['locationTime']=record['consumeTime']
            id = mongo.db.googleLocation.insert(resp_dict) # insert()會返回ObjectId類型的_id屬性
    #對用戶狀態做檢查
    u_records = mongo.db.customer.find_one({'id':auth_id}) #Bson
    u_resp_tmp = dumps(u_records) #Json
    u_tmp_dict = json.loads(u_resp_tmp) #dict
    if(u_tmp_dict['status']!='old'):
       WriteResult = mongo.db.customer.update({'id':auth_id},{'$set':{"status":context.user_status(auth_id)}}) # update()會返回WriteResult document that contains the status of the operation.
    resp = jsonify('Converted successfully!')
    resp.status_code = 200
    return resp
'''
#在他每記一筆記帳紀錄的時候，重新計算一次他的月平均消費(計算近六個月的月平均花費)
#當他是舊用戶的時候再更新他的月平均消費
@app.route('/api/bookkeeping/<auth_id>/api/count_average_cost', methods=['GET'])
def count_average_cost(auth_id):
    records = mongo.db.customer.find_one({'id':auth_id}) #Bson 
    resp_tmp = dumps(records) #Json
    tmp_dict = json.loads(resp_tmp) #dict
    #當他是舊用戶的時候再更新他的月平均消費
    if(tmp_dict['status']=='old'):
        today=datetime.today()
        count=0
        sum=0
        for i in range(-1,-7,-1):
            records = mongo.db.bookkeepingRecord.aggregate([{'$match':{"id":auth_id,"consumeTime":{'$gte':context.add_months(today,i),'$lte':context.add_months(today,i+1)}}},{'$group':{'_id':"$id",'total':{'$sum':"$consumeAmount"}}}])
            resp_tmp = dumps(records) #Json
            tmp_dict = json.loads(resp_tmp) #dict
            if len(tmp_dict)==0:
                break
            else:
                count+=1
                sum+=tmp_dict[0]['total']
        avg_cost=sum//count
        WriteResult = mongo.db.customer.update({'id':auth_id},{'$set':{"expenseMonth":avg_cost}}) # update()會返回WriteResult document that contains the status of the operation.
        resp = jsonify('changed successfully!')
        resp.status_code = 200
        return resp
    else:
        return jsonify('not changed!')

#------------------------------------------------分析資料(for dashboard)------------------------------------------------#

if __name__ == "__main__":
    app.run(host='0.0.0.0')


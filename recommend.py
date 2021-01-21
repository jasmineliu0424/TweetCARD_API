import json
from app import app, mongo
from bson.json_util import dumps
from bson.objectid import ObjectId
from flask import jsonify, request,Response
import ast
import json
from datetime import datetime
import calendar
import context
import re

#-------------------------------------------------用卡推薦-----------------------------------------------------#

# 回傳(座標，卡種編號，優惠時數(str)(可停x小時)，卡名，銀行) 
# 停車優惠：{‘上個月帳單限制’:20000,‘前三個月帳單限制’:100000,‘前十二個月帳單限制’:600000}
# 不包含百貨公司內的停車場
# app回傳座標跟地點名稱 'lat':lat,'lng':lng,'地點名稱':
def parking_discount(lat,lng,place_name,auth_id): #用戶擁有的卡種編號(list)
    parking_recommend_list=[]

    #取出該用戶擁有的所有卡種編號(list)
    cards = mongo.db.cusCreditCard.find_one({'id': auth_id}) #Bson
    cards_tmp = dumps(cards) #Json
    tmp_card_dict = json.loads(cards_tmp)
    
    #判斷是否符合資格
    for cardID, level in tmp_card_dict['cardID'].items():
        #level=level[:-2] #把正卡/副卡去掉
        #抓取該信用卡的優惠內容
        card = mongo.db.reward.find_one({'cardID': cardID}) #Bson
        resp_tmp = dumps(card) #Json
        tmp_dict = json.loads(resp_tmp) #dict
        #因為reward裡面沒有銀行，所以要用卡種編號去creditCard裡面抓
        card_limit = mongo.db.creditCard.find_one({'cardID': cardID}) #Bson
        card_resp_tmp = dumps(card_limit) #Json
        card_dict = json.loads(card_resp_tmp) #dict

        
        if(tmp_dict['parkingRewMax'] is not None):
            can_park=0
            for i in tmp_dict['parkingRewLocation']:
                if place_name in i or i in place_name or place_name==i:
                    can_park=1
            if can_park:
                if(tmp_dict['parkingRewStatementMin']['上個月帳單限制'] is not None and total_consumption_last_month(cardID,auth_id)>tmp_dict['parkingRewStatementMin']['上個月帳單限制']):
                    if(type(tmp_dict['parkingRewMax'])==dict and level in tmp_dict['parkingRewMax'].keys()):
                        parking_recommend_list.append({'cardID':cardID,'優惠時數':tmp_dict['parkingRewMax'][level],'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName']})
                    else: #沒有等級差別 tmp_dict['parkingRewMax']=int
                        parking_recommend_list.append({'cardID':cardID,'優惠時數':tmp_dict['parkingRewMax'],'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName']})
                elif(tmp_dict['parkingRewStatementMin']['前三個月帳單限制'] is not None and total_consumption_last_three_months(cardID,auth_id)>tmp_dict['parkingRewStatementMin']['前三個月帳單限制']):
                    if(type(tmp_dict['parkingRewMax'])==dict and level in tmp_dict['parkingRewMax'].keys()):
                        parking_recommend_list.append({'cardID':cardID,'優惠時數':tmp_dict['parkingRewMax'][level],'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName']})
                    else:
                        parking_recommend_list.append({'cardID':cardID,'優惠時數':tmp_dict['parkingRewMax'],'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName']}) 
                elif(tmp_dict['parkingRewStatementMin']['前十二個月帳單限制'] is not None and total_consumption_last_year(cardID,auth_id)>tmp_dict['parkingRewStatementMin']['前十二個月帳單限制']):
                    if(type(tmp_dict['parkingRewMax'])==dict and level in tmp_dict['parkingRewMax'].keys()):
                        parking_recommend_list.append({'cardID':cardID,'優惠時數':tmp_dict['parkingRewMax'][level],'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName']})
                    else:
                        parking_recommend_list.append({'cardID':cardID,'優惠時數':tmp_dict['parkingRewMax'],'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName']})
                #elif(tmp_dict['停車_當期帳單(前一個月)'] is not None and tmp_dict['停車_當期帳單(前三個月)'] is not None and tmp_dict['停車_當期帳單(前12個月)'] is not None and tmp_dict['消費滿'] is not None):
                #    parking_recommend_list.append({'卡片id':tmp_dict['卡片id'],'優惠時數':tmp_dict['可停時數'],'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName稱']})
    
    result = sorted(parking_recommend_list,key = lambda i: i['優惠時數'],reverse=True)
    recommend_list={'lat':lat,'lng':lng,'placeName':place_name}
    if(len(result)>=3):
        recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':'可停'+str(result[0]['優惠時數'])+'小時','fir_recommend_bank':result[0]['銀行']})
        recommend_list.update({'sec_recommend_cardID':result[1]['cardID'],'sec_recommend_card':result[1]['卡名'],'sec_recommend_discount':'可停'+str(result[1]['優惠時數'])+'小時','sec_recommend_bank':result[1]['銀行']})
        recommend_list.update({'thr_recommend_cardID':result[2]['cardID'],'thr_recommend_card':result[2]['卡名'],'thr_recommend_discount':'可停'+str(result[2]['優惠時數'])+'小時','thr_recommend_bank':result[2]['銀行']})
    elif(len(result)==2):
        recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':'可停'+str(result[0]['優惠時數'])+'小時','fir_recommend_bank':result[0]['銀行']})
        recommend_list.update({'sec_recommend_cardID':result[1]['cardID'],'sec_recommend_card':result[1]['卡名'],'sec_recommend_discount':'可停'+str(result[1]['優惠時數'])+'小時','sec_recommend_bank':result[1]['銀行']})
        recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
    elif(len(result)==1):
        recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':'可停'+str(result[0]['優惠時數'])+'小時','fir_recommend_bank':result[0]['銀行']})
        recommend_list.update({'sec_recommend_cardID':None,'sec_recommend_card':None,'sec_recommend_discount':None,'sec_recommend_bank':None})
        recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
    else:
        recommend_list.update({'fir_recommend_cardID':None,'fir_recommend_card':None,'fir_recommend_discount':None,'fir_recommend_bank':None})
        recommend_list.update({'sec_recommend_cardID':None,'sec_recommend_card':None,'sec_recommend_discount':None,'sec_recommend_bank':None})
        recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
    return recommend_list

# 現金回饋
def cash_return_discount(lat,lng,place_name,auth_id): #用戶擁有的卡種編號(list)
    cash_recommend_list=[]

    #取出該用戶擁有的所有卡種編號(list)
    cards = mongo.db.cusCreditCard.find_one({'id': auth_id}) #Bson
    cards_tmp = dumps(cards) #Json
    tmp_card_dict = json.loads(cards_tmp) #dict
    
    for cardID, level in tmp_card_dict['cardID'].items():
        #level=level[:-2] #把正卡/副卡去掉
        card = mongo.db.reward.find_one({'cardID': cardID}) #Bson
        resp_tmp = dumps(card) #Json
        tmp_dict = json.loads(resp_tmp) #dict
        #因為reward裡面沒有銀行，所以要用卡種編號去creditCard裡面抓
        card_limit = mongo.db.creditCard.find_one({'cardID': cardID}) #Bson
        card_resp_tmp = dumps(card_limit) #Json
        card_dict = json.loads(card_resp_tmp) #dict
        if(tmp_dict['cashReward'] is not None): #判斷該卡是否有現金回饋優惠
            if(not can_use_in_here(place_name,tmp_dict['excludeLocation'])):
                if("現金回饋4" in tmp_dict['cashReward'].keys()): 
                    if(total_consumption_last_month(cardID,auth_id)>=tmp_dict['cashReward']['現金回饋4'][4] and (can_use_in_here(place_name,tmp_dict['cashReward']['現金回饋4'][3]) or "不限" in tmp_dict['cashReward']['現金回饋4'][3]) and (place_name not in cannot_use_in_here(tmp_dict['cashReward']['現金回饋4'][3]))):
                        cash_recommend_list.append({'cardID':cardID,'現金回饋%數':tmp_dict['cashReward']['現金回饋4'][0],'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'回饋上限':has_limit_or_not(tmp_dict['cashReward']['現金回饋4'][2])})
                    elif(total_consumption_last_month(cardID,auth_id)>=tmp_dict['cashReward']['現金回饋3'][4] and (can_use_in_here(place_name,tmp_dict['cashReward']['現金回饋3'][3]) or "不限" in tmp_dict['cashReward']['現金回饋3'][3] ) and ( place_name not in cannot_use_in_here(tmp_dict['cashReward']['現金回饋3'][3]))):
                        cash_recommend_list.append({'cardID':cardID,'現金回饋%數':tmp_dict['cashReward']['現金回饋3'][0],'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'回饋上限':has_limit_or_not(tmp_dict['cashReward']['現金回饋3'][2])})
                    elif(total_consumption_last_month(cardID,auth_id)>=tmp_dict['cashReward']['現金回饋2'][4] and (can_use_in_here(place_name,tmp_dict['cashReward']['現金回饋2'][3]) or "不限" in tmp_dict['cashReward']['現金回饋2'][3] ) and ( place_name not in cannot_use_in_here(tmp_dict['cashReward']['現金回饋2'][3]))):
                        cash_recommend_list.append({'cardID':cardID,'現金回饋%數':tmp_dict['cashReward']['現金回饋2'][0],'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'回饋上限':has_limit_or_not(tmp_dict['cashReward']['現金回饋2'][2])})
                    elif(total_consumption_last_month(cardID,auth_id)>=tmp_dict['cashReward']['現金回饋1'][4] and (can_use_in_here(place_name,tmp_dict['cashReward']['現金回饋1'][3]) or "不限" in tmp_dict['cashReward']['現金回饋1'][3] ) and ( place_name not in cannot_use_in_here(tmp_dict['cashReward']['現金回饋1'][3]))):
                        cash_recommend_list.append({'cardID':cardID,'現金回饋%數':tmp_dict['cashReward']['現金回饋1'][0],'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'回饋上限':has_limit_or_not(tmp_dict['cashReward']['現金回饋1'][2])})
                elif("現金回饋3" in tmp_dict['cashReward'].keys()): 
                    if(total_consumption_last_month(cardID,auth_id)>=tmp_dict['cashReward']['現金回饋3'][4] and (can_use_in_here(place_name,tmp_dict['cashReward']['現金回饋3'][3]) or "不限" in tmp_dict['cashReward']['現金回饋3'][3]) and (place_name not in cannot_use_in_here(tmp_dict['cashReward']['現金回饋3'][3]))):
                        cash_recommend_list.append({'cardID':cardID,'現金回饋%數':tmp_dict['cashReward']['現金回饋3'][0],'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'回饋上限':has_limit_or_not(tmp_dict['cashReward']['現金回饋3'][2])})
                    elif(total_consumption_last_month(cardID,auth_id)>=tmp_dict['cashReward']['現金回饋2'][4] and (can_use_in_here(place_name,tmp_dict['cashReward']['現金回饋2'][3]) or "不限" in tmp_dict['cashReward']['現金回饋2'][3]) and (place_name not in cannot_use_in_here(tmp_dict['cashReward']['現金回饋2'][3]))):
                        cash_recommend_list.append({'cardID':cardID,'現金回饋%數':tmp_dict['cashReward']['現金回饋2'][0],'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'回饋上限':has_limit_or_not(tmp_dict['cashReward']['現金回饋2'][2])})
                    elif(total_consumption_last_month(cardID,auth_id)>=tmp_dict['cashReward']['現金回饋1'][4] and (can_use_in_here(place_name,tmp_dict['cashReward']['現金回饋1'][3]) or "不限" in tmp_dict['cashReward']['現金回饋1'][3]) and (place_name not in cannot_use_in_here(tmp_dict['cashReward']['現金回饋1'][3]))):
                        cash_recommend_list.append({'cardID':cardID,'現金回饋%數':tmp_dict['cashReward']['現金回饋1'][0],'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'回饋上限':has_limit_or_not(tmp_dict['cashReward']['現金回饋1'][2])})
                elif("現金回饋2" in tmp_dict['cashReward'].keys()): 
                    if(total_consumption_last_month(cardID,auth_id)>=tmp_dict['cashReward']['現金回饋2'][4] and (can_use_in_here(place_name,tmp_dict['cashReward']['現金回饋2'][3]) or "不限" in tmp_dict['cashReward']['現金回饋2'][3]) and (place_name not in cannot_use_in_here(tmp_dict['cashReward']['現金回饋2'][3]))):
                        cash_recommend_list.append({'cardID':cardID,'現金回饋%數':tmp_dict['cashReward']['現金回饋2'][0],'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'回饋上限':has_limit_or_not(tmp_dict['cashReward']['現金回饋2'][2])})
                    elif(total_consumption_last_month(cardID,auth_id)>=tmp_dict['cashReward']['現金回饋1'][4] and (can_use_in_here(place_name,tmp_dict['cashReward']['現金回饋1'][3]) or "不限" in tmp_dict['cashReward']['現金回饋1'][3]) and (place_name not in cannot_use_in_here(tmp_dict['cashReward']['現金回饋1'][3]))):
                        cash_recommend_list.append({'cardID':cardID,'現金回饋%數':tmp_dict['cashReward']['現金回饋1'][0],'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'回饋上限':has_limit_or_not(tmp_dict['cashReward']['現金回饋1'][2])})
                else: #只有現金回饋1
                    if(tmp_dict['cashReward']['現金回饋1'] is not None):
                        if(total_consumption_last_month(cardID,auth_id)>=tmp_dict['cashReward']['現金回饋1'][4] and (can_use_in_here(place_name,tmp_dict['cashReward']['現金回饋1'][3]) or "不限" in tmp_dict['cashReward']['現金回饋1'][3]) and (place_name not in cannot_use_in_here(tmp_dict['cashReward']['現金回饋1'][3]))):
                            cash_recommend_list.append({'cardID':cardID,'現金回饋%數':tmp_dict['cashReward']['現金回饋1'][0],'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'回饋上限':has_limit_or_not(tmp_dict['cashReward']['現金回饋1'][2])})
                    
    result = sorted(cash_recommend_list,key = lambda i:(-i['現金回饋%數'],-i['回饋上限']))
    tmp_per=result[0]['現金回饋%數']
    tmp_index=0
    for i in result:
        if result.index(i)!=0 and i['回饋上限']==-1 and i['現金回饋%數']==tmp_per:
            if(tmp_index==0):
                result.insert(0, result.pop(result.index(i)))
            else:
                result.insert(tmp_index, result.pop(result.index(i)))
            tmp_index=result.index(i)+1
        elif result.index(i)!=0 and i['現金回饋%數']==tmp_per:
            tmp_per=tmp_per
            tmp_index=tmp_index
        else:
            tmp_per=i['現金回饋%數']
            tmp_index=result.index(i)
                
    recommend_list={'lat':lat,'lng':lng,'placeName':place_name}
    if(len(result)>=3):
        recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':'現金回饋'+str(result[0]['現金回饋%數'])+'%','fir_recommend_bank':result[0]['銀行']})
        recommend_list.update({'sec_recommend_cardID':result[1]['cardID'],'sec_recommend_card':result[1]['卡名'],'sec_recommend_discount':'現金回饋'+str(result[1]['現金回饋%數'])+'%','sec_recommend_bank':result[1]['銀行']})
        recommend_list.update({'thr_recommend_cardID':result[2]['cardID'],'thr_recommend_card':result[2]['卡名'],'thr_recommend_discount':'現金回饋'+str(result[2]['現金回饋%數'])+'%','thr_recommend_bank':result[2]['銀行']})
    elif(len(result)==2):
        recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':'現金回饋'+str(result[0]['現金回饋%數'])+'%','fir_recommend_bank':result[0]['銀行']})
        recommend_list.update({'sec_recommend_cardID':result[1]['cardID'],'sec_recommend_card':result[1]['卡名'],'sec_recommend_discount':'現金回饋'+str(result[1]['現金回饋%數'])+'%','sec_recommend_bank':result[1]['銀行']})
        recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
    elif(len(result)==1):
        recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':'現金回饋'+str(result[0]['現金回饋%數'])+'%','fir_recommend_bank':result[0]['銀行']})
        recommend_list.update({'sec_recommend_cardID':None,'sec_recommend_card':None,'sec_recommend_discount':None,'sec_recommend_bank':None})
        recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
    else:
        recommend_list.update({'fir_recommend_cardID':None,'fir_recommend_card':None,'fir_recommend_discount':None,'fir_recommend_bank':None})
        recommend_list.update({'sec_recommend_cardID':None,'sec_recommend_card':None,'sec_recommend_discount':None,'sec_recommend_bank':None})
        recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
    #resp = dumps(parking_recommend_list)
    return recommend_list    

# 加油優惠
# 推薦順序：現折優惠>現金回饋>加油金>加油點數
# 加油點數目前只考慮汽車
# 加油方式是取記帳紀錄裡頻率較高的那個
def gas_discount(lat,lng,place_name,auth_id):
    save_recommend=[] #現折優惠
    reward_recommend=[] #現金回饋
    money_recommend_percent=[] #加油金(%)
    money_recommend_wen=[] #加油金(金額)
    point_recommend=[] #加油點數
    
    #取出該用戶擁有的所有卡種編號(list)
    cards = mongo.db.cusCreditCard.find_one({'id': auth_id}) #Bson
    cards_tmp = dumps(cards) #Json
    tmp_card_dict = json.loads(cards_tmp) #dict
    
    for cardID, level in tmp_card_dict['cardID'].items():
        #level=level[:-2] #把正卡/副卡去掉
        card = mongo.db.reward.find_one({'cardID': cardID}) #Bson
        resp_tmp = dumps(card) #Json
        tmp_dict = json.loads(resp_tmp) #dict
        #因為reward裡面沒有銀行，所以要用卡種編號去creditCard裡面抓
        card_limit = mongo.db.creditCard.find_one({'cardID': cardID}) #Bson
        card_resp_tmp = dumps(card_limit) #Json
        card_dict = json.loads(card_resp_tmp) #dict
        week=['週一','週二','週三','週四','週五','週六','週日']
        weekday=week[datetime.today().weekday()] #取得今天星期幾
        result=[]   
        #加油現折優惠
        if(tmp_dict['gasReward'] is not None):
            can_use_in_here=0
            #判斷是否在此地可用
            for i in tmp_dict['gasRewLocation']:
                if("之外" in i):
                    if (i[:i.rfind("之外")] not in place_name or place_name not in i[:i.rfind("之外")]) and place_name!=i[:i.rfind("之外")]:
                        can_use_in_here=1
                elif(i in place_name or place_name in i or place_name==i):
                    can_use_in_here=1
            if(can_use_in_here):
                #取出該用戶所有記帳資料並計算哪種加油方式頻率高
                records = mongo.db.bookkeepingRecord.find({'id': auth_id}) #Bson
                records_tmp = dumps(records) #Json
                tmp_record_dict = json.loads(records_tmp) #dict
                self=0
                not_self=0
                for record in tmp_record_dict:
                    if(record['consumeType']=='自助加油'):
                        self+=1
                    elif(record['consumeType']=='人工加油'):
                        not_self+=1
                if(self>=not_self):
                    prefer_mode='自助'
                else:
                    prefer_mode='人工'

                for i in tmp_dict['gasReward']:
                    reward_mode=i[0:i.find('/')] #加油方式
                    r=i[i.find('/')+1:]
                    reward_type=r[0:r.find('/')] #汽油or柴油
                    reward_weekday=r[r.find('/')+1:r.rfind('/')] #可用星期
                    reward_account=float(r[r.rfind('/')+1:len(r)]) #現折金額
                    #判斷今天是否在可用星期內
                    in_week=0
                    if(reward_weekday=='不限'):
                        in_week=1
                    elif(reward_weekday=='平日'):
                        if(datetime.today().weekday()<=5):
                            in_week=1
                    elif(reward_weekday==weekday):
                        in_week=1
                    if(prefer_mode==reward_mode and reward_type=='汽油' and in_week):
                        save_recommend.append({'cardID':cardID,'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'加油方式':reward_mode,'可用星期':reward_weekday,'現折金額':reward_account})
                    #result = sorted(save_recommend,key = lambda i: i['現折金額'],reverse=True) #由大到小 
        #加油現金回饋
        elif(tmp_dict['gasCashReward'] is not None):
            can_use_in_here=0
            #判斷是否在此地可用
            for i in tmp_dict['gasRewLocation']:
                if("之外" in i):
                    if (i[:i.rfind("之外")] not in place_name or place_name not in i[:i.rfind("之外")]) and place_name!=i[:i.rfind("之外")]:
                        can_use_in_here=1
                elif(i in place_name or place_name in i or place_name==i):
                    can_use_in_here=1
            if(can_use_in_here):
                fir_limit=int(tmp_dict['gasCashReward'][0:tmp_dict['gasCashReward'].find('/')])
                sec_limit=int(tmp_dict['gasCashReward'][tmp_dict['gasCashReward'].find('/')+1:tmp_dict['gasCashReward'].find('//')])
                fir_reward=int(tmp_dict['gasCashReward'][tmp_dict['gasCashReward'].find('//')+2:tmp_dict['gasCashReward'].rfind('/')][0:tmp_dict['gasCashReward'][tmp_dict['gasCashReward'].find('//')+2:tmp_dict['gasCashReward'].rfind('/')].find('/')])
                sec_reward=int(tmp_dict['gasCashReward'][tmp_dict['gasCashReward'].find('//')+2:tmp_dict['gasCashReward'].rfind('/')][tmp_dict['gasCashReward'][tmp_dict['gasCashReward'].find('//')+2:tmp_dict['gasCashReward'].rfind('/')].find('/')+1:])
                thr_reward=int(tmp_dict['gasCashReward'][tmp_dict['gasCashReward'].rfind('/')+1:])
                if sec_limit!=0:
                    if(total_consumption_last_month(cardID,auth_id)<=fir_limit): #第一級回饋
                        reward_recommend.append({'cardID':cardID,'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'加油現金回饋%數':fir_reward})
                    elif(total_consumption_last_month(cardID,auth_id)<=sec_limit and total_consumption_last_month(cardID,auth_id)>fir_limit): #第二級回饋
                        reward_recommend.append({'cardID':cardID,'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'加油現金回饋%數':sec_reward})
                    else: #第三級回饋
                        reward_recommend.append({'cardID':cardID,'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'加油現金回饋%數':thr_reward})
                else:
                    if(total_consumption_last_month(cardID,auth_id)<=fir_limit or sec_reward==0): #第一級回饋
                        reward_recommend.append({'cardID':cardID,'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'加油現金回饋%數':fir_reward})
                    else:
                        reward_recommend.append({'cardID':cardID,'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'加油現金回饋%數':sec_reward})
        #加油金優惠
        elif(tmp_dict['gasCash'] is not None):
            #%數優先於金額
            #由當期消費限制大往小
            gm_result=sorted(tmp_dict['gasCash'],key = lambda i: i['當期消費限制'],reverse=True) #由大到小
            for limit in gm_result:
                #判斷是否符合可用星期、地點、消費限制
                if total_consumption_last_month(cardID,auth_id)>=limit['當期消費限制'] and weekday in limit['可用星期'] and (limit['可用地點'] in place_name or place_name in limit['可用地點']):
                    if limit['加油金回饋'][-1:]=='%':
                        money_recommend_percent.append({'cardID':cardID,'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'加油金回饋%數':int(limit['加油金回饋'][:limit['加油金回饋'].rfind('%')])})
                        break
                    elif limit['加油金回饋'][-1:]=='元':
                        money_recommend_wen.append({'cardID':cardID,'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'加油金回饋':int(limit['加油金回饋'][:limit['加油金回饋'].rfind('元')])})
                        break
        #加油點數
        elif(tmp_dict['gasPointReward'] is not None):
            can_use_in_here=0
            #判斷是否在此地可用
            for i in tmp_dict['gasRewLocation']:
                if("之外" in i):
                    if (i[:i.rfind("之外")] not in place_name or place_name not in i[:i.rfind("之外")]) and place_name!=i[:i.rfind("之外")]:
                        can_use_in_here=1
                elif(i in place_name or place_name in i or place_name==i):
                    can_use_in_here=1
            if(can_use_in_here):
                point_recommend.append({'cardID':cardID,'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'幾元一點':tmp_dict['gasPointReward']})
    
    s_result=sorted(save_recommend,key = lambda i: i['現折金額'],reverse=True) #由大到小 
    r_result=sorted(reward_recommend,key = lambda i: i['加油現金回饋%數'],reverse=True) #由大到小
    mp_result=sorted(money_recommend_percent,key = lambda i: i['加油金回饋%數'],reverse=True) #由大到小 
    mw_result=sorted(money_recommend_wen,key = lambda i: i['加油金回饋'],reverse=True) #由大到小
    p_result=sorted(point_recommend,key = lambda i: i['幾元一點']) #由小到大，因為越小越好(幾元一點)
    result=s_result+r_result+mp_result+mw_result+p_result
    recommend_list={'lat':lat,'lng':lng,'placeName':place_name}
    #recommend_list回傳string(ex:現省1.2元、現金回饋5%、50元一點)
    if(len(result)>=3):
        recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':update_which(result[0]),'fir_recommend_bank':result[0]['銀行']})
        recommend_list.update({'sec_recommend_cardID':result[1]['cardID'],'sec_recommend_card':result[1]['卡名'],'sec_recommend_discount':update_which(result[1]),'sec_recommend_bank':result[1]['銀行']})
        recommend_list.update({'thr_recommend_cardID':result[2]['cardID'],'thr_recommend_card':result[2]['卡名'],'thr_recommend_discount':update_which(result[2]),'thr_recommend_bank':result[2]['銀行']})
    elif(len(result)==2):
        recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':update_which(result[0]),'fir_recommend_bank':result[0]['銀行']})
        recommend_list.update({'sec_recommend_cardID':result[1]['cardID'],'sec_recommend_card':result[1]['卡名'],'sec_recommend_discount':update_which(result[1]),'sec_recommend_bank':result[1]['銀行']})
        recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
    elif(len(result)==1):
        recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':update_which(result[0]),'fir_recommend_bank':result[0]['銀行']})
        recommend_list.update({'sec_recommend_cardID':None,'sec_recommend_card':None,'sec_recommend_discount':None,'sec_recommend_bank':None})
        recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
    else:
        recommend_list.update({'fir_recommend_cardID':None,'fir_recommend_card':None,'fir_recommend_discount':None,'fir_recommend_bank':None})
        recommend_list.update({'sec_recommend_cardID':None,'sec_recommend_card':None,'sec_recommend_discount':None,'sec_recommend_bank':None})
        recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
    return recommend_list

# 紅利回饋
# 只包含銀行本身的紅利點數(Ex:Line point不算)
# 會用地點名稱與地點類型去篩可用地點
# recommend_discount回傳string list([紅利倍數,紅利幾元一點])
def point_return_discount(lat,lng,place_name,place_type,auth_id):
    point_recommend_list=[]
    
    #取出該用戶擁有的所有卡種編號(list)
    cards = mongo.db.cusCreditCard.find_one({'id': auth_id}) #Bson
    cards_tmp = dumps(cards) #Json
    tmp_card_dict = json.loads(cards_tmp) #dict
    
    for cardID, level in tmp_card_dict['cardID'].items():
        #level=level[:-2] #把正卡/副卡去掉
        card = mongo.db.reward.find_one({'cardID': cardID}) #Bson
        resp_tmp = dumps(card) #Json
        tmp_dict = json.loads(resp_tmp) #dict
        if tmp_dict['pointReward']==True:
            #因為reward裡面沒有銀行，所以要用卡種編號去creditCard裡面抓
            card_limit = mongo.db.creditCard.find_one({'cardID': cardID}) #Bson
            card_resp_tmp = dumps(card_limit) #Json
            card_dict = json.loads(card_resp_tmp) #dict
            return_point=0
            #先判斷有無回饋倍數與生日當月紅利回饋倍數，再將兩者比較並存入recommend_list
            #紅利回饋限制
            dollar_per_point=0
            if tmp_dict['pointRewMax']=='不限':
                tmp_max_return=-1
            else:
                tmp_max_return=tmp_dict['pointRewMax']
            if(tmp_dict['pointRewDes'] is not None): #回饋倍數
                if(not can_use_in_here(place_name,tmp_dict['excludeLocation'])):
                    for reward in tmp_dict['pointRewDes']:
                        can_use_in_place=0 
                        #判斷是否可在此地使用
                        for place in reward['可用地點']:
                            if(place.lower() in place_name.lower() or place.lower() in place_type or place.lower()==place_name.lower()): 
                                can_use_in_place=1
                            elif '之外' in place and (place[0:place.find('之外')] not in place_name or place_name not in place[0:place.find('之外')]):
                                can_use_in_place=1
                            elif('不限' in place):
                                can_use_in_place=1
                        if reward['可用地點']=='不限':
                            can_use_in_place=1
                        #有無符合卡片等級
                        #有當期帳單限制
                        if(can_use_in_place==1 and reward['當期帳單限制'] is not None and total_consumption_last_month(cardID,auth_id)>=reward['當期帳單限制'] and (level in reward['可用卡別'] or '不限' in reward['可用卡別'])):
                            return_point=reward['回饋倍數']
                            dollar_per_point=reward['幾元一點']
                        #無當期帳單限制
                        elif(can_use_in_place==1 and reward['當期帳單限制'] is None and (level in reward['可用卡別'] or '不限' in reward['可用卡別'])):
                            return_point=reward['回饋倍數']
                            dollar_per_point=reward['幾元一點']
            #生日當月紅利回饋倍數
            if(tmp_dict['pointRewBirth'] is not None): #判斷有無生日當月紅利回饋倍數 #一律使用'非會員'的紅利倍數來比較
                if(not can_use_in_here(place_name,tmp_dict['excludeLocation'])):
                    #判斷是否是生日當月
                    birth_point=0
                    year=datetime.today().year
                    month=datetime.today().month
                    monthRange = calendar.monthrange(datetime.today().year,datetime.today().month)
                    start=datetime(year, month, 1,0,0,0)
                    end=datetime(year, month, monthRange[1],0,0,0)
                    cus_info = mongo.db.customer.find_one({'id': auth_id, 'birthday':{'$gte':start,'$lte':end}}) #Bson
                    cus_info_tmp = dumps(cus_info) #Json
                    cus_info_dict = json.loads(cus_info_tmp) #dict
                    if(cus_info_dict is not None):
                        for name, value in tmp_dict['pointRewBirth'].items():
                            if '非會員' in name:
                                birth_point=value
                        if(birth_point>=return_point): #生日>回饋倍數
                            point_recommend_list.append({'cardID':cardID,'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'紅利幾元一點':dollar_per_point,'紅利倍數':birth_point,'紅利回饋上限':tmp_max_return})
                        else:
                            point_recommend_list.append({'cardID':cardID,'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'紅利幾元一點':dollar_per_point,'紅利倍數':return_point,'紅利回饋上限':tmp_max_return})
                    else: #不是生日當月
                        point_recommend_list.append({'cardID':cardID,'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'紅利幾元一點':dollar_per_point,'紅利倍數':return_point,'紅利回饋上限':tmp_max_return})
            else: #no birthday reward
                if return_point!=0 and dollar_per_point!=0:
                    point_recommend_list.append({'cardID':cardID,'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'紅利幾元一點':dollar_per_point,'紅利倍數':return_point,'紅利回饋上限':tmp_max_return})
              
    result=sorted(point_recommend_list,key = lambda i: (-i['紅利倍數'],i['紅利幾元一點'],-i['紅利回饋上限']))
    tmp_per=result[0]['紅利倍數']
    tmp_wen=result[0]['紅利幾元一點']
    tmp_index=0
    for i in result:
        if result.index(i)==0 and i['紅利回饋上限']==-1:
            i.update({'紅利回饋上限':'不限'})
        elif result.index(i)!=0 and i['紅利回饋上限']==-1 and i['紅利倍數']==tmp_per and i['紅利幾元一點']==tmp_wen:
            i.update({'紅利回饋上限':'不限'})
            result.insert(tmp_index, result.pop(result.index(i)))
            tmp_index=result.index(i)+1
        elif result.index(i)!=0 and i['紅利倍數']==tmp_per and i['紅利幾元一點']==tmp_wen:
            tmp_per=tmp_per
            tmp_wen=tmp_wen
            tmp_index=tmp_index
        else:
            if i['紅利回饋上限']==-1:
                i.update({'紅利回饋上限':'不限'})
            tmp_per=i['紅利倍數']
            tmp_wen=i['紅利幾元一點']
            tmp_index=result.index(i)
    recommend_list={'lat':lat,'lng':lng,'placeName':place_name}
    if(len(result)>=3):
        recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':['紅利'+str(result[0]['紅利倍數'])+'倍','紅利'+str(result[0]['紅利幾元一點'])+'元一點','回饋上限'+str(result[0]['紅利回饋上限'])],'fir_recommend_bank':result[0]['銀行']})
        recommend_list.update({'sec_recommend_cardID':result[1]['cardID'],'sec_recommend_card':result[1]['卡名'],'sec_recommend_discount':['紅利'+str(result[1]['紅利倍數'])+'倍','紅利'+str(result[1]['紅利幾元一點'])+'元一點','回饋上限'+str(result[1]['紅利回饋上限'])],'sec_recommend_bank':result[1]['銀行']})
        recommend_list.update({'thr_recommend_cardID':result[2]['cardID'],'thr_recommend_card':result[2]['卡名'],'thr_recommend_discount':['紅利'+str(result[2]['紅利倍數'])+'倍','紅利'+str(result[2]['紅利幾元一點'])+'元一點','回饋上限'+str(result[2]['紅利回饋上限'])],'thr_recommend_bank':result[2]['銀行']})
    elif(len(result)==2):
        recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':['紅利'+str(result[0]['紅利倍數'])+'倍','紅利'+str(result[0]['紅利幾元一點'])+'元一點','回饋上限'+str(result[0]['紅利回饋上限'])],'fir_recommend_bank':result[0]['銀行']})
        recommend_list.update({'sec_recommend_cardID':result[1]['cardID'],'sec_recommend_card':result[1]['卡名'],'sec_recommend_discount':['紅利'+str(result[1]['紅利倍數'])+'倍','紅利'+str(result[1]['紅利幾元一點'])+'元一點','回饋上限'+str(result[1]['紅利回饋上限'])],'sec_recommend_bank':result[1]['銀行']})
        recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
    elif(len(result)==1):
        recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':['紅利'+str(result[0]['紅利倍數'])+'倍','紅利'+str(result[0]['紅利幾元一點'])+'元一點','回饋上限'+str(result[0]['紅利回饋上限'])],'fir_recommend_bank':result[0]['銀行']})
        recommend_list.update({'sec_recommend_cardID':None,'sec_recommend_card':None,'sec_recommend_discount':None,'sec_recommend_bank':None})
        recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
    else:
        recommend_list.update({'fir_recommend_cardID':None,'fir_recommend_card':None,'fir_recommend_discount':None,'fir_recommend_bank':None})
        recommend_list.update({'sec_recommend_cardID':None,'sec_recommend_card':None,'sec_recommend_discount':None,'sec_recommend_bank':None})
        recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
    return recommend_list

# 電影優惠
# 幾折優先於幾元(除非能取得預計消費消費)
# recommend_discount回傳string(ex:'6折')
def movie_discount(lat,lng,place_name,auth_id):
    che_recommend_list=[]
    wen_recommend_list=[]
    
    #取出該用戶擁有的所有卡種編號(list)
    cards = mongo.db.cusCreditCard.find_one({'id': auth_id}) #Bson
    cards_tmp = dumps(cards) #Json
    tmp_card_dict = json.loads(cards_tmp) #dict
    week=['週一','週二','週三','週四','週五','週六','週日']
    weekday=week[datetime.today().weekday()] #取得今天星期幾
    for cardID, level in tmp_card_dict['cardID'].items():
        #level=level[:-2] #把正卡/副卡去掉
        card = mongo.db.reward.find_one({'cardID': cardID}) #Bson
        resp_tmp = dumps(card) #Json
        tmp_dict = json.loads(resp_tmp) #dict
        #因為reward裡面沒有銀行，所以要用卡種編號去creditCard裡面抓
        card_limit = mongo.db.creditCard.find_one({'cardID': cardID}) #Bson
        card_resp_tmp = dumps(card_limit) #Json
        card_dict = json.loads(card_resp_tmp) #dict
        #判斷此卡是否有電影優惠
        if(tmp_dict['movieReward']):
            #判斷是否在此地可用
            can_use_in_here=0
            for i in tmp_dict['movieRewLocation']:
                if(i in place_name or place_name in i or place_name==i):
                    can_use_in_here=1
            if(can_use_in_here):
                #有當期帳單限制
                if(tmp_dict['movieRewBillMin'] is not None and total_consumption_last_month(cardID,auth_id)>=tmp_dict['movieRewBillMin']): 
                    for discount in tmp_dict['movieRewTerms']:
                        che_discount=0
                        wen_discount=0
                        if(weekday==discount[:discount.find('/')] or '每日'==discount[:discount.find('/')]):
                            if(discount[-1]=='折'):
                                che_discount=int(discount[discount.find('/')+1:-1])
                            elif(discount[-1]=='元'):
                                wen_discount=int(discount[discount.find('/')+1:-1])
                            if(che_discount!=0):
                                che_recommend_list.append({'cardID':cardID,'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'電影回饋':che_discount})
                            else:
                                wen_recommend_list.append({'cardID':cardID,'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'電影回饋':wen_discount})
                #沒有當期帳單限制
                else: 
                    for discount in tmp_dict['movieRewTerms']:
                        che_discount=0
                        wen_discount=0
                        if(weekday==discount[:discount.find('/')] or '每日'==discount[:discount.find('/')]):
                            if(discount[-1]=='折'):
                                che_discount=int(discount[discount.find('/')+1:-1])
                            elif(discount[-1]=='元'):
                                wen_discount=int(discount[discount.find('/')+1:-1])
                            if(che_discount!=0):
                                che_recommend_list.append({'cardID':cardID,'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'電影回饋':che_discount,'type':'折'})
                            else:
                                wen_recommend_list.append({'cardID':cardID,'銀行':card_dict['bankID'],'卡名':tmp_dict['cardName'],'電影回饋':wen_discount,'type':'元'})
    che_result=sorted(che_recommend_list,key = lambda i: i['電影回饋']) #由小到大 
    wen_result=sorted(wen_recommend_list,key = lambda i: i['電影回饋']) #由小到大
    result=che_result+wen_result
    recommend_list={'lat':lat,'lng':lng,'placeName':place_name}
    if(len(result)>=3):
        recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':update_which_type(result[0]),'fir_recommend_bank':result[0]['銀行']})
        recommend_list.update({'sec_recommend_cardID':result[1]['cardID'],'sec_recommend_card':result[1]['卡名'],'sec_recommend_discount':update_which_type(result[1]),'sec_recommend_bank':result[1]['銀行']})
        recommend_list.update({'thr_recommend_cardID':result[2]['cardID'],'thr_recommend_card':result[2]['卡名'],'thr_recommend_discount':update_which_type(result[2]),'thr_recommend_bank':result[2]['銀行']})
    elif(len(result)==2):
        recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':update_which_type(result[0]),'fir_recommend_bank':result[0]['銀行']})
        recommend_list.update({'sec_recommend_cardID':result[1]['cardID'],'sec_recommend_card':result[1]['卡名'],'sec_recommend_discount':update_which_type(result[1]),'sec_recommend_bank':result[1]['銀行']})
        recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
    elif(len(result)==1):
        recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':update_which_type(result[0]),'fir_recommend_bank':result[0]['銀行']})
        recommend_list.update({'sec_recommend_cardID':None,'sec_recommend_card':None,'sec_recommend_discount':None,'sec_recommend_bank':None})
        recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
    else:
        recommend_list.update({'fir_recommend_cardID':None,'fir_recommend_card':None,'fir_recommend_discount':None,'fir_recommend_bank':None})
        recommend_list.update({'sec_recommend_cardID':None,'sec_recommend_card':None,'sec_recommend_discount':None,'sec_recommend_bank':None})
        recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
    return recommend_list

#==========================================================================辦卡推薦==========================================================================#

# 須考慮是否符合職業與年收入低標

# app回傳座標跟地點名稱 'lat':lat,'lng':lng,'地點名稱':
# 用同群且有該卡的人的帳單
def parking_discount_for_apply_withLocation(lat,lng,place_name,auth_id,is_sim_auth,rd_or_ap): #用戶擁有的卡種編號(list) #rd_or_ap: 0:rd, 1:ap
    card_dict=[] #用戶所沒有的卡種編號 [{'卡種編號'},{'卡種編號']]
    parking_recommend_list=[]

    #取出該用戶基本資料
    info = mongo.db.customer.find_one({'id': auth_id}) #Bson
    info_json = dumps(info) #Json
    info_dict = json.loads(info_json)

    #取出該用戶擁有的所有卡種編號(list)
    own_cards = mongo.db.cusCreditCard.find_one({'id': auth_id}) #Bson
    own_cards_tmp = dumps(own_cards) #Json
    own_tmp_card_dict = json.loads(own_cards_tmp)
    #取出所有卡片
    #須考慮年收入是否高於年收入低標，職業是否符合或不限
    cards = mongo.db.creditCard.find({'annIncomeLimit':{'$lte': info_dict['annualIncome']}, 'occuLimit':{'$in':[info_dict['occupation'],"不限"]}}) #Bson
    cards_tmp = dumps(cards) #Json
    tmp_card_dict = json.loads(cards_tmp)
    #將此用戶沒有的卡存入card_dict
    if(own_tmp_card_dict['cardID'] is None): #該用戶一張卡都沒有
        card_dict=tmp_card_dict
    else:
        for elem in tmp_card_dict:
            if(elem['cardID'] not in own_tmp_card_dict['cardID'].keys()):
                card_dict.append(elem)
    #判斷是否符合資格
    for tmp_card in card_dict:
        similar_person_id=""
        cardID=tmp_card['cardID']
        card = mongo.db.reward.find_one({'cardID': cardID}) #Bson
        resp_tmp = dumps(card) #Json
        tmp_dict = json.loads(resp_tmp) #dict
        #因為reward裡面沒有銀行，所以要用卡種編號去creditCard裡面抓
        card_limit = mongo.db.creditCard.find_one({'cardID': cardID}) #Bson
        card_resp_tmp = dumps(card_limit) #Json
        card_dict = json.loads(card_resp_tmp) #dict
        if(is_sim_auth==2):
            similar_person_id=similar_person_id+auth_id
            #取出此人此卡的level
            per_cards = mongo.db.cusCreditCard.find_one({'id': similar_person_id}) #Bson
            per_cards_tmp = dumps(per_cards) #Json
            per_tmp_card_dict = json.loads(per_cards_tmp)
            level=per_tmp_card_dict['cardID'][cardID]
        else:
            #取出跟他同群且有此卡的人的id
            cus_records = mongo.db.customer.find_one({'id':auth_id}) #Bson
            cus_resp_tmp = dumps(cus_records) #Json
            cus_tmp_dict = json.loads(cus_resp_tmp) #dict
            feature_value=dict()
            feature_value['age']=cus_tmp_dict['age']
            feature_value['sex']=cus_tmp_dict['sex']
            feature_value['annualIncome']=cus_tmp_dict['annualIncome']
            feature_value['expenseMonth']=cus_tmp_dict['expenseMonth'] #要再寫一個計算的
            similar_persons=context.find_similar_(auth_id,feature_value)
            for person in similar_persons:
                sim_per_card = mongo.db.cusCreditCard.find_one({'id': person['id']}) #Bson
                sim_resp_tmp = dumps(sim_per_card) #Json
                sim_tmp_dict = json.loads(sim_resp_tmp) #dict
                if cardID in sim_tmp_dict['cardID'].keys():
                    similar_person_id=similar_person_id+person['id']
                    break
            #取出此人此卡的level
            per_cards = mongo.db.cusCreditCard.find_one({'id': similar_person_id}) #Bson
            per_cards_tmp = dumps(per_cards) #Json
            per_tmp_card_dict = json.loads(per_cards_tmp)
            level=per_tmp_card_dict['cardID'][cardID]
            #level=level[:-2] #把正卡/副卡去掉
        #dict空值為None 
        if(tmp_dict['parkingRewMax'] is not None ):
            can_park=0
            for i in tmp_dict['parkingRewLocation']:
                if(i in place_name or place_name in i or place_name==i):
                    can_park=1
            if(can_park==1):
                if(tmp_dict['parkingRewStatementMin']['上個月帳單限制'] is not None and total_consumption_last_month(cardID,similar_person_id)>tmp_dict['parkingRewStatementMin']['上個月帳單限制']):
                    if(type(tmp_dict['parkingRewMax'])==dict and level in tmp_dict['parkingRewMax'].keys()):
                        parking_recommend_list.append({'cardID':cardID,'優惠時數':tmp_dict['parkingRewMax'][level],'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName']})
                    else: #沒有等級差別
                        parking_recommend_list.append({'cardID':cardID,'優惠時數':tmp_dict['parkingRewMax'],'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName']})
                elif(tmp_dict['parkingRewStatementMin']['前三個月帳單限制'] is not None and total_consumption_last_three_months(cardID,similar_person_id)>tmp_dict['parkingRewStatementMin']['前三個月帳單限制']):
                    if(type(tmp_dict['parkingRewMax'])==dict and level in tmp_dict['parkingRewMax'].keys()):
                        parking_recommend_list.append({'cardID':cardID,'優惠時數':tmp_dict['parkingRewMax'][level],'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName']})
                    else:
                        parking_recommend_list.append({'cardID':cardID,'優惠時數':tmp_dict['parkingRewMax'],'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName']}) 
                elif(tmp_dict['parkingRewStatementMin']['前十二個月帳單限制'] is not None and total_consumption_last_year(cardID,similar_person_id)>tmp_dict['parkingRewStatementMin']['前十二個月帳單限制']):
                    if(type(tmp_dict['parkingRewMax'])==dict and level in tmp_dict['parkingRewMax'].keys()):
                        parking_recommend_list.append({'cardID':cardID,'優惠時數':tmp_dict['parkingRewMax'][level],'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName']})
                    else:
                        parking_recommend_list.append({'cardID':cardID,'優惠時數':tmp_dict['parkingRewMax'],'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName']})
                #elif(tmp_dict['停車_當期帳單(前一個月)'] is not None and tmp_dict['停車_當期帳單(前三個月)'] is not None and tmp_dict['停車_當期帳單(前12個月)'] is not None and tmp_dict['消費滿'] is not None):
                #    parking_recommend_list.append({'卡片id':tmp_dict['卡片id'],'優惠時數':tmp_dict['可停時數'],'銀行':tmp_card['bankID'],'卡名':tmp_dict['卡片名稱']})
        
    result = sorted(parking_recommend_list,key = lambda i: i['優惠時數'],reverse=True)
    recommend_list={'lat':lat,'lng':lng,'placeName':place_name}
    if rd_or_ap==0: #rd
        if(len(result)>=3):
            recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':'可停'+str(result[0]['優惠時數'])+'小時','fir_recommend_bank':result[0]['銀行']})
            recommend_list.update({'sec_recommend_cardID':result[1]['cardID'],'sec_recommend_card':result[1]['卡名'],'sec_recommend_discount':'可停'+str(result[1]['優惠時數'])+'小時','sec_recommend_bank':result[1]['銀行']})
            recommend_list.update({'thr_recommend_cardID':result[2]['cardID'],'thr_recommend_card':result[2]['卡名'],'thr_recommend_discount':'可停'+str(result[2]['優惠時數'])+'小時','thr_recommend_bank':result[2]['銀行']})
        elif(len(result)==2):
            recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':'可停'+str(result[0]['優惠時數'])+'小時','fir_recommend_bank':result[0]['銀行']})
            recommend_list.update({'sec_recommend_cardID':result[1]['cardID'],'sec_recommend_card':result[1]['卡名'],'sec_recommend_discount':'可停'+str(result[1]['優惠時數'])+'小時','sec_recommend_bank':result[1]['銀行']})
            recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
        elif(len(result)==1):
            recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':'可停'+str(result[0]['優惠時數'])+'小時','fir_recommend_bank':result[0]['銀行']})
            recommend_list.update({'sec_recommend_cardID':None,'sec_recommend_card':None,'sec_recommend_discount':None,'sec_recommend_bank':None})
            recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
        else:
            recommend_list.update({'fir_recommend_cardID':None,'fir_recommend_card':None,'fir_recommend_discount':None,'fir_recommend_bank':None})
            recommend_list.update({'sec_recommend_cardID':None,'sec_recommend_card':None,'sec_recommend_discount':None,'sec_recommend_bank':None})
            recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
    else:
        if len(result)==0:
            recommend_list.update({'park_recommend_cardID1':None,'park_recommend_card1':None,'park_recommend_discount1':None,'park_recommend_bank1':None})
        else:
            for i in range(len(result)):
                recommend_list.update({'park_recommend_cardID'+str(i+1):result[i]['cardID'],'park_recommend_card'+str(i+1):result[i]['卡名'],'park_recommend_discount'+str(i+1):'可停'+str(result[i]['優惠時數'])+'小時','park_recommend_bank'+str(i+1):result[i]['銀行']})
    #resp = dumps(parking_recommend_list)
    return recommend_list

#現金回饋
#現金_當期帳單: 存下限金額
#不可：便利商店(含7-ELEVEN、全家、萊爾富及OK超商)、連鎖速食店及全聯福利中心
#待改進：尚未考量回饋上限
#recommend_list回傳string(ex:現金回饋5%)
def cash_return_discount_for_apply_withLocation(lat,lng,place_name,auth_id,is_sim_auth,rd_or_ap): #用戶擁有的卡種編號(list)
    card_dict=[] #用戶所沒有的卡種編號 [{'卡種編號'},{'卡種編號']]
    cash_recommend_list=[]

    #取出該用戶基本資料
    info = mongo.db.customer.find_one({'id': auth_id}) #Bson
    info_json = dumps(info) #Json
    info_dict = json.loads(info_json)

    #取出該用戶擁有的所有卡種編號(list)
    own_cards = mongo.db.cusCreditCard.find_one({'id': auth_id}) #Bson
    own_cards_tmp = dumps(own_cards) #Json
    own_tmp_card_dict = json.loads(own_cards_tmp)
    #取出所有卡片
    #須考慮年收入是否高於年收入低標，職業是否符合或不限'
    occu = re.compile(info_dict['occupation']+'|不限',re.I)
    cards = mongo.db.creditCard.find({'annIncomeLimit':{'$lte': info_dict['annualIncome']}, "occuLimit": {'$regex': occu}})
    cards_tmp = dumps(cards) #Json
    tmp_card_dict = json.loads(cards_tmp)
    
    #將此用戶沒有的卡存入card_dict
    if(own_tmp_card_dict['cardID'] is None): #該用戶一張卡都沒有
        card_dict=tmp_card_dict
    else:
        for elem in tmp_card_dict:
            if(elem['cardID'] not in own_tmp_card_dict['cardID'].keys()):
                card_dict.append(elem)
    for tmp_card in card_dict:
        similar_person_id=""
        cardID=tmp_card['cardID']
        card = mongo.db.reward.find_one({'cardID': cardID}) #Bson
        resp_tmp = dumps(card) #Json
        tmp_dict = json.loads(resp_tmp) #dict
        #因為reward裡面沒有銀行，所以要用卡種編號去creditCard裡面抓
        if(is_sim_auth==2): #舊用戶
            similar_person_id=similar_person_id+auth_id
        else:
            #取出跟他同群且有此卡的人的id
            feature_value=dict()
            feature_value['age']=info_dict['age']
            feature_value['sex']=info_dict['sex']
            feature_value['annualIncome']=info_dict['annualIncome']
            feature_value['expenseMonth']=info_dict['expenseMonth'] #要再寫一個計算的
            similar_persons=context.find_similar_(auth_id,feature_value)
            for person in similar_persons:
                sim_per_card = mongo.db.cusCreditCard.find_one({'id': person['id']}) #Bson
                sim_resp_tmp = dumps(sim_per_card) #Json
                sim_tmp_dict = json.loads(sim_resp_tmp) #dict
                if cardID in sim_tmp_dict['cardID'].keys():
                    similar_person_id=similar_person_id+person['id']
                    break
        if(tmp_dict['cashReward'] is not None): #判斷該卡是否有現金回饋優惠
            if(not can_use_in_here(place_name,tmp_dict['excludeLocation'])):
                if("現金回饋4" in tmp_dict['cashReward'].keys()): 
                    if(total_consumption_last_month(cardID,similar_person_id)>=tmp_dict['cashReward']['現金回饋4'][4] and (can_use_in_here(place_name,tmp_dict['cashReward']['現金回饋4'][3]) or "不限" in tmp_dict['cashReward']['現金回饋4'][3]) and (place_name not in cannot_use_in_here(tmp_dict['cashReward']['現金回饋4'][3]))):
                        cash_recommend_list.append({'cardID':cardID,'現金回饋%數':tmp_dict['cashReward']['現金回饋4'][0],'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'回饋上限':has_limit_or_not(tmp_dict['cashReward']['現金回饋4'][2])})
                    elif(total_consumption_last_month(cardID,similar_person_id)>=tmp_dict['cashReward']['現金回饋3'][4] and (can_use_in_here(place_name,tmp_dict['cashReward']['現金回饋3'][3]) or "不限" in tmp_dict['cashReward']['現金回饋3'][3]) and (place_name not in cannot_use_in_here(tmp_dict['cashReward']['現金回饋3'][3]))):
                        cash_recommend_list.append({'cardID':cardID,'現金回饋%數':tmp_dict['cashReward']['現金回饋3'][0],'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'回饋上限':has_limit_or_not(tmp_dict['cashReward']['現金回饋3'][2])})
                    elif(total_consumption_last_month(cardID,similar_person_id)>=tmp_dict['cashReward']['現金回饋2'][4] and (can_use_in_here(place_name,tmp_dict['cashReward']['現金回饋2'][3]) or "不限" in tmp_dict['cashReward']['現金回饋2'][3]) and (place_name not in cannot_use_in_here(tmp_dict['cashReward']['現金回饋2'][3]))):
                        cash_recommend_list.append({'cardID':cardID,'現金回饋%數':tmp_dict['cashReward']['現金回饋2'][0],'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'回饋上限':has_limit_or_not(tmp_dict['cashReward']['現金回饋2'][2])})
                    elif(total_consumption_last_month(cardID,similar_person_id)>=tmp_dict['cashReward']['現金回饋1'][4] and (can_use_in_here(place_name,tmp_dict['cashReward']['現金回饋1'][3]) or "不限" in tmp_dict['cashReward']['現金回饋1'][3]) and (place_name not in cannot_use_in_here(tmp_dict['cashReward']['現金回饋1'][3]))):
                        cash_recommend_list.append({'cardID':cardID,'現金回饋%數':tmp_dict['cashReward']['現金回饋1'][0],'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'回饋上限':has_limit_or_not(tmp_dict['cashReward']['現金回饋1'][2])})
                elif("現金回饋3" in tmp_dict['cashReward'].keys()): 
                    if(total_consumption_last_month(cardID,similar_person_id)>=tmp_dict['cashReward']['現金回饋3'][4] and (can_use_in_here(place_name,tmp_dict['cashReward']['現金回饋3'][3]) or "不限" in tmp_dict['cashReward']['現金回饋3'][3]) and (place_name not in cannot_use_in_here(tmp_dict['cashReward']['現金回饋3'][3]))):
                        cash_recommend_list.append({'cardID':cardID,'現金回饋%數':tmp_dict['cashReward']['現金回饋3'][0],'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'回饋上限':has_limit_or_not(tmp_dict['cashReward']['現金回饋3'][2])})
                    elif(total_consumption_last_month(cardID,similar_person_id)>=tmp_dict['cashReward']['現金回饋2'][4] and (can_use_in_here(place_name,tmp_dict['cashReward']['現金回饋2'][3]) or "不限" in tmp_dict['cashReward']['現金回饋2'][3]) and (place_name not in cannot_use_in_here(tmp_dict['cashReward']['現金回饋2'][3]))):
                        cash_recommend_list.append({'cardID':cardID,'現金回饋%數':tmp_dict['cashReward']['現金回饋2'][0],'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'回饋上限':has_limit_or_not(tmp_dict['cashReward']['現金回饋2'][2])})
                    elif(total_consumption_last_month(cardID,similar_person_id)>=tmp_dict['cashReward']['現金回饋1'][4] and (can_use_in_here(place_name,tmp_dict['cashReward']['現金回饋1'][3]) or "不限" in tmp_dict['cashReward']['現金回饋1'][3]) and (place_name not in cannot_use_in_here(tmp_dict['cashReward']['現金回饋1'][3]))):
                        cash_recommend_list.append({'cardID':cardID,'現金回饋%數':tmp_dict['cashReward']['現金回饋1'][0],'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'回饋上限':has_limit_or_not(tmp_dict['cashReward']['現金回饋1'][2])})
                elif("現金回饋2" in tmp_dict['cashReward'].keys()): 
                    if(total_consumption_last_month(cardID,similar_person_id)>=tmp_dict['cashReward']['現金回饋2'][4] and (can_use_in_here(place_name,tmp_dict['cashReward']['現金回饋2'][3]) or "不限" in tmp_dict['cashReward']['現金回饋2'][3]) and place_name not in cannot_use_in_here(tmp_dict['cashReward']['現金回饋2'][3])):
                        cash_recommend_list.append({'cardID':cardID,'現金回饋%數':tmp_dict['cashReward']['現金回饋2'][0],'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'回饋上限':has_limit_or_not(tmp_dict['cashReward']['現金回饋2'][2])})
                    elif(total_consumption_last_month(cardID,similar_person_id)>=tmp_dict['cashReward']['現金回饋1'][4] and (can_use_in_here(place_name,tmp_dict['cashReward']['現金回饋1'][3]) or "不限" in tmp_dict['cashReward']['現金回饋1'][3]) and (place_name not in cannot_use_in_here(tmp_dict['cashReward']['現金回饋1'][3]))):
                        cash_recommend_list.append({'cardID':cardID,'現金回饋%數':tmp_dict['cashReward']['現金回饋1'][0],'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'回饋上限':has_limit_or_not(tmp_dict['cashReward']['現金回饋1'][2])})
                else: #只有現金回饋1
                    if(tmp_dict['cashReward']['現金回饋1'] is not None):
                        if(total_consumption_last_month(cardID,similar_person_id)>=tmp_dict['cashReward']['現金回饋1'][4] and (can_use_in_here(place_name,tmp_dict['cashReward']['現金回饋1'][3]) or "不限" in tmp_dict['cashReward']['現金回饋1'][3]) and (place_name not in cannot_use_in_here(tmp_dict['cashReward']['現金回饋1'][3]))):
                            cash_recommend_list.append({'cardID':cardID,'現金回饋%數':tmp_dict['cashReward']['現金回饋1'][0],'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'回饋上限':has_limit_or_not(tmp_dict['cashReward']['現金回饋1'][2])})
           
    result = sorted(cash_recommend_list,key = lambda i:(-i['現金回饋%數'],-i['回饋上限'])) 
    tmp_per=result[0]['現金回饋%數']
    tmp_index=0
    for i in result:
        if result.index(i)!=0 and i['回饋上限']==-1 and i['現金回饋%數']==tmp_per:
            if(tmp_index==0):
                result.insert(0, result.pop(result.index(i)))
            else:
                result.insert(tmp_index, result.pop(result.index(i)))
            tmp_index=result.index(i)+1
        elif result.index(i)!=0 and i['現金回饋%數']==tmp_per:
            tmp_per=tmp_per
            tmp_index=tmp_index
        else:
            tmp_per=i['現金回饋%數']
            tmp_index=result.index(i)      
    recommend_list={'lat':lat,'lng':lng,'placeName':place_name}
    if(rd_or_ap==0):
        if(len(result)>=3):
            recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':'現金回饋'+str(result[0]['現金回饋%數'])+'%','fir_recommend_bank':result[0]['銀行']})
            recommend_list.update({'sec_recommend_cardID':result[1]['cardID'],'sec_recommend_card':result[1]['卡名'],'sec_recommend_discount':'現金回饋'+str(result[1]['現金回饋%數'])+'%','sec_recommend_bank':result[1]['銀行']})
            recommend_list.update({'thr_recommend_cardID':result[2]['cardID'],'thr_recommend_card':result[2]['卡名'],'thr_recommend_discount':'現金回饋'+str(result[2]['現金回饋%數'])+'%','thr_recommend_bank':result[2]['銀行']})
        elif(len(result)==2):
            recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':'現金回饋'+str(result[0]['現金回饋%數'])+'%','fir_recommend_bank':result[0]['銀行']})
            recommend_list.update({'sec_recommend_cardID':result[1]['cardID'],'sec_recommend_card':result[1]['卡名'],'sec_recommend_discount':'現金回饋'+str(result[1]['現金回饋%數'])+'%','sec_recommend_bank':result[1]['銀行']})
            recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
        elif(len(result)==1):
            recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':'現金回饋'+str(result[0]['現金回饋%數'])+'%','fir_recommend_bank':result[0]['銀行']})
            recommend_list.update({'sec_recommend_cardID':None,'sec_recommend_card':None,'sec_recommend_discount':None,'sec_recommend_bank':None})
            recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
        else:
            recommend_list.update({'fir_recommend_cardID':None,'fir_recommend_card':None,'fir_recommend_discount':None,'fir_recommend_bank':None})
            recommend_list.update({'sec_recommend_cardID':None,'sec_recommend_card':None,'sec_recommend_discount':None,'sec_recommend_bank':None})
            recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
    else:
        if len(result)==0:
            recommend_list.update({'cash_recommend_cardID1':None,'cash_recommend_card1':None,'cash_recommend_discount1':None,'cash_recommend_bank1':None})
        else:
            for i in range(len(result)):
                recommend_list.update({'cash_recommend_cardID'+str(i+1):result[i]['cardID'],'cash_recommend_card'+str(i+1):result[i]['卡名'],'cash_recommend_discount'+str(i+1):'現金回饋'+str(result[i]['現金回饋%數'])+'%','cash_recommend_bank'+str(i+1):result[i]['銀行']})

    return recommend_list     

#推薦順序：現折優惠>現金回饋>(加油金)>加油點數
#除非能得到使用者欲加公升數與當前加油站油價，否則無法比較
#加油點數目前只考慮汽車
#加油方式是取記帳紀錄裡頻率較高的那個
def gas_discount_for_apply_withLocation(lat,lng,place_name,auth_id,is_sim_auth,rd_or_ap):
    save_recommend=[] #現折優惠
    reward_recommend=[] #現金回饋
    money_recommend_percent=[] #加油金(%)
    money_recommend_wen=[] #加油金(金額)
    point_recommend=[] #加油點數
    card_dict=[] #用戶所沒有的卡種編號 [{'卡種編號'},{'卡種編號']]
    
     #取出該用戶基本資料
    info = mongo.db.customer.find_one({'id': auth_id}) #Bson
    info_json = dumps(info) #Json
    info_dict = json.loads(info_json)

    #取出該用戶擁有的所有卡種編號(list)
    own_cards = mongo.db.cusCreditCard.find_one({'id': auth_id}) #Bson
    own_cards_tmp = dumps(own_cards) #Json
    own_tmp_card_dict = json.loads(own_cards_tmp)
    #取出所有卡片
    #須考慮年收入是否高於年收入低標，職業是否符合或不限
    occu = re.compile(info_dict['occupation']+'|不限',re.I)
    cards = mongo.db.creditCard.find({'annIncomeLimit':{'$lte': info_dict['annualIncome']}, "occuLimit": {'$regex': occu}})
    cards_tmp = dumps(cards) #Json
    tmp_card_dict = json.loads(cards_tmp)

    #將此用戶沒有的卡存入card_dict
    if(own_tmp_card_dict['cardID'] is None): #該用戶一張卡都沒有
        card_dict=tmp_card_dict
    else:
        for elem in tmp_card_dict:
            if(elem['cardID'] not in own_tmp_card_dict['cardID'].keys()):
                card_dict.append(elem)
    
    for tmp_card in card_dict:
        cardID=tmp_card['cardID']
        card = mongo.db.reward.find_one({'cardID': cardID}) #Bson
        resp_tmp = dumps(card) #Json
        tmp_dict = json.loads(resp_tmp) #dict
        #因為reward裡面沒有銀行，所以要用卡種編號去creditCard裡面抓
        week=['週一','週二','週三','週四','週五','週六','週日']
        weekday=week[datetime.today().weekday()] #取得今天星期幾
        result=[]
        if(is_sim_auth==2):
            similar_person_id=auth_id
        else:
            #取出跟他同群且有此卡的人的id
            feature_value=dict()
            feature_value['age']=info_dict['age']
            feature_value['sex']=info_dict['sex']
            feature_value['annualIncome']=info_dict['annualIncome']
            feature_value['expenseMonth']=info_dict['expenseMonth'] #要再寫一個計算的
            similar_persons=context.find_similar_(auth_id,feature_value)
            for person in similar_persons:
                sim_per_card = mongo.db.cusCreditCard.find_one({'id': person['id']}) #Bson
                sim_resp_tmp = dumps(sim_per_card) #Json
                sim_tmp_dict = json.loads(sim_resp_tmp) #dict
                if cardID in sim_tmp_dict['cardID'].keys():
                    similar_person_id=person['id']
                    break   
        #判斷此卡是否有加油優惠
        if(tmp_dict['gasReward'] is not None):
            can_use_in_here=0
            #判斷是否在此地可用
            for i in tmp_dict['gasRewLocation']:
                if("之外" in i):
                    if (i[:i.rfind("之外")] not in place_name or place_name not in i[:i.rfind("之外")]) and place_name!=i[:i.rfind("之外")]:
                        can_use_in_here=1
                elif(i in place_name or place_name in i or place_name==i):
                    can_use_in_here=1
            if(can_use_in_here):
                #取出該用戶所有記帳資料並計算哪種加油方式頻率高
                records = mongo.db.bookkeepingRecord.find({'id': similar_person_id}) #Bson
                records_tmp = dumps(records) #Json
                tmp_record_dict = json.loads(records_tmp) #dict
                self=0
                not_self=0
                for record in tmp_record_dict:
                    if(record['consumeType']=='自助加油'):
                        self+=1
                    elif(record['consumeType']=='人工加油'):
                        not_self+=1
                if(self>=not_self):
                    prefer_mode='自助'
                else:
                    prefer_mode='人工'

                for i in tmp_dict['gasReward']:
                    reward_mode=i[0:i.find('/')] #加油方式
                    r=i[i.find('/')+1:]
                    reward_type=r[0:r.find('/')] #汽油or柴油
                    reward_weekday=r[r.find('/')+1:r.rfind('/')] #可用星期
                    reward_account=float(r[r.rfind('/')+1:len(r)]) #現折金額
                    #判斷今天是否在可用星期內
                    in_week=0
                    if(reward_weekday=='不限'):
                        in_week=1
                    elif(reward_weekday=='平日'):
                        if(datetime.today().weekday()<=5):
                            in_week=1
                    elif(reward_weekday==weekday):
                        in_week=1
                    if(prefer_mode==reward_mode and reward_type=='汽油' and in_week):
                        save_recommend.append({'cardID':cardID,'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'加油方式':reward_mode,'可用星期':reward_weekday,'現折金額':reward_account})
                    #result = sorted(save_recommend,key = lambda i: i['現折金額'],reverse=True) #由大到小 
        elif(tmp_dict['gasCashReward'] is not None):
            can_use_in_here=0
            #判斷是否在此地可用
            for i in tmp_dict['gasRewLocation']:
                if("之外" in i):
                    if (i[:i.rfind("之外")] not in place_name or place_name not in i[:i.rfind("之外")]) and place_name!=i[:i.rfind("之外")]:
                        can_use_in_here=1
                elif(i in place_name or place_name in i or place_name==i):
                    can_use_in_here=1
            if(can_use_in_here):
                fir_limit=int(tmp_dict['gasCashReward'][0:tmp_dict['gasCashReward'].find('/')])
                sec_limit=int(tmp_dict['gasCashReward'][tmp_dict['gasCashReward'].find('/')+1:tmp_dict['gasCashReward'].find('//')])
                fir_reward=int(tmp_dict['gasCashReward'][tmp_dict['gasCashReward'].find('//')+2:tmp_dict['gasCashReward'].rfind('/')][0:tmp_dict['gasCashReward'][tmp_dict['gasCashReward'].find('//')+2:tmp_dict['gasCashReward'].rfind('/')].find('/')])
                sec_reward=int(tmp_dict['gasCashReward'][tmp_dict['gasCashReward'].find('//')+2:tmp_dict['gasCashReward'].rfind('/')][tmp_dict['gasCashReward'][tmp_dict['gasCashReward'].find('//')+2:tmp_dict['gasCashReward'].rfind('/')].find('/')+1:])
                thr_reward=int(tmp_dict['gasCashReward'][tmp_dict['gasCashReward'].rfind('/')+1:])
                if sec_limit!=0:
                    if(total_consumption_last_month(cardID,similar_person_id)<=fir_limit): #第一級回饋
                        reward_recommend.append({'cardID':cardID,'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'加油現金回饋%數':fir_reward})
                    elif(total_consumption_last_month(cardID,similar_person_id)<=sec_limit and total_consumption_last_month(cardID,similar_person_id)>fir_limit): #第二級回饋
                        reward_recommend.append({'cardID':cardID,'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'加油現金回饋%數':sec_reward})
                    else: #第三級回饋
                        reward_recommend.append({'cardID':cardID,'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'加油現金回饋%數':thr_reward})
                else:
                    if(total_consumption_last_month(cardID,auth_id)<=fir_limit or sec_reward==0): #第一級回饋
                        reward_recommend.append({'cardID':cardID,'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'加油現金回饋%數':fir_reward})
                    else:
                        reward_recommend.append({'cardID':cardID,'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'加油現金回饋%數':sec_reward})
        elif(tmp_dict['gasCash'] is not None):
            #%數優先於金額
            #由當期消費限制大往小
            gm_result=sorted(tmp_dict['gasCash'],key = lambda i: i['當期消費限制'],reverse=True) #由大到小
            for limit in gm_result:
                #判斷是否符合可用星期、地點、消費限制
                if total_consumption_last_month(cardID,similar_person_id)>=limit['當期消費限制'] and weekday in limit['可用星期'] and (limit['可用地點'] in place_name or place_name in limit['可用地點']):
                    if limit['加油金回饋'][-1:]=='%':
                        money_recommend_percent.append({'cardID':cardID,'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'加油金回饋%數':int(limit['加油金回饋'][:limit['加油金回饋'].rfind('%')])})
                        break
                    elif limit['加油金回饋'][-1:]=='元':
                        money_recommend_wen.append({'cardID':cardID,'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'加油金回饋':int(limit['加油金回饋'][:limit['加油金回饋'].rfind('元')])})
                        break
        elif(tmp_dict['gasPointReward'] is not None):
            can_use_in_here=0
            #判斷是否在此地可用
            for i in tmp_dict['gasRewLocation']:
                if("之外" in i):
                    if (i[:i.rfind("之外")] not in place_name or place_name not in i[:i.rfind("之外")]) and place_name!=i[:i.rfind("之外")]:
                        can_use_in_here=1
                elif(i in place_name or place_name in i or place_name==i):
                    can_use_in_here=1
            if(can_use_in_here):
                point_recommend.append({'cardID':cardID,'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'幾元一點':tmp_dict['gasPointReward']})
    
    s_result=sorted(save_recommend,key = lambda i: i['現折金額'],reverse=True) #由大到小 
    r_result=sorted(reward_recommend,key = lambda i: i['加油現金回饋%數'],reverse=True) #由大到小 
    mp_result=sorted(money_recommend_percent,key = lambda i: i['加油金回饋%數'],reverse=True) #由大到小 
    mw_result=sorted(money_recommend_wen,key = lambda i: i['加油金回饋'],reverse=True) #由大到小
    p_result=sorted(point_recommend,key = lambda i: i['幾元一點']) #由小到大，因為越小越好(幾元一點)
    result=s_result+r_result+mp_result+mw_result+p_result
    recommend_list={'lat':lat,'lng':lng,'placeName':place_name}
    #recommend_list回傳string(ex:現省1.2元、現金回饋5%、50元一點)
    if rd_or_ap==0:
        if(len(result)>=3):
            recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':update_which(result[0]),'fir_recommend_bank':result[0]['銀行']})
            recommend_list.update({'sec_recommend_cardID':result[1]['cardID'],'sec_recommend_card':result[1]['卡名'],'sec_recommend_discount':update_which(result[1]),'sec_recommend_bank':result[1]['銀行']})
            recommend_list.update({'thr_recommend_cardID':result[2]['cardID'],'thr_recommend_card':result[2]['卡名'],'thr_recommend_discount':update_which(result[2]),'thr_recommend_bank':result[2]['銀行']})
        elif(len(result)==2):
            recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':update_which(result[0]),'fir_recommend_bank':result[0]['銀行']})
            recommend_list.update({'sec_recommend_cardID':result[1]['cardID'],'sec_recommend_card':result[1]['卡名'],'sec_recommend_discount':update_which(result[1]),'sec_recommend_bank':result[1]['銀行']})
            recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
        elif(len(result)==1):
            recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':update_which(result[0]),'fir_recommend_bank':result[0]['銀行']})
            recommend_list.update({'sec_recommend_cardID':None,'sec_recommend_card':None,'sec_recommend_discount':None,'sec_recommend_bank':None})
            recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
        else:
            recommend_list.update({'fir_recommend_cardID':None,'fir_recommend_card':None,'fir_recommend_discount':None,'fir_recommend_bank':None})
            recommend_list.update({'sec_recommend_cardID':None,'sec_recommend_card':None,'sec_recommend_discount':None,'sec_recommend_bank':None})
            recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
    else:
        if(len(result)==0):
            recommend_list.update({'gas_recommend_cardID1':None,'gas_recommend_card1':None,'gas_recommend_discount1':None,'gas_recommend_bank1':None})
        else:
            for i in range(len(result)):
                recommend_list.update({'gas_recommend_cardID'+str(i+1):result[i]['cardID'],'gas_recommend_card'+str(i+1):result[i]['卡名'],'gas_recommend_discount'+str(i+1):update_which(result[i]),'gas_recommend_bank'+str(i+1):result[i]['銀行']})
    return recommend_list

#只包含銀行本身的紅利點數
#會用地點名稱與地點類型去篩可用地點
#recommend_discount回傳string list([紅利倍數,紅利幾元一點])
def point_return_discount_for_apply_withLocation(lat,lng,place_name,place_type,auth_id,is_sim_auth,rd_or_ap):
    point_recommend_list=[]
    card_dict=[] #用戶所沒有的卡種編號 [{'卡種編號'},{'卡種編號']]
    
    #取出該用戶基本資料
    info = mongo.db.customer.find_one({'id': auth_id}) #Bson
    info_json = dumps(info) #Json
    info_dict = json.loads(info_json)

    #取出該用戶擁有的所有卡種編號(list)
    own_cards = mongo.db.cusCreditCard.find_one({'id': auth_id}) #Bson
    own_cards_tmp = dumps(own_cards) #Json
    own_tmp_card_dict = json.loads(own_cards_tmp)
    #取出所有卡片
    #須考慮年收入是否高於年收入低標，職業是否符合或不限
    occu = re.compile(info_dict['occupation']+'|不限',re.I)
    cards = mongo.db.creditCard.find({'annIncomeLimit':{'$lte': info_dict['annualIncome']}, "occuLimit": {'$regex': occu}})
    cards_tmp = dumps(cards) #Json
    tmp_card_dict = json.loads(cards_tmp)
    #將此用戶沒有的卡存入card_dict
    if(own_tmp_card_dict['cardID'] is None): #該用戶一張卡都沒有
        card_dict=tmp_card_dict
    else:
        for elem in tmp_card_dict:
            if(elem['cardID'] not in own_tmp_card_dict['cardID'].keys()):
                card_dict.append(elem)
    
    for tmp_card in card_dict:
        cardID=tmp_card['cardID']
        card = mongo.db.reward.find_one({'cardID': cardID}) #Bson
        resp_tmp = dumps(card) #Json
        tmp_dict = json.loads(resp_tmp) #dict
        if tmp_dict['pointReward']==True: #have point reward
            #因為reward裡面沒有銀行，所以要用卡種編號去creditCard裡面抓
            if(is_sim_auth==2):
                similar_person_id=auth_id
                #取出此人此卡的level
                per_cards = mongo.db.cusCreditCard.find_one({'id': similar_person_id}) #Bson
                per_cards_tmp = dumps(per_cards) #Json
                per_tmp_card_dict = json.loads(per_cards_tmp)
                level=per_tmp_card_dict['cardID'][cardID]
            else:
                #取出跟他同群且有此卡的人的id
                feature_value=dict()
                feature_value['age']=info_dict['age']
                feature_value['sex']=info_dict['sex']
                feature_value['annualIncome']=info_dict['annualIncome']
                feature_value['expenseMonth']=info_dict['expenseMonth'] #要再寫一個計算的
                similar_persons=context.find_similar_(auth_id,feature_value)
                for person in similar_persons:
                    sim_per_card = mongo.db.cusCreditCard.find_one({'id': person['id']}) #Bson
                    sim_resp_tmp = dumps(sim_per_card) #Json
                    sim_tmp_dict = json.loads(sim_resp_tmp) #dict
                    if cardID in sim_tmp_dict['cardID'].keys():
                        similar_person_id=person['id']
                        break
                #取出此人此卡的level
                per_cards = mongo.db.cusCreditCard.find_one({'id': similar_person_id}) #Bson
                per_cards_tmp = dumps(per_cards) #Json
                per_tmp_card_dict = json.loads(per_cards_tmp)
                level=per_tmp_card_dict['cardID'][cardID]
                #level=level[:-2] #把正卡/副卡去掉
            
            return_point=0
            dollar_per_point=0
            if tmp_dict['pointRewMax']=='不限':
                tmp_max_return=-1
            else:
                tmp_max_return=tmp_dict['pointRewMax']
            #先判斷有無回饋倍數與生日當月紅利回饋倍數，再將兩者比較並存入recommend_list
            if(tmp_dict['pointRewDes'] is not None): #回饋倍數
                if(not can_use_in_here(place_name,tmp_dict['excludeLocation'])):
                    for reward in tmp_dict['pointRewDes']:
                        can_use_in_place=0 
                        #判斷是否可在此地使用
                        for place in reward['可用地點']:
                            if(place.lower() in place_name.lower() or place.lower() in place_type or place.lower()==place_name.lower()): 
                                can_use_in_place=1
                            elif '之外' in place and (place[0:place.find('之外')] not in place_name or place_name not in place[0:place.find('之外')]):
                                can_use_in_place=1
                            elif('不限' in place):
                                can_use_in_place=1
                        if reward['可用地點']=='不限':
                            can_use_in_place=1
                        #有無符合卡片等級
                        #有當期帳單限制
                        if(can_use_in_place==1 and reward['當期帳單限制'] is not None and total_consumption_last_month(cardID,similar_person_id)>=reward['當期帳單限制'] and (level in reward['可用卡別'] or '不限' in reward['可用卡別'])):
                            return_point=reward['回饋倍數']
                            dollar_per_point=reward['幾元一點']
                        #無當期帳單限制
                        elif(can_use_in_place==1 and reward['當期帳單限制'] is None and (level in reward['可用卡別'] or '不限' in reward['可用卡別'])):
                            return_point=reward['回饋倍數']
                            dollar_per_point=reward['幾元一點']
            if(tmp_dict['pointRewBirth'] is not None): #判斷有無生日當月紅利回饋倍數
                if(not can_use_in_here(place_name,tmp_dict['excludeLocation'])):
                    #判斷是否是生日當月
                    birth_point=0
                    year=datetime.today().year
                    month=datetime.today().month
                    monthRange = calendar.monthrange(datetime.today().year,datetime.today().month)
                    start=datetime(year, month, 1,0,0,0)
                    end=datetime(year, month, monthRange[1],0,0,0)
                    cus_info = mongo.db.customer.find_one({'id': auth_id, 'birthday':{'$gte':start,'$lte':end}}) #Bson
                    cus_info_tmp = dumps(cus_info) #Json
                    cus_info_dict = json.loads(cus_info_tmp) #dict
                    if(cus_info_dict is not None):
                        for name, value in tmp_dict['pointRewBirth'].items():
                            if '非會員' in name:
                                birth_point=value
                        if(birth_point>=return_point): #生日>回饋倍數
                            point_recommend_list.append({'cardID':cardID,'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'紅利幾元一點':dollar_per_point,'紅利倍數':birth_point,'紅利回饋上限':tmp_max_return})
                        else:
                            point_recommend_list.append({'cardID':cardID,'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'紅利幾元一點':dollar_per_point,'紅利倍數':return_point,'紅利回饋上限':tmp_max_return})
                    else: #不是生日當月
                        point_recommend_list.append({'cardID':cardID,'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'紅利幾元一點':dollar_per_point,'紅利倍數':return_point,'紅利回饋上限':tmp_max_return})
            else: #no birthday reward
                if return_point!=0 and dollar_per_point!=0:
                    point_recommend_list.append({'cardID':cardID,'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'紅利幾元一點':dollar_per_point,'紅利倍數':return_point,'紅利回饋上限':tmp_max_return})

    result=sorted(point_recommend_list,key = lambda i: ((-i['紅利倍數']),i['紅利幾元一點'],(-i['紅利回饋上限'])))
    tmp_per=result[0]['紅利倍數']
    tmp_wen=result[0]['紅利幾元一點']
    tmp_index=0
    for i in result:
        if result.index(i)==0 and i['紅利回饋上限']==-1:
            i.update({'紅利回饋上限':'不限'})
        elif result.index(i)!=0 and i['紅利回饋上限']==-1 and i['紅利倍數']==tmp_per and i['紅利幾元一點']==tmp_wen:
            i.update({'紅利回饋上限':'不限'})
            result.insert(tmp_index, result.pop(result.index(i)))
            tmp_index=result.index(i)+1
        elif result.index(i)!=0 and i['紅利倍數']==tmp_per and i['紅利幾元一點']==tmp_wen:
            tmp_per=tmp_per
            tmp_wen=tmp_wen
            tmp_index=tmp_index
        else:
            if i['紅利回饋上限']==-1:
                i.update({'紅利回饋上限':'不限'})
            tmp_per=i['紅利倍數']
            tmp_wen=i['紅利幾元一點']
            tmp_index=result.index(i)
    recommend_list={'lat':lat,'lng':lng,'placeName':place_name}
    if rd_or_ap==0:
        if(len(result)>=3):
            recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':['紅利'+str(result[0]['紅利倍數'])+'倍','紅利'+str(result[0]['紅利幾元一點'])+'元一點','回饋上限'+str(result[0]['紅利回饋上限'])],'fir_recommend_bank':result[0]['銀行']})
            recommend_list.update({'sec_recommend_cardID':result[1]['cardID'],'sec_recommend_card':result[1]['卡名'],'sec_recommend_discount':['紅利'+str(result[1]['紅利倍數'])+'倍','紅利'+str(result[1]['紅利幾元一點'])+'元一點','回饋上限'+str(result[1]['紅利回饋上限'])],'sec_recommend_bank':result[1]['銀行']})
            recommend_list.update({'thr_recommend_cardID':result[2]['cardID'],'thr_recommend_card':result[2]['卡名'],'thr_recommend_discount':['紅利'+str(result[2]['紅利倍數'])+'倍','紅利'+str(result[2]['紅利幾元一點'])+'元一點','回饋上限'+str(result[2]['紅利回饋上限'])],'thr_recommend_bank':result[2]['銀行']})
        elif(len(result)==2):
            recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':['紅利'+str(result[0]['紅利倍數'])+'倍','紅利'+str(result[0]['紅利幾元一點'])+'元一點','回饋上限'+str(result[0]['紅利回饋上限'])],'fir_recommend_bank':result[0]['銀行']})
            recommend_list.update({'sec_recommend_cardID':result[1]['cardID'],'sec_recommend_card':result[1]['卡名'],'sec_recommend_discount':['紅利'+str(result[1]['紅利倍數'])+'倍','紅利'+str(result[1]['紅利幾元一點'])+'元一點','回饋上限'+str(result[1]['紅利回饋上限'])],'sec_recommend_bank':result[1]['銀行']})
            recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
        elif(len(result)==1):
            recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':['紅利'+str(result[0]['紅利倍數'])+'倍','紅利'+str(result[0]['紅利幾元一點'])+'元一點','回饋上限'+str(result[0]['紅利回饋上限'])],'fir_recommend_bank':result[0]['銀行']})
            recommend_list.update({'sec_recommend_cardID':None,'sec_recommend_card':None,'sec_recommend_discount':None,'sec_recommend_bank':None})
            recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
        else:
            recommend_list.update({'fir_recommend_cardID':None,'fir_recommend_card':None,'fir_recommend_discount':None,'fir_recommend_bank':None})
            recommend_list.update({'sec_recommend_cardID':None,'sec_recommend_card':None,'sec_recommend_discount':None,'sec_recommend_bank':None})
            recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
    else:
        if len(result)==0:
            recommend_list.update({'point_recommend_cardID1':None,'point_recommend_card1':None,'point_recommend_discount1':None,'point_recommend_bank1':None})
        else:
            for i in range(len(result)):
                recommend_list.update({'point_recommend_cardID'+str(i+1):result[i]['cardID'],'point_recommend_card'+str(i+1):result[i]['卡名'],'point_recommend_discount'+str(i+1):['紅利'+str(result[i]['紅利倍數'])+'倍','紅利'+str(result[i]['紅利幾元一點'])+'元一點','回饋上限'+str(result[i]['紅利回饋上限'])],'point_recommend_bank'+str(i+1):result[i]['銀行']})
    return recommend_list

#幾折優先於幾元(除非能取得預計消費消費)
#recommend_discount回傳string(ex:'6折')
def movie_discount_for_apply_withLocation(lat,lng,place_name,auth_id,is_sim_auth,rd_or_ap):
    che_recommend_list=[]
    wen_recommend_list=[]
    card_dict=[] #用戶所沒有的卡種編號 [{'卡種編號'},{'卡種編號']]
    
    #取出該用戶基本資料
    info = mongo.db.customer.find_one({'id': auth_id}) #Bson
    info_json = dumps(info) #Json
    info_dict = json.loads(info_json)

    #取出該用戶擁有的所有卡種編號(list)
    own_cards = mongo.db.cusCreditCard.find_one({'id': auth_id}) #Bson
    own_cards_tmp = dumps(own_cards) #Json
    own_tmp_card_dict = json.loads(own_cards_tmp)
    #取出所有卡片
    #須考慮年收入是否高於年收入低標，職業是否符合或不限
    occu = re.compile(info_dict['occupation']+'|不限',re.I)
    cards = mongo.db.creditCard.find({'annIncomeLimit':{'$lte': info_dict['annualIncome']}, "occuLimit": {'$regex': occu}})
    cards_tmp = dumps(cards) #Json
    tmp_card_dict = json.loads(cards_tmp)
    #將此用戶沒有的卡存入card_dict
    if(own_tmp_card_dict['cardID'] is None): #該用戶一張卡都沒有
        card_dict=tmp_card_dict
    else:
        for elem in tmp_card_dict:
            if(elem['cardID'] not in own_tmp_card_dict['cardID'].keys()):
                card_dict.append(elem)
                
    week=['週一','週二','週三','週四','週五','週六','週日']
    weekday=week[datetime.today().weekday()] #取得今天星期幾
    
    for tmp_card in card_dict:
        cardID=tmp_card['cardID']
        card = mongo.db.reward.find_one({'cardID': cardID}) #Bson
        resp_tmp = dumps(card) #Json
        tmp_dict = json.loads(resp_tmp) #dict
        #因為reward裡面沒有銀行，所以要用卡種編號去creditCard裡面抓

        #判斷此卡是否有電影優惠
        if(tmp_dict['movieReward'] is not None):
            #判斷是否在此地可用
            for i in tmp_dict['movieRewLocation']:
                if(i in place_name or place_name in i or place_name==i):
                    can_use_in_here=1
            if(can_use_in_here):
                if(is_sim_auth==2):
                    similar_person_id=auth_id
                else:
                    #取出跟他同群且有此卡的人的id
                    feature_value=dict()
                    feature_value['age']=info_dict['age']
                    feature_value['sex']=info_dict['sex']
                    feature_value['annualIncome']=info_dict['annualIncome']
                    feature_value['expenseMonth']=info_dict['expenseMonth'] #要再寫一個計算的
                    similar_persons=context.find_similar_(auth_id,feature_value)
                    for person in similar_persons:
                        sim_per_card = mongo.db.cusCreditCard.find_one({'id': person['id']}) #Bson
                        sim_resp_tmp = dumps(sim_per_card) #Json
                        sim_tmp_dict = json.loads(sim_resp_tmp) #dict
                        if cardID in sim_tmp_dict['cardID'].keys():
                            similar_person_id=person['id']
                            break
                #有當期帳單限制
                if(tmp_dict['movieRewBillMin'] is not None and total_consumption_last_month(cardID,similar_person_id)>=tmp_dict['movieRewBillMin']): 
                    for discount in tmp_dict['movieRewTerms']:
                        che_discount=0
                        wen_discount=0
                        if(weekday==discount[:discount.find('/')] or '每日'==discount[:discount.find('/')]):
                            if(discount[-1]=='折'):
                                che_discount=int(discount[discount.find('/')+1:-1])
                            elif(discount[-1]=='元'):
                                wen_discount=int(discount[discount.find('/')+1:-1])
                            if(che_discount!=0):
                                che_recommend_list.append({'cardID':cardID,'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'電影回饋':che_discount})
                            else:
                                wen_recommend_list.append({'cardID':cardID,'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'電影回饋':wen_discount})
                #沒有當期帳單限制
                else: 
                    for discount in tmp_dict['movieRewTerms']:
                        che_discount=0
                        wen_discount=0
                        if(weekday==discount[:discount.find('/')] or '每日'==discount[:discount.find('/')]):
                            if(discount[-1]=='折'):
                                che_discount=int(discount[discount.find('/')+1:-1])
                            elif(discount[-1]=='元'):
                                wen_discount=int(discount[discount.find('/')+1:-1])
                            if(che_discount!=0):
                                che_recommend_list.append({'cardID':cardID,'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'電影回饋':che_discount,'type':'折'})
                            else:
                                wen_recommend_list.append({'cardID':cardID,'銀行':tmp_card['bankID'],'卡名':tmp_dict['cardName'],'電影回饋':wen_discount,'type':'元'})
    che_result=sorted(che_recommend_list,key = lambda i: i['電影回饋']) #由小到大 
    wen_result=sorted(wen_recommend_list,key = lambda i: i['電影回饋']) #由小到大
    result=che_result+wen_result
    recommend_list={'lat':lat,'lng':lng,'placeName':place_name}
    if rd_or_ap==0:
        if(len(result)>=3):
            recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':update_which_type(result[0]),'fir_recommend_bank':result[0]['銀行']})
            recommend_list.update({'sec_recommend_cardID':result[1]['cardID'],'sec_recommend_card':result[1]['卡名'],'sec_recommend_discount':update_which_type(result[1]),'sec_recommend_bank':result[1]['銀行']})
            recommend_list.update({'thr_recommend_cardID':result[2]['cardID'],'thr_recommend_card':result[2]['卡名'],'thr_recommend_discount':update_which_type(result[2]),'thr_recommend_bank':result[2]['銀行']})
        elif(len(result)==2):
            recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':update_which_type(result[0]),'fir_recommend_bank':result[0]['銀行']})
            recommend_list.update({'sec_recommend_cardID':result[1]['cardID'],'sec_recommend_card':result[1]['卡名'],'sec_recommend_discount':update_which_type(result[1]),'sec_recommend_bank':result[1]['銀行']})
            recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
        elif(len(result)==1):
            recommend_list.update({'fir_recommend_cardID':result[0]['cardID'],'fir_recommend_card':result[0]['卡名'],'fir_recommend_discount':update_which_type(result[0]),'fir_recommend_bank':result[0]['銀行']})
            recommend_list.update({'sec_recommend_cardID':None,'sec_recommend_card':None,'sec_recommend_discount':None,'sec_recommend_bank':None})
            recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
        else:
            recommend_list.update({'fir_recommend_cardID':None,'fir_recommend_card':None,'fir_recommend_discount':None,'fir_recommend_bank':None})
            recommend_list.update({'sec_recommend_cardID':None,'sec_recommend_card':None,'sec_recommend_discount':None,'sec_recommend_bank':None})
            recommend_list.update({'thr_recommend_cardID':None,'thr_recommend_card':None,'thr_recommend_discount':None,'thr_recommend_bank':None})
    else:
        if len(result)==0:
            recommend_list.update({'movie_recommend_cardID1':None,'movie_recommend_card1':None,'movie_recommend_discount1':None,'movie_recommend_bank1':None})
        else:
            for i in range(len(result)):
                recommend_list.update({'movie_recommend_cardID'+str(i+1):result[i]['cardID'],'movie_recommend_card'+str(i+1):result[i]['卡名'],'movie_recommend_discount'+str(i+1):update_which_type(result[i]),'movie_recommend_bank'+str(i+1):result[i]['銀行']})
    return recommend_list

#--------------------------------------------------------------------------補充功能------------------------------------------------------------------------------#

#判斷resp1回傳的推薦結果是否滿足三個了，若不足就會用resp2來補足
def return_enough(resp1,resp2):
    #resp2都沒有
    if resp2['fir_recommend_cardID'] is None:
        return resp1
    #resp1都沒有 resp2有一個
    elif resp1['fir_recommend_cardID'] is None and resp2['sec_recommend_cardID'] is None:
        resp1.update({'fir_recommend_cardID':resp2['fir_recommend_cardID'],'fir_recommend_card':resp2['fir_recommend_card'],'fir_recommend_discount':resp2['fir_recommend_discount'],'fir_recommend_bank':resp2['fir_recommend_bank']})
        return resp1
    #resp1都沒有 resp2有兩個
    elif resp1['fir_recommend_cardID'] is None and resp2['thr_recommend_cardID'] is None:
        resp1.update({'fir_recommend_cardID':resp2['fir_recommend_cardID'],'fir_recommend_card':resp2['fir_recommend_card'],'fir_recommend_discount':resp2['fir_recommend_discount'],'fir_recommend_bank':resp2['fir_recommend_bank']})
        resp1.update({'sec_recommend_cardID':resp2['sec_recommend_cardID'],'sec_recommend_card':resp2['sec_recommend_card'],'sec_recommend_discount':resp2['sec_recommend_discount'],'sec_recommend_bank':resp2['sec_recommend_bank']})
        return resp1
    #resp1都沒有 resp2有三個
    elif resp1['fir_recommend_cardID'] is None and resp2['thr_recommend_cardID'] is not None:
        resp1.update({'fir_recommend_cardID':resp2['fir_recommend_cardID'],'fir_recommend_card':resp2['fir_recommend_card'],'fir_recommend_discount':resp2['fir_recommend_discount'],'fir_recommend_bank':resp2['fir_recommend_bank']})
        resp1.update({'sec_recommend_cardID':resp2['sec_recommend_cardID'],'sec_recommend_card':resp2['sec_recommend_card'],'sec_recommend_discount':resp2['sec_recommend_discount'],'sec_recommend_bank':resp2['sec_recommend_bank']})
        resp1.update({'thr_recommend_cardID':resp2['thr_recommend_cardID'],'thr_recommend_card':resp2['thr_recommend_card'],'thr_recommend_discount':resp2['thr_recommend_discount'],'thr_recommend_bank':resp2['thr_recommend_bank']})
        return resp1
    #resp1有一個 resp2有一個
    elif resp1['sec_recommend_cardID'] is None and resp2['sec_recommend_cardID'] is None:
        resp1.update({'sec_recommend_cardID':resp2['fir_recommend_cardID'],'sec_recommend_card':resp2['fir_recommend_card'],'sec_recommend_discount':resp2['fir_recommend_discount'],'sec_recommend_bank':resp2['fir_recommend_bank']})
        return resp1
    #resp1有一個 resp2有兩或三個
    elif resp1['sec_recommend_cardID'] is None:
        resp1.update({'sec_recommend_cardID':resp2['fir_recommend_cardID'],'sec_recommend_card':resp2['fir_recommend_card'],'sec_recommend_discount':resp2['fir_recommend_discount'],'sec_recommend_bank':resp2['fir_recommend_bank']})
        resp1.update({'thr_recommend_cardID':resp2['sec_recommend_cardID'],'thr_recommend_card':resp2['sec_recommend_card'],'thr_recommend_discount':resp2['sec_recommend_discount'],'thr_recommend_bank':resp2['sec_recommend_bank']})
        return resp1
    #resp1有兩個 resp2有一二三個
    elif resp1['thr_recommend_cardID'] is None:
        resp1.update({'thr_recommend_cardID':resp2['fir_recommend_cardID'],'thr_recommend_card':resp2['fir_recommend_card'],'thr_recommend_discount':resp2['fir_recommend_discount'],'thr_recommend_bank':resp2['fir_recommend_bank']})
        return resp1
    #resp1有三個
    else:
        return resp1

#將回饋上限不限的轉為-1
def has_limit_or_not(limit_str):
    if(limit_str=="不限"):
        return -1
    else:
        return limit_str

#回傳不能用的地點名稱串列(list)
def cannot_use_in_here(place_list):
    prohibit_place=[]
    for i in place_list:
        if("之外" in i):
            prohibit_place.append(i[0:i.find('之外')])
    return prohibit_place
        
#判斷此地點可不可用
def can_use_in_here(place_name,place_list):
    for i in place_list:
        if(place_name in i):
            return 1
    return 0

#用來判斷加油優惠的'recommend_discount'的部分要回傳哪種優惠
def update_which(result):
    if('現折金額' in result.keys()):
        return result['加油方式']+'加油'+'現省'+str(result['現折金額'])+'元'
    elif('加油現金回饋%數' in result.keys()):
        return '現金回饋'+str(result['加油現金回饋%數'])+'%'
    elif('加油金回饋%數' in result.keys()):
        return '加油金回饋'+str(result['加油金回饋%數'])+'%'
    elif('加油金回饋' in result.keys()):
        return '加油金回饋'+str(result['加油金回饋'])+'元'
    elif('幾元一點' in result.keys()):
        return str(result['幾元一點'])+'元一點'

#用來判斷電影優惠的'recommend_discount'的部分要回傳哪種優惠
def update_which_type(result):
    if(result['type']=='折'):
        return '電影優惠'+str(result['電影回饋'])+'折'
    elif(result['type']=='元'):
        return '電影優惠現省'+str(result['電影回饋'])+'元'

#用來增減month(return date)
def add_months(sourcedate, months):
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, calendar.monthrange(year,month)[1])
    return datetime(year, month, day,sourcedate.time().hour,sourcedate.time().minute,sourcedate.time().second)

#計算該卡前一個月的消費金額
def total_consumption_last_month(cardID, auth_id):
    #消費時間YY/MM/DD (str)
    today = datetime.today()
    last_month = add_months(today,-1)
    records = mongo.db.bookkeepingRecord.aggregate([{'$match':{"cardID":cardID,"id":auth_id,"consumeTime":{'$gte':last_month,'$lte':today}}},{'$group':{'_id':"$id",'total':{'$sum':"$consumeAmount"}}}])
    resp_tmp = dumps(records) #Json
    tmp_dict = json.loads(resp_tmp) #dict
    if len(tmp_dict)==0:
        return 0
    return tmp_dict[0]['total']

#計算該卡前三個月的消費金額
def total_consumption_last_three_months(cardID, auth_id):
    #消費時間YY/MM/DD (str)
    today = datetime.today()
    last_month = add_months(today,-3)
    records = mongo.db.bookkeepingRecord.aggregate([{'$match':{"cardID":cardID,"id":auth_id,"consumeTime":{'$gte':last_month,'$lte':today}}},{'$group':{'_id':"$id",'total':{'$sum':"$consumeAmount"}}}])
    resp_tmp = dumps(records) #Json
    tmp_dict = json.loads(resp_tmp) #dict
    if len(tmp_dict)==0:
        return 0
    return tmp_dict[0]['total']

#計算該卡前十二個月的消費金額
def total_consumption_last_year(cardID, auth_id):
    #消費時間YY/MM/DD (str)
    today = datetime.today()
    last_month = add_months(today,-12)
    records = mongo.db.bookkeepingRecord.aggregate([{'$match':{"cardID":cardID,"id":auth_id,"consumeTime":{'$gte':last_month,'$lte':today}}},{'$group':{'_id':"$id",'total':{'$sum':"$consumeAmount"}}}])
    resp_tmp = dumps(records) #Json
    tmp_dict = json.loads(resp_tmp) #dict
    if len(tmp_dict)==0:
        return 0
    return tmp_dict[0]['total']

# 判斷用戶偏好現金回饋還是紅利回饋
def cash_or_point(auth_id):
    records = mongo.db.customer.find_one({'id': auth_id}) #Bson
    resp_tmp = dumps(records) #Json
    tmp_dict = json.loads(resp_tmp) #dict
    #現金回饋>紅利回饋
    #if(tmp_dict['cashReward']==1 and tmp_dict['pointRewPref']==0):
    if(tmp_dict['cashRewPref']==1 and tmp_dict['pointRewPref']==0):
        return 'cash'
    #紅利>現金
    #elif(tmp_dict['cashReward']==0 and tmp_dict['pointRewPref']==1):
    elif(tmp_dict['cashRewPref']==0 and tmp_dict['pointRewPref']==1):
        return 'point'
    #現金>紅利    
    else:
        return 'cash'

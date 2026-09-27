import json, os
from datetime import datetime

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path,'r',encoding='utf-8') as f: return json.load(f)
        except: return default
    return default

TRAINER_DB = load_json('trainer_db.json', {"沈集成":{"wins":28,"places":65,"runners":220,"last6_wins":5,"last6_places":8,"last6_runners":18,"past_wins":320,"past_places":580,"past_runners":1800}})
TRACK_DB = load_json('track_bias_db.json', {"沙田_1200_C+3":{"1":{"win_rate":0.12,"place_rate":0.35},"11":{"win_rate":0.04,"place_rate":0.15,"is_worst":True}}})
JOCKEY_DB = load_json('jockey_db.json', {"潘頓":{"place":0.38,"win":0.16,"overall_place":0.38,"overall_win":0.16,"style":"後上爆發型"},"沈集成+潘頓":{"place":0.42,"win":0.19,"combo_place":0.42,"combo_win":0.19}})
HORSE_DB = load_json('horse_db.json', {"浪漫勇士":{"dist_stats":{"1200":{"place_rate":0.55,"win_rate":0.25}},"affinity":{"潘頓":{"place":0.80,"win":0.5}}}})

def period_score(w,p,r):
    if r==0: return 50
    return w/r*100*0.7 + (p-w)/r*100*0.3 + p/r*10

def calc_d1(trainer, ctx):
    t=TRAINER_DB.get(trainer, {"wins":10,"places":30,"runners":100,"last6_wins":1,"last6_places":3,"last6_runners":10,"past_wins":60,"past_places":150,"past_runners":500})
    long_s=period_score(t['past_wins'],t['past_places'],t['past_runners'])
    season_s=period_score(t['wins'],t['places'],t['runners'])
    hot_s=min(period_score(t['last6_wins'],t['last6_places'],t['last6_runners'])*1.15,98)
    return int(max(35,min(99,long_s*0.4+season_s*0.4+hot_s*0.2))), f"獨贏{t['wins']/t['runners']*100:.1f}% 上名{t['places']/t['runners']*100:.0f}%"

def calc_d2(horse, ctx):
    key=f"{ctx['venue']}_{ctx['distance']}_{ctx['rail']}"
    stats=TRACK_DB.get(key,{}).get(str(horse['draw']),{"win_rate":0.07,"place_rate":0.22})
    base=stats['place_rate']*60+stats['win_rate']*120
    if stats.get('is_worst'): base=28
    bias=90 if ctx['rail'] in ['C','C+3'] and horse['draw']<=3 else 40 if horse['draw']>=10 else 75
    mod=1.0; tag=""
    if horse['draw']<=2 and horse['style']=='領放': mod=1.12; tag="✅內檔領放+12%"
    elif horse['draw']>=10 and horse['style']=='領放': mod=0.70; tag="🔴外檔領放死穴"
    elif horse['draw']<=2 and horse['style']=='後上': mod=0.85; tag="⚠️內檔後上易塞"
    final=(base*0.6+bias*0.25+70*0.15)*mod
    return int(max(20,min(99,final))), f"{horse['draw']}檔 上名{stats['place_rate']*100:.0f}% {tag}", stats.get('is_worst',False)

def calc_d3(jockey,trainer,horse,last_jockey):
    combo=JOCKEY_DB.get(f"{trainer}+{jockey}",{"combo_place":0.25,"combo_win":0.08,"place":0.25,"win":0.08})
    overall=JOCKEY_DB.get(jockey,{"overall_place":0.25,"overall_win":0.06,"style":"均衡"})
    cp=combo.get('combo_place',combo['place']); op=overall.get('overall_place',overall['place'])
    intent=(cp-op)*100; synergy=cp*60+combo.get('combo_win',0.08)*120+intent*0.8
    skill=95 if horse['style']=='後上' and overall.get('style')=='後上爆發型' else 92 if horse['style']=='領放' and overall.get('style')=='前速領放型' else 75
    switch=92 if last_jockey and JOCKEY_DB.get(jockey,{}).get('overall_win',0.06) > JOCKEY_DB.get(last_jockey,{}).get('overall_win',0.06)+0.05 else 70
    final=synergy*0.5+skill*0.3+switch*0.2
    tag="⭐️深度默契" if cp>=0.40 and intent>=10 else ""
    return int(max(35,min(99,final))), f"{tag} 組合{cp*100:.0f}%上名"

def calc_d4(horse,ctx):
    hdb=HORSE_DB.get(horse['name'],{})
    c_score=88 if horse.get('from_conghua') and horse.get('had_trial') else 70
    cur_w=horse.get('body_weight',1130); last_w=horse.get('last_body_weight',cur_w)
    w_score=85-15 if abs(cur_w-last_w)>=20 else 85
    dist_stats=hdb.get('dist_stats',{}).get(str(ctx['distance']),{"place_rate":0.25,"win_rate":0.07})
    dist_score=dist_stats['place_rate']*60+dist_stats['win_rate']*100
    aff=hdb.get('affinity',{}).get(horse['jockey'],{"place":0.25,"win":0.08})
    aff_score=aff['place']*60+aff['win']*100
    penalty=30 if horse.get('last_injury')=='骨折' else 0
    final=(c_score*0.25+w_score*0.25+dist_score*0.30+aff_score*0.20)-penalty
    return int(max(20,min(98,final))), f"體重{cur_w}磅 | {ctx['distance']}m上名{dist_stats['place_rate']*100:.0f}%", "⚠️腳患" if penalty else ""

def calc_d5(odds,fund):
    def drop(a,b): return (a-b)/a*100 if a else 0
    def s(d): return 95 if d>=50 else 85 if d>=30 else 78 if d>=15 else 68
    pools=['win','place','quinella','qp','forecast','trifecta']
    t1s=[];t2s=[];t3s=[]; drops={}
    for pool in pools:
        arr=odds.get(pool,[0,0,0])
        if len(arr)<3 or arr[0]==0: continue
        t1,t2,t3=arr
        drops[pool]={"t1_t2":drop(t1,t2),"t2_t3":drop(t2,t3),"t1_t3":drop(t1,t3),"t1":t1,"t2":t2,"t3":t3}
        t1s.append(70); t2s.append(s(drop(t1,t2))); t3s.append(s(drop(t2,t3)))
    raw = sum(t1s)/len(t1s)*0.2 + sum(t2s)/len(t2s)*0.3 + sum(t3s)/len(t3s)*0.5 if t1s else 70
    win_t3=odds.get('win',[0,0,6])[2]; win_t1=odds.get('win',[0,0,6])[0]; place_t3=odds.get('place',[0,0,3])[2]
    bonus=0; tags=[]
    if fund>=80 and win_t3>=10: bonus+=15; tags.append(f"💎高Value {fund}分但{win_t3}倍")
    elif fund<=50 and win_t3<=3: bonus-=20; tags.append(f"⚠️熱門陷阱")
    if win_t3>=12 and place_t3 and place_t3<=3.2: bonus+=12; tags.append(f"🛡️大戶保險盤 W{win_t3} vs P{place_t3}")
    final=max(15,min(99,raw+bonus))
    win_d=drops.get('win',{"t1_t2":0,"t2_t3":0,"t1_t3":drop(win_t1,win_t3),"t1":win_t1,"t2":odds.get('win',[0,0,0])[1],"t3":win_t3})
    display={"t1":{"value":win_d['t1'],"diff":0,"label":"T1 隔夜 20%"},"t2":{"value":win_d['t2'],"diff":win_d['t1_t2'],"label":"T2 中段 30%"},"t3":{"value":win_d['t3'],"diff":win_d['t2_t3'],"label":"T3 臨場 50%"},"t3_vs_t1":{"value":win_d['t3'],"diff":win_d['t1_t3'],"is_smart":win_d['t1_t3']>=35,"label":"T3 vs T1 終極"},"all_drops":drops,"cross_pool_count":sum(1 for v in drops.values() if v['t1_t3']>30)}
    return int(final), display, f"T1 {win_d['t1']}→T2 {win_d['t2']}→T3 {win_d['t3']} | T3vsT1 -{win_d['t1_t3']:.1f}%", tags

def build_race():
    ctx={"venue":"沙田","distance":1200,"rail":"C+3","going":"好地"}
    horses_input=[
        {"no":5,"name":"浪漫勇士","draw":1,"style":"領放","jockey":"潘頓","trainer":"沈集成","body_weight":1135,"last_body_weight":1138,"best_distance":1200,"carried_weight":135,"from_conghua":True,"conghua_days":10,"had_trial":True,"last_injury":None,"past_wins_with_jockey":{"潘頓":2},"odds":{"win":[15.0,9.5,6.5],"place":[4.2,3.1,2.2],"quinella":[30,20,14],"qp":[25,18,12],"forecast":[40,28,18],"trifecta":[120,90,60]},"last_jockey":"田泰安"},
        {"no":3,"name":"金鎗六十","draw":11,"style":"後上","jockey":"何澤堯","trainer":"呂健威","body_weight":1150,"last_body_weight":1120,"best_distance":1200,"carried_weight":126,"odds":{"win":[3.5,3.2,2.8],"place":[1.8,1.7,1.5],"quinella":[15,13,11],"qp":[12,10,8],"forecast":[20,18,15],"trifecta":[80,70,60]},"last_jockey":"何澤堯"},
        {"no":8,"name":"爆冷王","draw":5,"style":"後上","jockey":"田泰安","trainer":"桂福特","body_weight":1125,"last_body_weight":1128,"best_distance":1200,"carried_weight":115,"apprentice_allowance":7,"odds":{"win":[28.0,22.0,14.0],"place":[5.0,4.0,2.8],"quinella":[60,45,28],"qp":[40,30,18],"forecast":[80,60,35],"trifecta":[200,150,90]},"last_jockey":"潘明輝"},
        {"no":2,"name":"超強駒","draw":2,"style":"領放","jockey":"布文","trainer":"蔡約翰","body_weight":1100,"last_body_weight":1125,"best_distance":1400,"carried_weight":133,"last_injury":"骨折","days_since_injury":90,"odds":{"win":[4.5,5.0,6.0],"place":[2.2,2.4,2.6],"quinella":[18,20,22],"qp":[15,16,18],"forecast":[25,28,30],"trifecta":[100,110,120]},"last_jockey":"潘頓"},
    ]
    results=[]
    for h in horses_input:
        d1,d1d=calc_d1(h['trainer'],ctx)
        d2,d2d,dead=calc_d2(h,ctx)
        d3,d3d=calc_d3(h['jockey'],h['trainer'],h,h.get('last_jockey'))
        d4,d4d,inj=calc_d4(h,ctx)
        fund=(d1+d2+d3+d4)/4
        d5,d5_disp,d5_desc,tags=calc_d5(h['odds'],fund)
        total=fund*0.6+d5*0.4
        grade="S" if total>=90 else "A+" if total>=82 else "A" if total>=72 else "B" if total>=60 else "C"
        results.append({"no":h['no'],"name":h['name'],"draw":h['draw'],"style":h['style'],"jockey":h['jockey'],"trainer":h['trainer'],"d1":d1,"d2":d2,"d3":d3,"d4":d4,"d5":d5,"fundamental":int(fund),"total":int(total),"grade":grade,"d1_desc":d1d,"d2_desc":d2d,"d3_desc":d3d,"d4_desc":d4d,"d5_desc":d5_desc,"d5_tags":tags,"d5_display":d5_disp,"odds":h['odds'],"is_dead_draw":dead,"injury_alert":inj})
    solid=sorted([r for r in results if r['d4']>60 and not r['is_dead_draw'] and not r['injury_alert']], key=lambda x:x['fundamental'], reverse=True)[:4]
    heavy=sorted(results, key=lambda x:(x['d5_display']['cross_pool_count'],x['d5']), reverse=True)[:4]
    outsiders=[r for r in results if 12<=r['odds']['win'][2]<=50 and r['fundamental']>=60 and r['d5_display']['t3_vs_t1']['diff']>=20][:2]
    output={"race":f"{ctx['venue']} {ctx['distance']}m {ctx['rail']}","ctx":ctx,"timestamp":datetime.now().isoformat(),"horses":sorted(results,key=lambda x:x['total'],reverse=True),"recommendations":{"solid":{"title":"🟢 最合理結果","horses":[r['no'] for r in solid],"detail":[f"{r['no']}號 {r['name']} 基本面{r['fundamental']}分" for r in solid]},"heavy":{"title":"🔴 重票之選","horses":[r['no'] for r in heavy],"detail":[f"{r['no']}號 {r['name']} T3vsT1 -{r['d5_display']['t3_vs_t1']['diff']:.1f}% {r['d5_display']['cross_pool_count']}個彩池" for r in heavy]},"outsiders":{"title":"⚡️ 爆冷之選","horses":[r['no'] for r in outsiders],"detail":[f"{r['no']}號 {r['name']} {r['odds']['win'][2]}倍 T3急瀉{r['d5_display']['t3']['diff']:.1f}%" for r in outsiders]}}}
    with open('data.json','w',encoding='utf-8') as f: json.dump(output,f,ensure_ascii=False,indent=2)
    print("✅ data.json 已生成")
if __name__=="__main__": build_race()
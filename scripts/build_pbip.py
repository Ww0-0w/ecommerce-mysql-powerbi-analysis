"""Build a native PBIP prototype from the published MySQL aggregate CSVs."""
import csv
import json
import re
import uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'dashboard/data'
OUT=ROOT/'dashboard/powerbi_project'
NAME='EcommerceMySQL'
SM=OUT/f'{NAME}.SemanticModel'
REP=OUT/f'{NAME}.Report'
TABLES=['overview','monthly','categories','rfm','repeat','experiment','quality']
DECIMAL={'gmv','aov','units_per_order','daily_gmv','orders_per_buyer','monthly_gmv_mom_pct','daily_gmv_mom_pct','gmv_share_pct','buyer_share_pct','avg_spend','avg_orders','repeat_rate_pct','relative_lift_pct','baseline_pct','target_pct','absolute_lift_pp'}
INTEGER={'valid_orders','buyers','source_orders','excluded_orders','calendar_days','orders','eligible_buyers','repeat_buyers','sample_per_arm','sample_total','window_days'}

def write(path, content):
    path.parent.mkdir(parents=True,exist_ok=True)
    if isinstance(content,(dict,list)):
        content=json.dumps(content,ensure_ascii=False,indent=2)
    path.write_text(content+'\n',encoding='utf-8')

def q_m(v):
    if v is None or v=='':return 'null'
    return '"'+v.replace('"','""')+'"'

def m_value(v,kind):
    if v is None or v=='':return 'null'
    if kind=='string':return q_m(v)
    if not re.fullmatch(r'[+-]?\d+(?:\.\d+)?',v):raise ValueError(v)
    return v

def field(col):
    return {'Column':{'Expression':{'SourceRef':{'Entity':col[0]}},'Property':col[1]}}

def agg(table,col):
    return {'Aggregation':{'Expression':field((table,col)),'Function':0}}

def projection(table,col,aggregate=False):
    f=agg(table,col) if aggregate else field((table,col))
    ref=f'Sum({table}.{col})' if aggregate else f'{table}.{col}'
    return {'field':f,'queryRef':ref,'nativeQueryRef':col,'displayName':col}

def title(text):
    return {'title':[{'properties':{'show':{'expr':{'Literal':{'Value':'true'}}},'text':{'expr':{'Literal':{'Value':"'"+text.replace("'","''")+"'"}}}}}]}

def visual(page_id,kind,x,y,w,h,table,category=None,value=None,label=None,order=0):
    ident=uuid.uuid4().hex[:20]
    qs={}
    if kind=='cardVisual':
        qs['Data']={'projections':[projection(table,value,True)]}
        qs['Data']['projections'][0]['displayName']=label or value
    else:
        qs['Category']={'projections':[projection(table,category)]}
        qs['Y']={'projections':[projection(table,value,True)]}
    v={'$schema':'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.11.0/schema.json',
       'name':ident,'position':{'x':x,'y':y,'z':order,'height':h,'width':w,'tabOrder':order},
       'visual':{'visualType':kind,'query':{'queryState':qs},'visualContainerObjects':title(label or value)}}
    if category:
        sort_field=agg(table,value) if table=='categories' else field((table,category))
        direction='Descending' if table=='categories' else 'Ascending'
        v['visual']['query']['sortDefinition']={'sort':[{'field':sort_field,'direction':direction}],'isDefaultSort':True}
    write(REP/'definition/pages'/page_id/'visuals'/ident/'visual.json',v)

def page(name,visuals):
    ident=uuid.uuid4().hex[:20]
    write(REP/'definition/pages'/ident/'page.json',{'$schema':'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json','name':ident,'displayName':name,'displayOption':'FitToPage','height':720,'width':1280})
    for i,args in enumerate(visuals):visual(ident,*args,order=i*1000)
    return ident

if OUT.exists():
    raise SystemExit(f'Output already exists: {OUT}. Move it aside before rebuilding.')
for name in TABLES:
    with (DATA/f'{name}.csv').open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    cols=list(rows[0])
    kinds={c:('decimal' if c in DECIMAL else 'int64' if c in INTEGER else 'string') for c in cols}
    # Quality checks intentionally retain observed/expected as numeric values.
    if name=='quality':
        for c in ('observed','expected'):
            if c in kinds:kinds[c]='int64'
    lines=[f'table {name}']
    for c in cols:
        kind=kinds[c]
        lines.extend([f'\tcolumn {c}',f'\t\tdataType: {kind}',f'\t\tsourceColumn: {c}'])
        if kind=='string':lines.append('\t\tsummarizeBy: none')
    typefields=', '.join(f'{c} = nullable '+('text' if kinds[c]=='string' else 'number') for c in cols)
    mrows=',\n'.join('{' + ', '.join(m_value(row[c],kinds[c]) for c in cols) + '}' for row in rows)
    lines += [f'\tpartition {name} = m','\t\tmode: import','\t\tsource =',
              '\t\t\tlet',f'\t\t\t\tSource = #table(type table [{typefields}], {{']
    lines += ['\t\t\t\t\t'+line for line in mrows.splitlines()]
    lines += ['\t\t\t\t})','\t\t\tin','\t\t\t\tSource']
    write(SM/'definition/tables'/f'{name}.tmdl','\n'.join(lines))

write(SM/'definition/database.tmdl',f'database {uuid.uuid4()}\n\tcompatibilityLevel: 1702\n\tcompatibilityMode: powerBI\n\tlanguage: 1033')
write(SM/'definition/model.tmdl','model Model\n\tculture: zh-CN\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tsourceQueryCulture: zh-CN\n\n'+'\n'.join('ref table '+t for t in TABLES))
write(SM/'definition.pbism',{'$schema':'https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json','version':'4.2','settings':{'qnaEnabled':False}})
write(REP/'definition.pbir',{'$schema':'https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json','version':'4.0','datasetReference':{'byPath':{'path':f'../{NAME}.SemanticModel'}}})
write(OUT/f'{NAME}.pbip',{'$schema':'https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json','version':'1.0','artifacts':[{'report':{'path':f'{NAME}.Report'}}],'settings':{'enableAutoRecovery':True}})
write(REP/'definition/version.json',{'$schema':'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json','version':'2.0.0'})
write(REP/'definition/report.json',{'$schema':'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json','themeCollection':{},'settings':{'useStylableVisualContainerHeader':True}})

ids=[]
ids.append(page('经营概览',[
    ('cardVisual',30,35,280,135,'overview',None,'gmv','实付 GMV'),
    ('cardVisual',340,35,280,135,'overview',None,'valid_orders','成交订单'),
    ('cardVisual',650,35,280,135,'overview',None,'buyers','购买用户'),
    ('cardVisual',960,35,280,135,'overview',None,'aov','客单价'),
    ('lineChart',30,210,590,440,'monthly','month_key','gmv','整月 GMV'),
    ('lineChart',650,210,590,440,'monthly','month_key','daily_gmv','日均 GMV')]))
ids.append(page('月度与品类诊断',[
    ('columnChart',30,70,590,550,'monthly','month_key','orders','月成交订单'),
    ('barChart',650,70,590,550,'categories','category','gmv','品类 GMV')]))
ids.append(page('RFM 与复购',[
    ('barChart',30,70,590,550,'rfm','segment','buyers','RFM 分群人数'),
    ('lineChart',650,70,590,550,'repeat','window_days','repeat_rate_pct','首单后复购率 %')]))
ids.append(page('模拟实验与质量核对',[
    ('columnChart',30,70,590,550,'experiment','relative_lift_pct','sample_per_arm','模拟 A/B 每组样本量'),
    ('barChart',650,70,590,550,'quality','check_name','observed','质量检查观测值')]))
write(REP/'definition/pages/pages.json',{'$schema':'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json','pageOrder':ids,'activePageName':ids[0]})
print(OUT)

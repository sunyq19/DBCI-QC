"""Group validator occurrences by rule while retaining all source findings."""
import hashlib
from collections import defaultdict

TITLES = {
    'IEEG_ELECTRODES_REQUIRED': '缺少电极坐标配套表',
    'TSV_VALUE_INCORRECT_TYPE': '表格字段类型不符合规则',
    'NOT_INCLUDED': '目录中含规范未识别的文件',
    'SIDECAR_KEY_RECOMMENDED': '建议补充记录说明字段',
    'TSV_ADDITIONAL_COLUMNS_UNDEFINED': '建议补充自定义列的说明',
    'JSON_KEY_RECOMMENDED': '建议补充 JSON 字段',
}


def grouped_checks(validation):
    if validation.get('status') != 'completed': return None
    raw=validation.get('issues', {})
    items=raw.get('issues', []) if isinstance(raw,dict) else raw
    groups=defaultdict(list)
    for item in items:groups[(item.get('severity','unknown'),item.get('code','unknown'))].append(item)
    rows=[]
    for (severity,code),items in sorted(groups.items()):
        target=severity+':'+code
        files=sorted({str(i.get('location','')).lstrip('/') for i in items if i.get('location')})
        name=TITLES.get(code,code);level='错误' if severity=='error' else '建议' if severity=='warning' else '信息'
        rows.append({'id':hashlib.sha256(('bids:'+target).encode()).hexdigest()[:16],
            'module':'D01','code':'bids_validator','label':'BIDS 结构规范','label_en':'BIDS structure validation',
            'status':'review','target':target,'message':f'{level}：{name}；{len(items)} 处，涉及 {len(files)} 个路径。',
            'records':[],'files':files,'observed':{'severity':severity,'validator_code':code,'occurrences':len(items),
                'details':items}})
    if not rows:
        rows=[{'id':'bids-no-findings','module':'D01','code':'bids_validator','label':'BIDS 结构规范',
               'label_en':'BIDS structure validation','status':'pass','target':'BIDS','message':'BIDS Validator 未报告发现。',
               'records':[],'files':[],'observed':None}]
    return rows

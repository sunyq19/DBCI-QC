import concurrent.futures,hashlib,json,time,urllib.request
from datetime import datetime, timezone
from pathlib import Path
from dataset_paths import paths
args=paths()
root=args.data_root
previous_path=args.evidence_dir/'download_manifest.json'
previous={x['path']:x for x in json.loads(previous_path.read_text())} if previous_path.exists() else {}
items=[]
for slug,directory in [('eegmmidb','eegmmidb-1.0.0-expansion'),('sleep-edfx','sleep-edfx-1.0.0-sc4001'),('chbmit','chbmit-1.0.0-chb01')]:
    dest=root/directory
    for url,name,role in [(f'https://physionet.org/content/{slug}/1.0.0/','_provenance/official_dataset_page.html','official_description'),(f'https://physionet.org/content/{slug}/view-license/1.0.0/','_provenance/license-ODC-By-1.0.html','official_license'),(f'https://physionet.org/files/{slug}/1.0.0/SHA256SUMS.txt','_provenance/official_SHA256SUMS.txt','official_checksum')]:items.append((url,dest/name,role))
for slug,directory,rel in [('eegmmidb','eegmmidb-1.0.0-expansion','S001/S001R03.edf'),('sleep-edfx','sleep-edfx-1.0.0-sc4001','sleep-cassette/SC4001E0-PSG.edf'),('sleep-edfx','sleep-edfx-1.0.0-sc4001','sleep-cassette/SC4001EC-Hypnogram.edf'),('chbmit','chbmit-1.0.0-chb01','chb01/chb01_03.edf'),('chbmit','chbmit-1.0.0-chb01','chb01/chb01-summary.txt'),('chbmit','chbmit-1.0.0-chb01','chb01/chb01_03.edf.seizures')]:items.append((f'https://physionet.org/files/{slug}/1.0.0/{rel}',root/directory/Path(rel).name,'original_data' if rel.endswith('.edf') else 'original_annotation'))
items.extend([('https://archive.physionet.org/physiobank/database/eegmmidb/',root/'eegmmidb-1.0.0-expansion/_provenance/official_archive_protocol.html','official_description'),('https://physionet.org/files/chbmit/1.0.0/SUBJECT-INFO',root/'chbmit-1.0.0-chb01/_provenance/SUBJECT-INFO','official_description'),('https://physionet.org/files/sleep-edfx/1.0.0/SC-subjects.xls',root/'sleep-edfx-1.0.0-sc4001/_provenance/SC-subjects.xls','official_description')])
if not args.existing_r02:
    items.append(('https://physionet.org/files/eegmmidb/1.0.0/S001/S001R02.edf',root/'eegmmidb-1.0.0-expansion/S001R02.edf','original_data'))
def get(item):
    url,p,role=item;p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists():return {**previous.get(str(p),{}),'url':url,'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'role':role,'last_operation':'reuse_existing'}
    temp=p.with_name(p.name+'.partial')
    for attempt in range(3):
      try:
        sha=hashlib.sha256();n=0
        req=urllib.request.Request(url,headers={'User-Agent':'EEG-QC-public-research/1.0'})
        with urllib.request.urlopen(req,timeout=45) as response,temp.open('wb') as output:
          final_url=response.url;headers=dict(response.headers)
          while True:
            block=response.read(1024*1024)
            if not block:break
            output.write(block);sha.update(block);n+=len(block)
        temp.rename(p)
        record={'url':url,'final_url':final_url,'path':str(p),'bytes':n,'sha256':sha.hexdigest(),'role':role,'operation':'downloaded','retrieved_date':datetime.now(timezone.utc).date().isoformat(),'last_modified':headers.get('Last-Modified'),'content_type':headers.get('Content-Type')}
        print(json.dumps({'downloaded':p.name,'bytes':n}),flush=True);return record
      except Exception as e:
        if attempt==2:return {'url':url,'path':str(p),'role':role,'error':str(e)}
        time.sleep(1)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:results=list(ex.map(get,items))
previous_path.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'items':len(results),'errors':[x for x in results if 'error'in x]},ensure_ascii=False),flush=True)

if any("error" in row for row in results):raise SystemExit(1)

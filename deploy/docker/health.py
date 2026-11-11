from urllib.request import build_opener, ProxyHandler
import json
with build_opener(ProxyHandler({})).open('http://127.0.0.1:18769/api/v1/health', timeout=4) as response:
    assert json.load(response)['service'] == 'ephys-qc-modular-workbench'

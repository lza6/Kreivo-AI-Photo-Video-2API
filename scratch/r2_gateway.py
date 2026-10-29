import sys,os,json,base64
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
B="http://127.0.0.1:8977"
b64=base64.b64encode(open("test_1024.jpg","rb").read()).decode()
for svc in ["enhance","beauty","art-premium","segment","clothes","image-ai"]:
    r=requests.post(B+"/kreivo/service/"+svc,json={"image_base64":b64,"prompt":"van gogh starry night"},timeout=400)
    j=r.json()
    print(f"{svc:14} {r.status_code} url={str(j.get('url'))[:70]} seg={len(j.get('segments') or [])} {j.get('elapsed_s')}s err={j.get('error')}")

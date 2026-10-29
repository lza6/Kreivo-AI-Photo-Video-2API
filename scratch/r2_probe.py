import json,time
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sigkit import *
sync_time(BASE_IMG)
img=open("test_1024.jpg","rb").read()
def call(base,svc,body_maker,label):
    try:
        pd=presign(base,svc); put(pd["url"],img)
        body=body_maker(pd["path"])
        r=requests.post(base+svc,json=body,headers=headers(extra={"Content-Type":"application/json"}),timeout=180,verify=False)
        print(f"\n=== {label} [{r.status_code}] {svc}\nBODY {json.dumps(body)[:200]}\nRESP {r.text[:500]}")
        return r.json()
    except Exception as e:
        print(f"\n=== {label} EXC {e}")
        return None

call(BASE_IMG,"/api/v5/image-ai",lambda p:{"file":p,"files":[p],"mode":"IMAGE_EDITING","positivePrompt":"van gogh style"},"image-ai (flux-klein)")
call(BASE_IMG,"/api/v5/image-ai",lambda p:{"files":[p],"mode":"IMAGE_EDITING","positivePrompt":"van gogh style"},"image-ai alt files[]")
call("https://art-premium-core.aperogroup.ai","/api/v5/art-premium",lambda p:{"file":p},"art-premium")
call("https://enhance-core.aperogroup.ai","/api/v5/image-enhance",lambda p:{"file":p},"enhance")
call("https://segment-core.aperogroup.ai","/api/v5/segment",lambda p:{"file":p},"segment")
call("https://beauty-core.aperogroup.ai","/api/v5/beauty",lambda p:{"file":p},"beauty v5")
call("https://cloth-change-core.aperogroup.ai","/api/v5/clothes-changing",lambda p:{"file":p,"prompt":"a red evening dress"},"clothes")
call("https://objectremoval-core.aperogroup.ai","/api/v5/remove-object",lambda p:{"file":p,"mask":p},"remove-object (mask=同图试探)")

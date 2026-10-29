import json,time
from sigkit import *
sync_time(BASE_IMG)
bodies=[
 ("minimal",{"positivePrompt":"a serene fantasy castle at sunset, oil painting"}),
 ("full",{"positivePrompt":"a serene fantasy castle at sunset, oil painting","negativePrompt":"blurry","width":1024,"height":1024,"seed":42,"styleId":"1"}),
]
for tag,b in bodies:
    r=requests.post(BASE_IMG+"/api/v5/premium/text-2-image",json=b,headers=headers(extra={"Content-Type":"application/json"}),timeout=180,verify=False)
    print(f"[{tag}] {r.status_code} {r.text[:300]}")

import json,time
from sigkit import *
img=open("test.jpg","rb").read()
sync_time(BASE_VIDEO)
P="Animate this photo: gentle camera push-in, cinematic lighting"
def try_body(tag,v):
    pd=presign(BASE_VIDEO,"/api/v5/image-2-video"); put(pd["url"],img)
    v["files"]=[pd["path"]]
    r=requests.post(BASE_VIDEO+"/api/v5/image-2-video",json=v,headers=headers(extra={"Content-Type":"application/json"}),timeout=90,verify=False)
    print(f"{tag}: {r.status_code} {r.text[:260]}")
    return r
base={"mode":"i2v","positivePrompt":P,"positivePrompt2":"","positivePrompt3":"","negativePrompt":"","keepFace":False,"width":1024,"height":1024}
r=try_body("A width=1024 h=1024 no model",dict(base))
if r.status_code!=200:
    try_body("B +model='' lora=''",{**base,"model":"","loraName":""})
    try_body("C model=qwen keepFace false width720 h1280",{**base,"width":720,"height":1280,"model":"qwen"})
else:
    print(json.dumps(r.json(),ensure_ascii=False)[:400])

import json,time
from sigkit import *
sync_time(BASE_VIDEO)
P="Animate this photo: gentle camera push-in, cinematic lighting"
def run(tag,img_path,body_extra):
    img=open(img_path,"rb").read()
    pd=presign(BASE_VIDEO,"/api/v5/image-2-video"); put(pd["url"],img)
    body={"files":[pd["path"]],"mode":"i2v","positivePrompt":P}
    body.update(body_extra)
    r=requests.post(BASE_VIDEO+"/api/v5/image-2-video",json=body,headers=headers(extra={"Content-Type":"application/json"}),timeout=90,verify=False)
    print(f"{tag}: {r.status_code} {r.text[:280]}")
    return r
full={"positivePrompt2":"","positivePrompt3":"","negativePrompt":"","keepFace":False,"width":1024,"height":1024,"model":"","loraName":""}
r=run("full 1024x1024","test_1024.jpg",full)
if r.status_code!=200:
    run("full 720x720","test_768.jpg",{**full,"width":720,"height":720})
    run("full 512x512","test_768.jpg",{**full,"width":512,"height":512})

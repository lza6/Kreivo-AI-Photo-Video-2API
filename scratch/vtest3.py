import json,time
from sigkit import *
sync_time(BASE_VIDEO)
P="Animate this photo: gentle camera push-in, cinematic lighting"
def run(tag,img_path,extra=None):
    img=open(img_path,"rb").read()
    pd=presign(BASE_VIDEO,"/api/v5/image-2-video"); put(pd["url"],img)
    body={"files":[pd["path"]],"mode":"i2v","positivePrompt":P,"keepFace":False}
    if extra: body.update(extra)
    r=requests.post(BASE_VIDEO+"/api/v5/image-2-video",json=body,headers=headers(extra={"Content-Type":"application/json"}),timeout=90,verify=False)
    print(f"{tag}: {r.status_code} {r.text[:280]}")
    return r
r=run("1024 no wh","test_1024.jpg")
if r.status_code!=200:
    run("768 no wh","test_768.jpg")
    run("1024 w/h=1024","test_1024.jpg",{"width":1024,"height":1024})

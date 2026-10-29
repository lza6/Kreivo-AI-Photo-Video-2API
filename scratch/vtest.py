import json,time,itertools
from sigkit import *
img=open("test.jpg","rb").read()
sync_time(BASE_VIDEO)
P="Animate this photo: gentle camera push-in, cinematic lighting"
variants=[
 {"files":None,"mode":"i2v","positivePrompt":P,"keepFace":False},
 {"files":None,"mode":"i2v","positivePrompt":P,"positivePrompt2":"","positivePrompt3":"","negativePrompt":"","keepFace":False,"width":720,"height":1280,"model":"","loraName":""},
 {"files":None,"mode":"IMAGE_2_VIDEO","positivePrompt":P,"keepFace":False},
 {"files":None,"mode":"image_to_video","positivePrompt":P,"keepFace":False},
 {"files":None,"mode":"i2v","positivePrompt":P,"positivePrompt2":"","negativePrompt":"","keepFace":True,"notificationProvider":"","notificationId":""},
]
for i,v in enumerate(variants):
    pd=presign(BASE_VIDEO,"/api/v5/image-2-video"); put(pd["url"],img)
    v["files"]=[pd["path"]]
    r=requests.post(BASE_VIDEO+"/api/v5/image-2-video",json=v,headers=headers(extra={"Content-Type":"application/json"}),timeout=90,verify=False)
    print(f"#{i} {r.status_code} {r.text[:300]}")

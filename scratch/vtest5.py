import json,time,itertools
from sigkit import *
sync_time(BASE_VIDEO)
P="Animate this photo: gentle camera push-in, cinematic lighting"
img=open("test_1024.jpg","rb").read()
base={"mode":"i2v","positivePrompt":P,"positivePrompt2":"","positivePrompt3":"","negativePrompt":"","keepFace":False,"width":1024,"height":1024}
cands=[
 ("np=fcm",{**base,"notificationProvider":"fcm","notificationId":"dummy-fcm-token"}),
 ("model=veo3",{**base,"model":"veo3"}),
 ("model=kling",{**base,"model":"kling"}),
 ("model=wan",{**base,"model":"wan"}),
 ("np=fcm+model=veo3",{**base,"notificationProvider":"fcm","notificationId":"x","model":"veo3"}),
]
for tag,body in cands:
    pd=presign(BASE_VIDEO,"/api/v5/image-2-video"); put(pd["url"],img)
    b={"files":[pd["path"]],**body}
    r=requests.post(BASE_VIDEO+"/api/v5/image-2-video",json=b,headers=headers(extra={"Content-Type":"application/json"}),timeout=90,verify=False)
    print(f"{tag}: {r.status_code} {r.text[:250]}")

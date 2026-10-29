import json,time,sys
from sigkit import *
sync_time(BASE_VIDEO)
P=sys.argv[2] if len(sys.argv)>2 else "Animate this photo: gentle camera push-in, cinematic lighting, natural motion"
MODEL=sys.argv[1] if len(sys.argv)>1 else "inhouse"
img=open("test_1024.jpg","rb").read()
t0=time.time()
pd=presign(BASE_VIDEO,"/api/v5/image-2-video"); put(pd["url"],img)
body={"files":[pd["path"]],"mode":"i2v","positivePrompt":P,"positivePrompt2":"","positivePrompt3":"",
      "negativePrompt":"","keepFace":False,"width":1024,"height":1024,"model":MODEL,
      "notificationProvider":"fcm","notificationId":"fcm-"+uuid.uuid4().hex}
r=requests.post(BASE_VIDEO+"/api/v5/image-2-video",json=body,headers=headers(extra={"Content-Type":"application/json"}),timeout=90,verify=False)
d=r.json(); print(f"[submit {time.time()-t0:.1f}s] {r.status_code} {json.dumps(d)[:300]}")
vid=(d.get("data") or {}).get("videoId")
if not vid: sys.exit(1)
for i in range(90):
    time.sleep(5)
    rr=requests.get(BASE_VIDEO+f"/api/v5/image-2-video/video/{vid}",headers=headers(),timeout=60,verify=False)
    dd=rr.json(); data=dd.get("data") or {}
    st=data.get("videoStatus") or data.get("status")
    print(f"  poll#{i} {time.time()-t0:.0f}s {st} {json.dumps(data)[:220]}")
    if st in ("COMPLETED","FAILED"):
        print("FINAL:",json.dumps(dd)[:800]); break

import json,time,sys
from sigkit import *
sync_time(BASE_VIDEO)
MODEL=sys.argv[1] if len(sys.argv)>1 else "inhouse"
img=open("test_1024.jpg","rb").read()
t0=time.time()
pd=presign(BASE_VIDEO,"/api/v5/image-2-video"); put(pd["url"],img)
body={"files":[pd["path"]],"mode":"i2v","positivePrompt":"gentle camera push-in, cinematic","keepFace":False,
      "width":1024,"height":1024,"model":MODEL,"notificationProvider":"fcm","notificationId":"fcm-"+uuid.uuid4().hex}
r=requests.post(BASE_VIDEO+"/api/v5/image-2-video",json=body,headers=headers(extra={"Content-Type":"application/json"}),timeout=90,verify=False)
d=r.json(); print("SUBMIT",r.status_code,json.dumps(d,ensure_ascii=False))
vid=d["data"]["videoId"]
open("vid.txt","w").write(vid)
for i in range(120):
    time.sleep(5)
    rr=requests.get(BASE_VIDEO+f"/api/v5/image-2-video/video/{vid}",headers=headers(),timeout=60,verify=False)
    dd=rr.json()
    print(f"POLL#{i} {time.time()-t0:.0f}s",json.dumps(dd,ensure_ascii=False)[:700],flush=True)
    st=(dd.get("data") or {}).get("videoStatus")
    if st in ("COMPLETED","FAILED"): break

import json,time,sys,base64
from sigkit import *

def do_image(prompt="Turn this into a van gogh starry night oil painting"):
    t0=time.time()
    pd=presign(BASE_IMG,"/api/v5.1/qwen-editing")
    put(pd["url"], open("test.jpg","rb").read())
    body={"files":[pd["path"]],"mode":"IMAGE_EDITING","positivePrompt":prompt,"positivePrompt2":""}
    r=requests.post(BASE_IMG+"/api/v5.1/qwen-editing",json=body,
                    headers=headers(extra={"Content-Type":"application/json"}),timeout=180,verify=False)
    d=r.json()
    print(f"[image] {time.time()-t0:.1f}s status={d.get('statusCode')} msg={d.get('message')}")
    if d.get("statusCode")==200:
        url=d["data"]["url"]; print("[image] url:",url[:120])
        try:
            img=requests.get(url,timeout=120,verify=False).content
            open("out_image.jpg","wb").write(img); print("[image] saved",len(img),"bytes")
            return url
        except Exception as e: print("[image] dl err",e)
    else:
        print("[image] body:",json.dumps(d)[:400])

def do_video(prompt, mode="i2v", model=None):
    t0=time.time()
    pd=presign(BASE_VIDEO,"/api/v5/image-2-video")
    put(pd["url"], open("test.jpg","rb").read())
    body={"files":[pd["path"]],"mode":mode,"positivePrompt":prompt,"positivePrompt2":""}
    if model: body["model"]=model
    r=requests.post(BASE_VIDEO+"/api/v5/image-2-video",json=body,
                    headers=headers(extra={"Content-Type":"application/json"}),timeout=120,verify=False)
    d=r.json()
    print(f"[video] submit {time.time()-t0:.1f}s status={d.get('statusCode')} msg={d.get('message')} data={json.dumps(d.get('data'))[:200]}")
    if d.get("statusCode")!=200: return
    vid=(d.get("data") or {}).get("videoId")
    if not vid: return
    for i in range(60):
        time.sleep(4)
        rr=requests.get(BASE_VIDEO+f"/api/v5/image-2-video/video/{vid}",headers=headers(),timeout=60,verify=False)
        dd=rr.json(); data=dd.get("data") or {}
        st=data.get("videoStatus") or data.get("status")
        print(f"  poll#{i} {time.time()-t0:.0f}s status={st} keys={list(data)[:8]}")
        if st in ("COMPLETED","FAILED"):
            print("  final:",json.dumps(dd)[:600]); return dd

if __name__=="__main__":
    print("skew ms:",sync_time())
    what=sys.argv[1] if len(sys.argv)>1 else "both"
    if what in ("both","image"): do_image()
    if what in ("both","video"): do_video(sys.argv[2] if len(sys.argv)>2 else "Animate this photo: gentle camera push-in, subject smiles naturally, cinematic lighting", sys.argv[3] if len(sys.argv)>3 else "i2v")

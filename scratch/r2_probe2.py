import sys,os,json,time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sigkit import *
sync_time(BASE_IMG)
img=open("test_1024.jpg","rb").read()
def one(base,svc,body,files=1,label=""):
    pd=presign(base,svc); put(pd["url"],img)
    paths=[pd["path"]]
    for _ in range(files-1):
        pd2=presign(base,svc); put(pd2["url"],img); paths.append(pd2["path"])
    b=body(paths)
    r=requests.post(base+svc,json=b,headers=headers(extra={"Content-Type":"application/json"}),timeout=180,verify=False)
    print(f"\n=== {label} [{r.status_code}]\nBODY {json.dumps(b)[:180]}\nRESP {r.text[:380]}")
for mode in ["FAST_EDITING","TRANSFORM","ART"]:
    one(BASE_IMG,"/api/v5/image-ai",lambda p,m=mode:{"file":p[0],"mode":m,"positivePrompt":"van gogh style"},1,f"image-ai mode={mode}")
one("https://fitting-core.aperogroup.ai","/api/v5/fitting",lambda p:{"inputImage":p[0],"clothImage":p[1] if len(p)>1 else p[0],"clothType":"upper"},2,"fitting")

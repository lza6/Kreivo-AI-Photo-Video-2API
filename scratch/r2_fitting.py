import sys,os,json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sigkit import *
sync_time(BASE_IMG)
img=open("test_1024.jpg","rb").read()
for ct in ["upper_body"]:
    pd=presign("https://fitting-core.aperogroup.ai","/api/v5/fitting"); put(pd["url"],img)
    pd2=presign("https://fitting-core.aperogroup.ai","/api/v5/fitting"); put(pd2["url"],img)
    b={"inputImage":pd["path"],"clothImage":pd2["path"],"clothType":ct}
    r=requests.post("https://fitting-core.aperogroup.ai/api/v5/fitting",json=b,
        headers=headers(extra={"Content-Type":"application/json"}),timeout=240,verify=False)
    print(f"fitting clothType={ct} [{r.status_code}] {r.text[:400]}")

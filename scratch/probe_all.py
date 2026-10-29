import json
from sigkit import *
sync_time(BASE_IMG)
SVC=[
 ("img","/api/v5.1/qwen-editing"),("img","/api/v5/image-ai"),("img","/api/v5/art-premium"),
 ("img","/api/v5/image-enhance"),("img","/api/v5/remove-background"),("img","/api/v5/remove-object"),
 ("img","/api/v5/segment"),("img","/api/v5/image-restore"),("img","/api/v5/clothes-changing"),
 ("img","/api/v5/fitting"),("img","/api/v5/beauty"),("img","/api/v5/image-outpainting"),
 ("img","/api/v4/beauty"),("video","/api/v5/image-2-video"),
]
BASES={"img":BASE_IMG,"video":BASE_VIDEO,"premium":"https://art-premium-core.aperogroup.ai",
       "enhance":"https://enhance-core.aperogroup.ai","removebg":"https://core-outpaint.aperogroup.ai",
       "removeobj":"https://objectremoval-core.aperogroup.ai","segment":"https://segment-core.aperogroup.ai",
       "restore":"https://image-restore-core.aperogroup.ai","clothes":"https://cloth-change-core.aperogroup.ai",
       "fitting":"https://fitting-core.aperogroup.ai","beauty":"https://beauty-core.aperogroup.ai"}
EPBASE={"/api/v5.1/qwen-editing":"img","/api/v5/image-ai":"img","/api/v5/art-premium":"premium",
 "/api/v5/image-enhance":"enhance","/api/v5/remove-background":"removebg","/api/v5/remove-object":"removeobj",
 "/api/v5/segment":"segment","/api/v5/image-restore":"restore","/api/v5/clothes-changing":"clothes",
 "/api/v5/fitting":"fitting","/api/v5/beauty":"beauty","/api/v5/image-outpainting":"removebg",
 "/api/v4/beauty":"beauty","/api/v5/image-2-video":"video"}
for _,ep in SVC:
    b=BASES[EPBASE[ep]]
    try:
        r=requests.get(b+ep+"/presigned-link",headers=headers(),timeout=40,verify=False)
        t=r.text[:110].replace("\n"," ")
        print(f"{r.status_code} {b+ep+"/presigned-link":70} {t}")
    except Exception as e:
        print(f"EXC {ep} {e}")

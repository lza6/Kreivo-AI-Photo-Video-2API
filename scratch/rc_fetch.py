import json,urllib.request,uuid,ssl,sys
CTX=ssl.create_default_context()
WEBKEY="AIzaSyBEGwusHz7rcFj66cYlG6lpYogFLhIk-DU"
PROJ="aip894-ai-photo-video"
APPID="1:546583882737:android:b5f660b2d255e8f4be3250"
url=f"https://firebaseremoteconfig.googleapis.com/v1/projects/{PROJ}/namespaces/firebase:fetch?key={WEBKEY}"
body=json.dumps({"app_instance_id":str(uuid.uuid4()).replace('-',''),"app_id":APPID,"platform_version":"30"}).encode()
req=urllib.request.Request(url,data=body,headers={"Content-Type":"application/json","X-Android-Package":"com.ai.art.aiimagegenerator.aivideogenerator.aiphoto.aiart","X-Android-Cert":"61ed377e85d386a8dfee6b864bd85b0bfaa5af81"})
try:
    r=urllib.request.urlopen(req,context=CTX,timeout=40)
    d=json.loads(r.read())
    open("rc_raw.json","w",encoding="utf8").write(json.dumps(d,ensure_ascii=False,indent=1))
    ents=d.get("entries",{})
    print("entries:",len(ents))
    for k,v in ents.items():
        print(f"{k} = {v[:200]}")
except Exception as e:
    print("ERR",type(e).__name__,e)
    try: print(e.read().decode()[:800])
    except Exception: pass

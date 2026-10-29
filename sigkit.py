import base64,time,uuid,json
import requests, urllib3
urllib3.disable_warnings()
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_der_public_key

PUB="MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA5z8DrSdxAFy5ju27JzxUDGD5OdPRnKVrXPypiBVT7NK4ltgbcud3+Li3H1DiAFNvaSDPumZMEbAkfGWZ6s3KtiI7TRmZwQ2yyH6mug6GhrCLD6CZJUQ2CPmhO3JYTYOgN53E6hwm/Teb9I156S04qHjLLLBxk9Mklu5X06kdhMBYwHFAZ3oByeoWUryrQC0Mv9C5ZahKzoQNuJNL2sv+ws2e5Zaj8Rid4AjhvqB6dYhWP4QM+0IiNjs/j08aRgcyOrenbQEIieU+XF6mQWF2Jfg317e0KjWnpru+uPVVgrEn9rNvQeXu2u4SZhT6rnLQzBLbJrngNcNw3gXfxxsoowIDAQAB"
_PUB=load_der_public_key(base64.b64decode(PUB))
APPNAME="AI_AIP894_Visionlab_Android"
BUNDLE="com.ai.art.aiimagegenerator.aivideogenerator.aiphoto.aiart"
import os as _os
def _k():
    v=_os.environ.get("APERO_API_KEY","").strip()
    if v: return v
    f=_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),"apikey.local")
    if _os.path.exists(f):
        return open(f,encoding="utf-8").read().strip().splitlines()[0].strip()
    return "sk-REPLACE_ME_WITH_AN_ACTIVE_APERO_KEY"
KEY=_k()
BASE_IMG="https://api-img-gen-wrapper.aperogroup.ai"
BASE_VIDEO="https://video-gen-core.aperogroup.ai"
_skew=0

def sync_time(base=BASE_IMG):
    global _skew
    try:
        r=requests.get(base+"/timestamp",headers=headers(),timeout=20,verify=False)
        srv=r.json()["data"]["timestamp"]
        _skew=srv-int(time.time()*1000)
    except Exception:
        _skew=0
    return _skew

def headers(key=KEY,extra=None):
    ts=str(int(time.time()*1000)+_skew)
    nonce=str(uuid.uuid4().int%1000000).zfill(6)
    sig=base64.b64encode(_PUB.encrypt(f"{ts}@@@{key}@@@{nonce}".encode(),padding.PKCS1v15())).decode()
    h={"Accept":"application/json","device":"android","x-api-signature":sig,"x-api-timestamp":ts,
       "x-api-keyid":key,"x-api-token":"not_get_api_token","x-api-bundleId":BUNDLE,
       "App-name":APPNAME,"App-version":"1.1.0","Country-code":"US"}
    if extra: h.update(extra)
    return h

def presign(base,path,key=KEY):
    r=requests.get(base+path+"/presigned-link",headers=headers(key),timeout=40,verify=False)
    d=r.json()
    if d.get("statusCode")!=200: raise RuntimeError(f"presign {d.get('statusCode')} {d.get('message')}")
    return d["data"]

def put(url,data,ctype="image/jpeg"):
    r=requests.put(url,data=data,headers={"Content-Type":ctype},timeout=180,verify=False)
    if r.status_code>=300: raise RuntimeError(f"PUT {r.status_code} {r.text[:200]}")

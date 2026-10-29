import base64,time,uuid,json,sys
import requests, urllib3
urllib3.disable_warnings()
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_der_public_key

PUB="MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA5z8DrSdxAFy5ju27JzxUDGD5OdPRnKVrXPypiBVT7NK4ltgbcud3+Li3H1DiAFNvaSDPumZMEbAkfGWZ6s3KtiI7TRmZwQ2yyH6mug6GhrCLD6CZJUQ2CPmhO3JYTYOgN53E6hwm/Teb9I156S04qHjLLLBxk9Mklu5X06kdhMBYwHFAZ3oByeoWUryrQC0Mv9C5ZahKzoQNuJNL2sv+ws2e5Zaj8Rid4AjhvqB6dYhWP4QM+0IiNjs/j08aRgcyOrenbQEIieU+XF6mQWF2Jfg317e0KjWnpru+uPVVgrEn9rNvQeXu2u4SZhT6rnLQzBLbJrngNcNw3gXfxxsoowIDAQAB"
_pub=load_der_public_key(base64.b64decode(PUB))
APPNAME="AI_AIP894_Visionlab_Android"
BUNDLE="com.ai.art.aiimagegenerator.aivideogenerator.aiphoto.aiart"
BASES={"img":"https://api-img-gen-wrapper.aperogroup.ai","video":"https://video-gen-core.aperogroup.ai","premium":"https://art-premium-core.aperogroup.ai","style":"https://api-style-manager.aperogroup.ai"}

def hdr(key, ts=None):
    ts=str(int(time.time()*1000)) if ts is None else str(ts)
    nonce=str(uuid.uuid4().int%1000000).zfill(6)
    sig=base64.b64encode(_pub.encrypt(f"{ts}@@@{key}@@@{nonce}".encode(),padding.PKCS1v15())).decode()
    return {"Accept":"application/json","Content-Type":"application/json","device":"android",
            "x-api-signature":sig,"x-api-timestamp":ts,"x-api-keyid":key,"x-api-token":"not_get_api_token",
            "x-api-bundleId":BUNDLE,"App-name":APPNAME,"App-version":"1.1.0","Country-code":"US"}

KEYS={
 "kreivo_rc":"sk-REDACTED_USE_apikey.local",
 "alura":"sk-REDACTED_USE_apikey.local",
}
def get(url,key=None,**kw):
    try:
        r=requests.get(url,headers=hdr(key),timeout=40,verify=False,**kw)
        return r.status_code, r.text[:400]
    except Exception as e:
        return "EXC", f"{type(e).__name__}: {e}"

print("=== /timestamp on each base ===")
for name,b in BASES.items():
    sc,t=get(b+"/timestamp",KEYS["kreivo_rc"])
    print(f"{name:8} {b}/timestamp -> {sc} {t[:120]}")

print("\n=== presigned-link probes per key ===")
for kn,k in KEYS.items():
    for ep in ["/api/v5.1/qwen-editing/presigned-link","/api/v5/image-ai/presigned-link","/api/v5/image-2-video/presigned-link"]:
        base = BASES["video"] if "2-video" in ep else BASES["img"]
        sc,t=get(base+ep,k)
        print(f"[{kn:10}] {ep:45} -> {sc} {t[:200]}")

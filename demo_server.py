#!/usr/bin/env python3
"""
Kreivo (AI Photo & Video Generator v1.1.0) 2API demo gateway
============================================================
逆向自: kreivo---ai-photo-&-video-generator-1.1.0-modyolo.apk
包名:   com.ai.art.aiimagegenerator.aivideogenerator.aiphoto.aiart
后端:   aperogroup 全家桶 (api-img-gen-wrapper / video-gen-core / ...)

签名协议 (com/apero/signature/SignatureParserImpl#encryptSignature):
    x-api-signature = Base64( RSA/None/PKCS1Padding( pub,
                        f"{ms_ts}@@@{api_key}@@@{nonce(0..999999)}" ) )
    公钥 = assets/prod.pem (内嵌 2048-bit RSA，Apero 集团全站共用)
头部 6 件套: x-api-signature / x-api-timestamp / x-api-keyid / x-api-token /
             x-api-bundleId / App-name (+ App-version / Country-code / device)

能力 (已实测):
    POST /v1/images/edits        OpenAI 兼容 multipart 图生图  -> qwen-editing   ~18s
    POST /v1/images/generations  OpenAI 兼容文生图             -> premium/text-2-image ~9s
    POST /kreivo/i2v             图生视频 (提交+轮询)          -> image-2-video   ~45s(seedance-lite)
    POST /kreivo/edit            原生 JSON 图生图
    GET  /kreivo/styles          RC 风格库 (i2i / i2v / t2i)
    GET  /health                探活

浏览器 demo 页: http://127.0.0.1:8920/
"""
import base64
import json
import os
import re
import ssl
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import requests
import urllib3
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_der_public_key

urllib3.disable_warnings()

# ---------------------------------------------------------------- 协议常量
PUB = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA5z8DrSdxAFy5ju27JzxUDGD5OdPRnKVrXPypiBVT7NK4"
    "ltgbcud3+Li3H1DiAFNvaSDPumZMEbAkfGWZ6s3KtiI7TRmZwQ2yyH6mug6GhrCLD6CZJUQ2CPmhO3JYTYOgN53E"
    "6hwm/Teb9I156S04qHjLLLBxk9Mklu5X06kdhMBYwHFAZ3oByeoWUryrQC0Mv9C5ZahKzoQNuJNL2sv+ws2e5Zaj8"
    "Rid4AjhvqB6dYhWP4QM+0IiNjs/j08aRgcyOrenbQEIieU+XF6mQWF2Jfg317e0KjWnpru+uPVVgrEn9rNvQeXu2u"
    "4SZhT6rnLQzBLbJrngNcNw3gXfxxsoowIDAQAB"
)
PUB_KEY = load_der_public_key(base64.b64decode(PUB))
APP_NAME = "AI_AIP894_Visionlab_Android"
BUNDLE_ID = "com.ai.art.aiimagegenerator.aivideogenerator.aiphoto.aiart"
APP_VERSION = "1.1.0"

# Kreivo 自己 RC 下发的 key 已被上游停用 (401 ERR15 Not active api key)。
# 可用 key 需自备：同集团（Alura/Umagic 系）任一活跃 sk- key 即可，服务器 RSA 公钥全站共用。
# 提供方式：环境变量 APERO_API_KEY，或仓库根目录新建 apikey.local（已 gitignore，首行为 key）。
def _load_api_key() -> str:
    k = os.environ.get("APERO_API_KEY", "").strip()
    if k:
        return k
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "apikey.local")
    if os.path.exists(local):
        with open(local, encoding="utf-8") as f:
            lines = f.read().strip().splitlines()
        return lines[0].strip() if lines else ""
    return ""


API_KEY = _load_api_key() or "sk-REPLACE_ME_WITH_AN_ACTIVE_APERO_KEY"

BASE_IMG = "https://api-img-gen-wrapper.aperogroup.ai"     # qwen-editing / image-ai / premium text-2-image
BASE_VIDEO = "https://video-gen-core.aperogroup.ai"        # image-2-video
BASE_PREMIUM = "https://art-premium-core.aperogroup.ai"    # art-premium
BASE_ENHANCE = "https://enhance-core.aperogroup.ai"        # image-enhance
BASE_BEAUTY = "https://beauty-core.aperogroup.ai"          # beauty v5 / v4
BASE_SEGMENT = "https://segment-core.aperogroup.ai"        # segment
BASE_REMOVE_OBJ = "https://objectremoval-core.aperogroup.ai"
BASE_CLOTHES = "https://cloth-change-core.aperogroup.ai"
BASE_FITTING = "https://fitting-core.aperogroup.ai"

RC_PROJECT = "aip894-ai-photo-video"
RC_WEB_KEY = "AIzaSyBEGwusHz7rcFj66cYlG6lpYogFLhIk-DU"
RC_APP_ID = "1:546583882737:android:b5f660b2d255e8f4be3250"

PORT = int(os.environ.get("PORT", "8920"))
VIDEO_MODELS = ("inhouse", "seedance-lite", "seedance-pro")

_lock = threading.Lock()
_skew_ms = 0


# ---------------------------------------------------------------- 签名
def _headers(api_key: str = API_KEY, extra: dict | None = None) -> dict:
    with _lock:
        ts = str(int(time.time() * 1000) + _skew_ms)
    nonce = str(uuid.uuid4().int % 1_000_000).zfill(6)
    sig = base64.b64encode(
        PUB_KEY.encrypt(f"{ts}@@@{api_key}@@@{nonce}".encode(), padding.PKCS1v15())
    ).decode()
    h = {
        "Accept": "application/json",
        "device": "android",
        "x-api-signature": sig,
        "x-api-timestamp": ts,
        "x-api-keyid": api_key,
        "x-api-token": "not_get_api_token",   # Integrity token 空 => 客户端回落此常量
        "x-api-bundleId": BUNDLE_ID,
        "App-name": APP_NAME,
        "App-version": APP_VERSION,
        "Country-code": "US",
        "User-Agent": "okhttp/4.12.0",
    }
    if extra:
        h.update(extra)
    return h


def sync_time(base: str = BASE_IMG) -> int:
    """服务端 /timestamp 校准时钟偏移（x-api-timestamp 与服务器偏差过大会被拒）"""
    global _skew_ms
    try:
        r = requests.get(base + "/timestamp", headers=_headers(), timeout=20, verify=False)
        srv = r.json()["data"]["timestamp"]
        with _lock:
            _skew_ms = srv - int(time.time() * 1000)
    except Exception:
        with _lock:
            _skew_ms = 0
    return _skew_ms


# ---------------------------------------------------------------- 上游调用
def _presign(base: str, service_path: str) -> dict:
    r = requests.get(base + service_path + "/presigned-link", headers=_headers(), timeout=60, verify=False)
    d = r.json()
    if d.get("statusCode") != 200:
        raise RuntimeError(f"presign {d.get('statusCode')}: {d.get('message')}")
    return d["data"]


def _put_s3(url: str, blob: bytes, content_type: str = "image/jpeg") -> None:
    r = requests.put(url, data=blob, headers={"Content-Type": content_type}, timeout=180, verify=False)
    if r.status_code >= 300:
        raise RuntimeError(f"s3 put {r.status_code}: {r.text[:200]}")


def _clamp_dim(v) -> int:
    """上游要求 width/height ∈ [512,1024] 的整数"""
    try:
        n = int(v)
    except (TypeError, ValueError):
        return 1024
    return max(512, min(1024, n))


def edit_image(blob: bytes, prompt: str, mode: str = "IMAGE_EDITING") -> dict:
    """图生图 / 多图合成 -> api-img-gen-wrapper /api/v5.1/qwen-editing （同步返回 url）"""
    t0 = time.time()
    pd = _presign(BASE_IMG, "/api/v5.1/qwen-editing")
    _put_s3(pd["url"], blob)
    body = {"files": [pd["path"]], "mode": mode, "positivePrompt": prompt, "positivePrompt2": ""}
    r = requests.post(
        BASE_IMG + "/api/v5.1/qwen-editing",
        data=json.dumps(body),
        headers=_headers(extra={"Content-Type": "application/json"}),
        timeout=240,
        verify=False,
    )
    d = r.json()
    if d.get("statusCode") != 200:
        raise RuntimeError(f"upstream {d.get('statusCode')}: {d.get('message')}")
    return {"url": d["data"]["url"], "elapsed_s": round(time.time() - t0, 1)}


def text_to_image(prompt: str, width=1024, height=1024, negative: str = "") -> dict:
    """文生图 -> /api/v5/premium/text-2-image （flux-klein，同步）"""
    t0 = time.time()
    body = {"positivePrompt": prompt}
    if negative:
        body["negativePrompt"] = negative
    if width:
        body["width"] = _clamp_dim(width)
    if height:
        body["height"] = _clamp_dim(height)
    r = requests.post(
        BASE_IMG + "/api/v5/premium/text-2-image",
        data=json.dumps(body),
        headers=_headers(extra={"Content-Type": "application/json"}),
        timeout=240,
        verify=False,
    )
    d = r.json()
    if d.get("statusCode") != 200:
        raise RuntimeError(f"upstream {d.get('statusCode')}: {d.get('message')}")
    return {"url": d["data"]["url"], "elapsed_s": round(time.time() - t0, 1)}


def image_to_video(blob: bytes, prompt: str, model: str = "seedance-lite",
                   width=1024, height=1024, poll_timeout=600) -> dict:
    """图生视频 -> video-gen-core /api/v5/image-2-video （异步 + 轮询）

    必要字段（缺任一 => 400 client.bad-request）:
        files[path] / mode="i2v" / positivePrompt / keepFace
        width,height ∈ [512,1024] / model ∈ {inhouse,seedance-lite,seedance-pro}
        notificationProvider + notificationId  (FCM，可填任意非空串)
    """
    t0 = time.time()
    if model not in VIDEO_MODELS:
        raise ValueError(f"model 必须是 {VIDEO_MODELS} 之一")
    pd = _presign(BASE_VIDEO, "/api/v5/image-2-video")
    _put_s3(pd["url"], blob)
    body = {
        "files": [pd["path"]],
        "mode": "i2v",
        "positivePrompt": prompt,
        "positivePrompt2": "",
        "positivePrompt3": "",
        "negativePrompt": "",
        "keepFace": False,
        "width": _clamp_dim(width),
        "height": _clamp_dim(height),
        "model": model,
        "notificationProvider": "fcm",
        "notificationId": "fcm-" + uuid.uuid4().hex,
    }
    r = requests.post(
        BASE_VIDEO + "/api/v5/image-2-video",
        data=json.dumps(body),
        headers=_headers(extra={"Content-Type": "application/json"}),
        timeout=120,
        verify=False,
    )
    d = r.json()
    if d.get("statusCode") != 200:
        raise RuntimeError(f"submit {d.get('statusCode')}: {d.get('message')}")
    video_id = d["data"]["videoId"]
    deadline = time.time() + poll_timeout
    status = "queueing"
    while time.time() < deadline:
        time.sleep(4)
        rr = requests.get(
            BASE_VIDEO + f"/api/v5/image-2-video/video/{video_id}",
            headers=_headers(), timeout=60, verify=False,
        )
        info = (rr.json().get("data") or {}).get("result") or {}
        status = info.get("videoStatus") or "unknown"
        if status == "completed":
            return {
                "video_id": video_id,
                "url": info.get("resultFile"),
                "status": status,
                "model": model,
                "elapsed_s": round(time.time() - t0, 1),
            }
        if status in ("failed", "error"):
            raise RuntimeError(f"video {video_id} failed: {json.dumps(info)[:300]}")
    raise TimeoutError(f"video {video_id} timeout after {poll_timeout}s (last status={status})")


# ---------------------------------------------------------------- 通用单/双图服务
# name -> (base, path, 需要几张图)
SERVICE_ENDPOINTS = {
    "art-premium":   (BASE_PREMIUM, "/api/v5/art-premium", 1),
    "enhance":       (BASE_ENHANCE, "/api/v5/image-enhance", 1),
    "beauty":        (BASE_BEAUTY, "/api/v5/beauty", 1),
    "segment":       (BASE_SEGMENT, "/api/v5/segment", 1),
    "clothes":       (BASE_CLOTHES, "/api/v5/clothes-changing", 1),
    "image-ai":      (BASE_IMG, "/api/v5/image-ai", 1),
    "remove-object": (BASE_REMOVE_OBJ, "/api/v5/remove-object", 2),
    "fitting":       (BASE_FITTING, "/api/v5/fitting", 2),
}
# image-ai 的 mode 白名单（服务端只认这些，且大小写敏感，ART 必须小写才过）
IMAGE_AI_MODES = ("FAST_EDITING", "TRANSFORM", "SUPER_ART", "FASHION",
                  "MULTI_IMAGES", "POSE_TRANSFER", "VIDEO_POSE_TRANSFER")
CLOTH_TYPES = ("upper_body", "lower_body", "full_body")


def run_service(name: str, blobs: list[bytes], p: dict) -> dict:
    """通用单/双图服务调用。p 为业务参数字典。"""
    if name not in SERVICE_ENDPOINTS:
        raise ValueError(f"unknown service {name}")
    base, path, need = SERVICE_ENDPOINTS[name]
    if len(blobs) < need:
        raise ValueError(f"{name} 需要 {need} 张图")
    t0 = time.time()
    paths = []
    for blob in blobs[:need]:
        pd = _presign(base, path)
        _put_s3(pd["url"], blob)
        paths.append(pd["path"])
    prompt = p.get("prompt") or ""

    if name == "image-ai":
        mode = str(p.get("mode") or "FAST_EDITING").upper()
        if mode not in IMAGE_AI_MODES:
            raise ValueError(f"mode 必须是 {IMAGE_AI_MODES} 之一（ART 请用小写 art）")
        body = {"file": paths[0], "mode": mode, "positivePrompt": prompt or "enhance details"}
    elif name == "clothes":
        body = {"file": paths[0], "prompt": prompt or "a stylish outfit"}
    elif name == "remove-object":
        body = {"file": paths[0], "mask": paths[1]}
    elif name == "fitting":
        ct = str(p.get("cloth_type") or "upper_body")
        if ct not in CLOTH_TYPES:
            raise ValueError(f"cloth_type 必须是 {CLOTH_TYPES} 之一")
        body = {"inputImage": paths[0], "clothImage": paths[1], "clothType": ct}
    elif name == "beauty":
        body = {"file": paths[0]}
        for k in ("smooth", "eyes", "smile", "teethWhitening", "vLine", "lipsColor", "type", "denoise"):
            if p.get(k) is not None:
                body[k] = p[k]
    else:                                    # art-premium / enhance / segment
        body = {"file": paths[0]}

    r = requests.post(
        base + path,
        data=json.dumps(body),
        headers=_headers(extra={"Content-Type": "application/json"}),
        timeout=300,
        verify=False,
    )
    d = r.json()
    if d.get("statusCode") != 200:
        raise RuntimeError(f"upstream {d.get('statusCode')}: {d.get('message')}")
    data = d["data"]
    out = {"success": True, "elapsed_s": round(time.time() - t0, 1), "uploaded": paths}
    if isinstance(data, dict):
        out["url"] = data.get("url")
        out["path"] = data.get("path")
    else:
        out["segments"] = data                # segment 返回 [{className,xLeft,...matrix}]
    return out


# ---------------------------------------------------------------- 风格库 (Firebase RemoteConfig)
_style_cache: dict[str, tuple[float, str]] = {}


def fetch_rc_entry(key: str) -> str:
    """直拉 Firebase RemoteConfig REST，无需 APK / 无需设备"""
    hit = _style_cache.get(key)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    url = (f"https://firebaseremoteconfig.googleapis.com/v1/projects/{RC_PROJECT}"
           f"/namespaces/firebase:fetch?key={RC_WEB_KEY}")
    payload = {
        "app_instance_id": uuid.uuid4().hex,
        "app_id": RC_APP_ID,
        "platform_version": "30",
    }
    r = requests.post(url, json=payload, timeout=40,
                      headers={"X-Android-Package": BUNDLE_ID,
                               "X-Android-Cert": "61ed377e85d386a8dfee6b864bd85b0bfaa5af81"})
    value = (r.json().get("entries") or {}).get(key, "")
    _style_cache[key] = (time.time(), value)
    return value


def styles(kind: str = "i2i") -> dict:
    key = {"i2i": "image_to_image_style", "i2v": "image_to_video_style",
           "t2i": "text_to_image_style"}.get(kind, "image_to_image_style")
    raw = fetch_rc_entry(key)
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}


# ---------------------------------------------------------------- multipart 极简解析
TEXT_FIELDS = ("prompt", "model", "mode", "size", "n", "response_format")
_DISP_NAME = re.compile(rb';\s*name="([^"]*)"')


def parse_multipart(raw: bytes) -> dict:
    """极简 multipart/form-data 解析。注意不能按 `name="` 切分，
    因为 `filename="..."` 也含这个子串（会串键）。"""
    out = {}
    for m in _DISP_NAME.finditer(raw):
        name = m.group(1).decode(errors="ignore")
        start = raw.find(b"\r\n\r\n", m.end())
        if start < 0:
            continue
        start += 4
        end = raw.find(b"\r\n--", start)
        body = raw[start:end] if end >= 0 else raw[start:]
        if name in TEXT_FIELDS:
            out[name] = body.decode(errors="ignore").strip()
        else:
            out[name] = body
    return out


DEMO_HTML = r"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>Kreivo 2API Demo</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--bg:#0b0d12;--card:#151922;--line:#242b38;--fg:#e8ecf3;--dim:#8b96a8;--acc:#5b8cff;}
*{box-sizing:border-box}
body{margin:0;font:14px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--fg)}
header{padding:20px 24px;border-bottom:1px solid var(--line);display:flex;gap:16px;align-items:baseline}
h1{font-size:17px;margin:0}
header small{color:var(--dim)}
main{max-width:1080px;margin:0 auto;padding:24px;display:grid;grid-template-columns:380px 1fr;gap:20px}
@media(max-width:860px){main{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
label{display:block;font-size:12px;color:var(--dim);margin:12px 0 6px}
input[type=file],textarea,select,input[type=number],input[type=text]{width:100%;background:#0e1219;color:var(--fg);
 border:1px solid var(--line);border-radius:8px;padding:9px 11px;font:inherit}
textarea{min-height:78px;resize:vertical}
.row{display:flex;gap:10px}.row>*{flex:1}
button{margin-top:16px;width:100%;padding:11px;border:0;border-radius:9px;background:var(--acc);color:#fff;
 font-weight:600;font-size:14px;cursor:pointer}
button:disabled{opacity:.5;cursor:progress}
button.alt{background:#2a3140}
#out{min-height:360px;display:flex;flex-direction:column;gap:12px}
#out img,#out video{max-width:100%;border-radius:10px;border:1px solid var(--line)}
pre{background:#0e1219;border:1px solid var(--line);border-radius:8px;padding:12px;overflow:auto;
 font-size:12px;color:#9fb3d1;margin:0;max-height:220px}
.tag{display:inline-block;font-size:11px;color:var(--dim);border:1px solid var(--line);
 padding:2px 8px;border-radius:99px;margin-right:6px}
.styles{display:grid;grid-template-columns:repeat(auto-fill,minmax(74px,1fr));gap:8px;margin-top:8px}
.styles img{width:100%;aspect-ratio:1;object-fit:cover;border-radius:8px;cursor:pointer;
 border:2px solid transparent}
.styles img:hover{border-color:var(--acc)}
</style></head><body>
<header><h1>Kreivo 2API Demo</h1>
<small>aperogroup / qwen-editing · flux-klein · seedance</small>
<span class="tag" id="health">health…</span></header>
<main>
<div class="card">
  <label>输入图片（图生图 / 图生视频必填）</label>
  <input type="file" id="file" accept="image/*">
  <label>Prompt</label>
  <textarea id="prompt">Turn this photo into a van gogh starry night oil painting</textarea>
  <div class="row">
    <div><label>视频模型</label>
      <select id="model"><option>seedance-lite</option><option>inhouse</option><option>seedance-pro</option></select></div>
    <div><label>尺寸</label><input type="number" id="size" value="1024" min="512" max="1024"></div>
  </div>
  <button id="btnEdit">图生图 (qwen-editing)</button>
  <button id="btnVideo" class="alt">图生视频 (image-2-video)</button>
  <button id="btnT2I" class="alt">文生图 (flux-klein)</button>
  <label>其他服务（单图）</label>
  <select id="svc">
    <option>enhance</option><option>beauty</option><option>art-premium</option>
    <option>segment</option><option>clothes</option><option>image-ai</option>
  </select>
  <button id="btnSvc" class="alt">跑该服务</button>
  <label>风格库（点击套用 prompt）</label>
  <div class="styles" id="styles"></div>
</div>
<div class="card"><div id="out"><pre>等待操作…</pre></div></div>
</main>
<script>
const $ = s => document.querySelector(s);
const out = $('#out');
let stylesCache = {i2i: [], i2v: []};
const API_KEY = localStorage.getItem('kreivo_key') || '';

async function health(){
  try{ const r = await fetch('/health'); const j = await r.json();
    $('#health').textContent = j.ok ? `ok · key ${j.key_hint}` : 'down'; }catch(e){ $('#health').textContent='down'; }
}
health();

async function loadStyles(){
  for (const kind of ['i2i','i2v']){
    try{
      const r = await fetch('/kreivo/styles?kind=' + kind); const j = await r.json();
      const items = [];
      for (const cat of (j.categories||[])) for (const s of (cat.styles||{})) {
        const src = s.image_url; const p = s.image_prompt || s.video_prompt;
        if (src && p) items.push({src, p, name: s.style_name, kind});
      }
      stylesCache[kind] = items;
    }catch(e){}
  }
  const box = $('#styles'); box.innerHTML='';
  [...stylesCache.i2i.slice(0,12), ...stylesCache.i2v.slice(0,6)].forEach(s=>{
    const img = new Image(); img.src = s.src; img.title = s.name + ' · ' + s.kind;
    img.onclick = () => { $('#prompt').value = s.p;
      if (s.kind==='i2v') show(`<span class="tag">i2v 风格已套用</span>`); };
    box.appendChild(img);
  });
}
loadStyles();

function show(html){ out.innerHTML = html; }
function busy(on, label){
  document.querySelectorAll('button').forEach(b=>b.disabled=on);
  if(on) show('<pre>' + label + '…</pre>');
}
function fmt(o){ return '<pre>' + JSON.stringify(o,null,2).replace(/</g,'&lt;') + '</pre>'; }

$('#btnEdit').onclick = async () => {
  const f = $('#file').files[0]; if(!f) return alert('请先选择图片');
  const fd = new FormData(); fd.append('image', f); fd.append('prompt', $('#prompt').value);
  busy(true,'图生图中（约 15-25s）');
  const t0 = performance.now();
  try{
    const r = await fetch('/v1/images/edits', {method:'POST', body:fd});
    const j = await r.json();
    if(!j.data) return show(fmt(j));
    const url = j.data[0].url;
    show(`<span class="tag">${((performance.now()-t0)/1000).toFixed(1)}s</span>
      <img src="${url}"><pre>${url}</pre>`);
  }catch(e){ show(fmt({error:String(e)})); } finally { busy(false); }
};

$('#btnVideo').onclick = async () => {
  const f = $('#file').files[0]; if(!f) return alert('请先选择图片');
  const b64 = await new Promise(res=>{ const fr=new FileReader();
    fr.onload=()=>res(fr.result.split(',')[1]); fr.readAsDataURL(f); });
  busy(true,'图生视频中（seedance-lite 约 45-90s，别关页面）');
  const t0 = performance.now();
  try{
    const r = await fetch('/kreivo/i2v', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({image_base64:b64, prompt:$('#prompt').value,
        model:$('#model').value, width:+$('#size').value, height:+$('#size').value})});
    const j = await r.json();
    if(!j.url) return show(fmt(j));
    show(`<span class="tag">${((performance.now()-t0)/1000).toFixed(1)}s</span>
      <span class="tag">${j.model}</span><video src="${j.url}" controls autoplay loop></video><pre>${j.url}</pre>`);
  }catch(e){ show(fmt({error:String(e)})); } finally { busy(false); }
};

$('#btnSvc').onclick = async () => {
  const f = $('#file').files[0]; if(!f) return alert('请先选择图片');
  const b64 = await new Promise(res=>{ const fr=new FileReader();
    fr.onload=()=>res(fr.result.split(',')[1]); fr.readAsDataURL(f); });
  const svc = $('#svc').value;
  busy(true, svc + ' 处理中…');
  const t0 = performance.now();
  try{
    const r = await fetch('/kreivo/service/' + svc, {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({image_base64:b64, prompt:$('#prompt').value})});
    const j = await r.json();
    const dt = `<span class="tag">${((performance.now()-t0)/1000).toFixed(1)}s</span><span class="tag">${svc}</span>`;
    if(j.url) show(dt + `<img src="${j.url}"><pre>${j.url}</pre>`);
    else show(dt + fmt(j));
  }catch(e){ show(fmt({error:String(e)})); } finally { busy(false); }
};

$('#btnT2I').onclick = async () => {
  busy(true,'文生图中（约 8-15s）');
  const t0 = performance.now();
  try{
    const r = await fetch('/v1/images/generations', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({prompt:$('#prompt').value, size:$('#size').value+'x'+$('#size').value})});
    const j = await r.json();
    if(!j.data) return show(fmt(j));
    const url = j.data[0].url;
    show(`<span class="tag">${((performance.now()-t0)/1000).toFixed(1)}s</span>
      <img src="${url}"><pre>${url}</pre>`);
  }catch(e){ show(fmt({error:String(e)})); } finally { busy(false); }
};
</script></body></html>"""


# ---------------------------------------------------------------- HTTP 服务
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _send(self, code: int, body: bytes, ctype: str = "application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode())

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            return self._send(200, DEMO_HTML.encode(), "text/html; charset=utf-8")
        if u.path == "/health":
            return self._json(200, {"ok": True, "upstream": "aperogroup",
                                    "key_hint": API_KEY[:8] + "…" + API_KEY[-4:],
                                    "skew_ms": _skew_ms})
        if u.path == "/v1/models":
            return self._json(200, {"object": "list", "data": [
                {"id": "kreivo-image-edit", "object": "model"},
                {"id": "kreivo-text2image", "object": "model"},
                {"id": "kreivo-i2v-seedance-lite", "object": "model"},
                {"id": "kreivo-i2v-seedance-pro", "object": "model"},
                {"id": "kreivo-i2v-inhouse", "object": "model"},
                {"id": "kreivo-enhance", "object": "model"},
                {"id": "kreivo-beauty", "object": "model"},
                {"id": "kreivo-clothes", "object": "model"},
                {"id": "kreivo-image-ai", "object": "model"},
                {"id": "kreivo-art-premium", "object": "model"},
                {"id": "kreivo-segment", "object": "model"},
                {"id": "kreivo-remove-object", "object": "model"},
                {"id": "kreivo-fitting", "object": "model"},
            ]})
        if u.path == "/kreivo/styles":
            kind = (parse_qs(u.query).get("kind") or ["i2i"])[0]
            try:
                return self._json(200, styles(kind))
            except Exception as e:
                return self._json(502, {"error": str(e)})
        self._json(404, {"error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n)
        try:
            if self.path == "/v1/images/edits":
                f = parse_multipart(raw)
                img = f.get("image")
                if not img:
                    return self._json(400, {"error": {"message": "missing image field"}})
                res = edit_image(img, f.get("prompt") or "enhance")
                return self._json(200, {"created": int(time.time()),
                                        "data": [{"url": res["url"], "revised_prompt": f.get("prompt")}],
                                        "elapsed_s": res["elapsed_s"]})

            if self.path == "/v1/images/generations":
                d = json.loads(raw or b"{}")
                w = h = 1024
                if "x" in (d.get("size") or ""):
                    try:
                        w, h = (int(x) for x in d["size"].split("x"))
                    except ValueError:
                        pass
                res = text_to_image(d.get("prompt", ""), w, h, d.get("negative_prompt", ""))
                return self._json(200, {"created": int(time.time()),
                                        "data": [{"url": res["url"]}], "elapsed_s": res["elapsed_s"]})

            if self.path == "/kreivo/edit":
                d = json.loads(raw or b"{}")
                img = base64.b64decode(d["image_base64"]) if d.get("image_base64") else None
                if not img:
                    return self._json(400, {"error": "image_base64 required"})
                res = edit_image(img, d.get("prompt") or "enhance", d.get("mode") or "IMAGE_EDITING")
                return self._json(200, {"success": True, **res})

            if self.path == "/kreivo/i2v":
                d = json.loads(raw or b"{}")
                img = base64.b64decode(d["image_base64"]) if d.get("image_base64") else None
                if not img:
                    return self._json(400, {"error": "image_base64 required"})
                res = image_to_video(img, d.get("prompt") or "natural motion",
                                     d.get("model") or "seedance-lite",
                                     d.get("width") or 1024, d.get("height") or 1024)
                return self._json(200, {"success": True, **res})

            if self.path.startswith("/kreivo/service/"):
                name = self.path.rsplit("/", 1)[-1]
                d = json.loads(raw or b"{}")
                blobs = []
                for k in ("image_base64", "mask_base64", "cloth_base64"):
                    if d.get(k):
                        blobs.append(base64.b64decode(d[k]))
                return self._json(200, run_service(name, blobs, d))

            self._json(404, {"error": "not found"})
        except Exception as e:
            self._json(502, {"error": str(e)})


if __name__ == "__main__":
    print(f"Kreivo 2API demo  ->  http://127.0.0.1:{PORT}/   (key {API_KEY[:8]}…)")
    print("sync upstream clock…", sync_time(), "ms skew")
    print("warmup RC styles…", len(styles("i2i").get("categories", [])), "i2i categories")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

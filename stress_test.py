#!/usr/bin/env python3
"""
Kreivo 2API 本地压测
====================
对本地 demo_server.py 发起真实并发请求（不是 mock，全部打通到 aperogroup 上游）。

用法:
    python stress_test.py image 6        # 6 并发图生图 (qwen-editing)
    python stress_test.py t2i 8          # 8 并发文生图 (flux-klein)
    python stress_test.py video 3        # 3 并发图生视频 (seedance-lite, 约 60-120s/个)
    python stress_test.py mix 10         # 混合: 图生图*7 + 文生图*3

输出: 成功率 / p50 / p90 / max / 上游错误分布
"""
import base64
import os
import json
import statistics
import sys
import threading
import time
import urllib.request

BASE = "http://127.0.0.1:8977"
IMG = os.environ.get("INPUT_IMG", "samples/input.jpg")
PROMPTS = [
    "van gogh starry night oil painting",
    "anime cel-shaded portrait",
    "cyberpunk neon lighting",
    "soft watercolor dreamscape",
    "pixar 3d render style",
    "pencil sketch monochrome",
    "steampunk brass and gears",
    "studio portrait soft rim light",
]

_lock = threading.Lock()
rows: list[dict] = []


def _post(path: str, payload: dict, timeout: int) -> dict:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def worker(kind: str, idx: int, img_b64: str):
    prompt = PROMPTS[idx % len(PROMPTS)]
    t0 = time.time()
    err = None
    url = None
    try:
        if kind == "image":
            d = _post("/kreivo/edit", {"image_base64": img_b64, "prompt": prompt}, 300)
            url = d.get("url")
        elif kind == "t2i":
            d = _post("/v1/images/generations", {"prompt": prompt, "size": "1024x1024"}, 300)
            url = d["data"][0]["url"]
        elif kind == "video":
            d = _post("/kreivo/i2v", {"image_base64": img_b64, "prompt": prompt,
                                      "model": "seedance-lite", "width": 1024, "height": 1024}, 900)
            url = d.get("url")
        if not url:
            err = json.dumps(d)[:160]
    except Exception as e:                      # noqa: BLE001 - 压测需要收集一切失败
        err = f"{type(e).__name__}: {e}"
    dt = time.time() - t0
    with _lock:
        rows.append({"kind": kind, "idx": idx, "ok": bool(url), "t": dt, "err": err, "url": url})
        print(f"[{kind:5}] #{idx:02d} {'OK  ' if url else 'FAIL'} {dt:6.1f}s"
              + ("" if url else "  " + (err or "")), flush=True)


def run(kind: str, n: int, img_b64: str):
    threads = [threading.Thread(target=worker, args=(kind, i, img_b64)) for i in range(n)]
    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.time() - t0

    times = [r["t"] for r in rows]
    ok = sum(1 for r in rows if r["ok"])
    print("\n" + "=" * 66)
    print(f"kind={kind}  n={len(rows)}  success={ok}/{len(rows)} ({ok/len(rows)*100:.0f}%)  wall={wall:.1f}s")
    if times:
        p = lambda q: statistics.quantiles(times, n=100)[q - 1] if len(times) > 1 else times[0]
        print(f"latency  p50={statistics.median(times):.1f}s  p90={p(90):.1f}s  "
              f"max={max(times):.1f}s  min={min(times):.1f}s")
    fails = [r for r in rows if not r["ok"]]
    if fails:
        print(f"failures ({len(fails)}):")
        for r in fails:
            print(f"  #{r['idx']:02d} {r['err']}")
    print(f"throughput ~ {ok / wall * 60:.1f} req/min")
    print("=" * 66)
    return ok, len(rows)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "image"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    img_b64 = base64.b64encode(open(IMG, "rb").read()).decode()

    # /health 探活
    try:
        with urllib.request.urlopen(BASE + "/health", timeout=10) as r:
            print("health:", r.read().decode())
    except Exception as e:
        print("server down:", e)
        sys.exit(1)

    if mode == "mix":
        half = max(1, n * 7 // 10)
        run("image", half, img_b64)
        run("t2i", n - half, img_b64)
    else:
        run(mode, n, img_b64)

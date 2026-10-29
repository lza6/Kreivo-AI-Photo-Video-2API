#!/usr/bin/env bash
# 单实例、低频重试（GitHub 建仓是 abuse 级限流，别再高频打）
R=lza6/Kreivo-AI-Photo-Video-2API
for i in $(seq 1 6); do
  if gh repo view "$R" >/dev/null 2>&1; then
    echo "[try $i] repo exists"
  else
    out=$(gh repo create "$R" --public \
      --description "Reverse-engineered Kreivo AI Photo & Video Generator 1.1.0 (aperogroup) into a local 2API gateway: qwen-editing / flux-klein / seedance i2v" 2>&1)
    echo "[$(date +%H:%M:%S)] try $i: $(echo "$out" | tail -1)"
    if ! gh repo view "$R" >/dev/null 2>&1; then sleep 1200; continue; fi
  fi
  git remote remove kreivo 2>/dev/null
  git remote add kreivo "https://github.com/$R.git"
  if git push -q -u kreivo HEAD:main 2>&1 | tail -2; then
    echo "PUSHED OK -> https://github.com/$R"
    break
  fi
  sleep 1200
done

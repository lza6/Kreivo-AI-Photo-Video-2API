#!/usr/bin/env bash
# 建仓 + 推送（幂等），GitHub 建仓有小时级 abuse 限流，退避重试
R=lza6/Kreivo-AI-Photo-Video-2API
for i in $(seq 1 20); do
  if gh repo view "$R" >/dev/null 2>&1; then
    echo "[try $i] repo exists"
  else
    out=$(gh repo create "$R" --public \
      --description "Reverse-engineered Kreivo AI Photo & Video Generator 1.1.0 (aperogroup) into a local 2API gateway: qwen-editing / flux-klein / seedance i2v" 2>&1)
    echo "[try $i] create: $(echo "$out" | tail -1)"
    if echo "$out" | grep -q "too many repositories"; then sleep 300; continue; fi
    if ! echo "$out" | grep -q "Created repository"; then sleep 120; continue; fi
  fi
  git remote remove kreivo 2>/dev/null
  git remote add kreivo "https://github.com/$R.git"
  if git push -u kreivo HEAD:main 2>&1 | tail -2; then
    echo "PUSHED OK -> https://github.com/$R"
    break
  fi
  sleep 120
done

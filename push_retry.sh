#!/usr/bin/env bash
# GitHub 建仓有频率限制，指数退避重试
for i in $(seq 1 12); do
  out=$(gh repo create lza6/Kreivo-AI-Photo-Video-2API --public \
        --description "Reverse-engineered Kreivo AI Photo & Video Generator 1.1.0 (aperogroup) into a local 2API gateway: qwen-editing / flux-klein / seedance i2v" \
        --source=. --remote=origin --push 2>&1)
  echo "[try $i] $(echo "$out" | tail -2)"
  if ! echo "$out" | grep -q "too many repositories"; then
    echo "DONE: $out"
    break
  fi
  sleep 300
done

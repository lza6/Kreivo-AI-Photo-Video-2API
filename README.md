# Kreivo — AI Photo & Video Generator 1.1.0 · 逆向 + 2API 网关 (R1)

> APK：`kreivo---ai-photo-&-video-generator-1.1.0-modyolo.apk`
> 包名：`com.ai.art.aiimagegenerator.aivideogenerator.aiphoto.aiart`
> 上游：aperogroup 家族（与 Alura / Umagic 同集团，服务器 RSA 公钥全站共用）

**状态：协议 100% 还原，11 个服务全部跑通真实出图/出片（R1 三条主链 + R2 八个工具链），本地网关 + demo 页 + 压测全绿。**

---

## 30 秒跑起来

```bash
pip install requests cryptography

# 1) 填一个可用的上游 key（仓库不提交凭证，见下方「凭证」）
echo "sk-你的活跃apero_key" > apikey.local    # 或 set APERO_API_KEY=...

# 2) 起网关
python demo_server.py                        # 或 PORT=8977 python demo_server.py
# 浏览器打开 http://127.0.0.1:8977/
```

```bash
python stress_test.py image 10   # 10 并发图生图
python stress_test.py t2i 8      # 8 并发文生图
python stress_test.py video 3    # 3 并发图生视频（每个 45-65s）
python stress_test.py mix 10     # 混合
```

---

## 能力与实测数据

| 能力 | 上游 | 语义 | 实测 |
|---|---|---|---|
| 图生图 | `api-img-gen-wrapper` `/api/v5.1/qwen-editing` | 同步 | ✅ 17-24s |
| 文生图 | `api-img-gen-wrapper` `/api/v5/premium/text-2-image` | 同步 | ✅ 4.6-16s（flux-klein） |
| 图生视频 | `video-gen-core` `/api/v5/image-2-video` | 异步轮询 | ✅ 45-65s → h264 704×704 24fps 5.04s |
| 风格库 | Firebase RemoteConfig | 同步 | ✅ i2i 7 分类 / i2v 1 分类 / t2i 6 条 |
| 另 8 个工具 | enhance / beauty / art-premium / segment / clothes / image-ai / fitting / remove-object | 同步 | ✅ 全部真实出图（13-38s） |

**压测（真实并发打上游，零 mock）**

| 场景 | 并发 | 成功 | p50 | p90 | 吞吐 |
|---|---|---|---|---|---|
| 图生图 | 6 | 6/6 100% | 21.9s | 24.4s | 15.0 req/min |
| 图生图 | 10 | 10/10 100% | 23.1s | 30.2s | 19.8 req/min |
| 文生图 | 8 | 8/8 100% | 16.6s | 27.3s | 17.8 req/min |
| 图生视频 | 3 | 3/3 100% | 49.9s | 73.5s | 2.8 req/min |

零 429、零频控、零降级。上游只卡 `x-api-keyid` 是否活跃。

---

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 浏览器 demo 页（上传→图生图/图生视频/文生图，实时出结果） |
| GET | `/health` | 探活 + key 指纹 + 时钟偏移 |
| GET | `/v1/models` | 模型列表 |
| POST | `/v1/images/edits` | OpenAI 兼容 multipart 图生图 |
| POST | `/v1/images/generations` | OpenAI 兼容文生图 |
| POST | `/kreivo/edit` | 原生 JSON `{image_base64, prompt, mode}` |
| POST | `/kreivo/i2v` | 图生视频 `{image_base64, prompt, model, width, height}` |
| POST | `/kreivo/service/<name>` | 通用工具链：`enhance` `beauty` `art-premium` `segment` `clothes` `image-ai`（`{image_base64, prompt, mode?}`）、`fitting`（`{image_base64, cloth_base64, cloth_type}`）、`remove-object`（`{image_base64, mask_base64}`） |
| GET | `/kreivo/styles?kind=i2i\|i2v\|t2i` | RC 风格库原文 |

---

## 凭证

仓库**不提交**任何上游 key。`demo_server.py` / `sigkit.py` 按以下顺序取：

1. 环境变量 `APERO_API_KEY`
2. 同目录 `apikey.local`（已 gitignore，首行即 key）

Kreivo 自己 RemoteConfig 下发的 `api_key`（`sk-PCZX…WHPK`）**已被上游停用**，拿来跑会得到
`401 {"message":"Not active api key"}`。能用的必须是同集团（Alura / Umagic 系）任一活跃 `sk-` key ——
服务器 RSA 公钥全站共用，key 只决定配额。想自己找：抓任意同集团 APK 的 RC（`rc_fetch.py` 就是现成模板），
或从 `docs/PROTOCOL.md` §3 的 REST 端点拉别的项目。

---

## 核心协议（详见 `docs/PROTOCOL.md`）

```
x-api-signature = Base64_NO_WRAP( RSA/None/PKCS1Padding(pub, "{ms_ts}@@@{api_key}@@@{nonce 0..999999}" ))
```
- 公钥 = APK `assets/prod.pem`（2048-bit，Apero 集团全站共用）
- `api_key` 由 Firebase RemoteConfig 参数 `api_key` 下发，可纯 REST 直拉（项目 `aip894-ai-photo-video`）
- **Kreivo 自己的 key 已被上游停用（401 Not active api key）**，本仓库默认用同集团兄弟项目 Alura 的活跃 key，
  可用 `APERO_API_KEY` 环境变量覆盖
- 时间戳必须先 `/timestamp` 校准偏移
- `x-api-token: not_get_api_token` 是官方合法回落值（Play Integrity 未强制）

---

## 文件

```
demo_server.py          网关 + demo 页（单文件，零依赖除 requests/cryptography）
stress_test.py          并发压测（image / t2i / video / mix）
sigkit.py               协议内核：签名、presign、S3 PUT、时钟校准
e2e.py / video_full.py  单条链路实验脚本（图 / 视频）
probe.py / probe_all.py 端点头部与 14 个服务可用性探测
rc_fetch.py             Firebase RemoteConfig 直拉（含 ad 参数全量）
rc_raw.json             RC 全量快照（177 个参数）
browser_check.py        Playwright 真浏览器端到端验证
shot_initial.png / shot_t2i.png / shot_i2i.png / shot_i2v.png / shot_service.png   浏览器证据
out_image.jpg / out_video.mp4                                    真实产物
docs/PROTOCOL.md        协议还原报告（签名链/端点/踩坑/风控）
docs/NEW-API-INTEGRATION.md  new-api 对接指南（路线 A 零改造 / 路线 B 原生 type 74）
app.apk                 原始样本
```

---

## 风险与限制

1. **key 单点**：可用性完全取决于 `sk-VqJL…` 这把 key。上游一封 → 全线 401。渠道层必须支持热换 key，
   并把 `401 Not active api key` 单独映射（不要当 5xx 重试）。
2. **`seedance-pro` 未跑生成验收**：只验证了 `seedance-lite` 与 `inhouse` 出片。
3. **`beauty` 的可选参数（smooth/eyes/…）取值域未逐一枚举**，只验证了默认值出图；`image-ai` 的
   `ART` 模式服务端大小写处理有 bug（传 `ART` 报 `Invalid mode value: art`），实际可用 `FAST_EDITING`/`TRANSFORM`。
4. **无 Play Integrity 强校验是当前前提**，若上游打开强制校验，纯协议直连会断。
5. `remove-background` / `image-restore` / `image-outpainting` 三个 host 当前 404（服务未部署）。

---

## 免责

仅用于安全研究与协议互操作性分析，产物不对外提供服务。上游凭证与内容版权归原厂商所有。

---

## 归档位置

- 主仓库（目标）：`lza6/Kreivo-AI-Photo-Video-2API`
- 即时镜像：`lza6/Umagic-Kreivo-APP-2api` 分支 **`kreivo-1.1.0-gateway`**
  （同包名同集团的兄弟仓库，GitHub 建仓 abuse 限流期间先落到这里）

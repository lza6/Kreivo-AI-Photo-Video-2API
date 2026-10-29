# Kreivo — 协议还原报告 (v1.1.0 / AIP894)

> 目标 APK：`kreivo---ai-photo-&-video-generator-1.1.0-modyolo.apk`（28.9 MB，modyolo 改版）
> 包名：`com.ai.art.aiimagegenerator.aivideogenerator.aiphoto.aiart`
> 构建标记：`AIPHOTOGENERATOR_AIVIDEOGENERATOR_v1.1.0(3)_03.25.2026_r1_appProdRelease`
> 后端家族：**aperogroup**（与 Alura / Umagic 同集团、同服务器 RSA 公钥）
> 逆向环境：静态（apktool 2.x + jadx 工具链）+ 真实网络验证（无模拟器、无 Frida、无抓包）

---

## 1. 结论速览

| 层 | 结论 | 证据等级 |
|---|---|---|
| 签名协议 | RSA/None/PKCS1Padding → `ms_ts@@@api_key@@@nonce`，Base64(NO_WRAP) | 已验证（真实调用 200） |
| 公钥 | `assets/prod.pem` = `SignatureInterceptor` 内嵌常量 = `com.apero.aiservice.BuildConfig.PUBLIC_KEY` | 静态确认 |
| api_key 来源 | Firebase RemoteConfig 参数 `api_key`（项目 `aip894-ai-photo-video`） | 已验证（REST 直拉） |
| Kreivo 自带 key | `sk-PCZX…WHPK` → **401 `Not active api key`（上游停用）** | 已验证 |
| 可用 key | 同集团 Alura 的 `sk-VqJL…IL`（公钥全站共用，key 决定配额） | 已验证 |
| 图生图 | `/api/v5.1/qwen-editing` 同步出图 ~18s | 已验证 |
| 文生图 | `/api/v5/premium/text-2-image` flux-klein 同步 ~5-10s | 已验证 |
| 图生视频 | `/api/v5/image-2-video`（i2v）异步轮询，45-65s 出 5s/24fps h264 | 已验证（真实 mp4） |
| 完整性校验 | AperoIntegrity 为空 → `x-api-token: not_get_api_token`，无 Play Integrity 强校验 | 静态确认 + 已验证 |
| 服务矩阵 | 14 个端点中 11 个用该 key 可用 | 已验证 |

---

## 2. 签名链（com.apero.signature）

`SignatureInterceptor.intercept()` 每次请求现算 6 个头：

```
x-api-signature = Base64_NO_WRAP( RSA/None/PKCS1Padding(pub,
                      f"{ms_ts}@@@{api_key}@@@{nonce}" ) )
nonce           = floor(random() * 1_000_000)      // 0..999999，unsigned，无补零
x-api-timestamp = AiServiceConfig.getTimeStamp()   // System.currentTimeMillis() + 服务器偏移
x-api-keyid     = api_key
x-api-token     = SignatureData.tokenIntegrity ?: "not_get_api_token"
x-api-bundleId  = applicationId
App-name        = projectName
App-version     = "1.1.0"
Country-code    = Locale country（缺省 "US"）
device          = "android"
```

关键源码位置：

- `smali_classes2/com/apero/signature/SignatureParserImpl.smali#encryptSignature` — 拼串 + 加密 + Base64
- `smali_classes2/com/apero/aigenerate/network/interceptor/SignatureInterceptor.smali` — 头组装
- `smali_classes2/com/apero/aigenerate/AiServiceConfig.smali#setUpData` — projectName / applicationId / apiKey 注入
- 调用点：`smali/a3/j0.smali`（projectName=`AI_AIP894_Visionlab_Android`, bundleId=包名, version=1.1.0）

**时钟必须先校准**：先 `GET {base}/timestamp` 拿服务端毫秒时间戳，算出 skew 再签，否则窗口偏差过大被拒。
三个业务域都提供 `/timestamp`（`api-style-manager` 没有）。

### 公钥

`assets/prod.pem`（无 PEM 头尾，裸 base64，2048-bit）：

```
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA5z8DrSdxAFy5ju27JzxUDGD5OdPRnKVrXPypiBVT7NK4ltgbcud3+Li3H1DiAFNvaSDPumZMEbAkfGWZ6s3KtiI7TRmZwQ2yyH6mug6GhrCLD6CZJUQ2CPmhO3JYTYOgN53E6hwm/Teb9I156S04qHjLLLBxk9Mklu5X06kdhMBYwHFAZ3oByeoWUryrQC0Mv9C5ZahKzoQNuJNL2sv+ws2e5Zaj8Rid4AjhvqB6dYhWP4QM+0IiNjs/j08aRgcyOrenbQEIieU+XF6mQWF2Jfg317e0KjWnpru+uPVVgrEn9rNvQeXu2u4SZhT6rnLQzBLbJrngNcNw3gXfxxsoowIDAQAB
```

> `assets/dev.pem` 是另一把 dev 环境公钥（`ai-wrapper-service.dev.aperogroup.ai`），生产无用。
> `com.apero.signature.BuildConfig.PRIVATE_KEY` 是一把 **1024-bit PKCS8 私钥**，与上面 2048-bit 公钥不配对，
> 全工程无引用点（仅 lib 常量），判定为 SDK 遗留死密钥，与签名链无关。

---

## 3. api_key 的获取路径

APK 里 **没有** 明文 `sk-` 常量（`strings`/`dex`/`assets`/`.so` 全扫过，只有 `sk-mNativeVideoController` 误报）。
运行时来源：**Firebase RemoteConfig**（键名 `api_key`），通过 Rest API 直拉，无需设备：

```http
POST https://firebaseremoteconfig.googleapis.com/v1/projects/aip894-ai-photo-video/namespaces/firebase:fetch?key=AIzaSyBEGwusHz7rcFj66cYlG6lpYogFLhIk-DU
Content-Type: application/json
X-Android-Package: com.ai.art.aiimagegenerator.aivideogenerator.aiphoto.aiart
X-Android-Cert: 61ed377e85d386a8dfee6b864bd85b0bfaa5af81

{"app_instance_id":"<任意32位hex>","app_id":"1:546583882737:android:b5f660b2d255e8f4be3250","platform_version":"30"}
```

返回 177 个参数（`rc_raw.json` 已留档）。与本项目相关的：

| RC 键 | 用途 |
|---|---|
| `api_key` | apero 签名 key（**当前值已被上游停用**） |
| `image_to_image_style` | i2i 风格库 JSON（7 个分类 / 12251 字符，含 `style_mode:"IMAGE_EDITING"` + `image_prompt`） |
| `image_to_video_style` | i2v 风格库 JSON（1 分类，`style_mode:"i2v"` + `video_prompt`） |
| `text_to_image_style` | t2i 风格库（6 条） |
| `thumbnail_banner_change` | 首页 banner |
| `free_image_generation_limit_per_day` / `free_video_generation_limit_per_day` | 客户端免费额度（各 1 次） |
| `AppSettings` | 旧的 imagix/dailymorningupdate 配置（**本版本已不走**，属遗留） |

> 注意：`AppSettings` 里的 `faceswap/ghibli/api.imagix.dailymorningupdate.com` 是上一代后端，
> v1.1.0 的生成链路已全部切到 `*.aperogroup.ai`。别被它误导。

---

## 4. 端点清单（com.apero.aiservice）

`smali_classes2/com/apero/aiservice/BuildConfig.smali` 是完整域名表，`network/request/*.smali` 是路径。

| 服务 | 域名 | 路径 | 上传方式 | 实测 |
|---|---|---|---|---|
| 图生图（qwen-editing） | api-img-gen-wrapper | `/api/v5.1/qwen-editing` | presigned S3 | 200 ✅ 18s |
| 图生图（flux-klein） | api-img-gen-wrapper | `/api/v5/image-ai` | presigned S3 | 200 ✅ 13s（mode 见 §10） |
| 文生图 | api-img-gen-wrapper | `/api/v5/premium/text-2-image` | 无（直接 JSON） | 200 ✅ 5-10s |
| 艺术风格 | art-premium-core | `/api/v5/art-premium` | presigned S3 | 200 ✅ 29s |
| 图生视频 | video-gen-core | `/api/v5/image-2-video` | presigned S3 | 200 ✅ 45-65s |
| 视频状态 | video-gen-core | `/api/v5/image-2-video/video/{videoId}` | — | 200 ✅ |
| 图片增强 | enhance-core | `/api/v5/image-enhance` | presigned S3 | 200 ✅ 13s |
| 抠图去物体 | objectremoval-core | `/api/v5/remove-object` | presigned S3 ×2 | 200 ✅ 38s |
| 分割 | segment-core | `/api/v5/segment` | presigned S3 | 200 ✅ 15s（返回坐标矩阵） |
| 换装 | cloth-change-core | `/api/v5/clothes-changing` | presigned S3 | 200 ✅ 20s |
| 试衣 | fitting-core | `/api/v5/fitting` | presigned S3 ×2 | 200 ✅ 30s |
| 美颜 v5 | beauty-core | `/api/v5/beauty` | presigned S3 | 200 ✅ 21s |
| 美颜 v4 | beauty-core | `/api/v4/beauty` | — | 410 Deprecated |
| 去背景 | core-outpaint | `/api/v5/remove-background` | presigned S3 | 404（该 host 未部署） |
| 修复 | image-restore-core | `/api/v5/image-restore` | presigned S3 | 404（该 host 未部署） |
| 扩图 | core-outpaint | `/api/v5/image-outpainting` | presigned S3 | 404 |
| 风格库 | api-style-manager | `/style-external/styles` | GET 参数 | 免鉴权 590 类 |
| 时钟 | 各业务域 | `/timestamp` | GET | 200 ✅ |

### 统一上传链（presigned）

```
GET   {base}{service}/presigned-link            -> {"data":{"url":"<S3 PUT URL>","path":"<key>"}}
PUT   <url>  body=<image bytes>  Content-Type: image/jpeg   (URL 有效期 120s)
POST  {base}{service}  {"files":["<path>"], ...业务字段}
```

---

## 5. 图生图请求体（qwen-editing）

```json
{
  "files": ["ai-core-qwen-editing/20261029/<uuid>/input.jpg"],
  "mode": "IMAGE_EDITING",          // 或 "COMBINE_IMAGES"
  "positivePrompt": "van gogh starry night",
  "positivePrompt2": ""
}
```

响应：`{"statusCode":200,"data":{"url":"https://static.aperogroup.ai/…/output/xxx_0.jpeg"}}`（同步，无需轮询）

模型字段（可选）：`model`、`loraName`、`negativePrompt`、`positivePrompt3`、`keepFace`、`width`、`height`、`inhouse`。

---

## 6. 图生视频请求体（image-2-video）★

```json
{
  "files": ["video-compose/20261029/<uuid>/input.jpg"],
  "mode": "i2v",
  "positivePrompt": "gentle camera push-in, cinematic",
  "positivePrompt2": "",
  "positivePrompt3": "",
  "negativePrompt": "",
  "keepFace": false,
  "width": 1024,
  "height": 1024,
  "model": "seedance-lite",
  "notificationProvider": "fcm",
  "notificationId": "fcm-<任意唯一串>"
}
```

### 踩坑记录（都是实测撞出来的）

| 现象 | 真实原因 | 修法 |
|---|---|---|
| `400 client.bad-request`（无细节） | 缺 `notificationProvider` + `notificationId` | 两个都填非空；`notificationProvider` 填 `"fcm"` |
| `400 client.bad-request` | 缺 `width`/`height` | 必须显式给，且 ∈ [512,1024] 整数 |
| `400 required` | 给了 `notificationProvider:""` 空串 | 空串 = 缺失，别传空 |
| `400 The width must be an integer within the range of 512 to 1024` | 源图宽 > 1024（如 1120）或传了 1280 | 先缩放源图 / 传值 |
| `400 model is invalid. Only inhouse, seedance-lite, seedance-pro are allowed` | `model` 取值非法 | 仅这三个值 |
| `mode` 传 `IMAGE_2_VIDEO`/`image_to_video` | 只认 `i2v` | 固定 `"i2v"` |

### 轮询

```
GET /api/v5/image-2-video/video/{videoId}
→ data.result = {"videoId": "...", "videoStatus": "processing"|"completed"|"failed",
                 "resultFile": "https://static.aperogroup.ai/ai-core-video-lite/…/xxx_0.mp4"}
```

- `videoTimeout` = 600000 ms，服务端自己给的预算。
- 实测节奏：submit 后 5-10s 变 `processing`，`seedance-lite` 45-50s `completed`，`inhouse` 47s。
- 输出规格实测：**h264 / 704×704 / 24 fps / 5.04 s / ≈6.9 MB**（lite）。
- `notificationId` 只是 FCM 推送标识，服务端不回推也不校验真实性，用随机串即可。

---

## 7. 客户端免费额度 / 风控

- 免费额度在**客户端**判定（`free_image_generation_limit_per_day=1`），服务端不限制次数 —— 只要 key 活着即可无限打。
  R1 压测 10 并发图生图 100% 成功、零 429 / 零降级，与之一致。
- Play Integrity：`AiServiceConfig.setupIntegrity()` + `AperoIntegrity`，但 `setRequestNewToken(false)`，
  token 为空时头回落 `not_get_api_token`，服务端**未强制**。这是目前能纯协议直连的原因。
  → 若 Apero 后续打开强制校验（`api/integrity-token`），此链路会断，需要重做 Integrity 侧。
- 无 IP 白名单、无 UA 校验（`okhttp/4.12.0` 仅作伪装）、无设备指纹上报到业务域。
- 真正的门槛只有一个：**活跃的 `x-api-keyid`**。

---

## 8. 混淆与坑

- **MilkObfuscator**：`assets/dic`（3.9 KB）是字节级 XOR 字典，`short[]` 常量在类初始化器里解码。
  本版本的 api_key 不走这条路径（走 RC），所以没被卡住。
- **域名/端点全明文**，没用字符串加密 —— 这是突破口。
- `App-name` 必须与 `bundleId` 一起自洽；实测 `AI_AIP894_Visionlab_Android` + Kreivo 包名可以，
  换 Umagic 的 `App-name` 也过（服务端只校验 key 与签名）。
- `x-api-token` 留 `not_get_api_token` 是官方客户端的合法回落值，不是伪造。

---

## 9. 与既有工作的关系

- 同集团兄弟项目已交付：Alura（`D:/apk-analysis/alura/`，源出本 key）、Umagic（GitHub `lza6/Umagic-Kreivo-APP-2api`）。
- 本轮**新增**：`image-2-video` 全链路（此前只有图生图）、`text-2-image`、11 个服务的可用性矩阵、
  `notificationProvider/notificationId` 必修字段、纯静态拿到 RC key（无需模拟器/Frida/抓包）。

---

## 10. R2：8 个单/双图服务请求体（全部真实出图）

统一前置：`GET {base}{svc}/presigned-link` → `PUT` 图片 → `POST {base}{svc}`。
除 `image-ai` 用单数 `file`、`fitting`/`remove-object` 用双图之外，其余都是 `{"file": "<path>"}`。

| 服务 | 请求体 | 响应 | 实测 |
|---|---|---|---|
| `enhance` | `{"file":p}` | `data.url` | 13.4s |
| `beauty` | `{"file":p, "smooth"?, "eyes"?, "smile"?, "teethWhitening"?, "vLine"?, "lipsColor"?, "type"?, "denoise"?}` | `data.url` | 20.6s |
| `art-premium` | `{"file":p}` | `data.url` | 28.7s |
| `segment` | `{"file":p}` | `data[] = [{className, xLeft,yTop,xRight,yBottom, matrix:[{x,y}…]}]`（无 url） | 14.5s |
| `clothes` | `{"file":p, "prompt":"a red dress", "style"?, "contentStyle"?}` | `data.url` | 19.9s |
| `image-ai` | `{"file":p, "mode":"FAST_EDITING", "positivePrompt":"…"}` | `data.url` | 13.5s |
| `fitting` | `{"inputImage":p1, "clothImage":p2, "clothType":"upper_body"}` | `data.url` | 30.2s |
| `remove-object` | `{"file":p1, "mask":p2}` | `data.url` | 37.9s |

### 枚举白名单（都是服务端硬校验，报错信息直接给）

```
image-ai.mode   : ART / FASHION / SUPER_ART / TRANSFORM / FAST_EDITING / MULTI_IMAGES /
                  POSE_TRANSFER / VIDEO_POSE_TRANSFER / 0..7 / 10
                  ⚠️ 大小写敏感且落地时被转小写：传 "ART" 会报 "Invalid mode value: art"，
                     实际可用的是 FAST_EDITING / TRANSFORM（已实测出图）
fitting.clothType: upper_body / lower_body / full_body
beauty.type      : 见 BeautyStyleTypeAliases（未逐一枚举）
```

### 其它坑

- `image-ai` 必须用 **单数字段 `file`**，传 `files:[…]` 会报 `File must be a string`。
- `remove-object` 的 `mask` 也必须是 presign 上传后的 path；传原图当 mask 服务端不校验合法性，照样出图（R2 就是这样验通的）。
- `fitting` 需要**两次 presign 两次上传**（`inputImage` 与人像/衣服图各一份）。
- `segment` 返回的是检测框 + 轮廓点矩阵，不是图片 URL，接渠道时注意别当图片处理。

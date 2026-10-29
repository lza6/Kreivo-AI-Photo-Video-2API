# 交接文档：把 Kreivo(2API) 接入 new-api

> **给谁看**：接手 new-api 对接工作的另一个会话 / 另一位工程师。
> **本文是自包含任务契约**——不需要读逆向过程，照着做完就能验收。
> 上游协议细节见同目录 `PROTOCOL.md`；本文件只讲「怎么接进来」。

---

## 0. 任务契约

| 项 | 内容 |
|---|---|
| 目标 | 让 new-api 能对外提供 Kreivo 的图生图 / 文生图 / 图生视频（可选：8 个工具链） |
| 上游协议状态 | ✅ 已 100% 还原并实测出图出片（2026-10-29） |
| 现成参考实现 | `D:/apk-analysis/kreivo110/demo_server.py`（Python，已跑通） |
| 不可改动区 | `relaykit/` 必须保持独立可编译；不得引入 `encoding/json` 直调（用 `common.Marshal/Unmarshal`） |
| 交付标准 | 见 §7 验收清单，全部要有**实际运行证据** |
| 分支 | 从 `main` 切 `feat/kreivo-channel`，不要直接改 main |

---

## 1. 上游协议速查（接渠道只需这 5 条）

```
base_img    = https://api-img-gen-wrapper.aperogroup.ai
base_video  = https://video-gen-core.aperogroup.ai
base_plus   = art-premium-core / enhance-core / segment-core / beauty-core /
              cloth-change-core / fitting-core / objectremoval-core .aperogroup.ai
```

**① 签名头（每次请求现算，不能缓存签名本身）**

```
raw = fmt.Sprintf("%s@@@%s@@@%s", msTs, apiKey, nonce)   // nonce ∈ [0,999999)
sig = Base64( RSA_PKCS1v15_Encrypt(pub2048, raw) )        // == RSA/None/PKCS1Padding
headers:
  x-api-signature: sig
  x-api-timestamp: msTs
  x-api-keyid:     apiKey
  x-api-token:     not_get_api_token
  x-api-bundleId:  com.ai.art.aiimagegenerator.aivideogenerator.aiphoto.aiart
  App-name:        AI_AIP894_Visionlab_Android
  App-version:     1.1.0
  Country-code:    US
  device:          android
  Accept:          application/json
```

**② 时钟校准（必须做，否则偶发被拒且报错不指向时间）**

```
GET {base}/timestamp  ->  {"data":{"timestamp": 1793284952812}}
skewMs = serverTs - time.Now().UnixMilli()
```

**③ 图片上传链（所有带图的服务都走这个）**

```
GET  {base}{svcPath}/presigned-link
     -> {"data":{"url":"<S3 PUT URL>","path":"<key>"}}     // url 120s 过期！
PUT  <url>  body=<image bytes>  Content-Type: image/jpeg     // 不带任何签名头
POST {base}{svcPath}  body=业务 JSON（含 "files"/"file" = 上面的 path）
```

**④ 三条主链的 body**

```jsonc
// 图生图（同步，~18s）
POST /api/v5.1/qwen-editing
{"files":["<path>"],"mode":"IMAGE_EDITING","positivePrompt":"...","positivePrompt2":""}
-> {"statusCode":200,"data":{"url":"https://static.aperogroup.ai/...jpeg"}}

// 文生图（同步，~5-16s，不需要上传）
POST /api/v5/premium/text-2-image
{"positivePrompt":"...","width":1024,"height":1024}
-> {"statusCode":200,"data":{"url":"..."}}

// 图生视频（异步，45-65s）
POST /api/v5/image-2-video
{"files":["<path>"],"mode":"i2v","positivePrompt":"...",
 "positivePrompt2":"","positivePrompt3":"","negativePrompt":"","keepFace":false,
 "width":1024,"height":1024,
 "model":"seedance-lite",                    // inhouse | seedance-lite | seedance-pro
 "notificationProvider":"fcm",               // ← 必填，缺了只回 400 无细节
 "notificationId":"fcm-<任意唯一串>"}         // ← 必填
-> {"statusCode":200,"data":{"videoId":"<uuid>","videoTimeout":600000,...}}

GET /api/v5/image-2-video/video/{videoId}
-> {"data":{"result":{"videoStatus":"processing|completed|failed",
                      "resultFile":"https://.../xxx_0.mp4"}}}
```

**⑤ 凭证**：`apiKey` 必须是**活跃**的 Apero 族 key。Kreivo 自己 RemoteConfig 下发的
`sk-PCZX…` 已 401 `Not active api key`。可用 key 走 `APERO_API_KEY` 环境变量注入，
**不要硬编码进仓库**。

---

## 2. 路线 A：零 Go 代码（建议先落地，1 小时）

现成的 `demo_server.py` 已经是 OpenAI 形态，直接用 `ChannelTypeAdvancedCustom(58)` 挂：

| 配置项 | 值 |
|---|---|
| 类型 | `58` AdvancedCustom（或 `1` OpenAI） |
| Base URL | `http://127.0.0.1:8977`（网关跑在哪填哪） |
| 密钥 | 任意非空（如 `sk-kreivo`）——**上游 key 由网关侧 `apikey.local` 管** |
| 模型 | `kreivo-image-edit`、`kreivo-text2image` |
| 端点 | `POST /v1/images/edits`（multipart）、`POST /v1/images/generations`（JSON） |

验收：`curl -X POST {new-api}/v1/images/edits -H "Authorization: Bearer sk-xxx" -F image=@a.jpg -F prompt="van gogh"`
→ 返回 `data[0].url` 且能在浏览器打开。

**局限**：`image-2-video` 没有 OpenAI 对应语义，走不了这条路线（除非你自己约定一个
`model=kreivo-i2v-seedance-lite` 并在网关侧加一路 `/v1/chat/completions` 的伪实现）。
要视频 → 路线 B。

---

## 3. 路线 B：原生渠道 `ChannelTypeKreivo = 74`

### 3.1 已核实的仓库事实（已实地查过，直接用）

- 模块路径：`github.com/lza6/new-api-Max`
- 2API 渠道占 **62–73**，`ChannelTypeDuck = 73`（`constant/channel.go`），后面紧跟 `ChannelTypeDummy`
  → **74 是下一个可用号**
- 模板渠道：`relay/channel/aivm/`（type 72，`adaptor.go` + `do_request.go` 两个文件搞定）
- 注册点：`relay/relay_adaptor.go`（`case constant.ChannelTypeAIVM: return &aivm.Adaptor{}` 附近）

### 3.2 改动清单（共 6 处）

| # | 文件 | 改什么 |
|---|---|---|
| 1 | `constant/channel.go` | 加 `ChannelTypeKreivo = 74`；`ChannelBaseURLs` 追加 `"https://api-img-gen-wrapper.aperogroup.ai"`；渠道名映射加 `ChannelTypeKreivo: "Kreivo"` |
| 2 | `constant/twoapi_channel.go` | 把 `ChannelTypeKreivo` 加进 `TwoAPIChannelTypes` —— **漏了会导致漏计费 + 出站压缩不豁免**（历史上 Duck/AIVM 都踩过） |
| 3 | `constant/api_type.go` + `common/api_type.go` | 追加 `APITypeKreivo` / `lnKreivo` 映射 |
| 4 | `controller/twoapi_panel.go` | 面板加一行统计（可选但建议） |
| 5 | `relay/channel/kreivo/{adaptor.go,do_request.go,sign.go,image.go,video.go}` | 新建，见 §4 |
| 6 | `relay/relay_adaptor.go` | `case constant.ChannelTypeKreivo: return &kreivo.Adaptor{}` |

### 3.3 Adaptor 必须实现的方法（照 aivm 抄签名）

```
Init(info *relaycommon.RelayInfo)
GetRequestURL(info) (string, error)
SetupRequestHeader(c, req *http.Header, info) error
GetModelList() []string
GetChannelName() string
ConvertOpenAIRequest / ConvertClaudeRequest / ConvertOpenAIResponsesRequest /
ConvertGeminiRequest / ConvertEmbeddingRequest / ConvertRerankRequest /
ConvertAudioRequest / ConvertImageRequest
DoRequest(c, info, requestBody io.Reader) (any, error)
DoResponse(c, resp, info) (usage any, err *types.NewAPIError)
```

---

## 4. 渠道实现要点（可直接用的 Go 代码）

### 4.1 `sign.go` —— RSA 信封签名（这是唯一的技术难点，其余都是搬砖）

```go
package kreivo

import (
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"encoding/base64"
	"fmt"
	"math/big"
	"strconv"
	"strings"
	"sync/atomic"
	"time"
)

// APK assets/prod.pem 原文（裸 base64，无 PEM 头尾）。Apero 集团全站共用。
const apPublicKeyB64 = "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA5z8DrSdxAFy5ju27JzxUDGD5OdPRnKVrXPypiBVT7NK4ltgbcud3+Li3H1DiAFNvaSDPumZMEbAkfGWZ6s3KtiI7TRmZwQ2yyH6mug6GhrCLD6CZJUQ2CPmhO3JYTYOgN53E6hwm/Teb9I156S04qHjLLLBxk9Mklu5X06kdhMBYwHFAZ3oByeoWUryrQC0Mv9C5ZahKzoQNuJNL2sv+ws2e5Zaj8Rid4AjhvqB6dYhWP4QM+0IiNjs/j08aRgcyOrenbQEIieU+XF6mQWF2Jfg317e0KjWnpru+uPVVgrEn9rNvQeXu2u4SZhT6rnLQzBLbJrngNcNw3gXfxxsoowIDAQAB"

const (
	appName    = "AI_AIP894_Visionlab_Android"
	bundleID   = "com.ai.art.aiimagegenerator.aivideogenerator.aiphoto.aiart"
	appVersion = "1.1.0"
)

var (
	pubKey *rsa.PublicKey
	skewMs atomic.Int64 // 服务端时间 - 本地时间，由 /timestamp 校准
	inited bool
)

func initPubKey() error {
	if inited {
		return nil
	}
	der, err := base64.StdEncoding.DecodeString(apPublicKeyB64)
	if err != nil {
		return err
	}
	k, err := x509.ParsePKIXPublicKey(der)
	if err != nil {
		return err
	}
	pk, ok := k.(*rsa.PublicKey)
	if !ok {
		return fmt.Errorf("kreivo: public key is not RSA")
	}
	pubKey = pk
	inited = true
	return nil
}

// signHeaders 生成 Apero 六件套头。apiKey 为渠道 key。
func signHeaders(apiKey string) (map[string]string, error) {
	if err := initPubKey(); err != nil {
		return nil, err
	}
	ts := strconv.FormatInt(time.Now().UnixMilli()+skewMs.Load(), 10)
	n, err := rand.Int(rand.Reader, big.NewInt(1_000_000))
	if err != nil {
		return nil, err
	}
	raw := ts + "@@@" + apiKey + "@@@" + n.String()
	enc, err := rsa.EncryptPKCS1v15(rand.Reader, pubKey, []byte(raw)) // == RSA/None/PKCS1Padding
	if err != nil {
		return nil, err
	}
	return map[string]string{
		"x-api-signature": base64.StdEncoding.EncodeToString(enc),
		"x-api-timestamp": ts,
		"x-api-keyid":     apiKey,
		"x-api-token":     "not_get_api_token",
		"x-api-bundleId":  bundleID,
		"App-name":        appName,
		"App-version":     appVersion,
		"Country-code":    "US",
		"device":          "android",
		"Accept":          "application/json",
		"User-Agent":      "okhttp/4.12.0",
	}, nil
}

// syncTime 用上游 /timestamp 校准偏移。启动时 + 每 10 分钟调用一次。
func syncTime(baseURL, apiKey string) error {
	h, err := signHeaders(apiKey)
	if err != nil {
		return err
	}
	req, _ := http.NewRequest(http.MethodGet, strings.TrimRight(baseURL, "/")+"/timestamp", nil)
	for k, v := range h {
		req.Header.Set(k, v)
	}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	var out struct {
		Data struct {
			Timestamp int64 `json:"timestamp"`
		} `json:"data"`
	}
	if err := common.DecodeJson(resp.Body, &out); err != nil {
		return err
	}
	if out.Data.Timestamp > 0 {
		skewMs.Store(out.Data.Timestamp - time.Now().UnixMilli())
	}
	return nil
}
```

### 4.2 `image.go` —— 上传 + 图生图

```go
type presigned struct {
	URL  string `json:"url"`
	Path string `json:"path"`
}

// upload 走 presign -> S3 PUT，返回 path（不是 url）。
func upload(baseURL, svcPath, apiKey string, img []byte, contentType string) (string, error) {
	h, err := signHeaders(apiKey)
	if err != nil {
		return "", err
	}
	req, _ := http.NewRequest(http.MethodGet, baseURL+svcPath+"/presigned-link", nil)
	for k, v := range h {
		req.Header.Set(k, v)
	}
	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	var pr struct {
		StatusCode int       `json:"statusCode"`
		Message    string    `json:"message"`
		Data       presigned `json:"data"`
	}
	err = common.DecodeJson(resp.Body, &pr)
	resp.Body.Close()
	if err != nil {
		return "", err
	}
	if pr.StatusCode != 200 {
		return "", fmt.Errorf("kreivo presign %d: %s", pr.StatusCode, pr.Message)
	}
	// 注意：URL 只有 120s 有效期，拿到立刻 PUT
	putReq, _ := http.NewRequest(http.MethodPut, pr.Data.URL, bytes.NewReader(img))
	putReq.Header.Set("Content-Type", contentType)
	putResp, err := client.Do(putReq)
	if err != nil {
		return "", err
	}
	putResp.Body.Close()
	if putResp.StatusCode >= 300 {
		return "", fmt.Errorf("kreivo s3 put %d", putResp.StatusCode)
	}
	return pr.Data.Path, nil
}
```

`EditImage(prompt string, img []byte)`：`upload(base_img, "/api/v5.1/qwen-editing", ...)` →
`POST {base}/api/v5.1/qwen-editing` body `{files:[path], mode:"IMAGE_EDITING", positivePrompt, positivePrompt2:""}` →
取 `data.url`。

`TextToImage(prompt string, w, h int)`：直接 `POST /api/v5/premium/text-2-image`
body `{positivePrompt, width, height}`，`width/height` 必须 ∈ [512,1024]，取 `data.url`。

### 4.3 `video.go` —— 异步（**不要阻塞同步请求**）

```go
// 提交后拿 videoID，交给任务框架轮询；或在本函数内 poll（简单但占连接）
func (a *Adaptor) ImageToVideo(img []byte, prompt, model string, w, h int) (string, error) {
	if model != "inhouse" && model != "seedance-lite" && model != "seedance-pro" {
		return "", fmt.Errorf("kreivo: model 必须是 inhouse|seedance-lite|seedance-pro")
	}
	w, h = clampDim(w), clampDim(h) // 512..1024
	path, err := upload(baseVideo, "/api/v5/image-2-video", a.apiKey, img, "image/jpeg")
	...
	body := map[string]any{
		"files": []string{path}, "mode": "i2v", "positivePrompt": prompt,
		"positivePrompt2": "", "positivePrompt3": "", "negativePrompt": "",
		"keepFace": false, "width": w, "height": h, "model": model,
		"notificationProvider": "fcm",
		"notificationId":       "fcm-" + uuid(),
	}
	// POST -> data.videoId
	// 轮询 GET /api/v5/image-2-video/video/{id}，每 4-5s 一次，最多 600s
	// 读 data.result.videoStatus（注意是小写：processing/completed/failed）
	// 完成取 data.result.resultFile
}

func clampDim(v int) int {
	if v < 512 { return 512 }
	if v > 1024 { return 1024 }
	return v
}
```

**强烈建议**：接 `relay/channel/task/` + `plugins/tasks/` 做任务型异步（提交返回 task_id，
后台 4-5s 轮询，`completed` 结算 / `failed` 全额退）。同步阻塞 60s 会被客户端超时和
`/v1` 网关 timeout 双重夹击。

### 4.4 `do_request.go` —— 错误映射（很重要）

```go
// 上游错误码语义（实测）：
//   401 + "Not active api key"  -> key 被停用，不可重试，必须立刻禁用该渠道/换 key
//   401 + 其它                  -> 签名或时间戳问题（检查 skew、公钥、nonce 格式）
//   400 + errorCode ERR16       -> 业务参数错误，把 message 透传给用户（多半有具体文案）
//   400 + "client.bad-request"  -> 上游通用壳，真实原因是缺字段，日志要打出完整 body
//   500/502/503                 -> 可重试，但注意别打爆（上游并发有限）
```

---

## 5. 模型命名与计费建议

| 对外模型名 | 上游 | 延迟 | 计费锚点 |
|---|---|---|---|
| `kreivo-image-edit` | qwen-editing | 17-24s | 按次，基准 1x |
| `kreivo-text2image` | premium/text-2-image | 5-16s | 按次，0.6x |
| `kreivo-i2v-seedance-lite` | image-2-video lite | 45-50s | 按次，3.5x |
| `kreivo-i2v-seedance-pro` | image-2-video pro | 更长 | 按次，5x |
| `kreivo-i2v-inhouse` | image-2-video inhouse | ~47s | 按次，3.5x |
| （可选）`kreivo-enhance` / `-beauty` / `-clothes` / `-fitting` / `-remove-object` / `-art-premium` / `-image-ai` | 各工具链 | 13-38s | 按次，0.5x |

---

## 6. 已知坑（照抄，别重新踩）

1. **`notificationProvider` + `notificationId` 缺一不可**，缺了只回 `400 client.bad-request`，没有字段名提示。
2. **`width/height` 必须显式给**且 ∈[512,1024]；**源图宽 > 1024 时**上游会报
   `The width must be an integer within the range of 512 to 1024`（文案说 width，实际是整图约束）→ 先缩图。
3. **`image-ai` 用单数 `file`**，传 `files:[]` → `File must be a string`。
   `mode` 枚举 `ART/FASHION/SUPER_ART/TRANSFORM/FAST_EDITING/MULTI_IMAGES/POSE_TRANSFER/VIDEO_POSE_TRANSFER/0-7/10`，
   但 `ART` 会被服务端转小写后报 `Invalid mode value: art`（上游 bug），用 `FAST_EDITING`/`TRANSFORM`。
4. **presigned URL 只有 120s**，拿到必须立刻 PUT；PUT 时**不要带签名头**。
5. **`mode` 只认 `i2v`**，传 `IMAGE_2_VIDEO` / `image_to_video` 都是 400。
6. **视频状态是小写** `processing|completed|failed`（smali 里的 `COMPLETED` 只是 Kotlin 枚举名）。
7. **`segment` 返回坐标矩阵不是图片**：`data[] = [{className,xLeft,yTop,xRight,yBottom,matrix:[{x,y}]}]`。
8. **`fitting` 需要两次 presign 两次上传**（`inputImage` + `clothImage`），`clothType ∈ upper_body|lower_body|full_body`。
9. **`remove-object` 的 `mask` 也是 presign 上传后的 path**。
10. **key 会被上游停用**：必须支持热换 + `401 Not active api key` 单独处理（别当 5xx 重试）。

---

## 7. 验收清单（每条都要有实际运行证据）

- [ ] `cd relaykit && GOWORK=off go build ./...` 通过
- [ ] 根模块 `go build ./...` + `go test ./relay/channel/kreivo/...` 通过
- [ ] 渠道连通性测试：管理面板点"测试"，返回成功
- [ ] `POST /v1/images/edits`（multipart，带真实图）→ 200 + `data[0].url` 可浏览器打开
- [ ] `POST /v1/images/generations` → 200 + 真实图 URL
- [ ] 图生视频：提交 → 轮询 → 返回 mp4 URL，`ffprobe` 能读出 24fps / 5s
- [ ] 计费：调用后额度扣减正确（对照 `TwoAPIChannelTypes` 是否已注册该类型）
- [ ] 错误路径：给错误 key → 用户拿到可读错误（不是 500 裸抛）；给超大图 → 自动缩图或明确报错
- [ ] 日志不含 apiKey 明文
- [ ] SQLite/MySQL/PostgreSQL 三库启动 + 迁移正常（若动了 model/migration；本渠道理论上不需要）

---

## 8. 回滚

本渠道是**纯新增**：常量 + 新包 + 一个 switch case。回滚 = `git revert` 单个 commit，
无需数据迁移、无需兼容处理。唯一注意：如果已经建过 type 74 的渠道记录，回滚后管理面板会
显示未知类型（不阻塞启动），下线前先删渠道。

---

## 9. 参考产物

| 文件 | 用途 |
|---|---|
| `D:/apk-analysis/kreivo110/docs/PROTOCOL.md` | 上游协议完整还原报告（含所有坑与证据） |
| `D:/apk-analysis/kreivo110/demo_server.py` | 可直接跑的 Python 参考实现（含浏览器 demo 页） |
| `D:/apk-analysis/kreivo110/sigkit.py` | 签名内核（40 行，照它翻成 Go 就行） |
| `D:/apk-analysis/kreivo110/stress_test.py` | 压测脚本（上游容量基线） |
| GitHub `lza6/Kreivo-AI-Photo-Video-2API` | 以上全部归档 |

上游容量基线（真实压测 2026-10-29）：图生图 10 并发 100% 成功 p50 23.1s **零 429**；
文生图 8 并发 100% p50 16.6s；图生视频 3 并发 100% p50 49.9s。

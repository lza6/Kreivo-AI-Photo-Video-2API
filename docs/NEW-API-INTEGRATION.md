# Kreivo → new-api 对接指南

两条落地路径，按"要不要动 Go 代码"分流。R1 只交付了**网关 + 文档**，`new-api` 侧未改动。

---

## 路线 A（零改造，立即可用）：OpenAI 兼容旁挂

`demo_server.py` 已经暴露 OpenAI 形态的接口，直接用现成渠道类型挂上：

| 项 | 值 |
|---|---|
| 渠道类型 | `1`（OpenAI）或 `58`（AdvancedCustom，推荐，便于自定义超时） |
| Base URL | `http://127.0.0.1:8977` |
| 密钥 | 任意非空串（网关内部用环境变量 `APERO_API_KEY`，不读渠道 key） |
| 模型 | `kreivo-image-edit` / `kreivo-text2image` |
| 端点 | `/v1/images/edits`（multipart）、`/v1/images/generations`（JSON） |

客户端调用：

```bash
curl -X POST http://<new-api>/v1/images/edits \
  -H "Authorization: Bearer sk-xxx" \
  -F image=@photo.jpg -F prompt="van gogh starry night"
# → {"created":...,"data":[{"url":"https://static.aperogroup.ai/…jpeg"}]}
```

**优点**：不动 Go 代码，5 分钟上线；图生图/文生图立刻能计费。
**缺点**：`image-2-video` 走不了 OpenAI 语义（没有对应端点），只能用路线 B 或直连 `/kreivo/i2v`。

---

## 路线 B（原生渠道，推荐最终形态）：新增 `ChannelTypeKreivo = 74`

当前 2API 渠道占 62–73（`constant/channel.go`，`ChannelTypeDuck = 73` 之后紧跟 `ChannelTypeDummy`），
**74 是下一个可用号**。

### B1. 常量与注册（4 个文件）

1. `constant/channel.go`
   ```go
   ChannelTypeKreivo = 74
   ```
   并在 `ChannelBaseURLs` 追加 `"https://api-img-gen-wrapper.aperogroup.ai"`，
   在渠道名映射追加 `ChannelTypeKreivo: "Kreivo"`。

2. `constant/twoapi_channel.go` — 把 `ChannelTypeKreivo` 加进 `TwoAPIChannelTypes`，
   否则计费判定 / 出站压缩豁免 / 管理面板都不会识别它（历史事故：Duck、AIVM 漏计费）。

3. `constant/api_type.go` + `common/api_type.go` — 追加 `APITypeKreivo` 与 `lnKreivo` 映射。

4. `controller/twoapi_panel.go` — 面板加一行渠道统计。

### B2. 适配器 `relay/channel/kreivo/`

照 `relay/channel/aivm/`（type 72）的结构建：`adaptor.go` / `constants.go` / `dto.go` / `image.go` / `video.go`。

必需能力：

```go
// 签名（每次请求现算）
sigHeaders(apiKey string) map[string]string {
    ts   := strconv.FormatInt(time.Now().UnixMilli()+skewMs, 10)  // skew 由 /timestamp 校准后缓存
    nonce:= strconv.FormatInt(rand.Int63n(1_000_000), 10)
    raw  := ts + "@@@" + apiKey + "@@@" + nonce
    sig  := base64.StdEncoding.WithPadding(base64.NoPadding)(
              rsa.EncryptPKCS1v15(rand.Reader, pubKey, []byte(raw)))
    return map[string]string{
        "x-api-signature": sig, "x-api-timestamp": ts, "x-api-keyid": apiKey,
        "x-api-token": "not_get_api_token", "x-api-bundleId": kreivoBundle,
        "App-name": "AI_AIP894_Visionlab_Android", "App-version": "1.1.0",
        "Country-code": "US", "device": "android",
    }
}
```

- 公钥硬编码 `assets/prod.pem` 那把 2048-bit RSA（见 `docs/PROTOCOL.md` §2），
  用 `x509.ParsePKIXPublicKey(base64.StdEncoding.DecodeString(pub))` 解析一次缓存。
  > `Base64.NO_WRAP` == 标准编码 **不带换行**（`base64.StdEncoding` 本来就不换行，不要用 URL 编码）。
- 启动时对一个业务域打 `GET /timestamp`，把 `skewMs = serverTs - time.Now().UnixMilli()` 缓存，
  定期（10 min）刷新。偏差 >30s 会被上游拒。
- 两条主链路：
  - `presigned-link` → `PUT`（`Content-Type: image/jpeg`，URL 120s 过期）→ `POST` 业务端点。
  - 视频：`POST /api/v5/image-2-video` 拿 `videoId` → 轮询 `GET /api/v5/image-2-video/video/{id}`，
    `data.result.videoStatus` ∈ `processing|completed|failed`，完成取 `data.result.resultFile`。

### B3. 任务型异步（视频）

`image-2-video` 60s 级别，不要占同步请求。用仓库既有任务框架（`relay/channel/task/` + `plugins/tasks/`）：

| 阶段 | 动作 |
|---|---|
| 提交 | 上传 + `POST /api/v5/image-2-video` → 落库 `videoId`，返回 `task_id` |
| 轮询 | 5s 间隔 `GET .../video/{videoId}`，最多 600s（服务端 `videoTimeout`） |
| 结算 | `completed` 时按次扣费；`failed` 全额退还 |

### B4. 计费建议

| 模型 | 上游成本量级 | 建议单价锚点 |
|---|---|---|
| `kreivo-image-edit`（qwen-editing） | ~18s GPU | 按次 |
| `kreivo-text2image`（flux-klein） | ~5-10s | 按次，低于 edit |
| `kreivo-i2v-seedance-lite` | 45-50s，5s/24fps 视频 | 按次，约 3-4 倍图价 |
| `kreivo-i2v-seedance-pro` / `inhouse` | 更慢 | 按次，再上浮 |

### B5. 必须防的事

1. **key 会死**：Kreivo 自己 RC 下发的 `sk-PCZX…` 已经 401 停用，现在用的是兄弟项目 Alura 的 `sk-VqJL…`。
   渠道 key 要能热换，且要做 401 `Not active api key` 的显式错误映射（不要当通用 5xx 重试，会打爆）。
2. **上游 400 细节被吞**：`client.bad-request` 是通用壳，真实原因看 `ERR16` + 请求体字段。
   见 `docs/PROTOCOL.md` §6 的踩坑表，把这些前置校验做在渠道层，别透传给用户。
3. **宽高钳制**：`width/height` 必须 ∈ [512,1024] 整数，源图超过 1024 要先缩（否则上游报 width 越界）。
4. **`notificationProvider/notificationId` 必填**（`fcm` + 随机串），漏了就是 `400 client.bad-request`。
5. **S3 presign 120s 过期**：上传要在拿到 URL 后立刻做，别缓存 URL。

---

## 本地验证记录（R1，2026-10-29）

```
demo_server.py  @ 127.0.0.1:8977   (key sk-VqJLy…fLIL, skew +1.4s)
GET  /health                      ok
GET  /                            HTML demo 页（Playwright 真浏览器跑通全流程）
GET  /kreivo/styles?kind=i2v      200（RC 直拉）
POST /v1/images/edits             200  17.8s  → static.aperogroup.ai/…jpeg
POST /v1/images/generations       200   4.6s  → …jpeg
POST /kreivo/i2v                  200  47.6s  → …mp4（h264 704×704 24fps 5.04s 6.9MB）

压测（真实并发打上游，非 mock）
image  ×6    6/6   100%  p50=21.9s p90=24.4s   ~15.0 req/min
image  ×10  10/10  100%  p50=23.1s p90=30.2s   ~19.8 req/min   零 429
t2i    ×8    8/8   100%  p50=16.6s p90=27.3s   ~17.8 req/min
video  ×3    3/3   100%  p50=49.9s p90=73.5s   ~2.8  req/min
```

R2（8 个工具链，全部真实出图，走网关 `/kreivo/service/<name>`）
enhance 13.4s / beauty 20.6s / art-premium 28.7s / segment 14.5s（返回坐标矩阵）/
clothes 19.9s / image-ai 13.5s / fitting 30.2s / remove-object 37.9s —— 8/8 成功。

浏览器路径验证（Playwright/Chromium，`shot_*.png`）：
页面加载 → 风格库 12 缩略图 → 文生图 7.8s 出图 → 上传图生图出图 → 图生视频 47.6s 出 `<video>` 播放，
console error = 0。R2 补测：`enhance` 出图、`segment` 返回 JSON，console error 仍为 0（`shot_service.png`）。

# 音频模型定价对照：OpenAI vs Azure OpenAI

> 数据抓取时间：**2026-05-25**
> 来源：[OpenAI Pricing](https://platform.openai.com/docs/pricing) · [Azure OpenAI Pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/)
> 价格随时调整，正式商务报价以官方页面/合同为准。

## 🚀 30 秒速览

| 维度 | OpenAI | Azure OpenAI |
|---|---|---|
| 旗舰实时模型 | `gpt-realtime-2`（已上线） | ❌ 尚未上线，最新为 `gpt-realtime-1.5` |
| Realtime 单价 | Audio $32 / $0.40 缓存 / $64 输出 | 同价（Global） |
| TTS 老模型 | `tts-1` / `tts-1-hd` 仍提供 | ❌ 未列出，需用 `gpt-4o-mini-tts` 或独立 Azure AI Speech |
| Whisper | $0.006 / 分钟 | 可部署，价格相同；或走 Azure AI Speech 双轨计费 |
| 区域分层 | Regional 端点 +10% | Global / Data Zone / Regional 三档，后两档 +10% |
| 长期高并发 | Priority / Scale Tier | PTU 月/年预留（Azure 独有） |
| Batch API | 音频模型多数 N/A | 同样 N/A |

> 单位说明：除注明外，价格均为 **每 1M tokens（美元）**；"Audio"指音频模态 tokens，"Text"指文本模态 tokens。Azure 以 **Global Deployment** 为基准。

---

## 一、Realtime 实时语音模型

| 模型 | OpenAI | Azure OpenAI（Global） | 备注 |
|---|---|---|---|
| **gpt-realtime-2** | Audio: $32 / $0.40 / $64<br>Text: $4 / $0.40 / $24<br>Image: $5 / $0.50 | ❌ 尚未上线 | OpenAI 最新旗舰；Azure 滞后 |
| **gpt-realtime-1.5** | Audio: $32 / $0.40 / $64<br>Text: $4 / $0.40 / $16<br>Image: $5 / $0.50 | 同价 | ✅ |
| **gpt-realtime** | Audio: $32 / $0.40 / $64<br>Text: $4 / $0.40 / $16 | 同价 | ✅ |
| **gpt-realtime-mini** | Audio: $10 / $0.30 / $20<br>Text: $0.60 / $0.06 / $2.40 | `gpt-realtime-mini-2025-12-15`，同价 | ✅ |
| **gpt-realtime-translate** | Audio: $0.034 / 分钟 | ❌ 尚未上线 | 实时翻译专用 |
| **gpt-realtime-whisper** | Audio: $0.017 / 分钟 | ❌ 尚未上线 | 实时转写 |
| **gpt-4o-realtime-preview** | Audio: $40 / $2.50 / $80<br>Text: $5 / $2.50 / $20 | 同价（Data Zone/Regional +10%） | 旧版预览 |
| **gpt-4o-mini-realtime-preview** | Audio: $10 / $0.30 / $20<br>Text: $0.60 / $0.30 / $2.40 | 同价 | ✅ |

> 价格列格式：`输入 / 缓存输入 / 输出`

## 二、Audio（Chat Completions 音频）模型

| 模型 | OpenAI | Azure OpenAI | 备注 |
|---|---|---|---|
| **gpt-audio-1.5** | Audio: $32 / $64<br>Text: $2.50 / $10 | 同价 | ✅ |
| **gpt-audio** | Audio: $32 / $64<br>Text: $2.50 / $10 | Audio: **$40 / $80**<br>Text: $2.50 / $10 | ⚠️ Azure 偏高；优先用 `gpt-audio-1.5` |
| **gpt-audio-mini** | Audio: $10 / $20<br>Text: $0.60 / $2.40 | `gpt-audio-mini-2025-12-15`，同价 | ✅ |
| **gpt-4o-audio-preview** | Audio: $40 / $80<br>Text: $2.50 / $10 | 同价 | ✅ |
| **gpt-4o-mini-audio-preview** | Audio: $10 / $20<br>Text: $0.15 / $0.60 | 同价 | ✅ |

## 三、TTS 文本转语音

| 模型 | OpenAI | Azure OpenAI | 备注 |
|---|---|---|---|
| **gpt-4o-mini-tts** | Audio 输出: $12<br>Text 输入: $0.60 | 同价 | ✅ |
| **tts-1** | $15 / 1M 字符 | ❌ 未列出 | 用 `gpt-4o-mini-tts` 或 Azure AI Speech |
| **tts-1-hd** | $30 / 1M 字符 | ❌ 未列出 | 同上 |

## 四、STT / 转录模型

| 模型 | OpenAI | Azure OpenAI | 备注 |
|---|---|---|---|
| **gpt-4o-transcribe** | Text in: $2.50 / out: $10<br>Audio in: $6（≈$0.006/分钟） | 同价 | ✅ |
| **gpt-4o-transcribe-diarize** | Text: $2.50 / $10<br>Audio in: $6 | 同价 | ✅ 含说话人分离 |
| **gpt-4o-mini-transcribe** | Text: $1.25 / $5<br>Audio in: $3（≈$0.003/分钟） | `gpt-4o-mini-transcribe-2025-12-15`，同价 | ✅ |
| **whisper-1** | $0.006 / 分钟（$0.36/小时） | 同价；亦可走 Azure AI Speech（独立计费） | 老模型 |

---

## ⚠️ 迁移坑点（Pitfalls）

1. **新模型上线滞后**：`gpt-realtime-2`、`gpt-realtime-translate`、`gpt-realtime-whisper` 已在 OpenAI 上线但 Azure 未提供。需要这些能力的场景**暂不能迁移**或必须接受降级到 `1.5` 系列。

2. **`gpt-audio` 同名不同价**：Azure 上 `gpt-audio` 按 $40/$80 计费（与 `gpt-4o-audio-preview` 对齐），而 OpenAI 是 $32/$64。**迁移时显式指定 `gpt-audio-1.5`** 才能拿到一致单价。

3. **TTS 老模型缺失**：`tts-1`、`tts-1-hd` 在 Azure OpenAI 完全不可用。两种迁移路径：
   - 改用 `gpt-4o-mini-tts`（token 计费，质量更好，需调整接入代码）
   - 接 **Azure AI Speech**（独立服务，按字符/小时计费，不在 Azure OpenAI 配额内）

4. **Whisper 双轨**：Azure 上有两套转录：
   - **Azure OpenAI Whisper**：按分钟计费，与 OpenAI 一致；走 OpenAI SDK
   - **Azure AI Speech**：批量/实时双计费模式，不同 SDK，配额独立

5. **区域分层 +10%**：Azure 的 Data Zone（US/EU）和 Regional 部署比 Global 贵约 10%。如 `gpt-4o-realtime-preview` Audio 输入 Global=$40，Regional=$44。中国合规场景常被迫选 Regional，**报价务必按目标区域算**。

6. **PTU 折扣**：Azure 提供 PTU 月/年预留，对持续高并发场景比 PAYG 划算（≈30-50% off）；OpenAI 对应能力为 Priority Tier，对外公开折扣较少。

7. **配额单位差异**：Realtime 模型 Azure 按 **session × 分钟 + token** 综合计费，OpenAI 按纯 token；并发数限制各自独立，需分别申请。

---

## 📎 参考链接

- [OpenAI 官方定价](https://platform.openai.com/docs/pricing)
- [Azure OpenAI 官方定价](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/)
- [Azure AI Speech 定价](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/speech-services/)
- [OpenAI Realtime API 文档](https://platform.openai.com/docs/guides/realtime)
- [Azure OpenAI Realtime API 文档](https://learn.microsoft.com/azure/ai-services/openai/realtime-audio-quickstart)

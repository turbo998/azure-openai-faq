# Audio Model Pricing: OpenAI vs Azure OpenAI

> Snapshot date: **2026-05-25**
> Sources: [OpenAI Pricing](https://platform.openai.com/docs/pricing) · [Azure OpenAI Pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/)
> Prices change frequently. Treat the official pages / your contract as authoritative.

## 🚀 30-Second Overview

| Dimension | OpenAI | Azure OpenAI |
|---|---|---|
| Flagship realtime model | `gpt-realtime-2` (live) | ❌ Not yet; latest is `gpt-realtime-1.5` |
| Realtime price | Audio $32 / $0.40 cached / $64 out | Same (Global) |
| Legacy TTS | `tts-1` / `tts-1-hd` available | ❌ Not listed — use `gpt-4o-mini-tts` or Azure AI Speech |
| Whisper | $0.006 / min | Same; or Azure AI Speech (separate billing) |
| Regional tiering | Regional endpoints +10% | Global / Data Zone / Regional, latter two +10% |
| Long-term high concurrency | Priority / Scale Tier | PTU monthly/yearly reservations (Azure only) |
| Batch API | Mostly N/A on audio | Also N/A |

> Unit: per **1M tokens (USD)** unless noted. "Audio" = audio-modality tokens, "Text" = text tokens. Azure column = **Global Deployment** baseline.

---

## 1. Realtime Models

| Model | OpenAI | Azure OpenAI (Global) | Notes |
|---|---|---|---|
| **gpt-realtime-2** | Audio: $32 / $0.40 / $64<br>Text: $4 / $0.40 / $24<br>Image: $5 / $0.50 | ❌ Not yet | Latest flagship; Azure lags |
| **gpt-realtime-1.5** | Audio: $32 / $0.40 / $64<br>Text: $4 / $0.40 / $16<br>Image: $5 / $0.50 | Same | ✅ |
| **gpt-realtime** | Audio: $32 / $0.40 / $64<br>Text: $4 / $0.40 / $16 | Same | ✅ |
| **gpt-realtime-mini** | Audio: $10 / $0.30 / $20<br>Text: $0.60 / $0.06 / $2.40 | `gpt-realtime-mini-2025-12-15`, same | ✅ |
| **gpt-realtime-translate** | Audio: $0.034 / min | ❌ Not yet | Realtime translation |
| **gpt-realtime-whisper** | Audio: $0.017 / min | ❌ Not yet | Realtime transcription |
| **gpt-4o-realtime-preview** | Audio: $40 / $2.50 / $80<br>Text: $5 / $2.50 / $20 | Same (Data Zone/Regional +10%) | Legacy preview |
| **gpt-4o-mini-realtime-preview** | Audio: $10 / $0.30 / $20<br>Text: $0.60 / $0.30 / $2.40 | Same | ✅ |

> Format: `input / cached input / output`

## 2. Audio (Chat Completions) Models

| Model | OpenAI | Azure OpenAI | Notes |
|---|---|---|---|
| **gpt-audio-1.5** | Audio: $32 / $64<br>Text: $2.50 / $10 | Same | ✅ |
| **gpt-audio** | Audio: $32 / $64<br>Text: $2.50 / $10 | Audio: **$40 / $80**<br>Text: $2.50 / $10 | ⚠️ Azure higher; prefer `gpt-audio-1.5` |
| **gpt-audio-mini** | Audio: $10 / $20<br>Text: $0.60 / $2.40 | `gpt-audio-mini-2025-12-15`, same | ✅ |
| **gpt-4o-audio-preview** | Audio: $40 / $80<br>Text: $2.50 / $10 | Same | ✅ |
| **gpt-4o-mini-audio-preview** | Audio: $10 / $20<br>Text: $0.15 / $0.60 | Same | ✅ |

## 3. TTS

| Model | OpenAI | Azure OpenAI | Notes |
|---|---|---|---|
| **gpt-4o-mini-tts** | Audio out: $12<br>Text in: $0.60 | Same | ✅ |
| **tts-1** | $15 / 1M chars | ❌ Not listed | Use `gpt-4o-mini-tts` or Azure AI Speech |
| **tts-1-hd** | $30 / 1M chars | ❌ Not listed | Same |

## 4. STT / Transcription

| Model | OpenAI | Azure OpenAI | Notes |
|---|---|---|---|
| **gpt-4o-transcribe** | Text in: $2.50 / out: $10<br>Audio in: $6 (≈$0.006/min) | Same | ✅ |
| **gpt-4o-transcribe-diarize** | Text: $2.50 / $10<br>Audio in: $6 | Same | ✅ With speaker diarization |
| **gpt-4o-mini-transcribe** | Text: $1.25 / $5<br>Audio in: $3 (≈$0.003/min) | `gpt-4o-mini-transcribe-2025-12-15`, same | ✅ |
| **whisper-1** | $0.006 / min ($0.36/hr) | Same; also Azure AI Speech (separate billing) | Legacy |

---

## ⚠️ Migration Pitfalls

1. **New-model lag**: `gpt-realtime-2`, `gpt-realtime-translate`, `gpt-realtime-whisper` are live on OpenAI but not on Azure. Workloads needing them **cannot migrate** yet or must downgrade to the `1.5` family.

2. **Same name, different price for `gpt-audio`**: Azure bills `gpt-audio` at $40/$80 (aligned with `gpt-4o-audio-preview`), while OpenAI is $32/$64. **Explicitly target `gpt-audio-1.5`** on Azure to get parity pricing.

3. **No legacy TTS on Azure**: `tts-1` and `tts-1-hd` are absent. Two migration paths:
   - Switch to `gpt-4o-mini-tts` (token billing, better quality, requires SDK changes)
   - Use **Azure AI Speech** (separate service, char/hour billing, not under Azure OpenAI quota)

4. **Whisper dual-track on Azure**:
   - **Azure OpenAI Whisper**: per-minute billing, identical to OpenAI; OpenAI SDK compatible
   - **Azure AI Speech**: batch + realtime billing modes, different SDK, independent quota

5. **Regional +10%**: Azure's Data Zone (US/EU) and Regional deployments are ~10% more than Global. e.g., `gpt-4o-realtime-preview` Audio input is $40 (Global) / $44 (Regional). China-compliance scenarios are often forced to Regional — **quote against the target region**.

6. **PTU discount**: Azure offers monthly/yearly PTU reservations, often 30-50% cheaper than PAYG for sustained high concurrency. OpenAI's equivalent is Priority Tier with less public discount.

7. **Quota unit differences**: Realtime on Azure is billed as **session × minutes + tokens** combined, OpenAI is pure tokens. Concurrency limits are tracked separately on each platform and must be requested individually.

---

## 📎 References

- [OpenAI Pricing](https://platform.openai.com/docs/pricing)
- [Azure OpenAI Pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/)
- [Azure AI Speech Pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/speech-services/)
- [OpenAI Realtime API docs](https://platform.openai.com/docs/guides/realtime)
- [Azure OpenAI Realtime API docs](https://learn.microsoft.com/azure/ai-services/openai/realtime-audio-quickstart)

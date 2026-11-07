# Phase 4 AI Chat and Voice Notes

## Added
- Trading-focused AI chat endpoint at POST /api/ai/chat using the OpenAI Responses API.
- Secure server-side OPENAI_API_KEY configuration; no browser exposure and no key committed.
- Verified market snapshot is included when available; the assistant is instructed never to invent prices, candles, news, or test results.
- PNG/JPEG/WebP chart-image upload (up to 4 MB) for visual chart discussion.
- Browser speech recognition for voice input where supported, and device speech synthesis for spoken answers.
- AI status is exposed at /api/dashboard/status.
- AI chat interface added to the mobile dashboard.

## Configuration
Set OPENAI_API_KEY and optionally OPENAI_MODEL in the server/deployment environment. The .env.example contains empty placeholders only. GitHub Actions secrets do not automatically configure a deployed web app; add the key to the hosting provider's environment-variable settings when deployed.

## Limitations
- No API key is present by default, so chat returns a clear setup message until configured.
- Voice input depends on browser support and microphone permission; spoken output depends on installed device voices.
- Chart image analysis is visual and may not reliably identify exact prices or timeframe if labels are unclear.
- The current dashboard market provider is still OANDA; Twelve Data integration remains a separate pending task.
- Candlestick chart rendering, automated chart signal generation, news integration, and calibrated model confidence are not implemented by this change.
- No order placement or live execution. LIVE_TRADING remains false.

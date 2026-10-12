# 🧠 Jarvis LLM & Voice Microservice

A backend service built with **Flask**, **LangChain**, **Google Generative AI (`gemini-2.5-flash-lite`)**, and **pyttsx3** that handles LLM reasoning, text-to-speech feedback, rate-limiting, and daily usage tracking for Jarvis.

---

## ✨ Features

* **Multi-modal LLM Integration**: Powered by LangChain and Google's Gemini models for structured JSON output, raw text generation, and base64-encoded file/media processing.
* **Blocking Rate Limiter**: Thread-safe custom rate limiter ensuring calls respect strict minimum gaps and maximum thresholds.
* **Voice Synthesis Engine (`pyttsx3`)**: Asynchronous text-to-speech speaker for local audio feedback.
* **Daily Usage Tracking**: Automatically tracks and persists daily LLM invocation counts with milestone warning alerts.
* **REST API Endpoints**:
* `POST /invoke`: Executes LLM requests with built-in rate-limiting and usage counters.
* `POST /say`: Triggers local speech synthesis for custom text messages.
* `GET /health`: Simple service health check endpoint.



---

## 🛠️ Core Architecture Components

| Component | Description |
| --- | --- |
| `LLMModule` | Manages LangChain interfaces for structured JSON parsing, text responses, and multi-modal message handling. |
| `BlockingRateLimiter` | Manages concurrent call rates with thread locks and sliding time windows. |
| `Utterance` | Runs a background thread-safe text-to-speech loop using `pyttsx3`. |
| `DailyUsageTracker` | JSON-backed state manager to keep track of daily API consumption and warn when thresholds are approached. |

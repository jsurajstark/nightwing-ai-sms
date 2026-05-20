from sms_demo.config import Settings
from sms_demo.llm.anthropic_provider import AnthropicProvider
from sms_demo.llm.base import LLMProvider
from sms_demo.llm.bedrock_provider import BedrockProvider
from sms_demo.llm.gemini_provider import GeminiProvider
from sms_demo.llm.github_models_provider import GitHubModelsProvider
from sms_demo.llm.ollama_provider import OllamaProvider


def get_provider(settings: Settings) -> LLMProvider:
    p = (settings.llm_provider or "ollama").lower().strip()
    if p == "ollama":
        return OllamaProvider(
            settings.ollama_host,
            settings.ollama_model,
            timeout_s=settings.llm_timeout_s,
        )
    if p == "gemini":
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required when LLM_PROVIDER=gemini")
        return GeminiProvider(
            settings.google_api_key,
            settings.gemini_model,
            timeout_s=settings.llm_timeout_s,
        )
    if p in ("github", "github_models"):
        api_key = settings.resolved_github_models_api_key
        if not api_key:
            raise ValueError(
                "GITHUB_MODELS_API_KEY (or GITHUB_MODELS_TOKEN) is required when "
                "LLM_PROVIDER=github — create a PAT with the `models` scope (fine-grained: "
                "Models → Read) at https://github.com/settings/tokens"
            )
        return GitHubModelsProvider(
            api_key,
            settings.github_models_model,
            timeout_s=settings.llm_timeout_s,
            max_tokens=settings.llm_max_tokens,
            chat_url=settings.resolved_github_models_chat_url,
            api_version=settings.github_models_api_version,
        )
    if p == "anthropic":
        return AnthropicProvider()
    if p == "bedrock":
        return BedrockProvider()
    raise ValueError(
        f"Unknown LLM_PROVIDER: {settings.llm_provider!r}; "
        "use ollama|gemini|github|anthropic|bedrock"
    )

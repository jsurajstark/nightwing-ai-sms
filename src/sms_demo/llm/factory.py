from sms_demo.config import Settings
from sms_demo.llm.anthropic_provider import AnthropicProvider
from sms_demo.llm.base import LLMProvider
from sms_demo.llm.bedrock_provider import BedrockProvider
from sms_demo.llm.gemini_provider import GeminiProvider
from sms_demo.llm.github_provider import GitHubModelsProvider
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
    if p == "github":
        if not settings.github_models_api_key:
            raise ValueError(
                "GITHUB_MODELS_API_KEY is required when LLM_PROVIDER=github"
            )
        return GitHubModelsProvider(
            settings.github_models_api_key,
            settings.github_models_model,
            base_url=settings.github_models_base_url,
            api_version=settings.github_models_api_version,
            org=settings.github_models_org,
            fallback_models=settings.github_models_model_chain[1:],
            timeout_s=settings.llm_timeout_s,
            max_retries=settings.github_models_max_retries,
            retry_base_s=settings.github_models_retry_base_s,
        )
    if p == "anthropic":
        return AnthropicProvider()
    if p == "bedrock":
        return BedrockProvider()
    raise ValueError(
        f"Unknown LLM_PROVIDER: {settings.llm_provider!r}; "
        "use ollama|gemini|github|anthropic|bedrock"
    )

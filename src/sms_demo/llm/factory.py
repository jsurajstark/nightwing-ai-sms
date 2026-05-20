from sms_demo.config import Settings
from sms_demo.llm.anthropic_provider import AnthropicProvider
from sms_demo.llm.base import LLMProvider
from sms_demo.llm.bedrock_provider import BedrockProvider
from sms_demo.llm.gemini_provider import GeminiProvider
from sms_demo.llm.github_provider import GitHubModelsProvider
from sms_demo.llm.ollama_provider import OllamaProvider
from sms_demo.llm.openrouter_provider import OpenRouterProvider


def get_provider(settings: Settings) -> LLMProvider:
    p = (settings.llm_provider or "ollama").lower().strip()
    if p == "ollama":
        if not settings.ollama_model:
            raise ValueError("OLLAMA_MODEL is required in .env when LLM_PROVIDER=ollama")
        return OllamaProvider(
            settings.ollama_host,
            settings.ollama_model,
            timeout_s=settings.llm_timeout_s,
        )
    if p == "gemini":
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required when LLM_PROVIDER=gemini")
        if not settings.gemini_model:
            raise ValueError("GEMINI_MODEL is required in .env when LLM_PROVIDER=gemini")
        return GeminiProvider(
            settings.google_api_key,
            settings.gemini_model,
            timeout_s=settings.llm_timeout_s,
        )
    if p == "openrouter":
        if not settings.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is required when LLM_PROVIDER=openrouter")
        if not settings.openrouter_model:
            raise ValueError("OPENROUTER_MODEL is required in .env when LLM_PROVIDER=openrouter")
        if not settings.openrouter_base_url:
            raise ValueError("OPENROUTER_BASE_URL is required in .env when LLM_PROVIDER=openrouter")
        chain = settings.openrouter_model_chain
        return OpenRouterProvider(
            settings.openrouter_api_key,
            chain[0],
            fallback_models=chain[1:],
            base_url=settings.openrouter_base_url,
            timeout_s=settings.llm_timeout_s,
            max_retries=settings.openrouter_max_retries,
            retry_base_s=settings.openrouter_retry_base_s,
            http_referer=settings.openrouter_http_referer,
            app_title=settings.openrouter_app_title,
        )
    if p == "github":
        if not settings.github_models_api_key:
            raise ValueError("GITHUB_MODELS_API_KEY is required when LLM_PROVIDER=github")
        if not settings.github_models_model:
            raise ValueError("GITHUB_MODELS_MODEL is required in .env when LLM_PROVIDER=github")
        if not settings.github_models_base_url:
            raise ValueError("GITHUB_MODELS_BASE_URL is required in .env when LLM_PROVIDER=github")
        if not settings.github_models_api_version:
            raise ValueError(
                "GITHUB_MODELS_API_VERSION is required in .env when LLM_PROVIDER=github"
            )
        chain = settings.github_models_model_chain
        return GitHubModelsProvider(
            settings.github_models_api_key,
            chain[0],
            base_url=settings.github_models_base_url,
            api_version=settings.github_models_api_version,
            org=settings.github_models_org,
            fallback_models=chain[1:],
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
        "use ollama|gemini|openrouter|github|anthropic|bedrock"
    )

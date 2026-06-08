from datetime import UTC, datetime

DEMO_COST_ELEVATION_MULTIPLIER = 1000

# GCP base rates use Gemini 2.0 Flash tokens, Vertex AI grounding requests,
# and Cloud Run request-based active CPU/memory pricing.
GCP_INPUT_COST_PER_1K = 0.00015
GCP_OUTPUT_COST_PER_1K = 0.00060
GCP_API_CALL_COST_PER_1K = 2.50
GCP_COMPUTE_VCPU_COST_PER_SECOND = 0.000024
GCP_COMPUTE_MEMORY_GIB_COST_PER_SECOND = 0.0000025

LOCAL_DEMO_INPUT_COST_PER_1K = (
    GCP_INPUT_COST_PER_1K * DEMO_COST_ELEVATION_MULTIPLIER
)
LOCAL_DEMO_OUTPUT_COST_PER_1K = (
    GCP_OUTPUT_COST_PER_1K * DEMO_COST_ELEVATION_MULTIPLIER
)
LOCAL_DEMO_API_CALL_COST_PER_1K = (
    GCP_API_CALL_COST_PER_1K * DEMO_COST_ELEVATION_MULTIPLIER
)
LOCAL_DEMO_COMPUTE_VCPU_COST_PER_SECOND = (
    GCP_COMPUTE_VCPU_COST_PER_SECOND * DEMO_COST_ELEVATION_MULTIPLIER
)
LOCAL_DEMO_COMPUTE_MEMORY_GIB_COST_PER_SECOND = (
    GCP_COMPUTE_MEMORY_GIB_COST_PER_SECOND * DEMO_COST_ELEVATION_MULTIPLIER
)

LOCAL_INPUT_COST_PER_1K = LOCAL_DEMO_INPUT_COST_PER_1K
LOCAL_OUTPUT_COST_PER_1K = LOCAL_DEMO_OUTPUT_COST_PER_1K
LOCAL_API_CALL_COST_PER_1K = LOCAL_DEMO_API_CALL_COST_PER_1K
LOCAL_COMPUTE_VCPU_COST_PER_SECOND = LOCAL_DEMO_COMPUTE_VCPU_COST_PER_SECOND
LOCAL_COMPUTE_MEMORY_GIB_COST_PER_SECOND = LOCAL_DEMO_COMPUTE_MEMORY_GIB_COST_PER_SECOND


def _local_pricing_fields() -> dict[str, float]:
    return {
        "input_cost_per_1k": LOCAL_INPUT_COST_PER_1K,
        "output_cost_per_1k": LOCAL_OUTPUT_COST_PER_1K,
        "api_call_cost_per_1k": LOCAL_API_CALL_COST_PER_1K,
        "compute_vcpu_cost_per_second": LOCAL_COMPUTE_VCPU_COST_PER_SECOND,
        "compute_memory_gib_cost_per_second": LOCAL_COMPUTE_MEMORY_GIB_COST_PER_SECOND,
    }


def _gcp_operational_pricing_fields() -> dict[str, float]:
    return {
        "api_call_cost_per_1k": GCP_API_CALL_COST_PER_1K,
        "compute_vcpu_cost_per_second": GCP_COMPUTE_VCPU_COST_PER_SECOND,
        "compute_memory_gib_cost_per_second": GCP_COMPUTE_MEMORY_GIB_COST_PER_SECOND,
    }


MODEL_PRICING = [
    {
        "id": "price-ollama-llama32-3b",
        "provider": "ollama",
        "model_name": "llama3.2:3b",
        **_local_pricing_fields(),
        "effective_from": datetime.now(UTC),
        "effective_to": None,
    },
    {
        "id": "price-ollama-llama32-latest",
        "provider": "ollama",
        "model_name": "llama3.2:latest",
        **_local_pricing_fields(),
        "effective_from": datetime.now(UTC),
        "effective_to": None,
    },
    {
        "id": "price-ollama-llama31-8b",
        "provider": "ollama",
        "model_name": "llama3.1:8b",
        **_local_pricing_fields(),
        "effective_from": datetime.now(UTC),
        "effective_to": None,
    },
    {
        "id": "price-ollama-llama31-latest",
        "provider": "ollama",
        "model_name": "llama3.1:latest",
        **_local_pricing_fields(),
        "effective_from": datetime.now(UTC),
        "effective_to": None,
    },
    {
        "id": "price-groq-llama33-70b",
        "provider": "groq",
        "model_name": "llama-3.3-70b-versatile",
        "input_cost_per_1k": 0.00059,
        "output_cost_per_1k": 0.00079,
        **_gcp_operational_pricing_fields(),
        "effective_from": datetime.now(UTC),
        "effective_to": None,
    },
    {
        "id": "price-gemini-20-flash",
        "provider": "gemini",
        "model_name": "gemini-2.0-flash",
        "input_cost_per_1k": GCP_INPUT_COST_PER_1K,
        "output_cost_per_1k": GCP_OUTPUT_COST_PER_1K,
        **_gcp_operational_pricing_fields(),
        "effective_from": datetime.now(UTC),
        "effective_to": None,
    },
]

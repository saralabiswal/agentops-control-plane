from datetime import UTC, datetime

GCP_INPUT_COST_PER_1K = 0.0001
GCP_OUTPUT_COST_PER_1K = 0.0004

LOCAL_DEMO_INPUT_COST_PER_1K = 0.15
LOCAL_DEMO_OUTPUT_COST_PER_1K = 0.60

LOCAL_INPUT_COST_PER_1K = LOCAL_DEMO_INPUT_COST_PER_1K
LOCAL_OUTPUT_COST_PER_1K = LOCAL_DEMO_OUTPUT_COST_PER_1K

MODEL_PRICING = [
    {
        "id": "price-ollama-llama32-3b",
        "provider": "ollama",
        "model_name": "llama3.2:3b",
        "input_cost_per_1k": LOCAL_INPUT_COST_PER_1K,
        "output_cost_per_1k": LOCAL_OUTPUT_COST_PER_1K,
        "effective_from": datetime.now(UTC),
        "effective_to": None,
    },
    {
        "id": "price-ollama-llama32-latest",
        "provider": "ollama",
        "model_name": "llama3.2:latest",
        "input_cost_per_1k": LOCAL_INPUT_COST_PER_1K,
        "output_cost_per_1k": LOCAL_OUTPUT_COST_PER_1K,
        "effective_from": datetime.now(UTC),
        "effective_to": None,
    },
    {
        "id": "price-ollama-llama31-8b",
        "provider": "ollama",
        "model_name": "llama3.1:8b",
        "input_cost_per_1k": LOCAL_INPUT_COST_PER_1K,
        "output_cost_per_1k": LOCAL_OUTPUT_COST_PER_1K,
        "effective_from": datetime.now(UTC),
        "effective_to": None,
    },
    {
        "id": "price-ollama-llama31-latest",
        "provider": "ollama",
        "model_name": "llama3.1:latest",
        "input_cost_per_1k": LOCAL_INPUT_COST_PER_1K,
        "output_cost_per_1k": LOCAL_OUTPUT_COST_PER_1K,
        "effective_from": datetime.now(UTC),
        "effective_to": None,
    },
    {
        "id": "price-groq-llama33-70b",
        "provider": "groq",
        "model_name": "llama-3.3-70b-versatile",
        "input_cost_per_1k": 0.00059,
        "output_cost_per_1k": 0.00079,
        "effective_from": datetime.now(UTC),
        "effective_to": None,
    },
    {
        "id": "price-gemini-20-flash",
        "provider": "gemini",
        "model_name": "gemini-2.0-flash",
        "input_cost_per_1k": GCP_INPUT_COST_PER_1K,
        "output_cost_per_1k": GCP_OUTPUT_COST_PER_1K,
        "effective_from": datetime.now(UTC),
        "effective_to": None,
    },
]

import gc
import sys

_MODEL_PATH = "mlx-community/Llama-3.2-1B-Instruct-4bit"
_model = None
_tokenizer = None

def get_model():
    global _model, _tokenizer
    if sys.platform != "darwin":
        return None, None
        
    try:
        from mlx_lm import load
        if _model is None:
            print(f"Loading local LLM ({_MODEL_PATH})...")
            _model, _tokenizer = load(_MODEL_PATH)
        return _model, _tokenizer
    except ImportError:
        return None, None

def process_text_with_llm(raw_text: str, system_prompt: str, show_progress: bool = False) -> str:
    if not raw_text.strip() or not system_prompt.strip():
        return raw_text

    model, tokenizer = get_model()
    if model is None or tokenizer is None:
        # Graceful fallback for Windows or missing MLX
        print("Local LLM not available on this platform. Returning raw text.")
        return raw_text

    try:
        from mlx_lm import generate
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": raw_text}
        ]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        response = generate(
            model,
            tokenizer,
            prompt=prompt,
            max_tokens=1024,
            verbose=show_progress,
            temp=0.3
        )
        return response.strip()
    except ImportError:
        return raw_text

def unload_model():
    """Unload the LLM from memory if needed."""
    global _model, _tokenizer
    _model = None
    _tokenizer = None
    gc.collect()

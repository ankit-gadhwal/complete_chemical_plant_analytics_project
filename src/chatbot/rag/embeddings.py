import os
import time
import logging
import httpx
from src.config import Config

logger = logging.getLogger(__name__)


class EmbeddingsService:
    """
    Multi-Provider Cloud Embedding Service (0 MB Server RAM, Free-Tier Friendly).
    
    Automatically selects the active provider based on configured environment variables:
      1. Hugging Face Inference API (HF_TOKEN / HUGGINGFACEHUB_API_TOKEN)
      2. NVIDIA NIM API (NVIDIA_API_KEY)
      3. Jina AI API (JINA_API_KEY)
      4. Google Gemini API (GOOGLE_API_KEY)
    """

    def __init__(self):
        self.hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")
        self.nvidia_key = os.getenv("NVIDIA_API_KEY")
        self.jina_key = os.getenv("JINA_API_KEY")
        self.google_key = Config.GOOGLE_API_KEY

    # -------------------------------------------------------------------------
    # 1. Hugging Face Serverless Inference API
    # -------------------------------------------------------------------------
    def _embed_hf(self, texts: list[str]) -> list[list[float]]:
        model_id = os.getenv("HF_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        url = f"https://router.huggingface.co/hf-inference/models/{model_id}/pipeline/feature-extraction"
        headers = {
            "Authorization": f"Bearer {self.hf_token}",
            "Content-Type": "application/json",
        }
        
        # Hugging Face accepts up to 32 items per call
        batch_size = 32
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            payload = {"inputs": batch, "options": {"wait_for_model": True}}
            
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    raise RuntimeError(f"Hugging Face API Error ({resp.status_code}): {resp.text}")
                data = resp.json()
                # data is a list of float lists
                all_embeddings.extend(data)

        return all_embeddings

    # -------------------------------------------------------------------------
    # 2. NVIDIA NIM API (OpenAI Compatible)
    # -------------------------------------------------------------------------
    def _embed_nvidia(self, texts: list[str], input_type: str = "passage") -> list[list[float]]:
        model_id = os.getenv("NVIDIA_EMBEDDING_MODEL", "nvidia/nemotron-3-embed-1b")
        if not model_id.startswith("nvidia/") and not model_id.startswith("snowflake/") and not model_id.startswith("baai/"):
            model_id = f"nvidia/{model_id}"
        url = "https://integrate.api.nvidia.com/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {self.nvidia_key}",
            "Content-Type": "application/json",
        }

        batch_size = 50
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            payload = {
                "input": batch,
                "model": model_id,
                "input_type": input_type,
                "encoding_format": "float",
                "truncate": "END",
            }
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    raise RuntimeError(f"NVIDIA API Error ({resp.status_code}): {resp.text}")
                data = resp.json()
                embeddings = [item["embedding"] for item in data["data"]]
                all_embeddings.extend(embeddings)

        return all_embeddings

    # -------------------------------------------------------------------------
    # 3. Jina AI API (10M Free Tokens)
    # -------------------------------------------------------------------------
    def _embed_jina(self, texts: list[str]) -> list[list[float]]:
        url = "https://api.jina.ai/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {self.jina_key}",
            "Content-Type": "application/json",
        }
        batch_size = 50
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            payload = {
                "model": "jina-embeddings-v3",
                "task": "retrieval.passage",
                "input": batch,
            }
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    raise RuntimeError(f"Jina API Error ({resp.status_code}): {resp.text}")
                data = resp.json()
                embeddings = [item["embedding"] for item in data["data"]]
                all_embeddings.extend(embeddings)

        return all_embeddings

    # -------------------------------------------------------------------------
    # 4. Google Gemini API (Fallback)
    # -------------------------------------------------------------------------
    def _embed_gemini(self, texts: list[str]) -> list[list[float]]:
        from google import genai
        client = genai.Client(api_key=self.google_key)
        
        batch_size = 20
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            for attempt in range(3):
                try:
                    response = client.models.embed_content(
                        model="models/gemini-embedding-001",
                        contents=batch,
                    )
                    all_embeddings.extend([emb.values for emb in response.embeddings])
                    break
                except Exception as e:
                    if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                        time.sleep(5 * (attempt + 1))
                    else:
                        raise e
            if i + batch_size < len(texts):
                time.sleep(1.0)

        return all_embeddings

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------
    def embed_documents(self, documents: list[str]) -> list[list[float]]:
        if not documents:
            return []

        # 1. Try Hugging Face if HF_TOKEN is configured
        if self.hf_token:
            try:
                return self._embed_hf(documents)
            except Exception as e:
                logger.warning(f"HF embedding failed: {e}. Falling back...")

        # 2. Try NVIDIA NIM if NVIDIA_API_KEY is configured
        if self.nvidia_key:
            try:
                return self._embed_nvidia(documents)
            except Exception as e:
                logger.warning(f"NVIDIA embedding failed: {e}. Falling back...")

        # 3. Try Jina AI if JINA_API_KEY is configured
        if self.jina_key:
            try:
                return self._embed_jina(documents)
            except Exception as e:
                logger.warning(f"Jina embedding failed: {e}. Falling back...")

        # 4. Try Gemini if configured
        if self.google_key:
            return self._embed_gemini(documents)

        raise RuntimeError(
            "No active embedding API key configured! Please set HF_TOKEN, NVIDIA_API_KEY, or JINA_API_KEY in your .env."
        )

    def embed_query(self, query: str) -> list[float]:
        if not query:
            return []
        
        # 1. Try Hugging Face if HF_TOKEN is configured
        if self.hf_token:
            try:
                res = self._embed_hf([query])
                return res[0] if res else []
            except Exception as e:
                logger.warning(f"HF query embedding failed: {e}. Falling back...")

        # 2. Try NVIDIA NIM if NVIDIA_API_KEY is configured
        if self.nvidia_key:
            try:
                res = self._embed_nvidia([query], input_type="query")
                return res[0] if res else []
            except Exception as e:
                logger.warning(f"NVIDIA query embedding failed: {e}. Falling back...")

        # 3. Try Jina AI if JINA_API_KEY is configured
        if self.jina_key:
            try:
                res = self._embed_jina([query])
                return res[0] if res else []
            except Exception as e:
                logger.warning(f"Jina query embedding failed: {e}. Falling back...")

        # 4. Try Gemini if configured
        if self.google_key:
            res = self._embed_gemini([query])
            return res[0] if res else []

        raise RuntimeError(
            "No active embedding API key configured! Please set HF_TOKEN, NVIDIA_API_KEY, or JINA_API_KEY in your .env."
        )


embedding_service = EmbeddingsService()

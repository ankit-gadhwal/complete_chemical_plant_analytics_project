import time
import logging
from google import genai
from google.genai.errors import APIError
from src.config import Config

logger = logging.getLogger(__name__)


class EmbeddingsService:
    """
    Direct Google GenAI Native Batch Embedding Service.
    
    Why this solves both problems for free:
    1. Zero Server RAM: Computed on Google's cloud (0 MB local RAM on Render).
    2. Zero Rate Limit (429): Google's native client sends up to 50 text chunks
       in a SINGLE HTTP request (1 request instead of 50). A 150-chunk manual
       uses only 3 requests against the 100 req/min free limit.
    3. Automatic Exponential Backoff: Retries seamlessly if rate limited.
    """

    def __init__(self, model_name: str = "models/gemini-embedding-001"):
        self.model_name = model_name
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = genai.Client(api_key=Config.GOOGLE_API_KEY)
        return self._client

    def _embed_batch_with_retry(self, batch: list[str], max_retries: int = 3) -> list[list[float]]:
        for attempt in range(max_retries):
            try:
                response = self.client.models.embed_content(
                    model=self.model_name,
                    contents=batch,
                )
                return [emb.values for emb in response.embeddings]
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    wait_time = 5 * (attempt + 1)
                    logger.warning(f"Rate limit hit. Retrying batch in {wait_time}s... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Error generating embeddings: {e}")
                    raise e
        # Final attempt
        response = self.client.models.embed_content(
            model=self.model_name,
            contents=batch,
        )
        return [emb.values for emb in response.embeddings]

    def embed_documents(self, documents: list[str]) -> list[list[float]]:
        if not documents:
            return []

        # Send 40 chunks per SINGLE HTTP request (1 request per 40 chunks)
        batch_size = 40
        all_embeddings = []

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            embeddings = self._embed_batch_with_retry(batch)
            all_embeddings.extend(embeddings)
            
            # Small 0.5s courtesy delay between batches if multiple batches exist
            if i + batch_size < len(documents):
                time.sleep(0.5)

        return all_embeddings

    def embed_query(self, query: str) -> list[float]:
        response = self.client.models.embed_content(
            model=self.model_name,
            contents=query,
        )
        # For single query, response.embeddings has 1 item
        if response.embeddings:
            return response.embeddings[0].values
        return []


embedding_service = EmbeddingsService()

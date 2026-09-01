import time
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from src.config import Config


class EmbeddingsService:
    """
    Cloud-based Google Gemini Embeddings (text-embedding-004).
    Uses 0 MB server RAM, 0 disk space, 0 local model downloads.
    Batches chunks in small groups with pauses to guarantee zero
    rate limit / quota errors on the Google AI Studio free tier.
    """

    def __init__(self, model_name: str = "models/gemini-embedding-001"):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            self._model = GoogleGenerativeAIEmbeddings(
                model=self.model_name,
                google_api_key=Config.GOOGLE_API_KEY,
            )
        return self._model

    def embed_documents(self, documents: list[str]) -> list[list[float]]:
        if not documents:
            return []

        # Batch 20 chunks per single API request to respect the free-tier rate limits
        batch_size = 20
        all_embeddings = []
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            embeddings = self.model.embed_documents(batch)
            all_embeddings.extend(embeddings)
            if i + batch_size < len(documents):
                time.sleep(1.0)

        return all_embeddings

    def embed_query(self, query: str) -> list[float]:
        return self.model.embed_query(query)


embedding_service = EmbeddingsService()

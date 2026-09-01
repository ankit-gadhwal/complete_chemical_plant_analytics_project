from fastembed import TextEmbedding

class EmbeddingsService:
    """
    Wrapper around FastEmbed (ONNX Quantized Embeddings).
    Ultra-lightweight (~80MB RAM), CPU-optimized, zero PyTorch requirement,
    and no API rate limits.
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
    ):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            self._model = TextEmbedding(model_name=self.model_name)
        return self._model

    def embed_documents(self, documents: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple document chunks.
        """
        if not documents:
            return []
        embeddings = list(self.model.embed(documents))
        return [emb.tolist() for emb in embeddings]

    def embed_query(self, query: str) -> list[float]:
        """
        Generate embeddings for a single user query.
        """
        embedding = list(self.model.embed([query]))[0]
        return embedding.tolist()


embedding_service = EmbeddingsService()

import asyncio
from uuid import uuid4, UUID
from pathlib import Path
from .schemas import DocumentMetadata, DocumentSource
from .chunker import DocumentChunker
from .embeddings import embedding_service
from .loader import DocumentLoader
from .vector_store import VectorStore
from src.db.models import Document
from .retriever import Retriever


class IngestionService:

    def __init__(self):
        self.loader = DocumentLoader()
        self.chunker = DocumentChunker()
        self.embedding_service = embedding_service
        self.vector_store = VectorStore()
        self.retriever = Retriever(
            embedding_service=self.embedding_service,
            vector_store=self.vector_store,
        )

    def _sync_ingest(self, document: Document) -> int:
        document_name = Path(document.original_filename).name
        documents = self.loader.load(document.file_path)
        if not documents:
            return 0

        chunks = self.chunker.split_documents(documents)
        if not chunks:
            return 0

        texts = [chunk.page_content for chunk in chunks]
        embeddings = self.embedding_service.embed_documents(texts)
        ids = [str(uuid4()) for _ in chunks]

        metadatas = []
        for index, chunk in enumerate(chunks):
            page_raw = chunk.metadata.get("page")
            page_num = int(page_raw) if page_raw is not None and str(page_raw).isdigit() else 1
            metadata = DocumentMetadata(
                owner_uid=str(document.owner_uid),
                dataset_uid=str(document.dataset_uid),
                document_uid=str(document.uid),
                document_name=document_name,
                document_source=DocumentSource.USER,
                page=page_num,
                chunk_index=index,
            )
            metadatas.append(metadata.model_dump(exclude_none=True))

        self.vector_store.add_documents(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        return len(chunks)

    async def ingest_document(self, document: Document) -> int:
        # Run heavy I/O and embedding in thread pool to avoid blocking FastAPI event loop
        return await asyncio.to_thread(self._sync_ingest, document)
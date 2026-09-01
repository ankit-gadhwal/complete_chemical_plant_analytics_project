from fastapi import FastAPI
from contextlib import asynccontextmanager
from src.db.main import initdb
from src.datasets.routes import dataset_router
from src.Equipment.routes import equipment_router
from src.error import register_error_handlers
from .middleware import register_middleware
from .chatbot.routes import chat_router
from src.auth.router import auth_router
from src.documents.router import doc_router
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     print("Server is starting...")
#     await initdb()
#     yield
#     print("server is stoping")

app = FastAPI(
    title="Chemical Equipment Analytics API",
    # lifespan=lifespan  # add the lifespan event to our application
)

@app.get("/health", status_code=200)
async def health_check():
    return {"status": "healthy"}

register_error_handlers(app)
register_middleware(app)
app.include_router(
    dataset_router,prefix="/dataset",
    tags=['dataset']
)
app.include_router(equipment_router,prefix="/equipment",tags=["Equipment"])
app.include_router(chat_router,prefix= "/chat",tags=["Chatbot"])
app.include_router(auth_router,prefix= "/auth",tags= ["Auth"])
app.include_router(doc_router,prefix= "/documents",tags= ["Documents"])

# Mount Frontend static files
# import os
# from fastapi.staticfiles import StaticFiles

# frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
# if os.path.exists(frontend_dir):
#     app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

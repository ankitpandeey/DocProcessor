from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from pypdf import PdfReader
import chromadb
import os
import asyncio
import httpx

load_dotenv()
API_KEY = os.getenv("OPEN_API_KEY")
if os.name == "nt":
    client = OpenAI(
        api_key=API_KEY,
        http_client=httpx.Client(
            verify=r"C:\Users\MC823AX\ZscalerRootCertificate-2048-SHA256-Feb2025 (2).pem"
        )
    )
else:
    client = OpenAI(api_key=API_KEY)


chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="documents")
loader = PyPDFLoader("polity.pdf")
documents = loader.load()
splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200               
)
chunks = splitter.split_documents(documents)
texts = [chunk.page_content for chunk in chunks]

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


def ensure_indexed():
    try:
        if collection.count() > 0:
            print("DB is already updated")
            return
    except:
        pass
    print("updating DB")
    texts = [chunk.page_content for chunk in chunks]

batch_size = 100

for i in range(0, len(texts), batch_size):
    batch = texts[i:i+batch_size]
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=batch
    )
    for j, emb in enumerate(response.data):
        chunk = chunks[i + j]
        collection.add(
            ids=[f"doc_{i+j}"],
            documents=[chunk.page_content],
            embeddings=[emb.embedding],
            metadatas=[chunk.metadata]
        )


@app.on_event("startup")
def startup():
    ensure_indexed()

@app.post("/chat")
async def chat(data: ChatRequest):
    question = data.message
    query_embedding = client.embeddings.create(
        model="text-embedding-3-small",
        input=question
    ).data[0].embedding

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3
    )
    context = "\n".join(results["documents"][0])
    prompt = f"""
Use the context below to answer the question. Also generate follow up questions
Context:
{context}
Question:
{question}
"""
    stream = client.chat.completions.create(
        model="gpt-5.4",
        messages=[
            {"role": "system", "content": "Answer clearly using markdown headings and bullet points."},
            {"role": "user", "content": prompt}
        ],
        stream=True
    )

    async def event_generator():
        for chunk in stream:
            delta = chunk.choices[0].delta

            if delta and delta.content:
                yield delta.content
                await asyncio.sleep(0)

    return StreamingResponse(
        event_generator(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache"}
    )


@app.get("/health")
def health():
    return {"status": "ok"}

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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


chroma_client = chromadb.Client(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="documents")

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

def chunk_text(text, chunk_size=800, overlap=100):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

def ensure_indexed(text):
    try:
        if collection.count() > 0:
            return
    except:
        pass
    chunks = chunk_text(text)
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=chunks
    )

    embeddings = [e.embedding for e in response.data]

    collection.add(
        ids=[str(i) for i in range(len(chunks))],
        documents=chunks,
        embeddings=embeddings,
        metadatas=[{"source": "pd.pdf"} for _ in chunks]
    )

@app.on_event("startup")
def startup():
    pdf_path = "pd.pdf"
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    ensure_indexed(text)

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
Use the context below to answer the question.
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
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import chromadb
import os
import httpx

load_dotenv()

# ✅ Use your env var (your code uses OPEN_API_KEY)
API_KEY = os.getenv("OPEN_API_KEY")

# ✅ OpenAI client (your Zscaler cert)
client = OpenAI(
    api_key=API_KEY,
    http_client=httpx.Client(
        verify=r"C:\Users\MC823AX\ZscalerRootCertificate-2048-SHA256-Feb2025 (2).pem"
    )
)

# ✅ Chroma (TIP: use PersistentClient in real apps so it survives restarts)
chroma_client = chromadb.Client()
collection = chroma_client.get_or_create_collection(name="documents")

def chunk_text(text, chunk_size=100, overlap=20):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

def ensure_indexed():
    """Index document.txt only once (simple guard)."""
    # If already has embeddings/docs, skip.
    try:
        existing = collection.count()
        if existing and existing > 0:
            return
    except Exception:
        pass

    with open("document.txt", "r", encoding="utf-8") as doc:
        text = doc.read()

    chunks = chunk_text(text)

    for i, chunk in enumerate(chunks):
        emb = client.embeddings.create(
            model="text-embedding-3-small",
            input=chunk
        ).data[0].embedding

        collection.add(
            ids=[str(i)],
            documents=[chunk],
            embeddings=[emb]
        )

def answer_question(question: str) -> str:
    # Embed the question
    query_embedding = client.embeddings.create(
        model="text-embedding-3-small",
        input=question
    ).data[0].embedding

    # Retrieve top chunks
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3
    )

    context = "\n".join(results["documents"][0])

    prompt = f"""
Answer the question using the context below.

Context:
{context}

Question:
{question}
"""

    # Chat completion (message-based interface) [4](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/chatgpt)[5](https://deepwiki.com/openai/openai-python/4.1-chat-completions-api)
    chat = client.chat.completions.create(
        # ⚠️ Use a model you actually have access to.
        # Example: "gpt-4o-mini" (or your available one)
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    return chat.choices[0].message.content


app = FastAPI()

# ✅ CORS: allow your React dev server (Vite default is 5173)
# Without this, browser blocks calls across ports. [2](https://davidmuraya.com/blog/fastapi-cors-configuration/)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str

@app.on_event("startup")
def startup():
    ensure_indexed()

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    reply = answer_question(req.message)
    return ChatResponse(reply=reply)

@app.get("/health")
def health():
    return {"ok": True}
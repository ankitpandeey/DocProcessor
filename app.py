from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from pypdf import PdfReader
import chromadb
import os
import httpx

load_dotenv()
API_KEY = os.getenv("OPEN_API_KEY")
pdf_path = "pd.pdf"
reader = PdfReader(pdf_path)
all_text = ""
for page in reader.pages:
    page_text= page.extract_text()
    if page_text:
        all_text += page_text + "\n"

if os.name == "nt":
    client = OpenAI(
        api_key=API_KEY,
        http_client=httpx.Client(
            verify=r"C:\Users\MC823AX\ZscalerRootCertificate-2048-SHA256-Feb2025 (2).pem"
        )
    )
else:
    client = OpenAI(
        api_key=API_KEY
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
    """Index document only once"""
    try:
        if collection.count() > 0:
            return
    except:
        pass

    chunks = chunk_text(all_text)

    # Generate embeddings in batch
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=chunks
    )

    embeddings = [e.embedding for e in response.data]

    # Insert everything in one batch
    collection.add(
        ids=[str(i) for i in range(len(chunks))],
        documents=chunks,
        embeddings=embeddings
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
        model="gpt-5.4",
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
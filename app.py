from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader
from langchain_community.document_loaders import Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
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


loader = DirectoryLoader(
    path="kb",          
    glob="**/*.pdf",   
    loader_cls=PyPDFLoader,
    show_progress=True
)

# loader = PyPDFLoader("polity.pdf")
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
chat_history = []
def ensure_indexed():
    if collection.count() > 0:
        print("Vector DB already indexed")
        return
    print("Indexing documents...")
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
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

def rewrite_query(user_input, chat_history):
    if len(chat_history) == 0:
        return user_input
    conversation = "\n".join(
        [f"{m['role']}: {m['content']}" for m in chat_history[-4:]]
    )
    rewrite_prompt = f"""
    You rewrite follow-up questions into standalone search queries.
   Conversation:
   {conversation}
   User message:
   {user_input}
    Rewrite the message into a complete question suitable for search retrieval.
    If the question already has context return it unchanged.
    Only output the rewritten question.
    """
    response = client.chat.completions.create(
        model="gpt-5.4",
        messages=[
            {"role": "system", "content": "Rewrite follow up queries for search."},
            {"role": "user", "content": rewrite_prompt}
        ]
    )
    return response.choices[0].message.content.strip()

@app.on_event("startup")
def startup():
    ensure_indexed()

@app.post("/chat")
async def chat(data: ChatRequest):
    question = data.message
    chat_history.append({
        "role": "user",
        "content": question
    })
    rewritten_query = question
    if len(question.split()) < 4:
        rewritten_query = rewrite_query(question, chat_history)
    query_embedding = client.embeddings.create(
        model="text-embedding-3-small",
        input=rewritten_query
    ).data[0].embedding
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3
    )
    context = "\n".join(results["documents"][0])

    prompt = f"""
    You are a Business Analyst who try to explain tool's technical knowledge to a client.
    Use the provided context to answer the question.
    Context:
    {context}

    Question:
    {question}

    Explain clearly using headings and bullet points.
    Highlight exam traps when relevant.
    """
    stream = client.chat.completions.create(
        model="gpt-5.4",
        messages=[
            {"role": "system", "content": "You are an expert UPSC tutor."},
            *chat_history[-6:],
            {"role": "user", "content": prompt}
        ],
        stream=True
    )

    answer_buffer = ""
    async def event_generator():
        nonlocal answer_buffer
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                answer_buffer += delta.content
                yield delta.content
                await asyncio.sleep(0)
        chat_history.append({
            "role": "assistant",
            "content": answer_buffer
        })
    return StreamingResponse(
        event_generator(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache"}
    )

@app.get("/health")
def health():
    return {"status": "ok"}
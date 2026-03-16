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

chroma_client = chromadb.PersistentClient(path="/Users/ankitpandey/Documents/GitHub/DocProcessor/kb/chroma_db")
collection = chroma_client.get_or_create_collection(name="knowledge_base")
print(collection.count())
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

    scores = results["distances"][0]
    if min(scores) > 0.7:
        return "This question is not related to available documents"
    context = "\n".join(results["documents"][0])

    prompt = f"""
    You are a knowledgeable assistant.
    Use the provided context to answer the user's question.
    Guidelines:
    - Prefer information from the context when it is available.
    - If the context contains partial information, combine it with your general knowledge to provide a clear explanation.
    - If the question is completely unrelated to the context, explain that the information is not available in the provided sources and offer a helpful response if possible.
    Formatting guidelines:
    - Begin with a short explanatory paragraph.
    - Use bullet points only when listing key facts or steps.
    - Do not convert the entire answer into bullet points.
    Conversation guidelines:
    - Ask one relevant follow-up question when appropriate.
    Context:
{context}
Question:
{question}
Answer:
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


from openai import OpenAI
from dotenv import load_dotenv
import chromadb
import os
import httpx
load_dotenv()
API_KEY = os.getenv("OPEN_API_KEY")

chroma_client = chromadb.Client()
collection  = chroma_client.create_collection(name="documents")


client = OpenAI(
      api_key=API_KEY,
      http_client= httpx.Client(verify=r"C:\Users\MC823AX\ZscalerRootCertificate-2048-SHA256-Feb2025 (2).pem")
)
def chunk_text(text, chunk_size = 100, overlap = 20):
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks

with open("document.txt", "r") as doc:
    text = doc.read()
chunks = chunk_text(text)

embeddings = []

for i, chunk in enumerate(chunks):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=chunk
    )

    embedding = response.data[0].embedding
    collection.add(
        ids=[str(i),],
        documents=[chunk],
        embeddings=[embedding]
    )

question = input("Ask your question here? ")
response = client.embeddings.create(
    model = "text-embedding-3-small",
    input= question
 )
query_embedding = response.data[0].embedding

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

chat = client.chat.completions.create(
    model="gpt-5.4",
    messages=[
        {"role": "user", "content": prompt}
    ]
)

print("\nAnswer:\n")
print(chat.choices[0].message.content)
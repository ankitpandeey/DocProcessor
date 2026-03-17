import os
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from chromadb import PersistentClient
from openai import OpenAI
from dotenv import load_dotenv
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

# Chroma persistent DB
chroma_client = PersistentClient(path=r"C:\Users\MC823AX\OneDrive - EY\Documents\docProcessor\DocProcessor\kb\chroma_db")
collection = chroma_client.get_or_create_collection("knowledge_base_demo")
# Load all PDFs from kb folder
loader = TextLoader(
     "doc/KB_Template.txt",
)
# loader = DirectoryLoader(
#     "doc",
#     glob="**/*.pdf",
#     loader_cls=PyPDFLoader,
#     show_progress=True
# )

documents = loader.load()

# Split documents
splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)

chunks = splitter.split_documents(documents)

def ensure_indexed():
    print("Indexing documents...")
    batch_size = 100
    for i in range(0, len(chunks), batch_size):
        batch_chunks = chunks[i:i + batch_size]
        texts = [c.page_content for c in batch_chunks]
        # Generate embeddings
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=texts
        )
        ids = []
        documents_batch = []
        embeddings_batch = []
        metadata_batch = []

        for j, emb in enumerate(response.data):
            chunk = batch_chunks[j]
            source = os.path.basename(chunk.metadata.get("source", "unknown"))
            page = chunk.metadata.get("page", 0)
            # Stable ID for chunk
            chunk_id = f"{source}_p{page}_c{i+j}"
            ids.append(chunk_id)
            documents_batch.append(chunk.page_content)
            embeddings_batch.append(emb.embedding)
            metadata_batch.append(chunk.metadata)

        # Upsert prevents duplicates
        collection.upsert(
            ids=ids,
            documents=documents_batch,
            embeddings=embeddings_batch,
            metadatas=metadata_batch
        )

try:
    ensure_indexed()
    print("Indexing completed.")
except:
    print("Something went wrong")
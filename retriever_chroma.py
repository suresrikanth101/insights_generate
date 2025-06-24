import os
from typing import Optional
from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from pathlib import Path
import pickle
import json
from langchain_community.vectorstores import Chroma
from pymil_standard_mle import EMAS

EMAS_URL = "https://jarvis.verizon.com/v2/models/rt-llm-embeddings-v"
os.environ['LLM_ENDPOINT'] = 'https://vegas-llm-test.ebiz.verizon.com/vegas/apps/prompt'

def chunk_text(text: str, chunk_size: int = 10000, chunk_overlap: int = 400) -> list:
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = splitter.split_text(text)
    return chunks

def create_documents(chunks: list) -> list:
    documents = [Document(page_content=chunk) for chunk in chunks]
    return documents

def save_documents(documents, file_path):
    with open(file_path, 'wb') as f:
        pickle.dump(documents, f)

def load_documents(file_path):
    with open(file_path, 'rb') as f:
        return pickle.load(f)

def load_json_data(file_path: str) -> list:
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_text_and_metadata(data: list) -> list:
    extracted_data = []
    for entry in data:
        text = entry["content"]["text"]
        url = entry["content"].get("url", "Unknown")
        last_modified = entry["content"].get("last_modified", "Unknown")
        updated_time = entry["content"].get("updated_time", "Unknown")
        published_date = entry["content"].get("published_date", "Unknown")
        robots_status = entry["content"].get("robots_status", "Unknown")
        extracted_data.append({
            "text": text,
            "url": url,
            "last_modified": last_modified,
            "updated_time": updated_time,
            "published_date": published_date,
            "robots_status": robots_status
        })
    return extracted_data

def retrieve_chunks(query, k=3):
    # File paths
    json_file_path = "data/output/scraped_results_20250423_121953.json"
    chroma_db_path = "artifacts/chroma_db"
    documents_file_path = "artifacts/documents.pkl"

    # Load JSON data
    data = load_json_data(json_file_path)
    extracted_data = extract_text_and_metadata(data)

    # Initialize the model
    model = EMAS(emas_url=EMAS_URL)

    if not os.path.exists(chroma_db_path):
        # Chunk the extracted texts and add metadata
        chunks = []
        for entry in extracted_data:
            text_chunks = chunk_text(entry["text"])
            for chunk in text_chunks:
                chunks.append({
                    "text": chunk,
                    "url": entry["url"],
                    "last_modified": entry["last_modified"],
                    "updated_time": entry["updated_time"],
                    "published_date": entry["published_date"],
                    "robots_status": entry["robots_status"]
                })
        
        # Create Document objects with metadata
        documents = [
            Document(
                page_content=chunk["text"],
                metadata={
                    "url": chunk["url"],
                    "last_modified": chunk["last_modified"],
                    "updated_time": chunk["updated_time"],
                    "published_date": chunk["published_date"],
                    "robots_status": chunk["robots_status"]
                }
            )
            for chunk in chunks
        ]
        
        # Create ChromaDB index from documents
        chroma_db = Chroma.from_documents(
            documents=documents,
            embedding=model,
            persist_directory=chroma_db_path
        )
        
        # Save documents separately for reference
        save_documents(documents, documents_file_path)
        print(f"ChromaDB index created and saved to {chroma_db_path}")
    else:
        # Load the ChromaDB index from disk
        chroma_db = Chroma(
            persist_directory=chroma_db_path,
            embedding_function=model
        )
        print(f"ChromaDB index loaded from {chroma_db_path}")

    # Query the ChromaDB index
    results = chroma_db.similarity_search(query, k=k)

    print(f"Number of results from ChromaDB: {len(results)}")
    for i, result in enumerate(results, 1):
        print(f"Result {i}: {result.page_content[:100]}... URL: {result.metadata.get('url', '#')}")

    # Retrieve the relevant chunks with URLs for citation
    relevant_chunks = []
    for result in results:
        relevant_chunks.append({
            'page_content': result.page_content,
            'source_url': result.metadata.get('url', '#')
        })
    
    return relevant_chunks 
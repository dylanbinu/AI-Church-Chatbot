import os
import json
import asyncio
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

load_dotenv()

# --- CONFIG ---
base_dir = os.path.dirname(os.path.abspath(__file__))
import sys
sys.path.append(base_dir) 
from retrieval import retrieve_and_rank
project_root = os.path.join(base_dir, "..")
CHROMA_PATH = os.path.join(project_root, "chroma_db")
DATA_FILE = os.path.join(project_root, "scraped_data.jsonl")

# Ensure Key exists
if not os.environ.get("OPENAI_API_KEY"):
    raise RuntimeError("OPENAI_API_KEY not found in environment.")

# --- LOAD MOCK DATA ---
VALID_URLS = []
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                VALID_URLS.append(data["source"])
            except: pass

print(f"Loaded {len(VALID_URLS)} valid URLs for context checking.")

# --- MOCK REQUEST CLASS ---
class MockRequest:
    def __init__(self, message):
        self.message = message
        self.use_full_context = False

# --- TEST SUITE ---
TEST_QUESTIONS = [
    "Who is the lead pastor?",
    "What do you believe?",
    "Do you have a youth ministry?",
    "Is there anything for my kids?",
    "How can I give?",
    "What events are coming up?",
    "How do I join a small group?",
]

def run_tests():
    print("--- STARTING RETRIEVAL & GENERATION EVALUATION ---")
    
    if not os.path.exists(CHROMA_PATH):
        print("❌ Database not found. Run ingest.py first.")
        return

    embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
    vector_db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embedding_model)
    # Retriever creation moved to retrieve_and_rank
    llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.3)

    # --- SIMULATE SERVER.PY LOGIC ---
    # We copy the EXACT logic from server.py here to test it. 
    # (Ideally this would be a shared import, but for verifying the logic this is sufficient)

    PREFERRED_CAMPUS_KEYWORD = None
    # Auto-detect context (Mocking the server logic)
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            first_line = f.readline()
            if first_line:
                data = json.loads(first_line)
                first_url = data.get("source", "").strip("/")
                if "/" in first_url:
                    candidate = first_url.split("/")[-1]
                    if candidate.lower() not in ["locations", "campuses", "visit", "home", "en", "welcome"]:
                        PREFERRED_CAMPUS_KEYWORD = candidate.lower()
    
    print(f"Context Detected: {PREFERRED_CAMPUS_KEYWORD}")

    for question in TEST_QUESTIONS:
        print(f"\n[?] QUESTION: '{question}'")
        request = MockRequest(question)
        
        # Call shared retrieval logic
        # Note: retrieve_and_rank returns top 10. We can slice if we want only 5.
        final_docs = retrieve_and_rank(request.message, vector_db, VALID_URLS, PREFERRED_CAMPUS_KEYWORD)
        final_docs = final_docs[:5] # Keep it to 5 for the test output consistency

        # REPORTING
        print("   [+] Selected Documents:")
        for i, doc in enumerate(final_docs):
            source = doc.metadata.get("source", "unknown")
            print(f"      {i+1}. {source}")

        # GENERATION
        context_text = "\n\n".join([f"[Source: {d.metadata.get('source', 'unknown')}]\n{d.page_content}" for d in final_docs])
        
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """You are a warm, welcoming, and helpful digital greeter for a church website.
            
        GUIDELINES:
        1. **Persona & Tone (PRIORITY):** You are a friendly church assistant. BE WARM, CHATTY, AND INVITING.
            - **MANDATORY:** Start with a warm, conversational sentence BEFORE listing any information.
        2. **Accuracy:** From Context.
            - **CRITICAL:** DO NOT GUESS OR HALLUCINATE.
            - If the answer is NOT in the context, say: "I'm not sure about that specific detail, but I'd love to help you find out!" and then provide a link to the **[Contact Page]({{CONTACT_URL}})**.
        3. **Formatting & Structure (CARDS):**
            - **To make a "Card" in the chat, you MUST use a bullet point WITH A LINK.**
        4. **Fallbacks & Safety:**
            - **Distress:** Link "Prayer" or "Contact". Avoid specific care groups unless asked.
            - Compassionate tone.
                
        Context: {context}
        """),
            ("human", "{question}")
        ])

        chain = prompt_template | llm | StrOutputParser()
        # Mock contact replacement
        response = chain.invoke({"context": context_text, "question": request.message})
        # Generic Contact URL replacement if needed
        response = response.replace("{{CONTACT_URL}}", "/contact")
        
        # Sanitize for Windows Console
        safe_response = response.encode('cp1252', errors='ignore').decode('cp1252')
        print(f"\n   [ASSISTANT]: {safe_response}\n")

if __name__ == "__main__":
    run_tests()

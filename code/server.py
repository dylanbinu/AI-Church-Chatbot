# --- PYSQLITE3 FIX FOR LAMBDA (Must be first) ---
try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass 

import sys
import shutil
import traceback
import os
import json
import re

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional

# --- SAFETY BOOT HARNESS ---
GLOBAL_BOOT_ERROR = None
app = None
handler = None

try:
    # --- LAMBDA FIXES ---
    # 1. FIX READ-ONLY FILESYSTEM
    # Lambda effectively runs in read-only /var/task. SQLite needs to write wal/lock files.
    # We must copy the DB to /tmp (the only writable dir) on startup.
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        print("[INFO] Detected AWS Lambda Environment. Setting up /tmp...")
        writable_db_path = "/tmp/chroma_db"
        
        # Override config paths BEFORE import/usage
        # We need to manually fix config module attributes if they are already imported?
        # Typically config is imported below.
        
        # Check source path
        source_db_path = os.path.join(os.getcwd(), "chroma_db") 
        # (Assuming cwd is /var/task/code or /var/task depending on WORKDIR)
        
        if os.path.exists(source_db_path):
            if os.path.exists(writable_db_path):
                shutil.rmtree(writable_db_path)
            shutil.copytree(source_db_path, writable_db_path)
            print(f"[INFO] Copied ChromaDB from {source_db_path} to {writable_db_path}")
        else:
             # Fallback check for /var/task root
             root_source = "/var/task/chroma_db"
             if os.path.exists(root_source):
                 if os.path.exists(writable_db_path):
                    shutil.rmtree(writable_db_path)
                 shutil.copytree(root_source, writable_db_path)
                 print(f"[INFO] Copied ChromaDB from {root_source} to {writable_db_path}")

        # 3. FIX TIKTOKEN CACHE (Must be writable)
        os.environ["TIKTOKEN_CACHE_DIR"] = "/tmp"

    # --- LOAD DEPENDENCIES ---
    # (Delay imports to catch ImportError)
    from langchain_chroma import Chroma
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.messages import HumanMessage, AIMessage
    
    # Local Modules
    import config
    # Force override config path after import
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        config.CHROMA_PATH = "/tmp/chroma_db"

    from retrieval import retrieve_and_rank
    from context_manager import load_context_from_file
    from link_utils import validate_and_fix_links

    # --- LOAD CHURCH REGISTRY & CONTEXT ---
    CHURCHES = {}
    CHURCH_CONTEXTS = {} 

    if os.path.exists(config.CHURCHES_FILE):
        with open(config.CHURCHES_FILE, "r") as f:
            CHURCHES = json.load(f)
        print(f"Loaded {len(CHURCHES)} churches from registry.")

    # Load Default (Legacy) Context
    DEFAULT_CONTEXT = load_context_from_file(config.DEFAULT_DATA_FILE)
    if not DEFAULT_CONTEXT:
        DEFAULT_CONTEXT = {"valid_urls": set(), "main_domain": "https://google.com", "preferred_keyword": None}

    # Load Specific Church Contexts
    for church_id in CHURCHES:
        path = os.path.join(config.PROJECT_ROOT, f"scraped_data_{church_id}.jsonl")
        ctx = load_context_from_file(path)
        if ctx:
            CHURCH_CONTEXTS[church_id] = ctx
            print(f"Loaded context for {church_id}")

    # --- GLOBAL MODEL INITIALIZATION (Optimization) ---
    print("--- Initializing AI Models & Database Connection... ---")
    embedding_model = OpenAIEmbeddings(model=config.EMBEDDING_MODEL_NAME)
    llm = ChatOpenAI(model_name=config.LLM_MODEL_NAME, temperature=config.LLM_TEMPERATURE)

    # Initialize ChromaDB Client Globally if DB exists
    vector_db = None
    if os.path.exists(config.CHROMA_PATH):
        vector_db = Chroma(persist_directory=config.CHROMA_PATH, embedding_function=embedding_model)
        print("--- Vector Database Connected ---")
    else:
        print("--- WARNING: Vector Database not found. Run ingest.py first. ---")
        
    # --- GLOBAL MODEL INITIALIZATION (Optimization) ---
    print("--- Initializing AI Models & Database Connection... ---")
    embedding_model = OpenAIEmbeddings(model=config.EMBEDDING_MODEL_NAME)
    llm = ChatOpenAI(model_name=config.LLM_MODEL_NAME, temperature=config.LLM_TEMPERATURE)

    # Initialize ChromaDB Client Globally if DB exists
    vector_db = None
    if os.path.exists(config.CHROMA_PATH):
        vector_db = Chroma(persist_directory=config.CHROMA_PATH, embedding_function=embedding_model)
        print("--- Vector Database Connected ---")
    else:
        print("--- WARNING: Vector Database not found. Run ingest.py first. ---")
        
    # --- FASTAPI APP ---
    app = FastAPI(title="Church Assistant API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- DATA MODELS ---
    class ChatRequest(BaseModel):
        message: str
        history: List[dict] = []
        use_full_context: bool = False
        church_id: Optional[str] = None

    class ChatResponse(BaseModel):
        response: str
        sources: List[str]

    # --- CHAT ENDPOINT ---
    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest):
        try:
            # Determine Context
            church_id = request.church_id
            context_data = DEFAULT_CONTEXT
            
            if church_id and church_id in CHURCH_CONTEXTS:
                context_data = CHURCH_CONTEXTS[church_id]
                print(f"--- Using Context for Church ID: {church_id} ---")
            else:
                if church_id: print(f"--- Church ID {church_id} not found, using default ---")
                
            valid_urls = context_data["valid_urls"]
            main_domain = context_data["main_domain"]
            preferred_keyword = context_data.get("preferred_keyword")

            # 1. Database Check
            if vector_db is None:
                raise HTTPException(status_code=503, detail="Database not ready. Run ingest.py first.")

            # 2. Retrieve Relevant Context
            # Prune history to last 4 messages
            recent_history = request.history[-4:] if len(request.history) > 4 else request.history
            
            langchain_history = [
                HumanMessage(content=msg['content']) if msg['role'] == 'user' else AIMessage(content=msg['content'])
                for msg in recent_history
            ]

            final_docs = retrieve_and_rank(request.message, vector_db, valid_urls, preferred_keyword, church_id)
            
            # Construct Context Text
            context_text = "\n\n".join([f"[Source: {d.metadata.get('source', 'unknown')}]\n{d.page_content}" for d in final_docs])
            # HARD CAP: Limit context
            if len(context_text) > 15000:
                context_text = context_text[:15000] + "...(truncated)"

            # Dynamic Contact URL
            contact_url = "https://google.com"
            if main_domain: contact_url = main_domain
            for u in valid_urls:
                if "/contact" in u or "/connect" in u:
                    contact_url = u
                    break

            if not context_text:
                return ChatResponse(response=f"I apologize, that specific detail isn't available right now. Please visit our [Contact Page]({contact_url}).", sources=[])

            # 3. Generate Answer (Church Assistant Persona)
            # SYSTEM PROMPT - UNTOUCHED FOR SAFETY
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", """You are a warm, welcoming, and helpful digital greeter for a church website.
                
            GUIDELINES:
            1. **Persona & Tone (PRIORITY):** You are a friendly church assistant. BE WARM, CHATTY, AND INVITING.
                - **MANDATORY:** Start with a warm, conversational sentence BEFORE listing any information.
                - **NEVER** just output a list. Always speak first.
            2. **Accuracy (NO HALLUCINATIONS):**
                - **CRITICAL:** Use **ONLY** URLs that are explicitly provided in the `Context` below.
                - **NEVER** invent or guess a URL (e.g. do not make up `/care-support` or `/connect`).
                - **VERIFICATION:** If a URL you want to use is NOT listed in the `SOURCE:` fields of the context, **DO NOT USE IT.** This is a hard rule.
                - If you don't have a specific link for a topic, link to the **Home Page** or **Contact Page** found in context.
                - If the answer is NOT in the context, say: "I'm not sure about that specific detail, but I'd love to help you find out!" and then provide a link to the **[Contact Page]({{CONTACT_URL}})**.
            3. **Formatting & Structure (CARDS):**
                - **To make a "Card" in the chat, you MUST use a bullet point WITH A LINK.**
                - **Structure:** `* **[Campus Name](url)**: Service A, Service B...`
                - **Preferred Format:** 
                  `* **[Campus Name](url)**`
                  `  * Service A`
                  `  * Service B`
            4. **Links & CTA (STRICT DE-DUPLICATION):** 
                - **NEVER** output multiple bullet points that link to the SAME URL. This is critical.
                - **Consolidate:** If "Join Group", "Serve", and "Classes" all link to `/connect`, output **ONE** bullet: 
                  `* [Connect Page](url) - Join a group, serve on a team, or take a class.`
                - **Visual Check:** If you see the same blue link twice, you have failed. Merge them.
            5. **Fallbacks & Safety:**
                - **Plan Your Visit:** if no specific `/visit` or `/plan` page exists, link to the **Home Page**.
                - **Home Page Links:** When linking to the Home Page, **ALWAYS** use the base URL (e.g. `https://church.com/`). **NEVER** use a sub-page (like `/team/` or `/about/`) as the Home Page link.
                - **Distress:** Link "Prayer" or "Contact". Avoid specific care groups unless asked.
                - Compassionate tone.
            
            6. **Service Times Logic (CRITICAL):**
                - **GROUP TIMES BY DAY:** Never list the same day multiple times.
                    - **BAD:** "Every Sunday at 9:00 AM, Every Sunday at 11:00 AM"
                    - **GOOD:** "Sundays at 9:00 AM & 11:00 AM"
                - **NO REPETITION:** Do not use the phrase "Every Sunday" more than once per campus.
                - **ACCURACY:** Check the context carefully. If a campus lists multiple times (e.g. 9:30 & 11:00), you **MUST** list all of them. Do not skip any.
                - **Ignore** one-off event times (e.g., "Special Event") unless specifically asked.
                - **Format:**
                    `* **[Campus Name](url)**`
                    `  * Sundays at 9:00 AM & 11:00 AM`
                - **CRITICAL:** NEVER split a time string (e.g. `4:00 PM`) or date across formatting bold/italics. 
                - **Keep "Day & Time" together:** Do not put "Saturdays" in the header and "at 5pm" in the body. Keep them in the same bullet point.
                - **Unique Times:** If multiple locations exist, list times for **each** location clearly.
                    
            7. **Link Naming (ACCURACY):**
                - When creating a link `[Link Text](url)`, the "Link Text" MUST match the actual page title or header found in the context for that URL.
                - **DO NOT INVENT NAMES.** Do not call a page "Prayer Page" if the title is "Care & Support".
                    
            Context: {context}
            """),
                *langchain_history,
                ("human", "{question}")
            ])
            
            chain = prompt_template | llm
            response = chain.invoke({"context": context_text, "question": request.message})
            
            # Inject Dynamic Contact URL
            pattern = r'(?:\{+\s*CONTACT_URL\s*\}+|%7B\s*CONTACT_URL\s*%7D)'
            response.content = re.sub(pattern, contact_url, response.content, flags=re.IGNORECASE)
            
            # Validate Links
            validated_content = validate_and_fix_links(response.content, valid_urls, contact_url, main_domain)
            
            # Extract Sources
            unique_sources = list(set([d.metadata.get('source', '') for d in final_docs]))
            
            return ChatResponse(response=validated_content, sources=unique_sources)

        except Exception as e:
            # Catch-all for runtime errors (like OpenAI timeouts, Pydantic validation)
            print(f"CRITICAL CHAT ERROR: {e}")
            traceback.print_exc()
            return JSONResponse(status_code=500, content={"error": f"Internal Server Error: {str(e)}"})

    @app.get("/church_chatbot.js", response_class=FileResponse)
    async def get_widget_js():
        return os.path.join(config.BASE_DIR, "church_chatbot.js")

    @app.get("/", response_class=HTMLResponse)
    async def get_widget():
        widget_path = os.path.join(config.BASE_DIR, "widget_demo.html")
        with open(widget_path, "r", encoding="utf-8") as f:
            return f.read()

except Exception as e:
    # --- FALLBACK APP FOR DEBUGGING ---
    print(f"CRITICAL BOOT ERROR: {e}")
    GLOBAL_BOOT_ERROR = traceback.format_exc()
    app = FastAPI(title="Broken Boot App")

    @app.get("/{path:path}")
    @app.post("/{path:path}")
    def catch_all(path: str):
        return JSONResponse(
            status_code=500, 
            content={
                "error": "Application Failed to Start", 
                "traceback": GLOBAL_BOOT_ERROR,
                "cwd": os.getcwd(),
                "files": os.listdir(os.getcwd()) if os.path.exists(os.getcwd()) else []
            }
        )

# --- MANGUM HANDLER (Always Created) ---
from mangum import Mangum
handler = Mangum(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
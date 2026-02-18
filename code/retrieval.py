from typing import List, Set, Optional
from langchain_chroma import Chroma
from langchain_core.documents import Document

import config

def retrieve_and_rank(
    query: str,
    vector_db: Chroma,
    valid_urls: Set[str],
    preferred_campus_keyword: Optional[str] = None,
    church_id: Optional[str] = None
) -> List[Document]:
    """
    Performs hybrid retrieval (forced injection + semantic search) and custom scoring/ranking.
    """
    
    forced_docs = []
    
    # Helper to build filter
    def build_filter(source_url=None):
        if church_id and source_url:
            return {"$and": [{"church_id": church_id}, {"source": source_url}]}
        elif church_id:
            return {"church_id": church_id}
        elif source_url:
            return {"source": source_url}
        return None

    # 1. Force Injection Logic
    
    # A. Generic Service Times / Visit
    if ("service" in query.lower() and "times" in query.lower()) or \
       ("new" in query.lower()) or \
       ("visit" in query.lower()):
        print("--- DETECTED GENERIC SERVICE TIME QUERY: INJECTING LOCATIONS ---")
        location_urls = [u for u in valid_urls if "/locations/" in u or "/campuses/" in u or "/contact" in u or "/visit" in u or u.rstrip("/").count("/") == 2] 
        # OPTIMIZATION: Limit to top 4 shortest URLs to prevent timeout (generic queries shouldn't scan 50 subpages)
        location_urls.sort(key=len)
        location_urls = location_urls[:4]
        
        for url in location_urls:
             # Apply church_id filter if present
             f = build_filter(url)
             hits = vector_db.similarity_search("service times", k=1, filter=f)
             forced_docs.extend(hits)

    # B. Giving
    if any(q in query.lower() for q in ["give", "giving", "donate", "tithe"]):
        print("--- DETECTED GIVING QUERY: INJECTING GIVING PAGES ---")
        giving_urls = [u for u in valid_urls if "/give" in u or "/giving" in u or "/donate" in u]
        # OPTIMIZATION: Limit to 2
        giving_urls.sort(key=len)
        for url in giving_urls[:2]:
             f = build_filter(url)
             hits = vector_db.similarity_search("giving", k=1, filter=f)
             forced_docs.extend(hits)

    # C. Team/Staff
    if any(q in query.lower() for q in ["pastor", "team", "staff", "leader", "who"]):
        print("--- DETECTED TEAM QUERY: INJECTING TEAM PAGES ---")
        team_urls = [u for u in valid_urls if "/team" in u or "/staff" in u or "/leadership" in u or "/who-we-are" in u or "/about" in u]
        # OPTIMIZATION: Limit to 3 shortest (likely main staff page)
        team_urls.sort(key=len)
        for url in team_urls[:3]:
             f = build_filter(url)
             hits = vector_db.similarity_search("pastors staff team", k=1, filter=f)
             forced_docs.extend(hits)

    # D. Youth/Kids
    if any(q in query.lower() for q in ["youth", "kid", "child", "student", "teen"]):
        print("--- DETECTED YOUTH/KIDS QUERY: INJECTING YOUTH/KIDS PAGES ---")
        ministry_urls = [u for u in valid_urls if "/youth" in u or "/kid" in u or "/child" in u or "/student" in u]
        # OPTIMIZATION: Limit to 3
        ministry_urls.sort(key=len)
        for url in ministry_urls[:3]:
             f = build_filter(url)
             hits = vector_db.similarity_search("youth kids ministry", k=1, filter=f)
             forced_docs.extend(hits)
    
    # 2. Standard Semantic Retrieval (MMR)
    search_kwargs = {"k": 60, "fetch_k": 100}
    if church_id:
        search_kwargs["filter"] = {"church_id": church_id}
        
    retriever = vector_db.as_retriever(search_type="mmr", search_kwargs=search_kwargs)
    raw_docs = retriever.invoke(query)
    
    # 3. Combine & Deduplicate
    combined_docs = forced_docs + raw_docs
    unique_docs_map = {}
    for doc in combined_docs:
        # Dedupe by source + first 100 chars
        signature = (doc.metadata.get("source", ""), doc.page_content[:100])
        if signature not in unique_docs_map:
            unique_docs_map[signature] = doc
    
    candidates = list(unique_docs_map.values())

    # 4. Scoring / Re-Ranking
    scored_docs = []
    
    # Dynamic Campus Boosting: Check if user mentioned a specific campus
    mentioned_campus_slug = None
    for url in valid_urls:
        slug = url.rstrip("/").split("/")[-1].lower()
        if slug in query.lower().replace(" ", "-"):
            mentioned_campus_slug = slug
            break
            
    for doc in candidates:
        source = doc.metadata.get("source", "").lower()
        score = 0
        
        if any(sub in source for sub in config.HIGH_VALUE_SUBSTRINGS): score += 5
        if any(sub in source for sub in config.LOW_VALUE_SUBSTRINGS): score -= 10
        
        # Context Boost
        if preferred_campus_keyword and preferred_campus_keyword in source:
            score += 2 
            
        # Explicit Campus Request Boost
        if mentioned_campus_slug and mentioned_campus_slug in source:
            score += 25
            
        # Root Domain Boost
        if source.rstrip("/").count("/") == 2:
            score += 15
        
        scored_docs.append((doc, score))
        
    scored_docs.sort(key=lambda x: x[1], reverse=True)
    return [d[0] for d in scored_docs[:10]]

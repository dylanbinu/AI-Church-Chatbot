import os
import json
from collections import Counter
from urllib.parse import urlparse

def load_context_from_file(filepath):
    valid_urls = set()
    main_domain = ""
    preferred_keyword = None
    
    if not os.path.exists(filepath):
        return None

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            # Read first line for keyword (heuristic)
            first_line = f.readline()
            if first_line:
                try:
                    data = json.loads(first_line)
                    first_url = data.get("source", "").strip("/")
                    if "/" in first_url:
                        candidate = first_url.split("/")[-1]
                        # A better check to ensure we don't pick up common words as keywords
                        if candidate.lower() not in ["locations", "campuses", "visit", "home", "en", "welcome", "index"] and "." not in candidate:
                            preferred_keyword = candidate.lower()
                except:
                    pass

            f.seek(0)
            for line in f:
                try:
                    data = json.loads(line)
                    url = data.get("source")
                    content = data.get("content", "").lower()
                    if "page not found" in content or "404" in content: continue
                    if url: valid_urls.add(url)
                except: pass
        
        if valid_urls:
            domains = [urlparse(u).netloc for u in valid_urls]
            common = Counter(domains).most_common(1)
            if common:
                main_domain = f"https://{common[0][0]}"
                
        return {
            "valid_urls": valid_urls,
            "main_domain": main_domain,
            "preferred_keyword": preferred_keyword
        }
    except Exception as e:
        print(f"Error loading context from {filepath}: {e}")
        return None

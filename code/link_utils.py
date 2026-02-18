import re
from typing import Set

# Helper: Common hallucinations mapped to real paths (partial or full)
KEYWORD_FALLBACKS = {
    "give": ["give", "giving", "donate", "donation", "tithe", "offering"],
    "giving": ["give", "giving", "donate", "donation", "tithe", "offering"],
    "prayer": ["care", "prayer", "request"],
    "watch": ["watch", "message", "sermon", "media", "youtube"],
    "location": ["contact", "visit", "about", "home"],
    "locations": ["contact", "visit", "about", "home"],
    "kids": ["kid", "child", "family", "nursery"],
    "youth": ["youth", "student", "teen"]
}

def validate_and_fix_links(text: str, valid_urls: Set[str], fallback_url: str, main_domain: str = "") -> str:
    """
    Parses markdown links [text](url).
    Checks if 'url' is in valid_urls.
    If not, tries to find a close match or fallback.
    """
    def replace_link(match):

        label = match.group(1)
        url = match.group(2).rstrip("/")
        label_lower = label.lower()

        # --- 0. LABEL-BASED OVERRIDES (Fix Hallucinations/Bad Deep Links) ---
        
        # Calculate roots once (safe scope)
        roots = [v for v in valid_urls if v.rstrip('/').count('/') == 2]
        
        # A. "Home Page" -> Force Root Domain
        if "home page" in label_lower and "contact" not in label_lower:
            if roots:
                # Pick the shortest root (likely the actual main page)
                return f"[{label}]({min(roots, key=len)})"

        # B. "Plan Your Visit" -> specific page OR Root
        if "plan your visit" in label_lower or "visit us" in label_lower:
            # Try to find a REALLY good match first
            visits = [v for v in valid_urls if "/plan-your-visit" in v or "/visit" in v or "/im-new" in v]
            best_visit = None
            # Filter out known bad patterns if possible, or just pick shortest
            if visits:
                 # heuristic: pick shortest to avoid specific blog posts "visit-to-orphanage"
                 best_visit = min(visits, key=len)
            
            if best_visit:
                 return f"[{label}]({best_visit})"
            elif roots:
                 # Fallback to Home Page if no specific visit page
                 return f"[{label}]({min(roots, key=len)})"

        # 1. Exact Match
        if url in valid_urls:
            return f"[{label}]({url})"
        
        # 2. Case Insensitive Match
        for v in valid_urls:
            if v.lower() == url.lower():
                return f"[{label}]({v})"
            
            # Dynamic Partial Match: Use main_domain if available
            if main_domain:
                # e.g. url was "/contact", v is "https://church.com/contact"
                # Check if url is a suffix of v
                if url.startswith("/") and v.endswith(url):
                     return f"[{label}]({v})"
                 
                # Check if stripped URL is in v
                # e.g. url="https://wrong-domain.com/contact", v="https://church.com/contact"
                # This is tricky. Let's stick to relative path matching.
                if url.replace(main_domain, "") in v and len(url) > 10:
                     return f"[{label}]({v})"

        # 3. Smart Keyword Fallback (Generic)
        # Check if the hallucinates URL path (e.g. "give") matches a known concept
        cleaned_path = url.strip("/").lower()
        
        # Check our predefined concepts
        for concept, keywords in KEYWORD_FALLBACKS.items():
            if concept in cleaned_path:
                # Look for a VALID URL that matches any of these keywords
                for v in valid_urls:
                    v_lower = v.lower()
                    if any(kw in v_lower for kw in keywords):
                        # Found a match! e.g. "tithes-and-offerings" contains "tithe"
                        return f"[{label}]({v})"
                        
        # Fallback: STRICT GUARANTEE
        # If we reached here, the URL is NOT in our database and didn't match any heuristic.
        # We MUST replace it to prevent 404s/Hallucinations.
        return f"[{label}]({fallback_url})"
        
    # Regex for [text](url)
    pattern = r'\[([^\]]+)\]\((https?://[^)]+|/[^)]+)\)'
    return re.sub(pattern, replace_link, text)

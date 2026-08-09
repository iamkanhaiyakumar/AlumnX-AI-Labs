import re

def strip_html(text: str) -> str:
    """
    Strips HTML tags from the given text.
    """
    if not text:
        return ""
    clean = re.compile(r'<.*?>')
    return re.sub(clean, '', text)

def clean_whitespace(text: str) -> str:
    """
    Normalizes multiple spaces and trims lines.
    """
    if not text:
        return ""
    # Normalize lines and filter out empty ones
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join([line for line in lines if line])

def extract_new_message(body: str) -> str:
    """
    Extracts the newly written reply content from the email body,
    discarding quoted history and forwarded headers.
    """
    if not body:
        return ""
    
    # Strip HTML first
    body_clean = strip_html(body)
    
    # Regex patterns indicating the start of a quoted chain
    quote_headers = [
        r"(?i)^\s*On\s+.*\s+wrote:\s*$",                         # On ... wrote:
        r"(?i)^\s*On\s+.*\s+wrote\s+.*:\s*$",
        r"^-+\s*Original Message\s*-+$",                         # -----Original Message-----
        r"^\s*From:\s+.*",                                       # From: ...
        r"^\s*Sent:\s+.*",                                       # Sent: ...
        r"^\s*To:\s+.*",                                         # To: ...
        r"^\s*Subject:\s+.*",                                    # Subject: ...
        r"^\s*Date:\s+.*",                                       # Date: ...
        r"^\s*>.*",                                              # > Quoted text
        r"^-+\s*Forwarded message\s*-+$",                        # ---------- Forwarded message ---------
    ]
    
    lines = body_clean.splitlines()
    new_lines = []
    
    for line in lines:
        stripped = line.strip()
        is_quote = False
        for pattern in quote_headers:
            if re.match(pattern, stripped):
                is_quote = True
                break
        if is_quote:
            # We hit the quoted original text, stop extracting
            break
        new_lines.append(line)
        
    new_content = "\n".join(new_lines).strip()
    
    # Fallback to cleaned body if extraction result is empty
    if not new_content:
        return clean_whitespace(body_clean)
        
    return clean_whitespace(new_content)

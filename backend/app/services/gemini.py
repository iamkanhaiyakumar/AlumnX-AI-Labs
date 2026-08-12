import time
import logging
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, GoogleAPICallError
from typing import Type, Optional, Union, get_origin, get_args
import types
from pydantic import BaseModel, Field
from ..config import settings

logger = logging.getLogger(__name__)

# Stateful Key Rotation Index
current_key_index = 0

def get_current_key() -> str:
    """
    Returns the currently active Gemini API key from settings.
    """
    global current_key_index
    if not settings.GEMINI_API_KEYS:
        return settings.GEMINI_API_KEY
    return settings.GEMINI_API_KEYS[current_key_index % len(settings.GEMINI_API_KEYS)]

def rotate_key():
    """
    Rotates to the next available Gemini API key in settings.
    """
    global current_key_index
    if not settings.GEMINI_API_KEYS or len(settings.GEMINI_API_KEYS) <= 1:
        return
    current_key_index += 1
    next_key = get_current_key()
    logger.info(f"Rotating API Key. Switched to key index {current_key_index % len(settings.GEMINI_API_KEYS)}")
    genai.configure(api_key=next_key)

# Configure initial key
genai.configure(api_key=get_current_key())

def pydantic_to_gemini_schema(model: Type[BaseModel]) -> dict:
    """
    Translates a Pydantic model into a clean, Gemini API compliant schema dictionary.
    Excludes unsupported keys like 'default', 'title', 'anyOf' to prevent live SDK failures.
    """
    properties = {}
    required = []

    for field_name, field_info in model.model_fields.items():
        field_type = field_info.annotation
        description = field_info.description or ""
        
        # Check if type is Union (to handle Optional/nullable fields)
        is_nullable = False
        origin = get_origin(field_type)
        args = get_args(field_type)
        
        actual_type = field_type
        if origin is Union or (hasattr(types, "UnionType") and origin is types.UnionType):
            if type(None) in args:
                is_nullable = True
                non_none_types = [t for t in args if t is not type(None)]
                if non_none_types:
                    actual_type = non_none_types[0]

        # Map actual_type to Gemini type string
        type_str = "STRING"
        if actual_type is int:
            type_str = "INTEGER"
        elif actual_type is float:
            type_str = "NUMBER"
        elif actual_type is bool:
            type_str = "BOOLEAN"
        elif actual_type is str:
            type_str = "STRING"
        elif actual_type is dict or get_origin(actual_type) is dict:
            type_str = "OBJECT"
        elif actual_type is list or get_origin(actual_type) is list:
            type_str = "ARRAY"
            
        field_schema = {
            "type": type_str,
            "description": description
        }
        
        if is_nullable:
            field_schema["nullable"] = True
            
        properties[field_name] = field_schema
        
        # Add to required list if field is required in Pydantic
        if field_info.is_required():
            required.append(field_name)

    schema_dict = {
        "type": "OBJECT",
        "properties": properties,
    }
    if required:
        schema_dict["required"] = required
        
    return schema_dict

def call_groq_fallback(prompt: str, response_schema: Optional[Type[BaseModel]] = None) -> str:
    """
    Fallback call to Groq Cloud API using Llama 3 model when Gemini is rate-limited.
    """
    if not settings.GROQ_API_KEY:
        raise Exception("Groq API key not configured in settings")
        
    try:
        from groq import Groq
    except ImportError:
        raise Exception("groq python library not installed")
        
    logger.info("Initiating Groq (Llama-3) fallback call...")
    
    client = Groq(api_key=settings.GROQ_API_KEY)
    
    kwargs = {}
    if response_schema:
        kwargs["response_format"] = {"type": "json_object"}
        prompt += f"\nYour output must be a valid JSON object matching the required fields."

    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model="llama-3.1-8b-instant",
        temperature=0.1,
        **kwargs
    )
    
    if chat_completion.choices and chat_completion.choices[0].message.content:
        return chat_completion.choices[0].message.content
        
    raise Exception("Groq returned empty response")

def call_gemini_with_retry(
    prompt: str,
    response_schema: Optional[Type[BaseModel]] = None,
    max_retries: int = 5,
    initial_delay: float = 2.0
) -> str:
    """
    Calls the Gemini API. Rotates keys instantly on rate limits, or fails fast
    on permanent client errors to trigger local fallbacks without hanging.
    Supports a secondary fallback to Groq (Llama 3) if GROQ_API_KEY is configured.
    """
    try:
        generation_config = {}
        if response_schema:
            generation_config["response_mime_type"] = "application/json"
            generation_config["response_schema"] = pydantic_to_gemini_schema(response_schema)

        delay = initial_delay
        
        # Configure SDK with active key before calling
        genai.configure(api_key=get_current_key())

        for attempt in range(max_retries):
            try:
                model = genai.GenerativeModel(settings.GEMINI_MODEL)
                response = model.generate_content(
                    prompt,
                    generation_config=generation_config if generation_config else None
                )
                if response and response.text:
                    return response.text
                raise Exception("Gemini returned an empty response")
            except ResourceExhausted as e:
                # HTTP 429 - Rate Limits
                if len(settings.GEMINI_API_KEYS) > 1:
                    logger.warning(
                        f"Gemini API rate limit hit on key index {current_key_index % len(settings.GEMINI_API_KEYS)}. "
                        "Rotating key and retrying immediately..."
                    )
                    rotate_key()
                    continue
                else:
                    logger.warning("Gemini API rate limit hit (ResourceExhausted). Failing fast to trigger fallback.")
                    raise e
            except GoogleAPICallError as e:
                status_code = getattr(e, "code", None)
                if status_code in [400, 403, 404, 429]:
                    logger.warning(f"Gemini API returned permanent client error code {status_code}: {e}. Raising immediately.")
                    raise e
                logger.warning(f"Gemini API call failed on attempt {attempt+1}: {e}. Retrying in {delay}s...")
                time.sleep(delay)
                delay = min(delay * 2.0, 30.0)
            except Exception as e:
                logger.warning(f"Unexpected error calling Gemini on attempt {attempt+1}: {e}. Raising immediately.")
                raise e
                
        raise Exception("Max retries exceeded when calling Gemini API.")
    except Exception as gemini_err:
        # Gemini failed! Try Groq fallback before giving up
        if settings.GROQ_API_KEY:
            try:
                return call_groq_fallback(prompt, response_schema)
            except Exception as groq_err:
                logger.warning(f"Groq fallback also failed: {groq_err}")
        # If Groq is not configured or failed, re-raise the original Gemini exception
        raise gemini_err


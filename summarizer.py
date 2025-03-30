import os
import requests
import re
import tempfile
import time
import threading
import multiprocessing

# Import libraries for Llama model
try:
    import llama_cpp
    from huggingface_hub import hf_hub_download
    from langchain_community.chat_models import ChatLlamaCpp
    LLAMA_AVAILABLE = True
    print("Llama-Cpp Version:", llama_cpp.__version__)
except ImportError:
    LLAMA_AVAILABLE = False
    print("Llama-Cpp not available, will use fallback summarization")

# Global variables for model management
MODEL_LOADED = False
MODEL_LOADING = False
MODEL = None
MODEL_LOCK = threading.Lock()

def download_model():
    """
    Downloads the Llama model from Hugging Face Hub.
    Returns the path to the downloaded model file.
    """
    if not LLAMA_AVAILABLE:
        print("Llama libraries not available - using extractive summarization only")
        return None
        
    try:
        model_name = "lmstudio-community/Llama-3.2-3B-Instruct-GGUF"
        model_file = "Llama-3.2-3B-Instruct-Q4_K_M.gguf"
        
        print(f"Downloading model {model_name}/{model_file}...")
        model_path = hf_hub_download(model_name, filename=model_file)
        print(f"Model downloaded to {model_path}")
        return model_path
    except Exception as e:
        print(f"Error downloading model: {str(e)}")
        return None

def load_model():
    """
    Loads the Llama model for text summarization.
    Sets the global MODEL variable when complete.
    """
    global MODEL, MODEL_LOADED, MODEL_LOADING
    
    if MODEL_LOADED or MODEL_LOADING:
        return
    
    with MODEL_LOCK:
        if MODEL_LOADING:
            return
        MODEL_LOADING = True
    
    try:
        if not LLAMA_AVAILABLE:
            print("Llama libraries not available - using extractive summarization only")
            with MODEL_LOCK:
                MODEL_LOADING = False
            return
            
        model_path = download_model()
        if not model_path:
            print("Failed to download model")
            with MODEL_LOCK:
                MODEL_LOADING = False
            return
            
        print("Initializing Llama model...")
        
        # Configure the Llama model with optimal parameters
        llm = ChatLlamaCpp(
            temperature=0.5,
            model_path=model_path,
            n_ctx=4096,
            n_gpu_layers=6,  # Use GPU acceleration if available
            n_batch=128,
            max_tokens=512,
            n_threads=multiprocessing.cpu_count() - 1,  # Use all but one CPU core
            repeat_penalty=1.2,
            top_p=0.9,
            verbose=True
        )
        
        with MODEL_LOCK:
            MODEL = llm
            MODEL_LOADED = True
            MODEL_LOADING = False
            
        print("Model loaded successfully")
    except Exception as e:
        print(f"Error loading model: {str(e)}")
        with MODEL_LOCK:
            MODEL_LOADING = False

def fetch_article_text(url):
    """
    Extracts the main text content from a news article URL.
    Uses basic regex to extract text content.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            print(f"Failed to fetch article: HTTP {response.status_code}")
            return None
            
        html_content = response.text
        
        # Remove script, style, and other non-content tags
        clean_html = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL)
        clean_html = re.sub(r'<style[^>]*>.*?</style>', '', clean_html, flags=re.DOTALL)
        clean_html = re.sub(r'<nav[^>]*>.*?</nav>', '', clean_html, flags=re.DOTALL)
        clean_html = re.sub(r'<header[^>]*>.*?</header>', '', clean_html, flags=re.DOTALL)
        clean_html = re.sub(r'<footer[^>]*>.*?</footer>', '', clean_html, flags=re.DOTALL)
        
        # Try to find paragraphs
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', clean_html, flags=re.DOTALL)
        
        if paragraphs:
            # Remove HTML tags from paragraphs
            cleaned_paragraphs = [re.sub(r'<[^>]+>', '', p) for p in paragraphs]
            text = '\n'.join([p.strip() for p in cleaned_paragraphs if p.strip()])
            
            # Clean up text
            text = re.sub(r'\s+', ' ', text)  # Remove extra whitespace
            text = re.sub(r'(?<!\.)\.(?![\s\w])', '. ', text)  # Fix missing spaces after periods
            
            if len(text) > 100:
                return text
        
        # If no paragraphs found or text too short, try to extract all text
        all_text = re.sub(r'<[^>]+>', ' ', clean_html)
        all_text = re.sub(r'\s+', ' ', all_text).strip()
        
        return all_text[:3000]  # Limit to first 3000 chars to avoid huge texts
        
    except Exception as e:
        print(f"Error fetching article: {str(e)}")
        return None

def fallback_summarize(text):
    """
    Creates a simple extractive summary when the LLM model is unavailable.
    """
    if not text:
        return "Could not summarize the article."
        
    # Split into sentences
    sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', text)
    
    if len(sentences) <= 5:
        return text
        
    # Score sentences by position (earlier = more important) and length
    scored_sentences = []
    for i, sentence in enumerate(sentences):
        if len(sentence.split()) < 5:  # Skip very short sentences
            continue
            
        position_score = 1.0 / (i + 1)  # Earlier sentences get higher scores
        length_score = min(len(sentence.split()) / 20.0, 1.0)  # Prefer sentences of moderate length
        score = position_score + length_score
        
        scored_sentences.append((sentence, score))
        
    # Sort by score and take top sentences
    sorted_sentences = sorted(scored_sentences, key=lambda x: x[1], reverse=True)
    top_sentences = [s[0] for s in sorted_sentences[:5]]
    
    # Re-sort to maintain original order
    ordered_summary = []
    for sentence in sentences:
        if sentence in top_sentences:
            ordered_summary.append(sentence)
            if len(ordered_summary) >= 5:
                break
                
    return " ".join(ordered_summary)

def summarize_article(url):
    """
    Fetches an article and generates a summary.
    Uses Llama model if available, otherwise falls back to extractive summarization.
    """
    # Start model loading in background if not already loaded
    if not MODEL_LOADED and not MODEL_LOADING and LLAMA_AVAILABLE:
        model_thread = threading.Thread(target=load_model)
        model_thread.daemon = True
        model_thread.start()
    
    # Fetch the article content
    article_text = fetch_article_text(url)
    if not article_text:
        return "Could not fetch or parse the article content."
        
    # If the article is too long, truncate it for summarization
    if len(article_text) > 8000:
        article_text = article_text[:8000] + "..."
        
    # Check if model is loaded
    if MODEL_LOADED and LLAMA_AVAILABLE:
        try:
            with MODEL_LOCK:
                prompt = f"""Please provide a detailed summary of the following article. Focus on the main points, key findings, and important details. Keep the summary clear and informative.

Article:
{article_text}

Summary:"""
                
                response = MODEL.invoke(prompt)
                summary = response.content
                
                # Clean up response
                summary = re.sub(r'^Summary:', '', summary, flags=re.IGNORECASE).strip()
                
                return summary
        except Exception as e:
            print(f"Error using Llama model: {str(e)}")
            # Fall back to extractive summary
            return fallback_summarize(article_text)
    else:
        # Use fallback method
        return fallback_summarize(article_text)

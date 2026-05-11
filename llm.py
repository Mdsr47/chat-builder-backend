from groq import Groq
import os

# Fallback key (used if no user key is saved)
FALLBACK_GROQ_KEY = os.getenv("GROQ_API_KEY")


def _get_groq_client(api_key: str = None):
    key = api_key or FALLBACK_GROQ_KEY
    return Groq(api_key=key)


def _get_openai_client(api_key: str):
    try:
        from openai import OpenAI
        return OpenAI(api_key=api_key)
    except ImportError:
        raise RuntimeError("openai package not installed. Run: pip install openai")


def _get_claude_client(api_key: str):
    try:
        import anthropic
        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        raise RuntimeError("anthropic package not installed. Run: pip install anthropic")


def generate_answer(query, context_docs, provider: str = "groq", api_key: str = None, system_instructions: str = None, chat_history: list = None):
    context = "\n\n".join([doc["text"] for doc in context_docs])

    base_system = "RAG assistant"
    if system_instructions:
        base_system = system_instructions

    prompt = f"""You are a helpful AI assistant.

Instructions:
1. For common greetings (e.g., "hi", "hello", "how are you") or conversational closings (e.g., "ok", "thank you", "bye"), respond naturally, warmly, and softly. Then, politely ask a question related to the topic of the context to guide the conversation.
2. For all other questions, answer ONLY using the provided context.
3. If the answer to a question is not in the context, do not just say "I don't know". Instead, politely ask the user a question to gather more details related to the topic of the context.

Context:
{context}

Question:
{query}
"""

    if provider == "openai":
        return _generate_openai(prompt, base_system, api_key, chat_history)
    elif provider == "claude":
        return _generate_claude(prompt, base_system, api_key, chat_history)
    else:
        return _generate_groq(prompt, base_system, api_key, chat_history)


def analyze_intent(messages: list, provider: str = "groq", api_key: str = None) -> str:
    """
    Analyze the overall purchase/booking intent of a chat session.
    messages: list of dicts with keys 'role' (user/bot) and 'text'
    Returns one of: "low", "medium", "high", "very_high"
    """
    if not messages:
        return "low"

    # Build a compact conversation transcript (last 20 exchanges max)
    transcript_lines = []
    for m in messages:
        role = "User" if m.get("role") == "user" else "Bot"
        transcript_lines.append(f"{role}: {m.get('text', '')}")
    transcript = "\n".join(transcript_lines[-20:])

    prompt = f"""You are an expert sales analyst. Analyze the following chat conversation and classify the visitor's purchase/booking intent.

Conversation:
{transcript}

Based on this conversation, classify the visitor's intent as EXACTLY one of these values (no explanation, just the value):
- low       (browsing, no clear interest)
- medium    (some interest, asking questions)
- high      (strong interest, comparing options or asking about pricing/availability)
- very_high (ready to buy/book, asking how to proceed, providing contact info, or expressing urgency)

Reply with only one word: low, medium, high, or very_high"""

    system = "You are a precise intent classification assistant. Reply with exactly one word."

    try:
        if provider == "openai" and api_key:
            result = _generate_openai(prompt, system, api_key)
        elif provider == "claude" and api_key:
            result = _generate_claude(prompt, system, api_key)
        else:
            result = _generate_groq(prompt, system, api_key)

        result = result.strip().lower().replace(".", "").replace('"', "").replace("'", "")
        if result in ("low", "medium", "high", "very_high"):
            return result
        # Fuzzy match if LLM adds extra words
        for level in ("very_high", "high", "medium", "low"):
            if level in result:
                return level
        return "low"
    except Exception as e:
        print(f"[Intent] Analysis failed: {e}")
        return "low"


def _generate_groq(prompt: str, system: str, api_key: str = None, chat_history: list = None) -> str:
    client = _get_groq_client(api_key)
    messages = [{"role": "system", "content": system}]
    if chat_history:
        messages.extend(chat_history)
    messages.append({"role": "user", "content": prompt})
    
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages
    )
    return completion.choices[0].message.content


def _generate_openai(prompt: str, system: str, api_key: str, chat_history: list = None) -> str:
    if not api_key:
        raise ValueError("OpenAI API key is required")
    client = _get_openai_client(api_key)
    messages = [{"role": "system", "content": system}]
    if chat_history:
        messages.extend(chat_history)
    messages.append({"role": "user", "content": prompt})
    
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )
    return completion.choices[0].message.content


def _generate_claude(prompt: str, system: str, api_key: str, chat_history: list = None) -> str:
    if not api_key:
        raise ValueError("Claude API key is required")
    client = _get_claude_client(api_key)
    messages = []
    if chat_history:
        messages.extend(chat_history)
    messages.append({"role": "user", "content": prompt})
    
    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        system=system,
        messages=messages
    )
    return message.content[0].text
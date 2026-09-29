import json
import re
import requests


def extract_conversation_from_link(url):

    if not url.startswith("https://chatgpt.com/share/"):
        raise ValueError(
            "Please provide a valid ChatGPT shared link."
        )

    response = requests.get(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/139.0.0.0 Safari/537.36"
            )
        },
        timeout=30
    )

    response.raise_for_status()

    html = response.text

    # -------------------------------------------------
    # METHOD 1: Look for conversation data in script tags
    # -------------------------------------------------

    patterns = [
        r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        r'<script[^>]*type="application/json"[^>]*>(.*?)</script>',
    ]

    for pattern in patterns:

        matches = re.findall(
            pattern,
            html,
            re.DOTALL | re.IGNORECASE
        )

        for raw_data in matches:

            try:

                data = json.loads(raw_data)

                messages = find_messages(data)

                if messages:
                    return {
                        "title": find_title(data),
                        "text": format_messages(messages)
                    }

            except Exception:
                continue


    # -------------------------------------------------
    # METHOD 2: Search the raw HTML for message objects
    # -------------------------------------------------

    messages = extract_message_objects(html)

    if messages:

        return {
            "title": extract_title(html),
            "text": format_messages(messages)
        }


    raise ValueError(
        "ChatGPT shared page was reached, but the conversation "
        "messages could not be extracted. ChatGPT may have changed "
        "the shared-page format."
    )


# =====================================================
# Find message structures recursively
# =====================================================

def find_messages(obj):

    results = []

    if isinstance(obj, dict):

        # Common message structure
        if (
            "author" in obj
            and "content" in obj
        ):

            author = obj.get("author", {})

            if isinstance(author, dict):

                role = author.get("role")

                if role in ["user", "assistant"]:

                    text = extract_content(obj["content"])

                    if text:
                        results.append({
                            "role": role,
                            "content": text
                        })

        for value in obj.values():

            results.extend(
                find_messages(value)
            )

    elif isinstance(obj, list):

        for item in obj:

            results.extend(
                find_messages(item)
            )

    return results


# =====================================================
# Extract message objects from raw HTML
# =====================================================

def extract_message_objects(html):

    messages = []

    pattern = re.compile(
        r'"author"\s*:\s*\{.*?"role"\s*:\s*"(user|assistant)".*?'
        r'"content"\s*:\s*\{.*?\}',
        re.DOTALL
    )

    for match in pattern.finditer(html):

        role = match.group(1)

        block = match.group(0)

        text_match = re.search(
            r'"parts"\s*:\s*\[(.*?)\]',
            block,
            re.DOTALL
        )

        if not text_match:
            continue

        raw_parts = text_match.group(1)

        strings = re.findall(
            r'"((?:\\.|[^"\\])*)"',
            raw_parts
        )

        for value in strings:

            try:
                text = json.loads(
                    '"' + value + '"'
                )
            except Exception:
                text = value

            text = text.strip()

            if text:

                messages.append({
                    "role": role,
                    "content": text
                })

                break

    return messages


# =====================================================
# Extract content
# =====================================================

def extract_content(content):

    if not isinstance(content, dict):
        return ""

    parts = content.get("parts", [])

    texts = []

    for part in parts:

        if isinstance(part, str):

            texts.append(part)

    return "\n".join(texts).strip()


# =====================================================
# Format messages for Gemini
# =====================================================

def format_messages(messages):

    output = []

    for message in messages:

        role = message["role"].upper()

        content = message["content"]

        output.append(
            f"{role}:\n{content}"
        )

    return "\n\n".join(output)


# =====================================================
# Find title
# =====================================================

def find_title(data):

    if isinstance(data, dict):

        for key in ["title", "conversation_title"]:

            value = data.get(key)

            if isinstance(value, str) and value.strip():

                return value.strip()

        for value in data.values():

            result = find_title(value)

            if result:
                return result

    elif isinstance(data, list):

        for item in data:

            result = find_title(item)

            if result:
                return result

    return "ChatGPT Conversation"


def extract_title(html):

    match = re.search(
        r'<title[^>]*>(.*?)</title>',
        html,
        re.DOTALL | re.IGNORECASE
    )

    if match:

        title = match.group(1).strip()

        title = re.sub(
            r'\s+',
            ' ',
            title
        )

        return title

    return "ChatGPT Conversation"
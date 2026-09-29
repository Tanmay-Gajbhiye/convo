import json
import re
import requests
from urllib.parse import urlparse


def fetch_share_page(url: str) -> str:
    parsed = urlparse(url)

    if parsed.netloc not in {
        "chatgpt.com",
        "www.chatgpt.com",
        "chat.openai.com",
    }:
        raise ValueError("Invalid ChatGPT share URL.")

    if "/share/" not in parsed.path:
        raise ValueError(
            "URL must be a public ChatGPT /share/ link."
        )

    response = requests.get(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/139.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        },
        timeout=30,
    )

    if response.status_code != 200:
        raise ValueError(
            f"ChatGPT returned HTTP {response.status_code}."
        )

    return response.text


def extract_rsc_payload(html: str):
    """
    Extract the React Flight / turbo-stream payload
    used by modern ChatGPT shared pages.
    """

    chunks = []

    patterns = [
        r'streamController\.enqueue\("((?:\\.|[^"\\])*)"\)',
        r"streamController\.enqueue\('((?:\\.|[^'\\])*)'\)",
    ]

    for pattern in patterns:
        matches = re.findall(
            pattern,
            html,
            re.DOTALL,
        )

        for match in matches:
            try:
                decoded = json.loads(f'"{match}"')
                chunks.append(decoded)
            except Exception:
                # Fallback for malformed escaping
                chunks.append(
                    match.replace('\\"', '"')
                         .replace("\\\\", "\\")
                )

    if not chunks:
        raise ValueError(
            "Could not find ChatGPT's RSC payload."
        )

    return "\n".join(chunks)


def parse_flat_payload(payload: str):
    """
    Parse the positional flattened object graph.

    ChatGPT's payload stores values in a flat array.
    Integer values can point to another slot.
    """

    lines = payload.splitlines()

    flat = None
    promise_values = {}

    for line in lines:

        line = line.strip()

        if not line:
            continue

        # Main flat array
        if line.startswith("["):

            try:
                candidate = json.loads(line)

                if isinstance(candidate, list):
                    flat = candidate
                    continue

            except Exception:
                pass

        # Deferred promise records
        match = re.match(
            r"P(\d+):(.*)",
            line,
            re.DOTALL,
        )

        if match:

            index = int(match.group(1))
            raw = match.group(2)

            try:
                promise_values[index] = json.loads(raw)
            except Exception:
                pass

    if flat is None:
        raise ValueError(
            "Could not decode ChatGPT's flattened payload."
        )

    flat = list(flat)

    # Apply deferred values
    for index, value in promise_values.items():

        if index < len(flat):
            flat[index] = value

    return flat


def resolve_value(flat, index, cache=None, stack=None):
    """
    Recursively resolve references in the flat object graph.
    """

    if cache is None:
        cache = {}

    if stack is None:
        stack = set()

    if not isinstance(index, int):
        return index

    if index < 0 or index >= len(flat):
        return None

    if index in cache:
        return cache[index]

    if index in stack:
        return None

    stack.add(index)

    value = flat[index]

    # Integer = reference to another slot
    if isinstance(value, int):

        if value == index:
            result = None
        else:
            result = resolve_value(
                flat,
                value,
                cache,
                stack,
            )

        cache[index] = result
        stack.remove(index)
        return result

    # Lists
    if isinstance(value, list):

        result = [
            resolve_value(
                flat,
                item,
                cache,
                stack,
            )
            for item in value
        ]

        cache[index] = result
        stack.remove(index)
        return result

    # Objects
    if isinstance(value, dict):

        result = {}

        for key, val in value.items():

            # Turbo-stream object keys can look like "_123"
            if key.startswith("_") and key[1:].isdigit():

                key_index = int(key[1:])

                real_key = resolve_value(
                    flat,
                    key_index,
                    cache,
                    stack,
                )

                real_value = resolve_value(
                    flat,
                    val,
                    cache,
                    stack,
                )

                if isinstance(real_key, str):
                    result[real_key] = real_value

            else:

                result[key] = resolve_value(
                    flat,
                    val,
                    cache,
                    stack,
                )

        cache[index] = result
        stack.remove(index)

        return result

    cache[index] = value
    stack.remove(index)

    return value


def find_conversation(obj):
    """
    Search the decoded object graph by structure instead
    of depending on one hard-coded ChatGPT route.
    """

    if isinstance(obj, dict):

        if "linear_conversation" in obj:

            value = obj["linear_conversation"]

            if isinstance(value, list):
                return obj

        if "mapping" in obj:

            value = obj["mapping"]

            if isinstance(value, (dict, list)):
                return obj

        for value in obj.values():

            result = find_conversation(value)

            if result:
                return result

    elif isinstance(obj, list):

        for item in obj:

            result = find_conversation(item)

            if result:
                return result

    return None


def extract_text_from_content(content):

    if not isinstance(content, dict):
        return ""

    parts = content.get("parts", [])

    output = []

    for part in parts:

        if isinstance(part, str):
            output.append(part)

        elif isinstance(part, dict):

            text = part.get("text")

            if isinstance(text, str):
                output.append(text)

    return "\n".join(output).strip()


def message_to_text(message):

    if not isinstance(message, dict):
        return ""

    content = message.get("content")

    return extract_text_from_content(content)


def extract_messages(conversation):

    messages = []

    # ---------------------------------------------
    # Modern linear_conversation format
    # ---------------------------------------------

    linear = conversation.get(
        "linear_conversation"
    )

    if isinstance(linear, list):

        for item in linear:

            if not isinstance(item, dict):
                continue

            message = item.get("message", item)

            if not isinstance(message, dict):
                continue

            author = message.get(
                "author",
                {},
            )

            role = (
                author.get("role")
                if isinstance(author, dict)
                else None
            )

            if role not in {
                "user",
                "assistant",
            }:
                continue

            text = message_to_text(message)

            if text:

                messages.append({
                    "role": role,
                    "content": text,
                })

        if messages:
            return messages

    # ---------------------------------------------
    # Mapping format
    # ---------------------------------------------

    mapping = conversation.get("mapping")

    if isinstance(mapping, dict):

        for node in mapping.values():

            if not isinstance(node, dict):
                continue

            message = node.get("message")

            if not isinstance(message, dict):
                continue

            author = message.get(
                "author",
                {},
            )

            role = (
                author.get("role")
                if isinstance(author, dict)
                else None
            )

            if role not in {
                "user",
                "assistant",
            }:
                continue

            text = message_to_text(message)

            if text:

                messages.append({
                    "role": role,
                    "content": text,
                })

    return messages


def extract_chatgpt_conversation(url: str):

    html = fetch_share_page(url)

    payload = extract_rsc_payload(html)

    flat = parse_flat_payload(payload)

    cache = {}

    decoded = []

    for i in range(len(flat)):

        decoded.append(
            resolve_value(
                flat,
                i,
                cache,
            )
        )

    conversation = find_conversation(decoded)

    if not conversation:

        raise ValueError(
            "ChatGPT page was fetched successfully, "
            "but the conversation structure could not "
            "be located."
        )

    messages = extract_messages(conversation)

    if not messages:

        raise ValueError(
            "Conversation was found, but no user/assistant "
            "messages could be extracted."
        )

    title = (
        conversation.get("title")
        or conversation.get("pageTitle")
        or "ChatGPT Conversation"
    )

    transcript = "\n\n".join(
        f"{message['role'].upper()}:\n"
        f"{message['content']}"
        for message in messages
    )

    return {
        "title": title,
        "messages": messages,
        "transcript": transcript,
        "message_count": len(messages),
    }
"""Claude-powered analyst for scanned code."""
from typing import List, Dict, Optional

import anthropic

from app.config import ANTHROPIC_API_KEY, MODEL, USE_BEDROCK


if USE_BEDROCK:
    client = anthropic.AnthropicBedrock()
else:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are an expert software engineer and code analyst.
You have been given the full source code of a repository.
Your job is to:
1. Explain what the codebase does clearly and concisely.
2. Answer specific questions about functions, logic, configuration, and architecture.

Rules:
- Be precise. Reference specific file names and line numbers when relevant.
- If asked about a function or class, describe its purpose, inputs, outputs, and key logic.
- If asked about configuration, explain each relevant setting and its effect.
- Do not guess — if something is unclear from the code, say so.
- Format your responses in Markdown for readability.
"""


def summarize_repo(repo_context: str, file_tree: str) -> str:
    """Generate a high-level summary of the repository."""
    user_message = f"""Here is the file tree of the repository:

```
{file_tree}
```

Here is the full source code:

{repo_context}

---

Please provide a comprehensive summary covering:
1. **Purpose** — What does this project/application do?
2. **Architecture** — Key components, layers, and how they interact.
3. **Entry points** — How is the app started? Main files/modules.
4. **Key dependencies** — Important libraries/frameworks used and why.
5. **Data flow** — How data moves through the system (input → processing → output).
6. **Configuration** — Notable config files and what they control.
"""
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text


def answer_question(
    question: str,
    repo_context: str,
    file_tree: str,
    history: List[Dict],
    attachments: Optional[List[Dict]] = None,
) -> str:
    """Answer a specific question about the codebase, with optional file attachments."""
    messages = []

    # Inject the code context as the first user turn (only once)
    context_turn = {
        "role": "user",
        "content": f"""Here is the file tree of the repository:

```
{file_tree}
```

Here is the full source code:

{repo_context}

---

I will now ask you questions about this codebase.""",
    }
    context_ack = {
        "role": "assistant",
        "content": "Understood. I have reviewed the full source code and file tree. Ask me anything about this codebase.",
    }

    messages.append(context_turn)
    messages.append(context_ack)

    # Append prior conversation turns
    for turn in history:
        messages.append(turn)

    # Build the new user message, including any file attachments
    user_content: List = []

    # Add text attachments as text blocks
    if attachments:
        for att in attachments:
            if att.get("type") == "image" and att.get("image_data"):
                user_content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": att["media_type"],
                        "data": att["image_data"],
                    },
                })
                user_content.append({
                    "type": "text",
                    "text": f"[Image uploaded: {att['filename']}]",
                })
            elif att.get("type") == "text" and att.get("content"):
                user_content.append({
                    "type": "text",
                    "text": f"[Attached file: {att['filename']}]\n\n{att['content']}",
                })
            elif att.get("error"):
                user_content.append({
                    "type": "text",
                    "text": f"[File {att['filename']} could not be read: {att['error']}]",
                })

    user_content.append({"type": "text", "text": question})

    messages.append({"role": "user", "content": user_content})

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    return response.content[0].text

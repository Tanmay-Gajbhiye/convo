import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError("GEMINI_API_KEY is not set in .env")

client = genai.Client(api_key=api_key)

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def summarize_conversation(conversation):

    transcript = "\n".join(
        f"{m['role'].upper()}: {m['content']}"
        for m in conversation["messages"]
    )

    prompt = f"""
Turn the following complete conversation into a clean, professional,
human-readable conversation note.

The result should feel like a well-written note saved for later,
NOT like an AI-generated analysis or report.

REFERENCING THE PERSON:
- Always refer to the person as "User".
- Never use "I".
- Never use "you".
- Never write "the AI", "the assistant", or mention the AI/model name.
- Do not mention ChatGPT, Gemini, Claude, or any other model.

FORMATTING:

Use this general structure:

TITLE

One or two natural paragraphs explaining what User wanted and what happened.

If the conversation contains multiple important points, options, steps,
comparisons, or results, use a properly formatted list.

Lists may use:
1. First point
2. Second point
3. Third point

OR:

- First point
- Second point
- Third point

Choose whichever looks more natural.

IMPORTANT:
- NEVER use "*" as a bullet.
- NEVER create random bullet points just to make the answer look structured.
- Do not turn every sentence into a bullet.
- Use paragraphs when information reads naturally as prose.
- Use numbered lists when there is an order, process, ranking, or sequence.
- Use "-" lists when the items are independent.
- Keep related information together.
- Use **bold** for important terms when useful.
- *Italic* may be used sparingly when genuinely helpful.
- Do not over-format the response.
- Do not create unnecessary headings.
- Keep the visual structure clean and consistent.

CONTENT:

Start with a short, descriptive title.

Then explain:
- What User originally wanted.
- The important information discussed.
- The useful answer, solution, or result.
- Any important decision or change that happened later.

If the conversation contains useful code, commands, formulas, generated text,
an email, instructions, or another concrete output, preserve the important
actual output accurately.

Do not replace useful concrete content with a vague summary.

If appropriate, finish with a short:

BOTTOM LINE

or

STATUS

Do not force either section if it is unnecessary.

QUALITY RULES:
- Identify the original purpose of the conversation.
- Preserve the actual meaning of the conversation.
- Follow the conversation naturally.
- Give more importance to the final/correct information when something was
  later corrected.
- Preserve important requirements, preferences, decisions, and conclusions.
- Ignore greetings, filler, repetition, and meaningless back-and-forth.
- Do not repeat the entire conversation.
- Do not invent information.
- Do not guess missing information.
- If something cannot be determined, leave it out.
- Keep the result concise and easy to scan.
- The result should normally be readable in under one minute.
- Do not add an "AI Model" section.
- Do not add "Important Facts", "Highlights", "Quick Check",
  "Unresolved Questions", or similar artificial sections.
- Do not describe the process of summarizing.
- Do not mention that the output is a summary.
- Do not use excessive Markdown.
- NEVER use "*" for bullet points.

CONVERSATION:
{transcript}
"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt
    )

    return response.text


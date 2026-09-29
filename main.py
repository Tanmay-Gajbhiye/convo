from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from chatgpt_parser import extract_chatgpt_conversation
from summarizer import summarize_conversation


app = FastAPI(
    title="AI Conversation Summarizer"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def home():

    return FileResponse(
        "static/index.html"
    )


@app.post("/summarize-link")
async def summarize_link(data: dict):

    url = data.get("url", "").strip()

    if not url:

        raise HTTPException(
            status_code=400,
            detail="Please provide a ChatGPT shared link."
        )

    try:

        # 1. Extract complete ChatGPT conversation
        conversation = extract_chatgpt_conversation(
            url
        )

        print(
            f"Extracted: "
            f"{conversation['title']} "
            f"({conversation['message_count']} messages)"
        )

        # 2. Send transcript to Gemini
        result = summarize_conversation({
            "messages": conversation["messages"]
        })

        # 3. Return summary to frontend
        return {
            "title": conversation["title"],
            "message_count": conversation["message_count"],
            "summary": result
        }

    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception as e:

        print(
            "ERROR:",
            repr(e)
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to process conversation."
        )
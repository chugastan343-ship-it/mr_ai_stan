import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="MR AI Stan API", version="1.0.0")

# Ruhusu maombi kutoka kwenye Chrome Extension (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    prompt: str

class ChatResponse(BaseModel):
    status: str
    reply: str

@app.get("/")
async def root():
    return {"status": "online", "message": "MR AI Stan Engine Active"}

@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    if not payload.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")
    
    # Process AI Logic au Output
    response_text = f"MR AI Stan Response: {payload.prompt}"
    return ChatResponse(status="success", reply=response_text)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)

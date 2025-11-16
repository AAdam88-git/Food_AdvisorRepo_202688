import os, httpx
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field, validator
from typing import Literal, List
import psycopg2

app = FastAPI(title="Meal‑Planner API")

# -------------------------------------------------
#  Database helper
# -------------------------------------------------
def get_db():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    try:
        yield conn
    finally:
        conn.close()

# -------------------------------------------------
#  Input models
# -------------------------------------------------
class UserProfile(BaseModel):
    height_cm: int = Field(..., gt=0)
    weight_kg: float = Field(..., gt=0)
    daily_budget_egp: float = Field(..., gt=0)
    goal: Literal["lose_weight", "gain_weight"]

class RecommendationRequest(BaseModel):
    profile: UserProfile

# -------------------------------------------------
#  Prompt building helpers
# -------------------------------------------------
def fetch_affordable_items(conn, budget) -> List[dict]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT r.name, m.item_en, m.item_ar, m.price_egp
        FROM menu_item m
        JOIN restaurant r ON m.restaurant_id = r.id
        WHERE m.price_egp <= %s
        ORDER BY random()
        LIMIT 30;
        """,
        (budget,)
    )
    rows = cur.fetchall()
    cur.close()
    return [
        {"restaurant": r, "en": e, "ar": a, "price": float(p)}
        for r, e, a, p in rows
    ]

def build_prompt(profile: UserProfile, items: List[dict]) -> str:
    profile_line = (
        f"Height: {profile.height_cm} cm, Weight: {profile.weight_kg} kg, "
        f"Budget: {profile.daily_budget_egp} EGP per day, "
        f"Goal: {'lose weight' if profile.goal == 'lose_weight' else 'gain weight'}."
    )
    table = ["| Restaurant | Item (EN) | Item (AR) | Price (EGP) |",
             "|------------|-----------|-----------|------------|"]
    for it in items:
        table.append(
            f"| {it['restaurant']} | {it['en']} | {it['ar']} | {it['price']:.2f} |"
        )
    menu_table = "\n".join(table)

    instruction = (
        "Using the table above, propose a full‑day meal plan (breakfast, lunch, dinner, up to two snacks) "
        "that fits the budget and the user’s goal. For each dish list restaurant, English & Arabic name, price, "
        "and a short nutrition note (e.g., high‑protein, low‑carb). End with the total daily cost and a friendly motivational closing."
    )
    return f"{profile_line}\n\n{menu_table}\n\n{instruction}"

# -------------------------------------------------
#  LLM call – Hugging Face Inference API (free tier)
# -------------------------------------------------
HF_TOKEN = os.getenv("HF_API_TOKEN")
HF_MODEL = os.getenv("HF_MODEL", "EleutherAI/gpt-j-6b")
HF_ENDPOINT = f"https://api-inference.huggingface.co/models/{HF_MODEL}"

async def call_hf(prompt: str) -> str:
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": prompt, "parameters": {"max_new_tokens": 500, "temperature": 0.7}}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(HF_ENDPOINT, json=payload, headers=headers)
        if resp.status_code == 429:
            raise HTTPException(status_code=429, detail="HF free‑tier token quota exceeded")
        resp.raise_for_status()
        return resp.json()[0]["generated_text"]

# -------------------------------------------------
#  Endpoint
# -------------------------------------------------
@app.post("/recommend")
async def recommend(req: RecommendationRequest, db=Depends(get_db)):
    items = fetch_affordable_items(db, req.profile.daily_budget_egp)
    if not items:
        raise HTTPException(404, "No menu items within budget")
    prompt = build_prompt(req.profile, items)
    llm_answer = await call_hf(prompt)
    # Strip the original prompt if the model echoed it back
    if llm_answer.startswith(prompt):
        llm_answer = llm_answer[len(prompt):].strip()
    return {"email_body": llm_answer}

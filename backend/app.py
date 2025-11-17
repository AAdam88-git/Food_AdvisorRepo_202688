#!/usr/bin/env python3
# app.py – single‑file Flask app for healthy‑food recommendation

from flask import Flask, request, jsonify, abort
from sqlalchemy import (
    create_engine, Column, Integer, Float, String, ForeignKey, select
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import os

# -------------------------------------------------------------
# Configuration – use env var supplied by Railway
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dev.db")  # fallback for local dev

# -------------------------------------------------------------
# Database setup
Base = declarative_base()
engine = create_engine(DATABASE_URL, echo=False,
                       connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(bind=engine)

class Restaurant(Base):
    __tablename__ = "restaurants"
    id      = Column(Integer, primary_key=True)
    name    = Column(String, nullable=False, unique=True)
    address = Column(String)
    phone   = Column(String)
    menu    = relationship("MenuItem", back_populates="restaurant", cascade="all, delete-orphan")

class MenuItem(Base):
    __tablename__ = "menu_items"
    id            = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"))
    name          = Column(String, nullable=False)
    calories      = Column(Integer)      # kcal
    protein_g     = Column(Float)
    carbs_g       = Column(Float)
    fats_g        = Column(Float)
    price_usd     = Column(Float)

    restaurant = relationship("Restaurant", back_populates="menu")

# Create tables on first run (fine for the free tier, no migrations needed)
Base.metadata.create_all(bind=engine)

# -------------------------------------------------------------
# Flask setup
app = Flask(__name__)

# -------------------------------------------------------------
# Utility: simple AI logic – calories target
def compute_target_calories(weight_kg: float, goal: str) -> int:
    """
    Very naive estimate:
    - Tolerable daily gain: +500 kcal
    - Tolerable daily loss: -500 kcal
    """
    RMR = 10 * weight_kg + 6.25 * 175 - 5 * 30 + 5  # crude BMR (age 30, male)
    delta = 500 if goal == "gain" else -500
    return int(RMR + delta)

# -------------------------------------------------------------
@app.route("/restaurants", methods=["GET"])
def get_restaurants():
    session = SessionLocal()
    restaurants = session.query(Restaurant).all()
    data = [
        {"id": r.id, "name": r.name, "address": r.address, "phone": r.phone}
        for r in restaurants
    ]
    session.close()
    return jsonify(data), 200

# -------------------------------------------------------------
@app.route("/recommend", methods=["POST"])
def recommend():
    """
    Expected JSON:
    {
        "tall_cm": 175,
        "weight_kg": 70,
        "budget_usd": 12,
        "goal": "lose" | "gain",
        "restaurant_id": <int | null>
    }
    """
    payload = request.get_json()
    if not payload:
        abort(400, "Missing JSON payload")

    try:
        tall_cm      = float(payload.get("tall_cm"))
        weight_kg    = float(payload.get("weight_kg"))
        budget_usd   = float(payload.get("budget_usd"))
        goal         = payload.get("goal").lower()
        restaurant_id = payload.get("restaurant_id")
    except Exception as e:
        abort(400, f"Invalid payload: {e}")

    if goal not in ("gain", "lose"):
        abort(400, "Goal must be 'gain' or 'lose'")

    # 1. Pick target calories
    target_cal = compute_target_calories(weight_kg, goal)

    # 2. Build query
    session = SessionLocal()
    q = session.query(MenuItem)

    if restaurant_id:
        q = q.filter(MenuItem.restaurant_id == restaurant_id)

    # Keep price within budget and a very rough calorie bracket
    # (this is just a toy example – tweak as needed)
    q = q.filter(
        MenuItem.price_usd <= budget_usd,
        MenuItem.calories <= target_cal + 200,
        MenuItem.calories >= target_cal - 200,
    )

    items = q.limit(10).all()  # top 10 similar calories
    res = [
        {
            "name": i.name,
            "calories": i.calories,
            "protein_g": i.protein_g,
            "carbs_g": i.carbs_g,
            "fats_g": i.fats_g,
            "price_usd": i.price_usd,
            "restaurant_id": i.restaurant_id,
            "restaurant_name": i.restaurant.name,
        }
        for i in items
    ]
    session.close()
    return jsonify(res), 200

# -------------------------------------------------------------
if __name__ == "__main__":
    # 8000 is the port that Railway assigns automatically
    port = int

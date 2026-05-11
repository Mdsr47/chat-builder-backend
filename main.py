from typing import Optional
from fastapi import FastAPI, UploadFile, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta, timezone
import os
import httpx

from ingest import read_pdf, read_url, chunk_text
from retriever import add_documents, search, load_index, delete_store
from llm import generate_answer, analyze_intent
from database import SessionLocal
from models import (
    User, Conversation, Chatbot, FAQ, Category, ApiKey, Lead, TrainingSource,
    Subscription, Transaction, Availability, Meeting,
    SocialAccount, ChatbotChannel, SocialConversation, SocialMessage,
    WebhookEvent, AutomationRule
)
from auth import hash_password, verify_password
from jwt_handler import create_access_token
from schemas import (
    FAQRequest, LoginRequest, SignupRequest, ChatbotCreate,
    ApiKeyCreate, ApiKeyOut, LeadCreate, LeadOut, TrainingSourceOut,
    ProfileOut, ProfileUpdate, PlanOut, SubscriptionOut, TransactionOut,
    PaddleWebhookEvent, TrialStatusOut, AvailabilityUpdate, AvailabilityOut, MeetingOut,
    SocialAccountOut, ChatbotChannelCreate, ChatbotChannelOut,
    AutomationRuleCreate, AutomationRuleOut
)
from dependencies import get_current_user
from fastapi.responses import Response, HTMLResponse
import requests
from dotenv import load_dotenv
load_dotenv()

from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles


app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
# app.mount("/static", StaticFiles(directory="static"), name="static")
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
# Templates folder
templates = Jinja2Templates(directory="templates")

@app.get("/privacy-policy", response_class=HTMLResponse)
async def privacy_policy(request: Request):
    return templates.TemplateResponse(
        request,
        "privacy_policy.html",
        {
            "request": request,
            "app_name": "Your App Name",
            "company_name": "Your Company Name",
            "email": "support@yourdomain.com",
        },
    )

# CORS
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:8000", "http://localhost:8080"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

load_index()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



@app.get("/")
async def root(request: Request):
    # Get client IP
    # client_ip = request.client.host
    
    client_ip = request.headers.get("x-forwarded-for")
    if client_ip:
        client_ip = client_ip.split(",")[0]
    else:
        client_ip = request.client.host

    # Call IP geolocation API
    response = requests.get(f"https://ipapi.co/{client_ip}/json/").json()

    return {
        "ip": client_ip,
        "city": response.get("city"),
        "region": response.get("region"),
        "country": response.get("country_name"),
        "latitude": response.get("latitude"),
        "longitude": response.get("longitude"),
        "org": response.get("org"),
    }


# @app.get("/")
# async def root(request: Request):
#     # Get client IP
#     client_ip = request.client.host

#     # Fetch geo data
#     response = requests.get(f"https://ipapi.co/{client_ip}/json/").json()

#     # Print in terminal
#     print("\n--- Visitor Info ---")
#     print(f"IP: {client_ip}")
#     print(f"City: {response.get('city')}")
#     print(f"Country: {response.get('country_name')}")
#     print(f"Latitude: {response.get('latitude')}")
#     print(f"Longitude: {response.get('longitude')}")
#     print("--------------------\n")

#     return {"message": "Check terminal logs"}
# ============================================================
# WIDGET JS
# ============================================================
@app.get("/widget.js")
def serve_widget():
    js_code = """
(function () {
  const script = document.querySelector('script[data-bot-id]');
  const botId = script ? script.getAttribute('data-bot-id') : null;
  if (!botId) return;

  // ── Styles ──────────────────────────────────────────────
  const style = document.createElement('style');
  style.textContent = `
    #cg-bubble {
      position: fixed; bottom: 24px; right: 24px;
      height: 60px; border-radius: 30px;
      padding: 0 24px;
      background: #6366f1; border: none; cursor: pointer;
      display: flex; align-items: center; justify-content: center; gap: 8px;
      box-shadow: 0 4px 20px rgba(99,102,241,0.45);
      z-index: 9999; transition: transform 0.2s, box-shadow 0.2s;
    }
    #cg-bubble:hover { transform: scale(1.04); box-shadow: 0 6px 28px rgba(99,102,241,0.55); }
    #cg-bubble .cg-pulse {
      position: absolute; width: 60px; height: 60px; border-radius: 50%;
      background: rgba(99,102,241,0.35);
      animation: cgPulse 2s ease-out infinite;
    }
    @keyframes cgPulse {
      0%   { transform: scale(1);   opacity: 0.8; }
      70%  { transform: scale(1.6); opacity: 0;   }
      100% { transform: scale(1.6); opacity: 0;   }
    }
    #cg-bubble .cg-text {
      color: #fff; font-size: 16px; font-weight: 600; font-family: system-ui,sans-serif;
    }
    #cg-frame-wrap {
      position: fixed; bottom: 96px; right: 24px;
      width: 370px; height: 560px;
      z-index: 9998; border-radius: 18px;
      box-shadow: 0 8px 40px rgba(0,0,0,0.18);
      overflow: hidden;
      transform: translateY(20px) scale(0.97);
      opacity: 0; pointer-events: none;
      transition: transform 0.28s cubic-bezier(.4,0,.2,1), opacity 0.28s ease;
    }
    #cg-frame-wrap.cg-open {
      transform: translateY(0) scale(1);
      opacity: 1; pointer-events: all;
    }
    #cg-frame { width: 100%; height: 100%; border: none; border-radius: 18px; }
  `;
  document.head.appendChild(style);

  // ── Bubble ──────────────────────────────────────────────
  const bubble = document.createElement('button');
  bubble.id = 'cg-bubble';
  bubble.setAttribute('aria-label', 'Open chat');
  bubble.innerHTML = `
    <span class="cg-pulse"></span>
    <svg width="26" height="26" viewBox="0 0 24 24" fill="white" xmlns="http://www.w3.org/2000/svg">
      <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/>
    </svg>
    <span class="cg-text">asks chatiii</span>
  `;

  // ── Iframe wrapper ───────────────────────────────────────
  const wrap = document.createElement('div');
  wrap.id = 'cg-frame-wrap';
  const iframe = document.createElement('iframe');
  iframe.id = 'cg-frame';
  iframe.src = `http://localhost:8080/widget?bot_id=${botId}`;
  iframe.title = 'Chat';
  wrap.appendChild(iframe);

  document.body.appendChild(wrap);
  document.body.appendChild(bubble);

  // ── Toggle logic ─────────────────────────────────────────
  let isOpen = false;
  bubble.addEventListener('click', function () {
    isOpen = !isOpen;
    var svg = bubble.querySelector('svg');
    if (isOpen) {
      wrap.classList.add('cg-open');
      bubble.setAttribute('aria-label', 'Close chat');
      // Swap icon to X
      svg.innerHTML = '<path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" fill="white"/>';
      var textEl = bubble.querySelector('.cg-text');
      if (textEl) textEl.style.display = 'none';
      bubble.style.padding = '0';
      bubble.style.width = '60px';
    } else {
      wrap.classList.remove('cg-open');
      bubble.setAttribute('aria-label', 'Open chat');
      // Restore chat icon
      svg.innerHTML = '<path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z" fill="white"/>';
      var textEl = bubble.querySelector('.cg-text');
      if (textEl) textEl.style.display = 'block';
      bubble.style.padding = '0 24px';
      bubble.style.width = 'auto';
    }
  });
})();
"""
    return Response(content=js_code, media_type="application/javascript")


# ============================================================
# AUTH
# ============================================================
@app.post("/auth/signup")
def signup(data: SignupRequest, db: Session = Depends(get_db)):
    if data.password != data.confirmPassword:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        first_name=data.firstName,
        last_name=data.lastName,
        email=data.email,
        password=hash_password(data.password)
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # ── Auto-create 7-day free trial ──
    trial_sub = Subscription(
        user_id=user.id,
        plan="free",
        status="trialing",
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=7)
    )
    db.add(trial_sub)
    db.commit()

    return {"message": "User created successfully"}

@app.post("/auth/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.email == data.email).first()

        if not user or not verify_password(data.password, user.password):
            raise HTTPException(status_code=400, detail="Invalid email or password")

        token = create_access_token({"sub": str(user.id)})

        return {
            "access_token": token,
            "token_type": "bearer"
        }

    except Exception as e:
        print("LOGIN ERROR:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# PROFILE
# ============================================================
@app.get("/profile", response_model=ProfileOut)
def get_profile(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "company": user.company
    }

@app.put("/profile")
def update_profile(
    data: ProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    user.first_name = data.first_name
    user.last_name = data.last_name
    user.email = data.email
    user.company = data.company
    
    if data.password:
        user.password = hash_password(data.password)
        
    db.commit()
    return {"message": "Profile updated"}


# ============================================================
# BILLING
# ============================================================

# ── Paddle Config ──────────────────────────────────────────
PADDLE_API_KEY = os.getenv("PADDLE_API_KEY", "")  # Set in env: your Paddle secret key
PADDLE_BASE_URL = "https://sandbox-api.paddle.com"  # Change to https://api.paddle.com for production

PRICE_ID_TO_PLAN = {
    "pri_01kpd57fen551c0wm1zz9be4qf": "starter",
    "pri_sandbox_pro_monthly": "pro",
    "pri_sandbox_agency_monthly": "agency"
}

PLAN_NAMES = {
    "free": "Free Trial",
    "starter": "Starter",
    "pro": "Pro",
    "agency": "Agency"
}

# Chatbot limits per plan (-1 = unlimited)
PLAN_CHATBOT_LIMITS: dict[str, int] = {
    "free": 1,
    "starter": 1,
    "pro": 10,
    "agency": -1,
}

PLAN_MESSAGE_LIMITS: dict[str, int] = {
    "free": 5,
    "starter": 1000,
    "pro": 10000,
    "agency": 100000,
}

def get_plan_message_limit(plan: str) -> int:
    return PLAN_MESSAGE_LIMITS.get(plan, 5)


def get_plan_chatbot_limit(plan: str) -> int:
    """Return the max chatbots allowed for the given plan (-1 = unlimited)."""
    return PLAN_CHATBOT_LIMITS.get(plan, 1)


@app.get("/billing/plans", response_model=list[PlanOut])
def list_plans():
    return [
        {
            "id": "starter",
            "name": "Starter",
            "price": "$29",
            "period": "/mo",
            "features": ["1 Chatbot", "1,000 messages/mo", "Basic analytics", "Email support"],
            "price_id": "pri_01kpd57fen551c0wm1zz9be4qf"
        },
        {
            "id": "pro",
            "name": "Pro",
            "price": "$79",
            "period": "/mo",
            "features": ["10 Chatbots", "10,000 messages/mo", "Advanced analytics", "Priority support", "Custom branding"],
            "price_id": "pri_sandbox_pro_monthly"
        },
        {
            "id": "agency",
            "name": "Agency",
            "price": "$199",
            "period": "/mo",
            "features": ["Unlimited Chatbots", "100,000 messages/mo", "White-label", "API access", "Dedicated account manager"],
            "price_id": "pri_sandbox_agency_monthly"
        }
    ]


@app.get("/billing/subscription", response_model=Optional[SubscriptionOut])
def get_subscription(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    if not sub:
        return None
    # If trialing and trial has expired, auto-update status
    # SQLite stores naive datetimes, so compare with naive UTC
    if sub.status == "trialing" and sub.trial_ends_at:
        trial_end_naive = sub.trial_ends_at.replace(tzinfo=None) if sub.trial_ends_at.tzinfo else sub.trial_ends_at
        now_naive = datetime.utcnow()
        if trial_end_naive < now_naive:
            sub.status = "expired"
            db.commit()
    return sub


@app.get("/billing/trial-status", response_model=TrialStatusOut)
def get_trial_status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    if not sub or sub.status not in ("trialing", "expired"):
        return TrialStatusOut(
            is_trial=False,
            trial_active=False,
            days_remaining=0,
            trial_ends_at=None
        )
    # SQLite stores naive datetimes — compare as naive UTC throughout
    now_naive = datetime.utcnow()
    trial_end_naive = sub.trial_ends_at.replace(tzinfo=None) if sub.trial_ends_at and sub.trial_ends_at.tzinfo else sub.trial_ends_at
    days_left = max(0, (trial_end_naive - now_naive).days) if trial_end_naive else 0
    trial_active = sub.status == "trialing" and days_left > 0
    return TrialStatusOut(
        is_trial=True,
        trial_active=trial_active,
        days_remaining=days_left,
        trial_ends_at=sub.trial_ends_at
    )


@app.get("/billing/transactions", response_model=list[TransactionOut])
def get_transactions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Transaction).filter(Transaction.user_id == user.id).order_by(Transaction.billed_at.desc()).all()


@app.get("/billing/limits")
def get_billing_limits(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Return the user's current plan limits and usage."""
    sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    plan = sub.plan if sub else "free"
    status = sub.status if sub else "trialing"

    chatbot_limit = get_plan_chatbot_limit(plan)
    chatbot_count = db.query(Chatbot).filter(Chatbot.user_id == user.id).count()
    
    message_limit = get_plan_message_limit(plan)
    message_count = sub.message_count if sub else 0

    return {
        "plan": plan,
        "status": status,
        "chatbots": {
            "used": chatbot_count,
            "limit": chatbot_limit,          # -1 means unlimited
            "remaining": -1 if chatbot_limit == -1 else max(0, chatbot_limit - chatbot_count),
            "can_create": chatbot_limit == -1 or chatbot_count < chatbot_limit,
        },
        "messages": {
            "used": message_count,
            "limit": message_limit,
            "remaining": max(0, message_limit - message_count),
            "can_send": message_count < message_limit,
        }
    }


@app.post("/billing/cancel")
async def cancel_subscription(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Schedule subscription cancellation at end of current billing period."""
    sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    if not sub:
        raise HTTPException(404, "No active subscription found")
    if sub.status not in ("active", "past_due"):
        raise HTTPException(400, f"Cannot cancel subscription with status: {sub.status}")
    if sub.cancel_at_period_end:
        raise HTTPException(400, "Subscription is already scheduled to cancel")

    # Call Paddle API to schedule cancellation at period end
    if sub.paddle_subscription_id and PADDLE_API_KEY:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{PADDLE_BASE_URL}/subscriptions/{sub.paddle_subscription_id}/cancel",
                json={"effective_from": "next_billing_period"},
                headers={
                    "Authorization": f"Bearer {PADDLE_API_KEY}",
                    "Content-Type": "application/json"
                }
            )
            if resp.status_code not in (200, 202):
                print(f"Paddle cancel error: {resp.status_code} {resp.text}")
                raise HTTPException(502, "Failed to cancel subscription with Paddle")

    # Mark in DB immediately so UI updates
    sub.cancel_at_period_end = True
    db.commit()
    return {"message": "Subscription will be cancelled at end of billing period", "cancels_on": sub.current_period_end}


@app.post("/billing/reactivate")
async def reactivate_subscription(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Reactivate a subscription that was scheduled to cancel (but hasn't yet)."""
    sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    if not sub:
        raise HTTPException(404, "No subscription found")
    if not sub.cancel_at_period_end:
        raise HTTPException(400, "Subscription is not scheduled to cancel")
    if sub.status == "canceled":
        raise HTTPException(400, "Subscription already cancelled. Please subscribe again.")

    # Call Paddle API to stop the pending cancellation
    if sub.paddle_subscription_id and PADDLE_API_KEY:
        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f"{PADDLE_BASE_URL}/subscriptions/{sub.paddle_subscription_id}",
                json={"scheduled_change": None},
                headers={
                    "Authorization": f"Bearer {PADDLE_API_KEY}",
                    "Content-Type": "application/json"
                }
            )
            if resp.status_code not in (200, 202):
                print(f"Paddle reactivate error: {resp.status_code} {resp.text}")
                raise HTTPException(502, "Failed to reactivate subscription with Paddle")

    sub.cancel_at_period_end = False
    db.commit()
    return {"message": "Subscription reactivated successfully"}


@app.post("/billing/paddle-webhook")
async def paddle_webhook(event: PaddleWebhookEvent, db: Session = Depends(get_db)):
    data = event.data
    event_type = event.event_type

    print(f"[Paddle Webhook] Event: {event_type}")

    # ── Extract user_id from custom_data ──────────────────
    custom_data = data.get("custom_data") or {}
    user_id = custom_data.get("user_id")

    if not user_id and event_type.startswith("subscription."):
        # Fallback: look up by paddle subscription ID
        paddle_sub_id = data.get("id")
        if paddle_sub_id:
            existing = db.query(Subscription).filter(
                Subscription.paddle_subscription_id == paddle_sub_id
            ).first()
            if existing:
                user_id = existing.user_id

    if not user_id:
        print(f"[Paddle Webhook] No user_id found for event {event_type}, data keys: {list(data.keys())}")
        return {"status": "ignored"}

    # ── Subscription Events ───────────────────────────────
    if event_type in (
        "subscription.created", "subscription.activated", "subscription.updated",
        "subscription.past_due", "subscription.paused", "subscription.resumed",
        "subscription.canceled", "subscription.trialing"
    ):
        sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
        if not sub:
            sub = Subscription(user_id=user_id)
            db.add(sub)

        sub.paddle_subscription_id = data.get("id")
        sub.paddle_customer_id = data.get("customer_id")

        # Map Paddle status to our status
        paddle_status = data.get("status", "")
        STATUS_MAP = {
            "active": "active",
            "trialing": "trialing",
            "past_due": "past_due",
            "paused": "paused",
            "canceled": "canceled"
        }
        if paddle_status in STATUS_MAP:
            sub.status = STATUS_MAP[paddle_status]

        # subscription.canceled — keep active until period end
        if event_type == "subscription.canceled":
            sub.status = "active"       # Still active until period ends
            sub.cancel_at_period_end = True
            print(f"[Billing] Sub {sub.paddle_subscription_id} scheduled to cancel at period end")

        # subscription.activated / resumed — clear cancel flag
        if event_type in ("subscription.activated", "subscription.resumed"):
            sub.status = "active"
            sub.cancel_at_period_end = False

        # Billing cycle
        billing_cycle_data = data.get("billing_cycle")
        if billing_cycle_data and isinstance(billing_cycle_data, dict):
            sub.billing_cycle = billing_cycle_data.get("interval")

        # Next billing date (= current period end)
        next_billed_at = data.get("next_billed_at")
        if next_billed_at:
            try:
                sub.current_period_end = datetime.fromisoformat(next_billed_at.replace("Z", "+00:00"))
            except Exception as e:
                print(f"[Billing] Error parsing next_billed_at: {e}")

        # Resolve plan from price_id
        items = data.get("items", [])
        if items:
            price_id = items[0].get("price", {}).get("id") or items[0].get("price_id", "")
            if price_id in PRICE_ID_TO_PLAN:
                sub.plan = PRICE_ID_TO_PLAN[price_id]
            elif price_id:
                if "starter" in price_id.lower():  sub.plan = "starter"
                elif "pro" in price_id.lower():    sub.plan = "pro"
                elif "agency" in price_id.lower(): sub.plan = "agency"

        db.commit()
        print(f"[Billing] Sub updated: user={user_id} plan={sub.plan} status={sub.status} cancel_at_end={sub.cancel_at_period_end}")

    # ── Transaction Events ────────────────────────────────
    elif event_type == "transaction.completed":
        txn_id = data.get("id")
        existing_txn = db.query(Transaction).filter(Transaction.paddle_transaction_id == txn_id).first()
        if not existing_txn:
            # Build a human-readable description
            items = data.get("items", [])
            desc = None
            if items:
                price_id = items[0].get("price", {}).get("id", "")
                plan_name = PLAN_NAMES.get(PRICE_ID_TO_PLAN.get(price_id, ""), "Subscription")
                interval = items[0].get("price", {}).get("billing_cycle", {}).get("interval", "monthly")
                desc = f"{plan_name} Plan - {interval.capitalize()}"

            txn = Transaction(
                user_id=user_id,
                paddle_transaction_id=txn_id,
                amount=float(data.get("details", {}).get("totals", {}).get("total", 0)) / 100,
                currency=data.get("currency_code", "USD"),
                status="completed",
                description=desc
            )
            db.add(txn)
            db.commit()
            print(f"[Billing] Transaction recorded: user={user_id} amount={txn.amount} {txn.currency}")

    elif event_type == "transaction.payment_failed":
        txn_id = data.get("id")
        existing_txn = db.query(Transaction).filter(Transaction.paddle_transaction_id == txn_id).first()
        if not existing_txn:
            txn = Transaction(
                user_id=user_id,
                paddle_transaction_id=txn_id,
                amount=float(data.get("details", {}).get("totals", {}).get("total", 0)) / 100,
                currency=data.get("currency_code", "USD"),
                status="failed",
                description="Payment failed"
            )
            db.add(txn)
            db.commit()
            print(f"[Billing] Payment failed recorded: user={user_id}")

    return {"status": "ok"}


# ============================================================
# DASHBOARD
# ============================================================
@app.get("/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    chatbot_ids = [c.id for c in db.query(Chatbot).filter(Chatbot.user_id == user.id).all()]
    
    if not chatbot_ids:
        chart_data = []
        for i in range(11, -1, -1):
            day = datetime.date.today() - datetime.timedelta(days=i)
            chart_data.append({"date": day.strftime("%b %d"), "chats": 0})
        return {
            "totalChats": 0,
            "activeBots": 0,
            "totalLeads": 0,
            "resolutionRate": "0%",
            "chartData": chart_data,
            "topQuestions": [],
            "recentConversations": []
        }

    total_chats = db.query(Conversation).filter(Conversation.chatbot_id.in_(chatbot_ids)).count()
    active_bots = len(chatbot_ids)
    total_leads = db.query(Lead).filter(Lead.chatbot_id.in_(chatbot_ids)).count()
    
    chart_data = []
    for i in range(11, -1, -1):
        import datetime as dt_module
        day = dt_module.date.today() - dt_module.timedelta(days=i)
        start_date = dt_module.datetime.combine(day, dt_module.time.min)
        end_date = start_date + dt_module.timedelta(days=1)
        count = db.query(Conversation).filter(
            Conversation.chatbot_id.in_(chatbot_ids),
            Conversation.created_at >= start_date,
            Conversation.created_at < end_date
        ).count()
        chart_data.append({"date": day.strftime("%b %d"), "chats": count})
        
    top_questions = db.query(
        Conversation.user_message,
        func.count(Conversation.id).label("count")
    ).filter(Conversation.chatbot_id.in_(chatbot_ids)).group_by(Conversation.user_message).order_by(func.count(Conversation.id).desc()).limit(5).all()
    
    recent_convs = db.query(Conversation).filter(Conversation.chatbot_id.in_(chatbot_ids)).order_by(Conversation.created_at.desc()).limit(5).all()
    recent_result = []
    for c in recent_convs:
        chatbot = db.query(Chatbot).filter(Chatbot.id == c.chatbot_id).first()
        recent_result.append({
            "id": c.id,
            "visitorName": "Visitor",
            "chatbotName": chatbot.name if chatbot else "Unknown",
            "lastMessage": c.user_message,
            "status": "active"
        })

    return {
        "totalChats": total_chats,
        "activeBots": active_bots,
        "totalLeads": total_leads,
        "resolutionRate": "94%",
        "chartData": chart_data,
        "topQuestions": [{"question": q[0], "count": q[1]} for q in top_questions],
        "recentConversations": recent_result
    }

@app.get("/analytics/stats")
def get_analytics_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    chatbot_ids = [c.id for c in db.query(Chatbot).filter(Chatbot.user_id == user.id).all()]
    
    if not chatbot_ids:
        import datetime as dt_module
        chat_volume = []
        resolution_rate = []
        for i in range(13, -1, -1):
            day = dt_module.date.today() - dt_module.timedelta(days=i)
            chat_volume.append({"date": day.strftime("%b %d"), "chats": 0})
            resolution_rate.append({"date": day.strftime("%b %d"), "rate": 0})

        return {
            "chatVolume": chat_volume,
            "resolutionRate": resolution_rate,
            "satisfaction": [],
            "topQuestions": [],
        }
    
    # Chat Volume (last 14 days)
    chat_volume = []
    import datetime as dt_module
    for i in range(13, -1, -1):
        day = dt_module.date.today() - dt_module.timedelta(days=i)
        start_date = dt_module.datetime.combine(day, dt_module.time.min)
        end_date = start_date + dt_module.timedelta(days=1)
        count = db.query(Conversation).filter(
            Conversation.chatbot_id.in_(chatbot_ids),
            Conversation.created_at >= start_date,
            Conversation.created_at < end_date
        ).count()
        chat_volume.append({"date": day.strftime("%b %d"), "chats": count})
    
    # Top Questions
    top_questions = db.query(
        Conversation.user_message,
        func.count(Conversation.id).label("count")
    ).filter(Conversation.chatbot_id.in_(chatbot_ids)).group_by(Conversation.user_message).order_by(func.count(Conversation.id).desc()).limit(5).all()

    # Mocked data for Resolution Rate & Satisfaction for now
    # In a real app, these would be calculated from conversation feedback/status
    resolution_rate = []
    for i in range(13, -1, -1):
        day = dt_module.date.today() - dt_module.timedelta(days=i)
        import random
        resolution_rate.append({"date": day.strftime("%b %d"), "rate": random.randint(85, 98)})

    satisfaction = [
        {"rating": "5 Stars", "count": 45},
        {"rating": "4 Stars", "count": 32},
        {"rating": "3 Stars", "count": 12},
        {"rating": "2 Stars", "count": 5},
        {"rating": "1 Star", "count": 3},
    ]

    return {
        "chatVolume": chat_volume,
        "resolutionRate": resolution_rate,
        "satisfaction": satisfaction,
        "topQuestions": [{"question": q[0], "count": q[1]} for q in top_questions],
    }


# ============================================================
# CATEGORIES
# ============================================================
@app.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).all()


# ============================================================
# API KEYS
# ============================================================
@app.post("/api-keys")
def save_api_key(
    data: ApiKeyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if data.provider not in ("groq", "openai", "claude"):
        raise HTTPException(400, "Provider must be groq, openai, or claude")
    
    # Upsert: delete existing key for same provider, then add new one
    existing = db.query(ApiKey).filter(
        ApiKey.user_id == user.id,
        ApiKey.provider == data.provider
    ).first()
    if existing:
        db.delete(existing)
    
    key = ApiKey(
        user_id=user.id,
        provider=data.provider,
        api_key=data.api_key
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    
    return {"message": f"{data.provider} API key saved", "id": key.id}

@app.get("/api-keys")
def list_api_keys(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    keys = db.query(ApiKey).filter(ApiKey.user_id == user.id).all()
    result = []
    for k in keys:
        masked = k.api_key[:8] + "•" * (len(k.api_key) - 12) + k.api_key[-4:]
        result.append({
            "id": k.id,
            "provider": k.provider,
            "masked_key": masked,
            "created_at": k.created_at
        })
    return result

@app.delete("/api-keys/{key_id}")
def delete_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    key = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.user_id == user.id).first()
    if not key:
        raise HTTPException(404, "API key not found")
    db.delete(key)
    db.commit()
    return {"message": "API key deleted"}


# ============================================================
# CHATBOTS
# ============================================================
@app.post("/chatbots")
def create_chatbot(
    data: ChatbotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # ── Plan limit check ────────────────────────────────────
    sub = db.query(Subscription).filter(Subscription.user_id == current_user.id).first()
    plan = sub.plan if sub else "free"
    chatbot_limit = get_plan_chatbot_limit(plan)
    chatbot_count = db.query(Chatbot).filter(Chatbot.user_id == current_user.id).count()

    if chatbot_limit != -1 and chatbot_count >= chatbot_limit:
        limit_label = f"{chatbot_limit} chatbot" + ("s" if chatbot_limit != 1 else "")
        raise HTTPException(
            status_code=403,
            detail=(
                f"Your {PLAN_NAMES.get(plan, plan)} plan allows {limit_label}. "
                f"Please upgrade your plan to create more chatbots."
            )
        )
    # ────────────────────────────────────────────────────────

    # Generate system instructions based on category
    system_instructions = None
    if data.category_id:
        category = db.query(Category).filter(Category.id == data.category_id).first()
        if category:
            if category.slug == "real_estate":
                system_instructions = (
                    "You are a helpful real estate assistant. Help visitors with property inquiries, "
                    "pricing, scheduling viewings, neighborhood information, and mortgage guidance. "
                    "Be professional and informative. Capture visitor interest in specific properties."
                )
            elif category.slug == "freelancer_agency":
                system_instructions = (
                    "You are a helpful business assistant for a freelancer/agency. Help visitors understand "
                    "services offered, pricing, portfolio, process, timelines, and how to get started. "
                    "Be professional and encourage visitors to book a consultation or request a quote."
                )

    chatbot = Chatbot(
        name=data.name,
        website=data.website,
        language=data.language,
        model=data.model,
        welcome_message=data.welcome_message,
        brand_color=data.brand_color,
        category_id=data.category_id,
        system_instructions=system_instructions,
        user_id=current_user.id
    )

    db.add(chatbot)
    db.commit()
    db.refresh(chatbot)

    return chatbot

@app.get("/chatbots")
def get_chatbots(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Chatbot).filter(Chatbot.user_id == current_user.id).all()

@app.get("/chatbots/{chatbot_id}")
def get_chatbot(chatbot_id: int, db: Session = Depends(get_db), user = Depends(get_current_user)):
    chatbot = db.query(Chatbot).filter(
        Chatbot.id == chatbot_id,
        Chatbot.user_id == user.id
    ).first()

    if not chatbot:
        raise HTTPException(status_code=404, detail="Chatbot not found")

    # Include category info
    result = {
        "id": chatbot.id,
        "name": chatbot.name,
        "website": chatbot.website,
        "language": chatbot.language,
        "model": chatbot.model,
        "welcome_message": chatbot.welcome_message,
        "brand_color": chatbot.brand_color,
        "system_instructions": chatbot.system_instructions,
        "category_id": chatbot.category_id,
        "category_name": chatbot.category.name if chatbot.category else None,
        "created_at": chatbot.created_at,
        "user_id": chatbot.user_id,
    }
    return result

@app.get("/public/chatbots/{chatbot_id}")
def get_chatbot_public(chatbot_id: int, db: Session = Depends(get_db)):
    chatbot = db.query(Chatbot).filter(Chatbot.id == chatbot_id).first()
    if not chatbot:
        raise HTTPException(status_code=404, detail="Chatbot not found")
    return {
        "id": chatbot.id,
        "name": chatbot.name,
        "welcome_message": chatbot.welcome_message,
        "brand_color": chatbot.brand_color,
        "model": chatbot.model,
        "category_slug": chatbot.category.slug if chatbot.category else None,
        "category_name": chatbot.category.name if chatbot.category else None,
    }

@app.delete("/chatbots/{chatbot_id}")
def delete_chatbot(chatbot_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    chatbot = db.query(Chatbot).filter(
        Chatbot.id == chatbot_id,
        Chatbot.user_id == user.id
    ).first()

    if not chatbot:
        raise HTTPException(404, "Chatbot not found")

    db.delete(chatbot)
    db.commit()
    delete_store(chatbot_id)

    return {"message": "Chatbot deleted"}


# ============================================================
# TRAINING (PDF, URL, FAQ)
# ============================================================
@app.post("/chatbots/{chatbot_id}/train/pdf")
async def train_pdf(
    chatbot_id: int,
    file: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    chatbot = db.query(Chatbot).filter(
        Chatbot.id == chatbot_id,
        Chatbot.user_id == user.id
    ).first()

    if not chatbot:
        raise HTTPException(404, "Chatbot not found")

    text = read_pdf(file.file)
    chunks = chunk_text(text)

    add_documents(chunks, source=file.filename, chatbot_id=chatbot_id)

    # Track training source
    source = TrainingSource(
        chatbot_id=chatbot_id,
        source_type="pdf",
        source_name=file.filename,
        char_count=len(text),
        chunk_count=len(chunks),
        status="completed"
    )
    db.add(source)
    db.commit()

    return {"message": "PDF trained", "chunks": len(chunks), "chars": len(text)}


class URLRequest(BaseModel):
    url: str

@app.post("/chatbots/{chatbot_id}/train/url")
def train_url(
    chatbot_id: int,
    body: URLRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    chatbot = db.query(Chatbot).filter(
        Chatbot.id == chatbot_id,
        Chatbot.user_id == user.id
    ).first()

    if not chatbot:
        raise HTTPException(404, "Chatbot not found")

    text = read_url(body.url)
    if isinstance(text, str) and text.startswith("Failed to fetch URL:"):
        raise HTTPException(status_code=400, detail=text)

    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(status_code=400, detail="No content could be extracted from the provided URL.")

    add_documents(chunks, source=body.url, chatbot_id=chatbot_id)

    # Track training source
    source = TrainingSource(
        chatbot_id=chatbot_id,
        source_type="url",
        source_name=body.url,
        char_count=len(text),
        chunk_count=len(chunks),
        status="completed"
    )
    db.add(source)
    db.commit()

    return {"message": "URL trained", "chunks": len(chunks), "chars": len(text)}

    # return {"message": "URL trained", "chunks": len(chunks), "chars": len(text)}


@app.post("/chatbots/{chatbot_id}/faqs")
def add_faq(
    chatbot_id: int,
    body: FAQRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    chatbot = db.query(Chatbot).filter(
        Chatbot.id == chatbot_id,
        Chatbot.user_id == user.id
    ).first()

    if not chatbot:
        raise HTTPException(404, "Chatbot not found")

    faq = FAQ(
        question=body.question,
        answer=body.answer,
        chatbot_id=chatbot_id
    )

    db.add(faq)
    db.commit()

    # Also add to vector DB
    add_documents(
        [f"Q: {body.question}\nA: {body.answer}"],
        source="faq",
        chatbot_id=chatbot_id
    )

    # Track training source
    source = TrainingSource(
        chatbot_id=chatbot_id,
        source_type="faq",
        source_name=f"FAQ: {body.question[:50]}",
        char_count=len(body.question) + len(body.answer),
        chunk_count=1,
        status="completed"
    )
    db.add(source)
    db.commit()

    return {"message": "FAQ added"}


# ============================================================
# TRAINING SOURCES
# ============================================================
@app.get("/chatbots/{chatbot_id}/training-sources")
def get_training_sources(
    chatbot_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    chatbot = db.query(Chatbot).filter(
        Chatbot.id == chatbot_id,
        Chatbot.user_id == user.id
    ).first()

    if not chatbot:
        raise HTTPException(404, "Chatbot not found")

    sources = db.query(TrainingSource).filter(
        TrainingSource.chatbot_id == chatbot_id
    ).order_by(TrainingSource.created_at.desc()).all()

    return sources


# from datetime import datetime

def is_subscription_valid(sub: Subscription) -> bool:
    if not sub:
        return True  # allow free fallback (handled by limits)

    now = datetime.utcnow()

    # Check trial or billing expiry
    if sub.trial_ends_at and now > sub.trial_ends_at:
        return False

    if sub.current_period_end and now > sub.current_period_end:
        return False

    return True


def has_message_quota(sub: Subscription) -> bool:
    plan = sub.plan if sub else "free"
    limit = get_plan_message_limit(plan)
    count = sub.message_count if sub else 0

    return count < limit

# ============================================================
# AVAILABILITY & MEETINGS
# ============================================================
@app.get("/availability", response_model=AvailabilityOut)
def get_availability(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    avail = db.query(Availability).filter(Availability.user_id == user.id).first()
    if not avail:
        default_json = '{"monday": ["09:00", "17:00"], "tuesday": ["09:00", "17:00"], "wednesday": ["09:00", "17:00"], "thursday": ["09:00", "17:00"], "friday": ["09:00", "17:00"]}'
        avail = Availability(user_id=user.id, schedule_json=default_json)
        db.add(avail)
        db.commit()
        db.refresh(avail)
    return avail

@app.put("/availability", response_model=AvailabilityOut)
def update_availability(data: AvailabilityUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    avail = db.query(Availability).filter(Availability.user_id == user.id).first()
    if not avail:
        avail = Availability(user_id=user.id)
        db.add(avail)
    avail.schedule_json = data.schedule_json
    db.commit()
    db.refresh(avail)
    return avail

@app.get("/meetings")
def list_meetings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    meetings = db.query(Meeting).filter(Meeting.user_id == user.id).order_by(Meeting.scheduled_time.asc()).all()
    result = []
    for m in meetings:
        chatbot = db.query(Chatbot).filter(Chatbot.id == m.chatbot_id).first()
        result.append({
            "id": m.id,
            "chatbot_id": m.chatbot_id,
            "chatbot_name": chatbot.name if chatbot else "Unknown",
            "visitor_name": m.visitor_name,
            "visitor_email": m.visitor_email,
            "scheduled_time": m.scheduled_time,
            "status": m.status,
            "session_id": m.session_id,
            "created_at": m.created_at
        })
    return result

# ============================================================
# QUERY (Public — for widget)
# ============================================================
@app.post("/public/chatbots/{chatbot_id}/query")
def query(chatbot_id: int, q: str, session_id: str = None, db: Session = Depends(get_db)):
    chatbot = db.query(Chatbot).filter(Chatbot.id == chatbot_id).first()
    if not chatbot:
        raise HTTPException(404, "Chatbot not found")

    # Check message limit
    # sub = db.query(Subscription).filter(Subscription.user_id == chatbot.user_id).first()
    # plan = sub.plan if sub else "free"
    # message_limit = get_plan_message_limit(plan)
    # message_count = sub.message_count if sub else 0
    
    # if message_count >= message_limit:
    #     return {
    #         "answer": "This chatbot has exceeded its message limit for the current billing cycle. Please contact the owner.",
    #         "sources": []
    #     }
    sub = db.query(Subscription).filter(
        Subscription.user_id == chatbot.user_id
    ).first()
    
    print("PLAN:", sub.plan if sub else "free")
    print("COUNT:", sub.message_count if sub else 0)
    print("LIMIT:", get_plan_message_limit(sub.plan if sub else "free"))
    print("TRIAL_END:", sub.trial_ends_at if sub else None)
    print("PERIOD_END:", sub.current_period_end if sub else None)

    # ❌ BLOCK CONDITION (single unified logic)
    if not is_subscription_valid(sub) or not has_message_quota(sub):
        return {
            "answer": "Limit reached. Please contact support.",
            "sources": []
        }
    
    # Increment message count (we will commit at the end)
    if sub:
        sub.message_count += 1
    elif chatbot.user_id:
        sub = Subscription(user_id=chatbot.user_id, plan="free", status="trialing", message_count=1)
        db.add(sub)
    
    # Search only in this chatbot's vector store
    context_docs = search(q, chatbot_id=chatbot_id)
    
    # Determine provider & API key from chatbot owner's saved keys
    provider = "groq"  # default
    api_key = None
    
    if chatbot.user_id:
        # Check model to determine provider preference
        model_lower = (chatbot.model or "").lower()
        if "gpt" in model_lower or "openai" in model_lower:
            provider = "openai"
        elif "claude" in model_lower:
            provider = "claude"
        
        # Get user's API key for this provider
        user_key = db.query(ApiKey).filter(
            ApiKey.user_id == chatbot.user_id,
            ApiKey.provider == provider
        ).first()
        
        if user_key:
            api_key = user_key.api_key
        elif provider != "groq":
            # Fallback to groq if no key for selected provider
            groq_key = db.query(ApiKey).filter(
                ApiKey.user_id == chatbot.user_id,
                ApiKey.provider == "groq"
            ).first()
            if groq_key:
                api_key = groq_key.api_key
            provider = "groq"
    
    # Fetch recent chat history
    chat_history = []
    if session_id:
        past_convos = (
            db.query(Conversation)
            .filter(Conversation.session_id == session_id)
            .order_by(Conversation.created_at.desc())
            .limit(10)
            .all()
        )
        for c in reversed(past_convos):
            chat_history.append({"role": "user", "content": c.user_message})
            chat_history.append({"role": "assistant", "content": c.bot_response})

    # Inject Availability
    import datetime as dt_module
    import json
    
    availability_str = ""
    if chatbot.user_id:
        avail = db.query(Availability).filter(Availability.user_id == chatbot.user_id).first()
        if avail:
            availability_str += f"Weekly Availability Schedule: {avail.schedule_json}\n"
        else:
            availability_str += "Weekly Availability Schedule: Monday to Friday, 09:00 to 17:00\n"
            
        now = dt_module.datetime.utcnow()
        end_date = now + dt_module.timedelta(days=7)
        booked = db.query(Meeting).filter(
            Meeting.user_id == chatbot.user_id,
            Meeting.scheduled_time >= now,
            Meeting.scheduled_time <= end_date,
            Meeting.status != "cancelled"
        ).all()
        
        if booked:
            availability_str += "Currently Booked Times (Do NOT offer these):\n"
            for b in booked:
                availability_str += f"- {b.scheduled_time.strftime('%Y-%m-%d %H:%M')}\n"
        else:
            availability_str += "Currently Booked Times: None\n"
            
        lead = None
        if session_id:
            lead = db.query(Lead).filter(Lead.session_id == session_id).first()
            
        known_user_info = ""
        if lead:
            known_user_info = f"Known user details:\nName: {lead.name}\nEmail: {lead.email}\nDo NOT ask for their name and email, you already know them."
        else:
            known_user_info = "You do NOT know the user's name and email yet. You MUST ask for them."
            
        booking_instructions = f"""
\n\n--- BOOKING INSTRUCTIONS ---
You can help the user book a meeting/consultation.
Today's date is: {now.strftime('%Y-%m-%d')}.
{availability_str}
{known_user_info}
If the user wants to book, ask for their preferred date and time (matching the schedule and avoiding booked times). If their name and email are not known, ask for them too.
Once they provide all necessary details, output EXACTLY this string at the very end of your response (and nothing else after it):
[BOOK_MEETING: name="<their_name>", email="<their_email>", time="<YYYY-MM-DDTHH:MM:SS>"]
Example: [BOOK_MEETING: name="John Doe", email="john@test.com", time="2026-05-06T14:30:00"]
-----------------------------
"""
        system_instructions_injected = (chatbot.system_instructions or "") + booking_instructions
    else:
        system_instructions_injected = chatbot.system_instructions

    answer = generate_answer(
        q, context_docs,
        provider=provider,
        api_key=api_key,
        system_instructions=system_instructions_injected,
        chat_history=chat_history
    )
    
    # Extract [BOOK_MEETING: ...]
    import re
    book_match = re.search(r'\[BOOK_MEETING:\s*name="([^"]*)",\s*email="([^"]*)",\s*time="([^"]+)"\]', answer)
    if book_match:
        name = book_match.group(1)
        email = book_match.group(2)
        time_str = book_match.group(3)
        
        # fallback to lead if name/email is empty or placeholder
        if session_id:
            lead = db.query(Lead).filter(Lead.session_id == session_id).first()
            if lead:
                if not name or name == "<their_name>" or name.lower() == "unknown":
                    name = lead.name
                if not email or email == "<their_email>" or email.lower() == "unknown":
                    email = lead.email
        try:
            scheduled_time = dt_module.datetime.fromisoformat(time_str)
            
            # Save meeting
            meeting = Meeting(
                user_id=chatbot.user_id,
                chatbot_id=chatbot.id,
                visitor_name=name,
                visitor_email=email,
                scheduled_time=scheduled_time,
                session_id=session_id
            )
            db.add(meeting)
            db.commit()
            print(f"[Booking] Meeting booked for {name} at {scheduled_time}")
            
            # Remove tag from answer
            answer = answer[:book_match.start()].strip()
            answer += "\n\nYour meeting has been successfully booked! We will send you an email confirmation shortly."
        except Exception as e:
            print(f"[Booking] Error parsing time or saving meeting: {e}")
            answer = answer[:book_match.start()].strip()
            answer += "\n\nSorry, I couldn't book the meeting due to a system error. Please try again later."
            
    try:
        convo = Conversation(
            chatbot_id=chatbot_id,
            user_message=q,
            bot_response=answer,
            session_id=session_id
        )
        db.add(convo)
        db.commit()
    except Exception as e:
        print("DB Error:", e)

    # ── High-intent analysis (background, non-blocking) ──────────────
    if session_id:
        try:
            # Fetch all messages in this session for intent analysis
            session_convos = (
                db.query(Conversation)
                .filter(Conversation.session_id == session_id)
                .order_by(Conversation.created_at.asc())
                .all()
            )
            messages_for_intent = []
            for c in session_convos:
                messages_for_intent.append({"role": "user", "text": c.user_message})
                messages_for_intent.append({"role": "bot", "text": c.bot_response})

            intent_score = analyze_intent(
                messages_for_intent,
                provider=provider,
                api_key=api_key
            )
            print(f"[Intent] session={session_id} intent={intent_score}")

            # Update the linked lead's intent field
            lead = db.query(Lead).filter(Lead.session_id == session_id).first()
            if lead:
                lead.intent = intent_score
                lead.intent_updated_at = datetime.utcnow()
                db.commit()
        except Exception as e:
            print(f"[Intent] Error during analysis: {e}")

    return {
        "answer": answer,
        "sources": list(set([doc["source"] for doc in context_docs]))
    }


# ============================================================
# LEADS
# ============================================================
@app.post("/public/chatbots/{chatbot_id}/leads")
def create_lead(
    chatbot_id: int,
    data: LeadCreate,
    db: Session = Depends(get_db)
):
    chatbot = db.query(Chatbot).filter(Chatbot.id == chatbot_id).first()
    if not chatbot:
        raise HTTPException(404, "Chatbot not found")
    
    lead = Lead(
        chatbot_id=chatbot_id,
        name=data.name,
        email=data.email,
        phone=data.phone,
        message=data.message,
        session_id=data.session_id  # link lead to chat session
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    
    return {"message": "Lead captured", "id": lead.id}

@app.get("/leads")
def list_leads(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # Get all chatbot IDs for this user
    chatbot_ids = [c.id for c in db.query(Chatbot).filter(Chatbot.user_id == user.id).all()]
    
    leads = db.query(Lead).filter(Lead.chatbot_id.in_(chatbot_ids)).order_by(Lead.created_at.desc()).all()
    
    result = []
    for lead in leads:
        chatbot = db.query(Chatbot).filter(Chatbot.id == lead.chatbot_id).first()
        result.append({
            "id": lead.id,
            "chatbot_id": lead.chatbot_id,
            "name": lead.name,
            "email": lead.email,
            "phone": lead.phone,
            "message": lead.message,
            "session_id": lead.session_id,
            "intent": lead.intent,
            "intent_updated_at": lead.intent_updated_at,
            "created_at": lead.created_at,
            "chatbot_name": chatbot.name if chatbot else "Unknown",
            "category_name": chatbot.category.name if chatbot and chatbot.category else None,
        })
    
    return result


# ============================================================
# CONVERSATIONS
# ============================================================
@app.get("/conversations/sessions")
def get_sessions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    chatbot_ids = [c.id for c in db.query(Chatbot).filter(Chatbot.user_id == user.id).all()]

    subq = (
        db.query(
            Conversation.session_id,
            Conversation.chatbot_id,
            func.max(Conversation.created_at).label("last_time"),
            func.count(Conversation.id).label("message_count"),
        )
        .filter(Conversation.chatbot_id.in_(chatbot_ids))
        .filter(Conversation.session_id.isnot(None))
        .group_by(Conversation.session_id, Conversation.chatbot_id)
        .subquery()
    )

    rows = db.query(subq).order_by(subq.c.last_time.desc()).all()

    result = []
    for row in rows:
        last_msg = (
            db.query(Conversation)
            .filter(Conversation.session_id == row.session_id)
            .order_by(Conversation.created_at.desc())
            .first()
        )
        chatbot = db.query(Chatbot).filter(Chatbot.id == row.chatbot_id).first()
        # Look up the lead linked to this session (if any)
        lead = db.query(Lead).filter(Lead.session_id == row.session_id).first()
        result.append({
            "session_id": row.session_id,
            "chatbot_id": row.chatbot_id,
            "chatbot_name": chatbot.name if chatbot else "Unknown",
            "last_message": last_msg.user_message[:60] if last_msg else "",
            "last_time": row.last_time,
            "message_count": row.message_count,
            "lead_name": lead.name if lead else None,
            "lead_email": lead.email if lead else None,
        })

    return result


@app.get("/conversations/session/{session_id}")
def get_session_messages(session_id: str, db: Session = Depends(get_db)):
    return (
        db.query(Conversation)
        .filter(Conversation.session_id == session_id)
        .order_by(Conversation.created_at.asc())
        .all()
    )
# ============================================================
# PLATFORM FEEDBACK
# ============================================================
from schemas import PlatformFeedbackCreate, PlatformFeedbackOut, CustomQuotationCreate, CustomQuotationOut, CustomQuotationUpdate
from models import PlatformFeedback, CustomQuotation

@app.post("/feedback")
def submit_feedback(data: PlatformFeedbackCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    feedback = PlatformFeedback(
        user_id=user.id,
        feedback_text=data.feedback_text,
        category=data.category
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return {"message": "Feedback submitted successfully", "id": feedback.id}

@app.get("/feedback", response_model=list[PlatformFeedbackOut])
def get_feedbacks(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(PlatformFeedback).order_by(PlatformFeedback.created_at.desc()).all()


# ============================================================
# CUSTOM QUOTATIONS
# ============================================================
@app.post("/quotations")
def create_quotation(data: CustomQuotationCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    quotation = CustomQuotation(
        user_id=user.id,
        requirements=data.requirements,
        budget=data.budget
    )
    db.add(quotation)
    db.commit()
    db.refresh(quotation)
    return {"message": "Quotation submitted", "id": quotation.id}

@app.get("/quotations", response_model=list[CustomQuotationOut])
def get_user_quotations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(CustomQuotation).filter(CustomQuotation.user_id == user.id).order_by(CustomQuotation.created_at.desc()).all()

@app.post("/quotations/{quotation_id}/pay")
def pay_quotation(quotation_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    quotation = db.query(CustomQuotation).filter(CustomQuotation.id == quotation_id, CustomQuotation.user_id == user.id).first()
    if not quotation:
        raise HTTPException(404, "Quotation not found")
    if quotation.status != "quoted":
        raise HTTPException(400, "Cannot pay for this quotation")
    
    # Mocking payment success
    quotation.status = "paid"
    db.commit()
    return {"message": "Payment successful"}

@app.get("/admin/quotations", response_model=list[CustomQuotationOut])
def admin_get_quotations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # In a real app, verify user is admin. For now, we return all.
    return db.query(CustomQuotation).order_by(CustomQuotation.created_at.desc()).all()

@app.put("/admin/quotations/{quotation_id}")
def admin_update_quotation(quotation_id: int, data: CustomQuotationUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # In a real app, verify user is admin.
    quotation = db.query(CustomQuotation).filter(CustomQuotation.id == quotation_id).first()
    if not quotation:
        raise HTTPException(404, "Quotation not found")
    
    if data.quoted_price is not None:
        quotation.quoted_price = data.quoted_price
        if quotation.status == "pending":
            quotation.status = "quoted"
    
    if data.status is not None:
        quotation.status = data.status
        
    if data.widget_script is not None:
        quotation.widget_script = data.widget_script
        
    db.commit()
    return {"message": "Quotation updated"}


# ============================================================
# INSTAGRAM / SOCIAL INTEGRATION
# ============================================================
from instagram import (
    build_oauth_url, exchange_code_for_token,
    get_instagram_accounts, subscribe_page_to_webhooks,
    send_dm, reply_to_comment,
    IG_VERIFY_TOKEN
)
import uuid as _uuid


# ── Step 1 – Get OAuth URL ───────────────────────────────────────────────────
@app.get("/instagram/oauth-url")
def instagram_oauth_url(user: User = Depends(get_current_user)):
    """Return the Facebook OAuth URL.  Frontend redirects the user here."""
    state = f"{user.id}:{_uuid.uuid4().hex}"
    return {"url": build_oauth_url(state)}


# ── Step 2 – OAuth Callback  (Facebook redirects here with ?code=…&state=…) ─
@app.get("/instagram/callback")
async def instagram_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db)
):
    """Exchange code for token, fetch IG accounts, persist them."""
    parts = state.split(":", 1)
    if len(parts) != 2:
        raise HTTPException(400, "Invalid state parameter")
    user_id = int(parts[0])
    print(f"[IG Callback] user_id={user_id}, code_snippet={code[:20]}...")

    # Exchange code → long-lived token
    try:
        token_data = await exchange_code_for_token(code)
        user_access_token = token_data["access_token"]
        print(f"[IG Callback] Token obtained OK (type={token_data.get('token_type')}, expires_in={token_data.get('expires_in')})")
    except Exception as e:
        print(f"[IG Callback] ❌ Token exchange FAILED: {e}")
        raise HTTPException(400, f"Token exchange failed: {str(e)}")

    # Get all IG business accounts for this FB user
    try:
        accounts = await get_instagram_accounts(user_access_token)
        print(f"[IG Callback] Accounts returned: {len(accounts)} → {accounts}")
    except Exception as e:
        print(f"[IG Callback] ❌ get_instagram_accounts FAILED: {e}")
        accounts = []

    if not accounts:
        print("[IG Callback] ⚠️  No Instagram Business accounts found. Possible causes:")
        print("  1. Instagram account is PERSONAL — must be Business or Creator")
        print("  2. Instagram not linked to a Facebook Page")
        print("  3. Missing permissions scope")

    saved = []
    for acc in accounts:
        existing = db.query(SocialAccount).filter(
            SocialAccount.user_id == user_id,
            SocialAccount.account_id == acc["ig_id"],
            SocialAccount.platform == "instagram"
        ).first()

        if existing:
            existing.access_token = acc["page_token"]
            existing.username = acc["username"]
            existing.profile_pic_url = acc.get("profile_pic_url")
            existing.is_active = True
            print(f"[IG Callback] Updated existing account: @{acc['username']} (ig_id={acc['ig_id']})")
        else:
            sa = SocialAccount(
                user_id=user_id,
                platform="instagram",
                account_id=acc["ig_id"],
                username=acc["username"],
                access_token=acc["page_token"],
                profile_pic_url=acc.get("profile_pic_url"),
            )
            db.add(sa)
            print(f"[IG Callback] ✅ Saved NEW account: @{acc['username']} (ig_id={acc['ig_id']})")
        saved.append({"ig_id": acc["ig_id"], "username": acc["username"]})

        # Auto-subscribe the page to webhooks
        try:
            await subscribe_page_to_webhooks(acc["page_id"], acc["page_token"])
            print(f"[IG Callback] Subscribed page {acc['page_id']} to webhooks")
        except Exception as e:
            print(f"[IG Webhook] subscribe failed for page {acc['page_id']}: {e}")

    db.commit()
    print(f"[IG Callback] Done. Saved={saved}")

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    html = f"""
    <html>
      <body>
        <script>
          const payload = {{ type: "instagram_connected" }};
          try {{
            if (window.opener) {{
              window.opener.postMessage(payload, "{frontend_url}");
              window.close();
            }} else {{
              window.location.href = "{frontend_url}/instagram?connected=1";
            }}
          }} catch (err) {{
            window.location.href = "{frontend_url}/instagram?connected=1";
          }}
        </script>
        <p>Instagram connected successfully. You may close this window.</p>
      </body>
    </html>
    """
    return HTMLResponse(content=html, status_code=200)


# ── Step 2b – Fetch saved IG accounts for the current user ──────────────────
@app.get("/instagram/accounts", response_model=list[SocialAccountOut])
def list_instagram_accounts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    return db.query(SocialAccount).filter(
        SocialAccount.user_id == user.id,
        SocialAccount.platform == "instagram"
    ).all()


# ── Step 2c – Disconnect an IG account ───────────────────────────────────────
@app.delete("/instagram/accounts/{account_id}")
def disconnect_instagram_account(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    acc = db.query(SocialAccount).filter(
        SocialAccount.id == account_id,
        SocialAccount.user_id == user.id
    ).first()
    if not acc:
        raise HTTPException(404, "Account not found")
    db.delete(acc)
    db.commit()
    return {"message": "Account disconnected"}


# ── Step 3 – Link chatbot ↔ IG account (create channel) ─────────────────────
@app.post("/instagram/channels", response_model=ChatbotChannelOut)
def create_channel(
    data: ChatbotChannelCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Connect a chatbot to an Instagram account."""
    chatbot = db.query(Chatbot).filter(
        Chatbot.id == data.chatbot_id,
        Chatbot.user_id == user.id
    ).first()
    if not chatbot:
        raise HTTPException(404, "Chatbot not found")

    social_acc = db.query(SocialAccount).filter(
        SocialAccount.id == data.social_account_id,
        SocialAccount.user_id == user.id
    ).first()
    if not social_acc:
        raise HTTPException(404, "Instagram account not found")

    # Prevent duplicate
    existing = db.query(ChatbotChannel).filter(
        ChatbotChannel.chatbot_id == data.chatbot_id,
        ChatbotChannel.social_account_id == data.social_account_id
    ).first()
    if existing:
        raise HTTPException(400, "This chatbot is already connected to that Instagram account")

    channel = ChatbotChannel(
        chatbot_id=data.chatbot_id,
        social_account_id=data.social_account_id,
        auto_reply=data.auto_reply,
        reply_to_comments=data.reply_to_comments
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    return {
        "id": channel.id,
        "chatbot_id": channel.chatbot_id,
        "social_account_id": channel.social_account_id,
        "is_enabled": channel.is_enabled,
        "auto_reply": channel.auto_reply,
        "reply_to_comments": channel.reply_to_comments,
        "created_at": channel.created_at,
        "chatbot_name": chatbot.name,
        "ig_username": social_acc.username,
    }


# ── List channels for a chatbot ──────────────────────────────────────────────
@app.get("/chatbots/{chatbot_id}/channels", response_model=list[ChatbotChannelOut])
def list_channels(
    chatbot_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    chatbot = db.query(Chatbot).filter(
        Chatbot.id == chatbot_id,
        Chatbot.user_id == user.id
    ).first()
    if not chatbot:
        raise HTTPException(404, "Chatbot not found")

    channels = db.query(ChatbotChannel).filter(
        ChatbotChannel.chatbot_id == chatbot_id
    ).all()

    result = []
    for ch in channels:
        acc = db.query(SocialAccount).filter(SocialAccount.id == ch.social_account_id).first()
        result.append({
            "id": ch.id,
            "chatbot_id": ch.chatbot_id,
            "social_account_id": ch.social_account_id,
            "is_enabled": ch.is_enabled,
            "auto_reply": ch.auto_reply,
            "reply_to_comments": ch.reply_to_comments,
            "created_at": ch.created_at,
            "chatbot_name": chatbot.name,
            "ig_username": acc.username if acc else None,
        })
    return result


# ── Toggle channel on/off & update settings ──────────────────────────────────
@app.put("/instagram/channels/{channel_id}")
def update_channel(
    channel_id: int,
    data: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    channel = db.query(ChatbotChannel).join(Chatbot).filter(
        ChatbotChannel.id == channel_id,
        Chatbot.user_id == user.id
    ).first()
    if not channel:
        raise HTTPException(404, "Channel not found")
    if "is_enabled" in data:
        channel.is_enabled = data["is_enabled"]
    if "auto_reply" in data:
        channel.auto_reply = data["auto_reply"]
    if "reply_to_comments" in data:
        channel.reply_to_comments = data["reply_to_comments"]
    db.commit()
    return {"message": "Channel updated"}


# ── Delete a channel ─────────────────────────────────────────────────────────
@app.delete("/instagram/channels/{channel_id}")
def delete_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    channel = db.query(ChatbotChannel).join(Chatbot).filter(
        ChatbotChannel.id == channel_id,
        Chatbot.user_id == user.id
    ).first()
    if not channel:
        raise HTTPException(404, "Channel not found")
    db.delete(channel)
    db.commit()
    return {"message": "Channel removed"}


# ── Automation Rules ─────────────────────────────────────────────────────────
@app.post("/instagram/automation-rules", response_model=AutomationRuleOut)
def create_automation_rule(
    data: AutomationRuleCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # Verify channel belongs to user
    channel = db.query(ChatbotChannel).join(Chatbot).filter(
        ChatbotChannel.id == data.chatbot_channel_id,
        Chatbot.user_id == user.id
    ).first()
    if not channel:
        raise HTTPException(404, "Channel not found")

    rule = AutomationRule(
        chatbot_channel_id=data.chatbot_channel_id,
        trigger_type=data.trigger_type,
        keyword=data.keyword,
        response_type=data.response_type,
        template=data.template
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@app.get("/instagram/channels/{channel_id}/automation-rules", response_model=list[AutomationRuleOut])
def list_automation_rules(
    channel_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    channel = db.query(ChatbotChannel).join(Chatbot).filter(
        ChatbotChannel.id == channel_id,
        Chatbot.user_id == user.id
    ).first()
    if not channel:
        raise HTTPException(404, "Channel not found")
    return db.query(AutomationRule).filter(
        AutomationRule.chatbot_channel_id == channel_id
    ).all()


@app.delete("/instagram/automation-rules/{rule_id}")
def delete_automation_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    rule = db.query(AutomationRule).filter(AutomationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(404, "Rule not found")
    db.delete(rule)
    db.commit()
    return {"message": "Rule deleted"}


# ── Social Conversations log ──────────────────────────────────────────────────
@app.get("/instagram/conversations")
def list_social_conversations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """List all IG DM conversations for chatbots owned by the current user."""
    chatbot_ids = [c.id for c in db.query(Chatbot).filter(Chatbot.user_id == user.id).all()]
    convos = db.query(SocialConversation).filter(
        SocialConversation.chatbot_id.in_(chatbot_ids)
    ).order_by(SocialConversation.created_at.desc()).limit(100).all()

    result = []
    for c in convos:
        msgs = db.query(SocialMessage).filter(
            SocialMessage.conversation_id == c.id
        ).order_by(SocialMessage.created_at.desc()).limit(1).all()
        last_msg = msgs[0].message[:80] if msgs else ""
        acc = db.query(SocialAccount).filter(SocialAccount.id == c.social_account_id).first()
        chatbot = db.query(Chatbot).filter(Chatbot.id == c.chatbot_id).first()
        result.append({
            "id": c.id,
            "chatbot_id": c.chatbot_id,
            "chatbot_name": chatbot.name if chatbot else "Unknown",
            "ig_account": acc.username if acc else "Unknown",
            "user_ig_id": c.user_ig_id,
            "username": c.username,
            "last_message": last_msg,
            "created_at": c.created_at,
        })
    return result


# ── Webhook Verification (GET) ───────────────────────────────────────────────
@app.get("/instagram/webhook")
def verify_webhook(
    request: Request,
    hub_mode: str = None,
    hub_challenge: str = None,
    hub_verify_token: str = None
):
    """Facebook calls this GET to verify our webhook endpoint."""
    if hub_mode == "subscribe" and hub_verify_token == IG_VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(403, "Verification failed")

import json
# ── Webhook Events (POST) ────────────────────────────────────────────────────
@app.post("/instagram/webhook")
async def instagram_webhook(request: Request, db: Session = Depends(get_db)):
    """Receive DMs and Comment events from Instagram Graph API."""
    body = await request.json()
    print(f"[IG Webhook] Received: {json.dumps(body)[:500]}")

    # Log raw event
    event = WebhookEvent(
        platform="instagram",
        event_type=body.get("object", "unknown"),
        payload=json.dumps(body)
    )
    db.add(event)
    db.commit()

    for entry in body.get("entry", []):
        page_id = entry.get("id")

        # ── Direct Messages ───────────────────────────────────────────────
        for messaging in entry.get("messaging", []):
            sender_id = messaging.get("sender", {}).get("id")
            recipient_id = messaging.get("recipient", {}).get("id")
            msg_obj = messaging.get("message", {})
            text = msg_obj.get("text", "").strip()
            ig_msg_id = msg_obj.get("mid", "")

            # Skip echo events (bot's own outgoing messages reflected back)
            if msg_obj.get("is_echo"):
                continue

            if not text or sender_id == recipient_id:
                continue  # skip non-text or self-messages

            await _handle_dm(sender_id, recipient_id, text, ig_msg_id, db)

        # ── Comments ─────────────────────────────────────────────────────
        # Instagram Graph API sends comments with field="comments" and value.text
        for change in entry.get("changes", []):
            field = change.get("field", "")
            val = change.get("value", {})
            print(f"[IG Webhook] Change field={field!r} val_keys={list(val.keys())}")

            if field != "comments":
                continue

            # Instagram sends comment id as "id" (not "comment_id")
            comment_id = val.get("id") or val.get("comment_id")
            sender_id = val.get("from", {}).get("id")
            # Instagram uses "text" not "message"
            text = (val.get("text") or val.get("message") or "").strip()

            print(f"[IG Comment] comment_id={comment_id} sender={sender_id} text={text!r}")

            if not text or not comment_id:
                continue

            await _handle_comment(sender_id, page_id, comment_id, text, db)

    event.processed = True
    db.commit()
    return {"status": "ok"}


# ── Internal helper: handle an incoming IG DM ────────────────────────────────
async def _handle_dm(sender_ig_id: str, recipient_ig_id: str, text: str, ig_msg_id: str, db: Session):
    """Find matching channel, run automation / AI, send reply."""
    # Find the SocialAccount whose IG id is the recipient (our page)
    social_acc = db.query(SocialAccount).filter(
        SocialAccount.account_id == recipient_ig_id,
        SocialAccount.platform == "instagram"
    ).first()
    if not social_acc:
        print(f"[IG DM] No social account for recipient {recipient_ig_id}")
        return

    # Find active channels for this account
    channels = db.query(ChatbotChannel).filter(
        ChatbotChannel.social_account_id == social_acc.id,
        ChatbotChannel.is_enabled == True,
        ChatbotChannel.auto_reply == True
    ).all()

    if not channels:
        print(f"[IG DM] No active channels for account {recipient_ig_id}")
        return

    # Use the first matching channel (chatbot)
    channel = channels[0]
    chatbot = db.query(Chatbot).filter(Chatbot.id == channel.chatbot_id).first()
    if not chatbot:
        return

    # Check automation rules first (keyword-based)
    reply_text = await _match_automation_rule(
        channel.id, "dm", text, chatbot, social_acc, db
    )

    # Get/create conversation session
    convo = db.query(SocialConversation).filter(
        SocialConversation.social_account_id == social_acc.id,
        SocialConversation.user_ig_id == sender_ig_id,
        SocialConversation.chatbot_id == chatbot.id
    ).first()
    if not convo:
        convo = SocialConversation(
            chatbot_id=chatbot.id,
            social_account_id=social_acc.id,
            user_ig_id=sender_ig_id,
            session_id=f"ig_{sender_ig_id}_{chatbot.id}"
        )
        db.add(convo)
        db.commit()
        db.refresh(convo)

    # Log user message
    db.add(SocialMessage(
        conversation_id=convo.id,
        sender_type="user",
        message=text,
        message_type="dm",
        ig_message_id=ig_msg_id
    ))
    db.commit()

    # Send reply
    try:
        result = await send_dm(sender_ig_id, reply_text, social_acc.access_token)
        print(f"[IG DM] Sent reply to {sender_ig_id}: {reply_text[:80]}")
    except Exception as e:
        print(f"[IG DM] Send failed: {e}")
        return

    # Log bot message
    db.add(SocialMessage(
        conversation_id=convo.id,
        sender_type="bot",
        message=reply_text,
        message_type="dm"
    ))
    db.commit()


# ── Internal helper: handle an incoming IG Comment ──────────────────────────
async def _handle_comment(sender_ig_id: str, page_id: str, comment_id: str, text: str, db: Session):
    """Find matching channel with reply_to_comments=True, reply in comment AND send DM."""
    print(f"[IG Comment] _handle_comment: sender={sender_ig_id} page_id={page_id} comment_id={comment_id} text={text!r}")

    social_acc = db.query(SocialAccount).filter(
        SocialAccount.account_id == page_id,
        SocialAccount.platform == "instagram"
    ).first()
    if not social_acc:
        print(f"[IG Comment] ❌ No SocialAccount for page_id={page_id}")
        all_accs = db.query(SocialAccount).filter(SocialAccount.platform == "instagram").all()
        print(f"[IG Comment]    Known IG accounts: {[(a.account_id, a.username) for a in all_accs]}")
        return

    print(f"[IG Comment] ✅ SocialAccount: id={social_acc.id} username={social_acc.username}")

    channels = db.query(ChatbotChannel).filter(
        ChatbotChannel.social_account_id == social_acc.id,
        ChatbotChannel.is_enabled == True,
        ChatbotChannel.reply_to_comments == True
    ).all()
    if not channels:
        all_ch = db.query(ChatbotChannel).filter(ChatbotChannel.social_account_id == social_acc.id).all()
        print(f"[IG Comment] ❌ No comment-enabled channels. All channels: {[(c.id, c.is_enabled, c.reply_to_comments) for c in all_ch]}")
        return

    channel = channels[0]
    chatbot = db.query(Chatbot).filter(Chatbot.id == channel.chatbot_id).first()
    if not chatbot:
        print(f"[IG Comment] ❌ Chatbot {channel.chatbot_id} not found")
        return

    print(f"[IG Comment] Using chatbot: id={chatbot.id} name={chatbot.name!r}")

    reply_text = await _match_automation_rule(
        channel.id, "comment", text, chatbot, social_acc, db
    )
    print(f"[IG Comment] reply_text={reply_text!r}")

    # 1) Reply publicly in the comment thread
    try:
        await reply_to_comment(comment_id, reply_text, social_acc.access_token)
        print(f"[IG Comment] ✅ Replied to comment {comment_id}: {reply_text[:80]}")
    except Exception as e:
        print(f"[IG Comment] ❌ Reply failed: {e}")

    # 2) Also send a DM to the commenter (if we have their IG id and it's not our own page)
    if sender_ig_id and sender_ig_id != page_id:
        try:
            await send_dm(sender_ig_id, reply_text, social_acc.access_token)
            print(f"[IG Comment] ✅ Sent DM to commenter {sender_ig_id}")
        except Exception as e:
            print(f"[IG Comment] ❌ DM to commenter failed: {e}")


# ── AI / automation rule matcher ─────────────────────────────────────────────
async def _match_automation_rule(
    channel_id: int, trigger_type: str, text: str,
    chatbot, social_acc, db: Session
) -> str:
    """Check automation rules first; fall back to RAG AI answer."""
    rules = db.query(AutomationRule).filter(
        AutomationRule.chatbot_channel_id == channel_id,
        AutomationRule.trigger_type == trigger_type
    ).all()

    for rule in rules:
        keyword = (rule.keyword or "").lower().strip()
        if keyword and keyword not in text.lower():
            continue  # keyword doesn't match

        if rule.response_type == "template" and rule.template:
            return rule.template

        # response_type == "ai" — fall through to AI below
        break

    # ── AI answer via RAG ────────────────────────────────────────────────────
    context_docs = search(text, chatbot_id=chatbot.id)

    # Determine provider & API key — mirrors the website chatbot logic:
    # Try the chatbot's preferred provider first; if no key saved, fall back to Groq.
    provider = "groq"  # default
    api_key = None

    model_lower = (chatbot.model or "").lower()
    if "gpt" in model_lower or "openai" in model_lower:
        provider = "openai"
    elif "claude" in model_lower:
        provider = "claude"

    # Look up user's key for the preferred provider
    user_key = db.query(ApiKey).filter(
        ApiKey.user_id == chatbot.user_id,
        ApiKey.provider == provider
    ).first()

    if user_key:
        api_key = user_key.api_key
    elif provider != "groq":
        # Preferred provider has no saved key → fall back to Groq
        groq_key = db.query(ApiKey).filter(
            ApiKey.user_id == chatbot.user_id,
            ApiKey.provider == "groq"
        ).first()
        if groq_key:
            api_key = groq_key.api_key
        provider = "groq"  # use Groq (fallback key in llm.py handles None api_key too)

    try:
        answer = generate_answer(
            text, context_docs,
            provider=provider,
            api_key=api_key,
            system_instructions=chatbot.system_instructions,
        )
        print(f"[IG AI] Generated answer via {provider} (key={'yes' if api_key else 'fallback'})")
        return answer
    except Exception as e:
        print(f"[IG AI] Error generating answer: {e}")
        return "Hi! Thanks for reaching out. We'll get back to you shortly."


from models import Base
from database import engine

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

class SignupRequest(BaseModel):
    firstName: str
    lastName: str
    email: EmailStr
    password: str
    confirmPassword: str
    
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    
class ChatbotCreate(BaseModel):
    name: str
    website: str
    language: str
    model: str
    welcome_message: str
    brand_color: str
    category_id: Optional[int] = None
    
class FAQRequest(BaseModel):
    question: str
    answer: str
    
class ConversationOut(BaseModel):
    id: int
    chatbot_id: int
    user_message: str
    bot_response: str
    created_at: datetime
    session_id: str | None = None

    class Config:
        model_config = {"from_attributes": True}


# --- API Keys ---
class ApiKeyCreate(BaseModel):
    provider: str   # groq, openai, claude
    api_key: str

class ApiKeyOut(BaseModel):
    id: int
    provider: str
    masked_key: str
    created_at: datetime

    class Config:
        model_config = {"from_attributes": True}


# --- Categories ---
class CategoryOut(BaseModel):
    id: int
    name: str
    slug: str

    class Config:
        model_config = {"from_attributes": True}


# --- Leads ---
class LeadCreate(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    message: Optional[str] = None
    session_id: Optional[str] = None

class LeadOut(BaseModel):
    id: int
    chatbot_id: int
    name: str
    email: str
    phone: Optional[str] = None
    message: Optional[str] = None
    session_id: Optional[str] = None
    intent: Optional[str] = None
    intent_updated_at: Optional[datetime] = None
    created_at: datetime
    chatbot_name: Optional[str] = None
    category_name: Optional[str] = None

    class Config:
        model_config = {"from_attributes": True}


# --- Training Sources ---
class TrainingSourceOut(BaseModel):
    id: int
    source_type: str
    source_name: str
    char_count: int
    chunk_count: int
    status: str
    created_at: datetime

    class Config:
        model_config = {"from_attributes": True}


# --- Profile ---
class ProfileOut(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: EmailStr
    company: Optional[str] = None

class ProfileUpdate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    company: Optional[str] = None
    password: Optional[str] = None


# --- Billing ---
class PlanOut(BaseModel):
    id: str
    name: str
    price: str
    period: str
    features: list[str]
    price_id: str

class SubscriptionOut(BaseModel):
    plan: str
    billing_cycle: Optional[str] = None
    status: str
    current_period_end: Optional[datetime] = None
    trial_ends_at: Optional[datetime] = None
    cancel_at_period_end: Optional[bool] = False

    class Config:
        model_config = {"from_attributes": True}

class TrialStatusOut(BaseModel):
    is_trial: bool
    trial_active: bool
    days_remaining: int
    trial_ends_at: Optional[datetime] = None

class TransactionOut(BaseModel):
    id: int
    amount: float
    currency: str
    status: str
    description: Optional[str] = None
    billed_at: datetime

    class Config:
        model_config = {"from_attributes": True}

class PaddleWebhookEvent(BaseModel):
    event_type: str
    data: dict

# --- Meetings & Availability ---
class AvailabilityUpdate(BaseModel):
    schedule_json: str

class AvailabilityOut(BaseModel):
    id: int
    user_id: int
    schedule_json: str

    class Config:
        model_config = {"from_attributes": True}

class MeetingCreate(BaseModel):
    visitor_name: str
    visitor_email: str
    scheduled_time: datetime
    session_id: Optional[str] = None

class MeetingOut(BaseModel):
    id: int
    chatbot_id: int
    visitor_name: str
    visitor_email: str
    scheduled_time: datetime
    status: str
    session_id: Optional[str] = None
    created_at: datetime
    chatbot_name: Optional[str] = None

    class Config:
        model_config = {"from_attributes": True}


# --- Platform Feedback ---
class PlatformFeedbackCreate(BaseModel):
    feedback_text: str
    category: str

class PlatformFeedbackOut(BaseModel):
    id: int
    user_id: int
    feedback_text: str
    category: str
    created_at: datetime

    class Config:
        model_config = {"from_attributes": True}


# --- Custom Quotations ---
class CustomQuotationCreate(BaseModel):
    requirements: str
    budget: str

class CustomQuotationUpdate(BaseModel):
    quoted_price: Optional[str] = None
    status: Optional[str] = None
    widget_script: Optional[str] = None

class CustomQuotationOut(BaseModel):
    id: int
    user_id: int
    requirements: str
    budget: str
    quoted_price: Optional[str] = None
    status: str
    widget_script: Optional[str] = None
    created_at: datetime

    class Config:
        model_config = {"from_attributes": True}


# ── Instagram / Social ────────────────────────────────────────────────────────

class SocialAccountOut(BaseModel):
    id: int
    platform: str
    account_id: str
    username: Optional[str] = None
    profile_pic_url: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        model_config = {"from_attributes": True}


class ChatbotChannelCreate(BaseModel):
    chatbot_id: int
    social_account_id: int
    auto_reply: bool = True
    reply_to_comments: bool = False


class ChatbotChannelOut(BaseModel):
    id: int
    chatbot_id: int
    social_account_id: int
    is_enabled: bool
    auto_reply: bool
    reply_to_comments: bool
    created_at: datetime
    chatbot_name: Optional[str] = None
    ig_username: Optional[str] = None

    class Config:
        model_config = {"from_attributes": True}


class AutomationRuleCreate(BaseModel):
    chatbot_channel_id: int
    trigger_type: str          # comment | dm
    keyword: Optional[str] = None
    response_type: str         # ai | template
    template: Optional[str] = None


class AutomationRuleOut(BaseModel):
    id: int
    chatbot_channel_id: int
    trigger_type: str
    keyword: Optional[str] = None
    response_type: str
    template: Optional[str] = None

    class Config:
        model_config = {"from_attributes": True}


class SocialConversationOut(BaseModel):
    id: int
    chatbot_id: int
    social_account_id: int
    user_ig_id: str
    username: Optional[str] = None
    session_id: Optional[str] = None
    created_at: datetime

    class Config:
        model_config = {"from_attributes": True}
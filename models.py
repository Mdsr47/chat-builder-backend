from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    company = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    chatbots = relationship("Chatbot", back_populates="owner")
    api_keys = relationship("ApiKey", back_populates="owner")
    subscription = relationship("Subscription", back_populates="user", uselist=False)
    transactions = relationship("Transaction", back_populates="user")
    

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)

    chatbots = relationship("Chatbot", back_populates="category")


class Chatbot(Base):
    __tablename__ = "chatbots"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    website = Column(String)
    language = Column(String)
    model = Column(String)
    welcome_message = Column(String)
    brand_color = Column(String)
    system_instructions = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user_id = Column(Integer, ForeignKey("users.id"))
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    owner = relationship("User", back_populates="chatbots")
    category = relationship("Category", back_populates="chatbots")
    leads = relationship("Lead", back_populates="chatbot")

    
class FAQ(Base):
    __tablename__ = "faqs"

    id = Column(Integer, primary_key=True)
    question = Column(String)
    answer = Column(String)
    chatbot_id = Column(Integer, ForeignKey("chatbots.id"))
    
class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    chatbot_id = Column(Integer, index=True)
    user_message = Column(Text)
    bot_response = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    session_id = Column(String, nullable=True)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider = Column(String, nullable=False)  # groq, openai, claude
    api_key = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="api_keys")


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    chatbot_id = Column(Integer, ForeignKey("chatbots.id"), nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    message = Column(Text, nullable=True)
    session_id = Column(String, nullable=True, index=True)  # links lead to chat session
    intent = Column(String, nullable=True)                   # low | medium | high | very_high
    intent_updated_at = Column(DateTime, nullable=True)      # when intent was last analyzed
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    chatbot = relationship("Chatbot", back_populates="leads")


class TrainingSource(Base):
    __tablename__ = "training_sources"

    id = Column(Integer, primary_key=True, index=True)
    chatbot_id = Column(Integer, ForeignKey("chatbots.id"), nullable=False)
    source_type = Column(String, nullable=False)  # pdf, url, faq
    source_name = Column(String, nullable=False)   # filename or URL
    char_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    status = Column(String, default="completed")   # pending, completed, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())


from sqlalchemy import Float


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    paddle_subscription_id = Column(String, unique=True, nullable=True)
    paddle_customer_id = Column(String, nullable=True)
    plan = Column(String, default="free")         # free, starter, pro, agency
    billing_cycle = Column(String, nullable=True)  # monthly, yearly
    status = Column(String, default="trialing")    # trialing, active, past_due, paused, canceled
    message_count = Column(Integer, default=0)
    current_period_end = Column(DateTime, nullable=True)
    trial_ends_at = Column(DateTime, nullable=True)         # 7-day trial end date
    cancel_at_period_end = Column(Boolean, default=False)   # scheduled for cancellation
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="subscription")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    paddle_transaction_id = Column(String, unique=True)
    amount = Column(Float)
    currency = Column(String)
    status = Column(String)  # completed, pending, failed
    description = Column(String, nullable=True)   # e.g. "Starter Plan - Monthly"
    billed_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="transactions")

class Availability(Base):
    __tablename__ = "availability"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    # Using JSON to store schedule for flexibility (e.g. {"monday": ["09:00", "17:00"], ...})
    # For sqlite compatibility we can just use a Text column and serialize/deserialize JSON.
    schedule_json = Column(Text, nullable=False, default='{"monday": ["09:00", "17:00"], "tuesday": ["09:00", "17:00"], "wednesday": ["09:00", "17:00"], "thursday": ["09:00", "17:00"], "friday": ["09:00", "17:00"]}')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    chatbot_id = Column(Integer, ForeignKey("chatbots.id"), nullable=False)
    visitor_name = Column(String, nullable=False)
    visitor_email = Column(String, nullable=False)
    scheduled_time = Column(DateTime, nullable=False)
    status = Column(String, default="scheduled") # scheduled, cancelled, completed
    session_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class PlatformFeedback(Base):
    __tablename__ = "platform_feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    feedback_text = Column(Text, nullable=False)
    category = Column(String, nullable=False) # improvement, suggestion, bug, other
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")

class CustomQuotation(Base):
    __tablename__ = "custom_quotations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    requirements = Column(Text, nullable=False)
    budget = Column(String, nullable=False)
    quoted_price = Column(String, nullable=True)
    status = Column(String, default="pending") # pending, quoted, paid, rejected
    widget_script = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")

class SocialAccount(Base):
    __tablename__ = "social_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    platform = Column(String, nullable=False)  # instagram, facebook, whatsapp
    account_id = Column(String, nullable=False)  # IG user id
    username = Column(String, nullable=True)

    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)

    profile_pic_url = Column(String, nullable=True)  # optional: IG profile picture

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
    
class ChatbotChannel(Base):
    __tablename__ = "chatbot_channels"

    id = Column(Integer, primary_key=True, index=True)
    chatbot_id = Column(Integer, ForeignKey("chatbots.id"), nullable=False)
    social_account_id = Column(Integer, ForeignKey("social_accounts.id"), nullable=False)

    is_enabled = Column(Boolean, default=True)

    # automation settings
    auto_reply = Column(Boolean, default=True)
    reply_to_comments = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    chatbot = relationship("Chatbot")
    social_account = relationship("SocialAccount")
    
class SocialConversation(Base):
    __tablename__ = "social_conversations"

    id = Column(Integer, primary_key=True, index=True)
    chatbot_id = Column(Integer, ForeignKey("chatbots.id"))
    social_account_id = Column(Integer, ForeignKey("social_accounts.id"))

    user_ig_id = Column(String, nullable=False)  # IG sender id
    username = Column(String, nullable=True)

    session_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class SocialMessage(Base):
    __tablename__ = "social_messages"

    id = Column(Integer, primary_key=True, index=True)

    conversation_id = Column(Integer, ForeignKey("social_conversations.id"))

    sender_type = Column(String)  # user / bot
    message = Column(Text)

    message_type = Column(String)  # dm / comment
    ig_message_id = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    
class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True)
    platform = Column(String)  # instagram
    event_type = Column(String)  # message, comment, mention

    payload = Column(Text)  # raw JSON

    processed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class AutomationRule(Base):
    __tablename__ = "automation_rules"

    id = Column(Integer, primary_key=True)
    chatbot_channel_id = Column(Integer, ForeignKey("chatbot_channels.id"))

    trigger_type = Column(String)  # comment, dm
    keyword = Column(String, nullable=True)

    response_type = Column(String)  # ai, template
    template = Column(Text, nullable=True)
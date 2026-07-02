from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    user_id: str = Field(min_length=2, max_length=32)


class LoginResponse(BaseModel):
    session_token: int
    user_id: str
    attempt_number: int
    emotion: str
    position: str
    is_anger: bool


class CompleteExperimentRequest(BaseModel):
    session_token: int


class InstructionScreeningRequest(BaseModel):
    session_token: int
    has_similar_experience: bool


class InstructionScreeningResponse(BaseModel):
    ok: bool
    continue_experiment: bool
    exit_reason: str | None = None


class ClickEventRequest(BaseModel):
    session_token: int
    page: str
    element: str


class PageEnterRequest(BaseModel):
    session_token: int
    page: str


class PageLeaveRequest(BaseModel):
    session_token: int
    page: str
    entered_at: datetime
    left_at: datetime


class ChatSendRequest(BaseModel):
    session_token: int
    message: str = Field(min_length=1, max_length=4000)


class ChatMessageDTO(BaseModel):
    role: str
    content: str
    round_number: int | None = None
    timestamp: datetime


class ChatHistoryResponse(BaseModel):
    messages: list[ChatMessageDTO]
    ai_round_count: int
    chat_finished: bool
    is_anger: bool


class ChatSendResponse(BaseModel):
    user_message: ChatMessageDTO
    ai_message: ChatMessageDTO | None = None
    ai_round_count: int
    chat_finished: bool
    is_anger: bool


class SessionResponse(BaseModel):
    user_id: str
    attempt_number: int
    emotion: str
    position: str
    is_anger: bool
    ai_round_count: int
    chat_finished: bool
    experiment_finished: bool
    has_similar_experience: bool | None = None

from datetime import datetime

from pydantic import BaseModel, Field


class StartSessionResponse(BaseModel):
    session_token: int
    attempt_number: int
    is_anger: bool
    completion_code: str


class CompleteExperimentRequest(BaseModel):
    session_token: int


class CompleteExperimentResponse(BaseModel):
    ok: bool
    completion_code: str


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
    attempt_number: int
    is_anger: bool
    ai_round_count: int
    chat_finished: bool
    experiment_finished: bool
    completion_code: str

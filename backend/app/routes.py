from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.conditions import MAX_AI_ROUNDS, parse_user_id
from app.database import get_db
from app.models import ClickEvent, PageEvent
from app.schemas import (
    ChatHistoryResponse,
    ChatMessageDTO,
    ChatSendRequest,
    ChatSendResponse,
    ClickEventRequest,
    CompleteExperimentRequest,
    InstructionScreeningRequest,
    InstructionScreeningResponse,
    LoginRequest,
    LoginResponse,
    PageEnterRequest,
    PageLeaveRequest,
    SessionResponse,
)
from app.services import (
    complete_experiment,
    get_or_create_session,
    get_session_by_token,
    list_chat_messages,
    record_instruction_screening,
    send_user_message,
    stream_chat_events,
)

router = APIRouter(prefix="/api")


@router.get("/config")
def get_config():
    return {
        "max_ai_rounds": MAX_AI_ROUNDS,
    }


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        session, condition = get_or_create_session(db, payload.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return LoginResponse(
        session_token=session.id,
        user_id=condition.user_id,
        attempt_number=session.attempt_number,
        emotion=condition.emotion,
        position=condition.position,
        is_anger=condition.is_anger,
    )


@router.get("/session/{session_token}", response_model=SessionResponse)
def get_session(session_token: int, db: Session = Depends(get_db)):
    try:
        session = get_session_by_token(db, session_token)
        condition = parse_user_id(session.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return SessionResponse(
        user_id=session.user_id,
        attempt_number=session.attempt_number,
        emotion=condition.emotion,
        position=condition.position,
        is_anger=condition.is_anger,
        ai_round_count=session.ai_round_count,
        chat_finished=bool(session.chat_finished),
        experiment_finished=bool(session.experiment_finished),
        has_similar_experience=(
            bool(session.has_similar_experience)
            if session.has_similar_experience is not None
            else None
        ),
    )


@router.post("/experiment/complete")
def finish_experiment(payload: CompleteExperimentRequest, db: Session = Depends(get_db)):
    try:
        session = get_session_by_token(db, payload.session_token)
        complete_experiment(db, session)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"ok": True, "attempt_number": session.attempt_number}


@router.post("/instruction/screening", response_model=InstructionScreeningResponse)
def submit_instruction_screening(
    payload: InstructionScreeningRequest, db: Session = Depends(get_db)
):
    try:
        session = get_session_by_token(db, payload.session_token)
        continue_experiment = record_instruction_screening(
            db, session, payload.has_similar_experience
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return InstructionScreeningResponse(
        ok=True,
        continue_experiment=continue_experiment,
        exit_reason=session.exit_reason,
    )


@router.post("/events/click")
def log_click(payload: ClickEventRequest, db: Session = Depends(get_db)):
    try:
        session = get_session_by_token(db, payload.session_token)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    db.add(
        ClickEvent(
            session_id=session.id,
            page=payload.page,
            element=payload.element,
        )
    )
    db.commit()
    return {"ok": True}


@router.post("/events/page-enter")
def log_page_enter(payload: PageEnterRequest, db: Session = Depends(get_db)):
    try:
        session = get_session_by_token(db, payload.session_token)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    event = PageEvent(session_id=session.id, page=payload.page)
    db.add(event)
    db.commit()
    db.refresh(event)
    return {"event_id": event.id}


@router.post("/events/page-leave")
def log_page_leave(payload: PageLeaveRequest, db: Session = Depends(get_db)):
    try:
        session = get_session_by_token(db, payload.session_token)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    dwell_ms = max(int((payload.left_at - payload.entered_at).total_seconds() * 1000), 0)
    event = PageEvent(
        session_id=session.id,
        page=payload.page,
        entered_at=payload.entered_at,
        left_at=payload.left_at,
        dwell_ms=dwell_ms,
    )
    db.add(event)
    db.commit()
    return {"ok": True, "dwell_ms": dwell_ms}


@router.get("/chat/{session_token}", response_model=ChatHistoryResponse)
def get_chat_history(session_token: int, db: Session = Depends(get_db)):
    try:
        session = get_session_by_token(db, session_token)
        condition = parse_user_id(session.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    messages = [
        ChatMessageDTO(
            role=item.role,
            content=item.content,
            round_number=item.round_number,
            timestamp=item.timestamp,
        )
        for item in list_chat_messages(db, session)
    ]

    return ChatHistoryResponse(
        messages=messages,
        ai_round_count=session.ai_round_count,
        chat_finished=bool(session.chat_finished),
        is_anger=condition.is_anger,
    )


@router.post("/chat/send", response_model=ChatSendResponse)
def send_chat_message(payload: ChatSendRequest, db: Session = Depends(get_db)):
    try:
        session = get_session_by_token(db, payload.session_token)
        condition = parse_user_id(session.user_id)
        user_msg, ai_msg, finished = send_user_message(db, session, payload.message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"聊天服务异常：{exc}") from exc

    return ChatSendResponse(
        user_message=ChatMessageDTO(
            role=user_msg.role,
            content=user_msg.content,
            round_number=user_msg.round_number,
            timestamp=user_msg.timestamp,
        ),
        ai_message=(
            ChatMessageDTO(
                role=ai_msg.role,
                content=ai_msg.content,
                round_number=ai_msg.round_number,
                timestamp=ai_msg.timestamp,
            )
            if ai_msg
            else None
        ),
        ai_round_count=session.ai_round_count,
        chat_finished=finished,
        is_anger=condition.is_anger,
    )


@router.post("/chat/send-stream")
def send_chat_message_stream(payload: ChatSendRequest):
    return StreamingResponse(
        stream_chat_events(payload.session_token, payload.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.console import Console, ConsoleStatus
from app.models.session import Session, SessionStatus, SessionType

tz = ZoneInfo(settings.TIMEZONE)

ACTIVE_STATUSES = (
    SessionStatus.HOLD,
    SessionStatus.CONFIRMED,
    SessionStatus.ACTIVE,
)


async def check_slot_available(
    db: AsyncSession,
    console_id: int,
    slot_start: datetime.datetime,
    slot_end: datetime.datetime,
) -> bool:
    """Return True if the time slot is free for the given console."""
    stmt = select(Session).where(
        and_(
            Session.console_id == console_id,
            Session.status.in_(ACTIVE_STATUSES),
            # overlap condition: existing.start < new.end AND existing.end > new.start
            Session.slot_start < slot_end,
            Session.slot_end > slot_start,
        )
    )
    result = await db.execute(stmt)
    return result.scalars().first() is None


async def get_free_slots(
    db: AsyncSession,
    console_id: int,
    date: datetime.date,
    duration_minutes: int,
) -> list[datetime.datetime]:
    """Return available start times for a given date and duration (step = 30 min)."""
    day_start = datetime.datetime.combine(date, datetime.time.min, tzinfo=tz)
    day_end = day_start + datetime.timedelta(days=1)

    # fetch all occupied slots for the day
    stmt = select(Session).where(
        and_(
            Session.console_id == console_id,
            Session.status.in_(ACTIVE_STATUSES),
            Session.slot_start < day_end,
            Session.slot_end > day_start,
        )
    ).order_by(Session.slot_start)
    result = await db.execute(stmt)
    occupied = result.scalars().all()

    buffer = datetime.timedelta(minutes=settings.BUFFER_BETWEEN_SLOTS_MINUTES)
    duration = datetime.timedelta(minutes=duration_minutes)
    step = datetime.timedelta(minutes=30)

    now = datetime.datetime.now(tz)
    cursor = day_start
    if cursor < now:
        # round up to next 30-min boundary
        minutes = (now.minute // 30 + 1) * 30
        cursor = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(minutes=minutes)

    free: list[datetime.datetime] = []
    while cursor + duration <= day_end:
        proposed_end = cursor + duration
        conflict = False
        for s in occupied:
            busy_start = s.slot_start - buffer
            busy_end = s.slot_end + buffer
            if cursor < busy_end and proposed_end > busy_start:
                conflict = True
                break
        if not conflict:
            free.append(cursor)
        cursor += step

    return free


async def create_instant_session(
    db: AsyncSession,
    user_id: int,
    console_id: int,
    duration_minutes: int,
    price: int,
) -> Session | None:
    """Create an instant play session starting now. Returns None if slot taken."""
    now = datetime.datetime.now(tz)
    slot_end = now + datetime.timedelta(minutes=duration_minutes)

    if not await check_slot_available(db, console_id, now, slot_end):
        return None

    session = Session(
        user_id=user_id,
        console_id=console_id,
        session_type=SessionType.INSTANT,
        status=SessionStatus.HOLD,
        duration_minutes=duration_minutes,
        price=price,
        slot_start=now,
        slot_end=slot_end,
        hold_until=now + datetime.timedelta(minutes=settings.HOLD_TIMEOUT_MINUTES),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def create_booking_session(
    db: AsyncSession,
    user_id: int,
    console_id: int,
    slot_start: datetime.datetime,
    duration_minutes: int,
    price: int,
) -> Session | None:
    """Create a pre-booked session. Returns None if slot taken."""
    slot_end = slot_start + datetime.timedelta(minutes=duration_minutes)

    if not await check_slot_available(db, console_id, slot_start, slot_end):
        return None

    now = datetime.datetime.now(tz)
    session = Session(
        user_id=user_id,
        console_id=console_id,
        session_type=SessionType.BOOKING,
        status=SessionStatus.HOLD,
        duration_minutes=duration_minutes,
        price=price,
        slot_start=slot_start,
        slot_end=slot_end,
        hold_until=now + datetime.timedelta(minutes=settings.HOLD_TIMEOUT_MINUTES),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def activate_session(db: AsyncSession, session: Session) -> bool:
    """Activate a CONFIRMED booking (turn on power). Returns success."""
    now = datetime.datetime.now(tz)
    window_start = session.slot_start - datetime.timedelta(
        minutes=settings.ACTIVATION_WINDOW_MINUTES,
    )
    window_end = session.slot_start + datetime.timedelta(
        minutes=settings.ACTIVATION_WINDOW_MINUTES,
    )
    if not (window_start <= now <= window_end):
        return False

    session.status = SessionStatus.ACTIVE
    session.activated_at = now
    await db.commit()
    return True


async def get_next_free_time(
    db: AsyncSession, console_id: int,
) -> datetime.datetime | None:
    """Return the end time of the currently active/confirmed session (when console frees up)."""
    now = datetime.datetime.now(tz)
    stmt = (
        select(Session)
        .where(
            and_(
                Session.console_id == console_id,
                Session.status.in_((SessionStatus.ACTIVE, SessionStatus.CONFIRMED)),
                Session.slot_end > now,
            )
        )
        .order_by(Session.slot_end)
        .limit(1)
    )
    result = await db.execute(stmt)
    s = result.scalars().first()
    return s.slot_end if s else None

"""AI Mentor: Claude API bilan ishlash."""

import logging

import anthropic
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.arena.levels import level_for_xp
from apps.profiles.models import Achievement, UserSkill

from . import prompts
from .models import Conversation, Message

logger = logging.getLogger(__name__)

MAX_TOKENS = 8000
FALLBACK_BETA = "server-side-fallback-2026-07-01"
REFUSAL_REPLY = "Kechirasiz, bu savolga javob bera olmayman. Iltimos, savolni boshqacha shaklda bering."

_client = None


class AiError(Exception):
    """Talabaga ko'rsatiladigan xato."""


class AiLimitExceeded(AiError):
    pass


class AiUnavailable(AiError):
    pass


def get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def student_context(user) -> str:
    """Talaba haqida AI'ga yuboriladigan qisqa ma'lumot.

    Shaxsiy ma'lumotlar (ism, telefon, Telegram ID) yuborilmaydi.
    """
    level = level_for_xp(user.xp)
    skills = UserSkill.objects.filter(user=user).select_related("skill")
    achievements = Achievement.objects.filter(user=user, status=Achievement.Status.APPROVED)[:10]
    unknown = "ko'rsatilmagan"
    lines = [
        "Talaba haqida ma'lumot:",
        f"- Fakultet: {user.faculty.name if user.faculty else unknown}",
        f"- Kurs: {user.course or unknown}",
        f"- Platformadagi daraja: {level['name']} ({user.xp} XP)",
    ]
    if skills:
        lines.append("- Ko'nikmalar (1-5): " + ", ".join(f"{s.skill.name} {s.level}" for s in skills))
    if achievements:
        lines.append("- Yutuqlar: " + "; ".join(f"{a.get_kind_display()}: {a.title}" for a in achievements))
    return "\n".join(lines)


def messages_today(user) -> int:
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return Message.objects.filter(conversation__user=user, role=Message.Role.USER, created_at__gte=start).count()


def _history(conversation: Conversation) -> list[dict]:
    recent = list(conversation.messages.order_by("-created_at", "-id")[: settings.AI_HISTORY_MESSAGES])
    recent.reverse()
    # Tarix doim talaba xabari bilan boshlanishi kerak
    while recent and recent[0].role != Message.Role.USER:
        recent.pop(0)
    return [{"role": m.role, "content": m.content} for m in recent]


def _extract_text(response) -> str:
    return "".join(block.text for block in response.content if block.type == "text").strip()


def reply(conversation: Conversation, text: str, client=None) -> Message:
    """Talaba xabariga AI javobini oladi va ikkalasini saqlaydi."""
    user = conversation.user
    if messages_today(user) >= settings.AI_DAILY_MESSAGE_LIMIT:
        raise AiLimitExceeded(
            f"Bugungi limit tugadi ({settings.AI_DAILY_MESSAGE_LIMIT} ta xabar). Ertaga davom ettiramiz!"
        )

    mode = conversation.mode
    system = [
        {"type": "text", "text": prompts.MODES[mode], "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": student_context(user)},
    ]
    messages = _history(conversation) + [{"role": "user", "content": text}]

    try:
        client = client or get_client()
        response = client.beta.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=messages,
            output_config={"effort": prompts.EFFORT[mode]},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
    except anthropic.RateLimitError as exc:
        logger.warning("Claude API rate limit: %s", exc)
        raise AiUnavailable("AI hozir band. Bir daqiqadan keyin qayta urinib ko'ring.") from exc
    except anthropic.AuthenticationError as exc:
        logger.error("Claude API kaliti noto'g'ri yoki o'rnatilmagan")
        raise AiUnavailable("AI Mentor hali sozlanmagan. Administratorga murojaat qiling.") from exc
    except anthropic.APIStatusError as exc:
        logger.exception("Claude API xatosi (%s)", exc.status_code)
        raise AiUnavailable("AI vaqtincha ishlamayapti. Keyinroq urinib ko'ring.") from exc
    except anthropic.APIConnectionError as exc:
        logger.warning("Claude API bilan aloqa yo'q: %s", exc)
        raise AiUnavailable("AI bilan aloqa yo'q. Keyinroq urinib ko'ring.") from exc
    except anthropic.AnthropicError as exc:
        # Masalan, API kaliti umuman o'rnatilmagan bo'lsa
        logger.error("Claude mijozini yaratib bo'lmadi: %s", exc)
        raise AiUnavailable("AI Mentor hali sozlanmagan. Administratorga murojaat qiling.") from exc

    if response.stop_reason == "refusal":
        answer = REFUSAL_REPLY
    else:
        answer = _extract_text(response)
        if response.stop_reason == "max_tokens":
            answer += "\n\n(Javob juda uzun bo'lib qoldi. Davomini so'rang.)"
        if not answer:
            answer = REFUSAL_REPLY

    with transaction.atomic():
        Message.objects.create(conversation=conversation, role=Message.Role.USER, content=text)
        assistant = Message.objects.create(
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            content=answer,
            input_tokens=getattr(response.usage, "input_tokens", 0) or 0,
            output_tokens=getattr(response.usage, "output_tokens", 0) or 0,
        )
        if not conversation.title:
            conversation.title = text[:80]
        conversation.save(update_fields=["title", "updated_at"])
    return assistant

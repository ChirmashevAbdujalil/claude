from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from apps.ai import services
from apps.ai.models import Conversation, Message


class FakeClient:
    """Claude API o'rniga ishlatiladigan soxta mijoz."""

    def __init__(self, text="Salom! Keling, reja tuzamiz.", stop_reason="end_turn", error=None):
        self.calls = []
        self.text = text
        self.stop_reason = stop_reason
        self.error = error
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self.text)],
            stop_reason=self.stop_reason,
            usage=SimpleNamespace(input_tokens=120, output_tokens=40),
        )


@pytest.fixture
def fake_client(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(services, "get_client", lambda: client)
    return client


@pytest.fixture
def conversation(student):
    return Conversation.objects.create(user=student, mode=Conversation.Mode.MENTOR)


def test_reply_saves_messages_and_sends_request(api, student, conversation, fake_client, settings):
    response = api(student).post(
        f"/api/v1/ai/conversations/{conversation.id}/messages/",
        {"text": "Robototexnikani qanday o'rganay?"},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["content"] == "Salom! Keling, reja tuzamiz."
    assert conversation.messages.count() == 2

    call = fake_client.calls[0]
    assert call["model"] == settings.ANTHROPIC_MODEL
    assert call["fallbacks"] == "default"
    assert call["betas"] == [services.FALLBACK_BETA]
    assert call["messages"][-1] == {"role": "user", "content": "Robototexnikani qanday o'rganay?"}
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}

    conversation.refresh_from_db()
    assert conversation.title == "Robototexnikani qanday o'rganay?"


def test_history_is_sent(student, conversation, fake_client):
    services.reply(conversation, "Birinchi savol")
    services.reply(conversation, "Ikkinchi savol")
    messages = fake_client.calls[1]["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]


def test_context_has_no_personal_data(student, conversation, fake_client):
    student.first_name, student.last_name = "Aziza", "Rahimova"
    student.save()
    services.reply(conversation, "Salom")
    context = fake_client.calls[0]["system"][1]["text"]
    assert "Aziza" not in context and "Rahimova" not in context
    assert "Kompyuter injiniringi" in context


def test_refusal_returns_safe_message(student, conversation, monkeypatch):
    monkeypatch.setattr(services, "get_client", lambda: FakeClient(text="", stop_reason="refusal"))
    message = services.reply(conversation, "...")
    assert message.content == services.REFUSAL_REPLY


def test_daily_limit(api, student, conversation, fake_client, settings):
    settings.AI_DAILY_MESSAGE_LIMIT = 1
    client = api(student)
    url = f"/api/v1/ai/conversations/{conversation.id}/messages/"
    assert client.post(url, {"text": "1"}, format="json").status_code == 201
    assert client.post(url, {"text": "2"}, format="json").status_code == 429
    assert client.get("/api/v1/ai/quota/").data == {"used": 1, "limit": 1, "remaining": 0}


def test_api_error_returns_503_and_saves_nothing(api, student, conversation, monkeypatch):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    error = anthropic.APIConnectionError(request=request)
    monkeypatch.setattr(services, "get_client", lambda: FakeClient(error=error))
    response = api(student).post(
        f"/api/v1/ai/conversations/{conversation.id}/messages/", {"text": "Salom"}, format="json"
    )
    assert response.status_code == 503
    assert Message.objects.count() == 0


def test_cannot_access_others_conversation(api, make_user, conversation, fake_client):
    response = api(make_user()).post(
        f"/api/v1/ai/conversations/{conversation.id}/messages/", {"text": "x"}, format="json"
    )
    assert response.status_code == 404


def test_missing_api_key_gives_friendly_error(api, student, conversation, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(services, "_client", None)
    response = api(student).post(
        f"/api/v1/ai/conversations/{conversation.id}/messages/", {"text": "Salom"}, format="json"
    )
    assert response.status_code == 503
    assert response.data["detail"] == services.NOT_CONFIGURED
    assert Message.objects.count() == 0

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.ai import services
from apps.ai.models import Conversation

from ..forms import ChatForm, ConversationForm
from .common import run_service

MODES = [
    {
        "value": Conversation.Mode.MENTOR,
        "emoji": "🧭",
        "title": "AI Mentor",
        "text": "Maqsadingizni ayting: bosqichma-bosqich o'quv yo'l xaritasini tuzib beraman.",
        "prompts": ["Robototexnikani noldan o'rganmoqchiman", "Python bo'yicha 3 oylik reja tuzib ber"],
    },
    {
        "value": Conversation.Mode.IDEA_CHECK,
        "emoji": "💡",
        "title": "G'oya tekshiruvchi",
        "text": "Startup g'oyangizni yozing: bozor, raqobat va xavflarni halol tahlil qilaman.",
        "prompts": ["Talabalar uchun yotoqxona topish ilovasi", "Fermerlar uchun aqlli sug'orish tizimi"],
    },
    {
        "value": Conversation.Mode.CAREER,
        "emoji": "🚀",
        "title": "Kelajakdagi men",
        "text": "Ko'nikmalaringizga qarab mos kasblar va yetishmayotgan bilimlarni ko'rsataman.",
        "prompts": ["Menga qaysi kasblar mos keladi?", "Data Analyst bo'lish uchun nima yetishmaydi?"],
    },
]


@login_required
def ai_home(request):
    conversations = Conversation.objects.filter(user=request.user)[:20]
    used = services.messages_today(request.user)
    return render(
        request,
        "web/ai/index.html",
        {
            "modes": MODES,
            "conversations": conversations,
            "used": used,
            "limit": settings.AI_DAILY_MESSAGE_LIMIT,
            "ai_ready": services.is_configured(),
        },
    )


@login_required
@require_POST
def ai_start(request):
    form = ConversationForm(request.POST)
    if not form.is_valid():
        return redirect("web:ai")
    conversation = Conversation.objects.create(user=request.user, mode=form.cleaned_data["mode"])
    text = request.POST.get("text", "").strip()
    if text:
        run_service(request, services.reply, conversation, text[:4000])
    return redirect("web:ai-chat", pk=conversation.pk)


@login_required
def ai_chat(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk, user=request.user)
    if request.method == "POST":
        form = ChatForm(request.POST)
        if form.is_valid():
            run_service(request, services.reply, conversation, form.cleaned_data["text"])
        return redirect("web:ai-chat", pk=pk)
    mode = next(m for m in MODES if m["value"] == conversation.mode)
    return render(
        request,
        "web/ai/chat.html",
        {"conversation": conversation, "messages_list": conversation.messages.all(), "mode": mode},
    )


@login_required
@require_POST
def ai_delete(request, pk):
    get_object_or_404(Conversation, pk=pk, user=request.user).delete()
    return redirect("web:ai")

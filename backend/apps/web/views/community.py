from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Exists, OuterRef
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.community import services
from apps.community.models import Event, EventRegistration, Post
from apps.notifications.services import notify

from ..forms import CommentForm, EventForm, PostForm
from .common import paginate, reviewer_required, run_service


def _posts(user):
    liked = Post.likes.through.objects.filter(post_id=OuterRef("pk"), user_id=user.id)
    return (
        Post.objects.filter(is_hidden=False)
        .select_related("author", "author__faculty", "project")
        .annotate(
            like_count=Count("likes", distinct=True),
            comment_count=Count("comments", distinct=True),
            liked=Exists(liked),
        )
        .order_by("-created_at")
    )


@login_required
def feed(request):
    form = PostForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        project_id = request.POST.get("project")
        if project_id and request.user.project_memberships.filter(project_id=project_id, status="active").exists():
            post.project_id = project_id
        post.save()
        messages.success(request, "Post e'lon qilindi")
        return redirect("web:feed")
    return render(
        request, "web/community/feed.html", {"page": paginate(request, _posts(request.user), 10), "form": form}
    )


@login_required
def post_detail(request, pk):
    post = get_object_or_404(_posts(request.user), pk=pk)
    form = CommentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        comment.save()
        if post.author_id != request.user.id:
            notify(
                post.author,
                f"{request.user.get_full_name() or request.user.username} postingizga izoh yozdi",
                comment.text[:120],
                url=f"/feed/{post.pk}/",
                icon="💬",
            )
        return redirect("web:post-detail", pk=pk)
    comments = post.comments.select_related("author")
    return render(request, "web/community/post_detail.html", {"post": post, "form": form, "comments": comments})


@login_required
@require_POST
def post_like(request, pk):
    post = get_object_or_404(Post, pk=pk, is_hidden=False)
    if post.likes.filter(pk=request.user.pk).exists():
        post.likes.remove(request.user)
        liked = False
    else:
        post.likes.add(request.user)
        liked = True
    if request.headers.get("X-Requested-With") == "fetch":
        return JsonResponse({"liked": liked, "like_count": post.likes.count()})
    target = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(target, {request.get_host()}, request.is_secure()):
        target = reverse("web:feed")
    return redirect(target)


@login_required
@require_POST
def post_delete(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if post.author_id != request.user.id and not request.user.is_management:
        raise PermissionDenied
    post.delete()
    messages.info(request, "Post o'chirildi")
    return redirect("web:feed")


@login_required
def event_list(request):
    mine = EventRegistration.objects.filter(event_id=OuterRef("pk"), user_id=request.user.id)
    events = Event.objects.annotate(registered_count=Count("registrations"), is_registered=Exists(mine))
    past = request.GET.get("past") == "1"
    now = timezone.now()
    events = (
        events.filter(ends_at__lt=now).order_by("-starts_at")
        if past
        else events.filter(ends_at__gte=now).order_by("starts_at")
    )
    return render(request, "web/events/list.html", {"page": paginate(request, events), "past": past})


@login_required
def event_detail(request, pk):
    event = get_object_or_404(Event.objects.annotate(registered_count=Count("registrations")), pk=pk)
    registration = EventRegistration.objects.filter(event=event, user=request.user).first()
    is_organizer = request.user.is_reviewer or event.created_by_id == request.user.id
    context = {
        "event": event,
        "registration": registration,
        "is_organizer": is_organizer,
        "checkin_url": request.build_absolute_uri(reverse("web:event-checkin") + f"?code={event.checkin_code}")
        if is_organizer
        else None,
        "attendees": event.registrations.select_related("user").order_by("-attended_at") if is_organizer else None,
        "is_live": event.starts_at <= timezone.now() <= event.ends_at,
        "is_over": event.ends_at < timezone.now(),
    }
    return render(request, "web/events/detail.html", context)


@login_required
@require_POST
def event_register(request, pk):
    event = get_object_or_404(Event, pk=pk)
    run_service(request, services.register, event, request.user, success="Ro'yxatdan o'tdingiz! Ko'rishguncha 👋")
    return redirect("web:event-detail", pk=pk)


@login_required
def event_checkin(request):
    """QR kod skanerlanganda ochiladigan sahifa."""
    code = request.POST.get("code") or request.GET.get("code", "")
    event = Event.objects.filter(checkin_code=code).first() if code else None
    if request.method == "POST":
        registration = run_service(request, services.check_in, code, request.user)
        if registration:
            messages.success(request, f"Check-in qabul qilindi! +{registration.event.xp_reward} XP")
            return redirect("web:event-detail", pk=registration.event_id)
    return render(request, "web/events/checkin.html", {"event": event, "code": code})


@reviewer_required
def event_form(request, pk=None):
    instance = get_object_or_404(Event, pk=pk) if pk else None
    form = EventForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        event = form.save(commit=False)
        if instance is None:
            event.created_by = request.user
        event.save()
        messages.success(request, "Tadbir saqlandi")
        return redirect("web:event-detail", pk=event.pk)
    return render(request, "web/events/form.html", {"form": form, "instance": instance})

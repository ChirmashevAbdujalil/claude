from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.discovery import services
from apps.discovery.models import Challenge, Submission
from apps.discovery.selectors import visible_challenges

from ..forms import ChallengeForm, SubmissionForm
from .common import paginate, reviewer_required, run_service

TABS = [
    ("open", "Ochiq"),
    ("daily", "Kunlik"),
    ("weekly", "Haftalik"),
    ("monthly", "Oylik"),
    ("mine", "Mening javoblarim"),
]


@login_required
def challenge_list(request):
    tab = request.GET.get("tab", "open")
    my_submissions = {s.challenge_id: s for s in Submission.objects.filter(user=request.user)}
    if tab == "mine":
        challenges = visible_challenges(request.user, include_closed=True).filter(pk__in=my_submissions.keys())
    else:
        challenges = visible_challenges(request.user)
        if tab in {"daily", "weekly", "monthly"}:
            challenges = challenges.filter(kind=tab)
    page = paginate(request, challenges.order_by("ends_at"))
    for challenge in page:
        challenge.my_submission = my_submissions.get(challenge.pk)
    return render(request, "web/challenges/list.html", {"page": page, "tab": tab, "tabs": TABS})


@login_required
def challenge_detail(request, pk):
    challenge = get_object_or_404(visible_challenges(request.user, include_closed=True), pk=pk)
    submission = Submission.objects.filter(challenge=challenge, user=request.user).first()
    form = SubmissionForm(request.POST or None)
    if request.method == "POST" and submission is None and form.is_valid():
        result = run_service(request, services.submit, challenge, request.user, **form.cleaned_data)
        if result is not None:
            if result.status == Submission.Status.ACCEPTED:
                request.session["celebrate"] = result.xp_awarded
            elif result.status == Submission.Status.REJECTED:
                messages.error(request, "Javob noto'g'ri. Keyingi safar albatta chiqadi!")
            else:
                messages.success(request, "Yechim yuborildi. O'qituvchi tekshirgach XP olasiz.")
            return redirect("web:challenge-detail", pk=pk)
    celebrate = request.session.pop("celebrate", None)
    return render(
        request,
        "web/challenges/detail.html",
        {"challenge": challenge, "submission": submission, "form": form, "celebrate": celebrate},
    )


@reviewer_required
def challenge_create(request, pk=None):
    instance = get_object_or_404(Challenge, pk=pk) if pk else None
    form = ChallengeForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        challenge = form.save(commit=False)
        if instance is None:
            challenge.created_by = request.user
        challenge.save()
        messages.success(request, "Challenge saqlandi")
        return redirect("web:challenge-detail", pk=challenge.pk)
    return render(request, "web/challenges/form.html", {"form": form, "instance": instance})

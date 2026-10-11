from django.db import IntegrityError, transaction

from apps.arena import services as arena
from apps.notifications.services import notify

from .models import Challenge, Submission


class SubmissionError(Exception):
    pass


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _accept(submission: Submission, score: int | None, reviewer=None, feedback: str = "") -> Submission:
    xp = submission.challenge.xp_reward
    if score is not None:
        xp = round(xp * score / 100)
    submission.status = Submission.Status.ACCEPTED
    submission.score = score
    submission.reviewed_by = reviewer
    submission.feedback = feedback
    tx = arena.award(
        submission.user,
        arena.Reason.CHALLENGE,
        xp,
        ref=f"submission:{submission.pk}",
        note=submission.challenge.title,
    )
    submission.xp_awarded = tx.xp if tx else 0
    submission.save()
    arena.grant_badge(submission.user, "first-challenge")
    if reviewer is not None:
        notify(
            submission.user,
            f"Yechimingiz qabul qilindi: +{submission.xp_awarded} XP",
            f"«{submission.challenge.title}»" + (f": {feedback}" if feedback else ""),
            url=f"/challenges/{submission.challenge_id}/",
            icon="✅",
            kind="success",
        )
    return submission


@transaction.atomic
def submit(challenge: Challenge, user, answer: str = "", link: str = "") -> Submission:
    if not challenge.is_open:
        raise SubmissionError("Challenge yopiq yoki hali boshlanmagan")
    if challenge.faculty_id and challenge.faculty_id != user.faculty_id:
        raise SubmissionError("Bu challenge boshqa fakultet uchun")
    if not answer.strip() and not link:
        raise SubmissionError("Javob yoki havola kiriting")
    try:
        with transaction.atomic():
            submission = Submission.objects.create(challenge=challenge, user=user, answer=answer, link=link)
    except IntegrityError as exc:
        raise SubmissionError("Siz bu challenge'ga javob yuborgansiz") from exc

    arena.touch_streak(user)

    if challenge.expected_answer:
        if _normalize(answer) == _normalize(challenge.expected_answer):
            _accept(submission, score=None, feedback="Avtomatik tekshirildi: to'g'ri")
        else:
            submission.status = Submission.Status.REJECTED
            submission.feedback = "Avtomatik tekshirildi: noto'g'ri"
            submission.save(update_fields=["status", "feedback"])
    return submission


@transaction.atomic
def review(submission: Submission, reviewer, accept: bool, score: int | None = None, feedback: str = "") -> Submission:
    submission = Submission.objects.select_for_update().select_related("challenge", "user").get(pk=submission.pk)
    if submission.status != Submission.Status.PENDING:
        raise SubmissionError("Bu yechim allaqachon tekshirilgan")
    if submission.user_id == reviewer.id:
        raise SubmissionError("O'z yechimingizni tekshira olmaysiz")
    if accept:
        return _accept(submission, score, reviewer, feedback)
    submission.status = Submission.Status.REJECTED
    submission.score = score
    submission.reviewed_by = reviewer
    submission.feedback = feedback
    submission.save()
    notify(
        submission.user,
        "Yechimingiz rad etildi",
        f"«{submission.challenge.title}»" + (f": {feedback}" if feedback else ". O'qituvchi izohini ko'ring."),
        url=f"/challenges/{submission.challenge_id}/",
        icon="📝",
        kind="warning",
    )
    return submission

"""Talabalar javoblari fakultetlar kesimida (Word): har bir fakultet yangi varaqdan.

Tarkibi: umumiy jadval (fakultet bo'yicha javoblar soni), keyin har bir fakultet uchun talabalar ro'yxati va har bir
talabaning to'liq javoblari. Natijalar sahifasidagi filtrlar (fakultet, kurs, guruh, tyutor, javob sharti) hisobga
olinadi.
"""

from django.utils import timezone

from .docx import DARK, LIGHT, MUTED, TEAL, _banner, _cell, _note, _p, _row, _run, _table, package
from .models import Question
from .services import _label

Kind = Question.Kind
WIDTH = 10466  # A4 kitob varaq, 1,27 sm hoshiya
SOFT = "E2F0F4"
NO_FACULTY = "Fakultet ko'rsatilmagan"
PAGE_BREAK = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
LIST_WIDTHS = [500, 3300, 700, 1300, 2500, 2166]  # №, F.I.Sh., kurs, guruh, tyutor, telefon
ANSWER_WIDTHS = [3700, WIDTH - 3700]


def _head(titles, widths):
    return _row(
        [
            _cell(_p(_run(t, bold=True, size=8.5, color="FFFFFF")), w, fill=TEAL)
            for t, w in zip(titles, widths, strict=True)
        ],
        header=True,
        height=360,
    )


def _overview(groups, total):
    widths = [5600, 1600, 3266]
    rows = [_head(["Fakultet", "Javoblar", "Ulushi"], widths)]
    for index, (faculty, items) in enumerate(groups):
        share = round(len(items) * 100 / total) if total else 0
        cells = [
            _p(_run(faculty, bold=True, size=9.5)),
            _p(_run(len(items), bold=True, size=10, color=DARK), align="center"),
            _p(_run(f"{share}%", size=9.5, color=MUTED), align="center"),
        ]
        fill = LIGHT if index % 2 else None
        rows.append(_row([_cell(c, w, fill=fill) for c, w in zip(cells, widths, strict=True)], height=360))
    cells = [
        _p(_run("Jami", bold=True, size=9.5)),
        _p(_run(total, bold=True, size=10), align="center"),
        _p(_run("100%", size=9.5), align="center"),
    ]
    rows.append(_row([_cell(c, w, fill=SOFT) for c, w in zip(cells, widths, strict=True)], height=360))
    return _table(rows, widths)


def _student_list(items):
    rows = [_head(["№", "F.I.Sh.", "Kurs", "Guruh", "Tyutor", "Telefon"], LIST_WIDTHS)]
    for number, response in enumerate(items, 1):
        cells = [
            _p(_run(number, size=8.5, color=MUTED), align="center"),
            _p(_run(response.display_name, bold=True, size=9)),
            _p(_run(response.course or "—", size=9), align="center"),
            _p(_run(response.group or "—", size=9)),
            _p(_run(response.tutor.full_name if response.tutor_id else "—", size=8.5)),
            _p(_run(response.phone or "—", size=8.5)),
        ]
        fill = LIGHT if number % 2 == 0 else None
        rows.append(_row([_cell(c, w, fill=fill) for c, w in zip(cells, LIST_WIDTHS, strict=True)], height=330))
    return _table(rows, LIST_WIDTHS)


def _answer(question, response, files):
    if question.kind == Kind.FILE:
        names = [f.name for f in files.get(question.pk, [])]
        return ", ".join(names)
    value = response.answers.get(str(question.pk))
    if value in (None, "", []):
        return ""
    if question.kind == Kind.SCALE:
        return f"{value} / {question.scale_max}"
    return _label(question, value)


def _student(number, response, questions):
    meta = " · ".join(
        filter(
            None,
            [
                f"{response.course}-kurs" if response.course else "",
                response.group,
                f"tyutor: {response.tutor.full_name}" if response.tutor_id else "",
                response.phone,
                timezone.localtime(response.submitted_at).strftime("%d.%m.%Y %H:%M"),
            ],
        )
    )
    head = _table(
        [
            _row(
                [
                    _cell(
                        _p(_run(f"{number}. ", bold=True, size=10.5, color=TEAL),
                           _run(response.display_name, bold=True, size=10.5, color=DARK))
                        + _p(_run(meta or " ", size=8, color=MUTED)),
                        WIDTH,
                        fill=SOFT,
                        margins=(90, 160, 90, 160),
                    )
                ]
            )
        ],
        [WIDTH],
        borders=False,
    )  # fmt: skip
    files = {}
    for stored in response.files.all():
        files.setdefault(stored.question_id, []).append(stored)
    rows = []
    for question in questions:
        text = _answer(question, response, files)
        if not text:
            continue
        cells = [
            _p(_run(question.title, size=8.5, color=MUTED)),
            _p(
                _run(
                    text, size=9, color=DARK, bold=question.kind in Question.CHOICE_KINDS or question.kind == Kind.SCALE
                )
            ),
        ]
        rows.append(_row([_cell(c, w) for c, w in zip(cells, ANSWER_WIDTHS, strict=True)], cant_split=False))
    body = _table(rows, ANSWER_WIDTHS) if rows else _p(_run("Javoblar bo'sh", italic=True, size=9, color=MUTED))
    return head + body + _p(after=160)


def render(survey, responses, *, institution, prepared_by="", filter_note="") -> bytes:
    responses = list(
        responses.select_related("faculty", "tutor", "user")
        .prefetch_related("files")
        .order_by("faculty__name", "course", "group", "full_name", "submitted_at")
    )
    questions = [q for q in survey.questions.all() if q.is_answerable]
    groups = []
    for response in responses:
        name = response.faculty.name if response.faculty_id else NO_FACULTY
        if not groups or groups[-1][0] != name:
            groups.append((name, []))
        groups[-1][1].append(response)
    groups.sort(key=lambda group: (group[0] == NO_FACULTY, group[0]))
    now = timezone.localtime()

    subtitle = f"Talabalar javoblari fakultetlar kesimida · {institution} · {now:%d.%m.%Y %H:%M}"
    parts = [_banner(survey.title, subtitle, WIDTH), _p(after=160)]
    if filter_note:
        parts += [_note(f"Filtr: {filter_note}", WIDTH), _p(after=160)]
    parts += [
        _p(_run("Umumiy ko'rsatkich", bold=True, size=12, color=DARK), after=100, keep=True),
        _overview(groups, len(responses)),
        _p(
            _run(
                f"Har bir fakultet keyingi varaqdan boshlanadi: avval talabalar ro'yxati, so'ng har bir talabaning "
                f"javoblari ({len(questions)} ta savol; javob berilmagan savollar ko'rsatilmaydi).",
                size=8.5,
                color=MUTED,
            ),
            before=120,
        ),
    ]
    for faculty, items in groups:
        parts += [
            PAGE_BREAK,
            _banner(faculty, f"{len(items)} nafar talaba javob bergan · {survey.title}", WIDTH),
            _p(after=140),
            _p(_run("Talabalar ro'yxati", bold=True, size=11, color=DARK), after=80, keep=True),
            _student_list(items),
            _p(_run("Talabalar javoblari", bold=True, size=11, color=DARK), before=280, after=100, keep=True),
        ]
        parts += [_student(number, response, questions) for number, response in enumerate(items, 1)]
    if not groups:
        parts.append(
            _p(_run("Tanlangan filtr bo'yicha javob topilmadi.", italic=True, size=10, color=MUTED), before=200)
        )
    parts.append(
        _p(
            _run(f"Tayyorladi: {prepared_by or '________________'}   ____________ (imzo)", size=9.5, color=MUTED),
            before=360,
        )
    )
    return package(
        "".join(parts),
        landscape=False,
        title=f"{survey.title} — javoblar",
        author=institution,
        footer=f"{institution} · talabalar javoblari fakultetlar kesimida",
    )

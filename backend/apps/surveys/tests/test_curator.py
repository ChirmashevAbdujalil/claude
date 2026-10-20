import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.surveys import services
from apps.tenants.context import default_institution


@pytest.fixture
def rector(make_user):
    return make_user(role=User.Role.RECTOR, username="rektor")


def test_curator_block_on_fill_and_thanks_pages(rector):
    institution = default_institution()
    assert institution.curator_enabled and institution.curator_name == "Abdujalil Chirmashev"  # migratsiyadan
    assert institution.curator_url == "https://t.me/abdujalil_chirmashev" and institution.curator_photo

    survey = services.create_survey(rector, "feedback")
    services.publish(survey)
    client = Client()
    fill = client.get(reverse("web:survey-fill", args=[survey.token])).content.decode()
    assert "Abdujalil Chirmashev" in fill and "sv-sign" in fill and "t.me/abdujalil_chirmashev" not in fill
    url = reverse("web:survey-fill", args=[survey.token])
    scale = survey.questions.get(kind="scale")
    client.post(url, {f"q{scale.pk}": "5"})
    thanks = client.get(reverse("web:survey-thanks", args=[survey.token])).content.decode()
    assert "sv-curator" in thanks and "https://t.me/abdujalil_chirmashev" in thanks
    assert "E&#x27;lonlarni kuzatib borish" in thanks or "E'lonlarni kuzatib borish" in thanks

    admin = Client()
    admin.force_login(rector)
    response = admin.post(
        reverse("web:institution-settings"),
        {
            "form": "curator",
            "curator-curator_name": "Abdujalil Chirmashev",
            "curator-curator_title": "Mas'ul",
            "curator-curator_url": "t.me/boshqa_kanal",
            "curator-curator_message": "Salom",
        },
    )
    assert response.status_code == 302
    institution.refresh_from_db()
    assert not institution.curator_enabled and institution.curator_url == "https://t.me/boshqa_kanal"
    thanks = client.get(reverse("web:survey-thanks", args=[survey.token])).content.decode()
    assert "sv-curator" not in thanks


def test_long_curator_message_with_bold_and_paragraphs(rector):
    from apps.web.templatetags.web_tags import rich_text

    message = (
        "Assalomu alaykum! Men — **Abdujalil Chirmashev**.\n"
        + "Uzun matn. " * 80
        + "\n\n📢 Yangi xatboshi <script>x</script>"
    )
    assert len(message) > 300
    admin = Client()
    admin.force_login(rector)
    admin.post(
        reverse("web:institution-settings"),
        {"form": "curator", "curator-curator_enabled": "on", "curator-curator_name": "Abdujalil Chirmashev",
         "curator-curator_url": "https://t.me/abdujalil_chirmashev", "curator-curator_message": message},
    )  # fmt: skip
    institution = default_institution()
    institution.refresh_from_db()
    assert institution.curator_message == message.replace("\n", "\r\n") or institution.curator_message == message

    html = rich_text(message)
    assert "<b>Abdujalil Chirmashev</b>" in html and html.count("<p>") == 2 and "<br>" in html
    assert "<script>" not in html and "&lt;script&gt;" in html

    survey = services.create_survey(rector, "feedback")
    services.publish(survey)
    page = Client().get(reverse("web:survey-thanks", args=[survey.token])).content.decode()
    assert "<b>Abdujalil Chirmashev</b>" in page and "Uzun matn. Uzun matn." in page

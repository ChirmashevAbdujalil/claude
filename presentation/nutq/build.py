"""Pitch nutqini A4 HTML sahifalarga yig'adi; PDF ga `node pdf.js` aylantiradi.

Matnda: **qalin** = urg'u, // = pauza. Apostroflar o'zbek imlosiga (oʻ, gʻ, ʼ) o'giriladi.
"""

import html
import re
from pathlib import Path

HERE = Path(__file__).parent

ACTS = [
    ("I", "Kirish", "0:00", "0:50"),
    ("II", "Muammo va yechim", "0:50", "2:35"),
    ("III", "Mahsulot", "2:35", "4:10"),
    ("IV", "Isbot va biznes", "4:10", "5:30"),
    ("V", "So'rov va yakun", "5:30", "6:30"),
]

# (akt, slayd raqami, slayd nomi, vaqt, matn, sahna ko'rsatmasi, qisqartirsa bo'ladimi)
BLOCKS = [
    ("I", 1, "Muqova", "0:00 – 0:25",
     "Assalomu alaykum, hurmatli hakamlar! Mening ismim **Abdujalil Chirmashev**, men ANDTI Talent Hub "
     "loyihasining rahbariman. // Bir savol bilan boshlay. // Keyingi respublika olimpiadasining g'olibi, "
     "kelajakdagi kuchli muhandis yoki startap asoschisi **hozir shu institutda o'qiyotgan bo'lishi mumkin**. "
     "Lekin bugun buni hech kim bilmaydi: na rahbariyat, na o'qituvchi, ba'zan talabaning o'zi ham.",
     "Birinchi gapni yoddan ayting. Savoldan keyin 2 soniya jim turing va hakamlarga qarang.", False),
    ("I", 2, "Rektor so'zi", "0:25 – 0:50",
     "Bu loyihani biz o'ylab topmadik. // Rektorimiz talabalar bilan uchrashuvda ochiq aytdi: iqtidorli "
     "talabalar bilan ishlashda tartibsizlik bor; ularni tartibga solish va har birini iqtidoriga qarab "
     "to'g'ri yo'naltirish uchun raqamli platforma kerak. // Startap tilida bu eng kuchli signal: "
     "**mahsulotni mijozning o'zi so'rayapti.**",
     "Iqtibosni sekinroq o'qing. «Mazmunan» so'zini qo'shing.", False),
    ("II", 3, "Muammo", "0:50 – 1:15",
     "Biz o'rganib chiqdik va uchta muammoni ko'rdik. **Birinchi:** iqtidorli talabalar ro'yxati tarqoq: "
     "Excel, qog'oz, Telegram guruhlar. **Ikkinchi:** topilgan iqtidorga mas'ul mentor va aniq reja yo'q. "
     "**Uchinchi:** olimpiada, grant va tanlovlar haqida kerakli talaba kech biladi yoki umuman bilmaydi. "
     "// Natijada **iqtidor topiladi-yu, yo'qolib ketadi.**",
     "Har bir muammoda barmoq bilan sanang: bir, ikki, uch.", False),
    ("II", 4, "Yechim", "1:15 – 1:35",
     "Yechimimiz: **ANDTI Talent Hub**. Iqtidor bilan ishlashning to'liq zanjiri bitta platformada: "
     "// **aniqlash, // mentor, // reja, // natija.** Talaba, o'qituvchi, dekanat, rektorat, homiy va "
     "ish beruvchi bitta tizimda ishlaydi.",
     "To'rt so'zni alohida, urg'u bilan ayting: bu nutqning asosiy formulasi.", False),
    ("II", 5, "Diagnostika", "1:35 – 2:00",
     "Talaba **10 savollik, 3 daqiqalik** diagnostikadan o'tadi. Muhimi: natija faqat test javobiga emas, "
     "real ishiga ham tayanadi: 70 foiz javoblar, 30 foiz tasdiqlangan ko'nikma va yutuqlar. Tizim olti "
     "yo'nalishdan birini aniqlaydi: ilmiy tadqiqot, olimpiada, ixtirochilik, IT, startap yoki dizayn. "
     "// Yangi grant yoki tanlov chiqsa, platforma uni mos talabalarga Telegram orqali o'zi yuboradi. "
     "**Talaba imkoniyatni qidirmaydi, imkoniyat talabani topadi.**",
     None, False),
    ("II", 6, "Iqtidorlar reyestri", "2:00 – 2:20",
     "O'qituvchi «uchqun» belgisini qo'ysa yoki olimpiada, maqola, patent tasdiqlansa, talaba iqtidorlar "
     "reyestriga **o'zi tushadi**. Holati to'rt bosqichda ko'rinadi. Mentor semestr uchun muddatli maqsad "
     "qo'yadi. Muddat o'tib ketsa yoki talaba 14 kun mentorsiz qolsa, tizim dekanatga o'zi eslatadi. "
     "// **Endi hech kim e'tibordan chetda qolmaydi.**",
     None, False),
    ("II", 7, "Rektorat hisoboti", "2:20 – 2:35",
     "Rektorat uchun: **bitta tugma, rasmiy hisobot.** Fakultetlar kesimi, mentorlar faoliyati, natijalar "
     "va e'tibor talab qiladigan talabalar, PDF yoki Excelda. Vazirlikka hisobot **kunlab emas, daqiqalar** "
     "oladi.",
     None, False),
    ("III", 8, "Nishonlar va darajalar", "2:35 – 2:55",
     "Lekin eng yaxshi tizim ham, talaba kirmasa, ishlamaydi. // Shuning uchun talabani ushlab turish "
     "mexanikasini qurdik: har bir foydali ish uchun ball, «Yangi boshlovchi»dan «Afsona»gacha "
     "**5 ta daraja** va **14 xil nishon**. 7, 30 va 100 kunlik faollik seriyasi uchun alohida nishonlar bor.",
     "Ohangni jonlantiring: bu qism talabalar uchun qiziqarli.", False),
    ("III", 9, "Tanga va sovg'alar", "2:55 – 3:10",
     "Ball tangaga aylanadi, tanga esa **real sovg'aga**: oshxona taloni, kitob, futbolka, onlayn kurs "
     "// va eng qimmati: **rektor bilan choy.** Sovg'alar omborini rektorat boshqaradi.",
     "«Rektor bilan choy»dan keyin to'xtang: zalda tabassum bo'ladi.", False),
    ("III", 10, "Homiylar va liga", "3:10 – 3:25",
     "Sovg'alarni **homiy kompaniyalar** moliyalaydi: evaziga ular iqtidorli talabalar bilan tanishadi. "
     "**OTMlararo ligada** esa oliygohlar 30 kunlik o'rtacha ball bo'yicha teng sharoitda bellashadi. "
     "Liga yangi OTMlarni platformaga o'zi olib keladi.",
     None, True),
    ("III", 11, "Loyiha va jamoa", "3:25 – 3:40",
     "Talaba g'oyasini loyiha sifatida e'lon qiladi, tizim unga ko'nikmasi mos jamoadoshlarni tavsiya "
     "qiladi. Loyiha **g'oyadan prototip, sinov va startapgacha** boradi. // Aytgancha, bu Startaplar "
     "klubining o'zi uchun ham tayyor vosita.",
     "Oxirgi gapni klub vakillariga qarab ayting.", True),
    ("III", 12, "Karyera va AI rezyume", "3:40 – 3:55",
     "To'plangan hamma narsa karyeraga ishlaydi: ommaviy portfolio va **sun'iy intellekt yozgan rezyume**, "
     "o'zbek va ingliz tilida. Rezyumedagi QR kod orqali ish beruvchi ma'lumot haqiqiyligini tekshiradi.",
     None, True),
    ("III", 13, "AI, ishonch va Telegram", "3:55 – 4:10",
     "Sun'iy intellekt talabaga **24/7 mentor** bo'ladi, o'qituvchiga baho qoralamasini tayyorlaydi, "
     "lekin qarorni doim odam qabul qiladi. Har bir xodim harakati **o'zgartirib bo'lmaydigan jurnalga** "
     "yoziladi. Talabalar Telegramda yashaydi, shuning uchun platforma Telegramda ham ishlaydi.",
     None, True),
    ("IV", 14, "Ishlaydigan mahsulot", "4:10 – 4:25",
     "Va eng muhimi: // bu taqdimotdagi rasm emas. **Platforma ishlab turibdi:** // 15 modul, // 6 rol, "
     "// 226 avtomatik test, Payme va Click to'lovlari ulangan. 6 oylik pilotda maqsadimiz: 500 faol "
     "talaba, 100 iqtidor reyestrda, ularning 80 foiziga mentor.",
     "Raqamlar orasida to'xtang. Imkoni bo'lsa, telefonda natijalar sahifasini ko'rsating.", False),
    ("IV", 15, "Bozor", "4:25 – 4:40",
     "Bu muammo faqat bizda emas: O'zbekistondagi **200 dan ortiq oliygohning** har birida bor. Faqat OTM "
     "obunalarining o'zi yiliga **3 milliard so'mdan ortiq** bozor. Uch yillik maqsadimiz: 20 ta OTM, "
     "yiliga 300 million so'm.",
     None, False),
    ("IV", 16, "Biznes model", "4:40 – 5:00",
     "Biznes modelimiz **B2B SaaS**: talabalar uchun bepul, obunani OTM to'laydi. Pilot 90 kun bepul, "
     "Standart tarif oyiga 1,5 million so'm, Premium 3,5 million. Bu bitta xodimning maoshidan arzon, "
     "lekin butun institut uchun ishlaydi. // Yalpi marja taxminan 80 foiz: **ikkita obuna loyihaning "
     "oylik xarajatini qoplaydi.**",
     "Hakamlar eng ko'p shu slaydni yozib oladi: shoshilmang.", False),
    ("IV", 17, "Raqobat", "5:00 – 5:10",
     "HEMIS bilan raqobatlashmaymiz: HEMIS baholar va hujjatlar tizimi, biz esa **iqtidorni topish va "
     "rivojlantirish** tizimimiz. Biz uni to'ldiramiz.",
     None, True),
    ("IV", 18, "Bozorga chiqish va yo'l xaritasi", "5:10 – 5:30",
     "Rejamiz aniq: shu kuzda **ANDTIda pilot**, bahorda butun institut, 2027-yil kuzida birinchi uchta "
     "to'lovchi OTM, keyin 20 ta OTM va Markaziy Osiyo. Mijozlarni rektoratlarga taqdimot, bepul pilot va "
     "OTMlararo liga orqali olamiz.",
     "18 va 19-slaydlarni shu matn davomida almashtiring.", False),
    ("V", 20, "Xarajatlar", "5:30 – 5:45",
     "Byudjetimiz minimal: 6 oylik pilot uchun **13,2 million so'm**. Bu server, sun'iy intellekt xizmati, "
     "ochilish xakatoni sovg'a fondi va yuridik rasmiylashtirish. Jamoa maoshi kiritilmagan: biz "
     "ko'ngilli ishlaymiz.",
     None, False),
    ("V", 21, "Bizga qanday yordam bera olasiz", "5:45 – 6:05",
     "Sizdan nima so'raymiz? Beshta narsa: // **birinchi**, 13,2 million so'm grant; **ikkinchi**, server; "
     "**uchinchi**, rektor buyrug'i bilan rasmiy pilot; **to'rtinchi**, biznes va yuridik mentorlik; "
     "**beshinchi**, boshqa OTMlar va homiylar bilan tanishuv. // Bizdan esa taklif: **Startaplar klubining "
     "tanlovlarini platformamizda bepul o'tkazamiz.**",
     "Bu hakamlarning «sizga qanday yordam bera olamiz?» savoliga tayyor javob.", False),
    ("V", 22, "Jamoa", "6:05 – 6:15",
     "Jamoamiz: men mahsulot va arxitektura uchun javobgarman, [Ism] dasturlash, [Ism] dizayn va "
     "marketing bo'yicha. Platformani **zamonaviy AI vositalari** yordamida qurdik, shuning uchun MVP tez "
     "va arzon tayyor bo'ldi.",
     "Kvadrat qavsga jamoadoshlar ismini qo'ying. Ular zalda bo'lsa, qo'l bilan ko'rsating.", False),
    ("V", 23, "Yakun", "6:15 – 6:30",
     "Hurmatli hakamlar! // Har bir talabada iqtidor bor. Biz uni **ko'rinadigan, // yo'naltiriladigan // "
     "va rivojlanadigan** qilamiz. // ANDTI Talent Hub: **iqtidoringizni kashf qiling!** // E'tiboringiz "
     "uchun rahmat, savollaringizga tayyormiz.",
     "Oxirgi gapni yoddan, hakamlarning ko'ziga qarab ayting. Keyin jilmayib, 2 soniya kuting.", False),
]

SHORT = (
    "Assalomu alaykum! Men Abdujalil Chirmashev, ANDTI Talent Hub loyihasi rahbariman. // Rektorimiz aytgan "
    "muammo: iqtidorli talabalar bilan ishlash tartibsiz, ro'yxatlar tarqoq, mentor yo'q, imkoniyatlar "
    "kerakli talabaga yetmaydi. // Biz to'liq zanjirni bitta platformaga yig'dik: **aniqlash, mentor, reja, "
    "natija.** Diagnostika talabaning yo'nalishini aniqlaydi, reyestr o'zi to'ladi, mentor muddatli reja "
    "qo'yadi, rektorat bitta tugmada hisobot oladi. Talabani ball, 5 daraja, 14 nishon, sovg'alarga "
    "aylanadigan tangalar va OTMlararo liga ushlab turadi. // Platforma tayyor: 15 modul, 226 avtomatik "
    "test. Biznes model B2B SaaS, Standart tarif oyiga 1,5 million so'm. // Bizga 6 oylik pilot uchun "
    "13,2 million so'm va rasmiy pilotga ruxsat kerak. **Har bir iqtidor ko'rinadi, yo'naltiriladi va "
    "rivojlanadi.** Rahmat!"
)

QA = [
    ("Real foydalanuvchilar bormi?",
     "Mahsulot tayyor va sinovdan o'tgan. Rasmiy pilotga ruxsat so'rayapmiz: inkubatorga aynan shuning "
     "uchun keldik. [Mini-pilot raqamlari bo'lsa, shu yerda ayting.]"),
    ("Bu ANDTIning ichki tizimi emasmi?",
     "Yo'q, bu SaaS: har bir oliygoh o'z subdomenida ishlaydi, ma'lumotlari boshqalardan to'liq alohida. "
     "Ikkinchi OTM namunasini hozir ko'rsata olamiz."),
    ("HEMIS bor-ku, nega bu kerak?",
     "HEMIS baholar va hujjatlar tizimi. Biz iqtidorni topish va rivojlantirish tizimimiz. Biz HEMISni "
     "to'ldiramiz, keyin integratsiya qilib, talabalarni bir tugmada import qilamiz."),
    ("Nega OTM pul to'laydi?",
     "Standart tarif bitta xodim maoshidan arzon, lekin vazirlikka hisobotni daqiqalarga qisqartiradi va "
     "iqtidorli talabalar natijasini, ya'ni OTM reytingini oshiradi."),
    ("Narxlar qayerdan olingan?",
     "Bu gipoteza: bitta xodim maoshidan arzon. Pilot davomida oliygohlar bilan aniqlashtiramiz."),
    ("Homiylar nega qo'shiladi?",
     "Kompaniya sovg'a evaziga iqtidorli talabalarga to'g'ridan-to'g'ri yetib boradi: bu arzon va aniq "
     "kadr qidirish kanali."),
    ("Ballarni suiiste'mol qilishsa-chi?",
     "Kunlik 1 000 XP chegarasi bor, qo'lda berilgan har bir ball o'zgartirib bo'lmaydigan jurnalga yoziladi."),
    ("Diagnostika noto'g'ri yo'nalish bersa?",
     "Test qayta topshiriladi, yo'nalishni mentor yoki rahbariyat o'zgartira oladi. Tizim tavsiya beradi, "
     "qarorni odam qabul qiladi."),
    ("O'qituvchilar bunga vaqt topadimi?",
     "Ko'p ish avtomatik: reyestr o'zi to'ladi, eslatmalar o'zi ketadi, AI baho qoralamasini tayyorlaydi. "
     "O'qituvchi faqat qaror qabul qiladi."),
    ("Ma'lumotlar xavfsizmi?",
     "6 xil rol va huquqlar, har bir OTM ma'lumoti alohida, parollar shifrlangan, xesh-zanjirli audit "
     "jurnali. Serverni O'zbekistonda joylashtiramiz."),
    ("Kim dasturlagan, qancha vaqtda?",
     "Jamoamiz, zamonaviy AI vositalari yordamida: shuning uchun MVP tez va arzon tayyor bo'ldi. "
     "Arxitekturani o'zimiz to'liq boshqaramiz."),
    ("Pul nimaga sarflanadi?",
     "Server va AI xizmati, ochilish xakatoni sovg'a fondi, pilot marketingi va yuridik rasmiylashtirish. "
     "Jamoa maoshi kiritilmagan."),
]

NUMBERS = [
    ("15", "modul"), ("6", "rol"), ("226", "avtomatik test"), ("5", "daraja"),
    ("14", "nishon"), ("10 / 3", "savol / daqiqa"), ("6", "iqtidor yo'nalishi"), ("70 / 30", "javob / real ish, %"),
    ("1,5 mln", "Standart, so'm/oy"), ("3,5 mln", "Premium, so'm/oy"), ("≈80%", "yalpi marja"), ("13,2 mln", "pilot grant, so'm"),
]

TIPS = [
    "Birinchi va oxirgi gapni **yod oling**, qolganini tayanch so'zlar bilan gapiring.",
    "Hakamlarga qarang, ekranga faqat ko'rsatish uchun qarang.",
    "Raqamlarni aytganda **to'xtab oling**: «226 ta // avtomatik test».",
    "Bilmagan savolga: «Yaxshi savol, buni pilotda aniqlaymiz.» To'qib chiqarmang.",
    "Vaqt 5 daqiqa bo'lsa, **«qisqartirsa bo'ladi»** belgisi bor bloklarni bir gapga qisqartiring.",
    "Kamida 3 marta vaqt o'lchab mashq qiling, bir marta jamoadoshlar oldida.",
]

CHECK = [
    "Video noutbukda internetsiz ochiladi (diktorli va musiqali versiya)",
    "Taqdimot ochilgan, slaydlar to'liq ekran rejimida",
    "Demo hisoblar ochiq: demo_rector, demo_student2",
    "Natijalar sahifasi va QR kod telefonda tekshirilgan",
    "Kvadrat qavsdagi joylar (jamoa ismlari) to'ldirilgan",
    "Zaxira: skrinshotlar va PDF hisobot fleshkada",
]


def uz(text):
    """Apostrofni o'zbek imlosiga o'giradi: oʻ, gʻ (U+02BB), qolganlari tutuq belgisi ʼ (U+02BC)."""
    text = re.sub(r"([oOgG])'", "\\1\u02bb", text)
    return text.replace("'", "\u02bc")


def rich(text):
    out = html.escape(uz(text), quote=False)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    return out.replace(" // ", ' <span class="pause">‖</span> ').replace("// ", '<span class="pause">‖</span> ')


def t(text):
    return html.escape(uz(text), quote=False)


def footer(n):
    return (f'<footer><span>ANDTI Talent Hub · Pitch nutqi</span><span>{n}</span></footer>')


def cover():
    nums = "".join(
        f'<div class="cn"><b>{a}</b><span>{t(b)}</span></div>'
        for a, b in [("23", "slayd"), ("6:30", "daqiqa"), ("12", "savolga javob")]
    )
    return f"""
<section class="page cover">
  <div class="glow"></div>
  <div class="ring"></div>
  <p class="eyebrow">{t("«Mening startap loyiham» · ANDTI Startaplar klubi")}</p>
  <div class="cover-main">
    <p class="kicker">Pitch nutqi</p>
    <h1>ANDTI<br>Talent Hub</h1>
    <p class="sub">{t("Iqtidorli talabalarni aniqlash, rivojlantirish va to'g'ri yo'naltirishning SaaS platformasi")}</p>
    <div class="chain">
      <span>Aniqlash</span><i></i><span>Mentor</span><i></i><span>Reja</span><i></i><span>Natija</span>
    </div>
  </div>
  <div class="cover-nums">{nums}</div>
  <div class="cover-foot">
    <div><small>Loyiha rahbari</small><b>Abdujalil Chirmashev</b></div>
    <div class="r"><small>Taqdimot kuni</small><b>15 oktabr 2026</b></div>
  </div>
</section>"""


def overview(n):
    total = 390
    def sec(s):
        m, x = s.split(":")
        return int(m) * 60 + int(x)
    bars = ""
    for i, (num, name, a, b) in enumerate(ACTS):
        w = (sec(b) - sec(a)) / total * 100
        bars += (f'<div class="seg s{i}" style="width:{w:.2f}%"><b>{num}</b><span>{t(name)}</span>'
                 f'<em>{a}–{b}</em></div>')
    acts = ""
    for num, name, a, b in ACTS:
        slides = [blk for blk in BLOCKS if blk[0] == num]
        items = "".join(f"<li><b>{s[1]:02d}</b>{t(s[2])}</li>" for s in slides)
        acts += f'<div class="act"><h3><span>{num}</span>{t(name)}</h3><ul>{items}</ul></div>'
    return f"""
<section class="page">
  <p class="label">Nutq xaritasi</p>
  <h2>{t("6,5 daqiqa, 5 qism, 23 slayd")}</h2>
  <p class="lead">{t("Nutq taqdimot slaydlariga bir-bir mos keladi. Har bir blokda slayd raqami, vaqt, aytiladigan matn va sahna ko'rsatmasi bor.")}</p>
  <div class="timeline">{bars}</div>
  <div class="acts">{acts}</div>
  <div class="legend">
    <h3>{t("Belgilar")}</h3>
    <div class="lg"><strong>Qalin matn</strong><span>{t("ovozda urg'u bering")}</span></div>
    <div class="lg"><span class="pause big">‖</span><span>{t("qisqa pauza, 1 soniya")}</span></div>
    <div class="lg"><span class="dir-chip">Sahnada</span><span>{t("o'zingiz uchun ko'rsatma, ovoz chiqarib aytilmaydi")}</span></div>
    <div class="lg"><span class="cut-chip">{t("Qisqartirsa bo'ladi")}</span><span>{t("vaqt 5 daqiqa bo'lsa, bir gapga qisqartiring")}</span></div>
  </div>
  {footer(n)}
</section>"""


def block(b):
    act, num, name, time, text, direction, cut = b
    d = f'<p class="dir"><span class="dir-chip">Sahnada</span>{t(direction)}</p>' if direction else ""
    c = f'<span class="cut-chip">{t("Qisqartirsa bo'ladi")}</span>' if cut else ""
    return f"""
<article class="blk">
  <div class="meta"><span class="num">{num:02d}</span><span class="name">{t(name)}</span><span class="time">{time}</span>{c}</div>
  <div class="body"><p class="speech">{rich(text)}</p>{d}</div>
</article>"""


# Har bir sahifaga sig'adigan bloklar (slayd raqamlari bo'yicha).
PAGES = [(1, 2, 3), (4, 5, 6), (7, 8, 9), (10, 11, 12), (13, 14, 15), (16, 17, 18, 19), (20, 21), (22, 23)]


def speech_pages(start):
    out = []
    by_num = {b[1]: b for b in BLOCKS if b[1] != 19}
    by_num[19] = None
    n = start
    for group in PAGES:
        items = [by_num[g] for g in group if by_num.get(g)]
        acts = []
        for b in items:
            if b[0] not in acts:
                acts.append(b[0])
        label = " · ".join(f"{a}. {dict((x[0], x[1]) for x in ACTS)[a]}" for a in acts)
        body = "".join(block(b) for b in items)
        out.append(f"""
<section class="page">
  <p class="label">{t(label)}</p>
  {body}
  {footer(n)}
</section>""")
        n += 1
    return out, n


def short_page(n):
    return f"""
<section class="page">
  <p class="label">Zaxira variant</p>
  <h2>{t("1 daqiqalik qisqa nutq")}</h2>
  <p class="lead">{t("Vaqt juda qisqa bo'lsa, liftda yoki tanaffusda hakam bilan uchrashsangiz shu matnni ayting.")}</p>
  <div class="short"><p class="speech">{rich(SHORT)}</p></div>
  <h2 class="mt">{t("Yodda turadigan raqamlar")}</h2>
  <div class="nums">{"".join(f'<div class="nb"><b>{t(a)}</b><span>{t(b)}</span></div>' for a, b in NUMBERS)}</div>
  {footer(n)}
</section>"""


def qa_page(n):
    cards = "".join(f'<div class="qa"><h4>{t(q)}</h4><p>{t(a)}</p></div>' for q, a in QA)
    return f"""
<section class="page">
  <p class="label">Savol-javob</p>
  <h2>{t("Hakamlar savollariga tayyor javoblar")}</h2>
  <div class="qas">{cards}</div>
  {footer(n)}
</section>"""


def tips_page(n):
    tips = "".join(f'<li><span>{i}</span><p>{rich(x)}</p></li>' for i, x in enumerate(TIPS, 1))
    check = "".join(f"<li><i></i>{t(x)}</li>" for x in CHECK)
    return f"""
<section class="page">
  <p class="label">Sahnaga tayyorgarlik</p>
  <h2>{t("Sahnada o'zini tutish")}</h2>
  <ol class="tips">{tips}</ol>
  <h2 class="mt">{t("Sahnaga chiqishdan oldin")}</h2>
  <ul class="check">{check}</ul>
  <div class="final">
    <p>{t("Har bir talabada iqtidor bor. Biz uni ko'rinadigan, yo'naltiriladigan va rivojlanadigan qilamiz.")}</p>
    <b>{t("Omad, Abdujalil!")}</b>
  </div>
  {footer(n)}
</section>"""


def main():
    pages = [cover(), overview(2)]
    sp, n = speech_pages(3)
    pages += sp
    pages += [short_page(n), qa_page(n + 1), tips_page(n + 2)]
    css = (HERE / "style.css").read_text(encoding="utf-8")
    doc = (f'<!doctype html><html lang="uz"><head><meta charset="utf-8"><title>ANDTI Talent Hub · Pitch nutqi'
           f"</title><style>{css}</style></head><body>{''.join(pages)}</body></html>")
    (HERE / "nutq.html").write_text(doc, encoding="utf-8")


if __name__ == "__main__":
    main()

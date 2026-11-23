"""Alan sabitleri: Ankara ilçeleri, satış aşamaları, roller vb."""
from __future__ import annotations

ANKARA_DISTRICTS = [
    "Akyurt", "Altındağ", "Ayaş", "Bala", "Beypazarı", "Çamlıdere", "Çankaya", "Çubuk",
    "Elmadağ", "Etimesgut", "Evren", "Gölbaşı", "Güdül", "Haymana", "Kahramankazan",
    "Kalecik", "Keçiören", "Kızılcahamam", "Mamak", "Nallıhan", "Polatlı", "Pursaklar",
    "Sincan", "Şereflikoçhisar", "Yenimahalle",
]
assert len(ANKARA_DISTRICTS) == 25

# Adres metinlerinde görülen alternatif yazımlar
DISTRICT_ALIASES = {
    "kazan": "Kahramankazan",
    "serefli kochisar": "Şereflikoçhisar",
    "seref likochisar": "Şereflikoçhisar",
}

# Satış aşamaları (sıra önemli)
STAGES = [
    ("yeni", "Yeni tespit edildi"),
    ("arastiriliyor", "Araştırılıyor"),
    ("iletisime_hazir", "İletişime hazır"),
    ("ilk_gorusme", "İlk görüşme yapıldı"),
    ("ilgileniyor", "İlgileniyor"),
    ("teklif_gonderildi", "Teklif gönderildi"),
    ("kazanildi", "Müşteri kazanıldı"),
    ("olumsuz", "Olumsuz sonuçlandı"),
]
STAGE_KEYS = [s[0] for s in STAGES]
STAGE_LABELS = dict(STAGES)
CLOSED_STAGES = {"kazanildi", "olumsuz"}

SERVICE_LINES = {"isg": "İş Sağlığı ve Güvenliği", "yazilim": "Yazılım ve Dijital Çözümler"}

ROLES = ["admin", "manager", "sales", "viewer"]
ROLE_LABELS = {"admin": "Yönetici", "manager": "Satış Müdürü", "sales": "Satış Temsilcisi", "viewer": "Görüntüleyici"}

COMPANY_TYPES = {
    "AS": "Anonim Şirket",
    "LTD": "Limited Şirket",
    "KOLL": "Kollektif Şirket",
    "KOM": "Komandit Şirket",
    "KOOP": "Kooperatif",
    "SAHIS": "Gerçek Kişi Ticari İşletmesi",
    "DIGER": "Diğer",
}

CONTACT_TYPES = {"phone": "Telefon", "email": "E-posta", "website": "Web sitesi", "map_profile": "Harita/Firma profili"}

ACTIVITY_TYPES = {"call": "Telefon görüşmesi", "meeting": "Toplantı", "email": "E-posta", "note": "Not", "visit": "Ziyaret"}

# İYS (İleti Yönetim Sistemi) / iletişim izin durumları
IYS_STATUSES = {
    "bilinmiyor": "Kontrol edilmedi",
    "engel_yok": "Kontrol edildi – ret kaydı yok",
    "ret": "Ret / itiraz kaydı var",
}

HIGH_SCORE_THRESHOLD = 60

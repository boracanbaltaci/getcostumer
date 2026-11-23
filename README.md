# Ankara Business Radar

Ankara'nın 25 ilçesinde yeni kurulan işletmeleri **yetkili veri kaynaklarından** tespit eden, kamuya açık
kurumsal iletişim bilgilerini araştıran, İSG ve yazılım hizmetleri açısından **açıklanabilir** fırsat puanı
veren ve satış sürecini yöneten web uygulaması.

> Önce okuyun: [docs/VERI_KAYNAKLARI_RAPORU.md](docs/VERI_KAYNAKLARI_RAPORU.md). Otomatik ve hukuka uygun günlük
> tespit için TOBB **TTSG Veri Aboneliği** (web servis) veya günlük elektronik gazete satın alımı gerekir.
> Bunlar olmadan sistem çalışır, ancak yeni kayıtlar yalnızca manuel içe aktarma ile gelir ve taranmamış
> günler panelde açıkça "taranmadı" olarak gösterilir.

## Mimari

| Katman | Teknoloji |
|---|---|
| Arayüz | Next.js 14 (App Router), TypeScript, Tailwind CSS – Türkçe, mobil uyumlu |
| API | Python 3.12, FastAPI, SQLAlchemy 2, Pydantic 2, JWT + rol tabanlı yetki |
| Veritabanı | PostgreSQL 16 (Alembic migration) |
| Arka plan | Celery + Redis; Celery Beat ile günlük 08:30 (Europe/Istanbul) |
| Yapay zekâ | Değiştirilebilir sağlayıcı (varsayılan kapalı; `LLM_PROVIDER=anthropic`) |
| Dağıtım | Docker Compose |

```
backend/
  app/
    api/            REST uç noktaları (auth, businesses, crm, data)
    services/
      sources/      Veri kaynağı tanımları ve adaptörler (TTSG WS, klasör, lisanslı akış)
      importers/    CSV/Excel/PDF içe aktarma
      enrichment/   Web sitesi doğrulama, OSM, Google Places, arama API'si
      scoring/      Sektör/tehlike sınıfı, İSG & yazılım puanı, LLM katmanı
      ttsg_parser   İlan sınıflandırma (yalnızca yeni kuruluş) ve alan ayrıştırma
      ingestion     Ortak kayıt işleme, idempotent, mükerrer kontrolü
      pipeline      Günlük otomasyon akışı
      retention     KVKK saklama / anonimleştirme
    worker/         Celery uygulaması ve görevler
  alembic/          Veritabanı migration'ları
  tests/            Otomatik testler (32 test)
frontend/src/app/   Sayfalar (panel, işletmeler, detay, içe aktar, kaynaklar, görevler, raporlar…)
data/inbox/         Satın alınan günlük gazete PDF / fihrist Excel dosyalarının bırakılacağı klasör
```

## Kurulum (Docker Compose)

Gereksinim: Docker Desktop veya Docker Engine + Compose v2.

```bash
cp .env.example .env
# .env içinde en azından şunları doldurun:
#   SECRET_KEY            -> python3 -c "import secrets; print(secrets.token_urlsafe(64))"
#   POSTGRES_PASSWORD
#   FIRST_ADMIN_EMAIL / FIRST_ADMIN_PASSWORD (en az 10 karakter, harf+rakam)
docker compose up -d --build
```

- Arayüz: http://localhost:3000 – `FIRST_ADMIN_EMAIL` ile giriş yapın, ardından **Hesabım** sayfasından parolayı değiştirin.
- API dokümantasyonu: http://localhost:8000/api/docs
- Migration'lar backend açılışında otomatik çalışır (`alembic upgrade head`).
- Linux sunucuda `./data` klasörü konteyner içindeki 1000 numaralı kullanıcıya yazılabilir olmalıdır: `sudo chown -R 1000:1000 data`.
- `ENVIRONMENT=production` iken `SECRET_KEY` değiştirilmemişse backend bilerek başlamaz.

Yönetici hesabını komutla oluşturmak / sıfırlamak:

```bash
docker compose exec backend python -m app.cli create-admin --email admin@firmaniz.com.tr --name "Ad Soyad"
```

## Geliştirme ortamı (Docker olmadan)

```bash
# Backend (Python 3.12)
cd backend
python3.12 -m venv ../.venv && ../.venv/bin/pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+psycopg://radar:radar@localhost:5432/radar REDIS_URL=redis://localhost:6379/0 \
       INBOX_DIR=../data/inbox UPLOAD_DIR=../data/uploads
../.venv/bin/alembic upgrade head
../.venv/bin/python -m app.cli create-admin --email admin@ornek.local
../.venv/bin/uvicorn app.main:app --reload --port 8000
# İsteğe bağlı (zamanlanmış görevler):
../.venv/bin/celery -A app.worker.celery_app worker -l INFO
../.venv/bin/celery -A app.worker.celery_app beat -l INFO

# Frontend
cd ../frontend && npm install && BACKEND_URL=http://localhost:8000 npm run dev
```

Redis yoksa arayüzden tetiklenen görevler API süreci içinde iş parçacığında çalışır; zamanlanmış 08:30
taraması için Celery Beat gerekir (veya cron ile `python -m app.cli run-daily`).

## Testler

```bash
cd backend
../.venv/bin/python -m pytest -q                       # SQLite ile
TEST_DATABASE_URL=postgresql+psycopg://... ../.venv/bin/python -m pytest -q   # PostgreSQL ile
cd ../frontend && npx tsc --noEmit && npm run build
```

Testler: ilan sınıflandırma (kuruluş / şube / değişiklik / sermaye artırımı), alan ayrıştırma, ilçe tespiti,
mükerrer kontrolü ve birleştirme, CSV/Excel içe aktarma, KVKK (mobil/ücretsiz e-posta saklamama), web sitesi
doğrulama ve yanlış eşleşmenin reddi, puanlama ve LLM düzeltme sınırı, günlük akışta başarısız günün "taranamadı"
olarak işaretlenmesi, tekrar çalıştırmada veri bütünlüğü, eşzamanlı çalışma kilidi, API yetkilendirme, CRM/teklif
akışı ve Excel/PDF dışa aktarma. Test verileri tamamen kurgusaldır ("KURGU …").

## Kullanım

### 1. Veri kaynaklarını etkinleştirme
**Veri Kaynakları** sayfası her kaynağın erişim türünü, hukuki dayanağını, son başarılı taramasını ve hata
durumunu gösterir. Kimlik doğrulamalı kaynaklar (MERSİS, TTSG ilan görüntüleme) etkinleştirilemez.

- **TTSG Web Servis (abonelik):** `.env` içinde `TTSG_WS_ENABLED=true`, `TTSG_WS_BASE_URL`, kimlik bilgileri ve
  teknik dokümana göre `TTSG_WS_FIELD_MAP` girilir → Veri Kaynakları'nda **Etkinleştir**. İlk çalıştırmada son
  30 gün (`INITIAL_BACKFILL_DAYS`) taranır, sonra her gün kaldığı yerden devam eder. Hata alınan günler bir
  sonraki çalıştırmada tekrar denenir.
- **Günlük elektronik gazete (klasör):** TOBB'dan gelen PDF ve fihrist Excel dosyalarını `data/inbox/` klasörüne
  bırakın. 08:30 taramasında ve gün içinde saatlik kontrolde içe aktarılır; işlenenler `data/inbox/islenen/`,
  hatalılar `data/inbox/hatali/` klasörüne taşınır.
- **Lisanslı sağlayıcı:** `LICENSED_FEED_*` değişkenleri.

### 2. Manuel içe aktarma
**İçe Aktar** → dosya seç → **Önizle** (eşlenen sütunları görün) → **İçe aktar**. Şablon Excel indirilebilir.
Tanınan sütunlar: Ticaret Unvanı, Kuruluş Tarihi, Ticaret Sicil Müdürlüğü / TSM, Sicil No / TSM No, MERSİS No,
İlçe, Adres, Faaliyet Konusu / Amaç ve Konu, NACE Kodu, Şirket Türü, Sermaye, **İlan Türü**, Gazete Tarihi /
Sayısı / Baş Sayfa, İlan Linki, Kurumsal Telefon / E-posta / Web Sitesi.
"İlan Türü" sütunu varsa şube açılışı, adres/unvan değişikliği, sermaye artırımı, nakil vb. otomatik ayıklanır.
Aynı dosya ikinci kez yüklenmez; aynı ilan tekrar işlenmez.

### 3. İnceleme kuyruğu
Kuruluş ilanı olduğu ya da Ankara'ya ait olduğu doğrulanamayan kayıtlar buraya düşer. Kaynak metni okuyup
alanları düzelterek **onaylayın** veya **reddedin**. Onaylanan kayıt "manuel doğrulandı" olarak işaretlenir.

### 4. İşletmeler ve detay ekranı
Filtreler: ilçe, kuruluş tarihi, sektör, şirket türü, İSG / yazılım puanı, iletişim bilgisi, görüşme durumu,
hizmet hattı ve aşama, öncelik, tespit tarihi. Liste Excel / CSV / PDF olarak dışa aktarılabilir.
Detay ekranında: kaynak ve doğrulama bilgileri, ham ilan kaydı, iletişim bilgileri (kaynak bağlantısı + güven
puanı + doğrula / yanlış eşleşme), fırsat analizi (her faktör **doğrulanmış/tahmini** etiketli), İSG ve
yazılım fırsatları için ayrı satış aşaması, teklif oluşturma (PDF), görüşme notları ve takip tarihleri,
İYS / "iletişime geçme" / KVKK anonimleştirme.

### 5. Puanlama nasıl çalışır?
- Sektör: doğrulanmış NACE → resmî kaynak; yoksa unvan ve faaliyet metninden anahtar kelime (tahmini).
- Tehlike sınıfı: **İçe Aktar → İşyeri tehlike sınıfları listesi** ile resmî Tebliğ eki yüklenirse kesin;
  yüklenmezse NACE bölümüne göre tahmini.
- İSG puanı: tehlike sınıfı, sektör riski, şirket türü, sermaye, sanayi bölgesi adresi, yenilik, ulaşılabilirlik.
- Yazılım puanı: web sitesi bulunamadı, e-ticaret / randevu / CRM / otomasyon uygunluğu, ölçek, dijital ifadeler.
- Toplam = 0,65 × yüksek puan + 0,35 × düşük puan; öncelik A (≥70) / B (≥50) / C.
- LLM etkinse özet, görüşme notları ve en fazla ±10 puanlık "tahmini" düzeltme ekler; doğrulanmış veriyi değiştirmez.

### 6. Günlük otomasyon
08:30'da: kaynakları kontrol → yeni Ankara kuruluşlarını içe al → mükerrerleri ayıkla → iletişim araştır →
analiz → günlük özet → (yapılandırıldıysa) e-posta/Telegram ile **ekip içi** bildirim. 08:45'te takip
hatırlatmaları, her pazar 03:15'te KVKK saklama politikası çalışır. **Zamanlanmış Görevler** sayfasından
görevler elle tetiklenebilir ve günlükleri görülebilir.

### 7. Roller
| Rol | Yetki |
|---|---|
| Görüntüleyici | Okuma |
| Satış temsilcisi | İçe aktarma, inceleme, iletişim/görüşme/teklif, dışa aktarma |
| Satış müdürü | + birleştirme, görev tetikleme, KVKK anonimleştirme, tehlike listesi yükleme |
| Yönetici | + kullanıcı ve kaynak yönetimi, denetim kaydı, saklama politikası |

## Güvenlik notları
- Parolalar PBKDF2-SHA256 (390.000 tur) ile saklanır; JWT oturum süresi `ACCESS_TOKEN_EXPIRE_MINUTES`.
- Tüm gizli bilgiler ortam değişkenlerindedir; `.env` sürüm kontrolüne eklenmez.
- Görüntüleme, dışa aktarma, birleştirme ve silme işlemleri denetim kaydına yazılır.
- Üretimde arayüzü HTTPS arkasında (ör. Caddy/Nginx) yayınlayın; 8000 portu yalnızca localhost'a açıktır.

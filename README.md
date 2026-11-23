# İşletme Radarı

Haritadan seçilen konumun çevresinde, Google'da kayıtlı olup **web sitesi olmayan**
veya **eski görünümlü web sitesi** olan işletmeleri bulan tek ekranlı uygulama.

## Ne yapar?

1. Haritada bir noktaya tıklarsınız (işareti sürükleyerek de taşıyabilirsiniz).
2. Yarıçap seçip **Tara**'ya basarsınız.
3. Backend, Google Places API (New) ile çevredeki işletmeleri tarar; sitesi olanların
   ana sayfasını indirip "eski görünümlü mü?" analizini yapar (HTTPS yokluğu, mobil
   uyum etiketi yokluğu, eski doctype, terk edilmiş etiketler, Flash, eski CMS…).
4. Sonuçlar tabloda listelenir: **Firma Adı | Konum | Telefon | Web Sitesi | Aksiyon**.
   - `Site yok` — Google kaydında web sitesi yok
   - `Eski görünümlü` — site var ama teknik olarak eski
   - `Ulaşılamadı` — site açılmıyor / park sayfası
5. Aksiyon sütunundaki **e-posta** ve **SMS** ikonları taslak mesaj modal'ı açar
   (gönderim henüz bağlı değildir; metin yazıp Gönder demek modal'ı kapatır).
   Modal'ın üstündeki açılır listeden **Hızlı Mesajlar** ekranında kayıtlı
   şablonlar seçilip metni doldurur.

Her başarılı tarama sonucuyla birlikte veritabanına (Docker'da **PostgreSQL**,
yerelde **SQLite** `data/scans.db`) kaydedilir;
"Önceki Taramalar" ekranından geri açılabilir. **Kalp** ikonu iki yerde vardır:
tarama satırında taramayı, işletme tablosu satırlarında işletmeyi favoriler.
**Favoriler** ekranı iki bölümdür: "Favori İşletmeler" tablosu + "Favori Taramalar"
listesi.

## Giriş & kullanıcılar

Uygulama giriş ister. İlk açılışta hiç kullanıcı yoksa **admin / admin** hesabı
otomatik oluşur (kullanıcı adı + şifre yeterlidir). Oturum, HttpOnly cookie ile
taşınan bir oturum token'ıdır (`SESSION_TTL_DAYS` gün geçerli).

- Taramalar ve favoriler **kullanıcıya bağlıdır** — kullanıcılar birbirlerinin
  kayıtlarını göremez.
- Parolalar PBKDF2-HMAC-SHA256 ile hash'lenerek veritabanında tutulur;
  yeni kullanıcı eklemek için `users` tablosuna `services/auth.py`'deki
  `hash_password` ile satır eklenebilir.

## Teknoloji

- **Backend:** Python + FastAPI — `backend/app/` (`services/places.py` Google istemcisi,
  `services/sitescan.py` site analizi, `services/store.py` tarama/favori/kullanıcı
  kayıtları, `services/auth.py` giriş + oturum)
- **Frontend:** Next.js + TypeScript + Tailwind + Leaflet (react-leaflet) — `frontend/src/`,
  ekranlar: Giriş, Tarama, Önceki Taramalar, Favoriler, Hızlı Mesajlar
- **Harita:** Leaflet + OpenStreetMap (anahtarsız)
- **Veri:** Google Places API (New) — anahtar gerekli
- **Depolama:** PostgreSQL (Docker'da `db` servisi, `pgdata` volume) — tarama
  geçmişi, kullanıcılar, oturumlar, favoriler, hızlı mesajlar. `DATABASE_URL`
  boşsa yerelde SQLite'a (`data/scans.db`) düşer; ek kurulum gerekmez. İlk
  açılışta boş Postgres'e eski SQLite verisi otomatik taşınır.

## Kurulum (yerel)

```bash
# 1) Backend
cd backend
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 2) Frontend (ayrı terminal)
cd frontend
npm install
npm run dev        # http://localhost:3000
```

Frontend `/api/*` isteklerini `next.config.js`'deki rewrite ile backend'e proxy'ler
(varsayılan `http://localhost:8000`, `BACKEND_URL` ile değişir).

## Docker ile

```bash
docker compose up -d --build   # frontend + backend tek komutla
```

Arayüz: `http://localhost:${WEB_PORT:-3000}` (çakışırsa `.env`'de `WEB_PORT`
değiştir). Backend host portu açmaz — frontend, `/api/*` isteklerini compose
ağı içinden `backend:8000`'e proxy'ler. Veritabanı Postgres'tir (`db` servisi,
`pgdata` volume); `./data`'daki eski SQLite dosyası ilk açılışta boş Postgres'e
aktarılır.

Durdurmak: `docker compose down`.

## Google API anahtarı alma (adım adım)

Tarama için Google **Places API (New)** anahtarı gerekir. Ücretsiz kota kredisi
vardır (aylık belirli sayıda çağrı ücretsizdir; yine de faturalandırma hesabı açılmalıdır):

1. https://console.cloud.google.com/ adresine Google hesabınla gir.
2. Üstteki proje seçiciden **"Yeni proje"** oluştur (ör. `isletme-radari`).
3. Sol menü → **API'ler ve Hizmetler → Kitaplık** → `Places API (New)` ara → **Etkinleştir**.
   (Eski `Places API` değil — `(New)` olan.)
4. **Faturalandırma** menüsünden projeye bir faturalandırma hesabı bağla
   (kart gerekir; kullanılmadıkça ücret çıkmaz, ücretsiz kota aşılınca ücretlendirir).
5. **API'ler ve Hizmetler → Kimlik Bilgileri → + Kimlik bilgisi oluştur → API anahtarı**.
6. Oluşan anahtarı **kısıtla** (önerilir): "API kısıtlaması" → yalnızca
   **Places API (New)** seç. Anahtar sadece sunucuda (backend) kullanılır, tarayıcıya verilmez.
7. Anahtarı `.env` dosyasına yaz:

   ```
   GOOGLE_PLACES_API_KEY=AIza...senin_anahtarin
   ```

8. Backend'i yeniden başlat; arayüzdeki uyarı bandı kaybolur.

> Maliyet: tek taramada en fazla `PLACES_MAX_CALLS` (vars. 9) Places çağrısı yapılır.
> Site analizi Google dışıdır (işletmenin kendi sitesine HTTP isteği).

## Yapılandırma (.env)

Bkz. `.env.example`. Önemlileri:

| Değişken | Açıklama |
|---|---|
| `GOOGLE_PLACES_API_KEY` | Places API (New) anahtarı — zorunlu (tarama için) |
| `PLACES_MAX_CALLS` | Tarama başına Places çağrı üst sınırı (vars. 9) |
| `WEBSITE_CHECK_LIMIT` | Site analizi yapılacak en fazla işletme (vars. 60) |
| `CORS_ORIGINS` | Backend'e doğrudan erişecek kökenler |
| `DATABASE_URL` | Postgres bağlantı dizesi (boş = SQLite; Docker'da compose ayarlar) |
| `POSTGRES_PASSWORD` | Docker `db` servisi parolası (vars. radar) |
| `DB_PATH` | Geçmiş SQLite dosyası (vars. `data/scans.db`) |
| `SESSION_TTL_DAYS` | Oturum geçerliliği, gün (vars. 30) |
| `WEB_PORT` | Docker'da frontend portu (vars. 3000) |

## Testler

```bash
cd backend
pytest tests/ -q      # site-analiz + auth/izolasyon/favori testleri (ağ çağrısı yok)

cd frontend
npm run typecheck     # TypeScript denetimi
npm run build         # üretim derlemesi
```

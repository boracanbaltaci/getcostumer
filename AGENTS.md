# İşletme Radarı — Ajan Anayasası

Bu dosya projenin kural kitabı ve yönlendirme dizinidir; her görev öncesi okunur.
Detay kurallar bağlantılı dokümanlarda yaşar — bu dosya onların içeriğini tekrarlamaz.

Dokümantasyon dili: kök anayasa ve `README.md` Türkçe; `docs/` altındaki teknik
dokümanlar İngilizce. **Kullanıcıyla tüm iletişim Türkçe'dir.**

## Teknik özet

- **Backend:** Python, FastAPI, Pydantic 2 — `backend/app/`
  - `main.py` — HTTP katmanı: `GET /api/health`, `GET /api/config`, `POST /api/scan`,
    `GET/DELETE /api/scans[/{id}]`, `POST /api/auth/login`, `POST /api/auth/logout`,
    `GET /api/auth/me`, `GET/PUT/DELETE /api/favorites[/{scan_id}]` (tarama favorileri),
    `GET/PUT/DELETE /api/business-favorites[/{place_id}]` (işletme favorileri),
    `GET/POST/DELETE /api/quick-messages[/{id}]` (hızlı mesaj şablonları)
  - `services/places.py` — Google Places API (New) Nearby Search istemcisi (`FIELD_MASK` sabit)
  - `services/sitescan.py` — web sitesi "eski görünümlü mü?" sezgisel analizi
  - `services/scoring.py` — yazılım/dijital fırsat puanı (kural tabanlı; site
    durumu + `primaryType` sektör uygunluğu + isim sinyalleri → 0-100, A/B/C)
  - `services/store.py` — tarama geçmişi + kullanıcılar/oturumlar/favoriler
    (Postgres `DATABASE_URL` veya SQLite fallback; şema `_SCHEMA` + eklemeli ALTER)
  - `services/auth.py` — pbkdf2 parola doğrulama, oturum cookie, `get_current_user`
- **Frontend:** Next.js (App Router), TypeScript, Tailwind, Leaflet (react-leaflet) —
  `frontend/src/`; tek sayfa `app/page.tsx`, bileşenler `components/` (giriş ekranı
  dahil); tüm backend erişimi `src/lib/api.ts` üzerinden.
- **Veritabanı:** `DATABASE_URL` doluysa PostgreSQL (Docker `db` servisi,
  `pgdata` volume), boşsa SQLite (`data/scans.db` — yerel dev + testler);
  `*.db` gitignore'da. Postgres boşken `data/scans.db` ilk açılışta aktarılır.
- Frontend `/api/*` isteklerini `next.config.js` rewrite'ı ile backend'e proxy'ler.

## Oturum başlangıcı

1. Bu dosya.
2. `docs/SESSION_CONTEXT.md` — son oturumda ne değişti, hangi kanıt üretildi,
   açık iş ne var.
3. Görev yönlendirme tablosunda görev tipine düşen dokümanlar — en fazla 3 adet;
   daha fazlası gerekiyorsa görev bölünür.
4. Sahiplik belirsizse dosyaya dokunma; sor.

## Temel ilkeler

- **Önce oku, sonra yaz.** Hedef dosyayı düzenlemeden önce oku.
- **Varsayma, doğrula.** Sınıf/metot/alan codebase'de var mı bak; yoksa yazma.
- **Kararsızlık = sor.** Davranış, isim veya değer kullanıcıyla netleşmediyse tahmin etme;
  açık sorular yazmaya başlamadan çözülür.
- **Minimal değişiklik.** Görev dışı refactor yok; plan kapsamı dışına çıkma.
- **Bağlam bütçesi.** Önce ara, sonra yalnızca gereken aralığı oku; aynı sorguyu
  tekrarlama; rutin turda arama üst sınırı 15.
- **Kanıta dayalı tamamlama.** "Bitti/çalışıyor" demek için komut çıktısı şart.
- **Bilinen tuzaklara önce bak.** Hataya/debug'a girişmeden önce `docs/LESSONS.md`'yi
  kontrol et — çoğu tuzak zaten yazılı.

## Plan-gate

Önemsiz olmayan işte (çok dosyalı, çok adımlı, sistemler arası) yazmadan önce:

1. İsteği görevlere böl.
2. Planı tablo olarak sun: görev → dokunulan dosya/katman + doğrulama yolu + açık sorular.
3. Açık sorular başlamadan çözülür — "Kararsızlık = sor" burada da geçerli.
   Kullanıcı açıkça "başla"/"uygula" demeden hiçbir şey yazma. Soruların
   yanıtlanması, seçenek işaretlenmesi veya planın tartışılması onay sayılmaz;
   açık onay cümlesi gelene kadar bekle.
4. Onay sonrası gelen **yeni istek** yeni plan döngüsü başlatır; planda olmayan iş
   yapılmaz, iş ortasındaki plan-dışı bulgular yeniden onay ister.
   Kullanıcının mevcut plana revizyonu doğrudan uygulanır — isteğin kendisi onaydır.

Plan teknik işin tamamını kapsar: dosyalar ve dokundukları metot/sınıflar, test
eklemeleri, tesisat işleri (env, config, wiring) ve doküman güncellemeleri, DoD
kanıtını üreten doğrulama adımları — tekrarlı boilerplate tek bir checklist
satırına toplanabilir. Planlar oturumda kalır; kullanıcı istemedikçe ayrı plan
dokümanı yazılmaz.

Muaf: tek dosyalık basit düzeltmeler ve sorular doğrudan ilerler; skill
çağrıları kendi iç onay kapılarını izler (çift kapı yok).

## Görev yönlendirme tablosu

Yalnızca görevin değdiği satırlar okunur:

| Görev tipi | Oku |
|---|---|
| Herhangi bir kod değişikliği | `docs/conventions/CODE_STYLE.md` |
| Oturum başlangıcı / devam | `docs/SESSION_CONTEXT.md` |
| Var olan sistemde hata düzeltme | `docs/systems/<sistem>.md` (varsa) + `docs/LESSONS.md` |
| Tasarım veya mimari karar | `README.md` + `docs/decisions/_TEMPLATE.md` ile ADR yaz |
| Veri kaynağı / dış entegrasyon | `README.md` (Google API bölümü) + `docs/LESSONS.md` |
| Eşleşme yok / sahiplik belirsiz | Dosyaya dokunma; kullanıcıya sor |

## Değişmez kurallar

1. **Katman yönü:** backend `main.py` (HTTP) → `services/` (iş mantığı) → `store`
   (SQLite/Postgres); frontend `components/` → `lib/api.ts` → `/api/*` proxy →
   backend. Üst katman alt katmana bağımlı olabilir; ters yön ve çevrim yasak.
   HTTP katmanında iş mantığı yazılmaz.
2. **Tek sorumluluk:** her servis modülü tek alan işler. Bir fonksiyon ya kaydı
   işler ya karar verir — ikisi birden olmaz.
3. **Genişletme protokolle:** yeni dış veri kaynağı `services/` altında ayrı modül
   olarak eklenir; `main.py` yalnızca uç bağlar, mevcut çağrıcı kod değişmez.
4. **Fail fast config'te, dayanıklı kayıtta:** `GOOGLE_PLACES_API_KEY` yoksa
   `/api/scan` 503 ile net mesaj döner; ancak tarama içindeki tek işletme/site
   hatası loglanıp atlanır, akış durmaz (`warnings` listesine düşer).
5. **İdempotentlik zorunlu:** tarama aynı girdiyle tekrar çalıştırılabilir; favori
   PUT/DELETE tekrarı veriyi bozmaz.
6. **Kanıt zinciri:** tarama sonucu `businesses_json` snapshot'ı olarak saklanır;
   ham kayıt sonradan değiştirilmez. Doğrulanmış ile tahmini hiçbir yerde karışmaz.
7. **Gizli bilgi ortam değişkeninde:** API anahtarı yalnızca `.env`'de durur ve
   yalnızca sunucuda kullanılır; frontend'e/koda sır yazılmaz. `.env` sürüm
   kontrolüne girmez.
8. **Doküman-kod senkronu:** bir dokümanı geçersiz kılan değişiklik aynı işte
   o dokümanı günceller.
9. **Dosya yerleşimi:** doküman `docs/` altında yazılır; editör/araç dizinine
   dosya yazılmaz.
10. **Yapısal değişiklik kapısı:** yeni üst klasör, yeni servis modülü veya
    katmanlar arası yeni bağımlılık kullanıcı onayı + aynı işte yapı dokümanı
    güncellemesi ister.
11. **Git kapısı:** onaysız commit/push/PR yok. Commit istenirse yalnızca bu
    görevin değiştirdiği dosyalar stage'lenir — ilgisiz çalışma ağacı
    değişiklikleri eklenmez.
12. **Maliyet üst sınırı:** tek taramada en fazla `PLACES_MAX_CALLS` Places
    çağrısı; site analizi `WEBSITE_CHECK_LIMIT` işletmeyle sınırlıdır.
13. **Places alan maskesi sabittir:** yeni alan gerekirse `FIELD_MASK`'e eklenir;
    gereksiz alan istenmez (Google ücretlendirmesi alan bazlıdır — kırmızı listede).
14. **Kullanıcı izolasyonu:** taramalar, favoriler ve hızlı mesajlar `user_id`'ye
    bağlıdır; her sorgu oturum sahibiyle filtrelenir. `/api/health`, `/api/config`
    ve `/api/auth/*` dışındaki uçlar `Depends(auth.get_current_user)` ister.

## Ajan kuralları

- **Ajan önerir, kapı karar verir.** Ajan çıktısı kalıcı veriye doğrudan yazılmaz;
  bir öneri kaydı olarak saklanır ya da çağıranın deterministik kapısına / insan
  onayına döner.
- **Kırmızı yollar insana aittir:** auth/oturum yönetimi, kalıcı veri şeması,
  kullanıcı kaydı ve gerçek mesaj gönderimi — ajan taslak hazırlar, insan onaylar.
- **Her ajan koşusu görünür bir iş kaydıdır:** tetiklenebilir, loglanabilir,
  aynı anda tek koşu (kilitli); operasyon ekranından izlenebilir.
- **Çıktı şemalı + tahmini etiketli:** serbest metin değil, tanımlı JSON schema;
  doğrulanmış alanı ezmez, sayısal değere ancak sınırlı düzeltme yapar.
- **Flow başına bayrak:** her akış ayrı `AGENT_<AKIŞ>_ENABLED` bayrağıyla açılır;
  sağlayıcı (`LLM_PROVIDER`) yoksa akış sessizce devre dışı — kural tabanlı çalışma
  asla ajana bağımlı olmaz.
- **Maliyet üst sınırı:** tek koşuda `AGENT_MAX_CALLS_PER_RUN` LLM çağrısı; kalan
  iş sonraki koşuya kalır.
- **Veri minimizasyonu:** prompt'a kişisel veri sokulmaz; dış servise giden içerik
  en aza indirilir.

## Kod konvansiyonları (zorunlu)

Kod yazan veya değiştiren herkes — insan ya da ajan — ilgili katmanın konvansiyon
dokümanını uygular. Dosyaya dokunmadan önce ilgili doküman okunur:

| Dokunduğun katman | Oku |
|---|---|
| Backend (FastAPI / services / store) | `docs/conventions/CODE_STYLE.md` |
| Frontend (Next.js / React / Tailwind) | `docs/conventions/CODE_STYLE.md` |
| Şema / model / veri (`schemas.py`, `store.py`) | `docs/conventions/CODE_STYLE.md` |

Konvansiyonla çelişen mevcut kod görülürse dokunulan kapsam içinde düzeltilir; kapsam
dışıysa kullanıcıya bildirilir. Konvansiyonla istek çelişirse durulur ve sorulur.

## Risk seviyeleri

| Risk | Kim onaylar | Örnek kapsam |
|---|---|---|
| Yeşil | Plan yazıldı, bekleme yok | Metin/çip kopyası, test dosyaları, log satırları, README |
| Sarı | Plan onayı | Yeni uç/servis fonksiyonu, yeni bileşen/ekran, `schemas.py` alanı, yeni filtre |
| Kırmızı | Plan onayı yetmez — insan kapatır | Auth/oturum/parola (`services/auth.py`, `users`/`sessions`); DB şeması ve kalıcı veri alanı (`store.py` `_SCHEMA`/ALTER, toplu kullanıcı verisi işlemi); ücretli Google alanları (`FIELD_MASK`, `PLACES_MAX_CALLS`, yeni Places çağrı tipi); gerçek e-posta/SMS gönderimi |

Kırmızı listedeki bir yola dokunan iş kırmızıdır; insan onayı olmadan kapanmaz.

## Test kuralları

- Davranış değişen backend biriminin testi **aynı değişiklikte** gelir
  (`backend/tests/` pytest; ağ çağrısı mock'lanır).
- Frontend'de test altyapısı yok; kanıt `npm run typecheck` + `npm run build`.
- Test çıktısında yalnızca geçti/kaldı okunur. Geçtiyse durur. Bu değişiklikten
  kaynaklanan hata sormadan düzeltilir; başka hata yalnızca özetiyle bildirilir ve
  onaylanan madde tek tek düzeltilir.
- Ajanlı yol LLM'siz de test edilir (sağlayıcı kapatılınca kural motoruna düşüş).

## Görev sonu (Definition of Done)

- `pytest tests/ -q` (backend) + `npm run typecheck` + `npm run build` (frontend)
  temiz — kanıt komut çıktısı.
- **Kullanıcının yolu tekrarlandı:** hata düzeltmesi kullanıcının deneyimlediği
  giriş noktasından, aynı başlangıç durumuyla doğrulandı — doğrudan metot çağrısı
  kullanıcıya dönük kanıt sayılmaz.
- **Çalışan imaj güncel:** kod değişikliği tamamlanınca `docker compose up -d
  --build` ile imajlar yeniden derlenir (`up` tek başına var olan imajı kullanır,
  rebuild etmez); `docker compose ps` sağlıklı + `curl` port yanıtıyla doğrulanır.
  Ortam Docker'da çalışmıyorsa adım atlanır.
- Tekrar-çalıştırma kontrolü: aynı girdi ikinci kez işlenince veri bozulmuyor.
- `docs/SESSION_CONTEXT.md` güncellendi: ne değişti, doğrulama kanıtı, açık işler.
- Tekrarlayan/tahmin edilemez tuzaklar `docs/LESSONS.md`'e damıtıldı (tek seferlik
  hata ders değildir; yinelenen kök nedenli olanlar yazılır).
- Yeni ortam değişkeni için `.env.example` + README güncellemesi aynı değişiklikte.
- Yeni tablo/sütun için `store.py` `_SCHEMA` + eklemeli `ALTER TABLE` aynı
  değişiklikte (migration framework'ü yok; kalıp için `user_id` örneğine bak).

## Yanıt stili

Kullanıcıya dönük her yanıt kısa ve özettir: önce sonuç, tek cümle gerekçe.
Ham log/araç çıktısı yapıştırılmaz; gerekiyorsa özeti verilir.

## Yükseltme (escalation)

- İki doküman veya doküman-istek çelişkisi → dur, kullanıcıya bildir; sessizce çözme.
  Kök anayasayla alt doküman çelişirse kök kazanır ve çelişki kullanıcıya yazılır.
- İstenen değişiklik değişmez kuralı bozacaksa → dur ve sor.
- Yeni kırmızı yol, yeni dış veri kaynağı veya yeni kalıcı veri alanı → önce öner,
  onaydan sonra uygula.

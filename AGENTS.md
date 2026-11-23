# İşletme Radarı — Ajan Anayasası

Bu dosya projenin kural kitabıdır; her görev öncesi okunur. Dokümantasyon İngilizce veya
Türkçe olabilir; **kullanıcıyla tüm iletişim Türkçe'dir.**

## Teknik özet

- **Backend:** Python, FastAPI, Pydantic 2 — `backend/app/`
  - `main.py` — HTTP katmanı: `GET /api/health`, `GET /api/config`, `POST /api/scan`,
    `GET/DELETE /api/scans[/{id}]`
  - `services/places.py` — Google Places API (New) Nearby Search istemcisi
  - `services/sitescan.py` — web sitesi "eski görünümlü mü?" sezgisel analizi
  - `services/store.py` — tarama geçmişi (SQLite, `data/scans.db`)
- **Frontend:** Next.js (App Router), TypeScript, Tailwind, Leaflet (react-leaflet) —
  `frontend/src/`; tek sayfa `app/page.tsx`, bileşenler `components/`
- **Veritabanı:** SQLite (`data/scans.db`) — yalnızca tarama geçmişi; `*.db` gitignore'da.
- Frontend `/api/*` isteklerini `next.config.js` rewrite'ı ile backend'e proxy'ler.

## Temel ilkeler

- **Önce oku, sonra yaz.** Hedef dosyayı düzenlemeden önce oku.
- **Varsayma, doğrula.** Sınıf/metot/alan codebase'de var mı bak; yoksa yazma.
- **Kararsızlık = sor.** Davranış, isim veya değer kullanıcıyla netleşmediyse tahmin etme.
- **Minimal değişiklik.** Görev dışı refactor yok.
- **Kanıta dayalı tamamlama.** "Bitti/çalışıyor" demek için komut çıktısı şart.

## Değişmez kurallar

1. **Katman yönü:** `main.py` (HTTP) → `services/` (iş mantığı). HTTP katmanında iş
   mantığı yazılmaz; ters yönde import yasak.
2. **Fail fast config'te, dayanıklı kayıtta:** `GOOGLE_PLACES_API_KEY` yoksa `/api/scan`
   503 ile net mesaj döner; ancak tarama içindeki tek işletme/site hatası loglanıp
   atlanır, akış durmaz (`warnings` listesine düşer).
3. **Maliyet üst sınırı:** tek taramada en fazla `PLACES_MAX_CALLS` Places çağrısı;
   site analizi `WEBSITE_CHECK_LIMIT` işletmeyle sınırlıdır.
4. **Gizli bilgi ortam değişkeninde:** API anahtarı yalnızca `.env`'de durur ve yalnızca
   sunucuda kullanılır; frontend'e/koda sır yazılmaz. `.env` sürüm kontrolüne girmez.
5. **Places alan maskesi sabittir:** yeni alan gerekirse `FIELD_MASK`'e eklenir;
   gereksiz alan istenmez (Google ücretlendirmesi alan bazlıdır).

## Görev sonu (Definition of Done)

- `backend/tests/` pytest'i geçiyor; `npm run typecheck` ve `npm run build` temiz —
  kanıt komut çıktısı.
- Yeni ortam değişkeni için `.env.example` + README güncellemesi aynı değişiklikte.

## Yükseltme (escalation)

- İstenen değişiklik değişmez kuralı bozacaksa → dur ve sor.
- Yeni dış veri kaynağı veya kalıcı veri depolama → önce öner, onaydan sonra uygula.

# Veri Kaynakları Erişilebilirlik ve Entegrasyon Raporu

**Hazırlanma tarihi:** 5 Kasım 2026
**Kapsam:** Ankara'daki yeni işletme kuruluşlarının tespiti ve kamuya açık kurumsal iletişim bilgilerinin araştırılması

> Bu rapor hukuki görüş değildir. Satın alma / sözleşme ve ticari ileti süreçlerinden önce
> bir hukukçu ile KVKK ve 6563 sayılı Kanun açısından değerlendirme yapılmalıdır.

---

## 1. Özet

| Kaynak | Şirket bazlı veri | Otomatik erişim | Hukuki durum | Sistemdeki karşılığı |
|---|---|---|---|---|
| **TTSG Veri Aboneliği (TOBB) – Web Servis** | Evet (Düzey 2/3: MERSİS, adres, NACE, sermaye) | **Evet – resmî web servis** | Sözleşme ile yetkili | `ttsg_ws` adaptörü (otomatik, günlük) |
| **TTSG Bir Günlük Elektronik Gazete** (PDF + fihrist Excel) | Evet | Dosya teslimi (CD / web transfer) | Ücret karşılığı yetkili | `ttsg_inbox` klasör adaptörü (otomatik içe aktarma) |
| ticaretsicil.gov.tr İlan Görüntüleme | Evet (tek tek ilan) | **Hayır** – üye girişi + CAPTCHA | Kişisel görüntüleme | Manuel PDF içe aktarma |
| MERSİS | Evet | **Hayır** – e-Devlet / e-imza girişi | Kimlik doğrulamalı | Otomasyon yok |
| Ankara Ticaret Odası / Sicil Müdürlüğü | Olası (talep ile) | Kamuya açık liste tespit edilmedi | Yazılı talep / protokol | Manuel CSV/Excel içe aktarma |
| Ankara Sanayi Odası | Üye bilgisi | Hayır | Üyelik kapsamında | Kullanılmıyor |
| TOBB Kurulan/Kapanan Şirket İstatistikleri | **Hayır** (yalnızca toplu sayı) | Kamuya açık | Serbest | Kapsam kontrolü için referans |
| Lisanslı ticari veri sağlayıcıları | Sağlayıcıya göre | API / dosya | Lisans sözleşmesi | `licensed_feed` adaptörü |

**Sonuç:** Ankara'da kurulan bir şirketi resmî kayıt yayımlandığı gün otomatik ve yetkili biçimde
tespit etmenin tek yolu **TOBB TTSG Veri Aboneliği (web servis)**dir. Bütçe uygun değilse günlük
elektronik gazete satın alımı + klasöre bırakma yöntemi aynı gün içinde (dosya teslim edildiğinde)
otomatik işlenir. Bu ikisi dışındaki tüm yollar manuel veya gecikmelidir.

---

## 2. Kaynak bazında inceleme

### 2.1 Türkiye Ticaret Sicili Gazetesi (TTSG) – ticaretsicil.gov.tr

**İlan görüntüleme ekranı (inceleme: 5 Kasım 2026)**
- `ilangoruntuleme.php` sayfası "İlan görüntülemek ve ilan alımı için giriş yapmalısınız" uyarısı veriyor.
- Giriş formu e-posta + parola + **4 haneli güvenlik kodu (CAPTCHA)** istiyor; alternatif olarak e-Devlet ile giriş var.
- Sitede kamuya açık API veya RSS tespit edilmedi; `robots.txt` dosyası yok (404).

**Değerlendirme:** CAPTCHA ve oturum zorunluluğu, otomatik toplu erişimin site sahibi tarafından
istenmediğini açıkça gösterir. Sistem bu ekrana **otomatik erişmez**, CAPTCHA çözmez.
Kullanıcı tek tek ilanları kendisi görüntüleyip PDF olarak indirebilir ve "İçe Aktar" ekranından yükleyebilir.

**Resmî veri aboneliği (Abonelik sayfası, 2026 tarifesi)**

| Paket | İçerik (özet) | Teslim | 2026 yıllık ücret |
|---|---|---|---|
| Düzey_1 | Aranamaz PDF + fihrist: TSM, TSM no, unvan, ilan türü, yayın tarihi/sayı, sayfa | Web servis | 484.932 TL |
| Düzey_2 | Aranabilir PDF + fihrist + **MERSİS no, kuruluş adresi**, AŞ/LŞ sermaye | Web servis | 951.792 TL |
| Düzey_3 | Düzey_2 + tüm kuruluşlar için sermaye, vergi no/dairesi, UAVT adres kodu, **amaç-konu metni, ana/alt NACE kodları**, ortaklar ve temsilciler (TCKN maskeli) | Web servis | 1.427.688 TL |
| Bir günlük elektronik gazete | O günün PDF'i (~1.350 sayfa) + fihrist Excel (sıra no, TSM no, unvan, sicil müdürlüğü, tarih, sayı, sayfa, **ilan türü**) | CD / web transfer | 2.730 TL / gün |

Başvuru: abonelik formu + ödeme dekontu, `ttsgmd@tobb.org.tr` adresine ve ıslak imzalı olarak Müdürlüğe gönderilir.

TOBB'un uyarısı: ilan türü kodlaması personel tarafından yapılır ve hata içerebilir; ilan metni esastır.
Bu nedenle sistem ilan türünü filtre olarak kullanır, ancak belirsiz durumları **inceleme kuyruğuna** gönderir.

**Öneri:**
1. **Düzey_3** (NACE + amaç-konu sayesinde İSG tehlike sınıfı ve sektör tahmini *doğrulanmış* hale gelir).
2. Bütçe kısıtında **Düzey_2** (MERSİS + adres; sektör faaliyet metninden *tahmini*).
3. Abonelik öncesi deneme: birkaç günlük elektronik gazete satın alınıp `data/inbox` klasörüne bırakılarak
   ayrıştırıcının gerçek veriyle kalibrasyonu yapılmalıdır.

**Kişisel veri notu:** Düzey_3 ortak/temsilci listeleri (maskeli TCKN, ad soyad) içerir. Bu sistem bu alanları
**içe almaz**; yalnızca işletme düzeyindeki alanları eşler. Alan eşlemesine kişi alanları eklenmemelidir.

### 2.2 MERSİS (mersis.gtb.gov.tr)
- Firma sorgulama, e-Devlet / e-imza / mobil imza / MERSİS hesabı ile giriş gerektirir.
- Kamuya açık toplu sorgu, açık veri seti veya API tespit edilmedi.
- **Otomasyon yapılmaz.** MERSİS numarası TTSG Düzey_2/3 aboneliğinden gelir.

### 2.3 Ankara Ticaret Odası / Ankara Ticaret Sicili Müdürlüğü
- Ankara Ticaret Sicili Müdürlüğü ATO bünyesindedir; tescil edilen kuruluşlar TTSG'de ilan edilir.
- Yeni kayıtların kamuya açık, makine okunabilir bir listesi tespit edilmedi.
- Toplu liste için oda ile yazılı başvuru / protokol yapılabilir; gelen liste "İçe Aktar" ile yüklenir.
- **Not:** Ankara ilinde Polatlı gibi ilçe ticaret odalarının ayrı sicil müdürlükleri vardır. Sistem
  "Polatlı / Beypazarı …" gibi ilçe adlı sicil müdürlüklerini, adres Ankara içeriyorsa hedef il sayar.

### 2.4 Ankara Sanayi Odası
- Sanayi sicili / üyelik bilgileri yeni kuruluş tespiti için gecikmeli ve kapsamı dardır; kamuya açık veri seti yok.

### 2.5 TOBB Kurulan/Kapanan Şirket İstatistikleri
- Aylık, il bazında **toplu sayılar** yayımlanır; şirket adı içermez.
- Kullanım: "Bu ay Ankara'da TOBB X kuruluş açıkladı, sistemde Y var" şeklinde **kapsam kontrolü**.

### 2.6 Şahıs işletmeleri (gerçek kişi tacir / esnaf)
- Ticaret siciline kayıtlı gerçek kişi tacirlerin kuruluşları TTSG'de yer alır (Düzey_3 "gerçek kişi ticari işletmesi" kapsar).
- Esnaf ve sanatkâr sicili (ESBİS) ile vergi dairesi mükellef kayıtları kamuya açık değildir; bu kayıtlar **tespit edilemez**.
- Şahıs işletmelerinde unvan ve adres gerçek kişiyi tanımlayabildiğinden **KVKK kapsamında kişisel veri** sayılır.

---

## 3. İletişim bilgisi kaynakları

| Yöntem | Durum | Saklama kuralı |
|---|---|---|
| İşletmenin kendi web sitesi | robots.txt'e uyularak, host başına ≥1 sn aralıkla, en fazla 4 sayfa | Yalnızca **site alan adındaki** e-postalar ve sabit hat / 444 / 0850 numaraları |
| Alan adı tahmini (unvandan) | Aday üretir; **doğrulama puanı ≥ 60** gerekir | MERSİS/sicil no sitede yoksa güven en fazla 70 ("orta") |
| Brave Search API | Resmî arama API'si (anahtar gerekir) | Sadece aday URL; site doğrulamasından geçmeli |
| OpenStreetMap Nominatim | ODbL açık veri; ≤1 istek/sn, tanımlayıcı User-Agent | Kaynak bağlantısı ile; ODbL atfı gerekir |
| Google Places API (New) | Google Maps Platform koşulları: yalnızca `place_id` saklanabilir | Telefon/web **saklanmaz**, ekranda canlı gösterilir |
| Google Custom Search JSON API | Yeni müşterilere kapatıldığı duyurulmuştu; kullanılmadı | — |

**Yanlış eşleştirmeyi önleme:** Site, unvanın ayırt edici kelimeleri (jenerik sektör/tür ekleri hariç),
tam unvan, MERSİS no, sicil no, "Ankara" ve ilçe ifadeleri ve alan adı uyumu ile puanlanır. Ayırt edici kelimeler
sitede yoksa puan 0'dır. Kullanıcı her kaydı "Doğrula" veya "Yanlış eşleşme" olarak işaretleyebilir.

**Kişisel veri koruması:** gmail/hotmail vb. ücretsiz sağlayıcı e-postaları ve mobil numaralar (05xx) varsayılan
olarak saklanmaz (`STORE_MOBILE_NUMBERS=false`).

---

## 4. Hukuki çerçeve ve sistemdeki karşılığı

| Konu | Sistem davranışı |
|---|---|
| Yetkisiz erişim / CAPTCHA aşma | Yapılmaz. Kimlik doğrulamalı kaynaklar "reference" türündedir ve etkinleştirilemez. |
| Kaynak ve doğrulama tarihi | Her işletmede kaynak, kaynak referansı (dosya/satır/ilan id), doğrulama tarihi; her iletişim bilgisinde kaynak URL ve güven puanı. Ham kayıtlar kanıt olarak saklanır. |
| Sahte veri üretmeme | Ayrıştırılamayan / belirsiz kayıtlar oluşturulmaz, **inceleme kuyruğuna** gider. Doğrulanamayan iletişim bilgisi "Bulunamadı" görünür. |
| Taranmayan gün | Kapsam tablosu gün bazında tutulur; taranmayan veya erişim hatası alınan gün "sıfır kuruluş" gösterilmez. |
| KVKK | Rol tabanlı erişim, denetim kaydı (görüntüleme/dışa aktarma dahil), "iletişime geçme" işareti, anonimleştirme, otomatik saklama süresi (varsayılan 365 / 730 gün). |
| 6563 s. Kanun / İYS | Sistem **otomatik pazarlama iletisi göndermez.** Arama/e-posta öncesi "uygunluk kontrolü": İYS ret kaydı, "iletişime geçme" işareti, kontrol yapılmamış İYS durumu engeller. Tacir/esnaf alıcılara önceden onay şartı aranmasa da ret hakkı vardır; gönderim öncesi İYS sorgusu yapılmalıdır. |
| KVKK aydınlatma | Şahıs işletmeleriyle ilk temasta aydınlatma metni sunulmalıdır (sistem uyarı verir). |
| İSG değerlendirmesi | "Yeni kurulmuş olması çalışan istihdam ettiğini veya İSG hizmeti almadığını kanıtlamaz" uyarısı her analizde gösterilir. Tehlike sınıfı resmî liste yüklenmeden "tahmini" etiketlenir. |

---

## 5. Bilinen sınırlamalar

1. **TTSG web servis teknik dokümanı kamuya açık değil.** Adaptör, abonelik sayfasında listelenen alan adlarına
   göre varsayılan eşleme ile gelir; gerçek uç nokta ve JSON anahtarları sözleşme sonrası `TTSG_WS_FIELD_MAP`
   ile ayarlanmalı ve ilk gün sonuçları kontrol edilmelidir.
2. **PDF ayrıştırıcı gerçek gazete ile kalibre edilmedi.** Yaygın ilan kalıplarına göre yazıldı ve kurgusal
   örneklerle test edildi. Gazete PDF'leri çok sütunlu olduğundan metin sırası bozulabilir; bu durumda kayıtlar
   inceleme kuyruğuna düşer. İlk satın alınan gazete ile doğruluk ölçülmelidir. Fihrist Excel dosyası ilan türünü
   içerdiği için kuruluş filtresinde PDF'ten daha güvenilirdir.
3. **İşyeri Tehlike Sınıfları listesi** pakete eklenmedi (resmî listenin doğru sürümünü kullanıcı yüklemelidir).
4. **Esnaf ve vergi kaydıyla açılan şahıs işletmeleri** kamuya açık kaynaklarda yer almadığından tespit edilemez.
5. Yayın gecikmesi: tescil ile TTSG'de yayım arasında birkaç gün olabilir; "bugün kurulan" işletme ancak ilan
   yayımlandığında tespit edilebilir.

---

## 6. Kaynaklar

- TTSG ana sayfa ve ilan görüntüleme: https://www.ticaretsicil.gov.tr/ , https://www.ticaretsicil.gov.tr/view/hizlierisim/ilangoruntuleme.php
- TTSG Abonelik (veri aboneliği tarifeleri): https://www.ticaretsicil.gov.tr/view/hizlierisim/goster.php?Guid=4fb204d4-8b72-11e9-a292-54e058904e0d
- MERSİS: https://mersis.gtb.gov.tr/
- TOBB Kurulan/Kapanan Şirket İstatistikleri: https://www.tobb.org.tr/BilgiErisimMudurlugu/Sayfalar/KurulanKapananSirketistatistikleri.php
- Ticaret Bakanlığı – Ticaret Sicili: https://ticaret.gov.tr/ic-ticaret/ticaret-sicili
- Google Maps Platform Hizmete Özel Koşullar (Places önbellekleme): https://cloud.google.com/maps-platform/terms/maps-service-terms
- OpenStreetMap Nominatim Kullanım Politikası: https://operations.osmfoundation.org/policies/nominatim/

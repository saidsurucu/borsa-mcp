# Borsa MCP: Türk Finans Piyasaları için MCP Sunucusu

[![Star History Chart](https://api.star-history.com/svg?repos=saidsurucu/borsa-mcp&type=Date)](https://www.star-history.com/#saidsurucu/borsa-mcp&Date)

Borsa İstanbul (BIST) hisseleri, TEFAS fonları, kripto paralar ve döviz/emtia verilerine LLM'ler üzerinden erişim sağlayan [FastMCP](https://gofastmcp.com/) sunucusu. KAP, Yahoo Finance, BtcTurk, Coinbase, Doviz.com ve TCMB gibi kaynaklardan 41 araçla kapsamlı finansal analiz.

![ornek](./ornek.jpeg)

![fon ornek](./fon-ornek.png)

---

## ⚠️ Önemli Uyarılar

- **LLM'ler halüsinasyon yapabilir** - Verileri mutlaka doğrulayın
- **Yatırım tavsiyesi değildir** - Profesyonel danışmanlık alın
- **Eğitim amaçlıdır** - Sorumluluk size aittir

---

## 🚀 5 Dakikada Başla (Remote MCP)

**✅ Kurulum Gerektirmez! Hemen Kullan!**

🔗 **Remote MCP Adresi:** https://borsamcp.fastmcp.app/mcp

### Claude Desktop ile Kullanım

1. **Claude Desktop**'ı açın
2. **Settings** → **Connectors** → **Add Custom Connector**
3. Bilgileri girin:
   - **Name:** `Borsa MCP`
   - **URL:** `https://borsamcp.fastmcp.app/mcp`
4. **Add** butonuna tıklayın
5. Hemen kullanmaya başlayın! 🎉

**Örnek Sorular:**
```
GARAN hissesinin son 1 aylık performansını analiz et
XU100 endeksinin bugünkü durumunu göster
Bitcoin'in TRY fiyatını kontrol et
```

---

## 🎯 Temel Özellikler

**41 Araç ile Kapsamlı Finansal Analiz:**

* 📈 **BIST Hisseleri:** 758 şirket, finansal tablolar, teknik analiz, analist raporları, KAP haberleri
* 🆕 **Tarih Aralığı:** Belirli tarihler arası geçmiş veri sorgulaması (örn: "2024-01-01" - "2024-12-31")
* 🎯 **Pivot Points:** 3 direnç & 3 destek seviyesi hesaplama (klasik pivot formülü)
* 📊 **BIST Endeksleri:** XU100, XBANK, XK100 ve tüm endeksler için tam destek
* 💰 **TEFAS Fonları:** 800+ fon, performans analizi, portföy dağılımı, karşılaştırma
* ₿ **Kripto Paralar:** BtcTurk (TRY) ve Coinbase (USD/EUR) ile Türk ve global piyasalar
* 💱 **Döviz & Emtia:** USD, EUR, altın, petrol ve 28+ varlık takibi (Doviz.com)
* 📅 **Ekonomik Takvim:** TR, US, EU ve 30+ ülke için makroekonomik veriler
* 📉 **TCMB Enflasyon:** TÜFE/ÜFE resmi enflasyon verileri ve hesaplama araçları
* ☪️ **Katılım Finans:** İslami finans uygunluk verileri
* ⚡ **LLM Optimizasyonu:** Hızlı işleme ve domain-spesifik araç seçimi

## 📑 **İçindekiler**

- [🚀 5 Dakikada Başla (Remote MCP)](#-5-dakikada-başla-remote-mcp) - **Kurulum gerektirmez!**
- [🎯 Temel Özellikler](#-temel-özellikler)

<details>
<summary><b>💻 Gelişmiş Kurulum (İsteğe Bağlı)</b></summary>

- [5ire ve Diğer MCP İstemcileri](#-claude-haricindeki-modellerle-kullanmak-için-çok-kolay-kurulum-örnek-5ire-için)
- [Claude Desktop Manuel/Local Kurulum](#️-claude-desktop-manuel-kurulumu)

</details>

<details>
<summary><b>🛠️ Kullanılabilir Araçlar</b></summary>

- [Temel Şirket & Finansal Veriler](#temel-şirket--finansal-veriler)
- [Gelişmiş Analiz Araçları](#gelişmiş-analiz-araçları)
- [KAP & Haberler](#kap--haberler)
- [BIST Endeks Araçları](#bist-endeks-araçları)
- [Katılım Finans](#katılım-finans)
- [TEFAS Fon Araçları](#tefas-fon-araçları)
- [BtcTurk Kripto Araçları](#btcturk-kripto-para-araçları-türk-piyasası)
- [Coinbase Global Kripto Araçları](#coinbase-global-kripto-para-araçları-uluslararası-piyasalar)
- [Dovizcom Döviz & Emtia Araçları](#dovizcom-döviz--emtia-araçları-türk--uluslararası-piyasalar)
- [Ekonomik Takvim](#dovizcom-ekonomik-takvim-araçları)
- [TCMB Enflasyon Araçları](#tcmb-enflasyon-araçları)

</details>

<details>
<summary><b>🔍 Veri Kaynakları & Kapsam</b></summary>

- [KAP (Kamuyu Aydınlatma Platformu)](#kap-kamuyu-aydınlatma-platformu)
- [Yahoo Finance](#yahoo-finance-entegrasyonu)
- [Mynet Finans](#mynet-finans-hibrit-mod)
- [TEFAS](#tefas-türkiye-elektronik-fon-alım-satım-platformu)
- [BtcTurk & Coinbase](#btcturk-kripto-para-borsası-türk-piyasası)
- [Dovizcom](#dovizcom-döviz--emtia-platformu-türk--uluslararası-piyasalar)
- [TCMB](#tcmb-enflasyon-verileri-resmi-merkez-bankası)

</details>

<details>
<summary><b>📊 Örnek Kullanım</b></summary>

- [Hisse Senedi Analizleri](#-örnek-kullanım)
- [Fon Analizleri](#-örnek-kullanım)
- [Kripto Para Analizleri](#-örnek-kullanım)
- [Döviz & Emtia Analizleri](#-örnek-kullanım)
- [Ekonomik Takvim](#-örnek-kullanım)
- [Enflasyon Analizleri](#-örnek-kullanım)

</details>

---

## 💻 Gelişmiş Kurulum (İsteğe Bağlı)

**Not:** Remote MCP kullanıyorsanız bu adımları atlayabilirsiniz!

<details>
<summary><b>5ire ve Diğer MCP İstemcileri için Local Kurulum</b></summary>

Bu bölüm, Borsa MCP'yi 5ire gibi diğer MCP istemcileriyle local olarak kullanmak isteyenler içindir.

* **Python Kurulumu:** Sisteminizde Python 3.11 veya üzeri kurulu olmalıdır. Kurulum sırasında "**Add Python to PATH**" (Python'ı PATH'e ekle) seçeneğini işaretlemeyi unutmayın. [Buradan](https://www.python.org/downloads/) indirebilirsiniz.
* **Git Kurulumu (Windows):** Bilgisayarınıza [git](https://git-scm.com/downloads/win) yazılımını indirip kurun. "Git for Windows/x64 Setup" seçeneğini indirmelisiniz.
* **`uv` Kurulumu:**
    * **Windows Kullanıcıları (PowerShell):** Bir CMD ekranı açın ve bu kodu çalıştırın: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
    * **Mac/Linux Kullanıcıları (Terminal):** Bir Terminal ekranı açın ve bu kodu çalıştırın: `curl -LsSf https://astral.sh/uv/install.sh | sh`
* **Microsoft Visual C++ Redistributable (Windows):** Bazı Python paketlerinin doğru çalışması için gereklidir. [Buradan](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170) indirip kurun.
* İşletim sisteminize uygun [5ire](https://5ire.app) MCP istemcisini indirip kurun.
* 5ire'ı açın. **Workspace -> Providers** menüsünden kullanmak istediğiniz LLM servisinin API anahtarını girin.
* **Tools** menüsüne girin. **+Local** veya **New** yazan butona basın.
    * **Tool Key:** `borsamcp`
    * **Name:** `Borsa MCP`
    * **Command:**
        ```
        uvx --from git+https://github.com/saidsurucu/borsa-mcp borsa-mcp
        ```
    * **Save** butonuna basarak kaydedin.
* Şimdi **Tools** altında **Borsa MCP**'yi görüyor olmalısınız. Üstüne geldiğinizde sağda çıkan butona tıklayıp etkinleştirin (yeşil ışık yanmalı).
* Artık Borsa MCP ile konuşabilirsiniz.

</details>

<details>
<summary><b>Claude Desktop için Local Kurulum</b></summary>

**Not:** Remote MCP daha kolay bir seçenektir. Sadece local kurulum yapmak istiyorsanız bu adımları izleyin.

1.  **Ön Gereksinimler:** Python, `uv`, (Windows için) Microsoft Visual C++ Redistributable'ın sisteminizde kurulu olduğundan emin olun. Detaylı bilgi için yukarıdaki "5ire için Kurulum" bölümündeki ilgili adımlara bakabilirsiniz.
2.  Claude Desktop **Settings -> Developer -> Edit Config**.
3.  Açılan `claude_desktop_config.json` dosyasına `mcpServers` altına ekleyin. UYARI: // ile başlayan yorum satırını silmelisiniz:

    ```json
    {
      "mcpServers": {
        // ... (varsa diğer sunucularınız) ...
        "Borsa MCP": {
          "command": "uvx",
          "args": [
            "--from", "git+https://github.com/saidsurucu/borsa-mcp",
            "borsa-mcp"
          ]
        }
      }
    }
    ```
4.  Claude Desktop'ı kapatıp yeniden başlatın.

</details>

<details>
<summary><b>🛠️ Kullanılabilir Araçlar (MCP Tools)</b></summary>

Bu FastMCP sunucusu LLM modelleri için aşağıdaki araçları sunar:

### Temel Şirket & Finansal Veriler
* **`find_ticker_code`**: Güncel BIST şirketleri arasında ticker kodu arama.
* **`get_sirket_profili`**: Detaylı şirket profili.
* **`get_bilanco`**: Bilanço verileri (yıllık/çeyreklik).
* **`get_kar_zarar_tablosu`**: Kar-zarar tablosu (yıllık/çeyreklik).
* **`get_nakit_akisi_tablosu`**: Nakit akışı tablosu (yıllık/çeyreklik).
* **`get_finansal_veri`**: Geçmiş OHLCV verileri (hisse senetleri ve endeksler için). **YENİ:** Belirli tarih aralığı desteği (örn: start_date="2024-01-01", end_date="2024-12-31") veya dönem modu (1mo, 1y vb.).

### Gelişmiş Analiz Araçları
* **`get_analist_tahminleri`**: Analist tavsiyeleri, fiyat hedefleri ve trendler.
* **`get_temettu_ve_aksiyonlar`**: Temettü geçmişi ve kurumsal işlemler.
* **`get_hizli_bilgi`**: Hızlı finansal metrikler (P/E, P/B, ROE vb.).
* **`get_kazanc_takvimi`**: Kazanç takvimi ve büyüme verileri.
* **`get_teknik_analiz`**: Kapsamlı teknik analiz ve göstergeler.
* **`get_pivot_points`**: Günlük pivot noktaları ile 3 direnç ve 3 destek seviyesi hesaplama.
* **`get_sektor_karsilastirmasi`**: Sektör analizi ve karşılaştırması.

### KAP & Haberler
* **`get_kap_haberleri`**: Son KAP haberleri ve resmi şirket duyuruları.
* **`get_kap_haber_detayi`**: Detaylı KAP haber içeriği (Markdown formatında).

### BIST Endeks Araçları
* **`get_endeks_kodu`**: Güncel BIST endeks listesinde endeks kodu arama.
* **`get_endeks_sirketleri`**: Belirli endeksteki şirketlerin listesi.

### Katılım Finans
* **`get_katilim_finans_uygunluk`**: KAP Katılım finans uygunluk verileri ve katılım endeksi üyeliği.

### TEFAS Fon Araçları
* **`search_funds`**: Türk yatırım fonları arama (kategori filtreleme ve performans metrikleri ile).
* **`get_fund_detail`**: Kapsamlı fon bilgileri ve analitiği.
* **`get_fund_performance`**: Resmi TEFAS BindHistoryInfo API ile geçmiş fon performansı.
* **`get_fund_portfolio`**: Resmi TEFAS BindHistoryAllocation API ile fon portföy dağılımı.
* **`compare_funds`**: Resmi TEFAS karşılaştırma API ile çoklu fon karşılaştırması.

### Fon Mevzuat Araçları
* **`get_fon_mevzuati`**: Türk yatırım fonları mevzuat rehberi (hukuki uyumluluk için).

### BtcTurk Kripto Para Araçları (Türk Piyasası)
* **`get_kripto_exchange_info`**: Tüm kripto çiftleri, para birimleri ve borsa operasyonel durumu.
* **`get_kripto_ticker`**: Kripto çiftler için gerçek zamanlı fiyat verileri (çift veya kote para birimi filtresi ile).
* **`get_kripto_orderbook`**: Güncel alış/satış emirlerini içeren emir defteri derinliği.
* **`get_kripto_trades`**: Piyasa analizi için son işlem geçmişi.
* **`get_kripto_ohlc`**: Kripto grafikleri ve teknik analiz için OHLC verileri.
* **`get_kripto_kline`**: Çoklu zaman çözünürlükleri ile Kline (mum grafik) verileri.
* **`get_kripto_teknik_analiz`**: Türk kripto piyasaları için RSI, MACD, Bollinger Bantları ve al-sat sinyalleri ile kapsamlı teknik analiz.

### Coinbase Global Kripto Para Araçları (Uluslararası Piyasalar)
* **`get_coinbase_exchange_info`**: Global işlem çiftleri ve para birimleri (USD/EUR piyasaları ile).
* **`get_coinbase_ticker`**: Uluslararası piyasalar için gerçek zamanlı global kripto fiyatları (USD/EUR).
* **`get_coinbase_orderbook`**: USD/EUR alış/satış fiyatları ile global emir defteri derinliği.
* **`get_coinbase_trades`**: Çapraz piyasa analizi için son global işlem geçmişi.
* **`get_coinbase_ohlc`**: USD/EUR kripto grafikleri için global OHLC verileri.
* **`get_coinbase_server_time`**: Coinbase sunucu zamanı ve API durumu.
* **`get_coinbase_teknik_analiz`**: Global kripto piyasaları için RSI, MACD, Bollinger Bantları ve al-sat sinyalleri ile kapsamlı teknik analiz.

### Dovizcom Döviz & Emtia Araçları (Türk & Uluslararası Piyasalar)
* **`get_dovizcom_guncel`**: Güncel döviz kurları ve emtia fiyatları (USD, EUR, GBP, gram-altın, ons, BRENT, dizel, benzin, LPG).
* **`get_dovizcom_dakikalik`**: Gerçek zamanlı izleme için dakikalık veriler (60 veri noktasına kadar).
* **`get_dovizcom_arsiv`**: Teknik analiz ve trend araştırması için tarihsel OHLC verileri.

### Dovizcom Ekonomik Takvim Araçları
* **`get_economic_calendar`**: Çoklu ülke ekonomik takvimi (TR,US varsayılan) - GDP, enflasyon, istihdam verileri ve makroekonomik olaylar.

### TCMB Enflasyon Araçları
* **`get_turkiye_enflasyon`**: Resmi TCMB TÜFE/ÜFE enflasyon verileri - TÜFE: tüketici fiyatları (2005-2025, 245+ kayıt), ÜFE: üretici fiyatları (2014-2025, 137+ kayıt) - yıllık/aylık oranlar, tarih aralığı filtreleme, istatistiksel özet.
* **`get_enflasyon_hesapla`**: TCMB resmi enflasyon hesaplama API'si - iki tarih arası kümülatif enflasyon hesaplama, sepet değeri analizi, satın alma gücü kaybı/kazancı, ortalama yıllık enflasyon, TÜFE endeks değerleri.

</details>

<details>
<summary><b>🔍 Veri Kaynakları & Kapsam</b></summary>

### KAP (Kamuyu Aydınlatma Platformu)
- **Şirketler**: 758 BIST şirketi (ticker kodları, adlar, şehirler, çoklu ticker desteği)
- **Katılım Finans**: Resmi katılım finans uygunluk değerlendirmeleri
- **Güncelleme**: Otomatik önbellek ve yenileme

### Yahoo Finance Entegrasyonu
- **Endeks Desteği**: Tüm BIST endeksleri (XU100, XBANK, XK100 vb.) için tam destek
- **Zaman Dilimi**: Tüm zaman damgaları Avrupa/İstanbul'a çevrilir
- **Veri Kalitesi**: Büyük bankalar ve teknoloji şirketleri en iyi kapsama sahiptir
- **Tarih Aralığı Desteği**: Belirli tarihler arası sorgulama (YYYY-MM-DD formatında, örn: "2024-01-01" - "2024-12-31")
- **İki Sorgu Modu**:
  - **Dönem Modu:** Period parametresi ile (1d, 1mo, 1y, vb.) - varsayılan
  - **Tarih Modu:** start_date ve end_date parametreleri ile belirli tarih aralığı

### Mynet Finans (Hibrit Mod)
- **Türk Özel Verileri**: Kurumsal yönetim, ortaklık yapısı, bağlı şirketler
- **KAP Haberleri**: Gerçek zamanlı resmi duyuru akışı
- **Endeks Kompozisyonu**: Canlı endeks şirket listeleri

### TEFAS (Türkiye Elektronik Fon Alım Satım Platformu)
- **Fon Evreni**: 800+ Türk yatırım fonu
- **Resmi API**: TEFAS BindHistoryInfo ve BindHistoryAllocation API'leri
- **Kategori Filtreleme**: 13 fon kategorisi (borçlanma, hisse senedi, altın vb.)
- **Performans Metrikleri**: 7 dönemlik getiri analizi (1 günlük - 3 yıllık)
- **Portföy Analizi**: 50+ Türk varlık kategorisi ile detaylı dağılım
- **Güncellik**: Gerçek zamanlı fon fiyatları ve performans verileri

### Fon Mevzuatı
- **Kaynak**: `fon_mevzuat_kisa.md` - 80,820 karakter düzenleme metni
- **Kapsam**: Yatırım fonları için kapsamlı Türk mevzuatı
- **İçerik**: Portföy limitleri, fon türleri, uyumluluk kuralları
- **Güncelleme**: Dosya metadata ile son güncelleme tarihi

### BtcTurk Kripto Para Borsası (Türk Piyasası)
- **İşlem Çiftleri**: 295+ kripto para işlem çifti (ana TRY ve USDT piyasaları dahil)
- **Para Birimleri**: 158+ desteklenen kripto para ve fiat para birimi (BTC, ETH, TRY, USDT vb.)
- **API Endpoint**: Resmi BtcTurk Public API v2 (https://api.btcturk.com/api/v2)
- **Piyasa Verileri**: Gerçek zamanlı ticker fiyatları, emir defterleri, işlem geçmişi, OHLC/Kline grafikleri
- **Türk Odak**: TRY çiftleri için optimize edilmiş (BTCTRY, ETHTRY, ADATRY vb.)
- **Güncelleme Sıklığı**: Borsa bilgileri için 1 dakika önbellek ile gerçek zamanlı piyasa verileri
- **Veri Kalitesi**: Milisaniye hassasiyetli zaman damgaları ile profesyonel seviye borsa verileri

### Coinbase Global Kripto Para Borsası (Uluslararası Piyasalar)
- **İşlem Çiftleri**: 500+ global kripto para işlem çifti (ana USD, EUR ve GBP piyasaları dahil)
- **Para Birimleri**: 200+ desteklenen kripto para ve fiat para birimi (BTC, ETH, USD, EUR, GBP vb.)
- **API Endpoint**: Resmi Coinbase Advanced Trade API v3 ve App API v2 (https://api.coinbase.com)
- **Piyasa Verileri**: Gerçek zamanlı ticker fiyatları, emir defterleri, işlem geçmişi, OHLC/mum grafikleri, sunucu zamanı
- **Global Odak**: Uluslararası piyasalar için USD/EUR çiftleri (BTC-USD, ETH-EUR vb.)
- **Güncelleme Sıklığı**: Borsa bilgileri için 5 dakika önbellek ile gerçek zamanlı piyasa verileri
- **Veri Kalitesi**: Coinbase (NASDAQ: COIN) kurumsal seviye global likidite ile işletme düzeyinde borsa verileri
- **Kapsam**: Tam global piyasa kapsama, kurumsal seviye işlem verileri, çapraz piyasa arbitraj fırsatları
- **Çapraz Piyasa Analizi**: Türk kripto piyasaları (BtcTurk TRY çiftleri) ile global piyasaları (Coinbase USD/EUR çiftleri) karşılaştırma

### Dovizcom Döviz & Emtia Platformu (Türk & Uluslararası Piyasalar)
- **Varlık Kapsamı**: 28+ varlık (ana para birimleri, kıymetli madenler, enerji emtiaları, yakıt fiyatları)
- **Ana Para Birimleri**: USD, EUR, GBP, JPY, CHF, CAD, AUD ile gerçek zamanlı TRY döviz kurları
- **Kıymetli Madenler**: Hem Türk (gram-altın, gümüş) hem uluslararası (ons, XAG-USD, XPT-USD, XPD-USD) çifte fiyatlandırma
- **Enerji Emtiaları**: BRENT ve WTI petrol fiyatları ile tarihsel trendler ve piyasa analizi
- **Yakıt Fiyatları**: Dizel, benzin ve LPG fiyatları (TRY bazlı) ile günlük fiyat takibi
- **API Endpoint**: Resmi doviz.com API v12 (https://api.doviz.com/api/v12)
- **Gerçek Zamanlı Veri**: Kısa vadeli analiz için 60 veri noktasına kadar dakikalık güncellemeler
- **Tarihsel Veri**: Teknik analiz ve trend araştırması için özel tarih aralıklarında günlük OHLC verileri
- **Güncelleme Sıklığı**: Güncel kurlar için 1 dakika önbellek ile gerçek zamanlı piyasa verileri
- **Veri Kalitesi**: Türkiye'nin önde gelen finansal bilgi sağlayıcısından profesyonel seviye finansal veriler
- **Piyasa Odağı**: Çapraz piyasa analizi için uluslararası USD/EUR karşılaştırmaları ile Türk TRY bazlı fiyatlandırma
- **Kimlik Doğrulama**: Güvenilir API erişimi için uygun başlık yönetimi ile Bearer token kimlik doğrulaması
- **Kapsam**: Döviz ticareti, kıymetli maden yatırımı, emtia analizi ve yakıt fiyat takibi için tam finansal piyasalar kapsamı

### Dovizcom Ekonomik Takvim (Çoklu Ülke Desteği)
- **Makroekonomik Olaylar**: GDP, enflasyon, istihdam, sanayi üretimi, PMI, işsizlik oranları ve diğer piyasa etkili ekonomik göstergeler
- **Ülke Kapsamı**: 30+ ülke (TR, US, EU, GB, JP, DE, FR, CA, AU, CN, KR, BR vb.) için ekonomik veri takibi
- **Çoklu Ülke Filtreleme**: Virgülle ayrılmış ülke kodları ile esnek filtreleme (örn: "TR,US,DE")
- **Varsayılan Davranış**: Türkiye ve ABD ekonomik olayları (TR,US) varsayılan olarak gösterilir
- **API Endpoint**: Resmi Doviz.com Economic Calendar API (https://www.doviz.com/calendar/getCalendarEvents)
- **Filtreleme Özellikleri**: Ülke bazlı filtreleme, önem seviyesi seçimi (yüksek/orta/düşük), özelleştirilebilir tarih aralıkları
- **Veri Detayları**: Gerçek değerler, önceki dönem verileri, tahminler (mevcut olduğunda), dönem bilgileri Türkçe açıklamalar
- **Güncelleme Sıklığı**: Gerçek zamanlı ekonomik olay takibi ve uluslararası piyasa etkisi analizi
- **Zaman Dilimi Desteği**: Avrupa/İstanbul ana zaman dilimi ile Türk saati koordinasyonu
- **Veri Kalitesi**: Doviz.com'un özelleşmiş finansal veri ağından profesyonel seviye uluslararası makroekonomik bilgiler

### TCMB Enflasyon Verileri (Resmi Merkez Bankası)
- **Veri Kaynağı**: Türkiye Cumhuriyet Merkez Bankası resmi enflasyon istatistikleri sayfaları
- **Veri Türleri**: 
  - **TÜFE:** Tüketici Fiyat Endeksi (2005-2025, 245+ aylık kayıt)
  - **ÜFE:** Üretici Fiyat Endeksi - Yurt İçi (2014-2025, 137+ aylık kayıt)
- **Güncelleme Sıklığı**: Aylık (genellikle ayın ortasında resmi açıklama)
- **Veri Kalitesi**: Resmi TCMB kaynağından web scraping ile %100 güvenilir
- **Performans**: 2-3 saniye (1 saatlik cache ile optimize edilmiş)
- **Filtreleme**: Enflasyon türü seçimi, tarih aralığı (YYYY-MM-DD), kayıt sayısı limiti
- **İstatistikler**: Min/max oranlar, ortalamalar, son değerler otomatik hesaplama
- **Son Veriler (Mayıs 2025)**: 
  - **TÜFE:** %35.41 (yıllık), %1.53 (aylık)
  - **ÜFE:** %23.13 (yıllık), %2.48 (aylık)
- **Ekonomik Analiz**: ÜFE öncü gösterge olarak TÜFE hareketlerini öngörmede kullanılır

</details>

<details>
<summary><b>📊 Örnek Kullanım</b></summary>

```
# Şirket arama
GARAN hissesi için detaylı analiz yap

# Endeks analizi
XU100 endeksinin son 1 aylık performansını analiz et

# Tarih aralığı ile hisse analizi (YENİ!)
GARAN hissesinin 2024 yıl başından bugüne performansını analiz et

# Belirli dönem karşılaştırması (YENİ!)
THYAO'nun 2023 ve 2024 yıllarının ilk çeyreklerini karşılaştır

# Teknik analiz
ASELS için kapsamlı teknik analiz ve al-sat sinyalleri ver

# KAP haberleri
THYAO için son 5 KAP haberini getir ve ilkinin detayını analiz et

# Katılım finans
ARCLK'nın katılım finans uygunluğunu kontrol et

# Sektör karşılaştırması
Bankacılık sektöründeki ana oyuncuları karşılaştır: GARAN, AKBNK, YKBNK

# Fon arama ve analizi
"altın" fonları ara ve en iyi performans gösteren 3 tanesini karşılaştır

# Fon portföy analizi
AAK fonunun son 6 aylık portföy dağılım değişimini analiz et

# Fon mevzuat sorguları
Yatırım fonlarında türev araç kullanım limitleri nelerdir?

# Türk kripto para analizi
Bitcoin'in TRY cinsinden son 1 aylık fiyat hareketlerini analiz et

# Türk kripto piyasa takibi
BtcTurk'te en çok işlem gören kripto çiftleri listele ve fiyat değişimlerini göster

# Türk kripto emir defteri analizi
BTCTRY çiftinin emir defterini görüntüle ve derinlik analizini yap

# Global kripto para analizi
Bitcoin'in USD cinsinden Coinbase'deki son 1 aylık fiyat hareketlerini analiz et

# Global kripto piyasa takibi
Coinbase'de en popüler USD/EUR kripto çiftlerini listele ve global piyasa trendlerini göster

# Global kripto emir defteri analizi
BTC-USD çiftinin Coinbase emir defterini görüntüle ve global likidite analizini yap

# Çapraz piyasa kripto analizi
Bitcoin fiyatını Türk (BTCTRY) ve global (BTC-USD) piyasalarda karşılaştır

# Arbitraj fırsatı analizi
ETH fiyatlarını BtcTurk (ETHUSDT) ve Coinbase (ETH-USD) arasında karşılaştırarak arbitraj fırsatlarını tespit et

# BtcTurk kripto teknik analiz
BTCTRY çiftinin günlük teknik analizini yap ve al-sat sinyallerini değerlendir

# Coinbase global kripto teknik analiz  
BTC-USD çiftinin 4 saatlik teknik analizini yap ve RSI, MACD durumunu analiz et

# Çapraz piyasa teknik analiz karşılaştırması
Bitcoin'in hem Türk piyasasında (BTCTRY) hem global piyasada (BTC-USD) teknik analiz sinyallerini karşılaştır

# Global kripto teknik analiz
ETH-EUR çiftinin günlük Bollinger Bantları ve hareketli ortalama durumunu analiz et

# Döviz kuru analizi
USD/TRY kurunun güncel durumunu ve son 1 saatteki dakikalık hareketlerini analiz et

# Altın fiyat takibi
Gram altının TRY cinsinden güncel fiyatını al ve son 30 dakikadaki değişimini göster

# Uluslararası altın karşılaştırması
Türk gram altını ile uluslararası ons altın fiyatlarını karşılaştır

# Emtia fiyat analizi
Brent petrolün son 6 aylık OHLC verilerini al ve fiyat trendini analiz et

# Kıymetli maden portföy takibi
Altın, gümüş ve platinyum fiyatlarının güncel durumunu ve haftalık performansını karşılaştır

# Çapraz döviz analizi
EUR/TRY ve GBP/TRY kurlarının güncel durumunu karşılaştır ve arbitraj fırsatlarını değerlendir

# Yakıt fiyat takibi
Dizel, benzin ve LPG fiyatlarının güncel durumunu ve haftalık değişimlerini analiz et

# Yakıt fiyat karşılaştırması
Son 3 aylık dizel ve benzin fiyat trendlerini karşılaştır ve analiz et

# Haftalık ekonomik takvim (çoklu ülke)
Bu haftanın önemli ekonomik olaylarını TR,US,DE için listele ve piyasa etkilerini değerlendir

# Tek ülke ekonomik takip
Sadece Almanya'nın bu ayki ekonomik verilerini getir ve analiz et

# Çoklu ülke ekonomik karşılaştırma
TR,US,GB,FR,DE ülkelerinin bu haftaki tüm ekonomik verilerini karşılaştır

# Ekonomik veri analizi
Türkiye ve ABD'nin son çeyrek GDP büyüme verilerini karşılaştır ve trend analizini yap

# TCMB TÜFE enflasyon analizi
Son 2 yılın tüketici enflasyon verilerini getir ve trend analizini yap

# TCMB ÜFE enflasyon analizi  
Üretici enflasyonunun son 1 yılını analiz et ve TÜFE ile karşılaştır

# Enflasyon dönemsel analizi
2022-2024 yüksek enflasyon dönemini hem TÜFE hem ÜFE açısından analiz et

# TÜFE vs ÜFE karşılaştırması
Son 12 aylık TÜFE ve ÜFE verilerini karşılaştır ve fiyat geçişkenliğini analiz et

# Güncel enflasyon durumu
Son 6 aylık hem tüketici hem üretici enflasyon verilerini al ve Merkez Bankası hedefleriyle karşılaştır

# TCMB enflasyon hesaplayıcı analizi
2020'deki 100 TL'nin bugünkü satın alma gücünü hesapla

# Yüksek enflasyon dönemi analizi
2021-2024 yüksek enflasyon döneminde 1000 TL'nin değişimini hesapla ve kümülatif enflasyon etkisini analiz et

# Uzun dönemli satın alma gücü analizi
2010'dan bugüne 5000 TL'lik maaşın satın alma gücündeki değişimi hesapla

# Kısa dönemli enflasyon hesaplaması
Son 6 aylık enflasyon etkisini hesapla ve yıllık bazda projeksiyon yap

# Ekonomik kriz dönemleri karşılaştırması
2001, 2008 ve 2018 ekonomik krizlerinin enflasyon etkilerini karşılaştır

# Kontrat endeksleme hesaplaması
Kira sözleşmelerinin enflasyon ayarlaması için gerekli artış oranını hesapla
```

</details>

---

📜 **Lisans**

Bu proje MIT Lisansı altında lisanslanmıştır. Detaylar için `LICENSE` dosyasına bakınız.

# Borsa MCP: Borsa İstanbul (BIST), TEFAS Fonları ve Türk/Global Kripto Piyasaları için MCP Sunucusu

[![Star History Chart](https://api.star-history.com/svg?repos=saidsurucu/borsa-mcp&type=Date)](https://www.star-history.com/#saidsurucu/borsa-mcp&Date)

Bu proje, Borsa İstanbul (BIST) verilerine, Türk yatırım fonları verilerine, global kripto para verilerine ve döviz/emtia verilerine erişimi kolaylaştıran bir [FastMCP](https://gofastmcp.com/) sunucusu oluşturur. Bu sayede, KAP (Kamuyu Aydınlatma Platformu), TEFAS (Türkiye Elektronik Fon Alım Satım Platformu), BtcTurk, Coinbase, Doviz.com, Mynet Finans ve Yahoo Finance'dan hisse senedi bilgileri, fon verileri, hem Türk hem de global kripto para piyasa verileri, döviz kurları ve emtia fiyatları, finansal veriler, teknik analiz ve sektör karşılaştırmaları, Model Context Protocol (MCP) destekleyen LLM (Büyük Dil Modeli) uygulamaları (örneğin Claude Desktop veya [5ire](https://5ire.app)) ve diğer istemciler tarafından araç (tool) olarak kullanılabilir hale gelir.

![ornek](./ornek.jpeg)

![fon ornek](./fon-ornek.png)


🎯 **Temel Özellikler**

* Borsa İstanbul (BIST), Türk yatırım fonları, global kripto para verileri ve döviz/emtia verilerine programatik erişim için kapsamlı bir MCP arayüzü.
* **39 Araç** ile tam finansal analiz desteği:
    * **Şirket Arama:** 758 BIST şirketi arasında ticker kodu ve şirket adına göre arama (çoklu ticker desteği ile).
    * **Finansal Veriler:** Bilanço, kar-zarar, nakit akışı tabloları ve geçmiş OHLCV verileri.
    * **Teknik Analiz:** RSI, MACD, Bollinger Bantları gibi teknik göstergeler ve al-sat sinyalleri.
    * **Analist Verileri:** Analist tavsiyeleri, fiyat hedefleri ve kazanç takvimi.
    * **KAP Haberleri:** Resmi şirket duyuruları ve düzenleyici başvurular.
    * **Endeks Desteği:** BIST endeksleri (XU100, XBANK, XK100 vb.) için tam destek.
    * **Katılım Finans:** Katılım finans uygunluk verileri.
    * **TEFAS Fonları:** 800+ Türk yatırım fonu arama, performans, portföy analizi.
    * **Fon Mevzuatı:** Yatırım fonları düzenlemeleri ve hukuki uyumluluk rehberi.
    * **BtcTurk Kripto:** 295+ Türk kripto para çifti (TRY/USDT), gerçek zamanlı fiyatlar, emir defteri, işlem geçmişi, teknik analiz.
    * **Coinbase Global:** 500+ global kripto para çifti (USD/EUR), uluslararası piyasa verileri, çapraz piyasa analizi, teknik analiz.
    * **Kripto Teknik Analiz:** RSI, MACD, Bollinger Bantları ve al-sat sinyalleri ile hem Türk hem global kripto piyasalar için kapsamlı teknik analiz.
    * **Doviz.com Döviz & Emtia:** 25+ varlık ile döviz kurları (USD, EUR, GBP), kıymetli madenler (altın, gümüş), enerji emtiaları (petrol).
    * **Gerçek Zamanlı Döviz:** Dakikalık fiyat güncellemeleri ve tarihsel OHLC analizi ile kapsamlı döviz takibi.
    * **Hibrit Veri:** Yahoo Finance + Mynet Finans'tan birleştirilmiş şirket bilgileri.
* Türk hisse senetleri, endeksler, yatırım fonları ve kripto para için optimize edilmiş veri işleme.
* **LLM Optimizasyonu:** Domain-özel araç ön ekleri ("BIST STOCKS:", "CRYPTO BtcTurk:", "CRYPTO Coinbase:") ile gelişmiş araç seçimi.
* **Hızlı İşleme:** Kısa araç açıklamaları ve LLM-dostu dokümantasyon ile optimize edilmiş performans.
* Claude Desktop uygulaması ile kolay entegrasyon.
* Borsa MCP, [5ire](https://5ire.app) gibi Claude Desktop haricindeki MCP istemcilerini de destekler.

---
🚀 **Claude Haricindeki Modellerle Kullanmak İçin Çok Kolay Kurulum (Örnek: 5ire için)**

Bu bölüm, Borsa MCP aracını 5ire gibi Claude Desktop dışındaki MCP istemcileriyle kullanmak isteyenler içindir.

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

---
⚙️ **Claude Desktop Manuel Kurulumu**

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

🛠️ **Kullanılabilir Araçlar (MCP Tools)**

Bu FastMCP sunucusu LLM modelleri için aşağıdaki araçları sunar:

### Temel Şirket & Finansal Veriler
* **`find_ticker_code`**: Güncel BIST şirketleri arasında ticker kodu arama.
* **`get_sirket_profili`**: Detaylı şirket profili.
* **`get_bilanco`**: Bilanço verileri (yıllık/çeyreklik).
* **`get_kar_zarar_tablosu`**: Kar-zarar tablosu (yıllık/çeyreklik).
* **`get_nakit_akisi_tablosu`**: Nakit akışı tablosu (yıllık/çeyreklik).
* **`get_finansal_veri`**: Geçmiş OHLCV verileri (hisse senetleri ve endeksler için).

### Gelişmiş Analiz Araçları
* **`get_analist_tahminleri`**: Analist tavsiyeleri, fiyat hedefleri ve trendler.
* **`get_temettu_ve_aksiyonlar`**: Temettü geçmişi ve kurumsal işlemler.
* **`get_hizli_bilgi`**: Hızlı finansal metrikler (P/E, P/B, ROE vb.).
* **`get_kazanc_takvimi`**: Kazanç takvimi ve büyüme verileri.
* **`get_teknik_analiz`**: Kapsamlı teknik analiz ve göstergeler.
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
* **`get_dovizcom_guncel`**: Güncel döviz kurları ve emtia fiyatları (USD, EUR, GBP, gram-altın, ons, BRENT).
* **`get_dovizcom_dakikalik`**: Gerçek zamanlı izleme için dakikalık veriler (60 veri noktasına kadar).
* **`get_dovizcom_arsiv`**: Teknik analiz ve trend araştırması için tarihsel OHLC verileri.

🔍 **Veri Kaynakları & Kapsam**

### KAP (Kamuyu Aydınlatma Platformu)
- **Şirketler**: 758 BIST şirketi (ticker kodları, adlar, şehirler, çoklu ticker desteği)
- **Katılım Finans**: Resmi katılım finans uygunluk değerlendirmeleri
- **Güncelleme**: Otomatik önbellek ve yenileme

### Yahoo Finance Entegrasyonu
- **Endeks Desteği**: Tüm BIST endeksleri (XU100, XBANK, XK100 vb.) için tam destek
- **Zaman Dilimi**: Tüm zaman damgaları Avrupa/İstanbul'a çevrilir
- **Veri Kalitesi**: Büyük bankalar ve teknoloji şirketleri en iyi kapsama sahiptir

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
- **Varlık Kapsamı**: 25+ varlık (ana para birimleri, kıymetli madenler, enerji emtiaları)
- **Ana Para Birimleri**: USD, EUR, GBP, JPY, CHF, CAD, AUD ile gerçek zamanlı TRY döviz kurları
- **Kıymetli Madenler**: Hem Türk (gram-altın, gümüş) hem uluslararası (ons, XAG-USD, XPT-USD, XPD-USD) çifte fiyatlandırma
- **Enerji Emtiaları**: BRENT ve WTI petrol fiyatları ile tarihsel trendler ve piyasa analizi
- **API Endpoint**: Resmi doviz.com API v12 (https://api.doviz.com/api/v12)
- **Gerçek Zamanlı Veri**: Kısa vadeli analiz için 60 veri noktasına kadar dakikalık güncellemeler
- **Tarihsel Veri**: Teknik analiz ve trend araştırması için özel tarih aralıklarında günlük OHLC verileri
- **Güncelleme Sıklığı**: Güncel kurlar için 1 dakika önbellek ile gerçek zamanlı piyasa verileri
- **Veri Kalitesi**: Türkiye'nin önde gelen finansal bilgi sağlayıcısından profesyonel seviye finansal veriler
- **Piyasa Odağı**: Çapraz piyasa analizi için uluslararası USD/EUR karşılaştırmaları ile Türk TRY bazlı fiyatlandırma
- **Kimlik Doğrulama**: Güvenilir API erişimi için uygun başlık yönetimi ile Bearer token kimlik doğrulaması
- **Kapsam**: Döviz ticareti, kıymetli maden yatırımı ve emtia analizi için tam finansal piyasalar kapsamı

📊 **Örnek Kullanım**

```
# Şirket arama
GARAN hissesi için detaylı analiz yap

# Endeks analizi  
XU100 endeksinin son 1 aylık performansını analiz et

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
```

📜 **Lisans**

Bu proje MIT Lisansı altında lisanslanmıştır. Detaylar için `LICENSE` dosyasına bakınız.

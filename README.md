# İnşaat Proje Yönetim Sistemi

Bu proje, örnek bir inşaat firması senaryosu için geliştirilen web tabanlı bir proje yönetim sistemidir. Sistem, projelerin takibi, kaynak yönetimi, kullanıcı yönetimi ve raporlamaları içermektedir. Hem veritabanı yapısı hem de görsel arayüz belgeleriyle birlikte sunulmuştur.

## 🚀 Projenin Amacı

İnşaat firmalarının projelerini daha etkin yönetebilmesi için:
- Projelerin genel ve detay bilgilerinin izlenmesi,
- Kaynak kullanımının takip edilmesi,
- Kullanıcı rollerinin tanımlanması,
- Raporlama fonksiyonlarının sağlanması amaçlanmıştır.

## 🛠 Kullanılan Teknolojiler

- **Backend:** Python (Flask mikro web çatısı)
- **Veritabanı:** MySQL (MySQL Connector ile bağlantı)
- **Frontend:**
  - HTML5, CSS3
  - [Bootstrap 5](https://getbootstrap.com/)
  - Jinja2 Template Engine
  - JavaScript (form etkileşimleri için)
- **PDF Oluşturma:** `pdfkit` (rapor çıktısı)
- **E-posta Servisi:** `smtplib` ile Gmail SMTP
- **Kimlik Doğrulama:** `itsdangerous` ile token tabanlı işlem
- **Dokümantasyon:** Microsoft Word, PDF
- **Görseller:** PNG formatında arayüz ekran görüntüleri

## ⚙️ Kurulum ve Çalıştırma

### 1. Reponun Klonlanması

```bash
git clone https://github.com/kullaniciadi/insaat-proje-yonetimi.git && cd insaat-proje-yonetimi
```

### 2. Sanal Ortam (Opsiyonel)

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. Gerekli Paketlerin Kurulması

```bash
pip install -r requirements.txt
```


### 4. Veritabanı Kurulumu

- `insaat.sql` dosyasını MySQL üzerinde çalıştırarak veritabanını oluşturun.
- Gerekirse `app.py` içinde veritabanı bağlantı ayarlarını güncelleyin.

### 5. Sunucuyu Başlatma

```bash
python app.py
```

- Tarayıcıdan erişim: [http://localhost:5000](http://localhost:5000)

---

## 🔐 Giriş Bilgisi

Uygulama ilk açıldığında yönetici hesabı veritabanına manuel eklenmelidir.

## 📄 Lisans

Bu proje eğitim amaçlıdır. Ticari kullanım için izin gereklidir.

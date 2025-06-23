import datetime, re
from flask import Flask, request, jsonify, render_template, redirect, session, make_response
import mysql.connector
import json
import pdfkit
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart



smtp_server = "smtp.gmail.com"
smtp_port = 587
sender_email = ""
app_password = ""

app = Flask(__name__)

# Veritabanı Bağlantısı
db = mysql.connector.connect(
    host="localhost",
    user="root",   
    password="",  #MySQL şifrensi
    database="insaat"
)

cursor = db.cursor()
cursor.execute("SET SESSION sql_mode = ''")

app.secret_key = "gizli-key"
sifre_token_uretecisi = URLSafeTimedSerializer(app.secret_key)


@app.route("/")
def home():
    return "İnşaat Yönetim Sistemi API Çalışıyor!"










@app.route("/kullanici_sil/<int:kid>", methods=["DELETE"])
def sil_kullanici(kid):
    cursor.execute("DELETE FROM kullanici WHERE KID = %s", (kid,))
    db.commit()
    
    return jsonify({"message": f"{kid} ID'li kullanıcı silindi."})



@app.route("/giris", methods=["GET", "POST"])
def kullanici_giris():
    if request.method == "POST":
        email = request.form.get("email")
        sifre = request.form.get("sifre")

        sql = "SELECT KID, KAdi, email, rol FROM kullanici WHERE email = %s AND sifre = %s"
        cursor.execute(sql, (email, sifre))
        kullanici = cursor.fetchone()

        if kullanici:
            session["KID"] = kullanici[0]
            session["KAdi"] = kullanici[1]
            session["email"] = kullanici[2]
            session["rol"] = kullanici[3]
            return redirect("/panel")
        else:
            return render_template("login.html", hata="E-posta veya şifre hatalı!")

    return render_template("login.html")





@app.route("/panel")
def panel():
    if "KAdi" not in session:
        return redirect("/login")
    
    return render_template("panel.html", kullanici=session["KAdi"])



@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")



@app.route("/api/projeler", methods=["GET"])
def get_projeler():
    cursor.execute("SELECT * FROM proje")
    projeler = cursor.fetchall()

    proje_listesi = []
    for p in projeler:
        proje_listesi.append({
            "PID": p[0],
            "PAdi": p[1],
            "baslangic_tarihi": p[2].strftime('%Y-%m-%d'),
            "bitis_tarihi": p[3].strftime('%Y-%m-%d'),
            "PDurumu": p[4]
        })

    return app.response_class(
        response=json.dumps(proje_listesi, ensure_ascii=False),
        mimetype='application/json'
    )




@app.route("/projeler", methods=["GET", "POST"])
def projeler():
    if "KAdi" not in session:
        return redirect("/login")

    if request.method == "POST":
        data = request.form
        sql = "INSERT INTO proje (PAdi, baslangic_tarihi, bitis_tarihi, PDurumu) VALUES (%s, %s, %s, %s)"
        values = (data["PAdi"], data["baslangic_tarihi"], data["bitis_tarihi"], data["PDurumu"])
        cursor.execute(sql, values)
        db.commit()
        return redirect("/projeler")

    cursor.execute("SELECT * FROM proje")
    projeler = cursor.fetchall()
    proje_listesi = []

    for p in projeler:
        pid = p[0]
        # En son aşamayı al
        cursor.execute("""
            SELECT aciklama FROM proje_asamalari 
            WHERE PID = %s ORDER BY tarih DESC LIMIT 1
        """, (pid,))
        son_asama = cursor.fetchone()
        son_aciklama = son_asama[0] if son_asama else "Bu proje, planlanan sürede ilerlemektedir. İlerleme raporları zamanla eklenecektir."

        proje_listesi.append({
            "PID": pid,
            "PAdi": p[1],
            "baslangic_tarihi": p[2].strftime('%Y-%m-%d'),
            "bitis_tarihi": p[3].strftime('%Y-%m-%d'),
            "PDurumu": p[4],
            "aciklama": son_aciklama
        })

    return render_template("proje.html", projeler=proje_listesi)





@app.route("/proje/<int:pid>", methods=["GET", "POST"])
def proje_detay(pid):
    if "KAdi" not in session:
        return redirect("/login")

    
    # Yeni aşama ekleniyorsa
    if request.method == "POST":
        tarih = request.form["tarih"]
        aciklama = request.form["aciklama"]
        ekleyen_id = session["KID"]
        ekleyen_rol = session["rol"]

        if ekleyen_rol == "yönetici":
            sql = """INSERT INTO proje_asamalari 
             (PID, tarih, aciklama, ekleyen_id, onayli, onaylayan_id)
             VALUES (%s, %s, %s, %s, 1, %s)"""
            cursor.execute(sql, (pid, tarih, aciklama, ekleyen_id, ekleyen_id))
        else:
            sql = """INSERT INTO proje_asamalari 
             (PID, tarih, aciklama, ekleyen_id, onayli, onaylayan_id)
             VALUES (%s, %s, %s, %s, 0, NULL)"""
            cursor.execute(sql, (pid, tarih, aciklama, ekleyen_id))

        db.commit()
        return redirect(f"/proje/{pid}")


    # Proje bilgisi
    cursor.execute("SELECT * FROM proje WHERE PID = %s", (pid,))
    p = cursor.fetchone()
    if not p:
        return "Proje bulunamadı", 404

    proje = {
        "PID": p[0],
        "PAdi": p[1],
        "baslangic_tarihi": p[2].strftime('%Y-%m-%d'),
        "bitis_tarihi": p[3].strftime('%Y-%m-%d'),
        "PDurumu": p[4]
    }

    # Aşamaları çek (ekleyen ve onaylayan bilgileri dahil)
    # Aşamaları çek (ekleyen, onaylayan, düzenleyen dahil)
    cursor.execute("""
    SELECT pa.AID, pa.tarih, pa.aciklama, pa.onayli,
       ekleyen.KAdi AS ekleyen_ad, ekleyen.rol AS ekleyen_rol, ekleyen.KID AS ekleyen_id,
       onaylayan.KAdi AS onaylayan_ad, onaylayan.rol AS onaylayan_rol,
       duzenleyen.KAdi AS duzenleyen_ad, duzenleyen.rol AS duzenleyen_rol,
       pa.duzenleme_tarihi, pa.eski_aciklama
    FROM proje_asamalari pa
    JOIN kullanici ekleyen ON pa.ekleyen_id = ekleyen.KID
    LEFT JOIN kullanici onaylayan ON pa.onaylayan_id = onaylayan.KID
    LEFT JOIN kullanici duzenleyen ON pa.duzenleyen_id = duzenleyen.KID
    WHERE pa.PID = %s
    ORDER BY pa.tarih ASC""", (pid,))

    asamalar = []
    for a in cursor.fetchall():
        asamalar.append({
        "aid": a[0],
        "tarih": a[1].strftime('%Y-%m-%d'),
        "aciklama": a[2],
        "onayli": bool(a[3]),
        "ekleyen_ad": a[4],
        "ekleyen_rol": a[5],
        "ekleyen_id": a[6],
        "onaylayan_ad": a[7] if a[7] else None,
        "onaylayan_rol": a[8] if a[8] else None,
        "duzenleyen_ad": a[9] if a[9] else None,
        "duzenleyen_rol": a[10] if a[10] else None,
        "duzenleme_tarihi": a[11].strftime('%Y-%m-%d %H:%M') if a[11] else None,
        "eski_aciklama": a[12]
    })



    # En güncel açıklamayı çek
    cursor.execute("""
    SELECT aciklama 
    FROM proje_asamalari 
    WHERE PID = %s 
    ORDER BY tarih DESC, AID DESC 
    LIMIT 1""", (pid,))
    aciklama_son = cursor.fetchone()
    guncel_aciklama = aciklama_son[0] if aciklama_son else "Bu proje, planlanan sürede ilerlemektedir."

    return render_template("proje_detay.html", proje=proje, asamalar=asamalar, guncel_aciklama=guncel_aciklama)




@app.route("/proje/<int:pid>/asama-onayla/<int:aid>", methods=["POST"])
def asama_onayla(pid, aid):
    if session.get("rol") != "yönetici":
        return "Yetkisiz işlem", 403

    onaylayan_id = session["KID"]
    sql = """
        UPDATE proje_asamalari 
        SET onayli = 1, onaylayan_id = %s 
        WHERE AID = %s
    """
    cursor.execute(sql, (onaylayan_id, aid))
    db.commit()
    return redirect(f"/proje/{pid}")







@app.route("/proje/<int:pid>/asama-duzenle/<int:aid>", methods=["POST"])
def asama_duzenle(pid, aid):
    if "KID" not in session or session.get("rol") != "yönetici":
        return "Yetkisiz işlem", 403

    yeni_aciklama = request.form["aciklama"]
    duzenleyen_id = session["KID"]
    now = datetime.datetime.now()

    # Mevcut açıklamayı çek
    cursor.execute("SELECT aciklama FROM proje_asamalari WHERE AID = %s", (aid,))
    mevcut = cursor.fetchone()
    eski_aciklama = mevcut[0] if mevcut else None

    # Güncelleme sorgusu
    sql = """
        UPDATE proje_asamalari 
        SET aciklama = %s, 
            eski_aciklama = %s,
            duzenleyen_id = %s,
            duzenleme_tarihi = %s
        WHERE AID = %s
    """
    cursor.execute(sql, (yeni_aciklama, eski_aciklama, duzenleyen_id, now, aid))
    db.commit()

    return redirect(f"/proje/{pid}")






@app.route("/proje/<int:pid>/asama-ekle", methods=["POST"])
def asama_ekle(pid):
    if "KID" not in session:
        return redirect("/login")

    tarih = request.form.get("tarih")
    aciklama = request.form.get("aciklama")
    ekleyen_id = session["KID"]
    ekleyen_rol = session["rol"]

    if ekleyen_rol == "yönetici":
        # otomatik onayla
        sql = """INSERT INTO proje_asamalari 
                 (PID, tarih, aciklama, ekleyen_id, onayli, onaylayan_id)
                 VALUES (%s, %s, %s, %s, 1, %s)"""
        cursor.execute(sql, (pid, tarih, aciklama, ekleyen_id, ekleyen_id))
    else:
        sql = """INSERT INTO proje_asamalari 
                 (PID, tarih, aciklama, ekleyen_id, onayli, onaylayan_id)
                 VALUES (%s, %s, %s, %s, 0, NULL)"""
        cursor.execute(sql, (pid, tarih, aciklama, ekleyen_id))

    db.commit()
    return redirect(f"/proje/{pid}")





@app.route("/proje-duzenle/<int:pid>", methods=["GET", "POST"])
def proje_duzenle(pid):
    if request.method == "POST":
        data = request.form
        sql = """
            UPDATE proje 
            SET PAdi = %s, baslangic_tarihi = %s, bitis_tarihi = %s, PDurumu = %s
            WHERE PID = %s
        """
        values = (
            data["PAdi"],
            data["baslangic_tarihi"],
            data["bitis_tarihi"],
            data["PDurumu"],
            pid
        )
        cursor.execute(sql, values)
        db.commit()
        return redirect("/projeler")

    cursor.execute("SELECT * FROM proje WHERE PID = %s", (pid,))
    p = cursor.fetchone()
    proje = {
        "PID": p[0],
        "PAdi": p[1],
        "baslangic_tarihi": p[2].strftime('%Y-%m-%d'),
        "bitis_tarihi": p[3].strftime('%Y-%m-%d'),
        "PDurumu": p[4]
    }
    return render_template("proje_duzenle.html", proje=proje)





@app.route("/proje_ekle", methods=["POST"])
def proje_ekle():
    data = request.get_json()

    sql = "INSERT INTO proje (PAdi, baslangic_tarihi, bitis_tarihi, PDurumu) VALUES (%s, %s, %s, %s)"
    values = (data["PAdi"], data["baslangic_tarihi"], data["bitis_tarihi"], data["PDurumu"])

    cursor.execute(sql, values)
    db.commit()

    return jsonify({"message": "Proje başarıyla eklendi!"})




@app.route("/proje_guncelle/<int:pid>", methods=["PUT"])
def proje_guncelle(pid):
    data = request.get_json()

    sql = """
        UPDATE proje 
        SET PAdi = %s, baslangic_tarihi = %s, bitis_tarihi = %s, PDurumu = %s
        WHERE PID = %s
    """
    values = (data["PAdi"], data["baslangic_tarihi"], data["bitis_tarihi"], data["PDurumu"], pid)

    cursor.execute(sql, values)
    db.commit()

    return jsonify({"message": f"{pid} ID'li proje güncellendi."})




@app.route("/proje_sil/<int:pid>", methods=["DELETE"])
def proje_sil(pid):
    cursor.execute("DELETE FROM proje WHERE PID = %s", (pid,))
    db.commit()

    return jsonify({"message": f"{pid} ID'li proje silindi."})







@app.route("/kaynak_ekle", methods=["POST"])
def kaynak_ekle():
    data = request.get_json()

    sql = """
        INSERT INTO kaynak (PID, tip, KAdi, miktar, KDurumu)
        VALUES (%s, %s, %s, %s, %s)
    """
    values = (
        data["PID"],
        data["tip"],
        data["KAdi"],
        data["miktar"],
        data["KDurumu"]
    )

    cursor.execute(sql, values)
    db.commit()

    return jsonify({"message": "Kaynak başarıyla eklendi!"})



@app.route("/kaynak_guncelle/<int:kaid>", methods=["PUT"])
def kaynak_guncelle(kaid):
    data = request.get_json()

    sql = """
        UPDATE kaynak 
        SET PID = %s, tip = %s, KAdi = %s, miktar = %s, KDurumu = %s
        WHERE KAID = %s
    """
    values = (
        data["PID"],
        data["tip"],
        data["KAdi"],
        data["miktar"],
        data["KDurumu"],
        kaid
    )

    cursor.execute(sql, values)
    db.commit()

    return jsonify({"message": f"{kaid} ID'li kaynak güncellendi."})



@app.route("/kaynak_sil/<int:kaid>", methods=["DELETE"])
def kaynak_sil(kaid):
    cursor.execute("DELETE FROM kaynak WHERE KAID = %s", (kaid,))
    db.commit()

    return jsonify({"message": f"{kaid} ID'li kaynak silindi."})




@app.route("/proje/<int:pid>/kaynaklar", methods=["GET", "POST"])
def proje_kaynaklar(pid):
    if "KID" not in session:
        return redirect("/login")

    if request.method == "POST":
        kaid = request.form.get("kaid")
        tarih = request.form.get("tarih")
        kullanilan_miktar = request.form.get("kullanilan_miktar")
        aciklama = request.form.get("aciklama")

        sql = """
            INSERT INTO kaynak_kullanim (KAID, tarih, kullanilan_miktar, aciklama)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(sql, (kaid, tarih, kullanilan_miktar, aciklama))
        db.commit()
        return redirect(f"/proje/{pid}/kaynaklar")

    # Proje bilgisi
    cursor.execute("SELECT * FROM proje WHERE PID = %s", (pid,))
    p = cursor.fetchone()
    proje = {
        "PID": p[0],
        "PAdi": p[1]
    }

    # Kaynaklar
    cursor.execute("SELECT * FROM kaynak WHERE PID = %s", (pid,))
    kaynaklar_raw = cursor.fetchall()
    kaynaklar = [{
        "KAID": k[0],
        "PID": k[1],
        "tip": k[2],
        "KAdi": k[3],
        "miktar": k[4],
        "KDurumu": k[5]
    } for k in kaynaklar_raw]

    # Kullanım geçmişi
    cursor.execute("""
        SELECT k.tarih, k.kullanilan_miktar, k.aciklama 
        FROM kaynak_kullanim k
        JOIN kaynak ka ON k.KAID = ka.KAID
        WHERE ka.PID = %s
        ORDER BY k.tarih DESC
    """, (pid,))
    kullanimlar = [{
        "tarih": row[0].strftime('%Y-%m-%d'),
        "kullanilan_miktar": row[1],
        "aciklama": row[2]
    } for row in cursor.fetchall()]

    return render_template("kaynak.html", proje=proje, kaynaklar=kaynaklar, kullanimlar=kullanimlar)





@app.route("/proje/<int:pid>/kaynak-planla", methods=["GET", "POST"])
def kaynak_planla(pid):
    if "KID" not in session or session["rol"] != "yönetici":
        return "Bu işlem sadece yöneticiler içindir.", 403

    if request.method == "POST":
        kaid = request.form["kaid"]
        miktar = request.form["planlanan_miktar"]

        # Planlama tablosuna ekle
        cursor.execute("""
            INSERT INTO proje_kaynak (PID, KAID, planlanan_miktar)
            VALUES (%s, %s, %s)
        """, (pid, kaid, miktar))
        db.commit()
        return redirect(f"/proje/{pid}/kaynak-detay")

    # Proje adını al
    cursor.execute("SELECT PAdi FROM proje WHERE PID = %s", (pid,))
    proje_adi = cursor.fetchone()[0]

    # Kaynak tanımlarını çek
    cursor.execute("SELECT KTipID, KAdi, tip FROM kaynak_tanim ORDER BY tip, KAdi")
    kaynaklar = cursor.fetchall()

    # Türlerine göre ayır
    malzeme = [ (k[0], k[1]) for k in kaynaklar if k[2] == "Malzeme" ]
    ekipman = [ (k[0], k[1]) for k in kaynaklar if k[2] == "Ekipman" ]
    personel = [ (k[0], k[1]) for k in kaynaklar if k[2] == "Personel" ]

    return render_template(
        "kaynak_planla.html",
        pid=pid,
        proje_adi=proje_adi,
        malzeme=malzeme,
        ekipman=ekipman,
        personel=personel
    )




@app.route("/kaynaklar")
def kaynaklar_sayfasi():
    if "KID" not in session:
        return redirect("/login")

    cursor.execute("SELECT * FROM proje")
    projeler = cursor.fetchall()
    proje_listesi = [{
        "PID": p[0],
        "PAdi": p[1],
        "baslangic_tarihi": p[2].strftime('%Y-%m-%d'),
        "bitis_tarihi": p[3].strftime('%Y-%m-%d'),
        "PDurumu": p[4]
    } for p in projeler]

    return render_template("kaynak_projeler.html", projeler=proje_listesi)





@app.route("/proje/<int:pid>/kaynak-detay", methods=["GET"])
def kaynak_detay(pid):
    if "KID" not in session:
        return redirect("/login")

    # Proje bilgisi
    cursor.execute("SELECT PAdi FROM proje WHERE PID = %s", (pid,))
    proje = cursor.fetchone()
    if not proje:
        return "Proje bulunamadı", 404

    proje_info = {"PID": pid, "PAdi": proje[0]}

    # Kullanım zaman çizelgesi (soldaki liste)
    cursor.execute("""
        SELECT kk.tarih, kt.KAdi, kk.kullanilan_miktar, kk.aciklama
        FROM kaynak_kullanim kk
        JOIN kaynak k ON kk.KAID = k.KAID
        JOIN kaynak_tanim kt ON k.KTipID = kt.KTipID
        WHERE k.PID = %s
        ORDER BY kk.tarih DESC
    """, (pid,))
    kullanimlar = [{
        "tarih": row[0].strftime('%Y-%m-%d'),
        "kaynagin_adi": row[1],
        "kullanilan_miktar": row[2],
        "aciklama": row[3]
    } for row in cursor.fetchall()]

    # Kaynak tanımları (sol kullanım için)
    cursor.execute("""
        SELECT KTipID, KAdi, tip
        FROM kaynak_tanim
        ORDER BY tip, KAdi
    """)
    kullanim_kaynaklar = [{
        "KTipID": row[0],
        "KAdi": row[1],
        "tip": row[2]
    } for row in cursor.fetchall()]

    # Sağdaki Planlama Karşılaştırması (planlanan, mevcut, fark)
    cursor.execute("""
        SELECT 
             kt.KAdi,
            SUM(pk.planlanan_miktar),
            COALESCE(SUM(kk.kullanilan_miktar), 0),
            kt.tip,
            (SUM(pk.planlanan_miktar) - COALESCE(SUM(kk.kullanilan_miktar), 0)) AS fark
        FROM proje_kaynak pk
        JOIN kaynak k ON pk.KAID = k.KAID
        JOIN kaynak_tanim kt ON k.KTipID = kt.KTipID
        LEFT JOIN kaynak_kullanim kk ON kk.PKID = pk.PKID
        WHERE pk.PID = %s
        GROUP BY kt.KAdi, kt.tip
        HAVING SUM(pk.planlanan_miktar) > 0
        ORDER BY FIELD(kt.tip, 'Malzeme', 'Ekipman', 'Personel'), kt.KAdi
    """, (pid,))



    planlamalar = [{
        "KAdi": row[0],
        "planlanan_miktar": row[1],
        "mevcut_miktar": row[2],
        "tip": row[3],
        "fark": row[4]
    } for row in cursor.fetchall()]

    return render_template(
        "kaynak_detay.html",
        proje=proje_info,
        kullanimlar=kullanimlar,
        kullanim_kaynaklar=kullanim_kaynaklar,
        planlama_kaynaklar=kullanim_kaynaklar,
        planlamalar=planlamalar
    )



"""
cursor.execute(""
        SELECT 
            kt.KAdi,
            SUM(pk.planlanan_miktar),
            COALESCE(SUM(kk.kullanilan_miktar), 0),
            kt.tip,
            (SUM(pk.planlanan_miktar) - COALESCE(SUM(kk.kullanilan_miktar), 0)) AS fark
        FROM proje_kaynak pk
        JOIN kaynak k ON pk.KAID = k.KAID
        JOIN kaynak_tanim kt ON k.KTipID = kt.KTipID
        LEFT JOIN kaynak_kullanim kk ON kk.PKID = pk.PKID
        WHERE pk.PID = %s
        GROUP BY kt.KAdi, kt.tip
        ORDER BY FIELD(kt.tip, 'Malzeme', 'Ekipman', 'Personel'), kt.KAdi
    "", (pid,))
"""
"""
cursor.execute(""
        SELECT 
            kt.KAdi,
            pk.planlanan_miktar,
            COALESCE(SUM(kk.kullanilan_miktar), 0) AS mevcut_miktar,
            kt.tip,
            (pk.planlanan_miktar - COALESCE(SUM(kk.kullanilan_miktar), 0)) AS fark
        FROM proje_kaynak pk
        JOIN kaynak k ON pk.KAID = k.KAID
        JOIN kaynak_tanim kt ON k.KTipID = kt.KTipID
        LEFT JOIN kaynak_kullanim kk ON kk.PKID = pk.PKID
        WHERE pk.PID = %s
        AND pk.planlanan_miktar > 0
        GROUP BY kt.KAdi, pk.planlanan_miktar, kt.tip
        ORDER BY FIELD(kt.tip, 'Malzeme', 'Ekipman', 'Personel'), kt.KAdi
    "", (pid,))
"""


@app.route("/proje/<int:pid>/kaynak-kullanim-ekle", methods=["POST"])
def kaynak_kullanim_ekle(pid):
    if "KID" not in session:
        return redirect("/login")

    kaid_tanim = request.form.get("kaid")
    tarih = request.form.get("tarih")
    kullanilan_miktar = request.form.get("kullanilan_miktar")
    aciklama = request.form.get("aciklama")

    if not kaid_tanim:
        return "Bir kaynak seçilmedi!", 400

    # Kaynak adı ve tipi alınıyor
    cursor.execute("SELECT KAdi, tip FROM kaynak_tanim WHERE KTipID = %s", (kaid_tanim,))
    kaynak_tanim = cursor.fetchone()
    if not kaynak_tanim:
        return "Kaynak bulunamadı!", 400

    kaynak_adi, kaynak_tipi = kaynak_tanim

    # kaynak tablosunda bu kaynak var mı kontrolü
    cursor.execute("""
        SELECT KAID FROM kaynak
        WHERE PID = %s AND KAdi = %s
    """, (pid, kaynak_adi))
    mevcut_kaynak = cursor.fetchone()

    if mevcut_kaynak:
        proje_kaynak_kaid = mevcut_kaynak[0]
    else:
        cursor.execute("""
            INSERT INTO kaynak (PID, KTipID, KAdi, miktar, KDurumu)
            VALUES (%s, %s, %s, 0, 'aktif')
        """, (pid, kaid_tanim, kaynak_adi))
        db.commit()
        proje_kaynak_kaid = cursor.lastrowid

    # proje_kaynak'ta var mı kontrolü
    cursor.execute("""
        SELECT PKID FROM proje_kaynak
        WHERE PID = %s AND KAID = %s
    """, (pid, proje_kaynak_kaid))
    proje_kaynak_kontrol = cursor.fetchone()

    if not proje_kaynak_kontrol:
        cursor.execute("""
            INSERT INTO proje_kaynak (PID, KAID, planlanan_miktar)
            VALUES (%s, %s, %s)
        """, (pid, proje_kaynak_kaid, "0"))
        db.commit()
        # yeni oluşturulan PKID'yi alalım
        proje_kaynak_pkid = cursor.lastrowid
    else:
        proje_kaynak_pkid = proje_kaynak_kontrol[0]

    # 🔥 HATA BURADA OLUYORDU: şimdi doğru PKID'yi ekliyoruz
    cursor.execute("""
        INSERT INTO kaynak_kullanim (KAID, tarih, kullanilan_miktar, aciklama, PKID)
        VALUES (%s, %s, %s, %s, %s)
    """, (proje_kaynak_kaid, tarih, kullanilan_miktar, aciklama, proje_kaynak_pkid))

    db.commit()

    return redirect(f"/proje/{pid}/kaynak-detay")








"""
@app.route("/proje/<int:pid>/kaynak-kullanim-ekle", methods=["POST"])
def kaynak_kullanim_ekle(pid):
    if "KID" not in session:
        return redirect("/login")

    kaid_tanim = request.form.get("kaid")
    tarih = request.form.get("tarih")
    kullanilan_miktar = request.form.get("kullanilan_miktar")
    aciklama = request.form.get("aciklama")

    if not kaid_tanim:
        return "Bir kaynak seçilmedi!", 400

    # kaynak_tanimdan kaynak adı ve tipi al
    cursor.execute("SELECT KAdi, tip FROM kaynak_tanim WHERE KTipID = %s", (kaid_tanim,))
    kaynak_tanim = cursor.fetchone()
    if not kaynak_tanim:
        return "Kaynak bulunamadı!", 400

    kaynak_adi, kaynak_tipi = kaynak_tanim

    # kaynak tablosunda var mı kontrol et
    cursor.execute(""
        SELECT KAID FROM kaynak
        WHERE PID = %s AND KAdi = %s
    "", (pid, kaynak_adi))
    mevcut_kaynak = cursor.fetchone()

    if mevcut_kaynak:
        proje_kaynak_kaid = mevcut_kaynak[0]
    else:
        cursor.execute(""
            INSERT INTO kaynak (PID, KTipID, KAdi, miktar, KDurumu)
            VALUES (%s, %s, %s, 0, 'aktif')
        "", (pid, kaid_tanim, kaynak_adi))

        db.commit()
        proje_kaynak_kaid = cursor.lastrowid

    # 🔥 Burada proje_kaynak tablosunda var mı kontrol ediyoruz
    cursor.execute(""
        SELECT 1 FROM proje_kaynak
        WHERE PID = %s AND KAID = %s
    "", (pid, proje_kaynak_kaid))
    proje_kaynak_kontrol = cursor.fetchone()

    if not proje_kaynak_kontrol:
        cursor.execute(""
            INSERT INTO proje_kaynak (PID, KAID, planlanan_miktar)
            VALUES (%s, %s, %s)
        "", (pid, proje_kaynak_kaid, "0"))

        db.commit()

    # Şimdi kullanım kaydını ekle
    cursor.execute(""
        INSERT INTO kaynak_kullanim (KAID, tarih, kullanilan_miktar, aciklama)
        VALUES (%s, %s, %s, %s)
    "", (proje_kaynak_kaid, tarih, kullanilan_miktar, aciklama))
    db.commit()

    return redirect(f"/proje/{pid}/kaynak-detay")
"""






























@app.route("/rapor_ekle", methods=["POST"])
def rapor_ekle():
    data = request.get_json()

    sql = """
        INSERT INTO rapor (PID, KID, RTarihi, aciklama)
        VALUES (%s, %s, %s, %s)
    """
    values = (
        data["PID"],
        data["KID"],
        data["RTarihi"],
        data["aciklama"]
    )

    cursor.execute(sql, values)
    db.commit()

    return jsonify({"message": "Rapor başarıyla eklendi!"})




@app.route("/rapor_sil/<int:rid>", methods=["DELETE"])
def rapor_sil(rid):
    cursor.execute("DELETE FROM rapor WHERE RID = %s", (rid,))
    db.commit()

    return jsonify({"message": f"{rid} ID'li rapor silindi."})





@app.route("/raporlar")
def raporlar():
    if "KID" not in session:
        return redirect("/login")

    # Tüm projeleri çekelim
    cursor.execute("SELECT PID, PAdi, baslangic_tarihi, bitis_tarihi, PDurumu FROM proje")
    projeler = [{
        "PID": row[0],
        "PAdi": row[1],
        "baslangic": row[2].strftime("%Y-%m-%d"),
        "bitis": row[3].strftime("%Y-%m-%d"),
        "durum": row[4]
    } for row in cursor.fetchall()]

    return render_template("raporlar.html", projeler=projeler)





@app.route("/rapor/<int:pid>")
def rapor_goruntule(pid):
    if "KID" not in session:
        return redirect("/login")

    # 1. Proje Bilgileri
    cursor.execute("""
        SELECT PAdi, baslangic_tarihi, bitis_tarihi, PDurumu, Aciklama
        FROM proje
        WHERE PID = %s
    """, (pid,))
    proje_row = cursor.fetchone()
    if not proje_row:
        return "Proje bulunamadı", 404

    proje = {
    "PID": pid,  # <-- Bunu EKLE!
    "PAdi": proje_row[0],
    "baslangic": proje_row[1].strftime("%Y-%m-%d"),
    "bitis": proje_row[2].strftime("%Y-%m-%d"),
    "durum": proje_row[3],
    "aciklama": proje_row[4] if proje_row[4] else ""
}


    # 2. Aşamalar
    cursor.execute("""
        SELECT tarih, aciklama, ekleyen_ad, ekleyen_rol, onaylayan_ad, onaylayan_rol
        FROM proje_asama
        WHERE PID = %s
        ORDER BY tarih
    """, (pid,))
    asamalar = []
    for row in cursor.fetchall():
        asamalar.append({
            "tarih": row[0].strftime("%Y-%m-%d"),
            "aciklama": row[1],
            "ekleyen_ad": row[2],
            "ekleyen_rol": row[3],
            "onaylayan_ad": row[4],
            "onaylayan_rol": row[5]
        })

    # 3. Kullanım Zaman Çizelgesi
    cursor.execute("""
        SELECT kk.tarih, kt.KAdi, kk.kullanilan_miktar, kk.aciklama
        FROM kaynak_kullanim kk
        JOIN kaynak k ON kk.KAID = k.KAID
        JOIN kaynak_tanim kt ON k.KTipID = kt.KTipID
        WHERE k.PID = %s
        ORDER BY kk.tarih
    """, (pid,))
    kullanimlar = []
    for row in cursor.fetchall():
        kullanimlar.append({
            "tarih": row[0].strftime("%Y-%m-%d"),
            "kaynagin_adi": row[1],
            "kullanilan_miktar": row[2],
            "aciklama": row[3]
        })

    # 4. Planlanan vs Mevcut Kaynaklar
    cursor.execute("""
    SELECT 
        kt.KAdi,
        SUM(pk.planlanan_miktar),
        COALESCE(SUM(kk.kullanilan_miktar), 0),
        kt.tip,
        (SUM(pk.planlanan_miktar) - COALESCE(SUM(kk.kullanilan_miktar), 0)) AS fark
    FROM proje_kaynak pk
    JOIN kaynak k ON pk.KAID = k.KAID
    JOIN kaynak_tanim kt ON k.KTipID = kt.KTipID
    LEFT JOIN kaynak_kullanim kk ON kk.PKID = pk.PKID
    WHERE pk.PID = %s
    GROUP BY kt.KAdi, kt.tip
    HAVING SUM(pk.planlanan_miktar) > 0
    ORDER BY FIELD(kt.tip, 'Malzeme', 'Ekipman', 'Personel'), kt.KAdi
""", (pid,))

    planlamalar = [{
    "KAdi": row[0],
    "planlanan_miktar": row[1],
    "mevcut_miktar": row[2],
    "tip": row[3],
    "fark": row[4]
} for row in cursor.fetchall()]


    return render_template(
        "rapor.html",
        proje=proje,
        asamalar=asamalar,
        kullanimlar=kullanimlar,
        planlamalar=planlamalar
    )







# pdfkit ayarı (wkhtmltopdf yolu)
path_wkhtmltopdf = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)








@app.route("/rapor/<int:pid>/pdf")
def rapor_pdf_indir(pid):
    if "KID" not in session:
        return redirect("/login")

    # --- Proje Bilgileri
    cursor.execute("""
        SELECT PAdi, baslangic_tarihi, bitis_tarihi, PDurumu, Aciklama
        FROM proje
        WHERE PID = %s
    """, (pid,))
    proje_row = cursor.fetchone()
    if not proje_row:
        return "Proje bulunamadı", 404

    proje = {
        "PID": pid,
        "PAdi": proje_row[0],
        "baslangic": proje_row[1].strftime("%Y-%m-%d"),
        "bitis": proje_row[2].strftime("%Y-%m-%d"),
        "durum": proje_row[3],
        "aciklama": proje_row[4] if proje_row[4] else ""
    }

    # --- Aşamalar
    cursor.execute("""
        SELECT tarih, aciklama, ekleyen_ad, ekleyen_rol, onaylayan_ad, onaylayan_rol
        FROM proje_asama
        WHERE PID = %s
        ORDER BY tarih
    """, (pid,))
    asamalar = [{
        "tarih": row[0].strftime("%Y-%m-%d"),
        "aciklama": row[1],
        "ekleyen_ad": row[2],
        "ekleyen_rol": row[3],
        "onaylayan_ad": row[4],
        "onaylayan_rol": row[5]
    } for row in cursor.fetchall()]

    # --- Kullanım Zaman Çizelgesi
    cursor.execute("""
        SELECT kk.tarih, kt.KAdi, kk.kullanilan_miktar, kk.aciklama
        FROM kaynak_kullanim kk
        JOIN kaynak k ON kk.KAID = k.KAID
        JOIN kaynak_tanim kt ON k.KTipID = kt.KTipID
        WHERE k.PID = %s
        ORDER BY kk.tarih
    """, (pid,))
    kullanimlar = [{
        "tarih": row[0].strftime("%Y-%m-%d"),
        "kaynagin_adi": row[1],
        "kullanilan_miktar": row[2],
        "aciklama": row[3]
    } for row in cursor.fetchall()]

    # --- Planlanan vs Mevcut
    cursor.execute("""
    SELECT 
        kt.KAdi,
        SUM(pk.planlanan_miktar) AS planlanan_miktar,
        COALESCE(SUM(kk.kullanilan_miktar), 0) AS mevcut_miktar,
        kt.tip,
        (SUM(pk.planlanan_miktar) - COALESCE(SUM(kk.kullanilan_miktar), 0)) AS fark
    FROM proje_kaynak pk
    JOIN kaynak k ON pk.KAID = k.KAID
    JOIN kaynak_tanim kt ON k.KTipID = kt.KTipID
    LEFT JOIN kaynak_kullanim kk ON kk.PKID = pk.PKID
    WHERE pk.PID = %s
    GROUP BY kt.KAdi, kt.tip
    HAVING SUM(pk.planlanan_miktar) > 0
    ORDER BY FIELD(kt.tip, 'Malzeme', 'Ekipman', 'Personel'), kt.KAdi
""", (pid,))






    planlamalar = [{
        "KAdi": row[0],
        "planlanan_miktar": row[1],
        "mevcut_miktar": row[2],
        "fark": float(row[1]) - float(row[2]),
        "tip": row[3]
    } for row in cursor.fetchall()]




    # --- HTML render
    rendered = render_template(
        "rapor_pdf.html",
        proje=proje,
        asamalar=asamalar,
        kullanimlar=kullanimlar,
        planlamalar=planlamalar
    )

    # --- PDF oluştur
    pdf = pdfkit.from_string(rendered, False, configuration=config)

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=proje_{pid}_raporu.pdf'
    return response







def extract_number(text):
    match = re.search(r"(\d+(\.\d+)?)", str(text))
    return float(match.group(1)) if match else 0.0





@app.route("/asama_ekle_api", methods=["POST"])
def asama_ekle_api():
    if "KID" not in session:
        return redirect("/login")

    data = request.get_json()

    sql = """
        INSERT INTO proje_asama (PID, tarih, aciklama, ekleyen_ad, ekleyen_rol, onaylayan_ad, onaylayan_rol)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    values = (
        data["PID"],
        data["tarih"],
        data["aciklama"],
        data["ekleyen_ad"],
        data["ekleyen_rol"],
        data.get("onaylayan_ad"),
        data.get("onaylayan_rol")
    )

    cursor.execute(sql, values)
    db.commit()

    return jsonify({"message": "Aşama başarıyla eklendi!"})




@app.route("/kullanicilar")
def kullanicilar():
    if "KID" not in session:
        return redirect("/login")

    cursor.execute("SELECT KID, KAdi, email, rol FROM kullanici")
    kullanicilar = [{
        "KID": row[0],
        "KAdi": row[1],
        "email": row[2],
        "rol": row[3]
    } for row in cursor.fetchall()]

    return render_template("kullanicilar.html", kullanicilar=kullanicilar)

"""
@app.route("/kullanicilar")
def kullanicilar():
    if "KID" not in session:
        return redirect("/login")

    cursor.execute("SELECT KID, KAdi, email, rol FROM kullanici")
    kullanicilar = [{
        "KID": row[0],
        "KAdi": row[1],
        "email": row[2],
        "rol": row[3]
    } for row in cursor.fetchall()]

    return render_template("kullanicilar.html", kullanicilar=kullanicilar)
"""







@app.route("/kullanici_ekle", methods=["GET", "POST"])
def kullanici_ekle():
    if "KID" not in session:
        return redirect("/login")

    if request.method == "POST":
        ad = request.form.get("ad")
        email = request.form.get("email")
        sifre = request.form.get("sifre")
        rol = request.form.get("rol")

        sql = "INSERT INTO kullanici (KAdi, email, sifre, rol) VALUES (%s, %s, %s, %s)"
        cursor.execute(sql, (ad, email, sifre, rol))
        db.commit()
        return redirect("/kullanicilar")

    return render_template("kullanici_ekle.html")








@app.route("/kullanici_sil/<int:kid>", methods=["POST"])
def kullanici_sil(kid):
    if "KID" not in session:
        return redirect("/login")

    cursor.execute("DELETE FROM kullanici WHERE KID = %s", (kid,))
    db.commit()
    return redirect("/kullanicilar")






@app.route("/kullanici_duzenle/<int:kid>", methods=["GET", "POST"])
def kullanici_duzenle(kid):
    if "KID" not in session:
        return redirect("/login")

    if request.method == "POST":
        ad = request.form.get("ad")
        email = request.form.get("email")
        sifre = request.form.get("sifre")
        rol = request.form.get("rol")

        sql = "UPDATE kullanici SET KAdi = %s, email = %s, sifre = %s, rol = %s WHERE KID = %s"
        cursor.execute(sql, (ad, email, sifre, rol, kid))
        db.commit()
        return redirect("/kullanicilar")

    cursor.execute("SELECT KAdi, email, sifre, rol FROM kullanici WHERE KID = %s", (kid,))  # << BURADA KAdi doğru
    row = cursor.fetchone()
    if not row:
        return "Kullanıcı bulunamadı", 404

    kullanici = {
        "KAdi": row[0],   
        "email": row[1],
        "sifre": row[2],
        "rol": row[3]
    }


    return render_template("kullanici_duzenle.html", kullanici=kullanici, KID=kid)















@app.route("/kayit", methods=["GET", "POST"])
def kayit():
    if request.method == "POST":
        data = request.form

        if data["sifre"] != data["sifre_tekrar"]:
            return render_template("kayit.html", hata="Şifreler eşleşmiyor!")

        # Kullanıcının gönderdiği "rol" yerine sabit olarak 'çalışan' atanıyor
        sql = "INSERT INTO kullanici (KAdi, email, sifre, rol) VALUES (%s, %s, %s, %s)"
        values = (data["adsoyad"], data["email"], data["sifre"], "çalışan")
        try:
            cursor.execute(sql, values)
            db.commit()
            return redirect("/login")
        except Exception as e:
            return render_template("kayit.html", hata="Veritabanı hatası: " + str(e))

    return render_template("kayit.html")




@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")



@app.route("/sifremi-unuttum", methods=["GET", "POST"])
def sifremi_unuttum():
    if request.method == "POST":
        email = request.form["email"]

        # Veritabanında e-posta var mı kontrol et
        cursor.execute("SELECT * FROM kullanici WHERE email = %s", (email,))
        kullanici = cursor.fetchone()

        if kullanici:
            token = sifre_token_uretecisi.dumps(email, salt="sifre-salt")
            sifre_sifirlama_maili_gonder(email, token)
            mesaj = "Şifre sıfırlama bağlantısı e-posta adresinize gönderildi."
        else:
            mesaj = "Bu e-posta adresiyle kayıtlı kullanıcı bulunamadı."

        return render_template("sifremi_unuttum.html", mesaj=mesaj)

    return render_template("sifremi_unuttum.html")




@app.route("/sifre-sifirla/<token>", methods=["GET", "POST"])
def sifre_sifirla(token):
    try:
        email = sifre_token_uretecisi.loads(token, salt="sifre-salt", max_age=1800)  # 30 dakika geçerli
    except SignatureExpired:
        return "🔐 Bağlantı süresi dolmuş. Lütfen yeniden talep edin."
    except BadSignature:
        return "❌ Geçersiz bağlantı. Güvenlik nedeniyle işlem yapılamıyor."

    if request.method == "POST":
        yeni_sifre = request.form["sifre"]
        sifre_tekrar = request.form["sifre_tekrar"]

        if yeni_sifre != sifre_tekrar:
            return render_template("sifre_sifirla.html", hata="Şifreler eşleşmiyor!", email=email)

        # Şifreyi güncelle
        sql = "UPDATE kullanici SET sifre = %s WHERE email = %s"
        cursor.execute(sql, (yeni_sifre, email))
        db.commit()

        return redirect("/login")

    return render_template("sifre_sifirla.html", email=email)





def sifre_sifirlama_maili_gonder(email, token):
    reset_link = f"http://127.0.0.1:5000/sifre-sifirla/{token}"
    
    subject = "Şifre Sıfırlama Talebi"
    body = f"""
Merhaba,

Şifrenizi sıfırlamak için aşağıdaki bağlantıya tıklayın:
{reset_link}

Eğer bu talebi siz oluşturmadıysanız, bu e-postayı yok sayabilirsiniz.

Demir İnşaat
    """

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, app_password)
            server.sendmail(sender_email, email, message.as_string())
            print("E-posta gönderildi.")
    except Exception as e:
        print("E-posta gönderilemedi:", e)


if __name__ == "__main__":
    app.run(debug=True)

import io

from openpyxl import load_workbook

CSV = ("Ticaret Unvanı;İlçe;Faaliyet Konusu;Kurumsal Telefon;Şirket Türü\n"
       "KURGU API İNŞAAT LTD. ŞTİ.;Sincan;İnşaat taahhüt;0312 555 00 01;\n"
       "KURGU API YAZILIM A.Ş.;Çankaya;Yazılım geliştirme;;\n")


def _import(client, h, content=CSV, name="liste.csv"):
    return client.post("/api/imports", headers=h, files={"file": (name, content.encode("utf-8"), "text/csv")},
                       data={"declared_establishment": "true"})


def test_auth_and_rbac(client, viewer_h):
    assert client.get("/api/businesses").status_code == 401
    assert client.post("/api/auth/login", json={"email": "admin@test.local", "password": "yanlis"}).status_code == 401
    assert client.get("/api/businesses", headers=viewer_h).status_code == 200
    r = _import(client, viewer_h)
    assert r.status_code == 403


def test_import_list_filter_detail(client, sales_h):
    r = _import(client, sales_h)
    assert r.status_code == 200, r.text
    assert r.json()["stats"]["created"] == 2
    assert _import(client, sales_h).status_code == 409  # aynı dosya
    lst = client.get("/api/businesses", headers=sales_h).json()
    assert lst["total"] == 2
    assert client.get("/api/businesses?district=Sincan", headers=sales_h).json()["total"] == 1
    assert client.get("/api/businesses?has_contact=true", headers=sales_h).json()["total"] == 1
    assert client.get("/api/businesses?company_type=AS", headers=sales_h).json()["total"] == 1
    assert client.get("/api/businesses?q=yazilim", headers=sales_h).json()["total"] == 1
    bid = lst["items"][0]["id"]
    d = client.get(f"/api/businesses/{bid}", headers=sales_h).json()
    assert d["source"]["key"] == "manual_import" and d["verified_at"]
    assert len(d["opportunity_list"]) == 2


def test_crm_flow_quote_and_exports(client, sales_h, admin_h):
    _import(client, sales_h)
    item = client.get("/api/businesses?q=insaat", headers=sales_h).json()["items"][0]
    bid = item["id"]
    # analiz
    a = client.post(f"/api/businesses/{bid}/analyze?use_llm=false", headers=sales_h).json()
    assert a["isg_score"] is not None and a["analysis"]["isg"]["factors"]
    # İYS kontrolü yapılmadan e-posta kanalı engellenir
    oc = client.get(f"/api/businesses/{bid}/outreach-check?channel=email", headers=sales_h).json()
    assert oc["allowed"] is False
    client.post(f"/api/businesses/{bid}/compliance", headers=sales_h, json={"iys_status": "engel_yok"})
    oc = client.get(f"/api/businesses/{bid}/outreach-check?channel=phone", headers=sales_h).json()
    assert oc["allowed"] is True
    opp = item["opportunities"]["isg"]["id"]
    r = client.patch(f"/api/opportunities/{opp}", headers=sales_h,
                     json={"stage": "ilk_gorusme", "next_action": "Teklif hazırla", "next_action_date": "2026-11-10"})
    assert r.status_code == 200 and r.json()["stage"] == "ilk_gorusme"
    r = client.post(f"/api/businesses/{bid}/activities", headers=sales_h,
                    json={"type": "call", "content": "Yetkiliyle görüşüldü", "opportunity_id": opp,
                          "follow_up_date": "2026-11-06"})
    assert r.status_code == 200
    assert client.get("/api/reminders?days=30", headers=sales_h).json()
    q = client.post(f"/api/opportunities/{opp}/quotes", headers=sales_h, json={
        "title": "OSGB Hizmeti", "items": [{"description": "İş güvenliği uzmanlığı (aylık)", "quantity": 12,
                                            "unit": "Ay", "unit_price": 2500, "vat_rate": 20}]}).json()
    assert q["total"] == 36000.0 and q["number"].startswith("TKL-")
    pdf = client.get(f"/api/quotes/{q['id']}/pdf", headers=sales_h)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    client.patch(f"/api/quotes/{q['id']}", headers=sales_h, json={"status": "gonderildi"})
    d = client.get(f"/api/businesses/{bid}", headers=sales_h).json()
    assert d["sales_status"] == "teklif_gonderildi"
    m = client.get("/api/dashboard", headers=sales_h).json()["metrics"]
    assert m["quoted"] == 1 and m["total_active"] == 2 and m["today_detected"] == 2
    x = client.get("/api/exports/businesses.xlsx?district=Sincan", headers=sales_h)
    wb = load_workbook(io.BytesIO(x.content))
    rows = list(wb.active.iter_rows(values_only=True))
    assert len(rows) == 2 and rows[1][0] == "KURGU API İNŞAAT LTD. ŞTİ."
    assert "Bulunamadı" in rows[1]  # e-posta bulunamadı
    p = client.get("/api/exports/businesses.pdf", headers=sales_h)
    assert p.content[:4] == b"%PDF"
    audit = client.get("/api/audit", headers=admin_h).json()
    assert any(e["action"] == "export" for e in audit)


def test_review_queue_and_kvkk(client, sales_h, admin_h):
    pdf_like = "Ticaret Unvanı;İlan Türü\nKURGU BELİRSİZ LTD. ŞTİ.;\n"
    r = client.post("/api/imports", headers=sales_h,
                    files={"file": ("x.csv", pdf_like.encode(), "text/csv")}, data={"declared_establishment": "false"})
    assert r.json()["stats"].get("needs_review") == 1
    q = client.get("/api/review", headers=sales_h).json()
    assert len(q) == 1
    r = client.post(f"/api/review/{q[0]['id']}/approve", headers=sales_h, json={"fields": {"district": "Mamak"}})
    assert r.status_code == 200, r.text
    bid = r.json()["id"]
    assert r.json()["verification_status"] == "manuel_dogrulandi"
    assert client.post(f"/api/businesses/{bid}/kvkk/anonymize", headers=sales_h).status_code == 403
    r = client.post(f"/api/businesses/{bid}/kvkk/anonymize", headers=admin_h)
    assert r.json()["do_not_contact"] is True and r.json()["anonymized_at"]


def test_sources_and_coverage(client, admin_h):
    s = client.get("/api/sources", headers=admin_h).json()
    keys = {x["key"]: x for x in s}
    assert keys["ttsg_web"]["kind"] == "reference" and "CAPTCHA" in keys["ttsg_web"]["access_notes"]
    r = client.patch(f"/api/sources/{keys['mersis']['id']}", headers=admin_h, json={"enabled": True})
    assert r.status_code == 400
    cov = client.get("/api/coverage", headers=admin_h).json()
    assert cov and all(c["status"] == "not_scanned" for c in cov)

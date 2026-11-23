"""Değiştirilebilir LLM sağlayıcı katmanı.

LLM, kural tabanlı analizi DESTEKLER; doğrulanmış verileri değiştirmez. Çıktısı her zaman
'tahmini' olarak etiketlenir ve puanlara en fazla ±10 düzeltme uygulayabilir.
Sağlayıcı yoksa veya çağrı başarısız olursa sistem yalnızca kural motoruyla çalışır.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Protocol

from app.config import settings
from app.models import Business

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Türkiye'de yeni kurulan işletmeleri satış ekibi için değerlendiren bir analistsin. İki hizmet hattı var: "
    "(1) İş Sağlığı ve Güvenliği (OSGB, iş güvenliği uzmanlığı, işyeri hekimliği, risk değerlendirmesi, eğitimler), "
    "(2) Yazılım ve dijital çözümler (web sitesi, e-ticaret, CRM/ERP, otomasyon, yapay zekâ entegrasyonu). "
    "Yalnızca verilen bilgilere dayan. Çalışan sayısı, mevcut hizmet sağlayıcısı veya web varlığı hakkında "
    "verilmeyen bilgileri kesinmiş gibi yazma; çıkarımları 'tahmini' olarak ifade et. Kural motorunun puanını "
    "yalnızca güçlü bir gerekçe varsa en fazla ±10 puan düzelt; aksi halde 0 ver. Türkçe yaz."
)

OUTPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "2-3 cümlelik satış özeti"},
        "likely_activity": {"type": "string", "description": "Faaliyetin sade açıklaması (tahmini)"},
        "isg_adjustment": {
            "type": "object",
            "properties": {"points": {"type": "integer"}, "reason": {"type": "string"}},
            "required": ["points", "reason"], "additionalProperties": False,
        },
        "software_adjustment": {
            "type": "object",
            "properties": {"points": {"type": "integer"}, "reason": {"type": "string"}},
            "required": ["points", "reason"], "additionalProperties": False,
        },
        "talking_points": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"},
                           "description": "Görüşmede doğrulanması gereken bilgiler"},
    },
    "required": ["summary", "likely_activity", "isg_adjustment", "software_adjustment", "talking_points",
                 "open_questions"],
    "additionalProperties": False,
}


class LLMProvider(Protocol):
    name: str

    def analyze(self, prompt: str) -> Optional[Dict[str, Any]]: ...


class AnthropicProvider:
    name = "anthropic"

    def __init__(self) -> None:
        import anthropic
        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY) if settings.ANTHROPIC_API_KEY \
            else anthropic.Anthropic()

    def analyze(self, prompt: str) -> Optional[Dict[str, Any]]:
        a = self._anthropic
        kwargs: Dict[str, Any] = dict(
            model=settings.LLM_MODEL,
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": settings.LLM_EFFORT, "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        )
        try:
            if settings.LLM_REFUSAL_FALLBACK:
                resp = self.client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
            else:
                resp = self.client.messages.create(**kwargs)
        except a.RateLimitError as exc:
            log.warning("LLM hız limiti: %s", exc)
            return None
        except a.APIStatusError as exc:
            log.warning("LLM API hatası (%s): %s", exc.status_code, exc)
            return None
        except a.APIConnectionError as exc:
            log.warning("LLM bağlantı hatası: %s", exc)
            return None
        if resp.stop_reason == "refusal":
            log.info("LLM isteği reddetti; kural tabanlı analiz kullanılacak")
            return None
        if resp.stop_reason == "max_tokens":
            log.warning("LLM yanıtı kesildi (max_tokens)")
            return None
        text = next((blk.text for blk in resp.content if getattr(blk, "type", None) == "text"), None)
        if not text:
            return None
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        data["_model"] = getattr(resp, "model", settings.LLM_MODEL)
        return data


_provider: Optional[LLMProvider] = None
_provider_loaded = False


def get_provider() -> Optional[LLMProvider]:
    global _provider, _provider_loaded
    if _provider_loaded:
        return _provider
    _provider_loaded = True
    if settings.LLM_PROVIDER == "anthropic":
        try:
            _provider = AnthropicProvider()
        except Exception as exc:  # paket/kimlik eksik
            log.warning("LLM sağlayıcı başlatılamadı: %s", exc)
            _provider = None
    return _provider


def set_provider(p: Optional[LLMProvider]) -> None:
    """Testler ve alternatif sağlayıcılar için."""
    global _provider, _provider_loaded
    _provider, _provider_loaded = p, True


def build_prompt(b: Business, cls: Dict, isg: Dict, sw: Dict) -> str:
    facts = {
        "ticaret_unvani": b.trade_name,
        "sirket_turu": b.company_type,
        "ilce": b.district,
        "adres": b.address,
        "faaliyet_konusu": (b.activity_text or "")[:3000] or None,
        "nace_kodu": b.nace_code,
        "nace_resmi_kaynaktan_dogrulandi": b.nace_verified,
        "sermaye_tl": str(b.capital) if b.capital is not None else None,
        "kurulus_tarihi": b.establishment_date.isoformat() if b.establishment_date else None,
        "tahmini_sektor": cls["sector_label"],
        "tehlike_sinifi": cls["hazard_class"],
        "tehlike_sinifi_dayanagi": cls["hazard_basis"],
        "web_sitesi_bulundu_mu": any(c.type == "website" and c.status != "reddedildi" for c in b.contacts),
        "iletisim_arastirmasi": b.enrichment_status,
    }
    return (
        "Aşağıdaki işletmeyi değerlendir. Kural motoru puanları: İSG="
        f"{isg['score']}, Yazılım={sw['score']}.\n\n<isletme>\n"
        + json.dumps(facts, ensure_ascii=False, indent=2)
        + "\n</isletme>\n\nKural motoru faktörleri:\n"
        + json.dumps({"isg": isg["factors"], "yazilim": sw["factors"]}, ensure_ascii=False)
    )


def refine(b: Business, cls: Dict, isg: Dict, sw: Dict) -> Optional[Dict[str, Any]]:
    p = get_provider()
    if not p:
        return None
    try:
        return p.analyze(build_prompt(b, cls, isg, sw))
    except Exception as exc:  # LLM hatası analizi durdurmaz
        log.warning("LLM analizi başarısız: %s", exc)
        return None

from __future__ import annotations

from datetime import datetime, timedelta
from math import sqrt

from sqlalchemy import func, select

from app.intelligence.fundamental_intelligence import FundamentalIntelligence
from app.intelligence.global_intelligence import aggregate_global_impact, detect_global_signals, sector_tags_for
from app.models.alert import OpportunityAlert
from app.models.event import MarketEvent
from app.models.fundamentals import CompanyFundamentals
from app.models.market_data import MarketData
from app.models.ml_prediction import MLPrediction
from app.models.news import NewsArticle
from app.models.stock import Stock


class RecommendationEngine:
    """Produce a small evidence-backed shortlist from alerts and the wider stock universe."""

    @staticmethod
    def build(db, limit: int = 5) -> list[dict]:
        recommendations = []
        seen = set()
        now = datetime.utcnow()
        cutoff = now - timedelta(days=14)
        # Detect global macro signals (Fed, crude, China, geopolitics, etc.) once per
        # build so every stock is scored against the same read of world conditions,
        # instead of re-scanning news per stock.
        global_impacts = RecommendationEngine._global_sector_impacts(db, cutoff)
        alerts = db.scalars(select(OpportunityAlert).where(OpportunityAlert.action.in_(["BUY", "WATCH"])).order_by(OpportunityAlert.opportunity_score.desc(), OpportunityAlert.created_at.desc()).limit(100)).all()
        for alert in alerts:
            if alert.symbol in seen: continue
            item = RecommendationEngine._from_stock(db, alert.symbol, alert=alert, cutoff=cutoff, global_impacts=global_impacts)
            if item:
                recommendations.append(item); seen.add(alert.symbol)
            if len(recommendations) >= limit: return RecommendationEngine._rank(recommendations)[:limit]
        recent_events = db.scalars(select(MarketEvent).where(MarketEvent.event_date >= cutoff).order_by(MarketEvent.event_date.desc()).limit(300)).all()
        recent_sectors = {str(e.sector).strip().upper() for e in recent_events if e.sector}
        stocks = db.scalars(select(Stock).where(Stock.is_active.is_(True)).order_by(Stock.symbol).limit(300)).all()
        fallback = []
        for stock in stocks:
            if stock.symbol in seen: continue
            item = RecommendationEngine._from_stock(db, stock.symbol, recent_sectors=recent_sectors, cutoff=cutoff, global_impacts=global_impacts)
            if item and item["score"] >= 30: fallback.append(item)
        fallback.sort(key=lambda x: (-x["score"], x["symbol"]))
        recommendations.extend(fallback[: max(0, limit - len(recommendations))])
        if not recommendations and stocks:
            best = None
            for stock in stocks:
                item = RecommendationEngine._from_stock(db, stock.symbol, recent_sectors=recent_sectors, cutoff=cutoff, global_impacts=global_impacts)
                if item and (best is None or item["score"] > best["score"]): best = item
            if best: recommendations.append(best)
        return RecommendationEngine._rank(recommendations)[:limit]

    @staticmethod
    def _global_sector_impacts(db, cutoff) -> dict:
        """Scan recently ingested news for global macro signals and return sector -> impact."""
        try:
            articles = db.scalars(
                select(NewsArticle).where(NewsArticle.created_at >= cutoff).order_by(NewsArticle.created_at.desc()).limit(300)
            ).all()
            signals = detect_global_signals(articles)
            aggregate = aggregate_global_impact(signals)
            return {item["sector"]: item for item in aggregate.get("sector_impacts", [])}
        except Exception:
            # Global intelligence is an enrichment layer; a failure here must never
            # break recommendation generation.
            return {}

    @staticmethod
    def _from_stock(db, symbol: str, alert=None, recent_sectors=None, cutoff=None, global_impacts=None):
        cutoff = cutoff or (datetime.utcnow() - timedelta(days=14))
        stock = db.scalar(select(Stock).where(Stock.symbol == symbol))
        if not stock: return None
        event = None; news = None
        if alert:
            event = db.scalar(select(MarketEvent).where(MarketEvent.id == alert.event_id))
            if event and event.news_id: news = db.scalar(select(NewsArticle).where(NewsArticle.id == event.news_id))
        if not event:
            sector = (stock.sector or "").strip().upper()
            events = db.scalars(select(MarketEvent).where(MarketEvent.event_date >= cutoff, MarketEvent.sector.is_not(None)).order_by(MarketEvent.event_date.desc()).limit(300)).all()
            event = next((e for e in events if str(e.sector).strip().upper() == sector), None)
            if event and event.news_id: news = db.scalar(select(NewsArticle).where(NewsArticle.id == event.news_id))

        fundamentals = db.scalar(select(CompanyFundamentals).where(CompanyFundamentals.stock_id == stock.id))
        prediction = db.scalar(select(MLPrediction).where(MLPrediction.stock_id == stock.id).order_by(MLPrediction.prediction_time.desc()))
        market = RecommendationEngine._market_stats(db, stock.id)
        current_price = market.get("current_price") or (prediction.price_at_prediction if prediction else None)
        if current_price is None: return None
        expected_5d = prediction.predicted_return_5d if prediction else None
        expected_20d = prediction.predicted_return_20d if prediction else None
        fundamental_assessment = FundamentalIntelligence.assess(fundamentals)
        fundamental_score = fundamental_assessment.score
        intelligence_score = float(alert.opportunity_score) if alert else RecommendationEngine._sector_intelligence_score(event, news, recent_sectors, stock)
        model_score = RecommendationEngine._model_score(prediction)
        market_score = RecommendationEngine._market_score(market)
        evidence_score = RecommendationEngine._evidence_score(db, event, news, stock.sector, cutoff)
        global_assessment = RecommendationEngine._global_assessment(global_impacts, stock.sector)
        global_score = global_assessment["score"]
        composite = round(min(100, 0.36 * intelligence_score + 0.19 * fundamental_score + 0.17 * model_score + 0.11 * market_score + 0.09 * evidence_score + 0.08 * global_score), 1)
        priority = RecommendationEngine._priority(composite, intelligence_score, fundamental_score, model_score, evidence_score)
        risk = (alert.risk if alert else RecommendationEngine._risk(market, fundamentals)) or "MEDIUM"
        entry_low, entry_high = RecommendationEngine._entry_zone(current_price, market, risk)
        action = "BUY" if alert and alert.action == "BUY" and composite >= 65 else "WATCH"
        fundamental_payload = RecommendationEngine._fundamentals(fundamentals)
        fundamental_payload["intelligence"] = fundamental_assessment.as_dict()
        return {
            "rank": 0, "symbol": stock.symbol, "company": stock.company_name or stock.symbol,
            "sector": stock.sector or (fundamentals.sector if fundamentals else None) or (event.sector if event else None),
            "action": action, "priority": priority,
            "priority_label": {"HIGH": "High priority", "MEDIUM": "Medium priority", "LOW": "Low priority"}[priority],
            "score": composite, "confidence": float(alert.confidence) if alert else round(min(0.85, max(0.30, composite / 100)), 3),
            "risk": risk, "horizon": (alert.expected_horizon if alert else None) or (event.time_horizon if event else "2–6 weeks"),
            "current_price": current_price, "entry_low": entry_low, "entry_high": entry_high,
            "predicted_5d": expected_5d, "predicted_20d": expected_20d, "model_signal": prediction.signal if prediction else None,
            "reason": alert.reason if alert else RecommendationEngine._fallback_reason(event, fundamentals, prediction, market),
            "thesis": alert.title if alert else (event.title if event else f"{stock.company_name or stock.symbol}: multi-factor setup"),
            "why_now": RecommendationEngine._why_now(alert, prediction, market, event, global_assessment), "invalidation": RecommendationEngine._invalidation(alert, prediction, market),
            "fundamentals": fundamental_payload, "market": market,
            "fundamental_score": round(fundamental_score, 1), "model_score": round(model_score, 1), "market_score": round(market_score, 1), "evidence_score": round(evidence_score, 1),
            "global_score": round(global_score, 1), "global_intelligence": global_assessment,
            "fundamental_quality_score": round(fundamental_assessment.quality_score, 1), "fundamental_growth_score": round(fundamental_assessment.growth_score, 1),
            "fundamental_profitability_score": round(fundamental_assessment.profitability_score, 1), "fundamental_balance_sheet_score": round(fundamental_assessment.balance_sheet_score, 1),
            "fundamental_valuation_score": round(fundamental_assessment.valuation_score, 1), "fundamental_cash_flow_score": round(fundamental_assessment.cash_flow_score, 1),
            "fundamental_earnings_quality_score": round(fundamental_assessment.earnings_quality_score, 1), "fundamental_data_completeness": round(fundamental_assessment.completeness, 2),
            "fundamental_classification": fundamental_assessment.classification, "fundamental_flags": fundamental_assessment.flags,
            "evidence": {"source": (alert.source_name if alert else None) or (news.source if news else None), "source_url": (alert.source_url if alert else None) or (news.url if news else None), "event_id": event.id if event else (alert.event_id if alert else None), "opportunity_score": alert.opportunity_score if alert else None, "evidence_count": RecommendationEngine._evidence_count(db, event, news, stock.sector, cutoff)},
            "news": {"title": news.title if news else None, "source": news.source if news else None, "source_url": news.url if news else None, "published_at": news.published_at.isoformat() if news and news.published_at else None, "summary": news.summary if news else None},
            "event": {"title": event.title if event else None, "description": event.description if event else None, "sector": event.sector if event else None, "direction": event.direction if event else None, "impact": event.impact if event else None, "horizon": event.time_horizon if event else None},
            "created_at": (alert.created_at if alert else datetime.utcnow()).isoformat(),
        }

    @staticmethod
    def _rank(items):
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        items.sort(key=lambda x: (priority_order.get(x["priority"], 3), -x["score"]))
        for i, item in enumerate(items, 1): item["rank"] = i
        return items

    @staticmethod
    def _priority(composite, intelligence, fundamentals, model, evidence):
        if composite >= 80 and intelligence >= 70 and fundamentals >= 60 and model >= 55 and evidence >= 55: return "HIGH"
        if composite >= 60 and intelligence >= 50 and (fundamentals >= 45 or model >= 50): return "MEDIUM"
        return "LOW"

    @staticmethod
    def _global_assessment(global_impacts, sector) -> dict:
        """Translate detected global macro signals into a 0-100 score for this stock's sector.

        global_impacts maps a signal-sector tag (e.g. "BANKING", "OIL & GAS") to an
        aggregate impact record from GlobalIntelligence. A stock's yfinance sector is
        expanded to the tags it plausibly belongs to via sector_tags_for, and the
        strongest matching signal decides the score. No matching signal is neutral
        (50), not a penalty — absence of global news is not evidence of anything.
        """
        if not global_impacts or not sector:
            return {"score": 50.0, "matched": False, "sectors_considered": []}
        tags = sector_tags_for(sector)
        matches = [global_impacts[tag] for tag in tags if tag in global_impacts]
        if not matches:
            return {"score": 50.0, "matched": False, "sectors_considered": list(tags)}
        strongest = max(matches, key=lambda m: abs(m["score"]))
        # aggregate_global_impact's "score" is a running SUM across every matching
        # article, not a per-signal strength -- a sector mentioned in 50 articles
        # would otherwise swamp the scale. Normalize by signal count first so the
        # result reflects average conviction, not article volume.
        signal_count = max(1, strongest["signals"])
        avg_impact = strongest["score"] / signal_count
        score = max(0.0, min(100.0, 50.0 + avg_impact * 40))
        return {
            "score": round(score, 1),
            "matched": True,
            "sectors_considered": list(tags),
            "matched_sector_tag": strongest["sector"],
            "signal_count": strongest["signals"],
            "raw_impact": round(avg_impact, 3),
        }

    @staticmethod
    def _sector_intelligence_score(event, news, recent_sectors, stock):
        score = 35.0
        if event:
            score += 15
            if event.impact and str(event.impact).upper() in {"HIGH", "SEVERE"}: score += 15
            elif event.impact: score += 7
            if event.direction and str(event.direction).upper() in {"POSITIVE", "BULLISH"}: score += 8
        if news: score += 12
        if stock.sector and stock.sector.strip().upper() in (recent_sectors or set()): score += 10
        return min(100, score)

    @staticmethod
    def _risk(market, fundamentals):
        vol = market.get("volatility_20d_annualized_pct") or 25
        debt = getattr(fundamentals, "debt_to_equity", None) if fundamentals else None
        if vol > 55 or (debt is not None and debt > 2): return "HIGH"
        if vol > 35 or (debt is not None and debt > 1.2): return "MEDIUM"
        return "LOW"

    @staticmethod
    def _market_stats(db, stock_id: int) -> dict:
        rows = list(reversed(db.scalars(select(MarketData).where(MarketData.stock_id == stock_id).order_by(MarketData.timestamp.desc()).limit(260)).all()))
        if not rows: return {}
        closes = [float(r.close) for r in rows if r.close is not None]; volumes = [float(r.volume) for r in rows if r.volume is not None and r.volume > 0]
        if not closes: return {}
        current = closes[-1]
        def ret(days): return (current / closes[-days - 1] - 1) * 100 if len(closes) > days and closes[-days - 1] else None
        daily = [(closes[i] / closes[i-1] - 1) for i in range(1, len(closes)) if closes[i-1]]
        recent = daily[-20:]; mean = sum(recent) / len(recent) if recent else 0
        vol20 = (sum((x-mean)**2 for x in recent)/len(recent))**0.5 * sqrt(252) * 100 if recent else None
        high52, low52 = max(closes[-252:]), min(closes[-252:]); avg20 = sum(volumes[-20:])/min(20, len(volumes)) if volumes else None; latest = volumes[-1] if volumes else None
        return {"current_price": round(current,2), "return_1d_pct": round(ret(1),2) if ret(1) is not None else None, "return_5d_pct": round(ret(5),2) if ret(5) is not None else None, "return_20d_pct": round(ret(20),2) if ret(20) is not None else None, "return_60d_pct": round(ret(60),2) if ret(60) is not None else None, "volatility_20d_annualized_pct": round(vol20,2) if vol20 is not None else None, "high_52w": round(high52,2), "low_52w": round(low52,2), "distance_from_52w_high_pct": round((current/high52-1)*100,2) if high52 else None, "distance_from_52w_low_pct": round((current/low52-1)*100,2) if low52 else None, "volume_vs_20d_avg": round(latest/avg20,2) if latest and avg20 else None, "data_points": len(rows), "data_as_of": rows[-1].timestamp.isoformat() if rows[-1].timestamp else None}

    @staticmethod
    def _market_score(m):
        if not m: return 50.0
        score=50.0; r5=m.get("return_5d_pct"); r20=m.get("return_20d_pct")
        if r5 is not None: score += max(-15,min(15,r5*2))
        if r20 is not None: score += max(-12,min(12,r20*0.8))
        v=m.get("volume_vs_20d_avg")
        if v is not None and v>1.5: score+=8
        elif v is not None and v<0.7: score-=4
        return max(0,min(100,score))

    @staticmethod
    def _evidence_count(db,event,news,sector=None,cutoff=None):
        cutoff = cutoff or (datetime.utcnow()-timedelta(days=14)); count=1 if news else 0
        if event:
            related=db.scalars(select(MarketEvent).where(MarketEvent.id!=event.id,MarketEvent.event_date>=cutoff)).all()
            if sector: related=[e for e in related if e.sector and str(e.sector).strip().upper()==str(sector).strip().upper()]
            count += len(related)
        if sector: count += db.scalar(select(func.count(NewsArticle.id)).where(NewsArticle.created_at>=cutoff)) or 0
        return min(50,count)

    @staticmethod
    def _evidence_score(db,event,news,sector=None,cutoff=None): return min(100.0,40+RecommendationEngine._evidence_count(db,event,news,sector,cutoff)*3)

    @staticmethod
    def _entry_zone(current,market,risk):
        if not current: return None,None
        vol=market.get("volatility_20d_annualized_pct") or 25; discount=min(0.08,max(0.02,vol/1000)) + (0.02 if str(risk).upper()=="HIGH" else 0)
        return round(current*(1-discount),2),round(current*(1+min(0.01,discount/4)),2)

    @staticmethod
    def _fundamental_score(f): return FundamentalIntelligence.assess(f).score

    @staticmethod
    def _model_score(p):
        if not p: return 45.0
        score=50.0
        if p.predicted_return_5d is not None: score += max(-20,min(20,float(p.predicted_return_5d)*3))
        if p.predicted_return_20d is not None: score += max(-15,min(15,float(p.predicted_return_20d)*2))
        if str(p.signal or "").upper() in {"BUY","BULLISH","LONG"}: score+=8
        elif str(p.signal or "").upper() in {"SELL","BEARISH","SHORT"}: score-=8
        return max(0,min(100,score))

    @staticmethod
    def _fundamentals(f):
        if not f: return {}
        return {"pe":f.pe_ratio,"pb":f.pb_ratio,"roe":f.roe,"debt_to_equity":f.debt_to_equity,"profit_margin":f.profit_margin,"revenue_growth":f.revenue_growth,"earnings_growth":f.earnings_growth,"market_cap":f.market_cap,"revenue":f.revenue,"net_income":f.net_income,"eps":f.eps,"roa":f.roa,"operating_margin":f.operating_margin,"sector":f.sector,"industry":f.industry,"operating_cash_flow":f.operating_cash_flow,"capital_expenditure":f.capital_expenditure,"free_cash_flow":f.free_cash_flow,"total_debt":f.total_debt,"cash_and_equivalents":f.cash_and_equivalents,"interest_expense":f.interest_expense}

    @staticmethod
    def _fallback_reason(event, fundamentals, prediction, market):
        if event: return f"{event.title}: {event.direction or 'market'} impact in {event.sector or 'affected sector'}"
        if fundamentals: return f"Fundamental score {FundamentalIntelligence.assess(fundamentals).score:.0f}/100 with available company financial data"
        if prediction: return "Model and market signals are being monitored"
        return "Market setup is being monitored"

    @staticmethod
    def _why_now(alert, prediction, market, event, global_assessment=None):
        if alert and alert.reason: return alert.reason
        parts=[]
        if event and event.title: parts.append(event.title)
        if prediction and prediction.predicted_return_5d is not None: parts.append(f"ML 5D estimate {float(prediction.predicted_return_5d):+.2f}%")
        if market.get("return_5d_pct") is not None: parts.append(f"5D price move {float(market['return_5d_pct']):+.2f}%")
        if global_assessment and global_assessment.get("matched") and abs(global_assessment.get("raw_impact", 0)) >= 0.3:
            parts.append(f"Global {global_assessment['matched_sector_tag'].title()} signal ({global_assessment['signal_count']} article(s))")
        return " · ".join(parts) if parts else "Fresh evidence is being evaluated"

    @staticmethod
    def _invalidation(alert, prediction, market):
        if alert and alert.reason: return "Reassess if the catalyst weakens, price invalidates the setup, or new evidence changes the thesis."
        if market.get("low_52w") is not None: return f"Reassess on sustained deterioration toward the 52-week low ({market['low_52w']})."
        return "Reassess if the catalyst weakens or market/fundamental evidence changes materially."

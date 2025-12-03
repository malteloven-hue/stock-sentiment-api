from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import yfinance as yf
import requests_cache
import time
import random

app = FastAPI(title="Stock Sentinel API (Smart)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. INSTALLERA CACHE (Räddningen mot Yahoo-blockering!)
# Sparar svar i 30 minuter. Stoppar 429-felen.
session = requests_cache.CachedSession('yfinance.cache', expire_after=1800)

# 2. FEJKA EN WEBBLÄSARE
# Yahoo tror nu att vi är en vanlig användare, inte en robot.
session.headers['User-agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

# 3. LÄTTVIKTS-AI (VADER)
# Drar inget minne, funkar perfekt på din Starter-plan.
analyzer = SentimentIntensityAnalyzer()
print("Sentinel Engine Loaded (VADER Mode) 🚀")

@app.get("/")
def root():
    return {"status": "ok", "msg": "API is running with Cache protection"}

@app.get("/calendar")
def get_earnings_calendar():
    watchlist = ["AAPL", "NVDA", "TSLA", "MSFT", "VOLV-B.ST", "ERIC-B.ST", "HM-B.ST"]
    upcoming = []

    for ticker in watchlist:
        try:
            # Använd session=session för att använda cachen
            stock = yf.Ticker(ticker, session=session)
            cal = stock.calendar
            
            if cal and "Earnings Date" in cal:
                dates = cal["Earnings Date"]
                next_date = dates[0] if isinstance(dates, list) else dates
                
                if next_date:
                    upcoming.append({
                        "ticker": ticker,
                        "date": next_date.strftime("%Y-%m-%d"),
                        "est_revenue": "N/A"
                    })
            # Liten paus för att vara snäll mot Yahoo
            time.sleep(random.uniform(0.5, 1.0))
            
        except Exception as e:
            continue
    
    upcoming.sort(key=lambda x: x['date'])
    return upcoming[:10]

@app.get("/earnings/{ticker}")
def check_earnings(ticker: str):
    try:
        stock = yf.Ticker(ticker.upper(), session=session)
        news = stock.news
        
        earnings_keywords = ["earnings", "report", "quarter", "q1", "q2", "q3", "q4", "resultat", "revenue"]
        earnings_news = []
        
        for item in news:
            title = item.get("title", "").lower()
            if any(key in title for key in earnings_keywords):
                earnings_news.append(item.get("title", ""))
        
        if not earnings_news:
            return {"status": "No recent report", "verdict": "Waiting...", "color": "gray", "headlines": []}

        total_score = 0
        for headline in earnings_news[:5]:
            score = analyzer.polarity_scores(headline)['compound']
            total_score += score

        avg_score = total_score / len(earnings_news) if earnings_news else 0
        
        full_text = " ".join(earnings_news).lower()
        if "beat" in full_text or "strong" in full_text: avg_score += 0.25
        if "miss" in full_text or "weak" in full_text: avg_score -= 0.25

        if avg_score >= 0.05:
            verdict = "STRONG BEAT 🚀"
            color = "green"
        elif avg_score <= -0.05:
            verdict = "MISS / WEAK 🔻"
            color = "red"
        else:
            verdict = "NEUTRAL"
            color = "yellow"
            
        return {"status": "Report Found", "verdict": verdict, "color": color, "headlines": earnings_news[:3]}

    except Exception:
        return {"status": "Error", "verdict": "N/A", "headlines": []}

@app.get("/analyze/{ticker}")
def analyze_ticker(ticker: str):
    try:
        stock = yf.Ticker(ticker.upper(), session=session)
        news = stock.news
        
        if not news:
            return {"ticker": ticker, "final_sentiment": "Neutral", "sentiment_score": 0, "news_analysis": []}

        total_score = 0
        analyzed_news = []
        
        for item in news[:8]:
            headline = item.get("title", "")
            score = analyzer.polarity_scores(headline)['compound']
            label = "positive" if score >= 0.05 else "negative" if score <= -0.05 else "neutral"
            
            analyzed_news.append({"headline": headline, "score": round(score, 2), "sentiment": label})
            total_score += score
            
        avg_score = total_score / len(analyzed_news) if analyzed_news else 0
        final_sent = "Bullish 🚀" if avg_score > 0.05 else "Bearish 🐻" if avg_score < -0.05 else "Neutral 😐"
        
        return {
            "ticker": ticker.upper(),
            "final_sentiment": final_sent,
            "sentiment_score": round(avg_score * 100, 0),
            "news_analysis": analyzed_news
        }
    except Exception:
        return {"ticker": ticker, "final_sentiment": "Data Unavailable", "sentiment_score": 0, "news_analysis": []}

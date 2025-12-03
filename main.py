from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import yfinance as yf
from typing import List, Dict, Any
from datetime import datetime

app = FastAPI(title="Stock Sentinel API (Lite)")

# Tillåt trafik från alla håll (viktigt för Lovable)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initiera "Lättvikts-hjärnan" (VADER) - Drar inget minne!
analyzer = SentimentIntensityAnalyzer()
print("Sentinel Engine Loaded (VADER Mode) 🚀")

@app.get("/")
def root():
    return {"status": "ok", "msg": "Stock Sentinel API is running smoothly!"}

# --- 1. KALENDER (Visar kommande rapporter) ---
@app.get("/calendar")
def get_earnings_calendar():
    """Hämtar nästa rapportdatum för dina bevakade aktier."""
    # Du kan lägga till fler aktier i den här listan
    watchlist = ["AAPL", "MSFT", "GOOGL", "META", "AMZN", "NVDA", "TSLA", "VOLV-B.ST", "ERIC-B.ST", "HM-B.ST"]
    upcoming = []

    for ticker in watchlist:
        try:
            stock = yf.Ticker(ticker)
            # Försök hämta kalenderdata
            cal = stock.calendar
            
            # yfinance kan returnera data på olika sätt, vi försöker hitta datumet
            if cal and "Earnings Date" in cal:
                dates = cal["Earnings Date"]
                # Ibland är det en lista, ibland ett enskilt värde
                next_date = dates[0] if isinstance(dates, list) else dates
                
                if next_date:
                    upcoming.append({
                        "ticker": ticker,
                        "date": next_date.strftime("%Y-%m-%d"),
                        "est_revenue": "N/A" # Yahoo ger inte alltid detta gratis
                    })
        except Exception:
            # Om en aktie strular, hoppa bara över den
            continue
    
    # Sortera listan: Snaraste datumet först
    upcoming.sort(key=lambda x: x['date'])
    
    # Returnera de 10 närmaste rapporterna
    return upcoming[:10]

# --- 2. LIVE RAPPORT-FEED (För 'Earnings Hub') ---
@app.get("/earnings/{ticker}")
def check_earnings(ticker: str):
    """Kollar om bolaget släppt en rapport nyligen och analyserar den."""
    try:
        stock = yf.Ticker(ticker.upper())
        news = stock.news
        
        # Nyckelord vi letar efter
        earnings_keywords = ["earnings", "report", "quarter", "q1", "q2", "q3", "q4", "resultat", "kvartal", "revenue", "profit"]
        earnings_news = []
        
        # Filtrera fram relevanta nyheter
        for item in news:
            title = item.get("title", "").lower()
            if any(key in title for key in earnings_keywords):
                earnings_news.append(item.get("title", ""))
        
        if not earnings_news:
            return {
                "status": "No recent report",
                "verdict": "Waiting...",
                "color": "gray",
                "headlines": []
            }

        # Analysera stämningen i rapport-nyheterna
        total_score = 0
        for headline in earnings_news[:5]:
            score = analyzer.polarity_scores(headline)['compound']
            total_score += score

        avg_score = total_score / len(earnings_news) if earnings_news else 0
        
        # Leta efter "Starka ord" för att avgöra domen
        full_text = " ".join(earnings_news).lower()
        if "beat" in full_text or "soars" in full_text or "strong" in full_text or "jump" in full_text:
            avg_score += 0.25
        if "miss" in full_text or "falls" in full_text or "weak" in full_text or "drop" in full_text:
            avg_score -= 0.25

        # Sätt etikett (Verdict)
        if avg_score >= 0.05:
            verdict = "STRONG BEAT 🚀"
            color = "green"
        elif avg_score <= -0.05:
            verdict = "MISS / WEAK 🔻"
            color = "red"
        else:
            verdict = "NEUTRAL"
            color = "yellow"
            
        return {
            "status": "Report Found",
            "verdict": verdict,
            "color": color,
            "headlines": earnings_news[:3]
        }

    except Exception as e:
        print(f"Error checking earnings: {e}")
        return {"status": "Error", "verdict": "N/A", "headlines": []}

# --- 3. ALLMÄN SENTIMENT-ANALYS (För Startsidan) ---
@app.get("/analyze/{ticker}")
def analyze_ticker(ticker: str):
    try:
        stock = yf.Ticker(ticker.upper())
        news = stock.news
        
        if not news:
            return {"ticker": ticker, "final_sentiment": "Neutral", "sentiment_score": 0, "news_analysis": []}

        total_score = 0
        analyzed_news = []
        
        for item in news[:8]: # Analysera de 8 senaste rubrikerna
            headline = item.get("title", "")
            # VADER ger poäng mellan -1 och 1
            score = analyzer.polarity_scores(headline)['compound']
            
            label = "neutral"
            if score >= 0.05: label = "positive"
            elif score <= -0.05: label = "negative"
            
            analyzed_news.append({
                "headline": headline,
                "score": round(score, 2),
                "sentiment": label
            })
            total_score += score
            
        avg_score = total_score / len(analyzed_news) if analyzed_news else 0
        
        # Översätt till mänskligt språk
        final_sent = "Bullish 🚀" if avg_score > 0.05 else "Bearish 🐻" if avg_score < -0.05 else "Neutral 😐"
        
        return {
            "ticker": ticker.upper(),
            "final_sentiment": final_sent,
            "sentiment_score": round(avg_score * 100, 0), # Gör om till 0-100 skala
            "news_analysis": analyzed_news
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from transformers import pipeline
import yfinance as yf
from typing import List, Dict, Any

app = FastAPI(title="Stock Sentiment API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize FinBERT pipeline (loads on startup)
print("Loading FinBERT model...")
sentiment_pipeline = pipeline("sentiment-analysis", model="ProsusAI/finbert")
print("FinBERT model loaded!")


def get_sentiment_score(label: str, score: float) -> float:
    """Convert FinBERT output to -100 to +100 scale."""
    if label == "positive":
        return score * 100
    elif label == "negative":
        return score * -100
    return 0  # neutral


@app.get("/")
def root():
    return {"status": "ok", "message": "Stock Sentiment API is running"}


@app.get("/analyze/{ticker}")
def analyze_ticker(ticker: str) -> Dict[str, Any]:
    """Analyze sentiment for a stock ticker using news headlines."""
    try:
        # Fetch stock info and news
        stock = yf.Ticker(ticker.upper())
        news = stock.news
        
        if not news:
            raise HTTPException(status_code=404, detail=f"No news found for {ticker}")
        
        # Analyze each headline
        news_analysis: List[Dict[str, Any]] = []
        total_score = 0
        
        for item in news[:15]:  # Limit to 15 most recent
            headline = item.get("title", "")
            if not headline:
                continue
            
            # Run FinBERT
            result = sentiment_pipeline(headline[:512])[0]  # Truncate to model max
            label = result["label"]
            confidence = result["score"]
            score = get_sentiment_score(label, confidence)
            
            news_analysis.append({
                "headline": headline,
                "source": item.get("publisher", "Unknown"),
                "link": item.get("link", ""),
                "sentiment": label,
                "confidence": round(confidence, 3),
                "score": round(score, 2),
                "timestamp": item.get("providerPublishTime", 0)
            })
            total_score += score
        
        if not news_analysis:
            raise HTTPException(status_code=404, detail="Could not analyze any headlines")
        
        # Calculate final sentiment
        avg_score = total_score / len(news_analysis)
        
        if avg_score > 15:
            final_sentiment = "Bullish"
        elif avg_score < -15:
            final_sentiment = "Bearish"
        else:
            final_sentiment = "Neutral"
        
        return {
            "ticker": ticker.upper(),
            "final_sentiment": final_sentiment,
            "sentiment_score": round(avg_score, 2),
            "total_articles": len(news_analysis),
            "news_analysis": news_analysis
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

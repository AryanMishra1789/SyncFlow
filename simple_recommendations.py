import sqlite3
import json
import sys
from datetime import datetime

def get_recommendations():
    try:
        # Connect to the database
        conn = sqlite3.connect('history.db')
        cursor = conn.cursor()
        
        # Get top categories from history
        cursor.execute("""
            SELECT category, COUNT(*) as count
            FROM history
            WHERE category IS NOT NULL AND category != 'Other'
            GROUP BY category
            ORDER BY count DESC
            LIMIT 5
        """)
        
        categories = cursor.fetchall()
        
        # Predefined recommendations by category
        recommendations = {
            "Technology": [
                {"url": "https://github.com/explore", "title": "GitHub Explore", "confidence": 90},
                {"url": "https://dev.to", "title": "DEV Community", "confidence": 85},
                {"url": "https://news.ycombinator.com", "title": "Hacker News", "confidence": 80}
            ],
            "Entertainment": [
                {"url": "https://www.youtube.com/trending", "title": "YouTube Trending", "confidence": 90},
                {"url": "https://www.netflix.com/browse", "title": "Netflix", "confidence": 85},
                {"url": "https://www.spotify.com/browse", "title": "Spotify", "confidence": 80}
            ],
            "Social": [
                {"url": "https://www.linkedin.com", "title": "LinkedIn", "confidence": 90},
                {"url": "https://twitter.com", "title": "Twitter", "confidence": 85},
                {"url": "https://www.reddit.com", "title": "Reddit", "confidence": 80}
            ],
            "Shopping": [
                {"url": "https://www.amazon.com", "title": "Amazon", "confidence": 90},
                {"url": "https://www.ebay.com", "title": "eBay", "confidence": 85},
                {"url": "https://www.etsy.com", "title": "Etsy", "confidence": 80}
            ],
            "News": [
                {"url": "https://news.google.com", "title": "Google News", "confidence": 90},
                {"url": "https://www.reuters.com", "title": "Reuters", "confidence": 85},
                {"url": "https://www.bbc.com/news", "title": "BBC News", "confidence": 80}
            ]
        }
        
        # Generate recommendations based on user's top categories
        final_recommendations = []
        for category, count in categories:
            if category in recommendations:
                for rec in recommendations[category][:2]:  # Take top 2 from each category
                    final_recommendations.append({
                        "url": rec["url"],
                        "title": rec["title"],
                        "category": category,
                        "confidence": rec["confidence"],
                        "description": f"Recommended based on your {category} browsing"
                    })
        
        # If no recommendations were generated, provide default ones
        if not final_recommendations:
            final_recommendations = [
                {
                    "url": "https://github.com/explore",
                    "title": "GitHub Explore",
                    "category": "Technology",
                    "confidence": 80,
                    "description": "Explore trending repositories"
                },
                {
                    "url": "https://www.youtube.com/trending",
                    "title": "YouTube Trending",
                    "category": "Entertainment",
                    "confidence": 80,
                    "description": "See what's trending on YouTube"
                }
            ]
        
        conn.close()
        return json.dumps(final_recommendations)
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        return json.dumps([])

if __name__ == "__main__":
    print(get_recommendations()) 
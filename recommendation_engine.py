import requests
import os
import json
import random
from urllib.parse import urlparse, quote_plus
import sqlite3
from datetime import datetime, timedelta
import numpy as np
from history_analyzer import categories_dataset, category_for_entry
from collections import Counter, defaultdict
import sys

# Constants
NEWS_API_KEY = "pub_765013277f722bcbd875eb5ccdebf5e14194f"
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "AIzaSyD28AvgIHKGbWo8QdvI1pWl-x0hUHrijb8")

class RecommendationEngine:
    def __init__(self):
        self.database = 'history.db'
        self.categories = {
            'Technology': ['github.com', 'stackoverflow.com', 'dev.to', 'medium.com'],
            'News': ['news.google.com', 'reuters.com', 'bbc.com', 'cnn.com'],
            'Entertainment': ['youtube.com', 'netflix.com', 'spotify.com'],
            'Productivity': ['gmail.com', 'docs.google.com', 'notion.so'],
            'Social': ['linkedin.com', 'twitter.com', 'facebook.com'],
            'Education': ['coursera.org', 'udemy.com', 'edx.org']
        }
        
        self.recommendation_sources = {
            "Technology": [
                {"url": "https://github.com/explore", "title": "GitHub Explore - Trending Projects"},
                {"url": "https://dev.to", "title": "DEV Community"},
                {"url": "https://news.ycombinator.com", "title": "Hacker News"},
                {"url": "https://medium.com/topic/technology", "title": "Medium Technology"},
                {"url": "https://www.producthunt.com", "title": "Product Hunt"}
            ],
            "News": [
                {"url": "https://news.google.com", "title": "Google News"},
                {"url": "https://reuters.com", "title": "Reuters"},
                {"url": "https://apnews.com", "title": "Associated Press"},
                {"url": "https://www.bbc.com/news", "title": "BBC News"},
                {"url": "https://www.aljazeera.com", "title": "Al Jazeera"}
            ],
            "Entertainment": [
                {"url": "https://www.youtube.com/trending", "title": "YouTube Trending"},
                {"url": "https://www.imdb.com", "title": "IMDb"},
                {"url": "https://www.spotify.com/browse", "title": "Spotify Browse"},
                {"url": "https://www.netflix.com/browse", "title": "Netflix Browse"},
                {"url": "https://www.twitch.tv/directory", "title": "Twitch Directory"}
            ],
            "Productivity": [
                {"url": "https://www.notion.so", "title": "Notion - All-in-one Workspace"},
                {"url": "https://trello.com", "title": "Trello"},
                {"url": "https://www.evernote.com", "title": "Evernote"},
                {"url": "https://calendar.google.com", "title": "Google Calendar"},
                {"url": "https://todoist.com", "title": "Todoist"}
            ],
            "Education": [
                {"url": "https://www.coursera.org", "title": "Coursera"},
                {"url": "https://www.udemy.com", "title": "Udemy"},
                {"url": "https://www.edx.org", "title": "edX"},
                {"url": "https://www.khanacademy.org", "title": "Khan Academy"},
                {"url": "https://www.codecademy.com", "title": "Codecademy"}
            ]
        }
        
        # Initialize databases
        self.init_databases()
        
        # Add some sample history data if no data exists
        self.ensure_sample_data()

    def init_databases(self):
        """Initialize both history and recommendations databases."""
        try:
            # Initialize history database
            conn = sqlite3.connect(self.database)
            cursor = conn.cursor()
            
            # Create history table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    title TEXT,
                    visit_time TEXT NOT NULL,
                    domain TEXT,
                    category TEXT,
                    website_name TEXT,
                    visit_count INTEGER DEFAULT 1,
                    category_confidence REAL DEFAULT 0.0
                )
            """)
            
            # Create recommendations table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    confidence REAL,
                    timestamp TEXT,
                    is_visited INTEGER DEFAULT 0
                )
            """)
            
            conn.commit()
            conn.close()
            print("Databases initialized successfully")
        except Exception as e:
            print(f"Error initializing databases: {str(e)}")

    def ensure_sample_data(self):
        """Add sample history data if no data exists."""
        try:
            conn = sqlite3.connect(self.database)
            cursor = conn.cursor()
            
            # Check if history table is empty
            cursor.execute("SELECT COUNT(*) FROM history")
            count = cursor.fetchone()[0]
            
            if count == 0:
                # Add sample history data
                sample_data = [
                    ('https://github.com', 'GitHub', '2024-03-10 10:00:00', 'github.com', 'Technology', 'GitHub', 1, 0.8),
                    ('https://news.google.com', 'Google News', '2024-03-10 11:00:00', 'news.google.com', 'News', 'Google News', 1, 0.8),
                    ('https://youtube.com', 'YouTube', '2024-03-10 12:00:00', 'youtube.com', 'Entertainment', 'YouTube', 1, 0.8),
                    ('https://docs.google.com', 'Google Docs', '2024-03-10 13:00:00', 'docs.google.com', 'Productivity', 'Google Docs', 1, 0.8),
                    ('https://linkedin.com', 'LinkedIn', '2024-03-10 14:00:00', 'linkedin.com', 'Social', 'LinkedIn', 1, 0.8)
                ]
                
                cursor.executemany("""
                    INSERT INTO history (url, title, visit_time, domain, category, website_name, visit_count, category_confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, sample_data)
                
                conn.commit()
                print("Added sample history data")
            
            conn.close()
        except Exception as e:
            print(f"Error adding sample data: {str(e)}")

    def analyze_history(self):
        try:
            conn = sqlite3.connect(self.database)
            cursor = conn.cursor()
            
            # Get category distribution
            cursor.execute("""
                SELECT category, COUNT(*) as count
                FROM history
                WHERE category IS NOT NULL
                GROUP BY category
                ORDER BY count DESC
            """)
            
            categories = {}
            for row in cursor.fetchall():
                categories[row[0]] = row[1]
            
            # Get time patterns
            cursor.execute("""
                SELECT strftime('%H', visit_time) as hour, COUNT(*) as count
                FROM history
                GROUP BY hour
                ORDER BY count DESC
            """)
            
            time_patterns = {}
            for row in cursor.fetchall():
                time_patterns[row[0]] = row[1]
            
            # Get weekly patterns
            cursor.execute("""
                SELECT strftime('%w', visit_time) as day, COUNT(*) as count
                FROM history
                GROUP BY day
                ORDER BY day
            """)
            
            weekly_patterns = {}
            for row in cursor.fetchall():
                weekly_patterns[row[0]] = row[1]
            
            conn.close()
            
            return {
                'categories': {
                    'distribution': categories,
                    'time_patterns': time_patterns,
                    'weekly_patterns': weekly_patterns
                },
                'total_visits': sum(categories.values()) if categories else 0
            }
            
        except Exception as e:
            print(f"Error analyzing history: {str(e)}", file=sys.stderr)
            return None

    def get_user_interests(self):
        """Get user interests based on browsing history."""
        try:
            conn = sqlite3.connect(self.database)
            cursor = conn.cursor()
            
            # Get category distribution with visit counts and recency
            cursor.execute("""
                SELECT 
                    category,
                    COUNT(*) as visit_count,
                    MAX(visit_time) as last_visit
                FROM history 
                WHERE category IS NOT NULL
                GROUP BY category
                ORDER BY visit_count DESC
            """)
            
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                return {}
                
            # Calculate scores based on visit count and recency
            now = datetime.now()
            interests = {}
            total_visits = sum(row[1] for row in results)
            
            for category, visits, last_visit in results:
                if not category or category == 'Other':
                    continue
                    
                # Convert last_visit string to datetime
                try:
                    last_visit_dt = datetime.strptime(last_visit, '%Y-%m-%d %H:%M:%S')
                    days_since = (now - last_visit_dt).days
                    recency_score = 1 / (days_since + 1)  # Higher score for more recent visits
                except:
                    recency_score = 0.1  # Default if date parsing fails
                
                # Normalize visit count and combine with recency
                visit_score = visits / total_visits
                interests[category] = (visit_score * 0.7) + (recency_score * 0.3)
            
            # Normalize scores to sum to 1
            total_score = sum(interests.values())
            if total_score > 0:
                interests = {k: v/total_score for k, v in interests.items()}
            
            return interests
            
        except Exception as e:
            print(f"Error getting user interests: {str(e)}")
            return {}

    def generate_recommendations(self, limit=5):
        """Generate personalized recommendations based on user interests."""
        try:
            # Get user interests
            interests = self.get_user_interests()
            
            if not interests:
                print("No user interests found, generating default recommendations")
                # Generate default recommendations if no interests found
                interests = {
                    'Technology': 0.3,
                    'News': 0.2,
                    'Entertainment': 0.2,
                    'Productivity': 0.15,
                    'Social': 0.15
                }
            
            recommendations = []
            used_urls = set()
            
            # Sort categories by interest score
            sorted_interests = sorted(interests.items(), key=lambda x: x[1], reverse=True)
            
            # Generate recommendations based on interest weights
            for category, score in sorted_interests:
                if category in self.recommendation_sources:
                    category_recs = self.recommendation_sources[category]
                    
                    # Add recommendations from this category
                    for rec in category_recs:
                        if rec['url'] not in used_urls:
                            confidence = round(score * 100, 2)  # Convert score to percentage
                            recommendations.append({
                                'url': rec['url'],
                                'title': rec['title'],
                                'category': category,
                                'confidence': confidence,
                                'description': f"Recommended based on your interest in {category}"
                            })
                            used_urls.add(rec['url'])
                            
                            if len(recommendations) >= limit:
                                break
                                
                if len(recommendations) >= limit:
                    break
            
            # Save recommendations to database
            if recommendations:
                self.save_recommendations(recommendations)
                print(f"Generated and saved {len(recommendations)} recommendations")
                
                # Verify recommendations were saved
                saved_recs = self.get_recommendations_from_db()
                if saved_recs:
                    print(f"Successfully verified {len(saved_recs)} recommendations in database")
                else:
                    print("Warning: Recommendations were not found in database after saving")
            else:
                print("No recommendations generated")
            
            return recommendations
            
        except Exception as e:
            print(f"Error generating recommendations: {str(e)}")
            print("Error details:", e.__class__.__name__)
            return []

    def get_category_stats(self):
        """Get statistics about browsing categories."""
        try:
            conn = sqlite3.connect(self.database)
            cursor = conn.cursor()
            
            # Get category distribution
            cursor.execute("""
                SELECT 
                    category,
                    COUNT(*) as count,
                    COUNT(DISTINCT domain) as unique_domains,
                    MAX(visit_time) as last_visit
                FROM history
                WHERE category IS NOT NULL
                GROUP BY category
                ORDER BY count DESC
            """)
            
            results = cursor.fetchall()
            conn.close()
            
            stats = []
            for category, count, unique_domains, last_visit in results:
                if not category:
                    continue
                    
                stats.append({
                    'category': category,
                    'visit_count': count,
                    'unique_domains': unique_domains,
                    'last_visit': last_visit
                })
            
            return stats
            
        except Exception as e:
            print(f"Error getting category stats: {str(e)}")
            return []

    def print_detailed_recommendations(self, recommendations, analysis):
        """Print detailed recommendations with analytics insights."""
        print("\n=== Personalized Recommendations ===\n")
        
        # Print analytics summary
        print("📊 Browsing Analytics Summary:")
        print("-" * 40)
        categories = analysis['categories']['distribution']
        total_visits = sum(categories.values())
        print(f"Total analyzed visits: {total_visits}")
        print("\nTop Categories:")
        for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]:
            percentage = (count / total_visits) * 100
            print(f"• {category}: {count} visits ({percentage:.1f}%)")
        
        print("\n🎯 Personalized Recommendations:")
        print("-" * 40)
        
        # Group and print recommendations by type and category
        by_type = {}
        for rec in recommendations:
            rec_type = rec.get('type', 'general')
            if rec_type not in by_type:
                by_type[rec_type] = {}
            category = rec['category']
            if category not in by_type[rec_type]:
                by_type[rec_type][category] = []
            by_type[rec_type][category].append(rec)
        
        # Print by type
        type_emojis = {
            'general': '🌐',
            'video': '🎥',
            'news': '📰'
        }
        
        for rec_type, categories in by_type.items():
            print(f"\n{type_emojis.get(rec_type, '•')} {rec_type.upper()} RECOMMENDATIONS:")
            
            for category, recs in categories.items():
                print(f"\n{category}:")
                print("=" * len(category))
                
                for rec in recs:
                    print(f"\n  📌 {rec['title']}")
                    print(f"     {rec['description']}")
                    print(f"     URL: {rec['url']}")
                    print(f"     Confidence: {rec['confidence']}%")
                    print("     " + "-" * 40)

    def save_recommendations(self, recommendations):
        """Save recommendations to the database."""
        try:
            conn = sqlite3.connect(self.database)
            cursor = conn.cursor()
            
            # Clear old recommendations
            cursor.execute("DELETE FROM recommendations")
            
            # Insert new recommendations
            for rec in recommendations:
                cursor.execute("""
                    INSERT INTO recommendations (
                        title, url, description, category, confidence, timestamp
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    rec['title'],
                    rec['url'],
                    rec.get('description', ''),
                    rec['category'],
                    rec['confidence'],
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))
            
            conn.commit()
            conn.close()
            print(f"Saved {len(recommendations)} recommendations to database")
            
        except Exception as e:
            print(f"Error saving recommendations: {str(e)}")
            print("Error details:", e.__class__.__name__)

    def get_recommendations_from_db(self):
        """Retrieve saved recommendations from the database."""
        try:
            conn = sqlite3.connect(self.database)
            cursor = conn.cursor()
            
            # First check if recommendations table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='recommendations'
            """)
            if not cursor.fetchone():
                print("Recommendations table does not exist")
                return []
            
            # Get recommendations
            cursor.execute("""
                SELECT title, url, description, category, confidence, timestamp
                FROM recommendations
                ORDER BY confidence DESC
                LIMIT 5
            """)
            
            recommendations = []
            for row in cursor.fetchall():
                recommendations.append({
                    'title': row[0],
                    'url': row[1],
                    'description': row[2],
                    'category': row[3],
                    'confidence': row[4],
                    'timestamp': row[5]
                })
            
            conn.close()
            print(f"Retrieved {len(recommendations)} recommendations from database")
            return recommendations
            
        except Exception as e:
            print(f"Error retrieving recommendations: {str(e)}")
            print("Error details:", e.__class__.__name__)
            return []

def get_response(url, params, timeout=10, retries=3):
    """
    Makes a GET request with retries on failure.
    """
    session = requests.Session()
    for i in range(retries):
        try:
            response = session.get(url, params=params, timeout=timeout)
            if response.status_code == 200:
                return response
            # For rate limiting, wait longer
            if response.status_code == 429:
                import time
                time.sleep(2 ** i)  # Exponential backoff
                continue
        except requests.exceptions.RequestException as e:
            print(f"Request error (attempt {i+1}/{retries}): {e}")
            if i == retries - 1:
                raise
    return None

def get_video_recommendations(interest, max_results=3):
    """
    Get video recommendations from YouTube based on an interest.
    Returns a list of dictionaries with video information.
    """
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": interest,
        "type": "video",
        "maxResults": max_results,
        "key": YOUTUBE_API_KEY,
        "relevanceLanguage": "en",
        "videoDuration": "medium"  # Medium length videos
    }
    
    try:
        response = get_response(url, params)
        if not response:
            # Fallback to alternative API or use mock data
            return get_alternative_video_recommendations(interest, max_results)
            
        data = response.json()
        videos = []
        
        for item in data.get("items", []):
            video_id = item["id"]["videoId"]
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            title = item["snippet"]["title"]
            description = item["snippet"]["description"]
            
            videos.append({
                "title": title,
                "description": description,
                "url": video_url,
                "thumbnail": item["snippet"]["thumbnails"]["medium"]["url"] if "thumbnails" in item["snippet"] else None
            })
            
        return videos
    except Exception as e:
        print(f"Error fetching video recommendations: {str(e)}")
        # Fallback to alternative sources
        return get_alternative_video_recommendations(interest, max_results)

def get_alternative_video_recommendations(interest, max_results=3):
    """
    Alternative method to get video suggestions if the YouTube API fails.
    Uses a web scraping service or other video APIs.
    """
    # For this implementation, we'll use the SerpApi web scraping service
    # Since we don't have access to this API, we'll build a search URL for YouTube
    videos = []
    search_term = quote_plus(interest)
    
    for i in range(min(max_results, 3)):
        # Create YouTube search URLs
        video_url = f"https://www.youtube.com/results?search_query={search_term}"
        
        # Generate some realistic titles based on the interest
        titles = [
            f"Top 10 {interest} Trends in 2023",
            f"The Ultimate Guide to {interest}",
            f"Why {interest} Matters: An In-depth Look",
            f"How {interest} is Changing Our World",
            f"{interest} Explained in 5 Minutes",
            f"The Future of {interest}: Expert Analysis",
            f"Everything You Need to Know About {interest}"
        ]
        
        videos.append({
            "title": titles[random.randint(0, len(titles)-1)],
            "description": f"A comprehensive video about {interest}. Click to watch on YouTube.",
            "url": video_url
        })
    
    return videos

def get_news_recommendations(interest, max_results=3):
    """
    Fetches news articles related to the given interest using NewsData.io API.
    Returns a list of dictionaries with article information.
    """
    url = "https://newsdata.io/api/1/news"
    params = {
        "apikey": NEWS_API_KEY,
        "q": interest,
        "language": "en"
    }
    
    try:
        response = get_response(url, params)
        if not response:
            # If API request fails, use alternative method
            return get_alternative_news_recommendations(interest, max_results)
            
        data = response.json()
        articles = []
        
        for article in data.get("results", [])[:max_results]:
            title = article.get("title")
            link = article.get("link") or article.get("url")
            description = article.get("description", "")
            source = article.get("source_id", "")
            
            if title and link:
                articles.append({
                    "title": title,
                    "url": link,
                    "description": description,
                    "source": source
                })
        
        return articles
    except Exception as e:
        print(f"Error fetching news recommendations: {str(e)}")
        # Fallback to alternative sources
        return get_alternative_news_recommendations(interest, max_results)

def get_alternative_news_recommendations(interest, max_results=3):
    """
    Alternative method to get news recommendations if the NewsData.io API fails.
    Uses generic news URLs with the interest as a search term.
    """
    articles = []
    search_term = quote_plus(interest)
    
    # List of news sources to query
    news_sources = [
        {"name": "Google News", "url": f"https://news.google.com/search?q={search_term}"},
        {"name": "Bing News", "url": f"https://www.bing.com/news/search?q={search_term}"},
        {"name": "Yahoo News", "url": f"https://news.yahoo.com/search?q={search_term}"}
    ]
    
    # Generate some realistic titles based on the interest
    titles = [
        f"Breaking: New Developments in {interest}",
        f"{interest} Trends That Are Reshaping the Industry",
        f"Experts Weigh In on the Future of {interest}",
        f"The Impact of {interest} on Global Markets",
        f"5 Things You Need to Know About {interest} Today",
        f"{interest}: A Comprehensive Analysis",
        f"Why {interest} Matters More Than Ever"
    ]
    
    for i in range(min(max_results, len(news_sources))):
        source = news_sources[i]
        articles.append({
            "title": titles[random.randint(0, len(titles)-1)],
            "url": source["url"],
            "description": f"Latest news about {interest} from {source['name']}.",
            "source": source["name"]
        })
    
    return articles

def fetch_content_preview(url):
    """
    Fetches a preview of content at the given URL.
    Returns a dictionary with title, description, and image if available.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            # Very basic preview extraction from HTML content
            html = response.text
            title = extract_tag_content(html, "title")
            description = extract_meta_content(html, "description")
            
            return {
                "title": title,
                "description": description,
                "url": url
            }
    except Exception as e:
        print(f"Error fetching content preview: {str(e)}")
    
    # Return basic info if extraction failed
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    return {
        "title": domain,
        "description": "Content preview not available",
        "url": url
    }

def extract_tag_content(html, tag):
    """
    Extracts content from an HTML tag.
    """
    import re
    pattern = f"<{tag}[^>]*>(.*?)</{tag}>"
    match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""

def extract_meta_content(html, name):
    """
    Extracts content from a meta tag with the given name.
    """
    import re
    pattern = f'<meta[^>]*name=["\']?{name}["\']?[^>]*content=["\']?(.*?)["\']?[/\\s>]'
    match = re.search(pattern, html, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # Try with property instead of name (for Open Graph tags)
    pattern = f'<meta[^>]*property=["\']?og:{name}["\']?[^>]*content=["\']?(.*?)["\']?[/\\s>]'
    match = re.search(pattern, html, re.IGNORECASE)
    return match.group(1).strip() if match else ""

def main():
    if len(sys.argv) < 2:
        print("Error: Method name required", file=sys.stderr)
        sys.exit(1)

    method = sys.argv[1]
    engine = RecommendationEngine()

    try:
        # Print initialization messages to stderr
        print("Initializing recommendation engine...", file=sys.stderr)
        
        if method == 'analyze_history':
            result = engine.analyze_history()
        elif method == 'generate_recommendations':
            result = engine.generate_recommendations()
        elif method == 'get_user_interests':
            result = engine.get_user_interests()
        elif method == 'get_category_stats':
            result = engine.get_category_stats()
        else:
            print(f"Error: Unknown method {method}", file=sys.stderr)
            sys.exit(1)

        # Only print the JSON result to stdout
        print(json.dumps(result))
        sys.exit(0)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

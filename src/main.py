import requests
from bs4 import BeautifulSoup
import sqlite3
import re
import os
import urllib3
from datetime import datetime

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# base url
BASE_URL = "https://www.dit.uoi.gr/"

# fetch url
GET_ARTICLES_URL = "https://www.dit.uoi.gr/getarticles.php"

# categories with form data
CATEGORIES = {
    "Διαλεξη": "category=Διαλεξη",
    "Εργαστηριο": "category=Εργαστηριο",
    "Μαθημα": "category=Μαθημα",
    "Γραμματειας / Τμημα": "category=Γραμματειας / Τμημα",
    "Φορεις του ΤΕΙ": "category=Φορεις του ΤΕΙ",
    "Λοιπες Ανακοινωσεις": "category=Λοιπες Ανακοινωσεις",
    "Μεταπτυχιακο Προγραμμα Σπουδων": "category=Μεταπτυχιακο Προγραμμα Σπουδων",
    "Εκδηλωσεις": "category=Εκδηλωσεις",
    "Γραμματειας / Τμημα, Πρωτοετεις": "category=Γραμματειας / Τμημα, Πρωτοετεις"
}

# manipulate browser headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": "https://www.dit.uoi.gr/articles.php"
}

def extract_id_from_link(link):
    """Extract the ID from the link."""
    match = re.search(r"id=(\d+)", link)
    return int(match.group(1)) if match else None

def check_directory(filepath):
    """Ensure the directory for the given filepath exists."""
    directory = os.path.dirname(filepath)
    if not os.path.exists(directory):
        os.makedirs(directory)

def init_database(db_path):
    """Initialize the SQLite database with the articles table."""
    check_directory(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create articles table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            link TEXT NOT NULL,
            date TEXT NOT NULL,
            category TEXT NOT NULL,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"Database initialized at {db_path}")

def get_latest_id(db_path):
    """Get the latest article ID from the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('SELECT MAX(id) FROM articles')
    result = cursor.fetchone()[0]
    conn.close()
    
    return result if result else 0

def fetch_new_articles(db_path):
    """Fetch only new articles based on the global latest ID."""
    # Get the latest ID from database
    latest_id = get_latest_id(db_path)
    print(f"Latest article ID in database: {latest_id}")

    session = requests.Session()
    session.headers.update(HEADERS)
    new_articles = []
    max_id = latest_id

    for category_name, category_value in CATEGORIES.items():
        print(f"Fetching new articles for category: {category_name}")
        category_count = 0
        try:
            # post (disable SSL verification for sites with certificate issues)
            response = session.post(GET_ARTICLES_URL, data={"category": category_value.split("=")[1]}, verify=False)
            print(f"Response Status Code: {response.status_code}")

            if response.status_code != 200:
                print(f"Failed to fetch category: {category_name}")
                continue

            # Parse html response (use html.parser as fallback if lxml not installed)
            soup = BeautifulSoup(response.text, "html.parser")

            # locate content table
            table = soup.find("table", {"class": "table table-striped"})
            if not table:
                print(f"No table found for category: {category_name}")
                continue

            # The HTML has malformed <tr> tags, so we need to find all <td> elements
            # and group them by pairs
            all_tds = table.find_all("td")
            print(f"Found {len(all_tds)} <td> elements for {category_name}")
            
            valid_rows = 0
            # Process td elements in pairs
            i = 0
            while i < len(all_tds):
                td = all_tds[i]
                
                # Skip header rows (colspan=2)
                if td.get('colspan'):
                    i += 1
                    continue
                
                # Check if this is a link td (article title)
                link_tag = td.find("a")
                if link_tag and i + 1 < len(all_tds):
                    # Next td should be the date
                    date_td = all_tds[i + 1]
                    valid_rows += 1
                    date_td = all_tds[i + 1]
                    valid_rows += 1
                    
                    title = link_tag.text.strip()
                    link = BASE_URL + link_tag["href"]
                    article_id = extract_id_from_link(link)
                    date = date_td.text.strip().strip("()")

                    # Skip if we already have this article
                    if article_id and article_id <= latest_id:
                        i += 2
                        continue

                    if article_id:  # Only add if we successfully extracted an ID
                        new_articles.append({
                            "id": article_id,
                            "title": title,
                            "link": link,
                            "date": date,
                            "category": category_name
                        })
                        max_id = max(max_id, article_id)
                        category_count += 1
                    
                    i += 2  # Move to next pair of tds
                else:
                    i += 1

            print(f"Valid rows with 2 columns: {valid_rows}")
            print(f"Found {category_count} articles in {category_name}")

        except Exception as e:
            print(f"Error fetching category {category_name}: {e}")

    return new_articles


def save_articles_to_db(db_path, articles):
    """Save articles to SQLite database."""
    if not articles:
        print("No new articles to save.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    saved_count = 0
    for article in articles:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO articles (id, title, link, date, category, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                article['id'],
                article['title'],
                article['link'],
                article['date'],
                article['category'],
                datetime.now().isoformat()
            ))
            if cursor.rowcount > 0:
                saved_count += 1
        except sqlite3.IntegrityError:
            # Article already exists
            continue
    
    conn.commit()
    conn.close()
    
    print(f"Saved {saved_count} new articles to database.")
    return saved_count

def get_article_count(db_path):
    """Get total number of articles in database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM articles')
    count = cursor.fetchone()[0]
    conn.close()
    return count

# Database path
db_path = "./database/news.db"

# Initialize database
init_database(db_path)

# Fetch and save new articles
print(f"Total articles in database: {get_article_count(db_path)}")
new_articles = fetch_new_articles(db_path)
save_articles_to_db(db_path, new_articles)
print(f"Total articles in database: {get_article_count(db_path)}")

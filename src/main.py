import requests
import os
from bs4 import BeautifulSoup
import json

# Base URL
BASE_URL = "https://www.dit.uoi.gr/"

# article fetch url
GET_ARTICLES_URL = "https://www.dit.uoi.gr/getarticles.php"

# all the categories
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

# simulate browser headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": "https://www.dit.uoi.gr/articles.php"
}

def fetch_articles():
    """News parser"""
    session = requests.Session()
    session.headers.update(HEADERS)
    all_articles = {}

    for category_name, category_value in CATEGORIES.items():
        print(f"Fetching news for category: {category_name}")
        try:
            # send post request
            response = session.post(GET_ARTICLES_URL, data={"category": category_value.split("=")[1]})
            print(f"Response Status Code: {response.status_code}")

            if response.status_code != 200:
                print(f"Failed to fetch category: {category_name}")
                continue

            # Parse the response HTML
            soup = BeautifulSoup(response.text, "lxml")

            # Locate the table containing the articles
            table = soup.find("table", {"class": "table table-striped"})
            if not table:
                print(f"No table found for category: {category_name}")
                continue

            category_articles = []

            # Extract articles from table rows
            for row in table.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) == 2:  # only scrape news rows
                    link_tag = cols[0].find("a")
                    if link_tag:
                        title = link_tag.text.strip()
                        link = BASE_URL + link_tag["href"]  # add base url to json
                        date = cols[1].text.strip().strip("()")  # Clean up date data
                        category_articles.append({
                            "title": title,
                            "link": link,
                            "date": date
                        })

            all_articles[category_name] = category_articles

        except Exception as e:
            print(f"Error fetching category {category_name}: {e}")

    return all_articles



##############
#    MAIN    #
##############

output_dir = "./json_dump"
os.makedirs(output_dir, exist_ok=True)

output_file = os.path.join(output_dir, "news_data.json")

articles_by_category = fetch_articles()

# Save to JSON
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(articles_by_category, f, ensure_ascii=False, indent=4)

print(f"News articles saved to {output_file}")


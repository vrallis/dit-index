import requests
from bs4 import BeautifulSoup
import json
import re
import os

# base url
BASE_URL = "https://www.dit.uoi.gr/"

# fetch url
GET_ARTICLES_URL = "https://www.dit.uoi.gr/getarticles.php"

MEILISEARCH_URL = "http://localhost:7700"
INDEX_NAME = "news"

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

def ensure_directory_exists(filepath):
    directory = os.path.dirname(filepath)
    if not os.path.exists(directory):
        os.makedirs(directory)

import os

def ensure_directory_exists(filepath):
    """Ensure the directory for the given filepath exists."""
    directory = os.path.dirname(filepath)
    if not os.path.exists(directory):
        os.makedirs(directory)

def fetch_new_articles(latest_id_file):
    """Fetch only new articles based on the global latest ID."""
    # Ensure the directory exists
    ensure_directory_exists(latest_id_file)

    # Load the latest global ID
    try:
        with open(latest_id_file, "r", encoding="utf-8") as f:
            latest_id = int(f.read().strip())
    except FileNotFoundError:
        print(f"{latest_id_file} not found. Starting fresh.")
        latest_id = 0

    session = requests.Session()
    session.headers.update(HEADERS)
    new_articles = []
    max_id = latest_id

    for category_name, category_value in CATEGORIES.items():
        print(f"Fetching new articles for category: {category_name}")
        try:
            # post
            response = session.post(GET_ARTICLES_URL, data={"category": category_value.split("=")[1]})
            print(f"Response Status Code: {response.status_code}")

            if response.status_code != 200:
                print(f"Failed to fetch category: {category_name}")
                continue

            # Parse html response
            soup = BeautifulSoup(response.text, "lxml")

            # locate content table
            table = soup.find("table", {"class": "table table-striped"})
            if not table:
                print(f"No table found for category: {category_name}")
                continue

            # extract news articles
            for row in table.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) == 2:
                    link_tag = cols[0].find("a")
                    if link_tag:
                        title = link_tag.text.strip()
                        link = BASE_URL + link_tag["href"]
                        article_id = extract_id_from_link(link)
                        date = cols[1].text.strip().strip("()")

                        # stop fetching
                        if article_id <= latest_id:
                            break

                        new_articles.append({
                            "id": article_id,
                            "title": title,
                            "link": link,
                            "date": date,
                            "category": category_name
                        })
                        max_id = max(max_id, article_id)

        except Exception as e:
            print(f"Error fetching category {category_name}: {e}")

    # update latest id
    with open(latest_id_file, "w", encoding="utf-8") as f:
        f.write(str(max_id))

    return new_articles


def update_json_with_new_articles(existing_file, output_file, latest_id_file):
    """Detect and add new articles to the JSON."""
    try:
        # load existing json data
        with open(existing_file, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
    except FileNotFoundError:
        print(f"{existing_file} not found. Creating a new one.")
        existing_data = []

    # fetch new articles
    new_articles = fetch_new_articles(latest_id_file)

    # append new articles to existing data
    existing_data.extend(new_articles)

    # save updated json
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=4)

    print(f"Updated JSON saved to {output_file}")

def upload_to_meilisearch(json_file, meilisearch_url, index_name):
    """Upload updated articles to Meilisearch."""
    with open(json_file, "r", encoding="utf-8") as f:
        articles = json.load(f)

    response = requests.post(
        f"{meilisearch_url}/indexes/{index_name}/documents",
        headers={"Content-Type": "application/json"},
        json=articles
    )

    if response.status_code == 202:
        print(f"Successfully uploaded to Meilisearch. Task UID: {response.json().get('taskUid')}")
    else:
        print(f"Failed to upload to Meilisearch: {response.text}")

# paths
existing_file = "./json_dump/news_data.json"
output_file = "./json_dump/news_data.json"
latest_id_file = "./json_dump/latest_id.txt"

# update JSON with new articles
update_json_with_new_articles(existing_file, output_file, latest_id_file)

# upload the updated JSON to Meilisearch
upload_to_meilisearch(output_file, MEILISEARCH_URL, INDEX_NAME)

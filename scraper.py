import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
from selenium.webdriver.chrome.service import Service

def scrape_marketplace(url):
    """
    Scrape product info from Verizon Marketplace.
    Returns a DataFrame with columns: Product Name, Category, Description, Key Features, etc.
    """
    logging.info(f"Starting to scrape products from {url}")
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
    except Exception as e:
        logging.error(f"Failed to fetch marketplace page: {e}")
        return pd.DataFrame()
    soup = BeautifulSoup(resp.text, "html.parser")

    # You must inspect the page and update selectors as needed!
    products = []
    for card in soup.find_all("div", class_="VZMH-card"):  # Example class, update as needed
        name = card.find("h2").get_text(strip=True) if card.find("h2") else ""
        desc = card.find("p").get_text(strip=True) if card.find("p") else ""
        category = card.find("span", class_="VZMH-category").get_text(strip=True) if card.find("span", class_="VZMH-category") else ""
        features = ", ".join([li.get_text(strip=True) for li in card.find_all("li")])
        products.append({
            "Product Name": name,
            "Category": category,
            "Description": desc,
            "Key Features": features
        })
    logging.info(f"Found {len(products)} products.")
    return pd.DataFrame(products)

def save_products_csv(df, path):
    df.to_csv(path, index=False)

def scrape_marketplace_selenium_bs4(url, output_csv="data/products.csv", headless=True, driver_path="chromedriver"):
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    service = Service(driver_path)
    driver = webdriver.Chrome(service=service, options=options)
    driver.get(url)

    # Wait for products to load (adjust time or use WebDriverWait for better reliability)
    time.sleep(10)

    # Get the fully rendered HTML
    html = driver.page_source
    driver.quit()

    # Parse with BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("[class*=product-card], [data-testid*=product-card]")

    products = []
    for card in cards:
        name = card.find(["h2", "h3"]).get_text(strip=True) if card.find(["h2", "h3"]) else ""
        desc = card.find("p").get_text(strip=True) if card.find("p") else ""
        category = card.find(attrs={"class": lambda x: x and "category" in x}).get_text(strip=True) if card.find(attrs={"class": lambda x: x and "category" in x}) else ""
        features = ", ".join([li.get_text(strip=True) for li in card.find_all("li")])
        products.append({
            "Product Name": name,
            "Category": category,
            "Description": desc,
            "Key Features": features
        })

    df = pd.DataFrame(products)
    df.to_csv(output_csv, index=False)
    print(f"Scraped {len(df)} products. Saved to {output_csv}")
    return df

if __name__ == "__main__":
    scrape_marketplace_selenium_bs4(
        url="https://www.verizon.com/business/shop/marketplace",
        output_csv="data/products.csv",
        headless=False,  # Set to True to run without opening a browser window
        driver_path=r"C:\Users\Hp\Downloads\chromedriver_win32\chromedriver.exe"  # Update if your chromedriver is elsewhere
    ) 
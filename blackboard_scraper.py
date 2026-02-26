import json
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

BLACKBOARD_URL = "https://kettering.blackboard.com"  # Confirmed for Kettering
LOGIN_URL = f"{BLACKBOARD_URL}/ultra"  # Use /ultra root, not /login, to allow SSO redirect

USERNAME = "korn6011"  # Replace with your actual username
PASSWORD = "BariaImbe_212"  # Replace with your actual password

OUTPUT_FILE = "assignments.json"

def init_browser():
    options = Options()
    # options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-3d-apis")
    driver = webdriver.Chrome(options=options)
    return driver

def login(driver):
    driver.get(LOGIN_URL)

    try:
        # Wait for redirection to Kettering's IdP
        WebDriverWait(driver, 15).until(EC.url_contains("idp.kettering.edu"))

        print("🌐 Reached IdP login page. Submitting credentials...")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        driver.find_element(By.NAME, "username").send_keys(USERNAME)
        driver.find_element(By.NAME, "password").send_keys(PASSWORD)

        # If there's a popup (e.g., cookie consent), close it
        try:
            ok_button = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, '//button[text()="OK" or text()="Ok" or text()="ok"]'))
            )
            ok_button.click()
        except:
            pass

        # Look for submit button with value="Sign In"
        try:
            submit = driver.find_element(By.XPATH, '//input[@value="Sign In"]')
            driver.execute_script("arguments[0].click();", submit)
        except:
            driver.find_element(By.NAME, "submit").click()

    except Exception as e:
        print("⚠️ Could not auto-login. Please log in manually if required.")

    print("🔐 Waiting for Blackboard dashboard after login...")
    WebDriverWait(driver, 180).until(EC.url_contains("blackboard.kettering.edu"))
    print("✅ Login complete.")

def get_course_links(driver):
    driver.get(f"{BLACKBOARD_URL}/ultra/course")
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(5)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    course_links = []
    for link in soup.find_all("a", href=True):
        href = link['href']
        if "/ultra/courses/" in href and href not in course_links:
            course_links.append(BLACKBOARD_URL + href)
    return list(set(course_links))

def get_assignments_from_course(driver, course_url):
    driver.get(course_url + "/stream")
    time.sleep(5)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    assignments = []
    cards = soup.find_all("div", class_="upcoming-assignment")
    if not cards:
        cards = soup.find_all("span", class_="item-name")

    for item in cards:
        parent = item.find_parent("a")
        if not parent:
            continue

        title = item.text.strip()
        href = parent['href'] if parent else ""
        due = "Unknown"

        due_container = item.find_parent().find_next("div")
        if due_container:
            possible_due = due_container.text.strip()
            if "Due" in possible_due:
                due = possible_due.replace("Due:", "").strip()

        assignments.append({
            "course": course_url.split("/")[-1],
            "title": title,
            "due": due,
            "submitted": False
        })
    return assignments

def fetch_assignments():
    driver = init_browser()
    login(driver)

    course_links = get_course_links(driver)
    all_assignments = []

    for course in course_links:
        course_assignments = get_assignments_from_course(driver, course)
        all_assignments.extend(course_assignments)

    driver.quit()

    for assignment in all_assignments:
        try:
            dt = datetime.strptime(assignment['due'], "%b %d, %Y, %I:%M %p")
            assignment['due'] = dt.isoformat()
        except Exception:
            pass

    with open(OUTPUT_FILE, "w") as f:
        json.dump(all_assignments, f, indent=2)

    return all_assignments

if __name__ == "__main__":
    tasks = fetch_assignments()
    print(json.dumps(tasks, indent=2))

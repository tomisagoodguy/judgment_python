# finlab-format

import selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, timedelta
import time
from bs4 import BeautifulSoup
import json
import re
import requests
import os
from selenium.webdriver.chrome.options import Options
import random  # 匯入 random 模組以實現隨機延遲


def roc_year_converter(dt: datetime):
    """
    doc: 將西元年轉換為民國年、月、日。
    :param dt: datetime 物件。
    :return: (民國年, 月, 日) 的元組。
    """
    return dt.year - 1911, dt.month, dt.day


def sanitize_filename(title: str) -> str:
    """
    doc: 清理字串，使其可用作安全的檔案名稱。
    :param title: 原始標題字串。
    :return: 清理後的檔案名稱字串。
    """
    s = re.sub(r'[\\/:*?"<>|]', '', title)
    s = s.replace(' ', '_')
    s = s.strip()
    if len(s) > 100:
        s = s[:100]
    return s


def parse_judgment_list(list_html: str):
    """
    doc: 解析判決列表頁面的HTML，提取所有判決的連結和標題。
    :param list_html: 判決列表頁面的 HTML 原始碼字串。
    :return: 一個包含判決資訊（連結與標題）的字典列表。
    """
    print("步驟 6: 正在解析判決列表，提取各篇判決的連結和標題...")
    soup = BeautifulSoup(list_html, 'html.parser')
    judgments_info = []

    link_tags = soup.find_all(
        'a', href=lambda href: href and 'data.aspx' in href)

    for tag in link_tags:
        full_link = "https://judgment.judicial.gov.tw/FJUD/" + tag['href']
        title = tag.text.strip()
        judgments_info.append({'link': full_link, 'title': title})

    if not judgments_info:
        print("在查詢結果頁面中找不到任何判決連結。")
    else:
        print(f"解析完成！共找到 {len(judgments_info)} 筆判決連結。")

    return judgments_info


def get_full_text(driver: webdriver.Chrome, judgment_url: str, judgment_title: str):
    """
    doc: 訪問單一判決的連結，抓取其完整內文，並儲存為Markdown和PDF。
    :param driver: Selenium WebDriver 實例。
    :param judgment_url: 單一判決的 URL。
    :param judgment_title: 判決的標題，用於命名檔案。
    :return: 判決的純文字內文。
    """
    try:
        driver.get(judgment_url)
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        content_div = soup.find('div', class_='htmlcontent')

        # --- 程式碼修改處 (Markdown 換行) ---
        # 使用 .get_text(separator='\\n') 來保留 HTML 中的換行
        # 這會將 <br> 或區塊級標籤轉換為換行符，使輸出的 .md 檔案更易於閱讀
        full_text = content_div.get_text(
            separator='\n').strip() if content_div else "無法找到內文區塊。"

        sanitized_title = sanitize_filename(judgment_title)

        markdown_dir = "markdown_judgments"
        pdf_dir = "pdf_judgments"

        os.makedirs(markdown_dir, exist_ok=True)
        os.makedirs(pdf_dir, exist_ok=True)

        # 儲存為 Markdown
        md_filename = os.path.join(markdown_dir, f"{sanitized_title}.md")
        with open(md_filename, 'w', encoding='utf-8') as f:
            f.write(full_text)
        print(f"已將判決全文儲存至 {md_filename}。")

        # 提取 PDF 連結並下載
        pdf_link_tag = soup.find('a', id='hlExportPDF')
        if pdf_link_tag and pdf_link_tag.get('href'):
            pdf_relative_url = pdf_link_tag.get('href')
            pdf_url = "https://judgment.judicial.gov.tw" + pdf_relative_url

            pdf_filename = os.path.join(pdf_dir, f"{sanitized_title}.pdf")
            try:
                pdf_response = requests.get(pdf_url, stream=True)
                pdf_response.raise_for_status()

                with open(pdf_filename, 'wb') as f:
                    for chunk in pdf_response.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"已將判決PDF儲存至 {pdf_filename}。")
            except requests.exceptions.RequestException as e:
                print(f"下載PDF失敗: {pdf_url}, 錯誤: {e}")
        else:
            print("未找到PDF下載連結。")

        return full_text

    except Exception as e:
        print(f"抓取內文失敗: {judgment_url}, 錯誤: {e}")
        return "抓取失敗。"


def scrape_judicial_yuan_advanced(driver: webdriver.Chrome, keyword: str, years: int = 3):
    """
    doc: 執行司法院進階查詢。
    :param driver: Selenium WebDriver 實例。
    :param keyword: 查詢關鍵字。
    :param years: 查詢年限（從現在往前推算）。
    :return: 查詢結果頁面的 HTML 原始碼。
    """
    url = 'https://judgment.judicial.gov.tw/FJUD/Default_AD.aspx'
    print("步驟 1: 正在取得進階查詢頁面...")
    driver.get(url)

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, 'jud_kw'))
    )

    end_date = datetime.now()
    start_date = end_date - timedelta(days=365 * years)
    roc_start_y, roc_start_m, roc_start_d = roc_year_converter(start_date)
    roc_end_y, roc_end_m, roc_end_d = roc_year_converter(end_date)

    driver.find_element(By.ID, 'jud_kw').send_keys(keyword)
    driver.find_element(By.ID, 'dy1').send_keys(str(roc_start_y))
    driver.find_element(By.ID, 'dm1').send_keys(str(roc_start_m).zfill(2))
    driver.find_element(By.ID, 'dd1').send_keys(str(roc_start_d).zfill(2))
    driver.find_element(By.ID, 'dy2').send_keys(str(roc_end_y))
    driver.find_element(By.ID, 'dm2').send_keys(str(roc_end_m).zfill(2))
    driver.find_element(By.ID, 'dd2').send_keys(str(roc_end_d).zfill(2))

    civil_checkbox = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (By.XPATH, '//input[@name="jud_sys" and @value="V"]'))
    )
    if not civil_checkbox.is_selected():
        driver.execute_script("arguments[0].click();", civil_checkbox)
        print("已透過 JavaScript 點擊 '民事' 案件類別。")

    print(f"步驟 2: 準備使用關鍵字 '{keyword}' 查詢...")
    print("步驟 3: 正在送出查詢請求...")

    search_button = driver.find_element(By.ID, 'btnQry')
    search_button.click()

    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, 'iframe-data'))
        )
        print("查詢成功！已取得結果頁面。")
    except Exception as e:
        print(f"等待結果頁面載入時發生錯誤或超時: {e}")
        print("可能沒有找到結果，或者網站結構改變。")

    return driver.page_source


if __name__ == '__main__':
    """
    doc: 主程式執行入口。
    """
    chrome_options = Options()
    # chrome_options.add_argument('--headless')
    chrome_options.add_argument("--window-size=1920,1080")
    # 避免被部分網站偵測為機器人
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(60)

    # --- 程式碼修改處 (關鍵字建議) ---
    suggested_keywords = [
        "prp 韌帶", "prp 半月板", "半月板破裂", "半月板障礙",
        "膝部扭傷", "十字韌帶破裂", "半月板撕裂", "創傷性關節病變"
    ]
    print("--- 常用關鍵字建議 ---")
    for i, kw in enumerate(suggested_keywords):
        print(f"{i+1}. {kw}")
    print("----------------------")

    search_keyword = input("請輸入搜尋關鍵字 (可從上方建議列表複製): ")
    try:
        search_years = int(input("請輸入搜尋年限 (例如: 3): "))
    except ValueError:
        print("年限輸入無效，將使用預設值 3 年。")
        search_years = 3

    all_judgments_data = []
    page_count = 1

    try:
        search_page_html = scrape_judicial_yuan_advanced(
            driver, keyword=search_keyword, years=search_years)

        if "id=\"iframe-data\"" not in search_page_html:
            raise Exception("查詢結果頁面HTML中未包含 'iframe-data'，查詢可能失敗或無結果。")

        soup = BeautifulSoup(search_page_html, 'html.parser')
        iframe = soup.find('iframe', id='iframe-data')

        if not (iframe and iframe.get('src')):
            if "查無資料" in search_page_html:
                print("查無資料，程式即將結束。")
            else:
                raise Exception("未找到 iframe 或 iframe 缺少 src 屬性。")
        else:
            iframe_src = iframe.get('src')
            current_list_page_url = f"https://judgment.judicial.gov.tw/FJUD/{iframe_src}"
            print(f"成功進入判決列表 iframe: {current_list_page_url}")

            # --- 程式碼修改處 (溫和爬蟲策略) ---
            # 在開始爬取列表前，先隨機延遲一下
            initial_delay = random.uniform(2.0, 4.0)
            print(f"首次進入列表，隨機延遲 {initial_delay:.2f} 秒...")
            time.sleep(initial_delay)

            while True:
                print(f"--- 正在處理第 {page_count} 頁 ---")
                driver.get(current_list_page_url)

                try:
                    WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located(
                            (By.XPATH, "//a[contains(@href, 'data.aspx')]"))
                    )
                except Exception:
                    print(f"在第 {page_count} 頁等待判決連結超時，可能已是最後一頁。")
                    break

                list_html = driver.page_source
                judgments_info = parse_judgment_list(list_html)

                if not judgments_info:
                    print(f"第 {page_count} 頁沒有找到判決連結，抓取結束。")
                    break

                for judgment in judgments_info:
                    print(f"正在抓取判決: {judgment['title']} ({judgment['link']})")
                    full_text = get_full_text(
                        driver, judgment['link'], judgment['title'])
                    all_judgments_data.append({
                        "篇數": len(all_judgments_data) + 1,
                        "連結": judgment['link'],
                        "標題": judgment['title'],
                        "內文": full_text
                    })
                    # --- 程式碼修改處 (溫和爬蟲策略) ---
                    # 在每次抓取單篇判決後，加入 1.5 到 3.0 秒的隨機延遲
                    delay = random.uniform(1.5, 3.0)
                    print(f"...延遲 {delay:.2f} 秒...")
                    time.sleep(delay)

                list_soup = BeautifulSoup(list_html, 'html.parser')
                next_page_link_tag = list_soup.find('a', id='hlNext')

                if next_page_link_tag and next_page_link_tag.get('href'):
                    next_page_relative_url = next_page_link_tag.get('href')
                    base_list_url = current_list_page_url.split('?')[0]
                    current_list_page_url = f"{base_list_url}{next_page_relative_url}"
                    print(f"找到下一頁，準備前往: {current_list_page_url}")
                    page_count += 1
                    # --- 程式碼修改處 (溫和爬蟲策略) ---
                    # 換頁時，加入 2 到 4 秒的隨機延遲
                    page_delay = random.uniform(2.0, 4.0)
                    print(f"換頁延遲 {page_delay:.2f} 秒...")
                    time.sleep(page_delay)
                else:
                    print("沒有找到下一頁連結，所有頁面已抓取完畢。")
                    break

            print("\n--- 所有判決抓取完畢 ---")
            print(f"總共抓取到 {len(all_judgments_data)} 筆判決。")

            if all_judgments_data:
                json_filename = "judgments_data.json"
                with open(json_filename, 'w', encoding='utf-8') as f:
                    json.dump(all_judgments_data, f,
                              ensure_ascii=False, indent=4)
                print(f"\n已將所有判決資料儲存至 {json_filename}。")

    except Exception as e:
        print(f"執行過程中發生錯誤: {e}")
    finally:
        driver.quit()
        print("瀏覽器已關閉。")

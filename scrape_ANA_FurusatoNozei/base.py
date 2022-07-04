import json
from typing import Pattern
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.select import Select
from time import sleep
import sys
import os
import traceback
import re


def headless_chrome():
    is_dev = os.environ["HOME"]
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--lang=ja-JP")
    options.add_argument("--single-process")
    # options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280x1696")
    options.add_argument("--disable-application-cache")
    options.add_argument("--disable-infobars")
    # options.add_argument("--hide-scrollbars")
    # options.add_argument("--enable-logging")
    # options.add_argument("--log-level=0")
    # options.add_argument("--ignore-certificate-errors")
    options.add_argument("--homedir=/tmp")
    options.add_argument("start-maximized")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-dev-shm-usage")

    if is_dev == '/Users/hosodaraimu':
        driver = webdriver.Chrome(
            "/usr/local/bin/chromedriver",
            options=options)
    else:
        options.binary_location = "/opt/headless/python/bin/headless-chromium"
        driver = webdriver.Chrome(
            executable_path="/opt/headless/python/bin/chromedriver",
            chrome_options=options
        )

    return driver


def is_findable_element(driver, attribute, attribute_value, target=None):
    #  print(attribute_value + "is_findable_element入った")
    driver.implicitly_wait(1)
    attribute = attribute.upper()

    if target and attribute == "XPATH":
        raise Exception("XPATH is invaild to find in target")

    result = driver.find_elements(getattr(By, attribute), attribute_value)
    # print(len(result))

    return bool(result)


def scrape_shop_list():
    try:
        print("start scraping shop_list")
        driver = headless_chrome()
        driver.implicitly_wait(3)

        shop_list = []
        scr_err_cnt = 0
        page_num = 1
        max_page_num = 2
        domain = "thebase.in"
        search_word = "アクセサリー"
        # base_url_list = ["developers.thebase.in", "design.thebase.in", "lp.thebase.in"]

        driver.get("https://www.google.co.jp/")
        search_bar = driver.find_element_by_name("q")
        search_bar.send_keys(f"site:*.{domain} {search_word}")
        search_bar.send_keys(Keys.ENTER)

        top_url = driver.current_url

        if "https://www.google.com/sorry/index" in top_url:
            print("google アクセスブロック 処理終了")
            return shop_list, scr_err_cnt

        while page_num <= max_page_num:
            elements = driver.find_elements_by_xpath(
                "//div[@class='yuRUbf']/a")

            if not elements:
                print("検索結果のurl(elements)取得できず")
                break

            urls = [i.get_attribute("href") for i in elements]
            for url in urls:
                print("ショップへ")

                try:
                    driver.get(url)
                except Exception as e:
                    print(f"エラー! navigate.to url: {url} 次のショップへ遷移")
                    continue

                if is_findable_element(driver, "name", "author") and driver.find_element_by_name("author").get_attribute("content") == "BASE":
                    print("BASEのサイトに入ったので次のショップへ遷移")
                    continue

                if not is_findable_element(driver, "xpath", "//a[contains(@href,'base')]"):
                    print("Base以外のサイトに入ったので次のショップへ遷移")
                    continue

                try:
                    current_url = driver.current_url
                    pattern1 = re.compile("https?://[^/]+/.+")
                    result = re.match(pattern1, current_url)
                    if result:
                        pattern2 = re.compile("https?://[^/]+/")
                        home_url = re.match(pattern2, current_url).group()
                        driver.get(home_url)
                        shop_url = home_url
                    else:
                        shop_url = home_url

                    shop_name = driver.title
                    print(shop_name)
                    shop_description = driver.find_element_by_name(
                        "description").get_attribute("content")
                    contact_url = driver.find_element_by_xpath(
                        "//a[contains(@href,'/inquiry/')]").get_attribute("href")
                    if is_findable_element(driver, "class_name", "logoImage"):
                        shop_img_url = driver.find_element_by_class_name(
                            "logoImage").get_attribute("src")
                    elif is_findable_element(driver, "class_name", "cot-shopLogoImage"):
                        shop_img_url = driver.find_element_by_class_name(
                            "cot-shopLogoImage").get_attribute("src")
                    else:
                        shop_img_url = ""

                    shop_dict = {"shop_name": shop_name, "shop_description": shop_description,
                                 "shop_url": shop_url, "contact_url": contact_url, "shop_img_url": shop_img_url}
                    shop_list.append(shop_dict)
                except Exception as e:
                    print(
                        f"スクレイピングエラー ショップ名: {shop_name}, URL: {shop_url} 次のショップへ")
                    print(traceback.format_exception_only(
                        type(e), e)[0].rstrip("\n"))
                    scr_err_cnt += 1
                    continue

            driver.get(top_url)
            page_num += 1
            print(f"next page_num: {page_num}")
            page_num_str = str(page_num)
            if is_findable_element(driver, "link_text", page_num_str):
                print("次のページへ遷移")
                driver.find_element_by_link_text(page_num_str).click()
            else:
                print("次ページなし スクレイピング終了")
                list(set(shop_list))
                break
    except Exception as e:
        print("fatalエラー")
        driver.quit()
        raise
    else:
        print("全ページスクレイピング完了")
        driver.quit()
        return shop_list, scr_err_cnt


def save_shoplist(shop_list):
    print("shop_list")
    print(shop_list)


def main():
    shop_list, scr_err_cnt = scrape_shop_list()

    if shop_list:
        print("get result")
        # print(f"shop_list: {shop_list}")
        # print(f"scr_err_cnt: {scr_err_cnt}")
        # save_shoplist(shop_list)
        return True
    else:
        print("no result")
        res = {}
        return False


def lambda_handler(event, context):
    try:
        result = main()

        if result:
            print("get result")
            res = {
                "statusCode": 200,
                "body": json.dumps({
                    "message": "success!",
                })
            }
        else:
            print("no result")
            res = {
                "statusCode": 400,
                "body": json.dumps({
                    "message": "failed!",
                })
            }

        return res
    except Exception as e:
        print("----------")
        type_, value_, traceback_ = sys.exc_info()
        # print(type_)
        # print(value_)
        # print(traceback_)
        print(traceback.format_exception(type_, value_, traceback_))
        print("----------")
        return

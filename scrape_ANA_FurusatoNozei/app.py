import json
# from operator import neg
import sys
import os
import traceback
import re
# from turtle import end_fill
import uuid
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome import options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.select import Select
import boto3
import pytz


def get_driver():
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--lang=ja-JP")
        options.add_argument("--single-process")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1280x1696")
        options.add_argument("--disable-application-cache")
        options.add_argument("--disable-infobars")
        # options.add_argument("--disable-setuid-sandbox")
        # options.add_argument('--disable-features=VizDisplayCompositor')
        # options.add_argument("--hide-scrollbars")
        # options.add_argument("--enable-logging")
        # options.add_argument("--log-level=0")
        # options.add_argument("--ignore-certificate-errors")
        options.add_argument("--homedir=/tmp")
        options.add_argument("start-maximized")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-dev-shm-usage")

        options.binary_location = "/opt/python/headless-chromium"
        driver = webdriver.Chrome(
            executable_path="/opt/python/chromedriver",
            chrome_options=options
        )
        print("headless_chrome終わり")
    except Exception as e:
        raise

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


def scrape_shop_info(driver):
    current_url = driver.current_url
    pattern1 = re.compile("https?://[^/]+/.+")
    result = re.match(pattern1, current_url)

    if result:
        print(f"current_url--------------------: {current_url}")
        pattern2 = re.compile("https?://[^/]+/")
        home_url = re.match(pattern2, current_url).group()
        driver.get(home_url)
        shop_url = home_url
    else:
        shop_url = current_url

    shop_name = driver.title

    try:
        shop_description = driver.find_element_by_name(
            "description").get_attribute("content")
        contact_url = driver.find_element_by_xpath(
            "//a[contains(@href,'/inquiry/')]").get_attribute("href")
        shop_img_url = ""
        if is_findable_element(driver, "class_name", "logoImage"):
            shop_img_url = driver.find_element_by_class_name(
                "logoImage").get_attribute("src")
        elif is_findable_element(driver, "class_name", "cot-shopLogoImage"):
            shop_img_url = driver.find_element_by_class_name(
                "cot-shopLogoImage").get_attribute("src")
    except Exception as e:
        raise e

    shop_dict = {"shop_name": shop_name, "shop_description": shop_description, "shop_url": shop_url, "contact_url": contact_url, "shop_img_url": shop_img_url}
    print(f"shop_dict: {shop_dict}")

    return shop_dict


def scrape_ranking():
    gift_list = []
    try:
        print("start scraping ranking")
        driver = get_driver()
        driver.implicitly_wait(3)

        driver.get("https://furusato.ana.co.jp/products/ranking.php")
        items = driver.find_elements_by_xpath("//*[@id=\"ranking_weekly\"]/ul/li")
        items_count = len(items)
        n = 1
        while n <= items_count:
            print(f'ランキング: {n}位')
            if is_findable_element(driver,'id',f'ranking_weekly_{n}'):
                ranking = n
                gift_area = driver.find_element_by_xpath(f"//*[@id=\"ranking_weekly_{n}\"]/a/section/h3/span[1]") # 北海道紋別市
                gift_area = gift_area.text
                print(gift_area)
                gift_name = driver.find_element_by_xpath(f"//*[@id=\"ranking_weekly_{n}\"]/a/section/h3/span[2]") #10-68 オホーツク産ホタテ玉冷大(1kg)
                gift_name = gift_name.text
                print(gift_name)
                gift_price = driver.find_element_by_xpath(f"//*[@id=\"ranking_weekly_{n}\"]/a/section/span[2]") # 10,000
                gift_price = gift_price.text
                print(gift_price)

                gift_dict = {'ranking':ranking, 'gift_area':gift_area, 'gift_name':gift_name, 'gift_price' :gift_price}
                gift_list.append(gift_dict)
            else:
                # 同率順位があって、アイテム数＞ランキング順位数の場合はスキップ
                print('ランキングなし')
                next
            n += 1
                
    except Exception as e:
        print("Error. quit driver")
        driver.quit()
        raise
    else:
        print("全ページスクレイピング完了")
        driver.quit()
        return gift_list


def make_shop_uuid():
    shop_uuid = f"shop_{str(uuid.uuid4())}"
    return shop_uuid


def get_current_datetime():
    tokyo = pytz.timezone("Asia/Tokyo")
    current_datetime = datetime.now(tokyo).strftime("%Y-%m-%d %H:%M:%S")
    return current_datetime



def write_spreadsheet(gift_list):
    print(gift_list)
    session = get_session

def get_session():
    print('セッション開始')


def main(event):
    body = event["body"]
    should_scrape = body["should_scrape"]
    is_success = False
    is_written = False
    params_gift_list = body["gift_list"]

    gift_list = (scrape_ranking()) if should_scrape else params_gift_list

    print("-------------------------")
    print(f"gift_list: {gift_list}")
    print("-------------------------")

    if gift_list:
        # is_written = write_spreadsheet(gift_list)
        is_written = True
    else:
        print("no gift_list")
        is_success = False 

    if is_written:
        is_success = True

    return is_success


def lambda_handler(event, context):
    try:
        is_success = main(event)

        if is_success:
            res = {
                "statusCode": 200,
                "body": json.dumps({
                    "message": "success!"
                })
            }
        else:
            res = {
                "statusCode": 200,
                "body": json.dumps({
                    "message": "not success"
                })
            }

        return res
    except Exception as e:
        print("----------")
        type_, value_, traceback_ = sys.exc_info()
        print(type_)
        print(value_)
        print(traceback_)
        print(traceback.format_exc())
        print("----------")
        return {
            "statusCode": 400,
            "body": json.dumps({
                "message": "Error!",
            })
        }

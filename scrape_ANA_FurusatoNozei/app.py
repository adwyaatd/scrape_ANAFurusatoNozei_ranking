from calendar import weekday
import json
import sys
import traceback
import re
import uuid
import datetime
from wsgiref.util import shift_path_info

from selenium import webdriver
from selenium.webdriver.chrome import options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.select import Select
import boto3
import pytz
import gspread
from gspread_formatting import *
from oauth2client.service_account import ServiceAccountCredentials
import requests

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


def scrape_ranking(url):
    gift_list = []
    try:
        driver = get_driver()
        driver.implicitly_wait(3)
        print("start scraping ranking")

        driver.get(url)
        items = driver.find_elements_by_xpath("//*[@id=\"ranking_weekly\"]/ul/li")
        items_count = len(items)
        n = 1
        while n <= items_count:
            # print(f'ランキング: {n}位')
            if is_findable_element(driver,'id',f'ranking_weekly_{n}'):
                ranking = n
                gift_area = driver.find_element_by_xpath(f"//*[@id=\"ranking_weekly_{n}\"]/a/section/h3/span[1]") # 北海道紋別市
                gift_area = gift_area.text
                # print(gift_area)
                gift_name = driver.find_element_by_xpath(f"//*[@id=\"ranking_weekly_{n}\"]/a/section/h3/span[2]") #10-68 オホーツク産ホタテ玉冷大(1kg)
                gift_name = gift_name.text
                # print(gift_name)
                gift_price = driver.find_element_by_xpath(f"//*[@id=\"ranking_weekly_{n}\"]/a/section/span[2]") # 10,000
                gift_price = gift_price.text
                # print(gift_price)

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


def get_inclusive_index(list, purpose):
    for index, element in enumerate(list):
        if purpose in element: return index

    raise IndexError


def get_parameters_from_SSM(parameter_name_list):
    ssm = boto3.client('ssm')
    parameters = dict()

    ssm_response = ssm.get_parameters(
        Names=parameter_name_list,
        WithDecryption=True,
    )

    for param in ssm_response['Parameters']:
        parameters[ param["Name"] ] = param["Value"]

    return parameters



def write_spreadsheet(scraped_gift_list, sheet_name, gsp_key_list):
    sheet = get_Gspreed_sheet(sheet_name, gsp_key_list)

    print('設定開始')
    last_row_num = get_last_row_num(sheet)
    new_row_num = last_row_num + 1
    new_col_num = get_last_col_num(sheet) + 1

    todays_date = datetime.date.today()
    now_time = datetime.datetime.now().time().strftime('%X')
    todays_weekday = get_weekday(todays_date)

    print(f'new_col_num: {new_col_num}')
    print(f'new_row_num: {new_row_num}')

    sheet.update_cell(4,new_col_num,now_time)
    sheet.update_cell(5,new_col_num,str(todays_date))
    sheet.update_cell(6,new_col_num,todays_weekday)

    print("本日の列の枠線設置開始")

    # 範囲
    todays_top_cel = gspread.utils.rowcol_to_a1(5, new_col_num)
    todays_current_bottom_cel = gspread.utils.rowcol_to_a1(last_row_num, new_col_num)
    todays_col_range = f'{todays_top_cel}:{todays_current_bottom_cel}'
    todays_top_range = todays_top_cel

    dot = Border("DOTTED", Color(0, 0, 0, 0))
    solid = Border("SOLID", Color(0, 0, 0, 0))

    fmt_td_bd_rs_ls_border = CellFormat(borders=Borders(top=dot,bottom=dot,left=solid,right=solid))
    fmt_ts = CellFormat(borders=Borders(top=solid))
    format_cell_range(sheet, todays_col_range, fmt_td_bd_rs_ls_border)
    format_cell_range(sheet, todays_top_range, fmt_ts)

    print('記録開始')

    add_row_count = 0

    last_row_num = get_last_row_num(sheet)
    all_add_list = []
    ranking_list = []
    new_gift_No = int(sheet.cell(last_row_num,1).value)+1

    # 取得済みの自治体名、返礼品名、金額をリストで取得
    existing_gitf_area_list = sheet.col_values(2)
    existing_gitf_name_list = sheet.col_values(3)
    existing_gitf_price_list = sheet.col_values(4)
    for scraped_gift in scraped_gift_list:
        is_matched = False
        transrate_table = str.maketrans('','',',円')
        scraped_gift_price = int(scraped_gift['gift_price'].translate(transrate_table))
        scraped_gift_area = scraped_gift['gift_area'].replace(' ','')
        if scraped_gift['gift_name'] == existing_gitf_name_list:
            # print('返礼品名あり')
            index = get_inclusive_index(existing_gitf_name_list, scraped_gift['gift_name'])
            existing_gift_price = int(existing_gitf_price_list[index].translate(transrate_table))
            existing_gift_area = existing_gitf_area_list[index].replace(' ','')
            # print(f'index: {index}')
            # print(f'scraped_gift_area: {scraped_gift_area}')
            # print(f'existing_gift_area: {existing_gift_area}')
            # print(f'scraped_gift_price: {scraped_gift_price}')
            # print(f'existing_gift_price: {existing_gift_price}')

            if scraped_gift_area == existing_gift_area and scraped_gift_price == existing_gift_price:
                # print('全一致 返礼品あり')
                is_matched = True
                row_num = index+1
                sheet.update_cell(row_num,new_col_num,scraped_gift["ranking"])
                continue

        if not is_matched:
            # print("合致なし。新規返礼品として登録")
            add_list = [new_gift_No,scraped_gift_area,scraped_gift['gift_name'],scraped_gift_price]
            all_add_list.append(add_list)
            ranking_list.append([scraped_gift["ranking"]])
            new_gift_No += 1
            add_row_count += 1

    if add_row_count >= 1:
        print('新規返礼品あり。返礼品情報書き込み')
        new_top_left_cel = gspread.utils.rowcol_to_a1(new_row_num, 1)
        sheet.append_rows(all_add_list, table_range=new_top_left_cel)

        print('ランキング書き込み')
        new_top_right_cel = gspread.utils.rowcol_to_a1(new_row_num, new_col_num)
        sheet.append_rows(ranking_list, table_range=new_top_right_cel)

        print('枠線設置')
        new_bottom_row_num = last_row_num + add_row_count
        new_bottom_right_cel = gspread.utils.rowcol_to_a1(new_bottom_row_num, new_col_num)
        add_range = f'{new_top_left_cel}:{new_bottom_right_cel}'
        format_cell_range(sheet, add_range, fmt_td_bd_rs_ls_border)
    else:
        print('全て既存品のみで追加はなし')

    print("スプレッドシートへの書き込み完了")
    return True

def get_Gspreed_sheet(sheet_name, gsp_key_list):
    print('認証開始')

    project_id           = gsp_key_list['project_id']
    private_key_id       = gsp_key_list['private_key_id']
    private_key          = gsp_key_list['private_key'].replace('\\n','\n')
    client_email         = gsp_key_list['client_email']
    client_id            = gsp_key_list['client_id']
    client_x509_cert_url = gsp_key_list['client_x509_cert_url']
    
    key_dict = {
        "type": "service_account",
        "project_id": project_id,
        "private_key_id": private_key_id,
        "private_key": private_key,
        "client_email": client_email,
        "client_id": client_id,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": client_x509_cert_url
    }

    scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']

    #ダウンロードしたjsonファイル名をクレデンシャル変数に設定。
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    #OAuth2の資格情報を使用してGoogle APIにログイン。
    session = gspread.authorize(credentials)

    #スプレッドシートIDを変数に格納する。
    key = '1dOpDkDIa1CrrIPazjx6FiHUhZ1vxhu7gGWH5OV9hbo0'
    # スプレッドシート（ブック）を開く
    sheets = session.open_by_key(key)

    sheet = sheets.worksheet(sheet_name)
    return sheet


def get_last_col_num(sheet):
    str_list = list(filter(None, sheet.row_values(5)))
    return len(str_list)


def get_last_row_num(sheet):
    str_list = list(filter(None, sheet.col_values(1)))
    return len(str_list)


def get_weekday(date):
    days = ['月', '火', '水', '木', '金', '土', '日']
    weekday_num = date.weekday()
    weekday = days[weekday_num]
    return weekday


def send_line_notification(gsp_sheet_name, is_success, access_token):
    url = "https://notify-api.line.me/api/notify"
    headers = {'Authorization': 'Bearer ' + access_token}
    message = f'Succes: {gsp_sheet_name}' if is_success else f'Failure: {gsp_sheet_name}'
    payload = {'message': message}
    r = requests.post(url, headers=headers, params=payload,)


def main(event):
    body = event["body"]
    should_scrape = body.get("should_scrape", False)
    demo_gift_list = body.get("demo_gift_list", None)
    is_success = False
    is_written = False
    url = event.get('ana_total_ranking', event.get('ana_meat_ranking')).get('url')
    gsp_sheet_name = event.get('ana_total_ranking', event.get('ana_meat_ranking')).get('gsp_sheet_name')

    gsp_key_name_list = [
        'gsp_ANA_FURUSATONOZEI_client_id',
        'gsp_ANA_FURUSATONOZEI_project_id',
        'gsp_ANA_FURUSATONOZEI_client_email',
        'gsp_ANA_FURUSATONOZEI_client_x509_cert_url',
        'gsp_ANA_FURUSATONOZEI_private_key',
        'gsp_ANA_FURUSATONOZEI_private_key_id',
        'LINE_API_access_token',
    ]

    parameters = get_parameters_from_SSM(gsp_key_name_list) 

    project_id           = parameters['gsp_ANA_FURUSATONOZEI_project_id']
    private_key_id       = parameters['gsp_ANA_FURUSATONOZEI_private_key_id']
    private_key          = parameters['gsp_ANA_FURUSATONOZEI_private_key'].replace('\\n','\n')
    client_email         = parameters['gsp_ANA_FURUSATONOZEI_client_email']
    client_id            = parameters['gsp_ANA_FURUSATONOZEI_client_id']
    client_x509_cert_url = parameters['gsp_ANA_FURUSATONOZEI_client_x509_cert_url']
    access_token         = parameters['LINE_API_access_token']

    gsp_key_list = {'project_id':project_id, 'private_key_id':private_key_id ,'private_key':private_key ,'client_email':client_email ,'client_id':client_id ,'client_x509_cert_url':client_x509_cert_url}

    scraped_gift_list = (scrape_ranking(url)) if should_scrape else demo_gift_list

    print("-------------------------")
    print(f"scraped_gift_list: {scraped_gift_list}")
    print("-------------------------")

    if scraped_gift_list:
        is_written = write_spreadsheet(scraped_gift_list, gsp_sheet_name, gsp_key_list)
    else:
        print("no scraped_gift_list")
        is_success = False 

    is_success = True if is_written else False

    send_line_notification(gsp_sheet_name, is_success, access_token)

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
        print(e)
        print("----------")
        return {
            "statusCode": 400,
            "body": json.dumps({
                "message": 'error',
            })
        }

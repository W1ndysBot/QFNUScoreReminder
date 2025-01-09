# script/QFNUScoreReminder/main.py

import logging
import os
import sys
import requests
from PIL import Image
from io import BytesIO
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# 添加项目根目录到sys.path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.config import *
from app.api import *
from app.switch import load_switch, save_switch
from app.scripts.QFNUScoreReminder.captcha_ocr import get_ocr_res

# 数据存储路径，实际开发时，请将QFNUScoreReminder替换为具体的数据存放路径
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "QFNUScoreReminder",
)


# 查看功能开关状态
def load_function_status(group_id):
    return load_switch(group_id, "QFNUScoreReminder")


# 保存功能开关状态
def save_function_status(group_id, status):
    save_switch(group_id, "QFNUScoreReminder", status)


# 设置基本的URL和数据
RandCodeUrl = "http://zhjw.qfnu.edu.cn/verifycode.servlet"  # 验证码请求URL
loginUrl = "http://zhjw.qfnu.edu.cn/Logon.do?method=logonLdap"  # 登录请求URL
dataStrUrl = (
    "http://zhjw.qfnu.edu.cn/Logon.do?method=logon&flag=sess"  # 初始数据请求URL
)

# 初始化最近一次访问的时间
last_access_time = datetime.now()


def get_initial_session():
    """
    创建会话并获取初始数据
    返回: (session对象, cookies字典, 初始数据字符串)
    """
    session = requests.session()
    response = session.get(dataStrUrl, timeout=1000)
    cookies = session.cookies.get_dict()
    return session, cookies, response.text


def handle_captcha(session, cookies):
    """
    获取并识别验证码
    返回: 识别出的验证码字符串
    """
    response = session.get(RandCodeUrl, cookies=cookies)

    # 添加调试信息
    if response.status_code != 200:
        print(f"请求验证码失败，状态码: {response.status_code}")
        return None

    try:
        image = Image.open(BytesIO(response.content))
    except Exception as e:
        print(f"无法识别图像文件: {e}")
        return None

    return get_ocr_res(image)


def generate_encoded_string(data_str, user_account, user_password):
    """
    生成登录所需的encoded字符串
    参数:
        data_str: 初始数据字符串
        user_account: 用户账号
        user_password: 用户密码
    返回: encoded字符串
    """
    res = data_str.split("#")
    code, sxh = res[0], res[1]
    data = f"{user_account}%%%{user_password}"
    encoded = ""
    b = 0

    for a in range(len(code)):
        if a < 20:
            encoded += data[a]
            for _ in range(int(sxh[a])):
                encoded += code[b]
                b += 1
        else:
            encoded += data[a:]
            break
    return encoded


def login(session, cookies, user_account, user_password, random_code, encoded):
    """
    执行登录操作
    返回: 登录响应结果
    """
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36",
        "Origin": "http://zhjw.qfnu.edu.cn",
        "Referer": "http://zhjw.qfnu.edu.cn/",
        "Upgrade-Insecure-Requests": "1",
    }

    data = {
        "userAccount": user_account,
        "userPassword": user_password,
        "RANDOMCODE": random_code,
        "encoded": encoded,
    }

    return session.post(
        loginUrl, headers=headers, data=data, cookies=cookies, timeout=1000
    )


def get_user_credentials():
    """
    获取用户账号和密码
    返回: (user_account, user_password)
    """
    user_account = os.getenv("USER_ACCOUNT")
    user_password = os.getenv("USER_PASSWORD")
    print(f"用户名: {user_account}\n")
    print(f"密码: {user_password}\n")
    return user_account, user_password


def simulate_login(user_account, user_password):
    """
    模拟登录过程
    返回: (session对象, cookies字典)
    抛出:
        Exception: 当验证码错误时
    """
    session, cookies, data_str = get_initial_session()

    for attempt in range(3):  # 尝试三次
        random_code = handle_captcha(session, cookies)
        print(f"验证码: {random_code}\n")
        encoded = generate_encoded_string(data_str, user_account, user_password)
        response = login(
            session, cookies, user_account, user_password, random_code, encoded
        )

        # 检查响应状态码和内容
        if response.status_code == 200:
            if "验证码错误!!" in response.text:
                print(f"验证码识别错误，重试第 {attempt + 1} 次\n")
                continue  # 继续尝试
            if "密码错误" in response.text:
                raise Exception("用户名或密码错误")
            print("登录成功，cookies已返回\n")
            return session, cookies
        else:
            raise Exception("登录失败")

    raise Exception("验证码识别错误，请重试")


# 访问成绩页面
def get_score_page(session, cookies):
    url = "http://zhjw.qfnu.edu.cn/jsxsd/kscj/cjcx_list?kksj=2024-2025-1"
    respense = session.get(url, cookies=cookies)
    return respense.text


# 解析成绩页面
def analyze_score_page(pagehtml):
    soup = BeautifulSoup(pagehtml, "lxml")
    results = []

    # 找到成绩表格
    table = soup.find("table", {"id": "dataList"})
    if table:
        # 遍历表格的每一行
        rows = table.find_all("tr")[1:]  # 跳过表头
        for row in rows:
            columns = row.find_all("td")
            if len(columns) > 5:
                subject_name = columns[3].get_text(strip=True)
                score = columns[5].get_text(strip=True)
                results.append((subject_name, score))

    return results


# 分离新增成绩的科目和成绩
def get_new_scores(current_scores, last_scores):
    """
    获取新增的成绩
    参数:
        current_scores: 当前获取的成绩列表
        last_scores: 上一次获取的成绩列表
    返回: 新增成绩的列表
    """
    # 使用集合差集来找出新增的成绩
    new_scores = [score for score in current_scores if score not in last_scores]
    return new_scores


# 群消息处理函数
async def handle_QFNUScoreReminder_group_message(websocket, msg):
    # 确保数据目录存在
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        user_id = str(msg.get("user_id"))
        group_id = str(msg.get("group_id"))
        raw_message = str(msg.get("raw_message"))
        role = str(msg.get("sender", {}).get("role"))
        message_id = str(msg.get("message_id"))

    except Exception as e:
        logging.error(f"处理QFNUScoreReminder群消息失败: {e}")
        await send_group_msg(
            websocket,
            group_id,
            "处理QFNUScoreReminder群消息失败，错误信息：" + str(e),
        )
        return


# 群通知处理函数
async def handle_QFNUScoreReminder_group_notice(websocket, msg):
    # 确保数据目录存在
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        user_id = str(msg.get("user_id"))
        group_id = str(msg.get("group_id"))
        raw_message = str(msg.get("raw_message"))
        role = str(msg.get("sender", {}).get("role"))
        message_id = str(msg.get("message_id"))

    except Exception as e:
        logging.error(f"处理QFNUScoreReminder群通知失败: {e}")
        await send_group_msg(
            websocket,
            group_id,
            "处理QFNUScoreReminder群通知失败，错误信息：" + str(e),
        )
        return


# 定时监控，每分钟访问一次
async def monitor_score():
    global last_access_time
    if datetime.now().minute % 1 == 0 and datetime.now() - last_access_time > timedelta(
        minutes=1
    ):
        # 刷新最近一次访问的时间
        last_access_time = datetime.now()

        # 从数据列表中获取每人的用户名和密码
        for user_info in DATA_DIR:
            user_account = user_info.get("user_account")
            user_password = user_info.get("user_password")

            # 模拟登录
            session, cookies = simulate_login(user_account, user_password)

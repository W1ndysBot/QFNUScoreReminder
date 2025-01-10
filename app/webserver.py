from flask import Flask, request, render_template
import sqlite3
import requests
from PIL import Image
from io import BytesIO
from captcha_ocr import get_ocr_res
import os

app = Flask(__name__)

DATA_DIR = os.path.join(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ),
    "data",
    "QFNUScoreReminder",
)

# 数据库文件路径
DATABASE = os.path.join(DATA_DIR, "database.db")

print(DATABASE)


# 创建数据库表
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            group_id TEXT NOT NULL,
            qq_id TEXT NOT NULL
        )
    """
    )
    conn.commit()
    conn.close()


# 初始化数据库
init_db()

# 设置基本的URL和数据
RandCodeUrl = "http://zhjw.qfnu.edu.cn/verifycode.servlet"  # 验证码请求URL
loginUrl = "http://zhjw.qfnu.edu.cn/Logon.do?method=logonLdap"  # 登录请求URL
dataStrUrl = (
    "http://zhjw.qfnu.edu.cn/Logon.do?method=logon&flag=sess"  # 初始数据请求URL
)


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
    if len(res) < 2:
        raise ValueError("初始数据字符串格式不正确")

    code, sxh = res[0], res[1]
    data = f"{user_account}%%%{user_password}"
    encoded = ""
    b = 0

    for a in range(len(code)):
        if a < len(data):
            encoded += data[a]
            for _ in range(int(sxh[a])):
                if b < len(code):
                    encoded += code[b]
                    b += 1
                else:
                    raise ValueError("编码过程中索引超出范围")
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


@app.route("/", methods=["GET", "POST"])
def index():
    success_message = None
    error_message = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        group_id = request.form["group_id"]
        qq_id = request.form["qq_id"]
        try:
            simulate_login(username, password)
            save_to_db(username, password, group_id, qq_id)
            success_message = "账号和密码已保存，请关闭此页面，等待群内机器人通知即可！"
        except Exception as e:
            error_message = str(e) if str(e) else "发生未知错误，请联系管理员"

    return render_template(
        "index.html", success_message=success_message, error_message=error_message
    )


def save_to_db(username, password, group_id, qq_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO users (username, password, group_id, qq_id) VALUES (?, ?, ?, ?)",
        (username, password, group_id, qq_id),
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    app.run(port=5001, debug=True)

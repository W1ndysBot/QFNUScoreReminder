from flask import Flask, request, render_template
import sqlite3

app = Flask(__name__)

# 数据库文件路径
DATABASE = r"D:\bot\W1ndysBot\app\scripts\QFNUScoreReminder\app\database.db"


# 创建数据库表
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            group_id TEXT NOT NULL
        )
    """
    )
    conn.commit()
    conn.close()


# 初始化数据库
init_db()


@app.route("/", methods=["GET", "POST"])
def index():
    success_message = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        group_id = request.form["group_id"]
        save_to_db(username, password, group_id)
        success_message = "账号和密码已保存，请关闭此页面，等待群内机器人通知即可！"
    return render_template("index.html", success_message=success_message)


def save_to_db(username, password, group_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO users (username, password, group_id) VALUES (?, ?, ?)",
        (username, password, group_id),
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    app.run(port=5001, debug=True)
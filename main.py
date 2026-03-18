import json
import os
import sys
import uuid
import time
import random
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QHBoxLayout, QGridLayout,
    QTextEdit, QLineEdit, QFileDialog,
    QDialog, QDialogButtonBox, QComboBox, QStackedWidget
)
from PyQt5.QtGui import QPixmap, QFont, QPainter, QPainterPath, QColor, QPen
from PyQt5.QtCore import Qt, QTimer, QEvent


# =======================
# DỮ LIỆU BÀI VIẾT
# =======================

DEFAULT_POSTS = [
   
]

POST_FILE = "posts.json"
USER_FILE = "user.json"
FOLLOW_FILE = "follows.json"
NOTIFICATION_FILE = "notifications.json"
GROUP_FILE = "groups.json"

ADMIN_USERNAME = "Admin"
ADMIN_PASSWORD = "123456"
SUSPEND_CHOICES = {
    "24 giờ": timedelta(hours=24),
    "3 ngày": timedelta(days=3),
    "7 ngày": timedelta(days=7),
    "1 tháng": timedelta(days=30),
    "6 tháng": timedelta(days=180),
    "Vĩnh viễn": None,
}

DEFAULT_USERS = {
    "admin": {
        "password": "123456",
        "avatar": "",
        "suspended_until": "",
        "suspend_reason": "",
        "suspended_by": "",
        "suspended_at": "",
        "suspend_duration_label": "",
        "email": "",
    },
    ADMIN_USERNAME: {
        "password": ADMIN_PASSWORD,
        "avatar": "",
        "suspended_until": "",
        "suspend_reason": "",
        "suspended_by": "",
        "suspended_at": "",
        "suspend_duration_label": "",
        "email": "",
    }
}


def now_text():
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def relative_time_text(date_text):
    if not date_text:
        return ""

    dt = None
    for parser in (
        lambda value: datetime.strptime(value, "%d/%m/%Y %H:%M"),
        datetime.fromisoformat,
    ):
        try:
            dt = parser(date_text)
            break
        except (ValueError, TypeError):
            continue

    if not dt:
        return ""

    delta = datetime.now() - dt
    seconds = max(0, int(delta.total_seconds()))
    if seconds < 60:
        return "Vừa xong"
    if seconds < 3600:
        mins = seconds // 60
        return f"{mins} phút trước"
    if seconds < 86400:
        hours = seconds // 3600
        return f"{hours} giờ trước"
    days = seconds // 86400
    if days < 7:
        return f"{days} ngày trước"
    return dt.strftime("%d/%m/%Y %H:%M")


def generate_post_id():
    return str(uuid.uuid4())


class InlineToast(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("InlineToast")
        self.setWindowFlags(Qt.SubWindow)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setStyleSheet("""
            QFrame#InlineToast {
                background-color: rgba(15, 23, 42, 0.92);
                border: 1px solid rgba(255,255,255,0.40);
                border-radius: 12px;
            }
            QLabel {
                color: white;
                font-size: 13px;
                font-weight: bold;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        self.icon_label = QLabel("ℹ️")
        self.text_label = QLabel("")
        self.text_label.setWordWrap(True)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)
        self.hide()

    def show_message(self, text, level="info", timeout=4500):
        icon_map = {
            "success": "✅",
            "warning": "⚠️",
            "error": "❌",
            "info": "ℹ️"
        }
        self.icon_label.setText(icon_map.get(level, "ℹ️"))
        self.text_label.setText(text)
        self.adjustSize()

        parent = self.parentWidget()
        if parent:
            x = max(12, (parent.width() - self.width()) // 2)
            self.move(x, 16)

        self.show()
        self.raise_()
        self.timer.start(timeout)


def create_default_avatar(size):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    painter.setBrush(QColor("#cbd5e1"))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(0, 0, size, size)

    head_size = int(size * 0.34)
    body_w = int(size * 0.58)
    body_h = int(size * 0.36)
    cx = size // 2

    painter.setBrush(QColor("#f8fafc"))
    painter.drawEllipse(cx - head_size // 2, int(size * 0.22), head_size, head_size)

    body_rect_x = cx - body_w // 2
    body_rect_y = int(size * 0.56)
    painter.drawRoundedRect(body_rect_x, body_rect_y, body_w, body_h, body_h // 2, body_h // 2)

    painter.end()
    return pixmap


def make_circle_avatar(image_path, size=42):
    source = QPixmap(image_path) if image_path and os.path.exists(image_path) else QPixmap()
    if source.isNull():
        source = create_default_avatar(size)

    source = source.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)

    result = QPixmap(size, size)
    result.fill(Qt.transparent)

    painter = QPainter(result)
    painter.setRenderHint(QPainter.Antialiasing)

    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, source)

    painter.setClipping(False)
    painter.setPen(QPen(QColor(255, 255, 255, 190), max(2, size // 18)))
    painter.setBrush(Qt.NoBrush)
    painter.drawEllipse(1, 1, size - 2, size - 2)

    painter.end()
    return result


def build_avatar_label(image_path, size=42):
    label = QLabel()
    label.setFixedSize(size, size)
    label.setPixmap(make_circle_avatar(image_path, size))
    return label


def ensure_admin_account(data):
    data.setdefault(
        ADMIN_USERNAME,
        {
            "password": ADMIN_PASSWORD,
            "avatar": "",
            "suspended_until": "",
            "suspend_reason": "",
            "suspended_by": "",
            "suspended_at": "",
            "suspend_duration_label": "",
            "email": "",
        }
    )
    return data


def get_suspend_status(user_data):
    if not isinstance(user_data, dict):
        return False, ""

    suspended_until = user_data.get("suspended_until", "")
    if not suspended_until:
        return False, ""

    if suspended_until == "permanent":
        return True, "Tài khoản đang bị khóa vĩnh viễn."

    try:
        until_dt = datetime.fromisoformat(suspended_until)
    except ValueError:
        return False, ""

    if datetime.now() < until_dt:
        return True, f"Tài khoản đang bị khóa đến {until_dt.strftime('%d/%m/%Y %H:%M')}"

    return False, ""


def get_suspend_notice(user_data):
    suspended, status_message = get_suspend_status(user_data)
    if not suspended:
        return ""

    reason = user_data.get("suspend_reason", "") if isinstance(user_data, dict) else ""
    suspended_by = user_data.get("suspended_by", "Admin") if isinstance(user_data, dict) else "Admin"
    suspended_at = user_data.get("suspended_at", "") if isinstance(user_data, dict) else ""
    duration_label = user_data.get("suspend_duration_label", "") if isinstance(user_data, dict) else ""

    return (
        "🔒 Tài khoản đang bị khóa\n"
        f"• Lý do: {reason if reason else 'Không có'}\n"
        f"• Ngày giờ khóa: {suspended_at if suspended_at else 'Không có'}\n"
        f"• Thời gian khóa: {duration_label if duration_label else 'Không xác định'}\n"
        f"• Người khóa: {suspended_by if suspended_by else 'Admin'}\n"
        f"• Trạng thái: {status_message}"
    )


def normalize_users(raw_data):
    normalized = {}
    if not isinstance(raw_data, dict):
        return ensure_admin_account(DEFAULT_USERS.copy())

    for username, data in raw_data.items():
        if isinstance(data, str):
            normalized[username] = {
                "password": data,
                "avatar": "",
                "suspended_until": "",
                "suspend_reason": "",
                "suspended_by": "",
                "suspended_at": "",
                "suspend_duration_label": "",
                "email": "",
            }
        elif isinstance(data, dict):
            normalized[username] = {
                "password": data.get("password", ""),
                "avatar": data.get("avatar", ""),
                "suspended_until": data.get("suspended_until", ""),
                "suspend_reason": data.get("suspend_reason", ""),
                "suspended_by": data.get("suspended_by", ""),
                "suspended_at": data.get("suspended_at", ""),
                "suspend_duration_label": data.get("suspend_duration_label", ""),
                "email": data.get("email", ""),
            }

    if not normalized:
        return ensure_admin_account(DEFAULT_USERS.copy())
    return ensure_admin_account(normalized)


def load_posts():
    if not os.path.exists(POST_FILE):
        save_posts(DEFAULT_POSTS)
        return [post.copy() for post in DEFAULT_POSTS]

    try:
        with open(POST_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            valid_posts = []
            for post in data:
                if isinstance(post, dict):
                    if "title" in post and "content" in post:
                        valid_posts.append({
                            "id": post.get("id", generate_post_id()),
                            "title": post.get("title", ""),
                            "image": post.get("image", ""),
                            "content": post.get("content", ""),
                            "date": post.get("date", "Hôm nay"),
                            "author": post.get("author", "Ẩn danh"),
                            "likes": post.get("likes", []),
                            "comments": post.get("comments", [])
                        })
            if valid_posts:
                return valid_posts
    except (json.JSONDecodeError, OSError):
        pass

    save_posts(DEFAULT_POSTS)
    return [post.copy() for post in DEFAULT_POSTS]


def save_posts(data):
    normalized = []
    for post in data:
        normalized_post = post.copy()
        normalized_post.setdefault("id", generate_post_id())
        normalized.append(normalized_post)
    with open(POST_FILE, "w", encoding="utf-8") as file:
        json.dump(normalized, file, ensure_ascii=False, indent=4)


def load_users():
    if not os.path.exists(USER_FILE):
        defaults = ensure_admin_account(DEFAULT_USERS.copy())
        save_users(defaults)
        return defaults

    try:
        with open(USER_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        normalized = normalize_users(data)
        save_users(normalized)
        return normalized
    except (json.JSONDecodeError, OSError):
        pass

    defaults = ensure_admin_account(DEFAULT_USERS.copy())
    save_users(defaults)
    return defaults


def save_users(data):
    with open(USER_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def load_follows():
    if not os.path.exists(FOLLOW_FILE):
        save_follows({})
        return {}

    try:
        with open(FOLLOW_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        if isinstance(data, dict):
            normalized = {}
            for user, followings in data.items():
                if isinstance(followings, list):
                    normalized[user] = list(dict.fromkeys([u for u in followings if isinstance(u, str)]))
            return normalized
    except (json.JSONDecodeError, OSError):
        pass

    save_follows({})
    return {}


def save_follows(data):
    with open(FOLLOW_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def load_notifications():
    if not os.path.exists(NOTIFICATION_FILE):
        save_notifications({})
        return {}

    try:
        with open(NOTIFICATION_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        if isinstance(data, dict):
            normalized = {}
            for username, items in data.items():
                if isinstance(items, list):
                    normalized[username] = []
                    for item in items:
                        if isinstance(item, dict):
                            normalized[username].append({
                                "id": item.get("id", str(uuid.uuid4())),
                                "post_id": item.get("post_id", ""),
                                "actor": item.get("actor", "Ẩn danh"),
                                "action": item.get("action", "interaction"),
                                "message": item.get("message", "Thông báo mới"),
                                "date": item.get("date", now_text()),
                                "read": bool(item.get("read", False))
                            })
            return normalized
    except (json.JSONDecodeError, OSError):
        pass

    save_notifications({})
    return {}


def save_notifications(data):
    with open(NOTIFICATION_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def normalize_group(raw_group):
    if not isinstance(raw_group, dict):
        return None

    members = raw_group.get("members", [])
    deputies = raw_group.get("deputies", [])
    pending = raw_group.get("pending_members", [])
    group_posts = raw_group.get("posts", [])

    if not isinstance(members, list):
        members = []
    if not isinstance(deputies, list):
        deputies = []
    if not isinstance(pending, list):
        pending = []
    if not isinstance(group_posts, list):
        group_posts = []

    owner = raw_group.get("owner", "")
    if owner and owner not in members:
        members.append(owner)

    normalized_posts = []
    for post in group_posts:
        if isinstance(post, dict) and "title" in post and "content" in post:
            normalized_posts.append({
                "id": post.get("id", generate_post_id()),
                "title": post.get("title", ""),
                "content": post.get("content", ""),
                "image": post.get("image", ""),
                "date": post.get("date", now_text()),
                "author": post.get("author", "Ẩn danh"),
                "likes": post.get("likes", []),
                "comments": post.get("comments", []),
            })

    return {
        "id": raw_group.get("id", str(uuid.uuid4())),
        "name": raw_group.get("name", "Nhóm chưa đặt tên"),
        "avatar": raw_group.get("avatar", ""),
        "owner": owner,
        "deputies": list(dict.fromkeys([u for u in deputies if isinstance(u, str) and u != owner])),
        "members": list(dict.fromkeys([u for u in members if isinstance(u, str)])),
        "pending_members": list(dict.fromkeys([u for u in pending if isinstance(u, str)])),
        "posts": normalized_posts,
    }


def load_groups():
    if not os.path.exists(GROUP_FILE):
        save_groups([])
        return []

    try:
        with open(GROUP_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            normalized = []
            for group in data:
                ng = normalize_group(group)
                if ng:
                    normalized.append(ng)
            save_groups(normalized)
            return normalized
    except (json.JSONDecodeError, OSError):
        pass

    save_groups([])
    return []


def save_groups(data):
    with open(GROUP_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


posts = load_posts()
users = load_users()
follows = load_follows()
notifications = load_notifications()
groups = load_groups()


class PostCard(QFrame):
    def __init__(self, post, open_callback, get_followers_count_callback, get_user_avatar_callback, featured=False):
        super().__init__()
        self.post = post
        self.open_callback = open_callback
        self.featured = featured

        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 14px;
                border: 1px solid #e2e8f0;
            }
            QFrame:hover {
                border: 1px solid #cbd5e1;
                background-color: #f8fafc;
            }
        """)

        layout = QVBoxLayout(self) if featured else QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        image_label = QLabel()
        pixmap = QPixmap(post.get("image", ""))
        if not pixmap.isNull():
            if featured:
                pixmap = pixmap.scaled(340, 185, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            else:
                pixmap = pixmap.scaled(92, 72, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            image_label.setPixmap(pixmap)
        image_label.setStyleSheet("border-radius: 10px;")

        author_name = post.get("author", "Ẩn danh")
        followers_count = get_followers_count_callback(author_name)
        source = QLabel(f"{author_name} · {relative_time_text(post.get('date', '')) or post.get('date', '')}")
        source.setStyleSheet("color: #64748b; font-size: 12px;")

        title = QLabel(post.get("title", ""))
        title.setWordWrap(True)
        title.setStyleSheet("color: #0f172a; font-size: 15px; font-weight: bold;")

        reads = QLabel(f"{max(80, followers_count * 7)} reads")
        reads.setStyleSheet("color: #94a3b8; font-size: 12px;")

        if featured:
            layout.addWidget(image_label)
            layout.addWidget(source)
            layout.addWidget(title)
            layout.addWidget(reads)
        else:
            text_col = QVBoxLayout()
            text_col.setSpacing(4)
            text_col.addWidget(source)
            text_col.addWidget(title)
            text_col.addWidget(reads)
            text_col.addStretch()

            layout.addLayout(text_col, 1)
            if not pixmap.isNull():
                layout.addWidget(image_label)

    def mousePressEvent(self, event):
        self.open_callback(self.post)


class HomePage(QWidget):
    def __init__(
        self,
        open_detail_callback,
        get_followers_count_callback,
        get_user_avatar_callback,
        show_profile_callback,
        show_create_callback,
        show_groups_callback,
        show_message_callback,
        toggle_notifications_callback,
        get_unread_notifications_count_callback,
    ):
        super().__init__()
        self.open_detail_callback = open_detail_callback
        self.get_followers_count_callback = get_followers_count_callback
        self.get_user_avatar_callback = get_user_avatar_callback
        self.show_profile_callback = show_profile_callback
        self.show_create_callback = show_create_callback
        self.show_groups_callback = show_groups_callback
        self.show_message = show_message_callback
        self.toggle_notifications_callback = toggle_notifications_callback
        self.get_unread_notifications_count_callback = get_unread_notifications_count_callback

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(18, 14, 18, 14)
        root_layout.setSpacing(14)

        side_panel = QFrame()
        side_panel.setFixedWidth(250)
        side_panel.setStyleSheet("""
            QFrame {
                background-color: rgba(255,255,255,0.93);
                border: 1px solid rgba(15,23,42,0.12);
                border-radius: 14px;
            }
        """)
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(14, 14, 14, 14)
        side_layout.setSpacing(10)

        app_name = QLabel("NovaNews")
        app_name.setStyleSheet("color:#0f172a; font-size:22px; font-weight:900;")
        app_sub = QLabel("Ứng dụng tin tức desktop")
        app_sub.setStyleSheet("color:#475569; font-size:12px;")

        self.btn_notify = QPushButton("🔔")
        self.btn_notify.setFixedSize(46, 42)
        self.btn_notify.setStyleSheet("""
            QPushButton {
                background-color: #4f46e5;
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3730a3;
            }
        """)
        self.btn_notify.clicked.connect(lambda: self.toggle_notifications_callback(self.btn_notify))

        self.home_notify_badge = QLabel("0")
        self.home_notify_badge.setAlignment(Qt.AlignCenter)
        self.home_notify_badge.setFixedSize(18, 18)
        self.home_notify_badge.setStyleSheet("""
            QLabel {
                background-color: #e74a3b;
                color: white;
                border: 1px solid rgba(255,255,255,0.9);
                border-radius: 9px;
                font-size: 9px;
                font-weight: bold;
            }
        """)

        self.notify_btn_wrap = QFrame()
        notify_btn_wrap_layout = QGridLayout(self.notify_btn_wrap)
        notify_btn_wrap_layout.setContentsMargins(0, 0, 0, 0)
        notify_btn_wrap_layout.setHorizontalSpacing(0)
        notify_btn_wrap_layout.setVerticalSpacing(0)
        notify_btn_wrap_layout.addWidget(self.btn_notify, 0, 0, alignment=Qt.AlignCenter)
        notify_btn_wrap_layout.addWidget(self.home_notify_badge, 0, 0, alignment=Qt.AlignTop | Qt.AlignRight)

        self.btn_create = QPushButton("✍️ Tạo bài mới")
        self.btn_create.clicked.connect(self.show_create_callback)
        self.btn_profile = QPushButton("👤 Hồ sơ cá nhân")
        self.btn_profile.clicked.connect(self.show_profile_callback)
        self.btn_groups = QPushButton("👥 Quản lý nhóm")
        self.btn_groups.clicked.connect(self.show_groups_callback)

        for btn, color in [
            (self.btn_create, "#0ea5e9"),
            (self.btn_profile, "#10b981"),
            (self.btn_groups, "#f59e0b"),
        ]:
            btn.setFixedHeight(42)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    border: none;
                    border-radius: 10px;
                    text-align: left;
                    padding: 0 12px;
                    font-size: 13px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: rgba(15,23,42,0.78);
                }}
            """)

        side_layout.addWidget(app_name)
        side_layout.addWidget(app_sub)
        side_layout.addSpacing(6)
        notify_row = QHBoxLayout()
        notify_row.addWidget(self.notify_btn_wrap)
        notify_row.addStretch()
        side_layout.addLayout(notify_row)
        side_layout.addWidget(self.btn_create)
        side_layout.addWidget(self.btn_profile)
        side_layout.addWidget(self.btn_groups)
        side_layout.addStretch()

        main_panel = QFrame()
        main_panel.setStyleSheet("""
            QFrame {
                background-color: rgba(255,255,255,0.95);
                border: 1px solid rgba(15,23,42,0.10);
                border-radius: 14px;
            }
        """)
        main_layout = QVBoxLayout(main_panel)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(10)

        top_bar = QHBoxLayout()
        title = QLabel("Bảng tin hôm nay")
        title.setStyleSheet("color:#0f172a; font-size:24px; font-weight:900;")

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Tìm theo tiêu đề hoặc nội dung...")
        self.search_input.setFixedHeight(38)
        self.search_input.setMinimumWidth(380)
        self.search_input.textChanged.connect(self.filter_posts)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 10px;
                padding: 0 12px;
                color: #0f172a;
                font-size: 13px;
            }
            QLineEdit:focus { border: 2px solid #4f46e5; }
        """)

        top_bar.addWidget(title)
        top_bar.addStretch()
        top_bar.addWidget(self.search_input)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("border: none; background: transparent;")

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(10)
        self.scroll.setWidget(self.container)

        main_layout.addLayout(top_bar)
        main_layout.addWidget(self.scroll)

        root_layout.addWidget(side_panel)
        root_layout.addWidget(main_panel, 1)

        self.render_posts()
        self.update_notify_badge(self.get_unread_notifications_count_callback())

    def clear_posts(self):
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def render_posts(self, keyword=""):
        self.clear_posts()
        normalized_keyword = keyword.strip().lower()
        filtered_posts = []

        for post in posts:
            if not normalized_keyword:
                filtered_posts.append(post)
                continue

            title_match = normalized_keyword in post.get("title", "").lower()
            content_match = normalized_keyword in post.get("content", "").lower()
            if title_match or content_match:
                filtered_posts.append(post)

        for idx, post in enumerate(filtered_posts):
            card = PostCard(
                post,
                self.open_detail_callback,
                self.get_followers_count_callback,
                self.get_user_avatar_callback,
                featured=(idx == 0),
            )
            self.container_layout.addWidget(card)

        if not filtered_posts:
            empty_label = QLabel("Không tìm thấy bài viết phù hợp.")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #475569; font-size: 14px; padding: 20px;")
            self.container_layout.addWidget(empty_label)

        self.container_layout.addStretch()

    def update_notify_badge(self, unread_count):
        self.home_notify_badge.setText(str(unread_count))
        self.home_notify_badge.setVisible(unread_count > 0)

    def filter_posts(self, keyword):
        self.render_posts(keyword)


class DetailPage(QWidget):
    def __init__(self, post, back_callback, get_current_user_callback, save_callback, get_followers_count_callback, notify_callback, get_user_avatar_callback, show_message_callback):
        super().__init__()
        self.post = post
        self.get_current_user_callback = get_current_user_callback
        self.save_callback = save_callback
        self.notify_callback = notify_callback
        self.get_user_avatar_callback = get_user_avatar_callback
        self.show_message = show_message_callback

        main_layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(150, 30, 150, 30)
        layout.setSpacing(14)

        back_btn = QPushButton("← Quay lại")
        back_btn.clicked.connect(back_callback)
        back_btn.setFixedWidth(120)
        back_btn.setFixedHeight(34)
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.94);
                color: #1e2a56;
                border-radius: 17px;
                font-size: 12px;
                font-weight: bold;
                border: 2px solid rgba(30, 42, 86, 0.2);
                padding: 0 10px;
            }
            QPushButton:hover {
                background-color: #dbe4ff;
                border: 2px solid #4e73df;
            }
            QPushButton:pressed {
                background-color: #b8c6ff;
            }
        """)

        title = QLabel(post["title"])
        title.setFont(QFont("Arial", 28, QFont.Bold))
        title.setStyleSheet("color: white;")
        title.setWordWrap(True)

        meta_box = QFrame()
        meta_box.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 0.30);
                border: 1px solid rgba(255,255,255,0.45);
                border-radius: 14px;
                padding: 8px 12px;
            }
        """)
        meta_layout = QHBoxLayout(meta_box)
        meta_layout.setContentsMargins(12, 8, 12, 8)
        meta_layout.setSpacing(12)

        date = QLabel("🗓 " + post["date"])
        date.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 13px;")

        author_name = post.get("author", "Ẩn danh")
        followers_count = get_followers_count_callback(author_name)
        author_avatar = build_avatar_label(get_user_avatar_callback(author_name), 36)
        author = QLabel(f"👤 Người đăng: {author_name} | 👥 {followers_count} follower")
        author.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 13px;")

        self.like_count_label = QLabel(f"👍 {len(post.get('likes', []))} lượt thích")
        self.like_count_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 13px;")

        meta_layout.addWidget(date)
        meta_layout.addWidget(author_avatar)
        meta_layout.addWidget(author)
        meta_layout.addWidget(self.like_count_label)
        meta_layout.addStretch()

        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)

        if post["image"]:
            pixmap = QPixmap(post["image"])
            if not pixmap.isNull():
                image_label.setPixmap(pixmap.scaledToWidth(800, Qt.SmoothTransformation))

        content = QTextEdit()
        content.setReadOnly(True)
        content.setText(post["content"])
        content.setStyleSheet("""
            QTextEdit {
                background-color: rgba(0,0,0,0.4);
                color: white;
                border-radius: 15px;
                padding: 15px;
                font-size: 15px;
                border: 1px solid rgba(255,255,255,0.22);
            }
        """)

        self.like_btn = QPushButton("👍 Thích")
        self.like_btn.setFixedHeight(44)
        self.like_btn.clicked.connect(self.toggle_like)

        self.comment_input = QLineEdit()
        self.comment_input.setPlaceholderText("Viết bình luận...")
        self.comment_input.setFixedHeight(42)

        comment_btn = QPushButton("💬 Gửi bình luận")
        comment_btn.setFixedHeight(42)
        comment_btn.clicked.connect(self.add_comment)

        self.comment_scroll = QScrollArea()
        self.comment_scroll.setWidgetResizable(True)
        self.comment_scroll.setMinimumHeight(170)
        self.comment_scroll.setStyleSheet("""
            QScrollArea {
                background-color: rgba(0,0,0,0.35);
                border-radius: 12px;
                border: 1px solid rgba(255,255,255,0.25);
            }
        """)

        self.comment_container = QWidget()
        self.comment_layout = QVBoxLayout(self.comment_container)
        self.comment_layout.setContentsMargins(10, 10, 10, 10)
        self.comment_layout.setSpacing(8)
        self.comment_scroll.setWidget(self.comment_container)

        comment_row = QHBoxLayout()
        comment_row.addWidget(self.comment_input, 1)
        comment_row.addWidget(comment_btn)

        layout.addWidget(back_btn, alignment=Qt.AlignLeft)
        layout.addWidget(title)
        layout.addWidget(meta_box)
        layout.addWidget(image_label)
        layout.addWidget(content)
        layout.addWidget(self.like_btn)
        layout.addLayout(comment_row)
        layout.addWidget(self.comment_scroll)

        self.refresh_interaction_ui()

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def refresh_comments(self):
        while self.comment_layout.count():
            item = self.comment_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        comments = self.post.get("comments", [])
        if not comments:
            empty = QLabel("Chưa có bình luận nào.")
            empty.setStyleSheet("color: white;")
            self.comment_layout.addWidget(empty)
            self.comment_layout.addStretch()
            return

        for c in comments:
            row_frame = QFrame()
            row_frame.setStyleSheet("""
                QFrame {
                    background-color: rgba(255,255,255,0.09);
                    border-radius: 10px;
                    border: 1px solid rgba(255,255,255,0.2);
                }
            """)
            row_layout = QHBoxLayout(row_frame)
            row_layout.setContentsMargins(8, 6, 8, 6)
            row_layout.setSpacing(8)

            user = c.get("user", "Ẩn danh")
            avatar = build_avatar_label(self.get_user_avatar_callback(user), 30)
            text = c.get("text", "")
            cdate = c.get("date", "")

            label = QLabel(f"<b>{user}</b> ({cdate})<br>{text}")
            label.setWordWrap(True)
            label.setStyleSheet("color: white;")

            row_layout.addWidget(avatar)
            row_layout.addWidget(label, 1)
            self.comment_layout.addWidget(row_frame)

        self.comment_layout.addStretch()

    def refresh_interaction_ui(self):
        current_user = self.get_current_user_callback()
        liked = current_user in self.post.get("likes", []) if current_user else False
        self.like_btn.setText("💔 Bỏ thích" if liked else "👍 Thích")
        self.like_count_label.setText(f"👍 {len(self.post.get('likes', []))} lượt thích")
        self.refresh_comments()

    def toggle_like(self):
        current_user = self.get_current_user_callback()
        if not current_user:
            self.show_message("Bạn cần đăng nhập để thích bài viết!", "warning")
            return

        likes = self.post.setdefault("likes", [])
        if current_user in likes:
            likes.remove(current_user)
        else:
            likes.append(current_user)
            self.notify_callback(self.post, current_user, "like")

        self.save_callback()
        self.refresh_interaction_ui()

    def add_comment(self):
        current_user = self.get_current_user_callback()
        if not current_user:
            self.show_message("Bạn cần đăng nhập để bình luận!", "warning")
            return

        text = self.comment_input.text().strip()
        if not text:
            self.show_message("Nội dung bình luận không được để trống!", "error")
            return

        comments = self.post.setdefault("comments", [])
        comments.append({
            "user": current_user,
            "text": text,
            "date": now_text()
        })

        self.notify_callback(self.post, current_user, "comment")
        self.comment_input.clear()
        self.save_callback()
        self.refresh_interaction_ui()
        self.show_message("Đã gửi bình luận.", "success")


class CreatePage(QWidget):
    def __init__(self, back_callback, publish_callback, get_current_user_callback, show_message_callback, post_created_callback):
        super().__init__()

        self.back_callback = back_callback
        self.publish_callback = publish_callback
        self.get_current_user_callback = get_current_user_callback
        self.show_message = show_message_callback
        self.post_created_callback = post_created_callback
        self.selected_image = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(300, 50, 300, 50)
        layout.setSpacing(20)

        back_btn = QPushButton("← Quay lại")
        back_btn.setFixedWidth(120)
        back_btn.setFixedHeight(34)
        back_btn.setStyleSheet("background-color: rgba(255,255,255,0.95); color: #1e2a56; border: 1px solid rgba(0,0,0,0.12); border-radius: 17px; padding: 0 10px; font-weight: bold;")
        back_btn.clicked.connect(self.back_callback)

        title_label = QLabel("✍ Tạo bài viết mới")
        title_label.setFont(QFont("Arial", 26, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            color: white;
            padding: 15px;
        """)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Nhập tiêu đề bài viết...")
        self.title_input.setFixedHeight(45)
        self.title_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255,255,255,0.9);
                border-radius: 12px;
                padding: 10px;
                font-size: 14px;
                border: 1px solid rgba(0,0,0,0.08);
            }
            QLineEdit:focus {
                border: 2px solid #4e73df;
            }
        """)

        self.content_input = QTextEdit()
        self.content_input.setPlaceholderText("Nhập nội dung bài viết...")
        self.content_input.setStyleSheet("""
            QTextEdit {
                background-color: rgba(255,255,255,0.95);
                border-radius: 15px;
                padding: 15px;
                font-size: 14px;
                border: 1px solid rgba(0,0,0,0.08);
            }
            QTextEdit:focus {
                border: 2px solid #1cc88a;
            }
        """)

        image_btn = QPushButton("📷 Tải ảnh")
        image_btn.setFixedHeight(45)
        image_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.96);
                border-radius: 22px;
                font-weight: bold;
                border: 1px solid rgba(0,0,0,0.12);
                padding: 0 16px;
            }
            QPushButton:hover {
                background-color: #dbe4ff;
            }
            QPushButton:pressed {
                background-color: #b8c6ff;
            }
        """)
        image_btn.clicked.connect(self.choose_image)

        publish_btn = QPushButton("🚀 Đăng bài")
        publish_btn.setFixedHeight(50)
        publish_btn.setStyleSheet("""
            QPushButton {
                background-color: #1cc88a;
                color: white;
                border-radius: 24px;
                font-weight: bold;
                font-size: 15px;
                border: 1px solid rgba(255,255,255,0.35);
            }
            QPushButton:hover {
                background-color: #17a673;
            }
            QPushButton:pressed {
                background-color: #13855c;
            }
        """)
        publish_btn.clicked.connect(self.publish_post)

        layout.addWidget(back_btn, alignment=Qt.AlignLeft)
        layout.addWidget(title_label)
        layout.addWidget(self.title_input)
        layout.addWidget(self.content_input)
        layout.addWidget(image_btn)
        layout.addWidget(publish_btn)

    def choose_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn ảnh", "", "Images (*.png *.jpg *.jpeg)"
        )
        if file_path:
            self.selected_image = file_path

    def publish_post(self):
        current_user = self.get_current_user_callback()
        if not current_user:
            self.show_message("Vui lòng đăng nhập ở trang Hồ sơ trước khi đăng bài!", "warning")
            return

        title = self.title_input.text().strip()
        content = self.content_input.toPlainText().strip()

        if not title or not content:
            self.show_message("Vui lòng nhập đầy đủ!", "error")
            return

        new_post = {
            "id": generate_post_id(),
            "title": title,
            "content": content,
            "image": self.selected_image if self.selected_image else "",
            "date": now_text(),
            "author": current_user,
            "likes": [],
            "comments": []
        }
        posts.insert(0, new_post)
        save_posts(posts)
        self.post_created_callback(new_post)

        self.show_message("Đăng bài thành công!", "success")
        self.publish_callback()


class GroupPage(QWidget):
    def __init__(
        self,
        get_current_user_callback,
        show_message_callback,
        create_group_callback,
        request_join_group_callback,
        review_join_request_callback,
        remove_member_callback,
        assign_deputy_callback,
        transfer_owner_callback,
        dissolve_group_callback,
        leave_group_callback,
        create_group_post_callback,
        delete_group_post_callback,
        edit_group_post_callback,
        update_group_avatar_callback,
        view_group_post_callback,
        back_callback,
    ):
        super().__init__()
        self.get_current_user_callback = get_current_user_callback
        self.show_message = show_message_callback
        self.create_group_callback = create_group_callback
        self.request_join_group_callback = request_join_group_callback
        self.review_join_request_callback = review_join_request_callback
        self.remove_member_callback = remove_member_callback
        self.assign_deputy_callback = assign_deputy_callback
        self.transfer_owner_callback = transfer_owner_callback
        self.dissolve_group_callback = dissolve_group_callback
        self.leave_group_callback = leave_group_callback
        self.create_group_post_callback = create_group_post_callback
        self.delete_group_post_callback = delete_group_post_callback
        self.edit_group_post_callback = edit_group_post_callback
        self.update_group_avatar_callback = update_group_avatar_callback
        self.view_group_post_callback = view_group_post_callback
        self.back_callback = back_callback
        self.selected_group_id = None

        self.primary_btn_style = """
            QPushButton {
                background-color: rgba(255,255,255,0.94);
                color: #1e2a56;
                border-radius: 14px;
                font-size: 12px;
                font-weight: bold;
                border: 1px solid rgba(255,255,255,0.45);
                padding: 6px 10px;
            }
            QPushButton:hover {
                background-color: #dbe4ff;
            }
            QPushButton:pressed {
                background-color: #b8c6ff;
            }
        """
        self.green_btn_style = """
            QPushButton {
                background-color: #1cc88a;
                color: white;
                border-radius: 14px;
                font-size: 12px;
                font-weight: bold;
                border: 1px solid rgba(255,255,255,0.35);
                padding: 6px 10px;
            }
            QPushButton:hover { background-color: #17a673; }
            QPushButton:pressed { background-color: #13855c; }
        """
        self.red_btn_style = """
            QPushButton {
                background-color: #e74a3b;
                color: white;
                border-radius: 14px;
                font-size: 12px;
                font-weight: bold;
                border: 1px solid rgba(255,255,255,0.35);
                padding: 6px 10px;
            }
            QPushButton:hover { background-color: #d83b2e; }
            QPushButton:pressed { background-color: #bf3327; }
        """

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("border:none;")

        self.content = QWidget()
        self.layout = QVBoxLayout(self.content)
        self.layout.setContentsMargins(140, 30, 140, 30)
        self.layout.setSpacing(14)

        self.scroll.setWidget(self.content)
        root.addWidget(self.scroll)
        self.render_ui()

    def _build_section_title(self, text):
        label = QLabel(text)
        label.setStyleSheet(
            "color: white; font-size: 16px; font-weight: bold;"
            "padding: 6px 10px;"
            "background-color: rgba(255,255,255,0.08);"
            "border-radius: 10px;"
            "border: 1px solid rgba(255,255,255,0.25);"
        )
        return label

    def render_ui(self):
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        back_btn = QPushButton("← Quay lại")
        back_btn.setFixedWidth(120)
        back_btn.setFixedHeight(34)
        back_btn.setStyleSheet("background-color: rgba(255,255,255,0.95); color: #1e2a56; border: 1px solid rgba(0,0,0,0.12); border-radius: 17px; padding: 0 10px; font-weight: bold;")
        back_btn.clicked.connect(self.back_callback)

        title = QLabel("👥 Nhóm riêng")
        title.setFont(QFont("Arial", 24, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color:white;")
        self.layout.addWidget(back_btn, alignment=Qt.AlignLeft)
        self.layout.addWidget(title)

        current_user = self.get_current_user_callback()
        if not current_user:
            label = QLabel("Vui lòng đăng nhập để tạo/tham gia nhóm.")
            label.setStyleSheet("color:white; font-size:14px;")
            self.layout.addWidget(label)
            self.layout.addStretch()
            return

        create_card = QFrame()
        create_card.setStyleSheet("""
            QFrame {
                background-color: rgba(0,0,0,0.26);
                border: 1px solid rgba(255,255,255,0.35);
                border-radius: 16px;
                padding: 10px;
            }
        """)
        create_layout = QHBoxLayout(create_card)
        create_layout.setSpacing(10)
        self.new_group_name = QLineEdit()
        self.new_group_name.setPlaceholderText("Tên group mới...")
        self.new_group_name.setFixedHeight(42)
        self.new_group_name.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255,255,255,0.95);
                border-radius: 21px;
                padding: 0 14px;
                border: 1px solid rgba(0,0,0,0.1);
                font-size: 13px;
            }
            QLineEdit:focus { border: 2px solid #4e73df; }
        """)
        btn_create_group = QPushButton("➕ Tạo group")
        btn_create_group.setStyleSheet(self.green_btn_style)
        btn_create_group.clicked.connect(self.handle_create_group)
        create_layout.addWidget(self.new_group_name, 1)
        create_layout.addWidget(btn_create_group)
        self.layout.addWidget(create_card)

        board = QFrame()
        board.setStyleSheet("""
            QFrame {
                background-color: rgba(0,0,0,0.22);
                border: 1px solid rgba(255,255,255,0.30);
                border-radius: 18px;
            }
        """)
        board_layout = QHBoxLayout(board)
        board_layout.setContentsMargins(12, 12, 12, 12)
        board_layout.setSpacing(12)

        list_panel = QFrame()
        list_panel.setFixedWidth(300)
        list_panel.setStyleSheet("""
            QFrame {
                background-color: rgba(255,255,255,0.08);
                border: 1px solid rgba(255,255,255,0.20);
                border-radius: 16px;
            }
        """)
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(10, 10, 10, 10)
        list_layout.setSpacing(8)
        list_layout.addWidget(self._build_section_title("💬 Danh sách nhóm"))

        detail_panel = QFrame()
        detail_panel.setStyleSheet("""
            QFrame {
                background-color: rgba(255,255,255,0.07);
                border: 1px solid rgba(255,255,255,0.20);
                border-radius: 16px;
            }
        """)
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(12, 12, 12, 12)
        detail_layout.setSpacing(10)

        if not groups:
            empty = QLabel("Chưa có group nào. Hãy tạo group đầu tiên!")
            empty.setStyleSheet("color: #eef2ff; font-size: 14px; padding: 10px;")
            empty.setAlignment(Qt.AlignCenter)
            list_layout.addWidget(empty)
            detail_layout.addWidget(QLabel(""))
        else:
            if not self.selected_group_id or not any(g.get("id") == self.selected_group_id for g in groups):
                self.selected_group_id = groups[0].get("id")

            selected_group = next((g for g in groups if g.get("id") == self.selected_group_id), groups[0])
            self.selected_group_id = selected_group.get("id")

            for group in groups:
                owner = group.get("owner", "Ẩn danh")
                members = group.get("members", [])
                pending = group.get("pending_members", [])
                joined = current_user in members
                label = f"{group.get('name', 'Nhóm')}\n👥 {len(members)} thành viên"
                if not joined and current_user in pending:
                    label += " | ⏳ chờ duyệt"
                elif joined:
                    label += " | ✅ đã tham gia"
                btn_group = QPushButton(label)
                btn_group.setCursor(Qt.PointingHandCursor)
                btn_group.setMinimumHeight(56)
                btn_group.setStyleSheet(f"""
                    QPushButton {{
                        text-align: left;
                        padding: 8px 12px;
                        color: white;
                        background-color: {'rgba(78,115,223,0.55)' if group.get('id') == self.selected_group_id else 'rgba(255,255,255,0.10)'};
                        border: 1px solid {'rgba(255,255,255,0.70)' if group.get('id') == self.selected_group_id else 'rgba(255,255,255,0.20)'};
                        border-radius: 14px;
                        font-size: 12px;
                        font-weight: bold;
                    }}
                    QPushButton:hover {{
                        background-color: rgba(78,115,223,0.40);
                    }}
                """)
                btn_group.clicked.connect(lambda _, gid=group.get("id"): self.handle_select_group(gid))
                list_layout.addWidget(btn_group)
            list_layout.addStretch()

            owner = selected_group.get("owner", "Ẩn danh")
            deputies = selected_group.get("deputies", [])
            members = selected_group.get("members", [])
            pending = selected_group.get("pending_members", [])
            group_posts = selected_group.get("posts", [])
            is_owner = current_user == owner
            is_deputy = current_user in deputies
            is_manager = is_owner or is_deputy
            is_member = current_user in members

            head_box = QFrame()
            head_box.setStyleSheet("background-color: rgba(255,255,255,0.08); border-radius: 12px; border: 1px solid rgba(255,255,255,0.25);")
            head_layout = QHBoxLayout(head_box)
            head_layout.setContentsMargins(10, 10, 10, 10)
            head_layout.setSpacing(10)
            head_layout.addWidget(build_avatar_label(selected_group.get("avatar", ""), 54))
            head_text = QVBoxLayout()
            head = QLabel(f"📌 {selected_group.get('name', 'Nhóm')}")
            head.setStyleSheet("color:white; font-size:16px; font-weight:bold;")
            head_meta = QLabel(f"Trưởng nhóm: {owner} | Thành viên: {len(members)}")
            head_meta.setStyleSheet("color:#dbeafe; font-size:12px; font-weight:bold;")
            head_text.addWidget(head)
            head_text.addWidget(head_meta)
            head_layout.addLayout(head_text, 1)
            if is_manager:
                btn_group_avatar = QPushButton("Ảnh nhóm")
                btn_group_avatar.setStyleSheet(self.primary_btn_style)
                btn_group_avatar.clicked.connect(lambda _, gid=selected_group.get("id"): self.handle_update_group_avatar(gid))
                head_layout.addWidget(btn_group_avatar)
            detail_layout.addWidget(head_box)

            action_row = QHBoxLayout()
            action_row.setSpacing(8)
            if not is_member:
                if current_user in pending:
                    waiting = QLabel("⏳ Đang chờ duyệt vào nhóm")
                    waiting.setStyleSheet("color:#ffe082; font-weight:bold;")
                    action_row.addWidget(waiting)
                else:
                    btn_join = QPushButton("Xin vào nhóm")
                    btn_join.setStyleSheet(self.primary_btn_style)
                    btn_join.clicked.connect(lambda _, gid=selected_group.get("id"): self.handle_join_request(gid))
                    action_row.addWidget(btn_join)
            else:
                btn_leave = QPushButton("Rời nhóm")
                btn_leave.setStyleSheet(self.primary_btn_style)
                btn_leave.clicked.connect(lambda _, gid=selected_group.get("id"): self.handle_leave_group(gid))
                action_row.addWidget(btn_leave)
            action_row.addStretch()
            detail_layout.addLayout(action_row)

            if is_member:
                post_box = QFrame()
                post_box.setStyleSheet("""
                    QFrame {
                        background-color: rgba(255,255,255,0.08);
                        border-radius: 12px;
                        border: 1px solid rgba(255,255,255,0.22);
                        padding: 10px;
                    }
                """)
                post_layout = QVBoxLayout(post_box)
                post_layout.setSpacing(8)
                post_layout.addWidget(self._build_section_title(f"📝 Đăng bài vào: {selected_group.get('name', 'Nhóm')}"))

                self.group_post_title = QLineEdit()
                self.group_post_title.setPlaceholderText("Tiêu đề bài viết...")
                self.group_post_title.setFixedHeight(38)
                self.group_post_title.setStyleSheet("background-color: rgba(255,255,255,0.95); border-radius: 10px; padding: 0 12px; border: 1px solid rgba(0,0,0,0.1);")
                self.group_post_content = QTextEdit()
                self.group_post_content.setPlaceholderText("Nội dung bài viết trong nhóm...")
                self.group_post_content.setFixedHeight(90)
                self.group_post_content.setStyleSheet("background-color: rgba(255,255,255,0.95); border-radius: 10px; padding: 10px; border: 1px solid rgba(0,0,0,0.1);")
                btn_post = QPushButton("Đăng vào nhóm đang chọn")
                btn_post.setStyleSheet(self.green_btn_style)
                btn_post.clicked.connect(lambda _, gid=selected_group.get("id"), t=self.group_post_title, c=self.group_post_content: self.handle_group_post(gid, t, c))
                post_layout.addWidget(self.group_post_title)
                post_layout.addWidget(self.group_post_content)
                post_layout.addWidget(btn_post)
                detail_layout.addWidget(post_box)

            if is_owner:
                owner_box = QFrame()
                owner_box.setStyleSheet("""
                    QFrame {
                        background-color: rgba(255,255,255,0.08);
                        border-radius: 12px;
                        border: 1px solid rgba(255,255,255,0.22);
                        padding: 10px;
                    }
                """)
                owner_layout = QVBoxLayout(owner_box)
                owner_layout.setSpacing(8)
                owner_layout.addWidget(self._build_section_title("👑 Quyền trưởng nhóm"))

                transfer_row = QHBoxLayout()
                transfer_options = [u for u in members if u != owner]
                if transfer_options:
                    transfer_combo = QComboBox()
                    transfer_combo.addItems(transfer_options)
                    transfer_combo.setStyleSheet("background-color: white; border-radius: 8px; padding: 4px;")
                    transfer_btn = QPushButton("Nhường trưởng nhóm")
                    transfer_btn.setStyleSheet(self.primary_btn_style)
                    transfer_btn.clicked.connect(lambda _, gid=selected_group.get("id"), c=transfer_combo: self.handle_transfer_owner(gid, c.currentText()))
                    transfer_row.addWidget(transfer_combo, 1)
                    transfer_row.addWidget(transfer_btn)
                else:
                    no_member = QLabel("Không có thành viên khác để nhường quyền.")
                    no_member.setStyleSheet("color: #ffe082; font-weight: bold;")
                    transfer_row.addWidget(no_member)
                owner_layout.addLayout(transfer_row)

                dissolve_btn = QPushButton("Giải tán nhóm")
                dissolve_btn.setStyleSheet(self.red_btn_style)
                dissolve_btn.clicked.connect(lambda _, gid=selected_group.get("id"): self.handle_dissolve_group(gid))
                owner_layout.addWidget(dissolve_btn, alignment=Qt.AlignLeft)
                detail_layout.addWidget(owner_box)

            if is_manager and pending:
                detail_layout.addWidget(self._build_section_title("✅ Yêu cầu tham gia"))
                for username in list(pending):
                    row = QHBoxLayout()
                    name = QLabel(f"• {username}")
                    name.setStyleSheet("color: white; font-weight: bold;")
                    row.addWidget(name, 1)
                    approve = QPushButton("Duyệt")
                    reject = QPushButton("Từ chối")
                    approve.setStyleSheet(self.green_btn_style)
                    reject.setStyleSheet(self.red_btn_style)
                    approve.clicked.connect(lambda _, gid=selected_group.get("id"), u=username: self.handle_review_request(gid, u, True))
                    reject.clicked.connect(lambda _, gid=selected_group.get("id"), u=username: self.handle_review_request(gid, u, False))
                    row.addWidget(approve)
                    row.addWidget(reject)
                    detail_layout.addLayout(row)

            if is_manager and members:
                detail_layout.addWidget(self._build_section_title("👤 Thành viên"))
                for username in list(members):
                    if username == owner:
                        continue
                    row = QHBoxLayout()
                    row.setSpacing(8)
                    role_text = "Phó nhóm" if username in deputies else "Thành viên"
                    role_label = QLabel(f"• {username} ({role_text})")
                    role_label.setStyleSheet("color:white; font-weight:bold;")
                    row.addWidget(role_label, 1)
                    if is_owner:
                        btn_deputy = QPushButton("Phó nhóm")
                        btn_deputy.setStyleSheet(self.primary_btn_style)
                        btn_deputy.clicked.connect(lambda _, gid=selected_group.get("id"), u=username: self.handle_toggle_deputy(gid, u))
                        row.addWidget(btn_deputy)
                    btn_remove = QPushButton("Xóa")
                    btn_remove.setStyleSheet(self.red_btn_style)
                    btn_remove.clicked.connect(lambda _, gid=selected_group.get("id"), u=username: self.handle_remove_member(gid, u))
                    row.addWidget(btn_remove)
                    detail_layout.addLayout(row)

            if is_member and group_posts:
                detail_layout.addWidget(self._build_section_title("📚 Bài viết trong nhóm"))
                for gp in group_posts:
                    prow = QFrame()
                    prow.setStyleSheet("""
                        QFrame {
                            background-color: rgba(255,255,255,0.08);
                            border-radius: 10px;
                            border: 1px solid rgba(255,255,255,0.2);
                            padding: 8px;
                        }
                    """)
                    prow_layout = QHBoxLayout(prow)
                    lbl = QLabel(f"• {gp.get('title','')} - {gp.get('author','Ẩn danh')} ({gp.get('date','')})")
                    lbl.setStyleSheet("color:white;")
                    lbl.setWordWrap(True)
                    prow_layout.addWidget(lbl, 1)
                    btn_view = QPushButton("Xem")
                    btn_view.setStyleSheet(self.primary_btn_style)
                    btn_view.clicked.connect(lambda _, post=gp: self.handle_view_group_post(post))
                    prow_layout.addWidget(btn_view)
                    can_edit = is_manager or gp.get("author") == current_user
                    if can_edit:
                        btn_edit_post = QPushButton("Sửa")
                        btn_edit_post.setStyleSheet(self.primary_btn_style)
                        btn_edit_post.clicked.connect(lambda _, gid=selected_group.get("id"), post=gp: self.handle_edit_group_post(gid, post))
                        prow_layout.addWidget(btn_edit_post)
                    can_delete = is_manager and (is_owner or gp.get("author") != owner)
                    if can_delete:
                        btn_del_post = QPushButton("Xóa bài")
                        btn_del_post.setStyleSheet(self.red_btn_style)
                        btn_del_post.clicked.connect(lambda _, gid=selected_group.get("id"), pid=gp.get("id"): self.handle_delete_group_post(gid, pid))
                        prow_layout.addWidget(btn_del_post)
                    detail_layout.addWidget(prow)
            elif (not is_member) and group_posts:
                hint = QLabel("🔒 Hãy tham gia nhóm để xem bài viết của nhóm.")
                hint.setStyleSheet("color:#dbeafe; font-size:13px;")
                detail_layout.addWidget(hint)

            detail_layout.addStretch()

        board_layout.addWidget(list_panel)
        board_layout.addWidget(detail_panel, 1)
        self.layout.addWidget(board)
        self.layout.addStretch()

    def handle_select_group(self, group_id):
        self.selected_group_id = group_id
        self.render_ui()

    def handle_create_group(self):
        name = self.new_group_name.text().strip()
        ok, msg = self.create_group_callback(name)
        self.show_message(msg, "success" if ok else "error")
        if ok:
            self.new_group_name.clear()
            self.render_ui()

    def handle_join_request(self, group_id):
        ok, msg = self.request_join_group_callback(group_id)
        self.show_message(msg, "success" if ok else "warning")
        if ok:
            self.render_ui()

    def handle_review_request(self, group_id, username, approved):
        ok, msg = self.review_join_request_callback(group_id, username, approved)
        self.show_message(msg, "success" if ok else "error")
        if ok:
            self.render_ui()

    def handle_remove_member(self, group_id, username):
        ok, msg = self.remove_member_callback(group_id, username)
        self.show_message(msg, "success" if ok else "error")
        if ok:
            self.render_ui()

    def handle_toggle_deputy(self, group_id, username):
        ok, msg = self.assign_deputy_callback(group_id, username)
        self.show_message(msg, "success" if ok else "error")
        if ok:
            self.render_ui()

    def handle_transfer_owner(self, group_id, username):
        ok, msg = self.transfer_owner_callback(group_id, username)
        self.show_message(msg, "success" if ok else "error")
        if ok:
            self.render_ui()

    def handle_dissolve_group(self, group_id):
        ok, msg = self.dissolve_group_callback(group_id)
        self.show_message(msg, "success" if ok else "error")
        if ok:
            self.render_ui()

    def handle_leave_group(self, group_id):
        ok, msg = self.leave_group_callback(group_id)
        self.show_message(msg, "success" if ok else "warning")
        if ok:
            self.render_ui()

    def handle_quick_group_post(self):
        group_id = self.quick_group_combo.currentData()
        title = self.quick_post_title.text().strip()
        content = self.quick_post_content.toPlainText().strip()
        ok, msg = self.create_group_post_callback(group_id, title, content)
        self.show_message(msg, "success" if ok else "error")
        if ok:
            self.quick_post_title.clear()
            self.quick_post_content.clear()
            self.render_ui()

    def handle_group_post(self, group_id, title_input, content_input):
        title = title_input.text().strip()
        content = content_input.toPlainText().strip()
        ok, msg = self.create_group_post_callback(group_id, title, content)
        self.show_message(msg, "success" if ok else "error")
        if ok:
            title_input.clear()
            content_input.clear()
            self.render_ui()

    def handle_view_group_post(self, group_post):
        self.view_group_post_callback(group_post)

    def handle_update_group_avatar(self, group_id):
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn ảnh nhóm", "", "Images (*.png *.jpg *.jpeg)")
        if not file_path:
            return
        ok, msg = self.update_group_avatar_callback(group_id, file_path)
        self.show_message(msg, "success" if ok else "error")
        if ok:
            self.render_ui()

    def handle_edit_group_post(self, group_id, group_post):
        dialog = EditPostDialog(group_post)
        if dialog.exec_() != QDialog.Accepted:
            return
        title, content = dialog.get_data()
        ok, msg = self.edit_group_post_callback(group_id, group_post.get("id"), title, content)
        self.show_message(msg, "success" if ok else "error")
        if ok:
            self.render_ui()

    def handle_delete_group_post(self, group_id, post_id):
        ok, msg = self.delete_group_post_callback(group_id, post_id)
        self.show_message(msg, "success" if ok else "error")
        if ok:
            self.render_ui()


class EditPostDialog(QDialog):
    def __init__(self, post):
        super().__init__()
        self.setWindowTitle("Chỉnh sửa bài viết")
        self.setMinimumWidth(600)

        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(12)

        self.title_input = QLineEdit(post["title"])
        self.title_input.setPlaceholderText("Tiêu đề")

        self.content_input = QTextEdit(post["content"])
        self.content_input.setPlaceholderText("Nội dung")

        self.layout.addWidget(QLabel("Tiêu đề"))
        self.layout.addWidget(self.title_input)
        self.layout.addWidget(QLabel("Nội dung"))
        self.layout.addWidget(self.content_input)

        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.layout.addWidget(button_box)


class StableDurationComboBox(QComboBox):
    """Combobox ổn định hơn trong QScrollArea, tránh popup đóng ngay do sự kiện dư."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._popup_opened_at = 0.0
        self.setFocusPolicy(Qt.StrongFocus)

    def showPopup(self):
        self._popup_opened_at = time.monotonic()
        super().showPopup()

    def hidePopup(self):
        # Tránh trường hợp popup vừa mở đã bị đóng ngay lập tức do sự kiện chuột/scroll chồng.
        if time.monotonic() - self._popup_opened_at < 0.15:
            return
        super().hidePopup()

    def wheelEvent(self, event):
        # Không cho wheel làm thay đổi item hoặc đóng popup ngoài ý muốn khi đang cuộn trang hồ sơ.
        if not self.hasFocus() and not self.view().isVisible():
            event.ignore()
            return
        super().wheelEvent(event)


class AuthGatePage(QWidget):
    def __init__(self, login_callback, register_callback, forgot_password_request_callback, forgot_password_confirm_callback, show_message_callback):
        super().__init__()
        self.login_callback = login_callback
        self.register_callback = register_callback
        self.forgot_password_request_callback = forgot_password_request_callback
        self.forgot_password_confirm_callback = forgot_password_confirm_callback
        self.show_message = show_message_callback

        root = QHBoxLayout(self)
        root.setContentsMargins(40, 30, 40, 30)
        root.setSpacing(20)

        intro = QFrame()
        intro.setMinimumWidth(760)
        intro.setStyleSheet("""
            QFrame {
                background-color: rgba(15,23,42,0.30);
                border: 1px solid rgba(255,255,255,0.35);
                border-radius: 16px;
            }
        """)
        intro_layout = QVBoxLayout(intro)
        intro_layout.setContentsMargins(24, 24, 24, 24)

        image_grid = QGridLayout()
        image_grid.setContentsMargins(0, 0, 0, 0)
        image_grid.setHorizontalSpacing(14)
        image_grid.setVerticalSpacing(14)

        image_names = ["anh1.jpg", "anh2.jpg", "anh3.jpg", "anh4.jpg"]
        for idx, image_name in enumerate(image_names):
            image_label = QLabel()
            image_label.setMinimumSize(330, 215)
            image_label.setSizePolicy(image_label.sizePolicy().Expanding, image_label.sizePolicy().Expanding)
            image_label.setAlignment(Qt.AlignCenter)

            pixmap = QPixmap(image_name)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    image_label.width(),
                    image_label.height(),
                    Qt.KeepAspectRatioByExpanding,
                    Qt.SmoothTransformation,
                )
                image_label.setPixmap(scaled)
                image_label.setStyleSheet("border-radius: 12px; border: 3px solid white; background-color: white;")
            else:
                image_label.setText(f"Không tìm thấy\n{image_name}")
                image_label.setStyleSheet(
                    "color: #e2e8f0; border-radius: 12px; border: 3px dashed rgba(255,255,255,0.9);"
                    "background-color: rgba(255,255,255,0.08); font-size: 12px;"
                )

            row = idx // 2
            col = idx % 2
            image_grid.addWidget(image_label, row, col)

        intro_layout.addLayout(image_grid)
        intro_layout.addStretch()

        form = QFrame()
        form.setFixedWidth(420)
        form.setStyleSheet("""
            QFrame {
                background-color: rgba(255,255,255,0.96);
                border-radius: 16px;
                border: 1px solid rgba(15,23,42,0.10);
            }
        """)
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(24, 24, 24, 24)
        form_layout.setSpacing(10)

        self.title = QLabel("Đăng nhập hệ thống")
        self.title.setStyleSheet("color:#0f172a; font-size:24px; font-weight:800;")

        # Đăng nhập / đăng ký
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Tên đăng nhập")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Mật khẩu")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Email (dùng cho khôi phục mật khẩu)")

        # Khôi phục mật khẩu
        self.reset_username_input = QLineEdit()
        self.reset_username_input.setPlaceholderText("Tên đăng nhập")
        self.reset_email_input = QLineEdit()
        self.reset_email_input.setPlaceholderText("Email đã đăng ký")
        self.reset_code_input = QLineEdit()
        self.reset_code_input.setPlaceholderText("Mã xác thực")
        self.reset_new_password_input = QLineEdit()
        self.reset_new_password_input.setPlaceholderText("Mật khẩu mới")
        self.reset_new_password_input.setEchoMode(QLineEdit.Password)

        for field in [
            self.username_input,
            self.password_input,
            self.email_input,
            self.reset_username_input,
            self.reset_email_input,
            self.reset_code_input,
            self.reset_new_password_input,
        ]:
            field.setFixedHeight(42)
            field.setStyleSheet("""
                QLineEdit {
                    background-color: #f8fafc;
                    color: #0f172a;
                    border: 1px solid #cbd5e1;
                    border-radius: 10px;
                    padding: 0 12px;
                }
                QLineEdit:focus { border: 2px solid #4f46e5; }
            """)

        self.btn_login = QPushButton("Đăng nhập")
        self.btn_register = QPushButton("Tạo tài khoản")
        self.btn_forgot = QPushButton("Quên mật khẩu?")

        self.btn_send_code = QPushButton("Gửi mã xác thực")
        self.btn_confirm_reset = QPushButton("Đổi mật khẩu mới")
        self.btn_back_login = QPushButton("← Trở lại")

        for btn in [self.btn_login, self.btn_register, self.btn_forgot, self.btn_send_code, self.btn_confirm_reset, self.btn_back_login]:
            btn.setFixedHeight(40)

        self.btn_login.setStyleSheet("""
            QPushButton { background-color: #4f46e5; color: white; border-radius: 10px; font-weight: bold; border: none; }
            QPushButton:hover { background-color: #4338ca; }
        """)
        self.btn_register.setStyleSheet("""
            QPushButton { background-color: white; color: #334155; border-radius: 10px; border: 1px solid #cbd5e1; font-weight: bold; }
            QPushButton:hover { background-color: #f8fafc; }
        """)
        self.btn_forgot.setStyleSheet("""
            QPushButton { background-color: transparent; color: #334155; border: 1px dashed #94a3b8; border-radius: 10px; font-weight: bold; }
            QPushButton:hover { background-color: #f8fafc; }
        """)
        self.btn_send_code.setStyleSheet("""
            QPushButton { background-color: #0ea5e9; color: white; border-radius: 10px; font-weight: bold; border: none; }
            QPushButton:hover { background-color: #0284c7; }
        """)
        self.btn_confirm_reset.setStyleSheet("""
            QPushButton { background-color: #10b981; color: white; border-radius: 10px; font-weight: bold; border: none; }
            QPushButton:hover { background-color: #059669; }
        """)
        self.btn_back_login.setFixedWidth(120)
        self.btn_back_login.setStyleSheet("""
            QPushButton { background-color: white; color: #334155; border-radius: 10px; border: 1px solid #cbd5e1; font-weight: bold; }
            QPushButton:hover { background-color: #f8fafc; }
        """)

        # Khối đăng nhập
        self.login_box = QFrame()
        login_box_layout = QVBoxLayout(self.login_box)
        login_box_layout.setContentsMargins(0, 0, 0, 0)
        login_box_layout.setSpacing(8)
        login_box_layout.addWidget(self.username_input)
        login_box_layout.addWidget(self.password_input)
        login_box_layout.addWidget(self.email_input)
        login_box_layout.addWidget(self.btn_login)
        login_box_layout.addWidget(self.btn_register)
        login_box_layout.addWidget(self.btn_forgot)

        # Khối quên mật khẩu (cùng bên phải, không mở cửa sổ)
        self.reset_box = QFrame()
        reset_box_layout = QVBoxLayout(self.reset_box)
        reset_box_layout.setContentsMargins(0, 0, 0, 0)
        reset_box_layout.setSpacing(8)
        reset_box_layout.addWidget(self.reset_username_input)
        reset_box_layout.addWidget(self.reset_email_input)
        reset_box_layout.addWidget(self.btn_send_code)
        reset_box_layout.addWidget(self.reset_code_input)
        reset_box_layout.addWidget(self.reset_new_password_input)
        reset_box_layout.addWidget(self.btn_confirm_reset)
        reset_box_layout.addWidget(self.btn_back_login, alignment=Qt.AlignLeft)

        self.btn_login.clicked.connect(self.handle_login)
        self.btn_register.clicked.connect(self.handle_register)
        self.btn_forgot.clicked.connect(self.show_reset_view)
        self.btn_send_code.clicked.connect(self.handle_send_reset_code)
        self.btn_confirm_reset.clicked.connect(self.handle_confirm_reset)
        self.btn_back_login.clicked.connect(self.show_login_view)
        self.password_input.returnPressed.connect(self.handle_login)

        form_layout.addWidget(self.title)
        form_layout.addSpacing(4)
        form_layout.addWidget(self.login_box)
        form_layout.addWidget(self.reset_box)
        form_layout.addStretch()

        root.addWidget(intro, 2)
        root.addWidget(form)

        self.show_login_view()

    def show_login_view(self):
        self.title.setText("Đăng nhập hệ thống")
        self.login_box.setVisible(True)
        self.reset_box.setVisible(False)

    def show_reset_view(self):
        self.title.setText("Khôi phục mật khẩu")
        self.login_box.setVisible(False)
        self.reset_box.setVisible(True)
        self.reset_username_input.setText(self.username_input.text().strip())
        self.reset_email_input.setText(self.email_input.text().strip())

    def handle_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        success, message, lock_notice = self.login_callback(username, password)
        if success:
            self.show_message(message, "success")
            self.clear_inputs()
        else:
            self.show_message(lock_notice or message, "warning")

    def handle_register(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        email = self.email_input.text().strip()
        success, message = self.register_callback(username, password, email)
        if success:
            self.show_message(message, "success")
            self.clear_inputs()
        else:
            self.show_message(message, "warning")

    def handle_send_reset_code(self):
        username = self.reset_username_input.text().strip()
        email = self.reset_email_input.text().strip()
        success, message = self.forgot_password_request_callback(username, email)
        self.show_message(message, "success" if success else "warning")

    def handle_confirm_reset(self):
        username = self.reset_username_input.text().strip()
        code = self.reset_code_input.text().strip()
        new_password = self.reset_new_password_input.text().strip()
        success, message = self.forgot_password_confirm_callback(username, code, new_password)
        self.show_message(message, "success" if success else "warning")
        if success:
            self.show_login_view()
            self.password_input.clear()
            self.password_input.setFocus()

    def clear_inputs(self):
        self.username_input.clear()
        self.password_input.clear()
        self.email_input.clear()
        self.reset_username_input.clear()
        self.reset_email_input.clear()
        self.reset_code_input.clear()
        self.reset_new_password_input.clear()


class ProfilePage(QWidget):
    def __init__(
        self,
        get_current_user_callback,
        login_callback,
        register_callback,
        logout_callback,
        refresh_home_callback,
        get_follow_stats_callback,
        toggle_follow_callback,
        get_user_avatar_callback,
        set_user_avatar_callback,
        show_message_callback,
        admin_suspend_callback,
        admin_delete_post_callback,
        back_callback,
        change_password_callback,
    ):
        super().__init__()
        self.get_current_user_callback = get_current_user_callback
        self.login_callback = login_callback
        self.register_callback = register_callback
        self.logout_callback = logout_callback
        self.refresh_home_callback = refresh_home_callback
        self.get_follow_stats_callback = get_follow_stats_callback
        self.toggle_follow_callback = toggle_follow_callback
        self.get_user_avatar_callback = get_user_avatar_callback
        self.set_user_avatar_callback = set_user_avatar_callback
        self.show_message = show_message_callback
        self.admin_suspend_callback = admin_suspend_callback
        self.admin_delete_post_callback = admin_delete_post_callback
        self.back_callback = back_callback
        self.change_password_callback = change_password_callback
        self.editing_post = None
        self.delete_pending_post_id = None

        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)

        self.profile_scroll = QScrollArea()
        self.profile_scroll.setWidgetResizable(True)
        self.profile_scroll.setStyleSheet("border: none;")

        self.profile_content = QWidget()
        self.layout = QVBoxLayout(self.profile_content)
        self.layout.setContentsMargins(170, 35, 170, 35)
        self.layout.setSpacing(15)

        self.profile_scroll.setWidget(self.profile_content)
        self.root_layout.addWidget(self.profile_scroll)

        self.render_ui()

    def render_ui(self):
        self.clear_layout()

        back_btn = QPushButton("← Quay lại")
        back_btn.setFixedWidth(120)
        back_btn.setFixedHeight(34)
        back_btn.setStyleSheet("background-color: rgba(255,255,255,0.95); color: #1e2a56; border: 1px solid rgba(0,0,0,0.12); border-radius: 17px; padding: 0 10px; font-weight: bold;")
        back_btn.clicked.connect(self.back_callback)

        title = QLabel("👤 Trang hồ sơ người dùng")
        title.setFont(QFont("Arial", 24, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: white;")
        self.layout.addWidget(back_btn, alignment=Qt.AlignLeft)
        self.layout.addWidget(title)

        current_user = self.get_current_user_callback()

        if not current_user:
            form_card = QFrame()
            form_card.setStyleSheet("""
                QFrame {
                    background-color: rgba(0,0,0,0.30);
                    border-radius: 20px;
                    border: 1px solid rgba(255,255,255,0.35);
                    padding: 20px;
                    margin-top: 10px;
                }
            """)
            form_layout = QVBoxLayout(form_card)
            form_layout.setSpacing(14)

            self.lock_notice_frame = QFrame()
            self.lock_notice_frame.setVisible(False)
            self.lock_notice_frame.setStyleSheet("""
                QFrame {
                    background-color: rgba(231, 74, 59, 0.24);
                    border: 1px solid rgba(255,255,255,0.55);
                    border-radius: 14px;
                    padding: 10px;
                }
            """)
            lock_notice_layout = QVBoxLayout(self.lock_notice_frame)
            lock_notice_layout.setContentsMargins(10, 8, 10, 8)
            self.lock_notice_label = QLabel("")
            self.lock_notice_label.setWordWrap(True)
            self.lock_notice_label.setStyleSheet("color: white; font-size: 13px; font-weight: bold;")
            lock_notice_layout.addWidget(self.lock_notice_label)

            subtitle = QLabel("Đăng nhập hoặc tạo tài khoản để đăng và quản lí bài viết")
            subtitle.setWordWrap(True)
            subtitle.setStyleSheet("color: #eef2ff; font-size: 13px;")

            self.username_input = QLineEdit()
            self.username_input.setPlaceholderText("Tên đăng nhập")
            self.password_input = QLineEdit()
            self.password_input.setPlaceholderText("Mật khẩu")
            self.password_input.setEchoMode(QLineEdit.Password)

            for widget in [self.username_input, self.password_input]:
                widget.setFixedHeight(44)
                widget.setStyleSheet("""
                    QLineEdit {
                        background-color: rgba(255,255,255,0.95);
                        border-radius: 22px;
                        padding: 0 14px;
                        border: 1px solid rgba(255,255,255,0.3);
                        font-size: 13px;
                    }
                    QLineEdit:focus {
                        border: 2px solid #8fb0ff;
                    }
                """)

            button_row = QHBoxLayout()
            button_row.setSpacing(12)

            btn_login = QPushButton("🔐 Đăng nhập")
            btn_register = QPushButton("📝 Đăng ký")
            for btn, color in [(btn_login, "#4e73df"), (btn_register, "#1cc88a")]:
                btn.setFixedHeight(44)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {color};
                        color: white;
                        border-radius: 22px;
                        font-weight: bold;
                        border: 1px solid rgba(255,255,255,0.35);
                        padding: 0 16px;
                    }}
                    QPushButton:hover {{
                        background-color: rgba(255,255,255,0.26);
                    }}
                    QPushButton:pressed {{
                        background-color: rgba(0,0,0,0.25);
                    }}
                """)

            btn_login.clicked.connect(self.handle_login)
            btn_register.clicked.connect(self.handle_register)

            button_row.addWidget(btn_login)
            button_row.addWidget(btn_register)

            form_layout.addWidget(subtitle)
            form_layout.addWidget(self.lock_notice_frame)
            form_layout.addWidget(self.username_input)
            form_layout.addWidget(self.password_input)
            form_layout.addLayout(button_row)
            self.layout.addWidget(form_card)
        else:
            followers_count, following_count = self.get_follow_stats_callback(current_user)

            welcome_card = QFrame()
            welcome_card.setStyleSheet("""
                QFrame {
                    background-color: rgba(0,0,0,0.28);
                    border-radius: 16px;
                    border: 1px solid rgba(255,255,255,0.35);
                    padding: 14px;
                }
            """)
            welcome_layout = QVBoxLayout(welcome_card)
            welcome_layout.setContentsMargins(18, 18, 18, 18)
            welcome_layout.setSpacing(12)

            avatar_row = QHBoxLayout()
            avatar_row.setContentsMargins(0, 4, 0, 4)
            avatar_row.setSpacing(12)

            avatar_wrapper = QFrame()
            avatar_wrapper.setFixedSize(94, 94)
            avatar_wrapper.setStyleSheet("background: transparent; border: none;")
            avatar_wrapper_layout = QVBoxLayout(avatar_wrapper)
            avatar_wrapper_layout.setContentsMargins(6, 6, 6, 6)
            avatar_wrapper_layout.addWidget(build_avatar_label(self.get_user_avatar_callback(current_user), 82), alignment=Qt.AlignCenter)
            avatar_row.addWidget(avatar_wrapper, 0, Qt.AlignVCenter)

            welcome_text = QVBoxLayout()
            welcome = QLabel(f"Xin chào, {current_user}!")
            welcome.setStyleSheet("color: white; font-size: 20px; font-weight: bold;")
            follow_info = QLabel(f"👥 Followers: {followers_count} | ➕ Following: {following_count}")
            follow_info.setStyleSheet("color: #e5f7ff; font-size: 14px; font-weight: bold;")
            welcome_text.addWidget(welcome)
            welcome_text.addWidget(follow_info)
            avatar_row.addLayout(welcome_text)
            avatar_row.addStretch()
            welcome_layout.addLayout(avatar_row)

            action_row = QHBoxLayout()

            btn_upload_avatar = QPushButton("🖼 Tải ảnh đại diện")
            btn_upload_avatar.clicked.connect(self.handle_upload_avatar)
            btn_upload_avatar.setFixedHeight(42)
            btn_upload_avatar.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255,255,255,0.92);
                    color: #1e2a56;
                    border-radius: 21px;
                    font-weight: bold;
                    border: 1px solid rgba(255,255,255,0.45);
                    padding: 0 14px;
                }
                QPushButton:hover {
                    background-color: #dbe4ff;
                }
            """)

            btn_logout = QPushButton("Đăng xuất")
            btn_logout.clicked.connect(self.handle_logout)
            btn_logout.setFixedWidth(150)
            btn_logout.setFixedHeight(42)
            btn_logout.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255,255,255,0.92);
                    color: #1e2a56;
                    border-radius: 21px;
                    font-weight: bold;
                    border: 1px solid rgba(255,255,255,0.45);
                    padding: 0 14px;
                }
                QPushButton:hover {
                    background-color: #dbe4ff;
                }
            """)

            action_row.addWidget(btn_upload_avatar)
            action_row.addWidget(btn_logout)
            action_row.addStretch()
            welcome_layout.addLayout(action_row)
            self.layout.addWidget(welcome_card)

            feature_card = QFrame()
            feature_card.setStyleSheet("""
                QFrame {
                    background-color: rgba(0,0,0,0.24);
                    border-radius: 16px;
                    border: 1px solid rgba(255,255,255,0.32);
                    padding: 10px;
                }
            """)
            feature_layout = QVBoxLayout(feature_card)
            feature_layout.setSpacing(10)
            feature_title = QLabel("⚙️ Tính năng hồ sơ")
            feature_title.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
            feature_layout.addWidget(feature_title)

            feature_btn_row = QHBoxLayout()
            feature_btn_row.setSpacing(10)

            section_buttons = []

            def build_section_button(text):
                btn = QPushButton(text)
                btn.setFixedHeight(40)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(255,255,255,0.92);
                        color: #1e2a56;
                        border-radius: 20px;
                        font-weight: bold;
                        border: 1px solid rgba(255,255,255,0.45);
                        padding: 0 14px;
                    }
                    QPushButton:hover {
                        background-color: #dbe4ff;
                    }
                """)
                section_buttons.append(btn)
                return btn

            self.feature_stack = QStackedWidget()
            self.feature_stack.setStyleSheet("border: none;")

            change_pwd_card = QFrame()
            change_pwd_card.setStyleSheet("""
                QFrame {
                    background-color: rgba(0,0,0,0.28);
                    border-radius: 16px;
                    border: 1px solid rgba(255,255,255,0.35);
                    padding: 12px;
                }
            """)
            change_layout = QVBoxLayout(change_pwd_card)
            change_layout.setSpacing(10)

            change_title = QLabel("🔐 Đổi mật khẩu")
            change_title.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")

            self.current_password_input = QLineEdit()
            self.current_password_input.setPlaceholderText("Mật khẩu hiện tại")
            self.current_password_input.setEchoMode(QLineEdit.Password)

            self.new_password_input = QLineEdit()
            self.new_password_input.setPlaceholderText("Mật khẩu mới")
            self.new_password_input.setEchoMode(QLineEdit.Password)

            self.confirm_new_password_input = QLineEdit()
            self.confirm_new_password_input.setPlaceholderText("Xác nhận mật khẩu mới")
            self.confirm_new_password_input.setEchoMode(QLineEdit.Password)

            for field in [self.current_password_input, self.new_password_input, self.confirm_new_password_input]:
                field.setFixedHeight(40)
                field.setStyleSheet("""
                    QLineEdit {
                        background-color: rgba(255,255,255,0.95);
                        border-radius: 20px;
                        padding: 0 12px;
                        border: 1px solid rgba(255,255,255,0.35);
                        font-size: 13px;
                    }
                    QLineEdit:focus {
                        border: 2px solid #8fb0ff;
                    }
                """)

            btn_change_pwd = QPushButton("Đổi mật khẩu")
            btn_change_pwd.setFixedHeight(40)
            btn_change_pwd.setStyleSheet("""
                QPushButton {
                    background-color: #4e73df;
                    color: white;
                    border-radius: 20px;
                    font-weight: bold;
                    border: 1px solid rgba(255,255,255,0.35);
                    padding: 0 14px;
                }
                QPushButton:hover {
                    background-color: #3558c9;
                }
            """)
            btn_change_pwd.clicked.connect(self.handle_change_password)

            change_layout.addWidget(change_title)
            change_layout.addWidget(self.current_password_input)
            change_layout.addWidget(self.new_password_input)
            change_layout.addWidget(self.confirm_new_password_input)
            change_layout.addWidget(btn_change_pwd)
            self.feature_stack.addWidget(change_pwd_card)

            follow_page = QWidget()
            follow_layout = QVBoxLayout(follow_page)
            follow_layout.setContentsMargins(0, 0, 0, 0)
            follow_layout.setSpacing(10)
            discover_label = QLabel("🤝 Theo dõi người dùng")
            discover_label.setStyleSheet("color: white; font-size: 17px; font-weight: bold;")
            follow_layout.addWidget(discover_label)
            for username in users.keys():
                if username == current_user:
                    continue
                row = QFrame()
                row_layout = QHBoxLayout(row)
                user_followers, _ = self.get_follow_stats_callback(username)
                row_layout.addWidget(build_avatar_label(self.get_user_avatar_callback(username), 34))
                info = QLabel(f"{username} - 👥 {user_followers} followers")
                info.setStyleSheet("color: white;")
                following = current_user in follows and username in follows.get(current_user, [])
                btn = QPushButton("Bỏ theo dõi" if following else "Theo dõi")
                btn.setFixedHeight(38)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(255,255,255,0.92);
                        color: #1e2a56;
                        border-radius: 19px;
                        font-weight: bold;
                        border: 1px solid rgba(255,255,255,0.45);
                        padding: 0 14px;
                    }
                    QPushButton:hover {
                        background-color: #dbe4ff;
                    }
                """)
                btn.clicked.connect(lambda _, target=username: self.handle_toggle_follow(target))
                row_layout.addWidget(info, 1)
                row_layout.addWidget(btn)
                follow_layout.addWidget(row)
            follow_layout.addStretch()
            self.feature_stack.addWidget(follow_page)

            post_page = QWidget()
            post_layout_main = QVBoxLayout(post_page)
            post_layout_main.setContentsMargins(0, 0, 0, 0)
            post_layout_main.setSpacing(10)
            my_posts_label = QLabel("📚 Quản lí bài viết của bạn")
            my_posts_label.setStyleSheet("color: white; font-size: 17px; font-weight: bold;")
            post_layout_main.addWidget(my_posts_label)
            my_posts = [post for post in posts if post.get("author") == current_user]
            if not my_posts:
                empty = QLabel("Bạn chưa đăng bài nào.")
                empty.setStyleSheet("color: #f1f1f1;")
                post_layout_main.addWidget(empty)
            else:
                if self.editing_post:
                    edit_card = QFrame()
                    edit_card.setStyleSheet("""
                        QFrame {
                            background-color: rgba(0,0,0,0.34);
                            border: 1px solid rgba(255,255,255,0.35);
                            border-radius: 18px;
                            padding: 14px;
                        }
                    """)
                    edit_layout = QVBoxLayout(edit_card)
                    edit_title = QLabel("✏ Chỉnh sửa bài viết")
                    edit_title.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
                    self.edit_title_input = QLineEdit(self.editing_post.get("title", ""))
                    self.edit_title_input.setPlaceholderText("Tiêu đề")
                    self.edit_content_input = QTextEdit(self.editing_post.get("content", ""))
                    self.edit_content_input.setPlaceholderText("Nội dung")
                    self.edit_title_input.setStyleSheet("""
                        QLineEdit {
                            background-color: rgba(255,255,255,0.95);
                            border-radius: 10px;
                            padding: 8px 10px;
                            border: 1px solid rgba(255,255,255,0.4);
                        }
                    """)
                    self.edit_content_input.setStyleSheet("""
                        QTextEdit {
                            background-color: rgba(255,255,255,0.95);
                            border-radius: 10px;
                            padding: 10px;
                            border: 1px solid rgba(255,255,255,0.4);
                            min-height: 120px;
                        }
                    """)
                    edit_action_row = QHBoxLayout()
                    btn_save_edit = QPushButton("💾 Lưu")
                    btn_cancel_edit = QPushButton("✖ Hủy")
                    for btn, color in [(btn_save_edit, "#1cc88a"), (btn_cancel_edit, "#e74a3b")]:
                        btn.setFixedHeight(40)
                        btn.setStyleSheet(f"""
                            QPushButton {{
                                background-color: {color};
                                color: white;
                                border-radius: 20px;
                                font-weight: bold;
                                border: 1px solid rgba(255,255,255,0.40);
                                padding: 0 16px;
                            }}
                            QPushButton:hover {{
                                background-color: rgba(255,255,255,0.28);
                            }}
                        """)
                    btn_save_edit.clicked.connect(self.handle_save_edit)
                    btn_cancel_edit.clicked.connect(self.handle_cancel_edit)
                    edit_action_row.addWidget(btn_save_edit)
                    edit_action_row.addWidget(btn_cancel_edit)
                    edit_action_row.addStretch()
                    edit_layout.addWidget(edit_title)
                    edit_layout.addWidget(self.edit_title_input)
                    edit_layout.addWidget(self.edit_content_input)
                    edit_layout.addLayout(edit_action_row)
                    post_layout_main.addWidget(edit_card)

                for post in my_posts:
                    post_card = QFrame()
                    post_card.setStyleSheet("""
                        QFrame {
                            background-color: rgba(0,0,0,0.30);
                            border: 1px solid rgba(255,255,255,0.30);
                            border-radius: 18px;
                            padding: 12px;
                        }
                    """)
                    post_layout = QHBoxLayout(post_card)
                    post_layout.setSpacing(12)
                    post_info = QLabel(
                        f"• {post['title']} ({post['date']}) | 👍 {len(post.get('likes', []))} | 💬 {len(post.get('comments', []))}"
                    )
                    post_info.setStyleSheet("color: white; font-weight: bold;")
                    post_info.setWordWrap(True)
                    btn_edit = QPushButton("✏ Sửa")
                    btn_delete = QPushButton("🗑 Xóa")
                    for btn, color in [(btn_edit, "#4e73df"), (btn_delete, "#e74a3b")]:
                        btn.setFixedWidth(100)
                        btn.setFixedHeight(40)
                        btn.setStyleSheet(f"""
                            QPushButton {{
                                background-color: {color};
                                color: white;
                                border-radius: 20px;
                                font-weight: bold;
                                border: 1px solid rgba(255,255,255,0.40);
                            }}
                            QPushButton:hover {{
                                background-color: rgba(255,255,255,0.28);
                            }}
                        """)
                    btn_edit.clicked.connect(lambda _, p=post: self.handle_edit_post(p))
                    btn_delete.clicked.connect(lambda _, p=post: self.handle_delete_post(p))
                    post_layout.addWidget(post_info, 1)
                    post_layout.addWidget(btn_edit)
                    post_layout.addWidget(btn_delete)
                    post_layout_main.addWidget(post_card)
            post_layout_main.addStretch()
            self.feature_stack.addWidget(post_page)

            admin_page = None
            if current_user == ADMIN_USERNAME:
                admin_page = QWidget()
                admin_layout = QVBoxLayout(admin_page)
                admin_layout.setContentsMargins(0, 0, 0, 0)
                admin_layout.setSpacing(10)
                admin_label = QLabel("🛡 Quản trị tài khoản & nội dung")
                admin_label.setStyleSheet("color: #fff; font-size: 17px; font-weight: bold;")
                admin_layout.addWidget(admin_label)
                for username in users.keys():
                    if username == ADMIN_USERNAME:
                        continue
                    row = QFrame()
                    row.setStyleSheet("""
                        QFrame {
                            background-color: rgba(0,0,0,0.25);
                            border: 1px solid rgba(255,255,255,0.28);
                            border-radius: 14px;
                            padding: 8px;
                        }
                    """)
                    row_layout = QHBoxLayout(row)
                    row_layout.setSpacing(10)
                    row_layout.addWidget(build_avatar_label(self.get_user_avatar_callback(username), 32))
                    info = QLabel(f"{username}")
                    info.setStyleSheet("color: white; font-weight: bold;")
                    suspend_box = StableDurationComboBox()
                    suspend_box.addItems(list(SUSPEND_CHOICES.keys()))
                    suspend_box.setStyleSheet("background-color: white; border-radius: 8px; padding: 4px;")
                    reason_input = QLineEdit()
                    reason_input.setPlaceholderText("Lý do khóa...")
                    reason_input.setMinimumWidth(220)
                    reason_input.setStyleSheet("background-color: white; border-radius: 8px; padding: 4px;")
                    btn_suspend = QPushButton("Khóa")
                    btn_suspend.setStyleSheet("background-color:#f6c23e; color:#1e2a56; border-radius:16px; padding:6px 12px; font-weight:bold;")
                    btn_suspend.clicked.connect(lambda _, u=username, b=suspend_box, r=reason_input: self.handle_admin_suspend(u, b.currentText(), r.text().strip()))
                    row_layout.addWidget(info, 1)
                    row_layout.addWidget(suspend_box)
                    row_layout.addWidget(reason_input)
                    row_layout.addWidget(btn_suspend)
                    admin_layout.addWidget(row)

                admin_post_label = QLabel("🗑 Xóa bài viết không phù hợp")
                admin_post_label.setStyleSheet("color: #fff; font-size: 16px; font-weight: bold;")
                admin_layout.addWidget(admin_post_label)

                for post in posts:
                    if post.get("author") == ADMIN_USERNAME:
                        continue
                    row = QFrame()
                    row.setStyleSheet("""
                        QFrame {
                            background-color: rgba(0,0,0,0.22);
                            border: 1px solid rgba(255,255,255,0.25);
                            border-radius: 12px;
                            padding: 6px;
                        }
                    """)
                    row_layout = QHBoxLayout(row)
                    txt = QLabel(f"• {post.get('title','(Không tiêu đề)')} - {post.get('author','Ẩn danh')}")
                    txt.setStyleSheet("color: white;")
                    btn_remove = QPushButton("Xóa bài")
                    btn_remove.setStyleSheet("background-color:#e74a3b; color:white; border-radius:16px; padding:6px 12px; font-weight:bold;")
                    btn_remove.clicked.connect(lambda _, p=post: self.handle_admin_delete_post(p))
                    row_layout.addWidget(txt, 1)
                    row_layout.addWidget(btn_remove)
                    admin_layout.addWidget(row)
                admin_layout.addStretch()
                self.feature_stack.addWidget(admin_page)

            nav_items = [
                ("🔐 Đổi mật khẩu", 0),
                ("🤝 Theo dõi", 1),
                ("📚 Bài viết", 2),
            ]
            if admin_page:
                nav_items.append(("🛡 Quản trị", 3))

            for label, index in nav_items:
                btn = build_section_button(label)
                btn.clicked.connect(lambda _, i=index: self.feature_stack.setCurrentIndex(i))
                feature_btn_row.addWidget(btn)

            feature_layout.addLayout(feature_btn_row)
            feature_layout.addWidget(self.feature_stack)
            self.layout.addWidget(feature_card)

        self.layout.addStretch()

    def clear_layout(self):
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def handle_upload_avatar(self):
        current_user = self.get_current_user_callback()
        if not current_user:
            self.show_message("Bạn cần đăng nhập để cập nhật avatar!", "warning")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn ảnh đại diện", "", "Images (*.png *.jpg *.jpeg)"
        )
        if file_path:
            self.set_user_avatar_callback(current_user, file_path)
            self.show_message("Cập nhật ảnh đại diện thành công!", "success")
        self.render_ui()

    def handle_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        success, message, lock_notice = self.login_callback(username, password)
        if success:
            self.show_message("Đăng nhập thành công!", "success")
            self.render_ui()
        else:
            if lock_notice:
                self.lock_notice_label.setText(lock_notice)
                self.lock_notice_frame.setVisible(True)
                self.show_message(message, "warning")
            else:
                self.lock_notice_frame.setVisible(False)
                self.show_message(message, "error")

    def handle_register(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        email = self.email_input.text().strip()
        success, message = self.register_callback(username, password, email)
        if success:
            self.show_message(message, "success")
            self.render_ui()
        else:
            self.show_message(message, "error")

    def handle_logout(self):
        self.logout_callback()
        self.show_message("Đã đăng xuất!", "info")
        self.render_ui()

    def handle_toggle_follow(self, target_user):
        self.toggle_follow_callback(target_user)
        self.render_ui()

    def handle_change_password(self):
        current_user = self.get_current_user_callback()
        if not current_user:
            self.show_message("Bạn cần đăng nhập.", "warning")
            return

        current_password = self.current_password_input.text().strip()
        new_password = self.new_password_input.text().strip()
        confirm_password = self.confirm_new_password_input.text().strip()

        success, message = self.change_password_callback(
            current_user,
            current_password,
            new_password,
            confirm_password,
        )
        self.show_message(message, "success" if success else "warning")
        if success:
            self.current_password_input.clear()
            self.new_password_input.clear()
            self.confirm_new_password_input.clear()

    def handle_edit_post(self, post):
        self.editing_post = post
        self.render_ui()

    def handle_save_edit(self):
        if not self.editing_post:
            return

        title = self.edit_title_input.text().strip()
        content = self.edit_content_input.toPlainText().strip()
        if not title or not content:
            self.show_message("Tiêu đề và nội dung không được để trống!", "error")
            return

        self.editing_post["title"] = title
        self.editing_post["content"] = content
        self.editing_post = None
        save_posts(posts)
        self.show_message("Đã cập nhật bài viết!", "success")
        self.render_ui()

    def handle_cancel_edit(self):
        self.editing_post = None
        self.render_ui()

    def handle_delete_post(self, post):
        post_id = post.get("id")
        if self.delete_pending_post_id != post_id:
            self.delete_pending_post_id = post_id
            QTimer.singleShot(2000, self.reset_delete_pending)
            self.show_message("Nhấn Xóa lần nữa để xác nhận xóa bài viết.", "warning")
            return

        self.delete_pending_post_id = None
        posts.remove(post)
        if self.editing_post is post:
            self.editing_post = None
        save_posts(posts)
        self.show_message("Đã xóa bài viết!", "success")
        self.render_ui()

    def reset_delete_pending(self):
        self.delete_pending_post_id = None

    def handle_admin_suspend(self, target_user, duration_label, reason):
        success, message = self.admin_suspend_callback(target_user, duration_label, reason)
        self.show_message(message, "success" if success else "error")
        if success:
            self.render_ui()

    def handle_admin_delete_post(self, post):
        success, message = self.admin_delete_post_callback(post)
        self.show_message(message, "success" if success else "error")
        if success:
            self.render_ui()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.current_user = None
        self.password_reset_tokens = {}
        self.selected_notification = None
        self.notification_anchor_widget = None

        self.setWindowTitle("NovaNews Desktop")
        self.resize(1440, 900)

        self.main_layout = QVBoxLayout(self)

        self.app_title = QLabel("📰 NovaNews Desktop")
        self.app_title.setFont(QFont("Arial", 32, QFont.Bold))
        self.app_title.setAlignment(Qt.AlignCenter)
        self.app_title.setStyleSheet("""
            color: white;
            padding: 20px;
            letter-spacing: 2px;
        """)

        self.main_layout.addWidget(self.app_title)

        self.menu_bar = QFrame()
        self.menu_bar.setStyleSheet("background: transparent;")
        menu_layout = QHBoxLayout(self.menu_bar)
        menu_layout.setContentsMargins(0, 0, 0, 0)
        menu_layout.setSpacing(25)
        menu_layout.setAlignment(Qt.AlignCenter)

        self.btn_home = QPushButton("🏠 Home")
        self.btn_create = QPushButton("🌐 Top stories")
        self.btn_profile = QPushButton("👤 Profile")
        self.btn_groups = QPushButton("👥 Groups")

        for btn in [self.btn_home, self.btn_create, self.btn_profile, self.btn_groups]:
            btn.setFixedSize(165, 54)
            btn.setFont(QFont("Arial", 12, QFont.Bold))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255,255,255,0.98);
                    color: #1e293b;
                    border-radius: 24px;
                    border: 1px solid #e2e8f0;
                    padding: 0 14px;
                }
                QPushButton:hover {
                    background-color: #f8fafc;
                }
                QPushButton:pressed {
                    background-color: #eef2ff;
                }
            """)

        self.btn_notify = QPushButton("🔔")
        self.btn_notify.setFixedSize(70, 55)
        self.btn_notify.setFont(QFont("Arial", 18, QFont.Bold))
        self.btn_notify.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.96);
                border-radius: 27px;
                border: 1px solid rgba(0,0,0,0.1);
            }
            QPushButton:hover {
                background-color: #dbe4ff;
            }
        """)
        self.btn_notify.clicked.connect(self.toggle_notification_panel)

        self.notify_badge = QLabel("0")
        self.notify_badge.setAlignment(Qt.AlignCenter)
        self.notify_badge.setFixedSize(20, 20)
        self.notify_badge.setStyleSheet("""
            QLabel {
                background-color: #e74a3b;
                color: white;
                border: 1px solid rgba(255,255,255,0.85);
                border-radius: 10px;
                font-size: 10px;
                font-weight: bold;
            }
        """)

        self.notify_wrapper = QFrame()
        notify_layout = QGridLayout(self.notify_wrapper)
        notify_layout.setContentsMargins(0, 0, 0, 0)
        notify_layout.setHorizontalSpacing(0)
        notify_layout.setVerticalSpacing(0)
        notify_layout.addWidget(self.btn_notify, 0, 0, alignment=Qt.AlignCenter)
        notify_layout.addWidget(self.notify_badge, 0, 0, alignment=Qt.AlignTop | Qt.AlignRight)

        self.btn_home.clicked.connect(self.show_home)
        self.btn_create.clicked.connect(self.show_create)
        self.btn_profile.clicked.connect(self.show_profile)
        self.btn_groups.clicked.connect(self.show_groups)

        menu_layout.addWidget(self.btn_home)
        menu_layout.addWidget(self.btn_create)
        menu_layout.addWidget(self.btn_profile)
        menu_layout.addWidget(self.btn_groups)
        menu_layout.addWidget(self.notify_wrapper)

        self.main_layout.addWidget(self.menu_bar)

        self.notification_panel = QFrame(self)
        self.notification_panel.setVisible(False)
        self.notification_panel.setFixedWidth(420)
        self.notification_panel.setFixedHeight(500)
        self.notification_panel.setStyleSheet("""
            QFrame {
                background-color: rgba(15,23,42,0.95);
                border: 1px solid rgba(255,255,255,0.45);
                border-radius: 16px;
            }
        """)

        panel_layout = QVBoxLayout(self.notification_panel)
        panel_layout.setContentsMargins(12, 12, 12, 12)
        panel_layout.setSpacing(8)

        panel_title = QLabel("🔔 Thông báo")
        panel_title.setStyleSheet(
            "color: white; font-size: 17px; font-weight: bold;"
            "padding: 6px 10px;"
            "background-color: rgba(255,255,255,0.08);"
            "border-radius: 10px;"
            "border: 1px solid rgba(255,255,255,0.25);"
        )

        action_row = QHBoxLayout()
        self.btn_mark_read = QPushButton("✓ Đánh dấu đã đọc")
        self.btn_delete_selected = QPushButton("🗑 Xóa đã chọn")

        for btn, bg, hover, pressed in [
            (self.btn_mark_read, "#4e73df", "#3f63c9", "#3555ad"),
            (self.btn_delete_selected, "#e74a3b", "#d83b2e", "#bf3327")
        ]:
            btn.setFixedHeight(36)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: white;
                    border-radius: 18px;
                    font-size: 12px;
                    font-weight: bold;
                    border: 1px solid rgba(255,255,255,0.40);
                    padding: 0 12px;
                }}
                QPushButton:hover {{
                    background-color: {hover};
                    border: 1px solid rgba(255,255,255,0.65);
                }}
                QPushButton:pressed {{
                    background-color: {pressed};
                }}
            """)

        self.btn_mark_read.clicked.connect(self.mark_all_notifications_read)
        self.btn_delete_selected.clicked.connect(self.delete_selected_notification)
        action_row.addWidget(self.btn_mark_read)
        action_row.addWidget(self.btn_delete_selected)
        action_row.addStretch()

        self.notification_scroll = QScrollArea()
        self.notification_scroll.setWidgetResizable(True)
        self.notification_scroll.setStyleSheet("border: none;")

        self.notification_container = QWidget()
        self.notification_layout = QVBoxLayout(self.notification_container)
        self.notification_layout.setContentsMargins(0, 0, 0, 0)
        self.notification_layout.setSpacing(8)
        self.notification_scroll.setWidget(self.notification_container)

        panel_layout.addWidget(panel_title)
        panel_layout.addLayout(action_row)
        panel_layout.addWidget(self.notification_scroll)

        self.content_area = QVBoxLayout()
        self.main_layout.addLayout(self.content_area)

        self.toast = InlineToast(self)

        self.update_auth_state()
        self.update_notification_badge()
        QApplication.instance().installEventFilter(self)

    def update_auth_state(self):
        logged_in = bool(self.current_user)
        self.menu_bar.setVisible(False)
        self.notification_panel.setVisible(False)
        self.selected_notification = None
        self.notification_anchor_widget = None
        self.notify_badge.setVisible(False)
        self.btn_notify.setVisible(False)
        self.app_title.setVisible(not logged_in)

        if logged_in:
            self.show_home()
        else:
            self.show_auth_gate()

    def show_auth_gate(self):
        self.clear_content()
        self.auth_gate_page = AuthGatePage(
            self.login_user,
            self.register_user,
            self.request_password_reset,
            self.confirm_password_reset,
            self.show_inline_message,
        )
        self.content_area.addWidget(self.auth_gate_page)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.toast.isVisible():
            self.toast.show_message(self.toast.text_label.text(), "info", max(1, self.toast.timer.remainingTime()))

    def show_inline_message(self, text, level="info", timeout=4500):
        self.toast.show_message(text, level, timeout)

    def get_current_user(self):
        return self.current_user

    def get_user_avatar(self, username):
        if username not in users:
            return ""
        user_data = users.get(username, {})
        if isinstance(user_data, dict):
            return user_data.get("avatar", "")
        return ""

    def set_user_avatar(self, username, avatar_path):
        if username not in users:
            return
        user_data = users.get(username)
        if isinstance(user_data, str):
            users[username] = {
                "password": user_data,
                "avatar": avatar_path,
                "suspended_until": "",
                "suspend_reason": "",
                "suspended_by": "",
                "suspended_at": "",
                "suspend_duration_label": "",
                "email": "",
            }
        else:
            users[username]["avatar"] = avatar_path
        save_users(users)

    def get_follow_stats(self, username):
        following_count = len(follows.get(username, []))
        followers_count = sum(1 for us, lst in follows.items() if username in lst and us != username)
        return followers_count, following_count

    def get_followers_count(self, username):
        followers_count, _ = self.get_follow_stats(username)
        return followers_count

    def toggle_follow_user(self, target_user):
        current_user = self.get_current_user()
        if not current_user:
            return
        follows.setdefault(current_user, [])
        if target_user in follows[current_user]:
            follows[current_user].remove(target_user)
        else:
            follows[current_user].append(target_user)
        save_follows(follows)

    def login_user(self, username, password):
        user_data = users.get(username)
        if isinstance(user_data, str):
            valid = user_data == password
        elif isinstance(user_data, dict):
            valid = user_data.get("password") == password
        else:
            valid = False

        if not valid:
            return False, "Sai tài khoản hoặc mật khẩu!", ""

        if valid:
            suspended, suspend_message = get_suspend_status(user_data)
            if suspended:
                lock_notice = get_suspend_notice(user_data)
                return False, suspend_message, lock_notice

            if isinstance(user_data, dict):
                suspended_until = user_data.get("suspended_until", "")
                if suspended_until and suspended_until != "permanent":
                    user_data["suspended_until"] = ""
                    user_data["suspend_reason"] = ""
                    user_data["suspended_by"] = ""
                    user_data["suspended_at"] = ""
                    user_data["suspend_duration_label"] = ""
                    save_users(users)

        self.current_user = username
        follows.setdefault(username, [])
        notifications.setdefault(username, [])
        save_follows(follows)
        save_notifications(notifications)
        self.update_notification_badge()
        self.render_notifications()
        self.update_auth_state()
        return True, "Đăng nhập thành công!", ""

    def register_user(self, username, password, email=""):
        if not username or not password:
            return False, "Vui lòng nhập đầy đủ thông tin!"
        if username in users:
            return False, "Tên đăng nhập đã tồn tại!"
        if username == ADMIN_USERNAME:
            return False, "Tên này là tài khoản đặc biệt của hệ thống."

        users[username] = {
            "password": password,
            "avatar": "",
            "suspended_until": "",
            "suspend_reason": "",
            "suspended_by": "",
            "suspended_at": "",
            "suspend_duration_label": "",
            "email": email,
        }
        save_users(users)
        follows.setdefault(username, [])
        notifications.setdefault(username, [])
        save_follows(follows)
        save_notifications(notifications)
        self.current_user = username
        self.update_notification_badge()
        self.render_notifications()
        self.update_auth_state()
        return True, "Đăng ký thành công và đã đăng nhập!"


    def send_reset_code_email(self, to_email, username, code):
        smtp_host = os.getenv("SMTP_HOST", "")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER", "")
        smtp_pass = os.getenv("SMTP_PASS", "")
        smtp_from = os.getenv("SMTP_FROM", smtp_user)

        if not all([smtp_host, smtp_user, smtp_pass, smtp_from]):
            return False

        body = (
            f"Xin chào {username},\n\n"
            f"Mã xác thực đổi mật khẩu của bạn là: {code}\n"
            "Mã có hiệu lực trong 10 phút.\n\n"
            "NovaNews Desktop"
        )
        msg = MIMEText(body, _charset="utf-8")
        msg["Subject"] = "NovaNews - Mã xác thực đổi mật khẩu"
        msg["From"] = smtp_from
        msg["To"] = to_email

        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            return True
        except Exception:
            return False

    def request_password_reset(self, username, email):
        if not username or not email:
            return False, "Vui lòng nhập tên đăng nhập và email."

        user_data = users.get(username)
        if not isinstance(user_data, dict):
            return False, "Không tìm thấy tài khoản phù hợp."

        saved_email = user_data.get("email", "").strip().lower()
        if not saved_email:
            return False, "Tài khoản này chưa có email khôi phục. Hãy liên hệ quản trị viên."
        if saved_email != email.strip().lower():
            return False, "Email không khớp với tài khoản đã đăng ký."

        code = f"{random.randint(0, 999999):06d}"
        self.password_reset_tokens[username] = {
            "code": code,
            "expires_at": datetime.now() + timedelta(minutes=10),
        }

        sent = self.send_reset_code_email(email, username, code)
        if sent:
            return True, "Đã gửi mã xác thực qua email. Vui lòng kiểm tra hộp thư."
        return True, f"Không gửi được email trong môi trường hiện tại. Mã xác thực tạm thời: {code}"

    def confirm_password_reset(self, username, code, new_password):
        if not username or not code or not new_password:
            return False, "Vui lòng nhập đầy đủ thông tin."
        if len(new_password) < 6:
            return False, "Mật khẩu mới cần ít nhất 6 ký tự."

        token_info = self.password_reset_tokens.get(username)
        if not token_info:
            return False, "Chưa có yêu cầu khôi phục mật khẩu cho tài khoản này."

        if datetime.now() > token_info.get("expires_at", datetime.now()):
            self.password_reset_tokens.pop(username, None)
            return False, "Mã xác thực đã hết hạn. Vui lòng gửi lại mã mới."

        if token_info.get("code") != code:
            return False, "Mã xác thực không đúng."

        user_data = users.get(username)
        if not isinstance(user_data, dict):
            return False, "Không tìm thấy tài khoản."

        user_data["password"] = new_password
        save_users(users)
        self.password_reset_tokens.pop(username, None)
        return True, "Đổi mật khẩu thành công. Bạn có thể đăng nhập bằng mật khẩu mới."

    def change_password_user(self, username, current_password, new_password, confirm_password):
        if not username:
            return False, "Không xác định người dùng."
        user_data = users.get(username)
        if not isinstance(user_data, dict):
            return False, "Không tìm thấy tài khoản."

        if user_data.get("password", "") != current_password:
            return False, "Mật khẩu hiện tại không đúng."
        if not new_password or len(new_password) < 6:
            return False, "Mật khẩu mới cần ít nhất 6 ký tự."
        if new_password != confirm_password:
            return False, "Xác nhận mật khẩu mới không khớp."
        if new_password == current_password:
            return False, "Mật khẩu mới phải khác mật khẩu hiện tại."

        user_data["password"] = new_password
        save_users(users)
        return True, "Đổi mật khẩu thành công."

    def logout_user(self):
        self.current_user = None
        self.password_reset_tokens = {}
        self.selected_notification = None
        self.update_notification_badge()
        self.render_notifications()
        self.update_auth_state()

    def save_all(self):
        save_posts(posts)
        save_follows(follows)
        save_notifications(notifications)
        save_groups(groups)

    def create_interaction_notification(self, post, actor, action):
        author = post.get("author")
        if not author or actor == author:
            return

        notifications.setdefault(author, [])
        action_text = "đã thích" if action == "like" else "đã bình luận"

        notifications[author].insert(0, {
            "id": str(uuid.uuid4()),
            "post_id": post.get("id", ""),
            "actor": actor,
            "action": action,
            "message": f"{actor} {action_text} bài viết của bạn: {post.get('title', '')}",
            "date": now_text(),
            "read": False
        })
        save_notifications(notifications)
        self.update_notification_badge()
        self.render_notifications()

    def push_activity_notification(self, recipient, actor, action, message, post_id=""):
        if not recipient or recipient == actor:
            return

        notifications.setdefault(recipient, [])
        notifications[recipient].insert(0, {
            "id": str(uuid.uuid4()),
            "post_id": post_id,
            "actor": actor,
            "action": action,
            "message": message,
            "date": now_text(),
            "read": False,
        })

    def notify_new_post_activity(self, post):
        author = post.get("author", "")
        if not author:
            return

        for username, following_list in follows.items():
            if username != author and author in following_list:
                self.push_activity_notification(
                    username,
                    author,
                    "following_post",
                    f"{author} (người bạn theo dõi) vừa đăng bài mới: {post.get('title', '')}",
                    post.get("id", ""),
                )

        save_notifications(notifications)
        self.update_notification_badge()
        self.render_notifications()

    def get_notifications_for_current_user(self):
        if not self.current_user:
            return []
        return notifications.get(self.current_user, [])

    def get_unread_notifications_count(self):
        unread_count = 0
        for item in self.get_notifications_for_current_user():
            if not item.get("read", False):
                unread_count += 1
        return unread_count

    def update_notification_badge(self):
        unread_count = self.get_unread_notifications_count()
        self.notify_badge.setText(str(unread_count))
        show_count = unread_count if not self.notification_panel.isVisible() else 0
        self.notify_badge.setVisible(show_count > 0)
        if hasattr(self, "home") and self.home:
            self.home.update_notify_badge(show_count)

    def position_notification_panel(self):
        anchor = self.notification_anchor_widget if self.notification_anchor_widget else self.notify_wrapper
        bell_top_right = anchor.mapTo(self, anchor.rect().topRight())
        x = bell_top_right.x() + 2
        y = bell_top_right.y() - 2

        max_x = self.width() - self.notification_panel.width() - 12
        max_y = self.height() - self.notification_panel.height() - 12
        x = max(12, min(x, max_x))
        y = max(12, min(y, max_y))

        self.notification_panel.move(x, y)

    def show_notification_panel(self):
        self.position_notification_panel()
        self.render_notifications()
        self.notification_panel.show()
        self.notification_panel.raise_()
        self.notify_badge.setVisible(False)
        if hasattr(self, "home") and self.home:
            self.home.update_notify_badge(0)

    def hide_notification_panel(self):
        self.notification_panel.hide()
        self.update_notification_badge()

    def toggle_notification_panel(self, source_widget=None):
        if source_widget is not None:
            self.notification_anchor_widget = source_widget
        elif self.notification_anchor_widget is None:
            self.notification_anchor_widget = self.notify_wrapper

        if self.notification_panel.isVisible():
            self.hide_notification_panel()
        else:
            self.show_notification_panel()

    def eventFilter(self, watched, event):
        if self.notification_panel.isVisible() and event.type() == QEvent.MouseButtonPress:
            clicked_widget = QApplication.widgetAt(event.globalPos())
            if clicked_widget:
                if (
                    clicked_widget is self.notification_panel
                    or self.notification_panel.isAncestorOf(clicked_widget)
                    or clicked_widget is self.btn_notify
                    or clicked_widget is self.notify_badge
                    or self.notify_wrapper.isAncestorOf(clicked_widget)
                    or (
                        self.notification_anchor_widget
                        and (
                            clicked_widget is self.notification_anchor_widget
                            or self.notification_anchor_widget.isAncestorOf(clicked_widget)
                        )
                    )
                ):
                    return super().eventFilter(watched, event)
            self.hide_notification_panel()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.notification_panel.isVisible():
            self.position_notification_panel()

    def clear_notification_widgets(self):
        while self.notification_layout.count():
            item = self.notification_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def render_notifications(self):
        self.clear_notification_widgets()
        current_items = self.get_notifications_for_current_user()

        if self.selected_notification not in current_items:
            self.selected_notification = None

        self.btn_delete_selected.setEnabled(bool(self.selected_notification))

        if not self.current_user:
            label = QLabel("Vui lòng đăng nhập để xem thông báo.")
            label.setStyleSheet("color: #f1f1f1;")
            self.notification_layout.addWidget(label)
        elif not current_items:
            label = QLabel("Bạn chưa có thông báo nào.")
            label.setStyleSheet("color: #f1f1f1;")
            self.notification_layout.addWidget(label)
        else:
            for item in current_items:
                is_selected = item is self.selected_notification
                row = QFrame()
                row.setStyleSheet("""
                    QFrame {
                        background-color: rgba(255,255,255,0.12);
                        border-radius: 10px;
                        border: 1px solid rgba(255,255,255,0.25);
                        padding: 8px;
                    }
                """ if not is_selected else """
                    QFrame {
                        background-color: rgba(78,115,223,0.35);
                        border-radius: 10px;
                        border: 1px solid rgba(255,255,255,0.85);
                        padding: 8px;
                    }
                """)
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(10, 8, 10, 8)
                row_layout.setSpacing(8)

                text = item.get("message", "Thông báo")
                if not item.get("read", False):
                    text = "🔵 " + text
                relative = relative_time_text(item.get('date', ''))
                time_line = f"🕒 {item.get('date', '')}"
                if relative:
                    time_line += f" ({relative})"
                label = QLabel(f"{text}\n{time_line}")
                label.setWordWrap(True)
                label.setStyleSheet("color: white;")

                open_btn = QPushButton("Mở")
                open_btn.setFixedWidth(60)
                open_btn.clicked.connect(lambda _, n=item: self.open_notification(n))

                remove_btn = QPushButton("Xóa")
                remove_btn.setFixedWidth(60)
                remove_btn.clicked.connect(lambda _, n=item: self.delete_notification(n))

                row_layout.addWidget(label, 1)
                row_layout.addWidget(open_btn)
                row_layout.addWidget(remove_btn)

                row.mousePressEvent = lambda e, n=item: self.select_notification(n)
                label.mousePressEvent = lambda e, n=item: self.select_notification(n)

                self.notification_layout.addWidget(row)

        self.notification_layout.addStretch()
        self.update_notification_badge()

    def select_notification(self, notification_item):
        if not self.current_user:
            return
        self.selected_notification = notification_item
        if not notification_item.get("read", False):
            notification_item["read"] = True
            save_notifications(notifications)
        self.render_notifications()

    def delete_selected_notification(self):
        if not self.current_user or not self.selected_notification:
            return
        self.delete_notification(self.selected_notification)

    def mark_all_notifications_read(self):
        if not self.current_user:
            return
        for item in notifications.get(self.current_user, []):
            item["read"] = True
        save_notifications(notifications)
        self.render_notifications()

    def clear_notifications(self):
        if not self.current_user:
            return
        notifications[self.current_user] = []
        save_notifications(notifications)
        self.render_notifications()

    def delete_notification(self, notification_item):
        if not self.current_user:
            return
        user_notifications = notifications.get(self.current_user, [])
        if notification_item in user_notifications:
            user_notifications.remove(notification_item)
            save_notifications(notifications)
        self.render_notifications()

    def open_notification(self, notification_item):
        if not self.current_user:
            return
        self.selected_notification = notification_item
        notification_item["read"] = True
        save_notifications(notifications)
        self.update_notification_badge()

        target_post_id = notification_item.get("post_id", "")
        for post in posts:
            if post.get("id") == target_post_id:
                self.show_detail(post)
                self.hide_notification_panel()
                break
        self.render_notifications()

    def admin_suspend_user(self, target_user, duration_label, reason):
        if self.current_user != ADMIN_USERNAME:
            return False, "Chỉ Admin mới có quyền khóa tài khoản."
        if target_user == ADMIN_USERNAME:
            return False, "Không thể khóa tài khoản Admin."
        if target_user not in users:
            return False, "Không tìm thấy tài khoản."
        if duration_label not in SUSPEND_CHOICES:
            return False, "Thời hạn khóa không hợp lệ."

        user_data = users.get(target_user, {})
        if isinstance(user_data, str):
            user_data = {
                "password": user_data,
                "avatar": "",
                "suspended_until": "",
                "suspend_reason": "",
                "suspended_by": "",
                "suspended_at": "",
                "suspend_duration_label": "",
                "email": "",
            }
            users[target_user] = user_data
        else:
            user_data.setdefault("suspended_until", "")
            user_data.setdefault("suspend_reason", "")
            user_data.setdefault("suspended_by", "")
            user_data.setdefault("suspended_at", "")
            user_data.setdefault("suspend_duration_label", "")

        lock_reason = reason if reason else "Vi phạm quy định cộng đồng"
        lock_time = now_text()
        user_data["suspend_reason"] = lock_reason
        user_data["suspended_by"] = ADMIN_USERNAME
        user_data["suspended_at"] = lock_time
        user_data["suspend_duration_label"] = duration_label

        duration = SUSPEND_CHOICES[duration_label]
        if duration is None:
            user_data["suspended_until"] = "permanent"
            save_users(users)
            return True, f"Đã khóa {target_user} vĩnh viễn."

        until_dt = datetime.now() + duration
        user_data["suspended_until"] = until_dt.isoformat()
        save_users(users)
        return True, f"Đã khóa {target_user} đến {until_dt.strftime('%d/%m/%Y %H:%M')}."

    def admin_delete_post(self, post):
        if self.current_user != ADMIN_USERNAME:
            return False, "Chỉ Admin mới có quyền xóa bài viết."
        if post.get("author") == ADMIN_USERNAME:
            return False, "Chỉ xóa bài viết của tài khoản khác."
        if post not in posts:
            return False, "Không tìm thấy bài viết."

        posts.remove(post)
        save_posts(posts)
        return True, "Đã xóa bài viết không phù hợp."

    def get_group_by_id(self, group_id):
        for group in groups:
            if group.get("id") == group_id:
                return group
        return None

    def create_group(self, group_name):
        current_user = self.get_current_user()
        if not current_user:
            return False, "Bạn cần đăng nhập để tạo group."
        if not group_name:
            return False, "Tên group không được để trống."

        normalized_name = group_name.strip().lower()
        for group in groups:
            if group.get("name", "").strip().lower() == normalized_name:
                return False, "Tên group đã tồn tại."

        groups.insert(0, {
            "id": str(uuid.uuid4()),
            "name": group_name.strip(),
            "avatar": "",
            "owner": current_user,
            "deputies": [],
            "members": [current_user],
            "pending_members": [],
            "posts": [],
        })
        save_groups(groups)
        return True, "Tạo group thành công."

    def request_join_group(self, group_id):
        current_user = self.get_current_user()
        if not current_user:
            return False, "Bạn cần đăng nhập để xin vào group."

        group = self.get_group_by_id(group_id)
        if not group:
            return False, "Không tìm thấy group."
        if current_user in group.get("members", []):
            return False, "Bạn đã là thành viên của group này."
        if current_user in group.get("pending_members", []):
            return False, "Bạn đã gửi yêu cầu trước đó."

        group.setdefault("pending_members", []).append(current_user)
        save_groups(groups)
        return True, "Đã gửi yêu cầu tham gia group."

    def review_join_request(self, group_id, target_user, approved):
        current_user = self.get_current_user()
        group = self.get_group_by_id(group_id)
        if not current_user:
            return False, "Bạn cần đăng nhập."
        if not group:
            return False, "Không tìm thấy group."

        owner = group.get("owner")
        deputies = group.get("deputies", [])
        if current_user != owner and current_user not in deputies:
            return False, "Chỉ trưởng nhóm hoặc phó nhóm mới được duyệt thành viên."

        pending = group.setdefault("pending_members", [])
        if target_user not in pending:
            return False, "Không tìm thấy yêu cầu tham gia."

        pending.remove(target_user)
        if approved:
            group.setdefault("members", []).append(target_user)
            group["members"] = list(dict.fromkeys(group["members"]))
            save_groups(groups)
            return True, f"Đã duyệt {target_user} vào group."

        save_groups(groups)
        return True, f"Đã từ chối yêu cầu của {target_user}."

    def remove_group_member(self, group_id, target_user):
        current_user = self.get_current_user()
        group = self.get_group_by_id(group_id)
        if not current_user:
            return False, "Bạn cần đăng nhập."
        if not group:
            return False, "Không tìm thấy group."

        owner = group.get("owner")
        deputies = group.get("deputies", [])
        if current_user != owner and current_user not in deputies:
            return False, "Chỉ trưởng nhóm hoặc phó nhóm mới được xóa thành viên."
        if target_user == owner:
            return False, "Không thể xóa trưởng nhóm khỏi group."

        members = group.get("members", [])
        if target_user not in members:
            return False, "Người dùng không thuộc group."

        members.remove(target_user)
        if target_user in group.get("deputies", []):
            group["deputies"].remove(target_user)
        group.setdefault("pending_members", [])
        if target_user in group["pending_members"]:
            group["pending_members"].remove(target_user)

        save_groups(groups)
        return True, f"Đã xóa {target_user} khỏi group."

    def toggle_group_deputy(self, group_id, target_user):
        current_user = self.get_current_user()
        group = self.get_group_by_id(group_id)
        if not current_user:
            return False, "Bạn cần đăng nhập."
        if not group:
            return False, "Không tìm thấy group."
        if current_user != group.get("owner"):
            return False, "Chỉ trưởng nhóm mới được bổ nhiệm hoặc thu hồi phó nhóm."
        if target_user == group.get("owner"):
            return False, "Trưởng nhóm mặc định có quyền cao nhất."
        if target_user not in group.get("members", []):
            return False, "Người dùng phải là thành viên của group."

        deputies = group.setdefault("deputies", [])
        if target_user in deputies:
            deputies.remove(target_user)
            save_groups(groups)
            return True, f"Đã thu hồi quyền phó nhóm của {target_user}."

        deputies.append(target_user)
        group["deputies"] = list(dict.fromkeys(deputies))
        save_groups(groups)
        return True, f"Đã bổ nhiệm {target_user} làm phó nhóm."

    def transfer_group_owner(self, group_id, target_user):
        current_user = self.get_current_user()
        group = self.get_group_by_id(group_id)
        if not current_user:
            return False, "Bạn cần đăng nhập."
        if not group:
            return False, "Không tìm thấy group."
        if current_user != group.get("owner"):
            return False, "Chỉ trưởng nhóm hiện tại mới được nhường quyền."
        if target_user not in group.get("members", []):
            return False, "Người nhận quyền phải là thành viên trong group."
        if target_user == current_user:
            return False, "Bạn đang là trưởng nhóm rồi."

        old_owner = group.get("owner")
        group["owner"] = target_user

        deputies = group.setdefault("deputies", [])
        if target_user in deputies:
            deputies.remove(target_user)
        if old_owner not in deputies:
            deputies.append(old_owner)

        group["deputies"] = list(dict.fromkeys([u for u in deputies if u != group.get("owner")]))
        save_groups(groups)
        return True, f"Đã nhường trưởng nhóm cho {target_user}."

    def dissolve_group(self, group_id):
        current_user = self.get_current_user()
        group = self.get_group_by_id(group_id)
        if not current_user:
            return False, "Bạn cần đăng nhập."
        if not group:
            return False, "Không tìm thấy group."
        if current_user != group.get("owner"):
            return False, "Chỉ trưởng nhóm mới được giải tán nhóm."

        groups.remove(group)
        save_groups(groups)
        return True, "Đã giải tán nhóm."

    def leave_group(self, group_id):
        current_user = self.get_current_user()
        group = self.get_group_by_id(group_id)
        if not current_user:
            return False, "Bạn cần đăng nhập."
        if not group:
            return False, "Không tìm thấy group."

        if current_user == group.get("owner"):
            return False, "Trưởng nhóm không thể rời nhóm. Hãy chuyển quyền trước (chưa hỗ trợ)."

        members = group.get("members", [])
        if current_user not in members:
            return False, "Bạn chưa là thành viên group này."

        members.remove(current_user)
        if current_user in group.get("deputies", []):
            group["deputies"].remove(current_user)
        if current_user in group.get("pending_members", []):
            group["pending_members"].remove(current_user)

        save_groups(groups)
        return True, "Bạn đã rời group."

    def create_group_post(self, group_id, title, content):
        current_user = self.get_current_user()
        group = self.get_group_by_id(group_id)
        if not current_user:
            return False, "Bạn cần đăng nhập."
        if not group:
            return False, "Không tìm thấy group."
        if current_user not in group.get("members", []):
            return False, "Chỉ thành viên group mới được đăng bài."
        if not title or not content:
            return False, "Tiêu đề và nội dung không được để trống."

        new_group_post = {
            "id": generate_post_id(),
            "title": title,
            "content": content,
            "image": "",
            "date": now_text(),
            "author": current_user,
            "likes": [],
            "comments": [],
        }
        group.setdefault("posts", []).insert(0, new_group_post)

        for member in group.get("members", []):
            self.push_activity_notification(
                member,
                current_user,
                "group_post",
                f"{current_user} vừa đăng bài mới trong group '{group.get('name', '')}': {title}",
                new_group_post.get("id", ""),
            )

        save_groups(groups)
        save_notifications(notifications)
        self.update_notification_badge()
        self.render_notifications()
        return True, "Đã đăng bài vào group."

    def update_group_avatar(self, group_id, avatar_path):
        current_user = self.get_current_user()
        group = self.get_group_by_id(group_id)
        if not current_user:
            return False, "Bạn cần đăng nhập."
        if not group:
            return False, "Không tìm thấy group."
        if current_user != group.get("owner") and current_user not in group.get("deputies", []):
            return False, "Chỉ trưởng nhóm hoặc phó nhóm mới được cập nhật ảnh nhóm."
        group["avatar"] = avatar_path
        save_groups(groups)
        return True, "Cập nhật ảnh đại diện nhóm thành công."

    def edit_group_post(self, group_id, post_id, title, content):
        current_user = self.get_current_user()
        group = self.get_group_by_id(group_id)
        if not current_user:
            return False, "Bạn cần đăng nhập."
        if not group:
            return False, "Không tìm thấy group."
        if not title or not content:
            return False, "Tiêu đề và nội dung không được để trống."

        owner = group.get("owner")
        deputies = group.get("deputies", [])
        for post in group.get("posts", []):
            if post.get("id") != post_id:
                continue
            can_edit = post.get("author") == current_user or current_user == owner or current_user in deputies
            if not can_edit:
                return False, "Bạn không có quyền sửa bài viết này."
            post["title"] = title
            post["content"] = content
            save_groups(groups)
            return True, "Đã cập nhật bài viết trong group."
        return False, "Không tìm thấy bài viết trong group."

    def delete_group_post(self, group_id, post_id):
        current_user = self.get_current_user()
        group = self.get_group_by_id(group_id)
        if not current_user:
            return False, "Bạn cần đăng nhập."
        if not group:
            return False, "Không tìm thấy group."

        owner = group.get("owner")
        deputies = group.get("deputies", [])
        if current_user != owner and current_user not in deputies:
            return False, "Chỉ trưởng nhóm hoặc phó nhóm mới được xóa bài trong group."

        posts_in_group = group.get("posts", [])
        target_post = None
        for gp in posts_in_group:
            if gp.get("id") == post_id:
                target_post = gp
                break

        if not target_post:
            return False, "Không tìm thấy bài viết trong group."
        if current_user in deputies and target_post.get("author") == owner:
            return False, "Phó nhóm không thể xóa bài của trưởng nhóm."

        posts_in_group.remove(target_post)
        save_groups(groups)
        return True, "Đã xóa bài viết trong group."

    def show_home(self):
        self.clear_content()
        self.home = HomePage(
            self.show_detail,
            self.get_followers_count,
            self.get_user_avatar,
            self.show_profile,
            self.show_create,
            self.show_groups,
            self.show_inline_message,
            self.toggle_notification_panel,
            self.get_unread_notifications_count,
        )
        self.content_area.addWidget(self.home)

    def show_detail(self, post):
        self.clear_content()
        self.detail = DetailPage(post, self.show_home, self.get_current_user, self.save_all, self.get_followers_count, self.create_interaction_notification, self.get_user_avatar, self.show_inline_message)
        self.content_area.addWidget(self.detail)

    def show_create(self):
        self.clear_content()
        self.create_page = CreatePage(self.show_home, self.show_home, self.get_current_user, self.show_inline_message, self.notify_new_post_activity)
        self.content_area.addWidget(self.create_page)

    def show_group_post_detail(self, group_post):
        normalized_post = {
            "id": group_post.get("id", generate_post_id()),
            "title": group_post.get("title", ""),
            "content": group_post.get("content", ""),
            "date": group_post.get("date", now_text()),
            "author": group_post.get("author", "Ẩn danh"),
            "image": group_post.get("image", ""),
            "likes": group_post.get("likes", []),
            "comments": group_post.get("comments", []),
        }
        self.show_detail(normalized_post)

    def show_groups(self):
        self.clear_content()
        self.group_page = GroupPage(
            self.get_current_user,
            self.show_inline_message,
            self.create_group,
            self.request_join_group,
            self.review_join_request,
            self.remove_group_member,
            self.toggle_group_deputy,
            self.transfer_group_owner,
            self.dissolve_group,
            self.leave_group,
            self.create_group_post,
            self.delete_group_post,
            self.edit_group_post,
            self.update_group_avatar,
            self.show_group_post_detail,
            self.show_home,
        )
        self.content_area.addWidget(self.group_page)

    def show_profile(self):
        self.clear_content()
        self.profile_page = ProfilePage(
            self.get_current_user,
            self.login_user,
            self.register_user,
            self.logout_user,
            self.show_home,
            self.get_follow_stats,
            self.toggle_follow_user,
            self.get_user_avatar,
            self.set_user_avatar,
            self.show_inline_message,
            self.admin_suspend_user,
            self.admin_delete_post,
            self.show_home,
            self.change_password_user,
        )
        self.content_area.addWidget(self.profile_page)

    def clear_content(self):
        for i in reversed(range(self.content_area.count())):
            widget = self.content_area.itemAt(i).widget()
            if widget:
                widget.setParent(None)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = MainWindow()
    window.setStyleSheet("""
        QWidget {
            background: qlineargradient(
                spread:pad, x1:0, y1:0, x2:1, y2:1,
                stop:0 #4e73df,
                stop:1 #1cc88a
            );
        }
        QPushButton {
            border-radius: 12px;
            padding: 8px 14px;
            font-weight: bold;
        }
        QPushButton:hover {
            opacity: 0.92;
        }
        QLineEdit, QTextEdit {
            border-radius: 12px;
        }
    """)

    window.show()
    sys.exit(app.exec_())


from flask import Flask, request, jsonify
import sqlite3
import logging
import jwt
import datetime
from functools import wraps

app = Flask(__name__)

# Tắt logging của Flask để giảm nhiễu
log = logging.getLogger('werkzeug')
log.disabled = True

# Khóa bí mật cho JWT
SECRET_KEY = "your-secret-key"

# Khởi tạo cơ sở dữ liệu
def init_db():
    conn = sqlite3.connect('blog.db')
    cursor = conn.cursor()
    
    # Bảng users
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            email TEXT NOT NULL
        )
    ''')
    # Thêm người dùng mẫu
    users = [
        ('admin', 'admin123', 'admin@example.com'),
        ('user1', 'pass123', 'user1@example.com'),
        ('user2', 'secure456', 'user2@example.com')
    ]
    for user in users:
        cursor.execute("INSERT OR IGNORE INTO users (username, password, email) VALUES (?, ?, ?)", user)
    
    # Bảng posts
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    # Thêm bài viết mẫu
    posts = [
        (1, 'Admin Post', 'This is the admin\'s first post.', '2025-06-01'),
        (2, 'User1 Post', 'User1 shares some thoughts.', '2025-06-02'),
        (3, 'User2 Post', 'User2\'s blog entry.', '2025-06-03')
    ]
    for post in posts:
        cursor.execute("INSERT OR IGNORE INTO posts (user_id, title, content, created_at) VALUES (?, ?, ?, ?)", post)
    
    conn.commit()
    conn.close()

# Decorator xác thực JWT
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            try:
                token = request.headers['Authorization'].split("Bearer ")[1]
            except IndexError:
                return jsonify({'error': 'Invalid token format'}), 401

        if not token:
            return jsonify({'error': 'Authentication token is missing'}), 401

        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            current_user_id = data['user_id']
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

        return f(current_user_id, *args, **kwargs)
    return decorated

# Endpoint: Đăng ký người dùng
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    
    if not username or not password or not email:
        return jsonify({'error': 'Missing required fields'}), 400
    
    conn = sqlite3.connect('blog.db')
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)",
                      (username, password, email))
        conn.commit()
        return jsonify({'message': 'User registered successfully'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Username already exists'}), 400
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# Endpoint: Đăng nhập
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    conn = sqlite3.connect('blog.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        token = jwt.encode({
            'user_id': user[0],
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }, SECRET_KEY, algorithm="HS256")
        return jsonify({'message': 'Login successful', 'token': token, 'username': user[1]})
    return jsonify({'error': 'Invalid credentials'}), 401

# Endpoint: Xem profile cá nhân
@app.route('/users/me', methods=['GET'])
@token_required
def get_my_profile(current_user_id):
    conn = sqlite3.connect('blog.db')
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, username, email FROM users WHERE id = ?", (current_user_id,))
        user = cursor.fetchone()
        if user:
            return jsonify({'id': user[0], 'username': user[1], 'email': user[2]})
        return jsonify({'error': 'User not found'}), 404
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# Endpoint: Xem profile bất kỳ (BOLA)
@app.route('/users/<int:id>', methods=['GET'])
@token_required
def get_user_profile(current_user_id, id):
    conn = sqlite3.connect('blog.db')
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, username, email FROM users WHERE id = ?", (id,))
        user = cursor.fetchone()
        if user:
            return jsonify({'id': user[0], 'username': user[1], 'email': user[2]})
        return jsonify({'error': 'User not found'}), 404
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# Endpoint: Tạo bài viết
@app.route('/posts', methods=['POST'])
@token_required
def create_post(current_user_id):
    data = request.get_json()
    title = data.get('title')
    content = data.get('content')
    
    if not title or not content:
        return jsonify({'error': 'Missing required fields'}), 400
    
    created_at = datetime.datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect('blog.db')
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO posts (user_id, title, content, created_at) VALUES (?, ?, ?, ?)",
                      (current_user_id, title, content, created_at))
        conn.commit()
        return jsonify({'message': 'Post created successfully'}), 201
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# Endpoint: Sửa bài viết (BOLA)
@app.route('/posts/<int:id>', methods=['PUT'])
@token_required
def update_post(current_user_id, id):
    data = request.get_json()
    title = data.get('title')
    content = data.get('content')
    
    if not title or not content:
        return jsonify({'error': 'Missing required fields'}), 400
    
    conn = sqlite3.connect('blog.db')
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE posts SET title = ?, content = ? WHERE id = ?",
                      (title, content, id))
        if cursor.rowcount > 0:
            conn.commit()
            return jsonify({'message': 'Post updated successfully'})
        return jsonify({'error': 'Post not found'}), 404
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# Endpoint: Xóa bài viết (BOLA)
@app.route('/posts/<int:id>', methods=['DELETE'])
@token_required
def delete_post(current_user_id, id):
    conn = sqlite3.connect('blog.db')
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM posts WHERE id = ?", (id,))
        if cursor.rowcount > 0:
            conn.commit()
            return jsonify({'message': 'Post deleted successfully'})
        return jsonify({'error': 'Post not found'}), 404
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# Endpoint: Xem bài viết bất kỳ
@app.route('/posts/<int:id>', methods=['GET'])
def get_post(id):
    conn = sqlite3.connect('blog.db')
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, user_id, title, content, created_at FROM posts WHERE id = ?", (id,))
        post = cursor.fetchone()
        if post:
            return jsonify({
                'id': post[0],
                'user_id': post[1],
                'title': post[2],
                'content': post[3],
                'created_at': post[4]
            })
        return jsonify({'error': 'Post not found'}), 404
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)

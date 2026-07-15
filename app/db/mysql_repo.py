import json

from app.db.schema import (
    MYSQL_HISTORY_TABLE_SQL,
    MYSQL_USER_TABLE_SQL,
    SQLITE_HISTORY_TABLE_SQL,
    SQLITE_USER_TABLE_SQL,
)


def get_history_table_sql(is_sqlite: bool = False) -> str:
    return SQLITE_HISTORY_TABLE_SQL if is_sqlite else MYSQL_HISTORY_TABLE_SQL


def get_user_table_sql(is_sqlite: bool = False) -> str:
    return SQLITE_USER_TABLE_SQL if is_sqlite else MYSQL_USER_TABLE_SQL


class MySQLUserRepository:  # 定义MySQL用户仓储
    _columns = (
        "id",
        "username",
        "password_hash",
        "photo_path",
        "photo_mime_type",
        "face_analysis",
        "created_at",
        "updated_at",
    )

    def __init__(self, connection) -> None:  # 初始化仓储并注入数据库连接
        self.connection = connection  # 保存连接对象
        self._is_sqlite = connection.__class__.__module__.startswith("sqlite3")  # 判断是否为SQLite连接

    def _placeholder_sql(self, sql: str) -> str:  # 兼容不同数据库占位符
        return sql.replace("%s", "?") if self._is_sqlite else sql  # SQLite使用问号占位符

    def ensure_schema(self) -> None:  # 确保表结构存在
        cursor = self.connection.cursor()  # 获取游标对象
        cursor.execute(self._placeholder_sql(get_user_table_sql(self._is_sqlite)))  # 执行建表SQL
        self.connection.commit()  # 提交事务
        cursor.close()  # 关闭游标

    def _row_to_dict(self, row) -> dict | None:  # 将数据库行转为字典
        if row is None:  # 如果没有结果
            return None  # 直接返回空

        if isinstance(row, dict):
            data = row
        elif hasattr(row, "keys"):
            data = dict(row)
        else:
            data = dict(zip(self._columns, row))

        face_analysis = data.get("face_analysis")
        if isinstance(face_analysis, str):  # 如果 face_analysis 是JSON字符串
            try:
                data["face_analysis"] = json.loads(face_analysis)
            except Exception:
                pass
        return data  # 返回标准化结果

    def get_by_username(self, username: str) -> dict | None:  # 根据用户名查询用户
        cursor = self.connection.cursor()  # 获取游标
        cursor.execute(self._placeholder_sql("SELECT * FROM photo_style_users WHERE username = %s LIMIT 1"), (username,))  # 执行查询
        row = cursor.fetchone()  # 获取单条结果
        cursor.close()  # 关闭游标
        return self._row_to_dict(row)  # 返回结果

    def get_by_id(self, user_id: int) -> dict | None:  # 根据ID查询用户
        cursor = self.connection.cursor()  # 获取游标
        cursor.execute(self._placeholder_sql("SELECT * FROM photo_style_users WHERE id = %s LIMIT 1"), (user_id,))  # 执行查询
        row = cursor.fetchone()  # 获取单条结果
        cursor.close()  # 关闭游标
        return self._row_to_dict(row)  # 返回结果

    def create(self, username: str, password_hash: str) -> int:  # 创建用户
        cursor = self.connection.cursor()  # 获取游标对象
        cursor.execute(
            self._placeholder_sql("INSERT INTO photo_style_users (username, password_hash) VALUES (%s, %s)"),
            (username, password_hash),
        )
        self.connection.commit()  # 提交事务
        user_id = cursor.lastrowid  # 获取新增ID
        cursor.close()  # 关闭游标
        return user_id  # 返回ID

    def update_photo(self, username: str, photo_path: str, photo_mime_type: str | None = None, face_analysis: str | None = None) -> None:  # 更新用户照片信息
        cursor = self.connection.cursor()  # 获取游标对象
        cursor.execute(
            self._placeholder_sql("UPDATE photo_style_users SET photo_path = %s, photo_mime_type = %s, face_analysis = %s WHERE username = %s"),
            (photo_path, photo_mime_type, face_analysis, username),
        )
        self.connection.commit()  # 提交事务
        cursor.close()  # 关闭游标

    def update_profile(self, username: str, new_username: str | None = None, password_hash: str | None = None, photo_path: str | None = None, photo_mime_type: str | None = None, face_analysis: str | None = None) -> None:  # 更新用户资料
        fields = []
        params = []
        if new_username is not None:
            fields.append("username = %s")
            params.append(new_username)
        if password_hash is not None:
            fields.append("password_hash = %s")
            params.append(password_hash)
        if photo_path is not None:
            fields.append("photo_path = %s")
            params.append(photo_path)
        if photo_mime_type is not None:
            fields.append("photo_mime_type = %s")
            params.append(photo_mime_type)
        if face_analysis is not None:
            fields.append("face_analysis = %s")
            params.append(face_analysis)
        if not fields:
            return
        params.append(username)
        cursor = self.connection.cursor()
        cursor.execute(self._placeholder_sql(f"UPDATE photo_style_users SET {', '.join(fields)} WHERE username = %s"), tuple(params))
        self.connection.commit()
        cursor.close()

    def get_photo_payload(self, username: str) -> dict | None:  # 获取用户照片数据
        user = self.get_by_username(username)  # 查询用户
        if user is None:  # 如果不存在
            return None  # 返回空
        return {"photo_path": user.get("photo_path"), "photo_mime_type": user.get("photo_mime_type"), "face_analysis": user.get("face_analysis")}


class MySQLHistoryRepository:  # 定义MySQL历史记录仓储
    def __init__(self, connection) -> None:  # 初始化仓储并注入数据库连接
        self.connection = connection  # 保存连接对象
        self._is_sqlite = connection.__class__.__module__.startswith("sqlite3")  # 判断是否为SQLite连接

    def _placeholder_sql(self, sql: str) -> str:  # 兼容不同数据库占位符
        return sql.replace("%s", "?") if self._is_sqlite else sql  # SQLite使用问号占位符

    def ensure_schema(self) -> None:  # 确保表结构存在
        cursor = self.connection.cursor()  # 获取游标对象
        cursor.execute(self._placeholder_sql(get_history_table_sql(self._is_sqlite)))  # 执行建表SQL
        self.connection.commit()  # 提交事务
        cursor.close()  # 关闭游标

    def save(self, record: dict) -> None:  # 保存一条历史记录
        cursor = self.connection.cursor()  # 获取游标对象
        cursor.execute(  # 执行插入语句
            self._placeholder_sql(
                """
            INSERT INTO photo_style_history (user_id, input_data, output_data, liked, shot_success)
            VALUES (%s, %s, %s, %s, %s)
            """
            ),
            (
                record["user_id"],  # 用户ID
                record["input_data"],  # 输入数据
                record["output_data"],  # 输出数据
                int(record.get("liked", False)),  # 是否喜欢
                int(record.get("shot_success", False)),  # 是否出片成功
            ),
        )
        self.connection.commit()  # 提交事务
        cursor.close()  # 关闭游标

    def update_feedback(self, history_id: int, liked: bool, shot_success: bool) -> None:  # 更新历史记录的反馈
        cursor = self.connection.cursor()  # 获取游标对象
        cursor.execute(  # 执行更新语句
            self._placeholder_sql("UPDATE photo_style_history SET liked = %s, shot_success = %s WHERE id = %s"),
            (int(liked), int(shot_success), history_id),
        )
        self.connection.commit()  # 提交事务
        cursor.close()  # 关闭游标

    def list(self) -> list:  # 查询全部历史记录
        cursor = self.connection.cursor()  # 获取游标对象
        cursor.execute(  # 执行查询语句
            self._placeholder_sql("SELECT id, user_id, input_data, output_data, liked, shot_success, created_at FROM photo_style_history ORDER BY id DESC")
        )
        rows = cursor.fetchall()  # 获取结果集
        cursor.close()  # 关闭游标
        return rows  # 返回查询结果

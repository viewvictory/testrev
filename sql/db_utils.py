import mysql.connector
from db_config import DB_CONFIG

class DBUtils:
    @staticmethod
    def get_connection():
        """获取数据库连接"""
        try:
            connection = mysql.connector.connect(
                host=DB_CONFIG['host'],
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                database=DB_CONFIG['database'],
                charset=DB_CONFIG['charset']
            )
            return connection
        except mysql.connector.Error as e:
            print(f"数据库连接失败: {str(e)}")
            raise

    @staticmethod
    def execute_query(sql, params=None):
        """执行查询操作"""
        connection = None
        try:
            connection = DBUtils.get_connection()
            cursor = connection.cursor(dictionary=True)  # 使用字典游标
            
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            
            result = cursor.fetchall()
            return result
            
        except mysql.connector.Error as e:
            print(f"查询执行失败: {str(e)}")
            print(f"SQL: {sql}")
            if params:
                print(f"参数: {params}")
            return None
            
        finally:
            if connection:
                connection.close()

    @staticmethod
    def execute_update(sql, params=None):
        """执行更新操作"""
        connection = None
        cursor = None
        try:
            connection = DBUtils.get_connection()
            cursor = connection.cursor()
            
            if params:
                print("\n=== 执行更新操作 ===")
                print(f"SQL: {sql}")
                print(f"参数: {params}")
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            
            affected_rows = cursor.rowcount
            connection.commit()
            print(f"更新成功，影响行数: {affected_rows}")
            return True
            
        except mysql.connector.Error as e:
            if connection:
                connection.rollback()
            error_msg = str(e)
            print("\n=== 数据库更新错误 ===")
            print(f"错误信息: {error_msg}")
            print(f"SQL: {sql}")
            if params:
                print(f"参数: {params}")
            
            if "Duplicate entry" in error_msg:
                print("错误类型: 主键冲突")
            elif "foreign key constraint fails" in error_msg:
                print("错误类型: 外键约束失败")
            elif "Data too long" in error_msg:
                print("错误类型: 数据超出字段长度限制")
            
            return False
            
        except Exception as e:
            print(f"\n=== 非数据库错误 ===")
            print(f"错误类型: {type(e)}")
            print(f"错误信息: {str(e)}")
            return False
            
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
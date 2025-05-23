from db_utils import DBUtils
import os

def show_database_structure():
    """显示数据库表结构"""
    print("\n=== 数据库结构信息 ===")
    
    # 获取所有表名
    tables_sql = "SHOW TABLES"
    tables = DBUtils.execute_query(tables_sql)
    
    if not tables:
        print("数据库中没有表！")
        return
    
    # 遍历每个表
    for table in tables:
        table_name = list(table.values())[0]
        print(f"\n表名: {table_name}")
        print("-" * 50)
        
        # 获取表结构
        structure_sql = f"SHOW FULL COLUMNS FROM {table_name}"
        columns = DBUtils.execute_query(structure_sql)
        
        if columns:
            print(f"{'字段名':<20}{'类型':<15}{'是否为空':<10}{'键':<10}{'默认值':<15}{'备注'}")
            print("-" * 80)
            for column in columns:
                print(f"{column['Field']:<20}{column['Type']:<15}{column['Null']:<10}"
                      f"{column['Key']:<10}{str(column['Default']):<15}{column['Comment']}")
        
        # 获取表的索引信息
        index_sql = f"SHOW INDEX FROM {table_name}"
        indexes = DBUtils.execute_query(index_sql)
        
        if indexes:
            print("\n索引信息:")
            print(f"{'索引名':<20}{'列名':<20}{'是否唯一'}")
            print("-" * 50)
            for index in indexes:
                is_unique = "是" if index['Non_unique'] == 0 else "否"
                print(f"{index['Key_name']:<20}{index['Column_name']:<20}{is_unique}")


# 清空终端输出
os.system('cls' if os.name == 'nt' else 'clear')


if __name__ == "__main__":
    print("开始测试数据库连接...")
    connection = DBUtils.get_connection()
    if connection:
        print("数据库连接成功！")
        connection.close()
        show_database_structure()
    else:
        print("数据库连接失败！")
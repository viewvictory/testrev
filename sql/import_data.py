import json
from db_utils import DBUtils

def parse_js_array():
    """解析 left.js 文件中的数组数据"""
    with open('left.js', 'r', encoding='utf-8') as file:
        content = file.read()
        # 提取数组内容
        content = content.replace('var arrArea = new Array();', '')
        content = content.replace('arrArea[', '[')
        # 将 JavaScript 数组转换为 Python 列表
        areas = eval(content)
    return areas

def import_areas(areas):
    """导入区域数据"""
    print("开始导入区域数据...")
    
    for group_id, group_data in enumerate(areas):
        if not group_data:
            continue
            
        for area in group_data:
            # 插入洲际级别区域
            area_sql = """
                INSERT INTO area (area_id, name_zh, name_zht, name_en, level, parent_id, sort_order)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            area_data = (
                group_id,  # area_id
                area[0],   # name_zh
                area[1],   # name_zht
                area[2],   # name_en
                area[3],   # level
                None,      # parent_id
                0         # sort_order
            )
            
            if DBUtils.execute_update(area_sql, area_data):
                print(f"成功导入区域: {area[0]}")
                
                # 获取插入的区域ID
                parent_id_sql = "SELECT id FROM area WHERE area_id = %s"
                result = DBUtils.execute_query(parent_id_sql, (group_id,))
                if result:
                    parent_id = result[0]['id']
                    
                    # 处理联赛数据
                    if area[4]:  # 联赛数组
                        for league in area[4]:
                            competition_sql = """
                                INSERT INTO competition (
                                    competition_id, name_zh, name_zht, name_en,
                                    area_id, competition_type, level, original_group_id
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """
                            competition_data = (
                                league[0],  # competition_id
                                league[1],  # name_zh
                                league[2],  # name_zht
                                league[3],  # name_en
                                parent_id,  # area_id
                                league[4],  # competition_type
                                2,         # level
                                group_id   # original_group_id
                            )
                            if DBUtils.execute_update(competition_sql, competition_data):
                                print(f"  成功导入联赛: {league[1]}")
                    
                    # 处理杯赛数据
                    if area[5]:  # 杯赛数组
                        for cup in area[5]:
                            competition_sql = """
                                INSERT INTO competition (
                                    competition_id, name_zh, name_zht, name_en,
                                    area_id, competition_type, level, original_group_id
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """
                            competition_data = (
                                cup[0],    # competition_id
                                cup[1],    # name_zh
                                cup[2],    # name_zht
                                cup[3],    # name_en
                                parent_id, # area_id
                                cup[4],    # competition_type
                                2,        # level
                                group_id  # original_group_id
                            )
                            if DBUtils.execute_update(competition_sql, competition_data):
                                print(f"  成功导入杯赛: {cup[1]}")

def main():
    try:
        print("开始数据导入...")
        areas = parse_js_array()
        import_areas(areas)
        print("数据导入完成！")
    except Exception as e:
        print(f"导入过程中出错: {str(e)}")

if __name__ == "__main__":
    main()
import pandas as pd
import requests
import re
import json
import os
import sys
import time
import random
from datetime import datetime

# 导入全局配置
sys.path.append(os.path.dirname(__file__))
from Global_cfg import SOURCE_URL

# 数据库相关的导入
sys.path.append(os.path.join(os.path.dirname(__file__), 'sql'))
from db_utils import DBUtils

class LeagueSeasonFetcher:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.output_dir = os.path.join(os.path.dirname(__file__), 'LocalOutputFiles')
        self.output_file = os.path.join(self.output_dir, 'league_seasons.xlsx')

    def get_events_by_level(self):
        """按区域级别获取赛事数据"""
        events_by_level = {}
        
        # 先分别检查两个表的数据
        check_tables_sql = """
            SELECT 
                (SELECT COUNT(*) FROM events) as events_count,
                (SELECT COUNT(*) FROM areas) as areas_count
        """
        tables_count = DBUtils.execute_query(check_tables_sql)
        print("\n=== 表数据检查 ===")
        print(f"events表记录数: {tables_count[0]['events_count']}")
        print(f"areas表记录数: {tables_count[0]['areas_count']}")
        
        # 检查JOIN条件
        check_join_sql = """
            SELECT e.levelid, a.level, COUNT(*) as match_count
            FROM events e
            JOIN areas a ON e.levelid = a.level
            GROUP BY e.levelid, a.level
            ORDER BY e.levelid
        """
        join_result = DBUtils.execute_query(check_join_sql)
        print("\n=== JOIN条件检查 ===")
        for row in join_result:
            print(f"levelid: {row['levelid']}, level: {row['level']}, 匹配数: {row['match_count']}")
        
        # 修改分级别查询
        for level in range(6):
            sql = """
                SELECT e.event_id, e.name_zh, e.type_code, e.access_url, a.name_zh as area_name
                FROM events e
                JOIN areas a ON e.levelid = a.level
                WHERE e.levelid = %s
                ORDER BY e.event_id
            """
            events = DBUtils.execute_query(sql, (level,))
            if events:
                events_by_level[level] = events
            
        return events_by_level

    def generate_season_url(self, event_id):
        """生成赛季数据URL"""
        return f"{SOURCE_URL}jsData/LeagueSeason/sea{event_id}.js"

    def verify_url(self, url):
        """验证URL是否可访问"""
        try:
            time.sleep(random.uniform(0.5, 1))
            response = requests.get(url, headers=self.headers, timeout=10)
            
            print(f"\n验证URL: {url}")
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                content = response.text
                print(f"页面内容长度: {len(content)}")
                
                if '<title>404</title>' in content or 'error404' in content:
                    print("页面包含404标记")
                    return False, None
                
                # 检查是否包含赛季数据
                if 'var arrSeason' in content and '[' in content and ']' in content:
                    return True, content
                else:
                    print("页面不包含赛季数据")
                    return False, None
                    
            return False, None
        except Exception as e:
            print(f"验证URL失败: {str(e)}")
            return False, None

    def extract_seasons(self, js_content):
        """提取赛季数据"""
        pattern = r'var\s+arrSeason\s*=\s*(\[.*?\]);'
        match = re.search(pattern, js_content, re.DOTALL)
        if match:
            seasons_str = match.group(1).replace("'", '"')
            try:
                seasons = json.loads(seasons_str)
                processed_seasons = []
                
                for season in seasons:
                    if '-' in season:
                        # 处理格式1：'2024-2025'
                        start_year, end_year = season.split('-')
                        processed_seasons.append({
                            'start_year': start_year,
                            'end_year': end_year
                        })
                    else:
                        # 处理格式2：'2025'
                        processed_seasons.append({
                            'start_year': season,
                            'end_year': season
                        })
                
                return processed_seasons
            except json.JSONDecodeError as e:
                print(f"解析赛季数据失败: {e}")
        return None

    def process_events(self):
        """处理所有赛事数据"""
        events_by_level = self.get_events_by_level()
        all_data = []
        invalid_urls = []
        total_urls = 0
        valid_urls = 0

        for level, events in events_by_level.items():
            print(f"\n处理区域级别 {level} 的赛事...")
            level_data = []
            
            for event in events:
                total_urls += 1
                season_url = self.generate_season_url(event['event_id'])
                is_valid, content = self.verify_url(season_url)
                
                if is_valid:
                    valid_urls += 1
                    seasons = self.extract_seasons(content)
                else:
                    seasons = None
                    invalid_urls.append({
                        '区域': event['area_name'],
                        '赛事': event['name_zh'],
                        'URL': season_url
                    })

                level_data.append({
                    '赛事ID': event['event_id'],
                    '赛事名称': event['name_zh'],
                    '类型编码': event['type_code'],
                    '访问链接': event['access_url'],
                    '赛季数据链接': season_url,
                    '赛季数据': json.dumps(seasons, ensure_ascii=False) if seasons else '无数据'
                })
            
            if level_data:
                all_data.append((events[0]['area_name'], level_data))

        # 打印统计信息
        self.print_statistics(total_urls, valid_urls, invalid_urls)
        
        # 导出数据
        self.export_to_excel(all_data)

    def print_statistics(self, total_urls, valid_urls, invalid_urls):
        """打印URL统计信息"""
        print("\n=== URL统计信息 ===")
        print(f"总URL数量: {total_urls}")
        print(f"有效URL数量: {valid_urls}")
        print(f"无效URL数量: {len(invalid_urls)}")
        
        if invalid_urls:
            print("\n无效URL明细:")
            for item in invalid_urls:
                print(f"\n区域: {item['区域']}")
                print(f"赛事: {item['赛事']}")
                print(f"URL: {item['URL']}")

    def export_to_excel(self, data_list):
        """导出数据到Excel"""
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            
            with pd.ExcelWriter(self.output_file, engine='openpyxl') as writer:
                for area_name, events_data in data_list:
                    if events_data:
                        df = pd.DataFrame(events_data)
                        df.to_excel(writer, sheet_name=area_name, index=False)
            
            print(f"\nExcel文件已保存到: {self.output_file}")
            return True
        except Exception as e:
            print(f"导出Excel失败: {str(e)}")
            return False

def main():
    fetcher = LeagueSeasonFetcher()
    fetcher.process_events()

if __name__ == '__main__':
    main()
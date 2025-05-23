''' 1. 获取所有区域ID和赛事ID
    - 包括：区域名称、区域级别、赛事名称（简繁英）、赛事ID、赛事类型、类型编码。
    - 生成了以[编码类型]+[赛事ID]的HTTP访问链接，并验证URL有效性。 
    - 输出：原始JS、EXCEL、存储数据库表 'areas'、'events'
'''
import pandas as pd
import json
import requests
from requests.exceptions import RequestException
import os
import sys
import time
import random
    # 在文件开头添加必要的导入
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor


# 导入全局配置
sys.path.append(os.path.dirname(__file__))
from Global_cfg import AREAS_URL,SOURCE_URL

# 数据库相关的导入
sys.path.append(os.path.join(os.path.dirname(__file__), 'sql'))
from db_utils import DBUtils

# 数据源配置
class Config:
    """配置类，集中管理所有配置项
    属性说明：
        AREAS_URL = 全局AREAS_URL
        BASE_URL: 基础URL，用于构建具体赛事的访问链接
        OUTPUT_DIR: Excel输出目录
        EVENTS_EXCEL: Excel文件完整路径
        EVENT_TYPE_MAPPING: URL路径映射配置
            - 杯赛统一使用 CupMatch
            - 联赛根据type_code使用不同路径：
                2 = CupMatch（杯赛）
                1 = League（一级联赛）
                0 = SubLeague（次级联赛）
    """
    # URL配置
    # 数据格式：[赛事ID, 赛事名称, 赛事繁体名, 赛事英文名, 赛事类型]
    AREAS_URL = AREAS_URL  # 使用全局配置的AREAS_URL
    BASE_URL = SOURCE_URL + 'cn'  # 使用全局配置的SOURCE_URL

    # 添加 JS 文件保存目录配置
    JS_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'QtLocal_SourceJS', 'leftData')
    
    # 输出EXCEL文件配置
    EXCEL_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'LocalOutputFiles')
    EXCEL_EVENTS_EXCEL = os.path.join(EXCEL_OUTPUT_DIR, 'football_areas_events_all.xlsx')
    
    # 修改赛事类型URL映射，根据类型编码确定URL路径
    EVENT_TYPE_MAPPING = {
        '杯赛': 'CupMatch',    # type_code 为 2 时使用 CupMatch
        '联赛': {
            1: 'League',       # type_code 为 1 时使用 League
            0: 'SubLeague'     # type_code 为 0 时使用 SubLeague
        }
    }
# 清空终端输出
os.system('cls' if os.name == 'nt' else 'clear')


class DataFetcher:
    # 添加类变量用于URL缓存
    _url_cache = {}  # 格式: {url: {'valid': bool, 'timestamp': float}}
    _cache_timeout = 3600  # 缓存有效期(秒)，默认1小时

    @staticmethod
    def check_db_has_data():
        """检查数据库中是否已有数据"""
        try:
            # 检查 areas 和 events 表是否都有数据
            areas_count = DBUtils.execute_query("SELECT COUNT(*) as count FROM areas")
            events_count = DBUtils.execute_query("SELECT COUNT(*) as count FROM events")
            
            has_areas = areas_count and areas_count[0]['count'] > 0
            has_events = events_count and events_count[0]['count'] > 0
            
            return has_areas and has_events
        except Exception as e:
            print(f"检查数据库数据失败: {str(e)}")
            return False

    @staticmethod
    def check_files_exist():
        """检查必要的本地文件是否存在"""
        js_file = os.path.join(Config.JS_OUTPUT_DIR, 'leftData.js')
        js_exists = os.path.exists(js_file)
        excel_exists = os.path.exists(Config.EXCEL_EVENTS_EXCEL)
        return js_exists, excel_exists

    @staticmethod
    def compare_js_content(new_content, old_content):
        """比较新旧JS内容是否一致"""
        # 移除空白字符和换行符后比较
        new_content = ''.join(new_content.split())
        old_content = ''.join(old_content.split())
        return new_content == old_content
        
    @staticmethod
    def get_area_names(all_arrays):
        """从获取的数据中提取区域名称列表
        Args:
            all_arrays: 从URL获取的原始数据数组
        Returns:
            list: 包含所有区域信息的列表，每个元素为 [简体名, 繁体名, 英文名, 级别]
        """
        area_names = []
        for i, array in enumerate(all_arrays):
            if array and len(array) > 0:
                # 每个array的第一个元素包含区域信息
                area = array[0]
                if len(area) >= 4:  # 确保包含简体、繁体、英文名和级别
                    area_names.append([
                        area[0],    # name_zh
                        area[1],    # name_zht
                        area[2],    # name_en
                        area[3]     # level
                    ])
                else:
                    print(f"警告: 区域数据格式不正确 - {area}")
        
        if not area_names:
            raise Exception("未能获取有效的区域数据")
            
        return area_names

    @staticmethod
    def get_js_content(url):
        """从URL获取JavaScript内容"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        try:
            print(f"\n请求URL: {url}")  # 打印完整的URL请求
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # 如果状态码不是200，抛出异常
            # 检查请求状态码并提供详细信息
            if response.status_code == 200:
                print(f"请求成功 - 状态码: {response.status_code}")
            else:
                print(f"请求异常 - 状态码: {response.status_code}")
                print(f"响应内容: {response.text[:200]}...")  # 打印部分响应内容        
            
            # 确保响应的编码方式正确
            response.encoding = response.apparent_encoding
            return response.text
        except RequestException as e:
            print(f"获取数据失败: {str(e)}")
            raise

    @staticmethod
    def load_area_data(js_content):
        """从JavaScript内容中提取数据"""
        arrays = []
        for i in range(6):
            start = js_content.find(f'arrArea[{i}] = ')
            if start != -1:
                data_start = js_content.find('[', start)
                data_end = js_content.find('];', data_start)
                if data_start != -1 and data_end != -1:
                    array_data = js_content[data_start:data_end + 1]
                    array_data = (array_data
                                .replace('\'', '"')
                                .replace('\n', '')
                                .replace('\r', '')
                                .replace('\t', '')
                                .replace(' ', '')
                                .replace(',]', ']')
                                .replace(',,', ',')
                                .replace(f'[{i}]=', '')
                                )
                    try:
                        array = eval(array_data)
                        arrays.append(array)
                    except Exception as e:
                        print(f"解析错误: {str(e)}")
                        arrays.append([])
        return arrays

    @staticmethod
    def extract_area_data(area_data):
        """解析区域数据为结构化格式"""
        areas = []
        for area in area_data:
            area_info = {
                'area': {
                    'name_zh': area[0],          
                    'name_zht': area[1],         
                    'name_en': area[2],
                    'level': area[3]
                },
                'leagues': [
                    {
                        'id': league[0],
                        'name_zh': league[1],    
                        'name_zht': league[2],   
                        'name_en': league[3],
                        'type': league[4]
                    } for league in area[4]
                ] if area[4] else [],
                'cups': [
                    {
                        'id': cup[0],
                        'name_zh': cup[1],       
                        'name_zht': cup[2],      
                        'name_en': cup[3],
                        'type': cup[4]
                    } for cup in area[5]
                ] if area[5] else []
            }
            areas.append(area_info)
        return areas

    @staticmethod
    def generate_event_url(event_type, event_id, type_code):
        """根据赛事类型和ID生成访问链接
        Args:
            event_type: 赛事类型（'杯赛' 或 '联赛'）
            event_id: 赛事ID
            type_code: 类型编码
        Returns:
            str: 完整的访问链接
        """
        if event_type == '杯赛':
            url_path = Config.EVENT_TYPE_MAPPING['杯赛']
        elif event_type == '联赛':
            # type_code 为 0 表示顶级联赛，1 表示次级联赛
            url_path = Config.EVENT_TYPE_MAPPING['联赛'].get(type_code, 'League')
        else:
            raise ValueError(f"未知的赛事类型: {event_type}")
        
        return f"{Config.BASE_URL}/{url_path}/{event_id}.html"

    @staticmethod
    def print_url_statistics(events_data, invalid_urls):
        """打印URL验证统计信息"""
        total_urls = len(events_data)
        valid_urls = sum(1 for event in events_data if event['URL有效'])
        invalid_count = len(invalid_urls)
        
        print("\nURL验证统计:")
        print(f"总URL数量: {total_urls}")
        print(f"有效URL数量: {valid_urls}")
        print(f"无效URL数量: {total_urls - valid_urls}")
        
        if invalid_urls:
            print("\n无效URL列表:")
            for url_info in invalid_urls:
                print(f"区域: {url_info['区域']}")
                print(f"赛事: {url_info['赛事']}")
                print(f"URL: {url_info['URL']}")
                print("---")

    # 添加类变量用于URL缓存
    _url_cache = {}  # 格式: {url: {'valid': bool, 'timestamp': float}}
    _cache_timeout = 3600  # 缓存有效期(秒)，默认1小时

    @staticmethod
    def verify_url(url):
        """验证单个URL是否可访问"""
        # 检查URL缓存
        now = time.time()
        if url in DataFetcher._url_cache:
            cache_data = DataFetcher._url_cache[url]
            # 如果缓存未过期,直接返回缓存的结果
            if now - cache_data['timestamp'] < DataFetcher._cache_timeout:
                return cache_data['valid']

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            print(f"\n验证URL: {url}")
            print(f"状态码: {response.status_code}")
            
            is_valid = False
            if response.status_code == 200:
                content = response.text
                print(f"页面内容长度: {len(content)}")
                
                if '<title>404</title>' in content or 'error404' in content:
                    print("页面包含404标记")
                else:
                    is_valid = len(content) > 1000
            
            # 更新缓存
            DataFetcher._url_cache[url] = {
                'valid': is_valid,
                'timestamp': now
            }
            
            return is_valid
        except Exception as e:
            print(f"验证URL失败 {url}: {str(e)}")
            # 缓存失败结果
            DataFetcher._url_cache[url] = {
                'valid': False,
                'timestamp': now
            }
            return False

    @staticmethod
    async def verify_url_async(url, session):
        """异步验证URL是否可访问"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            async with session.get(url, headers=headers, timeout=10) as response:
                print(f"\n验证URL: {url}")
                print(f"状态码: {response.status}")
                
                is_valid = False
                if response.status == 200:
                    content = await response.text()
                    print(f"页面内容长度: {len(content)}")
                    
                    if '<title>404</title>' in content or 'error404' in content:
                        print("页面包含404标记")
                    else:
                        is_valid = len(content) > 1000
                
                return url, is_valid
        except Exception as e:
            print(f"验证URL失败 {url}: {str(e)}")
            return url, False

    @staticmethod
    async def verify_urls_batch(urls):
        """批量验证多个URL"""
        async with aiohttp.ClientSession() as session:
            tasks = []
            for url in urls:
                # 添加随机延迟以避免请求过于密集
                await asyncio.sleep(random.uniform(0.1, 0.3))
                tasks.append(asyncio.ensure_future(
                    DataFetcher.verify_url_async(url, session)
                ))
            results = await asyncio.gather(*tasks)
            return dict(results)

    @staticmethod
    def verify_urls(urls):
        """并发验证多个URL的入口方法"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(DataFetcher.verify_urls_batch(urls))
            return results
        finally:
            loop.close()

    @staticmethod
    def get_events_data(area_data):
        """从区域数据中提取赛事数据
        Returns:
            tuple: (events_data, invalid_urls)
        """
        events_data = []
        invalid_urls = []
        
        for area in area_data:
            area_name = area['area']['name_zh']      
            area_level = area['area']['level']
            
            # 处理联赛数据
            for league in area['leagues']:
                event_url = DataFetcher.generate_event_url('联赛', league['id'], league['type'])
                url_valid = DataFetcher.verify_url(event_url)
                
                if not url_valid:
                    invalid_urls.append({
                        '区域': area_name,
                        '赛事': league['name_zh'],
                        'URL': event_url
                    })
                    alternate_type = 1 if league['type'] == 0 else 0
                    event_url = DataFetcher.generate_event_url('联赛', league['id'], alternate_type)
                    url_valid = DataFetcher.verify_url(event_url)
                
                events_data.append({
                    '区域': area_name,
                    '区域级别': area_level,
                    '赛事ID': league['id'],
                    '赛事简休名': league['name_zh'],    
                    '赛事繁体名': league['name_zht'],   
                    '赛事英文名': league['name_en'],
                    '赛事类型': '联赛',
                    '类型编码': league['type'],
                    '访问链接': event_url,
                    'URL有效': url_valid
                })
            
            # 处理杯赛数据
            for cup in area['cups']:
                event_url = DataFetcher.generate_event_url('杯赛', cup['id'], cup['type'])
                url_valid = DataFetcher.verify_url(event_url)
                
                if not url_valid:
                    invalid_urls.append({
                        '区域': area_name,
                        '赛事': cup['name_zh'],
                        'URL': event_url
                    })
                
                events_data.append({
                    '区域': area_name,
                    '区域级别': area_level,
                    '赛事ID': cup['id'],
                    '赛事简休名': cup['name_zh'],       
                    '赛事繁体名': cup['name_zht'],      
                    '赛事英文名': cup['name_en'],
                    '赛事类型': '杯赛',
                    '类型编码': cup['type'],
                    '访问链接': event_url,
                    'URL有效': url_valid
                })
        
        # 打印统计信息
        DataFetcher.print_url_statistics(events_data, invalid_urls)
        return events_data

class ExcelExporter:
    """Excel导出类，负责数据导出到Excel文件"""
    @staticmethod
    def export_to_excel(data_list, output_file):
        """将数据导出到Excel文件，每个区域一个sheet"""
        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            # 创建ExcelWriter对象
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                for area_name, events_data in data_list:
                    if events_data:
                        df = pd.DataFrame(events_data)
                        df.to_excel(writer, sheet_name=area_name, index=False)
            
            print(f"Excel文件已保存到: {output_file}")
            return True
        except Exception as e:
            print(f"导出Excel失败: {str(e)}")
            return False

class DBManager:
    """数据库管理类，负责数据持久化"""
    @staticmethod
    def compare_area_data(new_areas, existing_areas):
        """比较区域数据的变化"""
        changes = []
        stats = {'updated': 0, 'added': 0, 'total': len(new_areas)}
        
        for new_area in new_areas:
            matching_area = next(
                (area for area in existing_areas 
                 if area['level'] == new_area[3]),
                None
            )
            if matching_area:
                # 检查每个字段的变化
                field_changes = []
                if matching_area['name_zh'] != new_area[0]:
                    field_changes.append({
                        'field': 'name_zh',
                        'old': matching_area['name_zh'],
                        'new': new_area[0]
                    })
                if matching_area['name_zht'] != new_area[1]:
                    field_changes.append({
                        'field': 'name_zht',
                        'old': matching_area['name_zht'],
                        'new': new_area[1]
                    })
                if matching_area['name_en'] != new_area[2]:
                    field_changes.append({
                        'field': 'name_en',
                        'old': matching_area['name_en'],
                        'new': new_area[2]
                    })
                
                if field_changes:
                    changes.append({
                        'level': new_area[3],
                        'type': 'update',
                        'changes': field_changes
                    })
                    stats['updated'] += 1
            else:
                changes.append({
                    'level': new_area[3],
                    'type': 'add',
                    'data': {
                        'name_zh': new_area[0],
                        'name_zht': new_area[1],
                        'name_en': new_area[2]
                    }
                })
                stats['added'] += 1
        
        if changes:
            print("\n区域数据变化统计:")
            print(f"总数据量: {stats['total']}")
            print(f"更新数量: {stats['updated']}")
            print(f"新增数量: {stats['added']}")
            
            print("\n变化明细:")
            for change in changes:
                if change['type'] == 'update':
                    print(f"\n级别 {change['level']} 的数据更新:")
                    for field_change in change['changes']:
                        print(f"  字段 {field_change['field']}:")
                        print(f"    原值: {field_change['old']}")
                        print(f"    新值: {field_change['new']}")
                else:
                    print(f"\n级别 {change['level']} 新增数据:")
                    for field, value in change['data'].items():
                        print(f"  {field}: {value}")
            return True
        return False

    @staticmethod
    def compare_events_data(new_events, existing_events):
        """比较赛事数据的变化"""
        changes = []
        stats = {'updated': 0, 'added': 0, 'total': len(new_events)}
        
        # 处理现有数据为空的情况
        if not existing_events:
            print("数据库中无现有数据，所有数据将作为新增处理")
            for new_event in new_events:
                changes.append({
                    'event_id': new_event['赛事ID'],
                    'type': 'add',
                    'data': new_event
                })
                stats['added'] += 1
            
            # 打印统计信息并返回
            DBManager._print_event_changes(changes, stats)
            return True
            
        # 将现有数据转换为字典格式，方便查找
        existing_dict = {
            str(event['event_id']): event 
            for event in existing_events
        }
        
        for new_event in new_events:
            event_id = str(new_event['赛事ID'])
            if event_id in existing_dict:
                field_changes = []
                matching_event = existing_dict[event_id]
                
                # 检查每个字段的变化
                field_mappings = {
                    'name_zh': '赛事简休名',
                    'name_zht': '赛事繁体名',
                    'name_en': '赛事英文名',
                    'event_type': '赛事类型',
                    'type_code': '类型编码',
                    'access_url': '访问链接',
                    'url_status': 'URL有效'
                }
                
                for db_field, new_field in field_mappings.items():
                    old_value = matching_event[db_field]
                    new_value = new_event[new_field]
                    if db_field == 'url_status':
                        new_value = 1 if new_value else 0
                    
                    if str(old_value) != str(new_value):
                        field_changes.append({
                            'field': db_field,
                            'old': old_value,
                            'new': new_value
                        })
                
                if field_changes:
                    changes.append({
                        'event_id': event_id,
                        'type': 'update',
                        'changes': field_changes
                    })
                    stats['updated'] += 1
            else:
                changes.append({
                    'event_id': event_id,
                    'type': 'add',
                    'data': new_event
                })
                stats['added'] += 1
        
        # 打印统计信息并返回
        DBManager._print_event_changes(changes, stats)
        return bool(changes)

    @staticmethod
    def _print_event_changes(changes, stats):
        """打印赛事数据变化统计信息"""
        if changes:
            print("\n赛事数据变化统计:")
            print(f"总数据量: {stats['total']}")
            print(f"更新数量: {stats['updated']}")
            print(f"新增数量: {stats['added']}")
            
            print("\n变化明细:")
            for change in changes:
                if change['type'] == 'update':
                    print(f"\n赛事ID {change['event_id']} 的数据更新:")
                    for field_change in change['changes']:
                        print(f"  字段 {field_change['field']}:")
                        print(f"    原值: {field_change['old']}")
                        print(f"    新值: {field_change['new']}")
                else:
                    print(f"\n新增赛事ID {change['event_id']}:")
                    for field, value in change['data'].items():
                        print(f"  {field}: {value}")
            return True
        return False

    @staticmethod
    def save_areas_to_db(area_names):
        """保存区域数据到数据库"""
        try:
            # 先获取现有数据
            existing_data = DBUtils.execute_query(
                "SELECT name_zh, name_zht, name_en, level FROM areas ORDER BY level"
            )
            
            # 比较数据变化
            if not DBManager.compare_area_data(area_names, existing_data):
                print("区域数据无变化，无需更新")
                return True
            
            # 如果变化，执行更新
            print("\n开始更新区域数据...")
            for i, area in enumerate(area_names):
                sql = """
                    INSERT INTO areas (name_zh, name_zht, name_en, level, sys_update_time)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE
                    name_zh = VALUES(name_zh),
                    name_zht = VALUES(name_zht),
                    name_en = VALUES(name_en),
                    sys_update_time = NOW()
                """
                params = (area[0], area[1], area[2], i)
                DBUtils.execute_update(sql, params)
                
            # 验证数据是否正确保存
            verify_sql = "SELECT level FROM areas ORDER BY level"
            result = DBUtils.execute_query(verify_sql)
            if not result:
                raise Exception("区域数据保存验证失败")
                
            print("区域数据保存成功")
            return True
        except Exception as e:
            print(f"保存区域数据失败: {str(e)}")
            return False

    @staticmethod
    def save_events_to_db(events_data):
        """保存赛事数据到数据库
        
        Args:
            events_data: 包含所有赛事信息的列表
            
        Returns:
            bool: 保存成功返回True，否则返回False
        """
        success_count = 0  # 成功更新的记录数
        error_count = 0    # 更新失败的记录数
        
        try:
            # 获取可用的区域级别 
            query_result = DBUtils.execute_query("SELECT level FROM areas")
            if not query_result:
                print("警告: 未找到区域级别数据")
                return False
                
            # 从字典列表中提取 level 值，并转换为字符串以便比较
            available_levels = [str(item['level']) for item in query_result]
            print(f"可用区域级别: {available_levels}")
            
            # 先获取现有数据，用于后续比较
            existing_data = DBUtils.execute_query("""
                SELECT event_id, name_zh, name_zht, name_en, 
                       event_type, type_code, levelid,
                       access_url, url_status
                FROM events
            """)
            print(f"现有数据条数: {len(existing_data) if existing_data else 0}")
            
            # 比较数据变化，如果没有变化则无需更新
            if not DBManager.compare_events_data(events_data, existing_data):
                print("赛事数据无变化，无需更新")
                return True
            
            # 如果有变化，执行更新
            print(f"\n开始更新赛事数据，总数据量: {len(events_data)}")
            for event in events_data:
                try:
                    # 确保区域级别是字符串类型进行比较
                    event_level = str(event['区域级别'])
                    if event_level not in available_levels:
                        print(f"跳过无效的区域级别: {event_level}")
                        continue
                    
                    # SQL语句：插入或更新赛事数据
                    # 使用ON DUPLICATE KEY UPDATE实现upsert操作
                    sql = """
                        INSERT INTO events (
                            event_id, levelid, name_zh, name_zht, name_en, 
                            event_type, type_code, access_url, url_status, 
                            sys_update_time
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        ON DUPLICATE KEY UPDATE
                        levelid = VALUES(levelid),
                        name_zh = VALUES(name_zh),
                        name_zht = VALUES(name_zht),
                        name_en = VALUES(name_en),
                        event_type = VALUES(event_type),
                        type_code = VALUES(type_code),
                        access_url = VALUES(access_url),
                        url_status = VALUES(url_status),
                        sys_update_time = NOW()
                    """
                    
                    # 确保 URL 状态值为整数 (1=有效，0=无效)
                    url_status = int(1 if event['URL有效'] else 0)
                    
                    # 准备SQL参数
                    params = (
                        event['赛事ID'],
                        int(event['区域级别']),  # 确保是整数
                        event['赛事简休名'],
                        event['赛事繁体名'],
                        event['赛事英文名'],
                        event['赛事类型'],
                        int(event['类型编码']),  # 确保是整数
                        event['访问链接'],
                        url_status
                    )
                    
                    # 打印处理信息，便于调试
                    print(f"\n处理赛事: {event['赛事简休名']}")
                    print(f"区域级别: {event['区域级别']}")
                    print(f"URL状态: {url_status}")
                    print(f"类型编码: {event['类型编码']}")
                    
                    # 执行SQL更新
                    result = DBUtils.execute_update(sql, params)
                    if result:
                        success_count += 1
                        print(f"赛事ID {event['赛事ID']} 更新成功")
                    else:
                        error_count += 1
                        print(f"赛事ID {event['赛事ID']} 更新失败")
                        
                except Exception as e:
                    # 单条记录处理失败不影响其他记录
                    error_count += 1
                    print(f"处理赛事ID {event['赛事ID']} 时发生错误: {str(e)}")
                    # 打印详细的参数信息以便调试
                    print(f"参数详情: {event}")
                    continue  # 继续处理下一条数据
            
            # 打印更新统计信息
            print(f"\n数据更新统计:")
            print(f"成功: {success_count}")
            print(f"失败: {error_count}")
            print(f"总计: {len(events_data)}")
            
            # 只要有成功的数据就返回 True
            return success_count > 0
            
        except Exception as e:
            # 处理整体异常
            print(f"保存赛事数据失败，详细错误: {str(e)}")
            import traceback
            traceback.print_exc()  # 打印完整的堆栈跟踪
            return False


def main():
    try:
        print("正在从URL获取数据...")
        js_content = DataFetcher.get_js_content(Config.AREAS_URL)
        
        # 检查数据库和文件状态
        db_has_data = DataFetcher.check_db_has_data()
        js_exists, excel_exists = DataFetcher.check_files_exist()
        
        # 确保输出目录存在
        os.makedirs(Config.JS_OUTPUT_DIR, exist_ok=True)
        js_file_path = os.path.join(Config.JS_OUTPUT_DIR, 'leftData.js')
        
        # 情况1：首次获取（数据库无数据）
        if not db_has_data:
            print("数据库中无数据，执行首次数据获取流程...")
            process_full_data(js_content)
            return
        
        # 情况2：数据库有数据，检查文件存在性
        if not js_exists or not excel_exists:
            print("本地文件不完整，需要重新生成...")
            if compare_with_db(js_content):
                print("数据与数据库一致，仅更新本地文件...")
                save_local_files(js_content)
            else:
                print("数据与数据库不一致，执行完整更新...")
                process_full_data(js_content)
            return
        
        # 情况3：数据库和文件都存在，比较内容
        with open(js_file_path, 'r', encoding='utf-8') as f:
            local_js_content = f.read()
            
        if DataFetcher.compare_js_content(js_content, local_js_content):
            if compare_with_db(js_content):
                print("数据无变化，程序退出")
                return
        
        print("检测到数据变化，执行更新...")
        process_full_data(js_content)

    except Exception as e:
        print(f"程序执行出错: {str(e)}")
        raise

def process_full_data(js_content):
    """执行完整的数据处理流程"""
    # 保存JS文件
    js_file_path = os.path.join(Config.JS_OUTPUT_DIR, 'leftData.js')
    with open(js_file_path, 'w', encoding='utf-8') as f:
        f.write(js_content)
    print(f"JS文件已保存到: {js_file_path}")
    
    print("正在解析数据...")
    all_arrays = DataFetcher.load_area_data(js_content)
    
    # 从获取的数据中提取区域名称
    area_names = DataFetcher.get_area_names(all_arrays)
    if not area_names:
        raise Exception("未能获取区域数据")
    
    # 数据库操作
    print("正在保存区域数据到数据库...")
    if not DBManager.save_areas_to_db(area_names):
        raise Exception("保存区域数据失败")
    
    # 处理数据
    data_for_excel = []
    for i, array in enumerate(all_arrays):
        if array:
            area_name = area_names[i][0]
            print(f"正在处理 {area_name} ...")
            area_data = DataFetcher.extract_area_data(array)
            events_data = DataFetcher.get_events_data(area_data)
            
            if events_data:
                if not DBManager.save_events_to_db(events_data):
                    raise Exception(f"保存 {area_name} 赛事数据失败")
                data_for_excel.append((area_name, events_data))
                print(f"{area_name} 处理完成")
            else:
                print(f"{area_name} 无数据")
    
    # 导出Excel
    if data_for_excel and not ExcelExporter.export_to_excel(data_for_excel, Config.EXCEL_EVENTS_EXCEL):
        raise Exception("导出Excel失败")
    
    print("所有数据处理完成")

def save_local_files(js_content):
    """仅保存本地文件，不进行数据验证和更新"""
    # 保存JS文件
    js_file_path = os.path.join(Config.JS_OUTPUT_DIR, 'leftData.js')
    with open(js_file_path, 'w', encoding='utf-8') as f:
        f.write(js_content)
    print(f"JS文件已保存到: {js_file_path}")
    
    # 解析数据并导出Excel
    all_arrays = DataFetcher.load_area_data(js_content)
    area_names = DataFetcher.get_area_names(all_arrays)
    data_for_excel = []
    
    for i, array in enumerate(all_arrays):
        if array:
            area_name = area_names[i][0]
            area_data = DataFetcher.extract_area_data(array)
            events_data = DataFetcher.get_events_data(area_data)
            if events_data:
                data_for_excel.append((area_name, events_data))
    
    if data_for_excel:
        ExcelExporter.export_to_excel(data_for_excel, Config.EXCEL_EVENTS_EXCEL)

def compare_with_db(js_content):
    """比较JS内容与数据库中的数据是否一致"""
    all_arrays = DataFetcher.load_area_data(js_content)
    area_names = DataFetcher.get_area_names(all_arrays)
    
    # 获取数据库中的数据
    existing_areas = DBUtils.execute_query(
        "SELECT name_zh, name_zht, name_en, level FROM areas ORDER BY level"
    )
    
    # 比较区域数据
    if DBManager.compare_area_data(area_names, existing_areas):
        return False
        
    # 提取并比较赛事数据
    for array in all_arrays:
        if array:
            area_data = DataFetcher.extract_area_data(array)
            events_data = DataFetcher.get_events_data(area_data)
            if events_data:
                existing_events = DBUtils.execute_query("""
                    SELECT event_id, name_zh, name_zht, name_en, 
                           event_type, type_code, levelid,
                           access_url, url_status
                    FROM events
                """)
                if DBManager.compare_events_data(events_data, existing_events):
                    return False
    
    return True


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"程序执行出错: {str(e)}")
        import traceback
        traceback.print_exc()



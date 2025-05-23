1. 运动类型表 → 赛事分类表（定义足球、篮球等大类）。
2. 赛事分类表 → 自关联（通过 `parent_id` 构建多级赛事层级）。
3. 赛事分类表 → 联赛表（关联国家联赛层级）。
4. 联赛表 → 赛季表（每个联赛包含多个赛季）。
5. 赛季表 → 比赛轮次表（每个赛季包含多轮比赛）。
6. 比赛轮次表 → 比赛详情表（每轮包含多场比赛）。
7. 赛季表 → 统计资料表（每个赛季关联独立统计内容）。

1. 赛事分类表（event_category）
存储 洲际赛事、欧洲赛事 等多级分类，通过 parent_id 实现层级嵌套。
```SQL
CREATE TABLE event_category (
    category_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '分类ID',
    category_name VARCHAR(100) NOT NULL COMMENT '分类名称（如欧洲赛事、英超）',
    parent_id INT DEFAULT NULL COMMENT '父级分类ID（用于多级嵌套）',
    -- 外键：父级分类关联自身
    FOREIGN KEY (parent_id) REFERENCES event_category(category_id),
    -- 索引：加速层级查询（如查询子分类）
    INDEX idx_parent_id (parent_id),
    INDEX idx_category_name (category_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

```
数据示例：
```Plaintext
category_id | category_name | parent_id
----------------------------------------
1           | 洲际赛事       | NULL
2           | 欧洲赛事       | NULL
3           | 英格兰         | 2         -- 父级为欧洲赛事
4           | 英超           | 3         -- 父级为英格兰
```


league_t1 (联赛一级分类)：洲际赛事、欧洲赛事、美洲赛事、亚洲赛事、大洋洲赛事、非洲赛事
    └── league_t2 (联赛二级分类类)：洲际赛事
        └── league (具体联赛)
            └── seasons (赛季)
                └── team (球队)
                └── matches (比赛)

league_t1 (联赛一级分类，目前有6个，不确定以后是否会增加)：洲际赛事、欧洲赛事、美洲赛事、亚洲赛事、大洋洲赛事、非洲赛事
    └── league_t2 (联赛二级分类，不确定以后是否会增加)：以欧洲赛事为例，包含了欧洲赛事、英格兰、意大利、西班牙等
        └── league (具体联赛，不确定以后是否会增加)：以英格兰为例，包含了英超、英冠、英甲、英乙、英议联等
            └── seasons (赛季)：2024-2025、2023-2024、2022-2023、2021-2022、2020-2021
                └── team (球队)：英格兰队、利物浦队、切尔西队等
                └── matches (比赛)：2024-2025赛季的第X轮英超联赛比赛列表

欧洲赛事
    └──'欧洲赛事','歐洲賽事','Europe',1,[]
        └──[67,'欧洲杯','歐洲盃','EURO Cup',2],
        └──[103,'欧冠杯','歐冠盃','UEFA CL',2],               
    └──'英格兰','英格蘭','England',1,
        └──[36,'英超','英超','ENG PR',1],
        └──[37,'英冠','英冠','ENG LCH',0],
    └──'意大利','義大利','Italy',1,
        └──[38,'意甲','意甲','ITA PR',1],
        └──[39,'意乙','意甲杯','ITA LCH',0],
        
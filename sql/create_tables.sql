-- 使用已存在的数据库
USE test;

-- 区域表
CREATE TABLE IF NOT EXISTS area (
    id INT PRIMARY KEY AUTO_INCREMENT,
    area_id INT NOT NULL UNIQUE COMMENT '原始区域ID',
    name_zh VARCHAR(50) NOT NULL COMMENT '中文名称',
    name_zht VARCHAR(50) COMMENT '繁体名称',
    name_en VARCHAR(50) COMMENT '英文名称',
    level INT COMMENT '层级：0=洲际, 1=国家/地区, 2=赛事',
    parent_id INT COMMENT '父级ID',
    sort_order INT COMMENT '排序',
    area_type TINYINT COMMENT '区域类型：1=联赛区域, 2=杯赛区域',  -- 新增
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_area_id (area_id),
    INDEX idx_parent_id (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='区域表';

-- 赛事表
CREATE TABLE IF NOT EXISTS competition (
    id INT PRIMARY KEY AUTO_INCREMENT,
    competition_id INT NOT NULL UNIQUE COMMENT '原始赛事ID',
    name_zh VARCHAR(50) NOT NULL COMMENT '中文名称',
    name_zht VARCHAR(50) COMMENT '繁体名称',
    name_en VARCHAR(50) COMMENT '英文名称',
    area_id INT COMMENT '所属区域ID',
    qt_league_id INT COMMENT '关联球探联赛ID',  -- 新增：关联球探联赛
    competition_type TINYINT COMMENT '赛事类型：0=联赛, 1=联赛, 2=杯赛',
    level INT COMMENT '赛事级别',
    is_active TINYINT(1) DEFAULT 1 COMMENT '是否激活',
    sort_order INT COMMENT '排序',
    original_group_id INT COMMENT '原始分组ID',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_competition_id (competition_id),
    INDEX idx_area_id (area_id),
    INDEX idx_qt_league_id (qt_league_id),  -- 新增：索引
    FOREIGN KEY (area_id) REFERENCES area(id),
    FOREIGN KEY (qt_league_id) REFERENCES league(qt_league_id)  -- 新增：外键约束
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='赛事表';

-- 赛季表
CREATE TABLE IF NOT EXISTS season (
    id INT PRIMARY KEY AUTO_INCREMENT,
    competition_id INT NOT NULL COMMENT '赛事ID',
    qt_league_id INT COMMENT '关联球探联赛ID',
    qt_season_id INT COMMENT '关联球探赛季ID',
    season_name VARCHAR(50) NOT NULL COMMENT '赛季名称',
    start_date DATE COMMENT '开始日期',
    end_date DATE COMMENT '结束日期',
    status TINYINT DEFAULT 1 COMMENT '状态：0=未开始, 1=进行中, 2=已结束',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_competition_id (competition_id),
    INDEX idx_qt_league_id (qt_league_id),
    INDEX idx_qt_season_id (qt_season_id),
    FOREIGN KEY (competition_id) REFERENCES competition(id),
    FOREIGN KEY (qt_league_id) REFERENCES league(qt_league_id),
    FOREIGN KEY (qt_season_id) REFERENCES seasons(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='赛季表';
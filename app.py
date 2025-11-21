import zipfile
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
import gzip
import re
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import box, Point

import streamlit as st
import pydeck as pdk

# 可视化相关
import matplotlib.pyplot as plt
import matplotlib
from matplotlib import font_manager
import seaborn as sns
import warnings

warnings.filterwarnings('ignore')


# ============================================================
#  配置中文字体
# ============================================================

def setup_chinese_font():
    """配置matplotlib中文字体"""
    import platform

    # 清除matplotlib缓存
    try:
        import os
        cache_dir = matplotlib.get_cachedir()
        if os.path.exists(cache_dir):
            for file in os.listdir(cache_dir):
                if file.endswith('.cache'):
                    try:
                        os.remove(os.path.join(cache_dir, file))
                    except:
                        pass
    except:
        pass

    # 根据操作系统选择字体
    if platform.system() == 'Windows':
        fonts = ['Microsoft YaHei', 'SimHei', 'SimSun', 'KaiTi', 'FangSong']
    elif platform.system() == 'Darwin':  # macOS
        fonts = ['PingFang SC', 'Heiti SC', 'STHeiti', 'Arial Unicode MS']
    else:  # Linux
        fonts = ['WenQuanYi Micro Hei', 'Noto Sans CJK SC', 'Droid Sans Fallback']

    # 强制设置字体
    plt.rcParams['font.sans-serif'] = fonts
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['font.size'] = 12

    # 设置seaborn样式
    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=1.3)

    # 验证字体设置
    test_fig = plt.figure(figsize=(1, 1))
    test_ax = test_fig.add_subplot(111)
    test_ax.text(0.5, 0.5, '测试中文', fontsize=12)
    plt.close(test_fig)


# 初始化字体设置
setup_chinese_font()

# ============================================================
#  中国常用坐标系定义
# ============================================================

CHINA_CRS_DEFINITIONS = {
    # WGS84地理坐标系
    "EPSG:4326": {
        "name": "WGS84地理坐标系",
        "type": "geographic",
        "unit": "度",
        "description": "全球通用经纬度坐标系",
        "typical_range": {"lon": (73, 135), "lat": (3, 54)},
        "color": "#3498db"
    },

    # UTM投影 - 中国主要使用的带
    "EPSG:32649": {
        "name": "WGS84 UTM 49N",
        "type": "projected",
        "unit": "米",
        "description": "适用于东经108°-114°地区（如重庆、武汉）",
        "typical_range": {"x": (200000, 800000), "y": (2000000, 6000000)},
        "color": "#e74c3c"
    },
    "EPSG:32650": {
        "name": "WGS84 UTM 50N",
        "type": "projected",
        "unit": "米",
        "description": "适用于东经114°-120°地区（如广州、上海）",
        "typical_range": {"x": (200000, 800000), "y": (2000000, 5500000)},
        "color": "#2ecc71"
    },
    "EPSG:32651": {
        "name": "WGS84 UTM 51N",
        "type": "projected",
        "unit": "米",
        "description": "适用于东经120°-126°地区（如台北、哈尔滨）",
        "typical_range": {"x": (200000, 800000), "y": (2500000, 6000000)},
        "color": "#f39c12"
    },

    # CGCS2000坐标系
    "EPSG:4490": {
        "name": "CGCS2000地理坐标系",
        "type": "geographic",
        "unit": "度",
        "description": "中国2000国家大地坐标系（与WGS84高度相似）",
        "typical_range": {"lon": (73, 135), "lat": (3, 54)},
        "color": "#9b59b6"
    },
    "EPSG:4547": {
        "name": "CGCS2000 3度带 39带",
        "type": "projected",
        "unit": "米",
        "description": "适用于东经115.5°-118.5°（中央经线117°）",
        "typical_range": {"x": (39000000, 39800000), "y": (-5000000, 5000000)},
        "color": "#1abc9c"
    },
    "EPSG:4548": {
        "name": "CGCS2000 3度带 40带",
        "type": "projected",
        "unit": "米",
        "description": "适用于东经118.5°-121.5°（中央经线120°）",
        "typical_range": {"x": (40000000, 40800000), "y": (-5000000, 5000000)},
        "color": "#e67e22"
    },

    # Web Mercator
    "EPSG:3857": {
        "name": "Web墨卡托投影",
        "type": "projected",
        "unit": "米",
        "description": "Google Maps、OpenStreetMap等使用",
        "typical_range": {"x": (8000000, 15000000), "y": (300000, 7000000)},
        "color": "#34495e"
    },

    # Beijing 1954
    "EPSG:2433": {
        "name": "Beijing 1954 3度带 39带",
        "type": "projected",
        "unit": "米",
        "description": "北京1954坐标系（老坐标系）",
        "typical_range": {"x": (39000000, 39800000), "y": (-5000000, 5000000)},
        "color": "#95a5a6"
    },
}


def get_recommended_crs_for_region(gdf: gpd.GeoDataFrame) -> List[str]:
    """根据研究范围智能推荐合适的坐标系"""
    recommendations = []

    # 先转换到WGS84获取经纬度范围
    gdf_wgs84 = gdf.to_crs(epsg=4326)
    bounds = gdf_wgs84.total_bounds
    center_lon = (bounds[0] + bounds[2]) / 2
    center_lat = (bounds[1] + bounds[3]) / 2

    # 1. 优先推荐：基于中心经度选择最佳UTM带
    utm_zone = int((center_lon + 180) / 6) + 1
    utm_epsg = f"EPSG:326{utm_zone:02d}"

    if utm_epsg in CHINA_CRS_DEFINITIONS:
        recommendations.append(utm_epsg)

    # 2. 根据经度范围推荐CGCS2000 3度带
    if 115.5 <= center_lon <= 118.5:
        recommendations.append("EPSG:4547")
    elif 118.5 <= center_lon <= 121.5:
        recommendations.append("EPSG:4548")

    # 3. 常用通用坐标系
    if "EPSG:3857" not in recommendations:
        recommendations.append("EPSG:3857")

    # 4. 地理坐标系
    recommendations.append("EPSG:4490")
    recommendations.append("EPSG:4326")

    return recommendations


def transform_coordinates(
        x: float,
        y: float,
        from_crs: str,
        to_crs: str
) -> Tuple[float, float]:
    """坐标转换"""
    try:
        from pyproj import Transformer
        transformer = Transformer.from_crs(from_crs, to_crs, always_xy=True)
        new_x, new_y = transformer.transform(x, y)
        return float(new_x), float(new_y)
    except Exception as e:
        st.error(f"坐标转换失败: {e}")
        return x, y


def display_coordinate_in_multiple_crs(
        x: float,
        y: float,
        source_crs: str,
        target_crs_list: List[str]
) -> pd.DataFrame:
    """显示同一点在多个坐标系下的坐标"""
    results = []

    for target_crs in target_crs_list:
        try:
            new_x, new_y = transform_coordinates(x, y, source_crs, target_crs)
            crs_info = CHINA_CRS_DEFINITIONS.get(target_crs, {})

            results.append({
                "坐标系": target_crs,
                "名称": crs_info.get("name", "未知"),
                "X坐标": f"{new_x:.6f}" if crs_info.get("type") == "geographic" else f"{new_x:.2f}",
                "Y坐标": f"{new_y:.6f}" if crs_info.get("type") == "geographic" else f"{new_y:.2f}",
                "单位": crs_info.get("unit", "未知"),
                "说明": crs_info.get("description", "")
            })
        except Exception as e:
            results.append({
                "坐标系": target_crs,
                "名称": "转换失败",
                "X坐标": "-",
                "Y坐标": "-",
                "单位": "-",
                "说明": str(e)
            })

    return pd.DataFrame(results)


# ============================================================
#  时间转换工具函数
# ============================================================

def time_string_to_minutes(time_str: str) -> int:
    """将 HH:MM:SS 格式转换为分钟数"""
    try:
        parts = time_str.split(':')
        if len(parts) == 3:
            h, m, s = map(int, parts)
            return h * 60 + m + (1 if s >= 30 else 0)
        elif len(parts) == 2:
            h, m = map(int, parts)
            return h * 60 + m
        else:
            return int(time_str)
    except:
        return 0


def minutes_to_time_string(minutes: int) -> str:
    """将分钟数转换为 HH:MM:SS 格式"""
    if minutes < 0:
        minutes = 0
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}:00"


def validate_time_string(time_str: str) -> bool:
    """验证时间字符串格式"""
    pattern = r'^([0-9]{1,2}):([0-5][0-9]):([0-5][0-9])$'
    return bool(re.match(pattern, time_str))


# ============================================================
#  通用工具函数
# ============================================================

def read_zipped_shapefile(uploaded_file) -> gpd.GeoDataFrame:
    """从用户上传的 zip 文件中读取 shapefile"""
    if uploaded_file is None:
        return None

    try:
        with zipfile.ZipFile(uploaded_file) as zf:
            import tempfile
            import os
            tmpdir = tempfile.mkdtemp()
            zf.extractall(tmpdir)

            shp_files = [f for f in os.listdir(tmpdir) if f.lower().endswith(".shp")]
            if not shp_files:
                st.error("ZIP 文件里没有找到 .shp 文件")
                return None
            shp_path = os.path.join(tmpdir, shp_files[0])

            gdf = gpd.read_file(shp_path)
            return gdf
    except Exception as e:
        st.error(f"读取 Shapefile 失败：{e}")
        return None


def ensure_projected(gdf: gpd.GeoDataFrame, target_crs: str = "EPSG:3857") -> gpd.GeoDataFrame:
    """确保 GeoDataFrame 在一个米制投影下"""
    if gdf is None or gdf.empty:
        return gdf

    if gdf.crs is None:
        gdf = gdf.set_crs(target_crs)
    elif gdf.crs.to_string() == "EPSG:4326":
        gdf = gdf.to_crs(target_crs)
    else:
        gdf = gdf.to_crs(target_crs)
    return gdf


def get_rate_for_age(age: int, rate_by_age: Dict[str, float]) -> float:
    """根据年龄获取对应的比率"""
    for k, v in rate_by_age.items():
        if "+" in k:
            low = int(k.replace("+", ""))
            if age >= low:
                return v
        else:
            parts = k.split("-")
            if len(parts) == 2:
                low, high = int(parts[0]), int(parts[1])
                if low <= age <= high:
                    return v
    return 0.0


def _sample_from_distribution(dist: Dict, rng: np.random.RandomState):
    """从分布中采样"""
    keys = list(dist.keys())
    vals = np.array(list(dist.values()), dtype=float)
    if vals.sum() <= 0:
        vals = np.ones_like(vals)
    probs = vals / vals.sum()
    idx = rng.choice(len(keys), p=probs)
    return keys[idx]


# ============================================================
#  地图显示函数（支持多中心点不同颜色）
# ============================================================

def show_polygon_map(
        gdf: gpd.GeoDataFrame,
        fill_color=(0, 0, 255, 128),
        height: int = 400,
        label: str = "",
        color_by: str = None,
        color_column: str = None
) -> None:
    """
    使用 pydeck 在底图上叠加多边形图层

    Args:
        gdf: GeoDataFrame
        fill_color: 默认填充颜色 (R, G, B, A)
        height: 地图高度
        label: 标签
        color_by: 着色方式 'center'(按中心点), 'area_type'(按区域类型), None(统一颜色)
        color_column: 用于着色的列名
    """
    if gdf is None or gdf.empty:
        st.info("没有几何数据可展示。")
        return

    gdf_ll = gdf.to_crs(epsg=4326).copy()

    # 定义颜色映射
    center_colors = {
        '主中心': [231, 76, 60, 180],  # 红色
        '中心点2': [46, 204, 113, 180],  # 绿色
        '中心点3': [52, 152, 219, 180],  # 蓝色
        '中心点4': [155, 89, 182, 180],  # 紫色
        '中心点5': [241, 196, 15, 180],  # 黄色
        '中心点6': [230, 126, 34, 180],  # 橙色
        '中心点7': [149, 165, 166, 180],  # 灰色
        '中心点8': [26, 188, 156, 180],  # 青色
    }

    area_type_colors = {
        'CBD': [231, 76, 60, 180],  # 红色
        'urban': [52, 152, 219, 180],  # 蓝色
        'suburban': [46, 204, 113, 180],  # 绿色
        'rural': [241, 196, 15, 180],  # 黄色
        'mixed': [155, 89, 182, 180],  # 紫色
        'default': [149, 165, 166, 180],  # 灰色
    }

    data = []

    for idx, row in gdf_ll.iterrows():
        geom = row.geometry
        if geom.is_empty:
            continue

        # 确定颜色
        if color_by == 'center' and color_column and color_column in gdf_ll.columns:
            center_name = row[color_column]
            color = center_colors.get(center_name, fill_color)
        elif color_by == 'area_type' and color_column and color_column in gdf_ll.columns:
            area_type = row[color_column]
            color = area_type_colors.get(area_type, fill_color)
        else:
            color = fill_color

        if geom.geom_type == "Polygon":
            coords = list(geom.exterior.coords)
            data.append({
                "polygon": coords,
                "fill_color": color
            })
        elif geom.geom_type == "MultiPolygon":
            for poly in geom.geoms:
                coords = list(poly.exterior.coords)
                data.append({
                    "polygon": coords,
                    "fill_color": color
                })

    if not data:
        st.info("未能从几何中提取 Polygon。")
        return

    minx, miny, maxx, maxy = gdf_ll.total_bounds
    mid_lon = (minx + maxx) / 2
    mid_lat = (miny + maxy) / 2

    layer = pdk.Layer(
        "PolygonLayer",
        data=data,
        get_polygon="polygon",
        get_fill_color="fill_color",
        get_line_color=[0, 0, 0, 200],
        line_width_min_pixels=1,
        stroked=True,
        pickable=True,
    )

    view_state = pdk.ViewState(
        longitude=mid_lon,
        latitude=mid_lat,
        zoom=10,
        pitch=0,
        bearing=0,
    )

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        map_style="mapbox://styles/mapbox/light-v9",
    )

    if label:
        st.markdown(label)
    st.pydeck_chart(deck, height=height)

    # 显示图例
    if color_by == 'center' and color_column and color_column in gdf_ll.columns:
        unique_centers = gdf_ll[color_column].unique()
        st.markdown("**图例（按中心点）：**")
        legend_cols = st.columns(len(unique_centers))
        for i, center in enumerate(unique_centers):
            color = center_colors.get(center, fill_color)
            with legend_cols[i]:
                st.markdown(
                    f'<div style="background-color:rgba({color[0]},{color[1]},{color[2]},{color[3] / 255}); '
                    f'padding:5px; border-radius:3px; text-align:center;">{center}</div>',
                    unsafe_allow_html=True
                )
    elif color_by == 'area_type' and color_column and color_column in gdf_ll.columns:
        unique_types = gdf_ll[color_column].unique()
        st.markdown("**图例（按区域类型）：**")
        legend_cols = st.columns(len(unique_types))
        for i, atype in enumerate(unique_types):
            color = area_type_colors.get(atype, fill_color)
            with legend_cols[i]:
                st.markdown(
                    f'<div style="background-color:rgba({color[0]},{color[1]},{color[2]},{color[3] / 255}); '
                    f'padding:5px; border-radius:3px; text-align:center;">{atype}</div>',
                    unsafe_allow_html=True
                )


# ============================================================
#  数据结构定义
# ============================================================

@dataclass
class CenterPoint:
    """中心点配置"""
    name: str
    x: float
    y: float
    rings: List[Tuple[float, str]]  # [(半径, area_type), ...]
    priority: int = 0
    crs: str = "EPSG:3857"


@dataclass
class AreaTypeConfig:
    """区域类型专属配置（完整参数）"""
    area_type: str

    # ===== 人口生成参数 =====
    # 家庭规模分布
    hhsize_dist: Dict[str, float] = field(default_factory=lambda: {
        "1": 0.30, "2": 0.40, "3": 0.20, "4": 0.10, "5+": 0.00
    })

    # 收入分布权重
    income_segment_weights: Dict[str, float] = field(default_factory=lambda: {
        "low": 0.3, "mid": 0.5, "high": 0.2
    })

    # 汽车拥有量（按收入和家庭规模）
    autos_by_income_and_hhsize: Dict[str, Dict[str, List[float]]] = field(default_factory=lambda: {
        "low": {"1": [0.8, 0.2, 0.0], "2": [0.6, 0.4, 0.0], "3+": [0.4, 0.4, 0.2]},
        "mid": {"1": [0.5, 0.5, 0.0], "2": [0.3, 0.6, 0.1], "3+": [0.2, 0.5, 0.3]},
        "high": {"1": [0.3, 0.4, 0.3], "2": [0.2, 0.4, 0.4], "3+": [0.1, 0.4, 0.5]}
    })

    # 年龄结构
    age_shares: Dict[str, float] = field(default_factory=lambda: {
        "0-5": 0.05, "6-17": 0.15, "18-22": 0.10, "23-64": 0.55, "65+": 0.15
    })

    # 就业率（按年龄）
    worker_rate_by_age: Dict[str, float] = field(default_factory=lambda: {
        "16-17": 0.05, "18-22": 0.30, "23-59": 0.80, "60-64": 0.40, "65+": 0.10
    })

    # 在学率（按年龄）
    student_rate_by_age: Dict[str, float] = field(default_factory=lambda: {
        "6-17": 0.95, "18-22": 0.70
    })

    # 驾照率（按年龄）
    license_rate_by_age: Dict[str, float] = field(default_factory=lambda: {
        "18-22": 0.50, "23-59": 0.90, "60-69": 0.70, "70+": 0.40
    })

    # ===== Tour生成参数 =====
    # Tour频率
    tour_frequency: Dict[str, Dict[int, float]] = field(default_factory=lambda: {
        'full_time_worker': {0: 0.05, 1: 0.60, 2: 0.30, 3: 0.05},
        'university_student': {0: 0.10, 1: 0.70, 2: 0.20},
        'non_worker': {0: 0.30, 1: 0.50, 2: 0.20},
        'child': {0: 0.20, 1: 0.70, 2: 0.10},
        'worker_other': {0: 0.15, 1: 0.60, 2: 0.25}
    })

    # Tour类型分布
    tour_type_dist: Dict[str, float] = field(default_factory=lambda: {
        'shopping': 0.30, 'social': 0.25, 'dining': 0.20,
        'escort': 0.15, 'other': 0.10
    })

    # 时间窗口（分钟）
    time_windows: Dict[str, Tuple[int, int]] = field(default_factory=lambda: {
        'work': (420, 540),  # 07:00-09:00
        'school': (390, 480),  # 06:30-08:00
        'shopping': (540, 1140),  # 09:00-19:00
        'social': (600, 1200),  # 10:00-20:00
        'dining': (660, 1260),  # 11:00-21:00
        'escort': (420, 540),  # 07:00-09:00
        'other': (480, 1200)  # 08:00-20:00
    })

    # 持续时间参数（分钟）
    duration_params: Dict[str, Tuple[int, int]] = field(default_factory=lambda: {
        'work': (420, 600),  # 7-10小时
        'school': (360, 480),  # 6-8小时
        'shopping': (60, 180),  # 1-3小时
        'social': (90, 240),  # 1.5-4小时
        'dining': (60, 150),  # 1-2.5小时
        'escort': (30, 60),  # 0.5-1小时
        'other': (60, 240)  # 1-4小时
    })

    # 停靠频率
    stop_frequency: Dict[str, Dict[int, float]] = field(default_factory=lambda: {
        'work': {0: 0.80, 1: 0.15, 2: 0.05},
        'school': {0: 0.85, 1: 0.12, 2: 0.03},
        'shopping': {0: 0.70, 1: 0.25, 2: 0.05},
        'social': {0: 0.70, 1: 0.25, 2: 0.05},
        'dining': {0: 0.90, 1: 0.08, 2: 0.02},
        'escort': {0: 0.70, 1: 0.25, 2: 0.05},
        'other': {0: 0.70, 1: 0.25, 2: 0.05}
    })

    # 出行距离参数
    max_distance: float = 30000.0
    distance_decay: float = 0.1


@dataclass
class PopulationConfig:
    """全局人口配置"""
    total_households: int
    max_persons_per_household: int
    hhsize_dist: Dict[str, float]
    income_segments: Dict[str, Tuple[float, float]]
    income_segment_weights: Dict[str, float]
    autos_by_income_and_hhsize: Dict[str, Dict[str, List[float]]]
    age_shares: Dict[str, float]
    worker_rate_by_age: Dict[str, float]
    student_rate_by_age: Dict[str, float]
    license_rate_by_age: Dict[str, float]


# ============================================================
#  人口生成相关函数
# ============================================================

def sample_age_for_role(role: str, age_shares: Dict[str, float], rng: np.random.RandomState) -> int:
    """根据角色采样年龄"""

    def pick_from_bins(bins: List[str]) -> str:
        weights = [max(age_shares.get(b, 0.0), 0.0) for b in bins]
        total = sum(weights)
        if total <= 0:
            weights = [1.0] * len(bins)
            total = float(len(bins))
        probs = [w / total for w in weights]
        idx = rng.choice(len(bins), p=probs)
        return bins[idx]

    if role == "child":
        label = pick_from_bins(["0-5", "6-17"])
    elif role == "adult":
        label = pick_from_bins(["18-22", "23-64"])
    else:  # elder
        label = "65+"

    if label == "0-5":
        low, high = 0, 5
    elif label == "6-17":
        low, high = 6, 17
    elif label == "18-22":
        low, high = 18, 22
    elif label == "23-64":
        low, high = 23, 64
    else:  # 65+
        low, high = 65, 90

    return int(rng.randint(low, high + 1))


def generate_household_structure(
        hhsize: int,
        age_shares: Dict[str, float],
        rng: np.random.RandomState
) -> List[Tuple[int, str]]:
    """根据 hhsize 生成一个家庭的年龄结构和角色"""
    persons: List[Tuple[int, str]] = []

    if hhsize == 1:
        age = sample_age_for_role("adult", age_shares, rng)
        persons.append((age, "adult"))
        return persons

    if hhsize == 2:
        r = rng.rand()
        if r < 0.7:
            a1 = sample_age_for_role("adult", age_shares, rng)
            a2 = int(np.clip(a1 + rng.randint(-10, 11), 20, 80))
            persons.append((a1, "adult"))
            persons.append((a2, "adult"))
        else:
            parent_age = sample_age_for_role("adult", age_shares, rng)
            max_child_age = max(min(parent_age - 18, 17), 0)
            if max_child_age <= 0:
                child_age = int(rng.randint(0, 6))
            else:
                child_age = int(rng.randint(0, max_child_age + 1))
            persons.append((parent_age, "adult"))
            persons.append((child_age, "child"))
        return persons

    if hhsize == 3:
        r = rng.rand()
        if r < 0.6:
            p1 = sample_age_for_role("adult", age_shares, rng)
            p2 = int(np.clip(p1 + rng.randint(-10, 11), 22, 70))
            oldest_parent = max(p1, p2)
            max_child_age = max(min(oldest_parent - 18, 17), 0)
            if max_child_age <= 0:
                child_age = int(rng.randint(0, 6))
            else:
                child_age = int(rng.randint(0, max_child_age + 1))
            persons.append((p1, "adult"))
            persons.append((p2, "adult"))
            persons.append((child_age, "child"))
        elif r < 0.9:
            parent_age = sample_age_for_role("adult", age_shares, rng)
            max_child_age = max(min(parent_age - 18, 17), 0)
            if max_child_age <= 0:
                c1 = int(rng.randint(0, 6))
                c2 = int(rng.randint(0, 6))
            else:
                c1 = int(rng.randint(0, max_child_age + 1))
                c2 = int(rng.randint(0, max_child_age + 1))
            persons.append((parent_age, "adult"))
            persons.append((c1, "child"))
            persons.append((c2, "child"))
        else:
            for _ in range(3):
                age = sample_age_for_role("adult", age_shares, rng)
                persons.append((age, "adult"))
        return persons

    # hhsize >= 4
    r = rng.rand()
    remaining = hhsize

    if r < 0.6:
        p1 = sample_age_for_role("adult", age_shares, rng)
        p2 = int(np.clip(p1 + rng.randint(-10, 11), 25, 70))
        persons.append((p1, "adult"))
        persons.append((p2, "adult"))
        remaining -= 2

        oldest_parent = max(p1, p2)
        max_child_age = max(min(oldest_parent - 18, 17), 0)

        for _ in range(remaining):
            if max_child_age <= 0:
                c_age = int(rng.randint(0, 6))
            else:
                c_age = int(rng.randint(0, max_child_age + 1))
            persons.append((c_age, "child"))

    elif r < 0.85:
        p1 = sample_age_for_role("adult", age_shares, rng)
        p2 = int(np.clip(p1 + rng.randint(-10, 11), 25, 70))
        elder_age = int(rng.randint(65, 90))
        persons.append((p1, "adult"))
        persons.append((p2, "adult"))
        persons.append((elder_age, "elder"))
        remaining -= 3

        oldest_parent = max(p1, p2)
        max_child_age = max(min(oldest_parent - 18, 17), 0)

        for _ in range(remaining):
            if max_child_age <= 0:
                c_age = int(rng.randint(0, 6))
            else:
                c_age = int(rng.randint(0, max_child_age + 1))
            persons.append((c_age, "child"))
    else:
        for _ in range(hhsize):
            age = sample_age_for_role("adult", age_shares, rng)
            persons.append((age, "adult"))

    return persons


def generate_grid_zones(
        study_gdf: gpd.GeoDataFrame,
        cell_size: float,
        min_overlap_ratio: float = 0.1
) -> gpd.GeoDataFrame:
    """在 study_gdf 范围内生成规则方格网格"""
    if study_gdf is None or study_gdf.empty:
        return None

    bounds = study_gdf.total_bounds
    minx, miny, maxx, maxy = bounds

    grid_cells = []
    zone_id = 1

    study_union = study_gdf.unary_union

    x = minx
    while x < maxx:
        y = miny
        while y < maxy:
            cell = box(x, y, x + cell_size, y + cell_size)
            intersection = cell.intersection(study_union)

            if not intersection.is_empty:
                overlap_area = intersection.area
                cell_area = cell.area
                overlap_ratio = overlap_area / cell_area if cell_area > 0 else 0

                if overlap_ratio >= min_overlap_ratio:
                    centroid = cell.centroid
                    grid_cells.append({
                        'zone_id': zone_id,
                        'centroid_x': centroid.x,
                        'centroid_y': centroid.y,
                        'geometry': cell
                    })
                    zone_id += 1

            y += cell_size
        x += cell_size

    if not grid_cells:
        return None

    grid_gdf = gpd.GeoDataFrame(grid_cells, crs=study_gdf.crs)
    return grid_gdf


def assign_area_type_rings(
        zones_gdf: gpd.GeoDataFrame,
        center_point: Tuple[float, float],
        rings: List[Tuple[float, str]]
) -> gpd.GeoDataFrame:
    """根据到中心点的距离，为每个 zone 分配 area_type"""
    zones_gdf = zones_gdf.copy()
    center = Point(center_point)

    def get_area_type(centroid):
        dist = centroid.distance(center)
        for radius, area_type in rings:
            if radius is None:
                return area_type
            elif dist < radius:
                return area_type
        return rings[-1][1]

    if 'centroid' not in zones_gdf.columns:
        zones_gdf['centroid'] = zones_gdf.geometry.centroid

    zones_gdf['area_type'] = zones_gdf['centroid'].apply(get_area_type)
    return zones_gdf


def assign_area_type_multi_centers(
        zones_gdf: gpd.GeoDataFrame,
        center_points: List[CenterPoint],
        default_area_type: str = "rural"
) -> gpd.GeoDataFrame:
    """
    根据多个中心点和它们的圈层，为每个zone分配area_type
    优先级高的中心点会覆盖优先级低的中心点的area_type
    """
    zones_gdf = zones_gdf.copy()

    if 'centroid' not in zones_gdf.columns:
        zones_gdf['centroid'] = zones_gdf.geometry.centroid

    # 初始化为默认类型
    zones_gdf['area_type'] = default_area_type
    zones_gdf['assigned_center'] = None

    # 获取zones的坐标系
    zones_crs = zones_gdf.crs.to_string()

    # 按优先级排序（优先级低的先处理，高的后处理会覆盖）
    sorted_centers = sorted(center_points, key=lambda x: x.priority)

    for center in sorted_centers:
        # 如果中心点坐标系与zones不同，需要转换
        center_x, center_y = center.x, center.y
        if center.crs != zones_crs:
            center_x, center_y = transform_coordinates(
                center.x, center.y, center.crs, zones_crs
            )

        center_point = Point(center_x, center_y)

        # 计算所有zone到该中心点的距离
        distances = zones_gdf['centroid'].apply(lambda c: c.distance(center_point))

        # 根据rings分配area_type
        for radius, area_type in center.rings:
            if radius is None:
                # 无限半径
                mask = zones_gdf['area_type'] == default_area_type
                zones_gdf.loc[mask, 'area_type'] = area_type
                zones_gdf.loc[mask, 'assigned_center'] = center.name
            else:
                # 在半径范围内的zone
                mask = distances < radius
                zones_gdf.loc[mask, 'area_type'] = area_type
                zones_gdf.loc[mask, 'assigned_center'] = center.name

    return zones_gdf


def get_all_area_types_from_centers(center_points: List[CenterPoint]) -> List[str]:
    """从中心点配置中提取所有唯一的area_type"""
    area_types = set()
    for center in center_points:
        for radius, area_type in center.rings:
            area_types.add(area_type)
    return sorted(list(area_types))


# ============================================================
#  人口生成函数（统一参数模式）
# ============================================================

def generate_households_and_persons(
        zones_gdf: gpd.GeoDataFrame,
        cfg: PopulationConfig,
        seed: int = 42
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """生成 households 和 persons（统一参数模式）"""
    rng = np.random.RandomState(seed)

    if zones_gdf is None or zones_gdf.empty:
        raise ValueError("zones_gdf 为空，无法生成人口数据。")

    if "zone_weight" in zones_gdf.columns:
        weights = zones_gdf["zone_weight"].values.astype(float)
    else:
        weights = zones_gdf.geometry.area.values.astype(float)
    weights = weights / weights.sum()

    households = []
    person_records = []

    def hhsize_from_label(label: str) -> int:
        if "+" in label:
            base = int(label.replace("+", ""))
            return min(base, cfg.max_persons_per_household)
        else:
            return int(label)

    income_segments = cfg.income_segments
    income_seg_ids = list(income_segments.keys())

    w_vals = np.array([cfg.income_segment_weights.get(s, 0.0) for s in income_seg_ids], dtype=float)
    if w_vals.sum() <= 0:
        w_vals = np.ones_like(w_vals)
    w_probs = w_vals / w_vals.sum()

    for hid in range(1, cfg.total_households + 1):
        z_idx = rng.choice(len(zones_gdf), p=weights)
        z_row = zones_gdf.iloc[z_idx]
        home_zone_id = z_row["zone_id"]
        area_type = z_row.get("area_type", "default")

        hhsize_label = _sample_from_distribution(cfg.hhsize_dist, rng)
        hhsize = hhsize_from_label(hhsize_label)

        seg_idx = rng.choice(len(income_seg_ids), p=w_probs)
        income_seg = income_seg_ids[seg_idx]
        income_min, income_max = income_segments[income_seg]

        lo = max(income_min, 1.0)
        hi = max(income_max, lo + 1.0)
        income_val = float(np.exp(rng.uniform(np.log(lo), np.log(hi))))

        if hhsize <= 1:
            hhsize_key = "1"
        elif hhsize == 2:
            hhsize_key = "2"
        else:
            hhsize_key = "3+"

        autos_dist = cfg.autos_by_income_and_hhsize.get(income_seg, {}).get(
            hhsize_key, [1.0, 0.0, 0.0]
        )
        autos_dist = np.array(autos_dist, dtype=float)
        if autos_dist.sum() <= 0:
            autos_dist = np.array([1.0, 0.0, 0.0])
        autos_probs = autos_dist / autos_dist.sum()
        autos_choice = rng.choice([0, 1, 2], p=autos_probs)
        if autos_choice == 2:
            autos = int(rng.randint(2, 4))
        else:
            autos = int(autos_choice)

        households.append(
            dict(
                household_id=hid,
                home_zone_id=home_zone_id,
                income=income_val,
                income_segment=income_seg,
                autos=autos,
                area_type=area_type,
                hhsize=hhsize,
            )
        )

    hh_df = pd.DataFrame(households)

    person_id_counter = 1

    for _, hh in hh_df.iterrows():
        hid = int(hh["household_id"])
        hhsize = int(hh["hhsize"])

        structure = generate_household_structure(hhsize, cfg.age_shares, rng)

        for age, role in structure:
            sex = rng.choice(["M", "F"])

            worker_rate = get_rate_for_age(age, cfg.worker_rate_by_age)
            student_rate = get_rate_for_age(age, cfg.student_rate_by_age)
            license_rate = get_rate_for_age(age, cfg.license_rate_by_age)

            if age < 16:
                worker_rate = 0.0
            if age < 6:
                student_rate = 0.0

            is_worker = int(rng.rand() < worker_rate)
            is_student = int(rng.rand() < student_rate)

            if age >= 30 and is_worker == 1:
                is_student = 0

            if age > 25 and is_student == 1:
                is_worker = 0

            has_license = int(rng.rand() < license_rate)
            if age < 18:
                has_license = 0

            if age < 16:
                person_type = "child"
            elif is_student == 1 and 18 <= age <= 25:
                person_type = "university_student"
            elif is_worker == 1 and 23 <= age <= 60:
                person_type = "full_time_worker"
            elif is_worker == 1:
                person_type = "worker_other"
            else:
                person_type = "non_worker"

            person_records.append(
                dict(
                    person_id=person_id_counter,
                    household_id=hid,
                    age=age,
                    sex=sex,
                    is_worker=is_worker,
                    is_student=is_student,
                    person_type=person_type,
                    license=has_license,
                )
            )
            person_id_counter += 1

    persons_df = pd.DataFrame(person_records)

    # 确保有车家庭至少有一人有驾照
    for idx, hh in hh_df.iterrows():
        autos = int(hh["autos"])
        hid = int(hh["household_id"])
        if autos <= 0:
            continue

        mask = persons_df["household_id"] == hid
        if not mask.any():
            continue

        if persons_df.loc[mask, "license"].sum() == 0:
            adult_mask = mask & (persons_df["age"] >= 18)
            if adult_mask.any():
                candidate_idx = persons_df.loc[adult_mask].sample(
                    1, random_state=rng.randint(0, 1_000_000)
                ).index[0]
            else:
                candidate_idx = persons_df.loc[mask].sample(
                    1, random_state=rng.randint(0, 1_000_000)
                ).index[0]
            persons_df.at[candidate_idx, "license"] = 1

    # 统计信息
    hh_size_actual = persons_df.groupby("household_id").size().rename("hhsize_actual")
    hh_workers = persons_df.groupby("household_id")["is_worker"].sum().rename("workers")
    hh_children = persons_df.groupby("household_id").apply(
        lambda df: (df["age"] < 16).sum()
    ).rename("children")

    hh_df = hh_df.merge(hh_size_actual, on="household_id", how="left")
    hh_df = hh_df.merge(hh_workers, on="household_id", how="left")
    hh_df = hh_df.merge(hh_children, on="household_id", how="left")

    hh_df["hhsize"] = hh_df["hhsize_actual"]
    hh_df.drop(columns=["hhsize_actual"], inplace=True)

    hh_df['workers'] = hh_df['workers'].fillna(0).astype(int)
    hh_df['children'] = hh_df['children'].fillna(0).astype(int)

    return hh_df, persons_df


# ============================================================
#  按区域类型生成人口的函数
# ============================================================

def generate_households_and_persons_by_area_type(
        zones_gdf: gpd.GeoDataFrame,
        total_households: int,
        max_persons_per_household: int,
        income_segments: Dict[str, Tuple[float, float]],
        area_type_configs: Dict[str, AreaTypeConfig],
        seed: int = 42
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """按area_type使用不同配置生成家庭和个人"""
    rng = np.random.RandomState(seed)

    if zones_gdf is None or zones_gdf.empty:
        raise ValueError("zones_gdf 为空，无法生成人口数据。")

    # 按area_type分组zones
    area_type_groups = zones_gdf.groupby('area_type')

    households = []
    person_records = []

    hh_id_counter = 1
    person_id_counter = 1

    for area_type, zones_group in area_type_groups:

        # 获取该area_type的配置
        if area_type not in area_type_configs:
            st.warning(f"⚠️ 区域类型 '{area_type}' 没有找到配置，跳过")
            continue

        config = area_type_configs[area_type]

        # 计算该area_type应生成的家庭数（按zone面积权重分配）
        if "zone_weight" in zones_group.columns:
            weights = zones_group["zone_weight"].values.astype(float)
        else:
            weights = zones_group.geometry.area.values.astype(float)

        total_weight = weights.sum()

        if "zone_weight" in zones_gdf.columns:
            area_total_weight = zones_gdf["zone_weight"].sum()
        else:
            area_total_weight = zones_gdf.geometry.area.sum()

        num_hh_for_area = int(total_households * (total_weight / area_total_weight))

        if num_hh_for_area == 0:
            continue

        weights = weights / weights.sum()

        # 生成该area_type的家庭
        for _ in range(num_hh_for_area):
            z_idx = rng.choice(len(zones_group), p=weights)
            z_row = zones_group.iloc[z_idx]
            home_zone_id = z_row["zone_id"]

            # 使用该area_type的hhsize分布
            hhsize_label = _sample_from_distribution(config.hhsize_dist, rng)

            def hhsize_from_label(label: str) -> int:
                if "+" in label:
                    base = int(label.replace("+", ""))
                    return min(base, max_persons_per_household)
                else:
                    return int(label)

            hhsize = hhsize_from_label(hhsize_label)

            # 使用该area_type的收入分布
            income_seg_ids = list(income_segments.keys())
            w_vals = np.array([config.income_segment_weights.get(s, 0.0) for s in income_seg_ids], dtype=float)
            if w_vals.sum() <= 0:
                w_vals = np.ones_like(w_vals)
            w_probs = w_vals / w_vals.sum()

            seg_idx = rng.choice(len(income_seg_ids), p=w_probs)
            income_seg = income_seg_ids[seg_idx]
            income_min, income_max = income_segments[income_seg]

            lo = max(income_min, 1.0)
            hi = max(income_max, lo + 1.0)
            income_val = float(np.exp(rng.uniform(np.log(lo), np.log(hi))))

            # 使用该area_type的汽车拥有率
            if hhsize <= 1:
                hhsize_key = "1"
            elif hhsize == 2:
                hhsize_key = "2"
            else:
                hhsize_key = "3+"

            autos_dist = config.autos_by_income_and_hhsize.get(income_seg, {}).get(
                hhsize_key, [1.0, 0.0, 0.0]
            )
            autos_dist = np.array(autos_dist, dtype=float)
            if autos_dist.sum() <= 0:
                autos_dist = np.array([1.0, 0.0, 0.0])
            autos_probs = autos_dist / autos_dist.sum()
            autos_choice = rng.choice([0, 1, 2], p=autos_probs)
            if autos_choice == 2:
                autos = int(rng.randint(2, 4))
            else:
                autos = int(autos_choice)

            households.append(
                dict(
                    household_id=hh_id_counter,
                    home_zone_id=home_zone_id,
                    income=income_val,
                    income_segment=income_seg,
                    autos=autos,
                    area_type=area_type,
                    hhsize=hhsize,
                )
            )

            # 生成家庭成员
            structure = generate_household_structure(hhsize, config.age_shares, rng)

            for age, role in structure:
                sex = rng.choice(["M", "F"])

                worker_rate = get_rate_for_age(age, config.worker_rate_by_age)
                student_rate = get_rate_for_age(age, config.student_rate_by_age)
                license_rate = get_rate_for_age(age, config.license_rate_by_age)

                if age < 16:
                    worker_rate = 0.0
                if age < 6:
                    student_rate = 0.0

                is_worker = int(rng.rand() < worker_rate)
                is_student = int(rng.rand() < student_rate)

                if age >= 30 and is_worker == 1:
                    is_student = 0

                if age > 25 and is_student == 1:
                    is_worker = 0

                has_license = int(rng.rand() < license_rate)
                if age < 18:
                    has_license = 0

                if age < 16:
                    person_type = "child"
                elif is_student == 1 and 18 <= age <= 25:
                    person_type = "university_student"
                elif is_worker == 1 and 23 <= age <= 60:
                    person_type = "full_time_worker"
                elif is_worker == 1:
                    person_type = "worker_other"
                else:
                    person_type = "non_worker"

                person_records.append(
                    dict(
                        person_id=person_id_counter,
                        household_id=hh_id_counter,
                        age=age,
                        sex=sex,
                        is_worker=is_worker,
                        is_student=is_student,
                        person_type=person_type,
                        license=has_license,
                    )
                )
                person_id_counter += 1

            hh_id_counter += 1

    hh_df = pd.DataFrame(households)
    persons_df = pd.DataFrame(person_records)

    # 后处理：确保有车家庭至少有一人有驾照
    for idx, hh in hh_df.iterrows():
        autos = int(hh["autos"])
        hid = int(hh["household_id"])
        if autos <= 0:
            continue

        mask = persons_df["household_id"] == hid
        if not mask.any():
            continue

        if persons_df.loc[mask, "license"].sum() == 0:
            adult_mask = mask & (persons_df["age"] >= 18)
            if adult_mask.any():
                candidate_idx = persons_df.loc[adult_mask].sample(
                    1, random_state=rng.randint(0, 1_000_000)
                ).index[0]
            else:
                candidate_idx = persons_df.loc[mask].sample(
                    1, random_state=rng.randint(0, 1_000_000)
                ).index[0]
            persons_df.at[candidate_idx, "license"] = 1

    # 统计信息
    hh_size_actual = persons_df.groupby("household_id").size().rename("hhsize_actual")
    hh_workers = persons_df.groupby("household_id")["is_worker"].sum().rename("workers")
    hh_children = persons_df.groupby("household_id").apply(
        lambda df: (df["age"] < 16).sum()
    ).rename("children")

    hh_df = hh_df.merge(hh_size_actual, on="household_id", how="left")
    hh_df = hh_df.merge(hh_workers, on="household_id", how="left")
    hh_df = hh_df.merge(hh_children, on="household_id", how="left")

    hh_df["hhsize"] = hh_df["hhsize_actual"]
    hh_df.drop(columns=["hhsize_actual"], inplace=True)

    hh_df['workers'] = hh_df['workers'].fillna(0).astype(int)
    hh_df['children'] = hh_df['children'].fillna(0).astype(int)

    return hh_df, persons_df


# ============================================================
#  Tour & Trip 生成模块 - 配置数据结构
# ============================================================

@dataclass
class TourTripConfig:
    """Tour 和 Trip 生成配置"""
    tour_frequency: Dict[str, Dict[int, float]]
    tour_type_dist: Dict[str, Dict[str, float]]
    time_windows: Dict[str, Tuple[int, int]]
    duration_params: Dict[str, Tuple[int, int]]
    max_distance: float
    distance_decay: float
    stop_frequency: Dict[str, Dict[int, float]]


# ============================================================
#  Tour & Trip 生成相关函数
# ============================================================

def get_zone_distance(zone1: int, zone2: int, zone_coords: pd.DataFrame) -> float:
    """计算两个zone之间的欧氏距离（米）"""
    z1 = zone_coords[zone_coords['zone_id'] == zone1]
    z2 = zone_coords[zone_coords['zone_id'] == zone2]

    if z1.empty or z2.empty:
        return 0.0

    z1 = z1.iloc[0]
    z2 = z2.iloc[0]

    dist = np.sqrt(
        (z1['centroid_x'] - z2['centroid_x']) ** 2 +
        (z1['centroid_y'] - z2['centroid_y']) ** 2
    )
    return float(dist)


def choose_destination_zone(
        origin_zone: int,
        zone_coords: pd.DataFrame,
        tour_type: str,
        config: TourTripConfig,
        rng: np.random.RandomState
) -> int:
    """基于距离衰减模型选择目的地zone"""
    origin = zone_coords[zone_coords['zone_id'] == origin_zone]

    if origin.empty:
        return int(zone_coords.iloc[0]['zone_id'])

    origin = origin.iloc[0]
    ox, oy = origin['centroid_x'], origin['centroid_y']

    zone_coords_copy = zone_coords.copy()
    zone_coords_copy['distance'] = np.sqrt(
        (zone_coords_copy['centroid_x'] - ox) ** 2 +
        (zone_coords_copy['centroid_y'] - oy) ** 2
    )

    candidates = zone_coords_copy[
        (zone_coords_copy['distance'] <= config.max_distance) &
        (zone_coords_copy['zone_id'] != origin_zone)
        ].copy()

    if len(candidates) == 0:
        others = zone_coords_copy[zone_coords_copy['zone_id'] != origin_zone]
        if others.empty:
            return int(origin_zone)
        return int(others.nsmallest(1, 'distance')['zone_id'].iloc[0])

    candidates['utility'] = np.exp(-config.distance_decay * candidates['distance'] / 1000.0)

    if tour_type == 'work':
        pass
    elif tour_type == 'school':
        candidates['utility'] = candidates['utility'] ** 2
    elif tour_type in ['shopping', 'dining', 'escort']:
        candidates['utility'] = candidates['utility'] ** 1.5

    probs = candidates['utility'].values
    probs = probs / probs.sum()

    chosen_idx = rng.choice(len(candidates), p=probs)
    return int(candidates.iloc[chosen_idx]['zone_id'])


def choose_destination_zone_with_params(
        origin_zone: int,
        zone_coords: pd.DataFrame,
        tour_type: str,
        max_distance: float,
        distance_decay: float,
        rng: np.random.RandomState
) -> int:
    """带参数的目的地选择函数（用于按区域类型配置）"""
    origin = zone_coords[zone_coords['zone_id'] == origin_zone]

    if origin.empty:
        return int(zone_coords.iloc[0]['zone_id'])

    origin = origin.iloc[0]
    ox, oy = origin['centroid_x'], origin['centroid_y']

    zone_coords_copy = zone_coords.copy()
    zone_coords_copy['distance'] = np.sqrt(
        (zone_coords_copy['centroid_x'] - ox) ** 2 +
        (zone_coords_copy['centroid_y'] - oy) ** 2
    )

    candidates = zone_coords_copy[
        (zone_coords_copy['distance'] <= max_distance) &
        (zone_coords_copy['zone_id'] != origin_zone)
        ].copy()

    if len(candidates) == 0:
        others = zone_coords_copy[zone_coords_copy['zone_id'] != origin_zone]
        if others.empty:
            return int(origin_zone)
        return int(others.nsmallest(1, 'distance')['zone_id'].iloc[0])

    candidates['utility'] = np.exp(-distance_decay * candidates['distance'] / 1000.0)

    if tour_type == 'work':
        pass
    elif tour_type == 'school':
        candidates['utility'] = candidates['utility'] ** 2
    elif tour_type in ['shopping', 'dining', 'escort']:
        candidates['utility'] = candidates['utility'] ** 1.5

    probs = candidates['utility'].values
    probs = probs / probs.sum()

    chosen_idx = rng.choice(len(candidates), p=probs)
    return int(candidates.iloc[chosen_idx]['zone_id'])


def choose_trip_mode(
        origin: int,
        destination: int,
        zone_coords: pd.DataFrame,
        has_license: int,
        hh_autos: int,
        age: int,
        tour_type: str,
        rng: np.random.RandomState
) -> str:
    """简化的mode choice模型"""
    dist = get_zone_distance(origin, destination, zone_coords)

    utilities = {}

    if dist < 1500:
        utilities['walk'] = 2.0 - dist / 500
    else:
        utilities['walk'] = -5.0

    if dist < 5000 and 12 <= age < 70:
        utilities['bike'] = 1.0 - dist / 2000
    else:
        utilities['bike'] = -5.0

    utilities['transit'] = 0.5 - dist / 10000

    if has_license == 1 and hh_autos > 0 and age >= 18:
        utilities['drive_alone'] = 1.5 - dist / 20000
        if tour_type in ['work', 'school']:
            utilities['drive_alone'] += 0.5
    else:
        utilities['drive_alone'] = -10.0

    if hh_autos > 0:
        utilities['shared_ride'] = 0.8 - dist / 15000
        if age < 16:
            utilities['shared_ride'] += 1.0
    else:
        utilities['shared_ride'] = -5.0

    exp_utils = {m: np.exp(min(u, 50)) for m, u in utilities.items()}
    total = sum(exp_utils.values())

    if total == 0:
        return 'walk'

    probs = {m: v / total for m, v in exp_utils.items()}

    modes_list = list(probs.keys())
    probs_list = [probs[m] for m in modes_list]

    chosen_idx = rng.choice(len(modes_list), p=probs_list)
    return modes_list[chosen_idx]


def calculate_trip_time(
        origin: int,
        destination: int,
        zone_coords: pd.DataFrame,
        mode: str
) -> int:
    """根据距离和模式估算出行时间（分钟）"""
    dist = get_zone_distance(origin, destination, zone_coords)

    speeds = {
        'walk': 5,
        'bike': 15,
        'transit': 25,
        'drive_alone': 40,
        'shared_ride': 35,
    }

    speed = speeds.get(mode, 30)
    time_hours = dist / 1000.0 / speed
    time_minutes = int(time_hours * 60)

    if mode == 'transit':
        time_minutes += 10
    elif mode in ['drive_alone', 'shared_ride']:
        time_minutes += 5

    return max(time_minutes, 1)


# ============================================================
#  Tour & Trip 生成函数（统一参数模式）
# ============================================================

def generate_tours_and_trips(
        persons_df: pd.DataFrame,
        households_df: pd.DataFrame,
        zones_gdf: gpd.GeoDataFrame,
        config: TourTripConfig,
        seed: int = 42
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """生成ActivitySim风格的tour和trip数据（统一参数模式）"""

    rng = np.random.RandomState(seed)

    zone_coords = zones_gdf[['zone_id', 'centroid_x', 'centroid_y']].copy()

    tours = []
    trips = []

    tour_id_counter = 1
    trip_id_counter = 1

    persons_full = persons_df.merge(
        households_df[['household_id', 'home_zone_id', 'autos', 'income']],
        on='household_id',
        how='left'
    )

    for _, person in persons_full.iterrows():
        person_id = int(person['person_id'])
        person_type = person['person_type']
        home_zone = int(person['home_zone_id'])
        has_license = int(person['license'])
        hh_autos = int(person['autos'])
        age = int(person['age'])
        is_worker = int(person['is_worker'])
        is_student = int(person['is_student'])

        freq_dist = config.tour_frequency.get(person_type, {0: 1.0})
        num_tours = int(_sample_from_distribution(freq_dist, rng))

        if num_tours == 0:
            continue

        for t in range(num_tours):
            type_dist = config.tour_type_dist.get(person_type, {'other': 1.0})

            if t == 0:
                if is_worker == 1:
                    tour_type = 'work'
                elif is_student == 1:
                    tour_type = 'school'
                else:
                    tour_type = _sample_from_distribution(type_dist, rng)
            else:
                non_mand = {k: v for k, v in type_dist.items()
                            if k not in ['work', 'school']}
                if not non_mand:
                    non_mand = {'shopping': 0.4, 'social': 0.3, 'other': 0.3}
                tour_type = _sample_from_distribution(non_mand, rng)

            dest_zone = choose_destination_zone(
                home_zone, zone_coords, tour_type, config, rng
            )

            time_window = config.time_windows.get(tour_type, (360, 1200))
            duration_range = config.duration_params.get(tour_type, (60, 480))

            start_time = int(rng.randint(time_window[0], time_window[1]))
            duration = int(rng.randint(duration_range[0], duration_range[1]))
            end_time = start_time + duration

            stop_dist = config.stop_frequency.get(tour_type, {0: 0.7, 1: 0.25, 2: 0.05})
            num_stops = int(_sample_from_distribution(stop_dist, rng))

            tours.append({
                'tour_id': tour_id_counter,
                'person_id': person_id,
                'household_id': int(person['household_id']),
                'tour_type': tour_type,
                'tour_category': 'mandatory' if tour_type in ['work', 'school'] else 'non_mandatory',
                'origin_zone_id': home_zone,
                'destination_zone_id': dest_zone,
                'start_time': start_time,
                'end_time': end_time,
                'duration': duration,
                'num_stops': num_stops,
            })

            stops = []
            if num_stops > 0:
                all_zones = zone_coords['zone_id'].values
                available = [z for z in all_zones if z not in [home_zone, dest_zone]]
                if len(available) >= num_stops:
                    stops = rng.choice(available, size=num_stops, replace=False).tolist()
                elif len(available) > 0:
                    stops = rng.choice(available, size=num_stops, replace=True).tolist()

            num_stops_out = num_stops // 2
            num_stops_in = num_stops - num_stops_out

            stops_out = stops[:num_stops_out]
            stops_in = stops[num_stops_out:]

            outbound_seq = [home_zone] + stops_out + [dest_zone]

            current_time = start_time
            trip_num = 1

            for i in range(len(outbound_seq) - 1):
                orig = int(outbound_seq[i])
                dest = int(outbound_seq[i + 1])

                purpose = tour_type if i == len(outbound_seq) - 2 else _sample_from_distribution(
                    {'shopping': 0.4, 'dining': 0.3, 'other': 0.3}, rng
                )

                mode = choose_trip_mode(
                    orig, dest, zone_coords, has_license, hh_autos, age, tour_type, rng
                )

                travel_time = calculate_trip_time(orig, dest, zone_coords, mode)

                trips.append({
                    'trip_id': trip_id_counter,
                    'tour_id': tour_id_counter,
                    'person_id': person_id,
                    'household_id': int(person['household_id']),
                    'trip_num': trip_num,
                    'outbound': True,
                    'origin_zone_id': orig,
                    'destination_zone_id': dest,
                    'purpose': purpose,
                    'departure_time': current_time,
                    'arrival_time': current_time + travel_time,
                    'travel_time': travel_time,
                    'mode': mode,
                })

                current_time += travel_time + 15
                trip_id_counter += 1
                trip_num += 1

            inbound_seq = [dest_zone] + stops_in + [home_zone]
            current_time = end_time - (duration // 2)

            for i in range(len(inbound_seq) - 1):
                orig = int(inbound_seq[i])
                dest = int(inbound_seq[i + 1])

                purpose = 'home' if i == len(inbound_seq) - 2 else _sample_from_distribution(
                    {'shopping': 0.4, 'dining': 0.3, 'other': 0.3}, rng
                )

                mode = choose_trip_mode(
                    orig, dest, zone_coords, has_license, hh_autos, age, tour_type, rng
                )

                travel_time = calculate_trip_time(orig, dest, zone_coords, mode)

                trips.append({
                    'trip_id': trip_id_counter,
                    'tour_id': tour_id_counter,
                    'person_id': person_id,
                    'household_id': int(person['household_id']),
                    'trip_num': trip_num,
                    'outbound': False,
                    'origin_zone_id': orig,
                    'destination_zone_id': dest,
                    'purpose': purpose,
                    'departure_time': current_time,
                    'arrival_time': current_time + travel_time,
                    'travel_time': travel_time,
                    'mode': mode,
                })

                current_time += travel_time + 15
                trip_id_counter += 1
                trip_num += 1

            tour_id_counter += 1

    tours_df = pd.DataFrame(tours)
    trips_df = pd.DataFrame(trips)

    return tours_df, trips_df


# ============================================================
#  按区域类型生成Tour/Trip的函数
# ============================================================

def generate_tours_and_trips_by_area_type(
        persons_df: pd.DataFrame,
        households_df: pd.DataFrame,
        zones_gdf: gpd.GeoDataFrame,
        area_type_configs: Dict[str, AreaTypeConfig],
        seed: int = 42
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """按area_type使用不同配置生成tour和trip"""
    rng = np.random.RandomState(seed)

    zone_coords = zones_gdf[['zone_id', 'centroid_x', 'centroid_y']].copy()

    tours = []
    trips = []

    tour_id_counter = 1
    trip_id_counter = 1

    persons_full = persons_df.merge(
        households_df[['household_id', 'home_zone_id', 'autos', 'income', 'area_type']],
        on='household_id',
        how='left'
    )

    for _, person in persons_full.iterrows():
        person_id = int(person['person_id'])
        person_type = person['person_type']
        home_zone = int(person['home_zone_id'])
        has_license = int(person['license'])
        hh_autos = int(person['autos'])
        age = int(person['age'])
        is_worker = int(person['is_worker'])
        is_student = int(person['is_student'])
        area_type = person['area_type']

        # 获取该area_type的配置
        if area_type not in area_type_configs:
            continue

        config = area_type_configs[area_type]

        # 使用该area_type的tour频率
        freq_dist = config.tour_frequency.get(person_type, {0: 1.0})
        num_tours = int(_sample_from_distribution(freq_dist, rng))

        if num_tours == 0:
            continue

        for t in range(num_tours):
            type_dist = config.tour_type_dist

            if t == 0:
                if is_worker == 1:
                    tour_type = 'work'
                elif is_student == 1:
                    tour_type = 'school'
                else:
                    tour_type = _sample_from_distribution(type_dist, rng)
            else:
                non_mand = {k: v for k, v in type_dist.items()
                            if k not in ['work', 'school']}
                if not non_mand:
                    non_mand = {'shopping': 0.4, 'social': 0.3, 'other': 0.3}
                tour_type = _sample_from_distribution(non_mand, rng)

            # 使用该area_type的距离参数
            dest_zone = choose_destination_zone_with_params(
                home_zone, zone_coords, tour_type,
                config.max_distance, config.distance_decay, rng
            )

            # 使用该area_type的时间参数
            time_window = config.time_windows.get(tour_type, (360, 1200))
            duration_range = config.duration_params.get(tour_type, (60, 480))

            start_time = int(rng.randint(time_window[0], time_window[1]))
            duration = int(rng.randint(duration_range[0], duration_range[1]))
            end_time = start_time + duration

            stop_dist = config.stop_frequency.get(tour_type, {0: 0.7, 1: 0.25, 2: 0.05})
            num_stops = int(_sample_from_distribution(stop_dist, rng))

            tours.append({
                'tour_id': tour_id_counter,
                'person_id': person_id,
                'household_id': int(person['household_id']),
                'tour_type': tour_type,
                'tour_category': 'mandatory' if tour_type in ['work', 'school'] else 'non_mandatory',
                'origin_zone_id': home_zone,
                'destination_zone_id': dest_zone,
                'start_time': start_time,
                'end_time': end_time,
                'duration': duration,
                'num_stops': num_stops,
                'area_type': area_type,
            })

            # 生成trips
            stops = []
            if num_stops > 0:
                all_zones = zone_coords['zone_id'].values
                available = [z for z in all_zones if z not in [home_zone, dest_zone]]
                if len(available) >= num_stops:
                    stops = rng.choice(available, size=num_stops, replace=False).tolist()
                elif len(available) > 0:
                    stops = rng.choice(available, size=num_stops, replace=True).tolist()

            num_stops_out = num_stops // 2
            num_stops_in = num_stops - num_stops_out

            stops_out = stops[:num_stops_out]
            stops_in = stops[num_stops_out:]

            outbound_seq = [home_zone] + stops_out + [dest_zone]

            current_time = start_time
            trip_num = 1

            for i in range(len(outbound_seq) - 1):
                orig = int(outbound_seq[i])
                dest = int(outbound_seq[i + 1])

                purpose = tour_type if i == len(outbound_seq) - 2 else _sample_from_distribution(
                    {'shopping': 0.4, 'dining': 0.3, 'other': 0.3}, rng
                )

                mode = choose_trip_mode(
                    orig, dest, zone_coords, has_license, hh_autos, age, tour_type, rng
                )

                travel_time = calculate_trip_time(orig, dest, zone_coords, mode)

                trips.append({
                    'trip_id': trip_id_counter,
                    'tour_id': tour_id_counter,
                    'person_id': person_id,
                    'household_id': int(person['household_id']),
                    'trip_num': trip_num,
                    'outbound': True,
                    'origin_zone_id': orig,
                    'destination_zone_id': dest,
                    'purpose': purpose,
                    'departure_time': current_time,
                    'arrival_time': current_time + travel_time,
                    'travel_time': travel_time,
                    'mode': mode,
                })

                current_time += travel_time + 15
                trip_id_counter += 1
                trip_num += 1

            inbound_seq = [dest_zone] + stops_in + [home_zone]
            current_time = end_time - (duration // 2)

            for i in range(len(inbound_seq) - 1):
                orig = int(inbound_seq[i])
                dest = int(inbound_seq[i + 1])

                purpose = 'home' if i == len(inbound_seq) - 2 else _sample_from_distribution(
                    {'shopping': 0.4, 'dining': 0.3, 'other': 0.3}, rng
                )

                mode = choose_trip_mode(
                    orig, dest, zone_coords, has_license, hh_autos, age, tour_type, rng
                )

                travel_time = calculate_trip_time(orig, dest, zone_coords, mode)

                trips.append({
                    'trip_id': trip_id_counter,
                    'tour_id': tour_id_counter,
                    'person_id': person_id,
                    'household_id': int(person['household_id']),
                    'trip_num': trip_num,
                    'outbound': False,
                    'origin_zone_id': orig,
                    'destination_zone_id': dest,
                    'purpose': purpose,
                    'departure_time': current_time,
                    'arrival_time': current_time + travel_time,
                    'travel_time': travel_time,
                    'mode': mode,
                })

                current_time += travel_time + 15
                trip_id_counter += 1
                trip_num += 1

            tour_id_counter += 1

    tours_df = pd.DataFrame(tours)
    trips_df = pd.DataFrame(trips)

    return tours_df, trips_df


# ============================================================
#  获取默认配置参数的辅助函数
# ============================================================

def get_default_population_params() -> Dict:
    """获取默认的人口配置参数"""
    return {
        'hhsize_dist': {"1": 0.30, "2": 0.40, "3": 0.20, "4": 0.10, "5+": 0.00},
        'income_segment_weights': {"low": 0.3, "mid": 0.5, "high": 0.2},
        'autos_by_income_and_hhsize': {
            "low": {"1": [0.8, 0.2, 0.0], "2": [0.6, 0.4, 0.0], "3+": [0.4, 0.4, 0.2]},
            "mid": {"1": [0.5, 0.5, 0.0], "2": [0.3, 0.6, 0.1], "3+": [0.2, 0.5, 0.3]},
            "high": {"1": [0.3, 0.4, 0.3], "2": [0.2, 0.4, 0.4], "3+": [0.1, 0.4, 0.5]}
        },
        'age_shares': {"0-5": 0.05, "6-17": 0.15, "18-22": 0.10, "23-64": 0.55, "65+": 0.15},
        'worker_rate_by_age': {"16-17": 0.05, "18-22": 0.30, "23-59": 0.80, "60-64": 0.40, "65+": 0.10},
        'student_rate_by_age': {"6-17": 0.95, "18-22": 0.70},
        'license_rate_by_age': {"18-22": 0.50, "23-59": 0.90, "60-69": 0.70, "70+": 0.40}
    }


def get_default_tour_params() -> Dict:
    """获取默认的Tour配置参数"""
    return {
        'tour_frequency': {
            'full_time_worker': {0: 0.05, 1: 0.60, 2: 0.30, 3: 0.05},
            'university_student': {0: 0.10, 1: 0.70, 2: 0.20},
            'non_worker': {0: 0.30, 1: 0.50, 2: 0.20},
            'child': {0: 0.20, 1: 0.70, 2: 0.10},
            'worker_other': {0: 0.15, 1: 0.60, 2: 0.25}
        },
        'tour_type_dist': {
            'shopping': 0.30, 'social': 0.25, 'dining': 0.20, 'escort': 0.15, 'other': 0.10
        },
        'time_windows': {
            'work': (420, 540), 'school': (390, 480), 'shopping': (540, 1140),
            'social': (600, 1200), 'dining': (660, 1260), 'escort': (420, 540), 'other': (480, 1200),
        },
        'duration_params': {
            'work': (420, 600), 'school': (360, 480), 'shopping': (60, 180),
            'social': (90, 240), 'dining': (60, 150), 'escort': (30, 60), 'other': (60, 240),
        },
        'stop_frequency': {
            'work': {0: 0.80, 1: 0.15, 2: 0.05}, 'school': {0: 0.85, 1: 0.12, 2: 0.03},
            'shopping': {0: 0.70, 1: 0.25, 2: 0.05}, 'social': {0: 0.70, 1: 0.25, 2: 0.05},
            'dining': {0: 0.90, 1: 0.08, 2: 0.02}, 'escort': {0: 0.70, 1: 0.25, 2: 0.05},
            'other': {0: 0.70, 1: 0.25, 2: 0.05},
        },
        'max_distance': 30000.0,
        'distance_decay': 0.1
    }


# ============================================================
#  时间选择器组件
# ============================================================

def time_input_hms(label: str, default_minutes: int, key: str = None) -> int:
    """HH:MM:SS 格式的时间输入组件，返回分钟数"""

    default_time = minutes_to_time_string(default_minutes)

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        time_str = st.text_input(
            label,
            value=default_time,
            key=key,
            help="格式: HH:MM:SS"
        )

    try:
        minutes = time_string_to_minutes(time_str)

        with col2:
            st.metric("小时", minutes // 60)
        with col3:
            st.metric("分钟", minutes % 60)

        return minutes
    except:
        st.error(f"时间格式错误: {time_str}")
        return default_minutes
# ============================================================
#  MATSim Population XML 生成
# ============================================================

def map_mode_to_matsim(mode: str) -> str:
    """将我们的 mode 映射到 MATSim mode"""
    mode_mapping = {
        'drive_alone': 'car',
        'shared_ride': 'car',
        'walk': 'walk',
        'bike': 'bike',
        'transit': 'pt',
    }
    return mode_mapping.get(mode, 'car')


def map_purpose_to_activity_type(purpose: str) -> str:
    """将出行目的映射到活动类型"""
    activity_mapping = {
        'work': 'work',
        'school': 'education',
        'shopping': 'shopping',
        'social': 'leisure',
        'dining': 'leisure',
        'escort': 'escort',
        'other': 'other',
        'home': 'home',
    }
    return activity_mapping.get(purpose, 'other')


def generate_matsim_population_xml(
        persons_df: pd.DataFrame,
        households_df: pd.DataFrame,
        tours_df: pd.DataFrame,
        trips_df: pd.DataFrame,
        zones_gdf: gpd.GeoDataFrame
) -> str:
    """生成符合 MATSim population_v6.dtd 的 XML 字符串"""
    from xml.etree.ElementTree import Element, SubElement, tostring
    from xml.dom import minidom

    zone_coords = {}
    for _, zone in zones_gdf.iterrows():
        zone_coords[zone['zone_id']] = (zone['centroid_x'], zone['centroid_y'])

    persons_full = persons_df.merge(
        households_df[['household_id', 'home_zone_id', 'autos']],
        on='household_id',
        how='left'
    )

    population = Element('population')

    for person_id in sorted(persons_full['person_id'].unique()):
        person_data = persons_full[persons_full['person_id'] == person_id].iloc[0]
        person_elem = SubElement(population, 'person', id=str(person_id))

        person_attrs = SubElement(person_elem, 'attributes')

        age_attr = SubElement(person_attrs, 'attribute', name='age', **{'class': 'java.lang.Integer'})
        age_attr.text = str(int(person_data['age']))

        sex_attr = SubElement(person_attrs, 'attribute', name='sex', **{'class': 'java.lang.String'})
        sex_attr.text = str(person_data['sex'])

        license_attr = SubElement(person_attrs, 'attribute', name='hasLicense', **{'class': 'java.lang.Boolean'})
        license_attr.text = 'true' if int(person_data['license']) == 1 else 'false'

        car_avail_attr = SubElement(person_attrs, 'attribute', name='carAvail', **{'class': 'java.lang.String'})
        autos = int(person_data['autos'])
        if autos == 0:
            car_avail_attr.text = 'never'
        elif autos >= 2 or (autos == 1 and int(person_data['license']) == 1):
            car_avail_attr.text = 'always'
        else:
            car_avail_attr.text = 'sometimes'

        employed_attr = SubElement(person_attrs, 'attribute', name='employed', **{'class': 'java.lang.Boolean'})
        employed_attr.text = 'true' if int(person_data['is_worker']) == 1 else 'false'

        person_tours = tours_df[tours_df['person_id'] == person_id].sort_values('start_time')

        if len(person_tours) == 0:
            plan = SubElement(person_elem, 'plan', selected='yes')
            home_zone = int(person_data['home_zone_id'])
            home_x, home_y = zone_coords.get(home_zone, (0.0, 0.0))
            activity = SubElement(plan, 'activity', type='home', x=f'{home_x:.2f}', y=f'{home_y:.2f}')
            continue

        plan = SubElement(person_elem, 'plan', selected='yes')
        home_zone = int(person_data['home_zone_id'])
        home_x, home_y = zone_coords.get(home_zone, (0.0, 0.0))

        first_tour = person_tours.iloc[0]
        first_activity = SubElement(
            plan, 'activity',
            type='home',
            x=f'{home_x:.2f}',
            y=f'{home_y:.2f}',
            end_time=minutes_to_time_string(int(first_tour['start_time']))
        )

        for tour_idx, (_, tour) in enumerate(person_tours.iterrows()):
            tour_id = tour['tour_id']
            tour_trips = trips_df[trips_df['tour_id'] == tour_id].sort_values('trip_num')

            if len(tour_trips) == 0:
                continue

            for trip_idx, (_, trip) in enumerate(tour_trips.iterrows()):
                mode = map_mode_to_matsim(trip['mode'])
                leg = SubElement(
                    plan, 'leg',
                    mode=mode,
                    dep_time=minutes_to_time_string(int(trip['departure_time'])),
                    trav_time=minutes_to_time_string(int(trip['travel_time']))
                )

                dest_zone = int(trip['destination_zone_id'])
                dest_x, dest_y = zone_coords.get(dest_zone, (0.0, 0.0))
                activity_type = map_purpose_to_activity_type(trip['purpose'])

                is_last_trip_in_tour = (trip_idx == len(tour_trips) - 1)
                is_last_tour = (tour_idx == len(person_tours) - 1)

                if is_last_trip_in_tour and is_last_tour:
                    activity = SubElement(
                        plan, 'activity',
                        type='home',
                        x=f'{home_x:.2f}',
                        y=f'{home_y:.2f}'
                    )
                elif is_last_trip_in_tour:
                    next_tour = person_tours.iloc[tour_idx + 1]
                    activity = SubElement(
                        plan, 'activity',
                        type='home',
                        x=f'{home_x:.2f}',
                        y=f'{home_y:.2f}',
                        end_time=minutes_to_time_string(int(next_tour['start_time']))
                    )
                else:
                    activity = SubElement(
                        plan, 'activity',
                        type=activity_type,
                        x=f'{dest_x:.2f}',
                        y=f'{dest_y:.2f}',
                        max_dur='00:15:00'
                    )

    rough_string = tostring(population, encoding='utf-8')
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent='  ', encoding='utf-8')

    lines = [line for line in pretty_xml.decode('utf-8').split('\n') if line.strip()]
    lines.insert(1, '<!DOCTYPE population SYSTEM "http://www.matsim.org/files/dtd/population_v6.dtd">')

    return '\n'.join(lines)


# ============================================================
#  DTD 验证功能
# ============================================================

DTD_CONTENT = '''<?xml version="1.0" encoding="utf-8"?>

<!ELEMENT population     (attributes?,person*)>
<!ATTLIST population
          desc           CDATA   #IMPLIED>

<!ELEMENT person         (attributes?,plan*)>
<!ATTLIST person
          id             CDATA                    #REQUIRED>

<!ELEMENT attributes    (attribute*)>

<!ELEMENT attribute       (#PCDATA)>
<!ATTLIST attribute
          name        CDATA #REQUIRED
          class       CDATA #REQUIRED>

<!ELEMENT plan          (attributes?, (activity|leg)* )>
<!ATTLIST plan
          score          CDATA    #IMPLIED
          type           CDATA    #IMPLIED
          selected       (yes|no) "no">

<!ELEMENT activity            (attributes?)>
<!ATTLIST activity
          type           CDATA #REQUIRED
          x              CDATA #IMPLIED
          y              CDATA #IMPLIED
          z              CDATA #IMPLIED
          link           CDATA #IMPLIED
          facility       CDATA #IMPLIED
          start_time     CDATA #IMPLIED
          end_time       CDATA #IMPLIED
          max_dur        CDATA #IMPLIED>

<!ELEMENT leg            (attributes?,route?)>
<!ATTLIST leg
          mode           CDATA                                                 #REQUIRED
          dep_time       CDATA                                                 #IMPLIED
          trav_time      CDATA                                                 #IMPLIED>

<!ELEMENT route          (#PCDATA)>
<!ATTLIST route
          type           CDATA #IMPLIED
          start_link	 CDATA #IMPLIED
          end_link       CDATA #IMPLIED
          trav_time		 CDATA #IMPLIED
          distance		 CDATA #IMPLIED
          vehicleRefId           CDATA #IMPLIED
          >
'''


def validate_matsim_xml_against_dtd(xml_string: str) -> Tuple[bool, List[str]]:
    """验证 MATSim XML 是否符合 population_v6.dtd"""
    from lxml import etree
    from io import StringIO

    errors = []

    try:
        dtd = etree.DTD(StringIO(DTD_CONTENT))
        parser = etree.XMLParser(dtd_validation=False)
        xml_doc = etree.fromstring(xml_string.encode('utf-8'), parser)
        is_valid = dtd.validate(xml_doc)

        if not is_valid:
            for error in dtd.error_log:
                errors.append(f"行 {error.line}: {error.message}")

        return is_valid, errors

    except Exception as e:
        return False, [f"验证过程出错: {str(e)}"]


def validate_matsim_population(
        persons_df: pd.DataFrame,
        tours_df: pd.DataFrame,
        trips_df: pd.DataFrame
) -> Dict[str, any]:
    """验证数据的完整性和一致性"""
    issues = []
    stats = {}

    stats['total_persons'] = len(persons_df)
    stats['persons_with_tours'] = tours_df['person_id'].nunique() if not tours_df.empty else 0
    stats['persons_without_tours'] = stats['total_persons'] - stats['persons_with_tours']
    stats['total_tours'] = len(tours_df)
    stats['total_trips'] = len(trips_df)

    if tours_df.empty:
        issues.append("没有生成任何 tours")
        return {'valid': False, 'issues': issues, 'stats': stats}

    if not trips_df.empty:
        tours_with_trips = trips_df['tour_id'].unique()
        all_tours = tours_df['tour_id'].unique()
        tours_without_trips = set(all_tours) - set(tours_with_trips)

        if len(tours_without_trips) > 0:
            issues.append(f"发现 {len(tours_without_trips)} 个没有 trips 的 tours")
            stats['tours_without_trips'] = len(tours_without_trips)
        else:
            stats['tours_without_trips'] = 0

        for tour_id in tours_df['tour_id'].unique():
            tour_trips = trips_df[trips_df['tour_id'] == tour_id].sort_values('trip_num')
            if len(tour_trips) == 0:
                continue

            expected_nums = list(range(1, len(tour_trips) + 1))
            actual_nums = tour_trips['trip_num'].tolist()
            if actual_nums != expected_nums:
                issues.append(f"Tour {tour_id} 的 trip_num 不连续: {actual_nums}")

        time_issues = 0
        for _, trip in trips_df.iterrows():
            dep = int(trip['departure_time'])
            arr = int(trip['arrival_time'])
            if arr < dep:
                time_issues += 1

        if time_issues > 0:
            issues.append(f"发现 {time_issues} 个时间逻辑错误的 trips")
            stats['time_issues'] = time_issues
        else:
            stats['time_issues'] = 0

    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'stats': stats
    }


def generate_sample_matsim_config(zones_gdf: gpd.GeoDataFrame) -> str:
    """生成一个示例的 MATSim config.xml"""
    bounds = zones_gdf.total_bounds
    minx, miny, maxx, maxy = bounds

    config = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE config SYSTEM "http://www.matsim.org/files/dtd/config_v2.dtd">
<config>
    <module name="network">
        <param name="inputNetworkFile" value="network.xml"/>
    </module>
    <module name="plans">
        <param name="inputPlansFile" value="population.xml"/>
    </module>
    <module name="controler">
        <param name="outputDirectory" value="./output"/>
        <param name="firstIteration" value="0"/>
        <param name="lastIteration" value="100"/>
        <param name="mobsim" value="qsim"/>
    </module>
    <module name="qsim">
        <param name="startTime" value="00:00:00"/>
        <param name="endTime" value="30:00:00"/>
    </module>
    <module name="global">
        <param name="coordinateSystem" value="{zones_gdf.crs.to_string()}"/>
    </module>
</config>
"""
    return config


# ============================================================
#  可视化图表生成功能（完整版，15个图表）
# ============================================================

def create_visualization_charts(
        hh_df: pd.DataFrame,
        persons_df: pd.DataFrame,
        tours_df: pd.DataFrame = None,
        trips_df: pd.DataFrame = None
):
    """创建所有可视化图表"""

    # 强制重新设置字体
    setup_chinese_font()

    figures = {}

    # 创建中文字体属性对象
    from matplotlib.font_manager import FontProperties
    chinese_font = FontProperties(family=['Microsoft YaHei', 'SimHei', 'SimSun'])

    # 1. 家庭规模分布
    fig1, ax1 = plt.subplots(figsize=(12, 7))
    hhsize_counts = hh_df['hhsize'].value_counts().sort_index()
    bars = ax1.bar(hhsize_counts.index, hhsize_counts.values, color='steelblue', edgecolor='black', linewidth=1.5)
    ax1.set_xlabel('家庭规模（人）', fontsize=16, fontweight='bold')
    ax1.set_ylabel('家庭数量', fontsize=16, fontweight='bold')
    ax1.set_title('家庭规模分布', fontsize=18, fontweight='bold', pad=20)
    ax1.grid(axis='y', alpha=0.3, linestyle='--')
    ax1.tick_params(labelsize=13)

    for bar in bars:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width() / 2., height,
                 f'{int(height)}',
                 ha='center', va='bottom', fontsize=12, fontweight='bold')
    plt.tight_layout()
    figures['household_size'] = fig1

    # 2. 收入分布
    fig2, ax2 = plt.subplots(figsize=(12, 7))
    income_counts = hh_df['income_segment'].value_counts()
    colors = {'low': '#e74c3c', 'mid': '#3498db', 'high': '#2ecc71'}
    income_labels = {'low': '低收入', 'mid': '中收入', 'high': '高收入'}

    sorted_segments = ['low', 'mid', 'high']
    sorted_counts = [income_counts.get(seg, 0) for seg in sorted_segments]
    sorted_labels = [income_labels[seg] for seg in sorted_segments]
    sorted_colors = [colors[seg] for seg in sorted_segments]

    bars = ax2.bar(range(len(sorted_segments)), sorted_counts,
                   color=sorted_colors, edgecolor='black', linewidth=1.5)
    ax2.set_xticks(range(len(sorted_segments)))
    ax2.set_xticklabels(sorted_labels, fontsize=14)
    ax2.set_ylabel('家庭数量', fontsize=16, fontweight='bold')
    ax2.set_title('家庭收入分段分布', fontsize=18, fontweight='bold', pad=20)
    ax2.grid(axis='y', alpha=0.3, linestyle='--')
    ax2.tick_params(labelsize=13)

    for bar in bars:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width() / 2., height,
                 f'{int(height)}',
                 ha='center', va='bottom', fontsize=12, fontweight='bold')
    plt.tight_layout()
    figures['income_distribution'] = fig2

    # 3. 汽车拥有量分布
    fig3, ax3 = plt.subplots(figsize=(12, 7))
    auto_counts = hh_df['autos'].value_counts().sort_index()
    bars = ax3.bar(auto_counts.index, auto_counts.values, color='orange', edgecolor='black', linewidth=1.5)
    ax3.set_xlabel('汽车数量', fontsize=16, fontweight='bold')
    ax3.set_ylabel('家庭数量', fontsize=16, fontweight='bold')
    ax3.set_title('家庭汽车拥有量分布', fontsize=18, fontweight='bold', pad=20)
    ax3.grid(axis='y', alpha=0.3, linestyle='--')
    ax3.tick_params(labelsize=13)

    for bar in bars:
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width() / 2., height,
                 f'{int(height)}',
                 ha='center', va='bottom', fontsize=12, fontweight='bold')
    plt.tight_layout()
    figures['auto_ownership'] = fig3

    # 4. 年龄分布
    fig4, ax4 = plt.subplots(figsize=(14, 7))
    n, bins, patches = ax4.hist(persons_df['age'], bins=20, color='mediumpurple',
                                edgecolor='black', alpha=0.7, linewidth=1.5)
    ax4.set_xlabel('年龄', fontsize=16, fontweight='bold')
    ax4.set_ylabel('人数', fontsize=16, fontweight='bold')
    ax4.set_title('人口年龄分布', fontsize=18, fontweight='bold', pad=20)
    ax4.grid(axis='y', alpha=0.3, linestyle='--')
    ax4.tick_params(labelsize=13)

    mean_age = persons_df['age'].mean()
    median_age = persons_df['age'].median()
    ax4.axvline(mean_age, color='red', linestyle='--', linewidth=2.5,
                label=f'平均年龄: {mean_age:.1f}岁')
    ax4.axvline(median_age, color='green', linestyle='--', linewidth=2.5,
                label=f'中位数: {median_age:.1f}岁')
    ax4.legend(fontsize=13, loc='upper right', prop=chinese_font)
    plt.tight_layout()
    figures['age_distribution'] = fig4

    # 5. 性别分布
    fig5, ax5 = plt.subplots(figsize=(10, 10))
    sex_counts = persons_df['sex'].value_counts()
    sex_labels = {'M': '男性', 'F': '女性'}
    labels = [sex_labels.get(x, x) for x in sex_counts.index]
    colors_sex = ['#3498db', '#e74c3c']

    wedges, texts, autotexts = ax5.pie(sex_counts.values, labels=labels, autopct='%1.1f%%',
                                       colors=colors_sex, startangle=90,
                                       textprops={'fontsize': 16, 'fontweight': 'bold'})
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontsize(16)
        autotext.set_fontweight('bold')
    ax5.set_title('性别分布', fontsize=18, fontweight='bold', pad=20)
    plt.tight_layout()
    figures['sex_distribution'] = fig5

    # 6. 人员类型分布
    fig6, ax6 = plt.subplots(figsize=(14, 8))
    person_type_counts = persons_df['person_type'].value_counts()
    type_labels = {
        'child': '儿童',
        'university_student': '大学生',
        'full_time_worker': '全职工作者',
        'worker_other': '其他工作者',
        'non_worker': '非工作者'
    }

    labels = [type_labels.get(x, x) for x in person_type_counts.index]
    bars = ax6.barh(range(len(person_type_counts)), person_type_counts.values,
                    color='teal', edgecolor='black', linewidth=1.5)
    ax6.set_yticks(range(len(person_type_counts)))
    ax6.set_yticklabels(labels, fontsize=14)
    ax6.set_xlabel('人数', fontsize=16, fontweight='bold')
    ax6.set_title('人员类型分布', fontsize=18, fontweight='bold', pad=20)
    ax6.grid(axis='x', alpha=0.3, linestyle='--')
    ax6.tick_params(labelsize=13)

    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax6.text(width, bar.get_y() + bar.get_height() / 2.,
                 f'{int(width)}',
                 ha='left', va='center', fontsize=12, fontweight='bold')
    plt.tight_layout()
    figures['person_type'] = fig6

    # 7. 就业和在学情况
    fig7, (ax7_1, ax7_2) = plt.subplots(1, 2, figsize=(16, 8))

    worker_counts = persons_df['is_worker'].value_counts()
    worker_labels = {0: '非就业', 1: '就业'}
    labels_worker = [worker_labels.get(x, str(x)) for x in sorted(worker_counts.index)]
    values_worker = [worker_counts.get(x, 0) for x in sorted(worker_counts.index)]

    wedges1, texts1, autotexts1 = ax7_1.pie(values_worker, labels=labels_worker, autopct='%1.1f%%',
                                            colors=['#95a5a6', '#27ae60'], startangle=90,
                                            textprops={'fontsize': 14, 'fontweight': 'bold'})
    for autotext in autotexts1:
        autotext.set_color('white')
        autotext.set_fontsize(14)
    ax7_1.set_title('就业情况', fontsize=16, fontweight='bold', pad=15)

    student_counts = persons_df['is_student'].value_counts()
    student_labels = {0: '非在学', 1: '在学'}
    labels_student = [student_labels.get(x, str(x)) for x in sorted(student_counts.index)]
    values_student = [student_counts.get(x, 0) for x in sorted(student_counts.index)]

    wedges2, texts2, autotexts2 = ax7_2.pie(values_student, labels=labels_student, autopct='%1.1f%%',
                                            colors=['#95a5a6', '#3498db'], startangle=90,
                                            textprops={'fontsize': 14, 'fontweight': 'bold'})
    for autotext in autotexts2:
        autotext.set_color('white')
        autotext.set_fontsize(14)
    ax7_2.set_title('在学情况', fontsize=16, fontweight='bold', pad=15)

    plt.tight_layout()
    figures['employment_education'] = fig7

    # 8. 驾照持有情况
    fig8, ax8 = plt.subplots(figsize=(12, 7))
    license_counts = persons_df['license'].value_counts()
    license_labels = {0: '无驾照', 1: '有驾照'}
    sorted_license = [0, 1]
    labels_license = [license_labels[x] for x in sorted_license]
    values_license = [license_counts.get(x, 0) for x in sorted_license]
    colors_license = ['#e74c3c', '#2ecc71']

    bars = ax8.bar(range(len(sorted_license)), values_license,
                   color=colors_license, edgecolor='black', linewidth=1.5)
    ax8.set_xticks(range(len(sorted_license)))
    ax8.set_xticklabels(labels_license, fontsize=14)
    ax8.set_ylabel('人数', fontsize=16, fontweight='bold')
    ax8.set_title('驾照持有情况', fontsize=18, fontweight='bold', pad=20)
    ax8.grid(axis='y', alpha=0.3, linestyle='--')
    ax8.tick_params(labelsize=13)

    for bar in bars:
        height = bar.get_height()
        ax8.text(bar.get_x() + bar.get_width() / 2., height,
                 f'{int(height)}',
                 ha='center', va='bottom', fontsize=12, fontweight='bold')
    plt.tight_layout()
    figures['license'] = fig8

    # 如果有 tours 和 trips 数据，生成出行相关图表
    if tours_df is not None and not tours_df.empty:
        # 9. Tour类型分布
        fig9, ax9 = plt.subplots(figsize=(14, 8))
        tour_type_counts = tours_df['tour_type'].value_counts()
        tour_type_labels = {
            'work': '工作',
            'school': '上学',
            'shopping': '购物',
            'social': '社交',
            'dining': '餐饮',
            'escort': '接送',
            'other': '其他'
        }

        labels_tour = [tour_type_labels.get(x, x) for x in tour_type_counts.index]
        colors_tour = plt.cm.Set3(range(len(tour_type_counts)))

        bars = ax9.barh(range(len(tour_type_counts)), tour_type_counts.values,
                        color=colors_tour, edgecolor='black', linewidth=1.5)
        ax9.set_yticks(range(len(tour_type_counts)))
        ax9.set_yticklabels(labels_tour, fontsize=14)
        ax9.set_xlabel('Tour数量', fontsize=16, fontweight='bold')
        ax9.set_title('Tour类型分布', fontsize=18, fontweight='bold', pad=20)
        ax9.grid(axis='x', alpha=0.3, linestyle='--')
        ax9.tick_params(labelsize=13)

        for i, bar in enumerate(bars):
            width = bar.get_width()
            ax9.text(width, bar.get_y() + bar.get_height() / 2.,
                     f'{int(width)}',
                     ha='left', va='center', fontsize=12, fontweight='bold')
        plt.tight_layout()
        figures['tour_types'] = fig9

        # 10. Tour开始和结束时间分布
        fig10, (ax10_1, ax10_2) = plt.subplots(2, 1, figsize=(16, 12))

        start_hours = tours_df['start_time'].apply(lambda x: x / 60.0)
        ax10_1.hist(start_hours, bins=48, range=(0, 24), color='coral',
                    edgecolor='black', alpha=0.7, linewidth=1.0)
        ax10_1.set_xlabel('小时', fontsize=16, fontweight='bold')
        ax10_1.set_ylabel('Tour数量', fontsize=16, fontweight='bold')
        ax10_1.set_title('Tour出发时间分布（从家出发）', fontsize=18, fontweight='bold', pad=20)
        ax10_1.set_xticks(range(0, 25, 2))
        ax10_1.set_xticklabels([f'{h:02d}:00' for h in range(0, 25, 2)], fontsize=12)
        ax10_1.grid(axis='y', alpha=0.3, linestyle='--')

        end_hours = tours_df['end_time'].apply(lambda x: x / 60.0)
        ax10_2.hist(end_hours, bins=48, range=(0, 24), color='skyblue',
                    edgecolor='black', alpha=0.7, linewidth=1.0)
        ax10_2.set_xlabel('小时', fontsize=16, fontweight='bold')
        ax10_2.set_ylabel('Tour数量', fontsize=16, fontweight='bold')
        ax10_2.set_title('Tour返回时间分布（返回家）', fontsize=18, fontweight='bold', pad=20)
        ax10_2.set_xticks(range(0, 25, 2))
        ax10_2.set_xticklabels([f'{h:02d}:00' for h in range(0, 25, 2)], fontsize=12)
        ax10_2.grid(axis='y', alpha=0.3, linestyle='--')

        plt.tight_layout()
        figures['tour_start_end_time'] = fig10

    if trips_df is not None and not trips_df.empty:
        # 11. 出行方式分布
        fig11, ax11 = plt.subplots(figsize=(12, 12))
        mode_counts = trips_df['mode'].value_counts()
        mode_labels = {
            'walk': '步行',
            'bike': '自行车',
            'transit': '公交',
            'drive_alone': '独自驾车',
            'shared_ride': '共乘'
        }

        labels_mode = [mode_labels.get(x, x) for x in mode_counts.index]
        colors_mode = ['#3498db', '#2ecc71', '#f39c12', '#e74c3c', '#9b59b6']

        wedges, texts, autotexts = ax11.pie(mode_counts.values, labels=labels_mode,
                                            autopct='%1.1f%%', colors=colors_mode,
                                            startangle=90, textprops={'fontsize': 15, 'fontweight': 'bold'})
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontsize(15)
        ax11.set_title('出行方式分布（Modal Share）', fontsize=18, fontweight='bold', pad=20)
        plt.tight_layout()
        figures['mode_share'] = fig11

        # 12. 出行时间分布
        fig12, ax12 = plt.subplots(figsize=(14, 7))
        travel_times = trips_df['travel_time'].clip(upper=180)
        ax12.hist(travel_times, bins=36, color='skyblue', edgecolor='black',
                  alpha=0.7, linewidth=1.0)
        ax12.set_xlabel('出行时间（分钟）', fontsize=16, fontweight='bold')
        ax12.set_ylabel('出行数量', fontsize=16, fontweight='bold')
        ax12.set_title('出行时间分布', fontsize=18, fontweight='bold', pad=20)
        ax12.axvline(travel_times.mean(), color='red', linestyle='--',
                     linewidth=2.5, label=f'平均: {travel_times.mean():.1f}分钟')
        ax12.axvline(travel_times.median(), color='green', linestyle='--',
                     linewidth=2.5, label=f'中位数: {travel_times.median():.1f}分钟')
        ax12.legend(fontsize=13, prop=chinese_font)
        ax12.grid(axis='y', alpha=0.3, linestyle='--')
        plt.tight_layout()
        figures['travel_time'] = fig12

        # 继续第13-15个图表...
        # （由于长度限制，在下一部分继续）

    return figures


def save_all_visualizations(figures: dict, prefix: str = "viz"):
    """将所有图表保存为文件并返回字节数据"""
    from io import BytesIO
    import zipfile

    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for name, fig in figures.items():
            img_buffer = BytesIO()
            fig.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight',
                        facecolor='white', edgecolor='none')
            img_buffer.seek(0)
            zip_file.writestr(f"{prefix}_{name}.png", img_buffer.read())
            plt.close(fig)

    zip_buffer.seek(0)
    return zip_buffer.read()


# ============================================================
#  可视化图表生成功能（续 - 完成第13-15个图表）
# ============================================================

# 在 create_visualization_charts 函数中继续添加第13-15个图表
# 这个函数是对第5部分的补充

def create_visualization_charts_complete(
        hh_df: pd.DataFrame,
        persons_df: pd.DataFrame,
        tours_df: pd.DataFrame = None,
        trips_df: pd.DataFrame = None
):
    """创建所有可视化图表（完整版 - 包含所有15个图表）"""

    # 前面的1-12个图表代码与第5部分相同，这里继续添加13-15

    # 先调用前面的函数获取1-12的图表
    figures = create_visualization_charts(hh_df, persons_df, tours_df, trips_df)

    from matplotlib.font_manager import FontProperties
    chinese_font = FontProperties(family=['Microsoft YaHei', 'SimHei', 'SimSun'])

    if trips_df is not None and not trips_df.empty:
        # 13. 出行目的分布
        fig13, ax13 = plt.subplots(figsize=(14, 8))
        purpose_counts = trips_df['purpose'].value_counts()
        purpose_labels = {
            'work': '工作',
            'school': '上学',
            'shopping': '购物',
            'social': '社交',
            'dining': '餐饮',
            'escort': '接送',
            'home': '回家',
            'other': '其他'
        }

        labels_purpose = [purpose_labels.get(x, x) for x in purpose_counts.index]
        colors_purpose = plt.cm.Set2(range(len(purpose_counts)))

        bars = ax13.bar(range(len(purpose_counts)), purpose_counts.values,
                        color=colors_purpose, edgecolor='black', linewidth=1.5)
        ax13.set_xticks(range(len(purpose_counts)))
        ax13.set_xticklabels(labels_purpose, fontsize=13, rotation=45, ha='right')
        ax13.set_ylabel('出行数量', fontsize=16, fontweight='bold')
        ax13.set_title('出行目的分布', fontsize=18, fontweight='bold', pad=20)
        ax13.grid(axis='y', alpha=0.3, linestyle='--')

        for bar in bars:
            height = bar.get_height()
            ax13.text(bar.get_x() + bar.get_width() / 2., height,
                      f'{int(height)}',
                      ha='center', va='bottom', fontsize=11, fontweight='bold')
        plt.tight_layout()
        figures['trip_purpose'] = fig13

        # 14. 出行出发和到达时间分布
        fig14, (ax14_1, ax14_2) = plt.subplots(2, 1, figsize=(18, 14))

        dep_hours = trips_df['departure_time'].apply(lambda x: x / 60.0)
        ax14_1.hist(dep_hours, bins=48, range=(0, 24), color='mediumpurple',
                    edgecolor='black', alpha=0.7, linewidth=1.0)
        ax14_1.set_xlabel('小时', fontsize=16, fontweight='bold')
        ax14_1.set_ylabel('出行数量', fontsize=16, fontweight='bold')
        ax14_1.set_title('出行出发时间分布（24小时）', fontsize=18, fontweight='bold', pad=20)
        ax14_1.set_xticks(range(0, 25, 1))
        ax14_1.set_xticklabels([f'{h:02d}:00' for h in range(0, 25, 1)],
                               rotation=45, ha='right', fontsize=11)
        ax14_1.grid(axis='y', alpha=0.3, linestyle='--')

        arr_hours = trips_df['arrival_time'].apply(lambda x: x / 60.0)
        ax14_2.hist(arr_hours, bins=48, range=(0, 24), color='lightcoral',
                    edgecolor='black', alpha=0.7, linewidth=1.0)
        ax14_2.set_xlabel('小时', fontsize=16, fontweight='bold')
        ax14_2.set_ylabel('出行数量', fontsize=16, fontweight='bold')
        ax14_2.set_title('出行到达时间分布（24小时）', fontsize=18, fontweight='bold', pad=20)
        ax14_2.set_xticks(range(0, 25, 1))
        ax14_2.set_xticklabels([f'{h:02d}:00' for h in range(0, 25, 1)],
                               rotation=45, ha='right', fontsize=11)
        ax14_2.grid(axis='y', alpha=0.3, linestyle='--')

        plt.tight_layout()
        figures['departure_arrival_time'] = fig14

        # 15. 按出行类型分类的时间分布
        fig15, axes15 = plt.subplots(2, 2, figsize=(18, 14))

        # Work出行
        work_trips = trips_df[trips_df['purpose'] == 'work']
        if len(work_trips) > 0:
            work_dep = work_trips['departure_time'].apply(lambda x: x / 60.0)
            work_arr = work_trips['arrival_time'].apply(lambda x: x / 60.0)

            axes15[0, 0].hist(work_dep, bins=48, range=(0, 24), color='#3498db',
                              alpha=0.6, label='出发', edgecolor='black', linewidth=0.8)
            axes15[0, 0].hist(work_arr, bins=48, range=(0, 24), color='#e74c3c',
                              alpha=0.6, label='到达', edgecolor='black', linewidth=0.8)
            axes15[0, 0].set_title('工作出行时间分布', fontsize=16, fontweight='bold')
            axes15[0, 0].set_xlabel('小时', fontsize=13)
            axes15[0, 0].set_ylabel('次数', fontsize=13)
            axes15[0, 0].legend(fontsize=12, prop=chinese_font)
            axes15[0, 0].grid(alpha=0.3)
            axes15[0, 0].set_xticks(range(0, 25, 3))

        # School出行
        school_trips = trips_df[trips_df['purpose'] == 'school']
        if len(school_trips) > 0:
            school_dep = school_trips['departure_time'].apply(lambda x: x / 60.0)
            school_arr = school_trips['arrival_time'].apply(lambda x: x / 60.0)

            axes15[0, 1].hist(school_dep, bins=48, range=(0, 24), color='#2ecc71',
                              alpha=0.6, label='出发', edgecolor='black', linewidth=0.8)
            axes15[0, 1].hist(school_arr, bins=48, range=(0, 24), color='#f39c12',
                              alpha=0.6, label='到达', edgecolor='black', linewidth=0.8)
            axes15[0, 1].set_title('上学出行时间分布', fontsize=16, fontweight='bold')
            axes15[0, 1].set_xlabel('小时', fontsize=13)
            axes15[0, 1].set_ylabel('次数', fontsize=13)
            axes15[0, 1].legend(fontsize=12, prop=chinese_font)
            axes15[0, 1].grid(alpha=0.3)
            axes15[0, 1].set_xticks(range(0, 25, 3))

        # Shopping出行
        shop_trips = trips_df[trips_df['purpose'] == 'shopping']
        if len(shop_trips) > 0:
            shop_dep = shop_trips['departure_time'].apply(lambda x: x / 60.0)
            shop_arr = shop_trips['arrival_time'].apply(lambda x: x / 60.0)

            axes15[1, 0].hist(shop_dep, bins=48, range=(0, 24), color='#9b59b6',
                              alpha=0.6, label='出发', edgecolor='black', linewidth=0.8)
            axes15[1, 0].hist(shop_arr, bins=48, range=(0, 24), color='#1abc9c',
                              alpha=0.6, label='到达', edgecolor='black', linewidth=0.8)
            axes15[1, 0].set_title('购物出行时间分布', fontsize=16, fontweight='bold')
            axes15[1, 0].set_xlabel('小时', fontsize=13)
            axes15[1, 0].set_ylabel('次数', fontsize=13)
            axes15[1, 0].legend(fontsize=12, prop=chinese_font)
            axes15[1, 0].grid(alpha=0.3)
            axes15[1, 0].set_xticks(range(0, 25, 3))

        # Home出行
        home_trips = trips_df[trips_df['purpose'] == 'home']
        if len(home_trips) > 0:
            home_dep = home_trips['departure_time'].apply(lambda x: x / 60.0)
            home_arr = home_trips['arrival_time'].apply(lambda x: x / 60.0)

            axes15[1, 1].hist(home_dep, bins=48, range=(0, 24), color='#e67e22',
                              alpha=0.6, label='出发', edgecolor='black', linewidth=0.8)
            axes15[1, 1].hist(home_arr, bins=48, range=(0, 24), color='#34495e',
                              alpha=0.6, label='到达（回家）', edgecolor='black', linewidth=0.8)
            axes15[1, 1].set_title('回家出行时间分布', fontsize=16, fontweight='bold')
            axes15[1, 1].set_xlabel('小时', fontsize=13)
            axes15[1, 1].set_ylabel('次数', fontsize=13)
            axes15[1, 1].legend(fontsize=12, prop=chinese_font)
            axes15[1, 1].grid(alpha=0.3)
            axes15[1, 1].set_xticks(range(0, 25, 3))

        plt.tight_layout()
        figures['trip_time_by_purpose'] = fig15

    return figures


# ============================================================
#  多中心点管理UI组件（完整版 - 支持上传shp文件）
# ============================================================

def render_center_points_manager(study_gdf: gpd.GeoDataFrame) -> List[CenterPoint]:
    """
    渲染多中心点管理界面
    - 支持上传shp文件计算中心
    - 支持手动输入经纬度
    - 统一使用WGS84经纬度输入，然后选择目标坐标系转换
    """

    st.markdown("### 🎯 多中心点管理（新功能 - 支持多坐标系）")

    # 获取研究范围的坐标系
    study_crs = study_gdf.crs.to_string()

    # 获取研究范围中心点（转换为WGS84经纬度）
    center_geom_wgs84 = study_gdf.to_crs(epsg=4326).unary_union.centroid
    default_lon, default_lat = center_geom_wgs84.x, center_geom_wgs84.y

    # 初始化session state
    if 'center_points' not in st.session_state:
        # 默认添加一个中心点（研究区域的几何中心）
        st.session_state.center_points = [
            {
                'name': '主中心',
                'lon': default_lon,
                'lat': default_lat,
                'target_crs': study_crs,
                'priority': 1,
                'rings': [
                    {'radius': 3000.0, 'area_type': 'CBD'},
                    {'radius': 10000.0, 'area_type': 'urban'},
                    {'radius': None, 'area_type': 'suburban'}
                ]
            }
        ]

    # 添加新中心点按钮
    col_add, col_info = st.columns([1, 3])
    with col_add:
        if st.button("➕ 添加中心点"):
            new_center = {
                'name': f'中心点{len(st.session_state.center_points) + 1}',
                'lon': default_lon,
                'lat': default_lat,
                'target_crs': study_crs,
                'priority': len(st.session_state.center_points) + 1,
                'rings': [
                    {'radius': 5000.0, 'area_type': 'urban'},
                    {'radius': None, 'area_type': 'suburban'}
                ]
            }
            st.session_state.center_points.append(new_center)
            st.rerun()

    with col_info:
        st.info(
            f"💡 当前共有 {len(st.session_state.center_points)} 个中心点。统一使用WGS84经纬度输入，可选择目标坐标系转换。")

    # 显示和编辑每个中心点
    centers_to_delete = []

    for idx, center_data in enumerate(st.session_state.center_points):
        with st.expander(f"📍 {center_data['name']} (优先级: {center_data['priority']})", expanded=(idx == 0)):

            col_del, col_name, col_priority = st.columns([1, 3, 2])

            with col_del:
                if len(st.session_state.center_points) > 1:
                    if st.button(f"🗑️ 删除", key=f"del_center_{idx}"):
                        centers_to_delete.append(idx)

            with col_name:
                center_data['name'] = st.text_input(
                    "中心点名称",
                    value=center_data['name'],
                    key=f"center_name_{idx}"
                )

            with col_priority:
                center_data['priority'] = st.number_input(
                    "优先级",
                    min_value=1,
                    max_value=100,
                    value=center_data['priority'],
                    key=f"center_priority_{idx}",
                    help="数字越大优先级越高，高优先级会覆盖低优先级的区域分类"
                )

            st.markdown("---")
            st.markdown("#### 📐 坐标设置（统一使用WGS84经纬度）")

            # 【新增】支持三种坐标输入方式
            coord_mode = st.radio(
                "坐标输入方式",
                options=[
                    "使用研究范围中心（WGS84）",
                    "上传Shapefile计算中心（WGS84）",
                    "手动输入经纬度（WGS84）"
                ],
                key=f"coord_mode_{idx}",
                horizontal=False
            )

            # 统一流程：经纬度输入
            if coord_mode == "使用研究范围中心（WGS84）":
                # 使用默认经纬度
                input_lon = default_lon
                input_lat = default_lat

                st.success(f"✓ 使用研究范围中心（WGS84经纬度）")
                col_coord1, col_coord2 = st.columns(2)
                with col_coord1:
                    st.metric("经度 (°)", f"{input_lon:.6f}")
                with col_coord2:
                    st.metric("纬度 (°)", f"{input_lat:.6f}")

            elif coord_mode == "上传Shapefile计算中心（WGS84）":
                # 【新增】上传shp文件计算中心
                st.markdown("**上传Shapefile ZIP文件**")

                uploaded_center_shp = st.file_uploader(
                    f"上传中心点范围Shapefile ZIP",
                    type=["zip"],
                    key=f"center_shp_{idx}",
                    help="将计算该Shapefile的几何中心作为中心点坐标"
                )

                if uploaded_center_shp is not None:
                    try:
                        # 读取上传的shapefile
                        center_gdf = read_zipped_shapefile(uploaded_center_shp)

                        if center_gdf is not None and not center_gdf.empty:
                            # 转换到WGS84并计算中心
                            center_gdf_wgs84 = center_gdf.to_crs(epsg=4326)
                            center_geom = center_gdf_wgs84.unary_union.centroid
                            input_lon = center_geom.x
                            input_lat = center_geom.y

                            # 更新到center_data
                            center_data['lon'] = input_lon
                            center_data['lat'] = input_lat

                            st.success(f"✓ 成功计算中心点坐标")
                            col_c1, col_c2 = st.columns(2)
                            with col_c1:
                                st.metric("经度 (°)", f"{input_lon:.6f}")
                            with col_c2:
                                st.metric("纬度 (°)", f"{input_lat:.6f}")

                            # 显示上传的shapefile范围
                            st.info(f"📊 上传的Shapefile包含 {len(center_gdf)} 个要素")
                        else:
                            st.error("❌ 无法读取Shapefile")
                            input_lon = center_data.get('lon', default_lon)
                            input_lat = center_data.get('lat', default_lat)
                    except Exception as e:
                        st.error(f"❌ 读取Shapefile失败: {e}")
                        input_lon = center_data.get('lon', default_lon)
                        input_lat = center_data.get('lat', default_lat)
                else:
                    # 没有上传文件，使用已有坐标
                    input_lon = center_data.get('lon', default_lon)
                    input_lat = center_data.get('lat', default_lat)
                    st.info(f"当前坐标: 经度={input_lon:.6f}°, 纬度={input_lat:.6f}°")

            else:
                # 手动输入经纬度
                st.markdown("**输入WGS84经纬度坐标**")

                # 确保有默认值
                if 'lon' not in center_data:
                    center_data['lon'] = default_lon
                if 'lat' not in center_data:
                    center_data['lat'] = default_lat

                col_lon, col_lat = st.columns(2)

                with col_lon:
                    input_lon = st.number_input(
                        "经度 (°)",
                        min_value=-180.0,
                        max_value=180.0,
                        value=float(center_data.get('lon', default_lon)),
                        format="%.6f",
                        key=f"center_lon_{idx}",
                        help="中国范围：73°E - 135°E"
                    )

                with col_lat:
                    input_lat = st.number_input(
                        "纬度 (°)",
                        min_value=-90.0,
                        max_value=90.0,
                        value=float(center_data.get('lat', default_lat)),
                        format="%.6f",
                        key=f"center_lat_{idx}",
                        help="中国范围：3°N - 54°N"
                    )

            # 更新经纬度
            center_data['lon'] = input_lon
            center_data['lat'] = input_lat

            # 坐标系转换选择
            st.markdown("---")
            st.markdown("#### 🔄 选择目标坐标系")

            # 获取推荐坐标系
            recommended = get_recommended_crs_for_region(study_gdf)

            # 所有可用坐标系（排除WGS84地理坐标系，因为已经是输入格式）
            all_crs = [crs for crs in CHINA_CRS_DEFINITIONS.keys() if crs != "EPSG:4326"]

            # 创建选项标签
            crs_options = []
            crs_labels = {}

            for crs in all_crs:
                info = CHINA_CRS_DEFINITIONS[crs]
                if crs in recommended[:3]:
                    label_text = f"⭐ {crs} - {info['name']} (推荐)"
                    crs_options.insert(len([c for c in crs_options if '⭐' in crs_labels.get(c, '')]), crs)
                else:
                    label_text = f"{crs} - {info['name']}"
                    crs_options.append(crs)
                crs_labels[crs] = label_text

            # 确保有target_crs字段
            if 'target_crs' not in center_data:
                center_data['target_crs'] = study_crs if study_crs != "EPSG:4326" else recommended[0]

            # 坐标系选择
            col_crs1, col_crs2 = st.columns([3, 1])

            with col_crs1:
                default_index = crs_options.index(center_data['target_crs']) if center_data[
                                                                                    'target_crs'] in crs_options else 0

                selected_target_crs = st.selectbox(
                    "转换到坐标系",
                    options=crs_options,
                    index=default_index,
                    format_func=lambda x: crs_labels[x],
                    key=f"target_crs_{idx}",
                    help="⭐标记为根据研究范围推荐的坐标系"
                )

                center_data['target_crs'] = selected_target_crs

            with col_crs2:
                target_info = CHINA_CRS_DEFINITIONS[selected_target_crs]
                st.info(f"**单位**\n\n{target_info['unit']}")

            # 显示转换后的坐标
            st.markdown("**转换后的坐标**")

            try:
                target_x, target_y = transform_coordinates(
                    input_lon, input_lat, "EPSG:4326", selected_target_crs
                )

                col_tx, col_ty = st.columns(2)
                with col_tx:
                    st.success(f"**X坐标**: {target_x:,.2f} {target_info['unit']}")
                with col_ty:
                    st.success(f"**Y坐标**: {target_y:,.2f} {target_info['unit']}")

            except Exception as e:
                st.error(f"坐标转换失败: {e}")
                target_x, target_y = input_lon, input_lat

            # 显示坐标系详细说明 - 使用checkbox避免嵌套expander
            if st.checkbox(f"📖 查看 {selected_target_crs} 详细说明", key=f"show_crs_info_{idx}"):
                st.info(f"""
**名称**: {target_info['name']}

**描述**: {target_info['description']}

**类型**: {target_info['type']}

**单位**: {target_info['unit']}
                """)

            # 显示在其他坐标系下的坐标
            if st.checkbox("📍 查看该点在其他坐标系的坐标", key=f"show_other_crs_{idx}"):
                display_crs = [crs for crs in recommended[:4] if crs != selected_target_crs and crs != "EPSG:4326"]
                if len(display_crs) < 4:
                    display_crs.extend(
                        [crs for crs in all_crs if crs not in display_crs and crs != selected_target_crs][
                        :4 - len(display_crs)])

                coord_df = display_coordinate_in_multiple_crs(
                    input_lon, input_lat, "EPSG:4326", display_crs[:5]
                )
                st.dataframe(coord_df, use_container_width=True)

            st.markdown("---")
            st.markdown("#### 🔵 圈层设置")

            # 添加圈层按钮
            if st.button(f"➕ 添加圈层", key=f"add_ring_{idx}"):
                center_data['rings'].insert(-1, {
                    'radius': 5000.0,
                    'area_type': 'mixed'
                })
                st.rerun()

            # 显示和编辑每个圈层
            rings_to_delete = []

            for ring_idx, ring in enumerate(center_data['rings']):
                is_last = (ring_idx == len(center_data['rings']) - 1)

                col_r1, col_r2, col_r3 = st.columns([2, 2, 1])

                with col_r1:
                    if is_last:
                        st.text_input(
                            f"圈层 {ring_idx + 1} 半径",
                            value="无限（外圈）",
                            disabled=True,
                            key=f"ring_radius_disabled_{idx}_{ring_idx}"
                        )
                    else:
                        ring['radius'] = st.number_input(
                            f"圈层 {ring_idx + 1} 半径 (米)",
                            min_value=100.0,
                            max_value=100000.0,
                            value=float(ring['radius']),
                            step=500.0,
                            key=f"ring_radius_{idx}_{ring_idx}"
                        )

                with col_r2:
                    ring['area_type'] = st.text_input(
                        f"区域类型",
                        value=ring['area_type'],
                        key=f"ring_type_{idx}_{ring_idx}",
                        help="如：CBD, urban, suburban, rural 等"
                    )

                with col_r3:
                    if not is_last and len(center_data['rings']) > 2:
                        if st.button("🗑️", key=f"del_ring_{idx}_{ring_idx}"):
                            rings_to_delete.append(ring_idx)

            # 删除标记的圈层
            for ring_idx in sorted(rings_to_delete, reverse=True):
                center_data['rings'].pop(ring_idx)

            if rings_to_delete:
                st.rerun()

            st.markdown("---")

    # 删除标记的中心点
    for idx in sorted(centers_to_delete, reverse=True):
        st.session_state.center_points.pop(idx)

    if centers_to_delete:
        st.rerun()

    # 转换为CenterPoint对象
    center_points = []
    for center_data in st.session_state.center_points:
        # 从WGS84经纬度转换到目标坐标系
        target_crs = center_data.get('target_crs', study_crs)
        lon = center_data.get('lon', default_lon)
        lat = center_data.get('lat', default_lat)

        try:
            target_x, target_y = transform_coordinates(lon, lat, "EPSG:4326", target_crs)
        except:
            # 转换失败，使用原始坐标
            target_x, target_y = lon, lat

        rings = [
            (ring['radius'], ring['area_type'])
            for ring in center_data['rings']
        ]

        center_points.append(CenterPoint(
            name=center_data['name'],
            x=target_x,
            y=target_y,
            rings=rings,
            priority=center_data['priority'],
            crs=target_crs
        ))

    return center_points


# ============================================================
#  按区域类型配置参数的UI组件（完整版 - 所有详细参数）
# ============================================================

def render_area_type_config_ui(area_types: List[str]) -> Dict[str, AreaTypeConfig]:
    """
    为每个area_type渲染完整的配置UI
    包含所有人口生成参数和Tour/Trip参数的详细配置
    """

    st.markdown("### 🎛️ 按区域类型配置参数（完整参数配置）")

    st.info("""
    💡 **新功能说明**：
    - 为每个区域类型（如CBD、城区、郊区）配置**所有详细参数**
    - 包括：家庭规模、收入、汽车、年龄、就业、Tour频率等**完整参数**
    - 提供快速预设模板（CBD/城区/郊区）一键应用
    - 如不启用，将使用统一参数（原有模式）
    """)

    # 初始化session state
    if 'use_area_type_config' not in st.session_state:
        st.session_state.use_area_type_config = False

    if 'area_type_configs' not in st.session_state:
        st.session_state.area_type_configs = {}

    # 选择是否启用按区域类型配置
    use_area_config = st.checkbox(
        "✅ 启用按区域类型差异化配置（完整参数）",
        value=st.session_state.use_area_type_config,
        help="勾选后可为每个区域类型单独配置**所有详细参数**；不勾选则使用统一参数（原有模式）"
    )

    st.session_state.use_area_type_config = use_area_config

    if not use_area_config:
        st.warning("⚠️ 当前使用统一参数模式（原有功能）")
        return {}

    # 为每个area_type创建配置
    area_configs = {}

    st.markdown(f"#### 检测到 {len(area_types)} 个区域类型")

    for area_type in area_types:

        with st.expander(f"🏙️ 区域类型：{area_type}", expanded=(area_type == area_types[0])):

            # 初始化默认配置
            if area_type not in st.session_state.area_type_configs:
                st.session_state.area_type_configs[area_type] = {
                    'population': get_default_population_params(),
                    'tour': get_default_tour_params()
                }

            config_data = st.session_state.area_type_configs[area_type]

            # ============ 快速预设模板 ============
            st.markdown("##### 🚀 快速配置模板")

            col_preset1, col_preset2, col_preset3, col_preset4 = st.columns(4)

            with col_preset1:
                if st.button(f"📍 CBD模板", key=f"preset_cbd_{area_type}"):
                    # CBD: 高就业率、低汽车、高收入、短距离
                    config_data['population']['hhsize_dist'] = {"1": 0.40, "2": 0.35, "3": 0.15, "4": 0.08, "5+": 0.02}
                    config_data['population']['income_segment_weights'] = {"low": 0.15, "mid": 0.40, "high": 0.45}
                    config_data['population']['worker_rate_by_age'] = {
                        "16-17": 0.05, "18-22": 0.35, "23-59": 0.90, "60-64": 0.50, "65+": 0.15
                    }
                    config_data['tour']['max_distance'] = 15000.0
                    config_data['tour']['distance_decay'] = 0.20
                    st.success("✅ 已应用CBD模板")

            with col_preset2:
                if st.button(f"🏘️ 城区模板", key=f"preset_urban_{area_type}"):
                    # 城区: 中等参数
                    config_data['population']['hhsize_dist'] = {"1": 0.30, "2": 0.40, "3": 0.20, "4": 0.10, "5+": 0.00}
                    config_data['population']['income_segment_weights'] = {"low": 0.30, "mid": 0.50, "high": 0.20}
                    config_data['population']['worker_rate_by_age'] = {
                        "16-17": 0.05, "18-22": 0.30, "23-59": 0.80, "60-64": 0.40, "65+": 0.10
                    }
                    config_data['tour']['max_distance'] = 25000.0
                    config_data['tour']['distance_decay'] = 0.10
                    st.success("✅ 已应用城区模板")

            with col_preset3:
                if st.button(f"🌳 郊区模板", key=f"preset_suburban_{area_type}"):
                    # 郊区: 高汽车、长距离
                    config_data['population']['hhsize_dist'] = {"1": 0.20, "2": 0.35, "3": 0.25, "4": 0.15, "5+": 0.05}
                    config_data['population']['income_segment_weights'] = {"low": 0.40, "mid": 0.45, "high": 0.15}
                    config_data['population']['worker_rate_by_age'] = {
                        "16-17": 0.05, "18-22": 0.25, "23-59": 0.75, "60-64": 0.35, "65+": 0.08
                    }
                    config_data['tour']['max_distance'] = 40000.0
                    config_data['tour']['distance_decay'] = 0.05
                    st.success("✅ 已应用郊区模板")

            with col_preset4:
                if st.button(f"🏞️ 农村模板", key=f"preset_rural_{area_type}"):
                    # 农村: 大家庭、低收入、长距离
                    config_data['population']['hhsize_dist'] = {"1": 0.15, "2": 0.25, "3": 0.25, "4": 0.20, "5+": 0.15}
                    config_data['population']['income_segment_weights'] = {"low": 0.60, "mid": 0.30, "high": 0.10}
                    config_data['population']['worker_rate_by_age'] = {
                        "16-17": 0.10, "18-22": 0.40, "23-59": 0.85, "60-64": 0.45, "65+": 0.20
                    }
                    config_data['tour']['max_distance'] = 50000.0
                    config_data['tour']['distance_decay'] = 0.03
                    st.success("✅ 已应用农村模板")

            # ============ 详细参数配置 ============
            st.markdown("---")

            # 使用tabs组织详细参数
            tab1, tab2, tab3, tab4 = st.tabs([
                "👥 家庭与收入",
                "🚗 汽车与年龄",
                "💼 就业与教育",
                "🚌 出行参数"
            ])

            # ===== Tab 1: 家庭与收入 =====
            with tab1:
                st.markdown("#### 家庭规模分布")

                col_h1, col_h2, col_h3, col_h4, col_h5 = st.columns(5)

                hhsize_dist = {}
                hhsize_dist["1"] = col_h1.number_input(
                    "1人户", 0.0, 1.0,
                    config_data['population']['hhsize_dist']["1"],
                    0.01, key=f"{area_type}_hh1"
                )
                hhsize_dist["2"] = col_h2.number_input(
                    "2人户", 0.0, 1.0,
                    config_data['population']['hhsize_dist']["2"],
                    0.01, key=f"{area_type}_hh2"
                )
                hhsize_dist["3"] = col_h3.number_input(
                    "3人户", 0.0, 1.0,
                    config_data['population']['hhsize_dist']["3"],
                    0.01, key=f"{area_type}_hh3"
                )
                hhsize_dist["4"] = col_h4.number_input(
                    "4人户", 0.0, 1.0,
                    config_data['population']['hhsize_dist']["4"],
                    0.01, key=f"{area_type}_hh4"
                )
                hhsize_dist["5+"] = col_h5.number_input(
                    "5人+", 0.0, 1.0,
                    config_data['population']['hhsize_dist']["5+"],
                    0.01, key=f"{area_type}_hh5"
                )

                st.markdown("---")
                st.markdown("#### 收入分布权重")

                col_i1, col_i2, col_i3 = st.columns(3)

                income_weights = {}
                income_weights["low"] = col_i1.number_input(
                    "低收入占比", 0.0, 1.0,
                    config_data['population']['income_segment_weights']["low"],
                    0.05, key=f"{area_type}_inc_low"
                )
                income_weights["mid"] = col_i2.number_input(
                    "中收入占比", 0.0, 1.0,
                    config_data['population']['income_segment_weights']["mid"],
                    0.05, key=f"{area_type}_inc_mid"
                )
                income_weights["high"] = col_i3.number_input(
                    "高收入占比", 0.0, 1.0,
                    config_data['population']['income_segment_weights']["high"],
                    0.05, key=f"{area_type}_inc_high"
                )

            # ===== Tab 2: 汽车与年龄 =====
            with tab2:
                st.markdown("#### 汽车拥有水平")

                auto_level = st.select_slider(
                    "整体汽车拥有水平",
                    options=["很低", "低", "中等", "高", "很高"],
                    value="中等",
                    key=f"{area_type}_auto_level",
                    help="CBD地区通常选择'很低'或'低'，郊区选择'高'或'很高'"
                )

                # 自动生成汽车配置
                auto_configs = {
                    "很低": {
                        "low": {"1": [0.9, 0.1, 0.0], "2": [0.8, 0.2, 0.0], "3+": [0.7, 0.3, 0.0]},
                        "mid": {"1": [0.7, 0.3, 0.0], "2": [0.6, 0.4, 0.0], "3+": [0.5, 0.4, 0.1]},
                        "high": {"1": [0.5, 0.4, 0.1], "2": [0.4, 0.5, 0.1], "3+": [0.3, 0.5, 0.2]}
                    },
                    "低": {
                        "low": {"1": [0.8, 0.2, 0.0], "2": [0.6, 0.4, 0.0], "3+": [0.4, 0.4, 0.2]},
                        "mid": {"1": [0.5, 0.5, 0.0], "2": [0.3, 0.6, 0.1], "3+": [0.2, 0.5, 0.3]},
                        "high": {"1": [0.3, 0.5, 0.2], "2": [0.2, 0.5, 0.3], "3+": [0.1, 0.4, 0.5]}
                    },
                    "中等": config_data['population']['autos_by_income_and_hhsize'],
                    "高": {
                        "low": {"1": [0.4, 0.5, 0.1], "2": [0.2, 0.6, 0.2], "3+": [0.1, 0.5, 0.4]},
                        "mid": {"1": [0.2, 0.6, 0.2], "2": [0.1, 0.5, 0.4], "3+": [0.0, 0.4, 0.6]},
                        "high": {"1": [0.1, 0.5, 0.4], "2": [0.0, 0.4, 0.6], "3+": [0.0, 0.3, 0.7]}
                    },
                    "很高": {
                        "low": {"1": [0.2, 0.6, 0.2], "2": [0.1, 0.5, 0.4], "3+": [0.0, 0.4, 0.6]},
                        "mid": {"1": [0.1, 0.5, 0.4], "2": [0.0, 0.4, 0.6], "3+": [0.0, 0.3, 0.7]},
                        "high": {"1": [0.0, 0.4, 0.6], "2": [0.0, 0.3, 0.7], "3+": [0.0, 0.2, 0.8]}
                    }
                }

                autos_config = auto_configs[auto_level]

                st.markdown("---")
                st.markdown("#### 年龄结构")

                col_a1, col_a2, col_a3, col_a4, col_a5 = st.columns(5)

                age_shares = {}
                age_shares["0-5"] = col_a1.number_input(
                    "0-5岁", 0.0, 1.0,
                    config_data['population']['age_shares']["0-5"],
                    0.01, key=f"{area_type}_age_0_5"
                )
                age_shares["6-17"] = col_a2.number_input(
                    "6-17岁", 0.0, 1.0,
                    config_data['population']['age_shares']["6-17"],
                    0.01, key=f"{area_type}_age_6_17"
                )
                age_shares["18-22"] = col_a3.number_input(
                    "18-22岁", 0.0, 1.0,
                    config_data['population']['age_shares']["18-22"],
                    0.01, key=f"{area_type}_age_18_22"
                )
                age_shares["23-64"] = col_a4.number_input(
                    "23-64岁", 0.0, 1.0,
                    config_data['population']['age_shares']["23-64"],
                    0.01, key=f"{area_type}_age_23_64"
                )
                age_shares["65+"] = col_a5.number_input(
                    "65+岁", 0.0, 1.0,
                    config_data['population']['age_shares']["65+"],
                    0.01, key=f"{area_type}_age_65"
                )

            # ===== Tab 3: 就业与教育 =====
            with tab3:
                st.markdown("#### 就业率（按年龄）")

                col_w1, col_w2, col_w3, col_w4, col_w5 = st.columns(5)

                worker_rate = {}
                worker_rate["16-17"] = col_w1.number_input(
                    "16-17岁", 0.0, 1.0,
                    config_data['population']['worker_rate_by_age']["16-17"],
                    0.05, key=f"{area_type}_wr_16_17"
                )
                worker_rate["18-22"] = col_w2.number_input(
                    "18-22岁", 0.0, 1.0,
                    config_data['population']['worker_rate_by_age']["18-22"],
                    0.05, key=f"{area_type}_wr_18_22"
                )
                worker_rate["23-59"] = col_w3.number_input(
                    "23-59岁", 0.0, 1.0,
                    config_data['population']['worker_rate_by_age']["23-59"],
                    0.05, key=f"{area_type}_wr_23_59",
                    help="CBD地区通常较高(0.85-0.95)，郊区较低(0.70-0.80)"
                )
                worker_rate["60-64"] = col_w4.number_input(
                    "60-64岁", 0.0, 1.0,
                    config_data['population']['worker_rate_by_age']["60-64"],
                    0.05, key=f"{area_type}_wr_60_64"
                )
                worker_rate["65+"] = col_w5.number_input(
                    "65+岁", 0.0, 1.0,
                    config_data['population']['worker_rate_by_age']["65+"],
                    0.05, key=f"{area_type}_wr_65"
                )

                st.markdown("---")
                st.markdown("#### 在学率（按年龄）")

                col_s1, col_s2 = st.columns(2)

                student_rate = {}
                student_rate["6-17"] = col_s1.number_input(
                    "6-17岁在学率", 0.0, 1.0,
                    config_data['population']['student_rate_by_age']["6-17"],
                    0.05, key=f"{area_type}_sr_6_17"
                )
                student_rate["18-22"] = col_s2.number_input(
                    "18-22岁在学率", 0.0, 1.0,
                    config_data['population']['student_rate_by_age']["18-22"],
                    0.05, key=f"{area_type}_sr_18_22"
                )

                st.markdown("---")
                st.markdown("#### 驾照率（按年龄）")

                col_l1, col_l2, col_l3, col_l4 = st.columns(4)

                license_rate = {}
                license_rate["18-22"] = col_l1.number_input(
                    "18-22岁", 0.0, 1.0,
                    config_data['population']['license_rate_by_age']["18-22"],
                    0.05, key=f"{area_type}_lr_18_22"
                )
                license_rate["23-59"] = col_l2.number_input(
                    "23-59岁", 0.0, 1.0,
                    config_data['population']['license_rate_by_age']["23-59"],
                    0.05, key=f"{area_type}_lr_23_59"
                )
                license_rate["60-69"] = col_l3.number_input(
                    "60-69岁", 0.0, 1.0,
                    config_data['population']['license_rate_by_age']["60-69"],
                    0.05, key=f"{area_type}_lr_60_69"
                )
                license_rate["70+"] = col_l4.number_input(
                    "70+岁", 0.0, 1.0,
                    config_data['population']['license_rate_by_age']["70+"],
                    0.05, key=f"{area_type}_lr_70"
                )

            # ===== Tab 4: 出行参数 =====
            with tab4:
                st.markdown("#### 出行距离参数")

                col_d1, col_d2 = st.columns(2)

                max_distance = col_d1.number_input(
                    "最大出行距离(米)", 5000.0, 100000.0,
                    config_data['tour']['max_distance'],
                    1000.0, key=f"{area_type}_maxdist",
                    help="CBD地区通常较短(10000-20000)，郊区较长(30000-50000)"
                )

                distance_decay = col_d2.number_input(
                    "距离衰减系数", 0.01, 0.50,
                    config_data['tour']['distance_decay'],
                    0.01, key=f"{area_type}_decay",
                    help="数值越大，人们越倾向于短距离出行。CBD通常0.15-0.25，郊区0.05-0.10"
                )

                st.markdown("---")
                st.markdown("#### Tour频率（全职工作者）")

                col_tf1, col_tf2, col_tf3, col_tf4 = st.columns(4)

                tour_freq_worker = {}
                tour_freq_worker[0] = col_tf1.number_input(
                    "0 tours", 0.0, 1.0,
                    config_data['tour']['tour_frequency']['full_time_worker'][0],
                    0.05, key=f"{area_type}_tf0"
                )
                tour_freq_worker[1] = col_tf2.number_input(
                    "1 tour", 0.0, 1.0,
                    config_data['tour']['tour_frequency']['full_time_worker'][1],
                    0.05, key=f"{area_type}_tf1"
                )
                tour_freq_worker[2] = col_tf3.number_input(
                    "2 tours", 0.0, 1.0,
                    config_data['tour']['tour_frequency']['full_time_worker'][2],
                    0.05, key=f"{area_type}_tf2"
                )
                tour_freq_worker[3] = col_tf4.number_input(
                    "3+ tours", 0.0, 1.0,
                    config_data['tour']['tour_frequency']['full_time_worker'][3],
                    0.05, key=f"{area_type}_tf3"
                )

                st.markdown("---")
                st.markdown("#### Tour类型分布")

                col_tt1, col_tt2, col_tt3, col_tt4, col_tt5 = st.columns(5)

                tour_type_dist = {}
                tour_type_dist['shopping'] = col_tt1.number_input(
                    "Shopping", 0.0, 1.0,
                    config_data['tour']['tour_type_dist']['shopping'],
                    0.05, key=f"{area_type}_tt_shop"
                )
                tour_type_dist['social'] = col_tt2.number_input(
                    "Social", 0.0, 1.0,
                    config_data['tour']['tour_type_dist']['social'],
                    0.05, key=f"{area_type}_tt_social"
                )
                tour_type_dist['dining'] = col_tt3.number_input(
                    "Dining", 0.0, 1.0,
                    config_data['tour']['tour_type_dist']['dining'],
                    0.05, key=f"{area_type}_tt_dining"
                )
                tour_type_dist['escort'] = col_tt4.number_input(
                    "Escort", 0.0, 1.0,
                    config_data['tour']['tour_type_dist']['escort'],
                    0.05, key=f"{area_type}_tt_escort"
                )
                tour_type_dist['other'] = col_tt5.number_input(
                    "Other", 0.0, 1.0,
                    config_data['tour']['tour_type_dist']['other'],
                    0.05, key=f"{area_type}_tt_other"
                )

            # ============ 保存配置到AreaTypeConfig对象 ============
            area_config = AreaTypeConfig(
                area_type=area_type,
                hhsize_dist=hhsize_dist,
                income_segment_weights=income_weights,
                autos_by_income_and_hhsize=autos_config,
                age_shares=age_shares,
                worker_rate_by_age=worker_rate,
                student_rate_by_age=student_rate,
                license_rate_by_age=license_rate,
                tour_frequency=config_data['tour']['tour_frequency'],
                tour_type_dist=tour_type_dist,
                time_windows=config_data['tour']['time_windows'],
                duration_params=config_data['tour']['duration_params'],
                stop_frequency=config_data['tour']['stop_frequency'],
                max_distance=max_distance,
                distance_decay=distance_decay
            )

            # 更新tour_frequency
            area_config.tour_frequency['full_time_worker'] = tour_freq_worker

            area_configs[area_type] = area_config

            # 更新session state
            config_data['population']['hhsize_dist'] = hhsize_dist
            config_data['population']['income_segment_weights'] = income_weights
            config_data['population']['autos_by_income_and_hhsize'] = autos_config
            config_data['population']['age_shares'] = age_shares
            config_data['population']['worker_rate_by_age'] = worker_rate
            config_data['population']['student_rate_by_age'] = student_rate
            config_data['population']['license_rate_by_age'] = license_rate
            config_data['tour']['max_distance'] = max_distance
            config_data['tour']['distance_decay'] = distance_decay
            config_data['tour']['tour_frequency']['full_time_worker'] = tour_freq_worker
            config_data['tour']['tour_type_dist'] = tour_type_dist

            st.markdown("---")

    return area_configs


# ============================================================
#  主程序 main() 函数（完整版 - 第一部分）
# ============================================================

def main():
    """主程序入口"""

    # ============================================================
    # 页面配置
    # ============================================================
    st.set_page_config(
        page_title="人口与分区生成工具（多中心点+多坐标系版）",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # ============================================================
    # 初始化 session_state
    # ============================================================
    if "zones_gdf" not in st.session_state:
        st.session_state["zones_gdf"] = None
    if "hh_df" not in st.session_state:
        st.session_state["hh_df"] = None
    if "persons_df" not in st.session_state:
        st.session_state["persons_df"] = None
    if "tours_df" not in st.session_state:
        st.session_state["tours_df"] = None
    if "trips_df" not in st.session_state:
        st.session_state["trips_df"] = None
    if "matsim_xml" not in st.session_state:
        st.session_state["matsim_xml"] = None
    if "matsim_config" not in st.session_state:
        st.session_state["matsim_config"] = None

    # ============================================================
    # 页面标题和说明
    # ============================================================
    st.title("🚗 ActivitySim/MATSim 人口与出行生成工具")
    st.subheader("多中心点增强版 + 多坐标系支持 + 完整参数配置 🌐")

    st.markdown(
        """
        **功能说明：**
        1. 📍 上传研究范围 Shapefile（ZIP）  
        2. 🗺️ 自动生成分区 zones（规则方格 / 导入现有分区）  
        3. 🎯 **【新功能】多中心点管理：支持添加多个中心点、上传shp文件计算中心**
        4. 🌈 **【新功能】不同中心点zones用不同颜色显示**
        5. 🌐 **【新功能】多坐标系支持：智能推荐并支持中国常用坐标系**
        6. 🎛️ **【新功能】按区域类型完整参数配置：所有人口和出行参数独立设置**
        7. 👥 生成 households.csv 与 persons.csv  
        8. 🚌 生成 ActivitySim 风格的 tours.csv 和 trips.csv
        9. 🔧 生成 MATSim population.xml 文件
        10. ✅ DTD验证和数据质量检查
        11. 📊 生成完整可视化图表（15个图表）
        12. 📥 下载所有结果文件

        **💡 新增功能亮点：**
        - ⭐ 智能推荐坐标系（根据研究范围自动推荐）
        - 📐 统一使用WGS84经纬度输入，可选择目标坐标系转换
        - 📂 支持上传Shapefile自动计算中心点坐标
        - 🌈 多中心点生成的zones用不同颜色区分
        - 🎛️ 每个区域类型可配置所有详细参数（家庭规模、收入、汽车、年龄、就业、Tour等）
        - 🚀 提供快速预设模板（CBD/城区/郊区/农村）一键应用
        """
    )

    # ============================================================
    # 侧边栏：全局参数
    # ============================================================
    st.sidebar.header("⚙️ 全局设置")

    seed = st.sidebar.number_input("随机种子", value=42, step=1, min_value=0)
    total_households = st.sidebar.number_input("总家庭数", value=1000, min_value=1, step=100)
    max_persons_per_household = st.sidebar.number_input("单户最大人数", value=6, min_value=1, max_value=20, step=1)

    st.sidebar.markdown("---")
    st.sidebar.subheader("📍 研究范围")

    study_area_file = st.sidebar.file_uploader(
        "上传研究范围 Shapefile ZIP",
        type=["zip"],
        help="包含 .shp/.dbf/.shx/.prj 文件的 ZIP 压缩包"
    )

    if study_area_file is None:
        st.warning("⚠️ 请先在左侧上传研究范围 Shapefile ZIP。")
        st.info("""
        **使用提示：**
        1. 准备包含研究范围的Shapefile（.shp, .dbf, .shx, .prj）
        2. 将这些文件压缩为一个ZIP文件
        3. 在左侧边栏上传ZIP文件
        4. 系统将自动读取并显示研究范围
        """)
        return

    # ============================================================
    # 读取并显示研究范围
    # ============================================================
    study_gdf = read_zipped_shapefile(study_area_file)
    if study_gdf is None or study_gdf.empty:
        st.error("❌ 研究范围读取失败或为空，请检查数据。")
        return

    study_gdf = ensure_projected(study_gdf)

    # 显示研究范围的坐标系信息
    st.sidebar.markdown("---")
    st.sidebar.subheader("📐 坐标系信息")
    study_crs = study_gdf.crs.to_string()
    st.sidebar.info(f"**当前坐标系**: {study_crs}")

    if study_crs in CHINA_CRS_DEFINITIONS:
        crs_info = CHINA_CRS_DEFINITIONS[study_crs]
        st.sidebar.write(f"**名称**: {crs_info['name']}")
        st.sidebar.write(f"**类型**: {crs_info['type']}")
        st.sidebar.write(f"**单位**: {crs_info['unit']}")

    # 显示推荐坐标系
    recommended_crs = get_recommended_crs_for_region(study_gdf)
    with st.sidebar.expander("💡 推荐坐标系"):
        st.write("基于研究范围，推荐以下坐标系：")
        for i, crs in enumerate(recommended_crs[:3], 1):
            if crs in CHINA_CRS_DEFINITIONS:
                crs_name = CHINA_CRS_DEFINITIONS[crs]['name']
                st.write(f"{i}. **{crs}** - {crs_name}")

    # 显示研究范围统计
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 研究范围统计")
    st.sidebar.metric("要素数量", len(study_gdf))
    st.sidebar.metric("总面积 (km²)", f"{study_gdf.geometry.area.sum() / 1e6:.2f}")

    # 显示研究范围预览地图
    show_polygon_map(
        study_gdf,
        fill_color=(0, 0, 255, 128),
        label="### 📍 研究范围预览"
    )

    # ============================================================
    # 1️⃣ 分区生成 (Zones)
    # ============================================================
    st.markdown("---")
    st.subheader("1️⃣ 分区生成 (Zones)")

    zone_mode = st.radio(
        "分区生成模式",
        options=["自动生成方格", "从已有 zones.shp 导入"],
        index=0,
        horizontal=True,
    )

    zones_gdf = st.session_state["zones_gdf"]

    if zone_mode == "自动生成方格":
        st.markdown("**格网参数**")

        col_grid1, col_grid2 = st.columns(2)
        with col_grid1:
            cell_size = st.number_input(
                "格网单元边长(米)",
                value=500.0,
                min_value=50.0,
                max_value=10000.0,
                step=50.0,
                help="格网越小，zones数量越多，计算时间越长"
            )
        with col_grid2:
            min_overlap_ratio = st.slider(
                "格网与研究范围重叠比例阈值",
                0.0, 1.0, 0.25, 0.05,
                help="只保留与研究范围重叠面积超过该比例的格网"
            )

        st.markdown("---")

        # 选择使用单中心点还是多中心点
        center_mode_choice = st.radio(
            "中心点配置模式",
            options=["单中心点（原有模式）", "多中心点（新功能 - 支持上传shp）"],
            index=1,
            horizontal=True,
            help="单中心点模式：简单快速；多中心点模式：支持多个中心点、上传shp文件、不同颜色显示"
        )

        if center_mode_choice == "单中心点（原有模式）":
            # ============================================================
            # 单中心点模式
            # ============================================================
            st.markdown("**区域类型：按与中心点距离分环**")

            st.info("💡 统一使用WGS84经纬度输入，然后选择目标坐标系转换")

            # 获取研究范围中心（WGS84经纬度）
            center_geom_wgs84 = study_gdf.to_crs(epsg=4326).unary_union.centroid
            default_lon, default_lat = center_geom_wgs84.x, center_geom_wgs84.y

            coord_mode = st.radio(
                "坐标输入方式",
                options=["使用研究范围中心（WGS84）", "手动输入经纬度（WGS84）"],
                key="single_center_coord_mode",
                horizontal=True,
            )

            # 统一使用经纬度输入
            if coord_mode == "使用研究范围中心（WGS84）":
                input_lon = default_lon
                input_lat = default_lat

                st.success(f"✓ 使用研究范围中心（WGS84经纬度）")
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    st.metric("经度 (°)", f"{input_lon:.6f}")
                with col_c2:
                    st.metric("纬度 (°)", f"{input_lat:.6f}")
            else:
                # 手动输入经纬度
                st.markdown("**输入WGS84经纬度坐标**")

                col_lon, col_lat = st.columns(2)

                with col_lon:
                    input_lon = st.number_input(
                        "经度 (°)",
                        min_value=-180.0,
                        max_value=180.0,
                        value=float(default_lon),
                        format="%.6f",
                        key="single_center_lon",
                        help="中国范围：73°E - 135°E"
                    )

                with col_lat:
                    input_lat = st.number_input(
                        "纬度 (°)",
                        min_value=-90.0,
                        max_value=90.0,
                        value=float(default_lat),
                        format="%.6f",
                        key="single_center_lat",
                        help="中国范围：3°N - 54°N"
                    )

            # 坐标系转换选择
            st.markdown("---")
            st.markdown("**选择目标坐标系**")

            # 所有可用坐标系（排除WGS84地理坐标系）
            all_crs = [crs for crs in CHINA_CRS_DEFINITIONS.keys() if crs != "EPSG:4326"]

            # 创建选项标签
            crs_options = []
            crs_labels = {}

            for crs in all_crs:
                info = CHINA_CRS_DEFINITIONS[crs]
                if crs in recommended_crs[:3]:
                    label_text = f"⭐ {crs} - {info['name']} (推荐)"
                    crs_options.insert(len([c for c in crs_options if '⭐' in crs_labels.get(c, '')]), crs)
                else:
                    label_text = f"{crs} - {info['name']}"
                    crs_options.append(crs)
                crs_labels[crs] = label_text

            # 默认选择
            default_target_crs = study_crs if study_crs != "EPSG:4326" else recommended_crs[0]
            default_index = crs_options.index(default_target_crs) if default_target_crs in crs_options else 0

            col_crs1, col_crs2 = st.columns([3, 1])

            with col_crs1:
                selected_target_crs = st.selectbox(
                    "转换到坐标系",
                    options=crs_options,
                    index=default_index,
                    format_func=lambda x: crs_labels[x],
                    key="single_target_crs",
                    help="⭐标记为根据研究范围推荐的坐标系"
                )

            with col_crs2:
                target_info = CHINA_CRS_DEFINITIONS[selected_target_crs]
                st.info(f"**单位**\n\n{target_info['unit']}")

            # 显示转换后的坐标
            st.markdown("**转换后的坐标**")

            try:
                center_x, center_y = transform_coordinates(
                    input_lon, input_lat, "EPSG:4326", selected_target_crs
                )

                col_tx, col_ty = st.columns(2)
                with col_tx:
                    st.success(f"**X坐标**: {center_x:,.2f} {target_info['unit']}")
                with col_ty:
                    st.success(f"**Y坐标**: {center_y:,.2f} {target_info['unit']}")

                center_crs = selected_target_crs

            except Exception as e:
                st.error(f"坐标转换失败: {e}")
                center_x, center_y = input_lon, input_lat
                center_crs = "EPSG:4326"

            # 显示坐标系详细说明
            if st.checkbox(f"📖 查看 {selected_target_crs} 详细说明", key="single_show_crs_info"):
                st.info(f"""
**名称**: {target_info['name']}

**描述**: {target_info['description']}

**类型**: {target_info['type']}

**单位**: {target_info['unit']}
                """)

            # 显示在其他坐标系下的坐标
            if st.checkbox("📍 查看该点在其他坐标系的坐标", key="single_show_other"):
                display_crs = [crs for crs in recommended_crs[:4] if crs != selected_target_crs and crs != "EPSG:4326"]
                if len(display_crs) < 4:
                    display_crs.extend(
                        [crs for crs in all_crs if crs not in display_crs and crs != selected_target_crs][
                        :4 - len(display_crs)])

                coord_df = display_coordinate_in_multiple_crs(
                    input_lon, input_lat, "EPSG:4326", display_crs[:5]
                )
                st.dataframe(coord_df, use_container_width=True)

            st.markdown("---")

            # 圈层配置
            st.markdown("**圈层配置**")
            col_r1, col_r2, col_r3 = st.columns(3)
            with col_r1:
                r1 = st.number_input("内圈半径(m)", value=3000.0, min_value=0.0, step=500.0)
                t1 = st.text_input("内圈 area_type", value="CBD")
            with col_r2:
                r2 = st.number_input("中圈半径(m)", value=10000.0, min_value=r1, step=1000.0)
                t2 = st.text_input("中圈 area_type", value="urban")
            with col_r3:
                t3 = st.text_input("外圈 area_type", value="suburban")

            if st.button("🗺️ 生成 Zones（单中心点模式）", type="primary"):
                with st.spinner("正在生成方格 zones ..."):
                    tmp_zones = generate_grid_zones(study_gdf, cell_size, min_overlap_ratio)
                    if tmp_zones is not None and not tmp_zones.empty:
                        # 如果中心点坐标系与zones不同，需要转换
                        final_center_x, final_center_y = center_x, center_y
                        if center_crs != tmp_zones.crs.to_string():
                            final_center_x, final_center_y = transform_coordinates(
                                center_x, center_y, center_crs, tmp_zones.crs.to_string()
                            )

                        tmp_zones = assign_area_type_rings(
                            tmp_zones,
                            (final_center_x, final_center_y),
                            [(r1, t1), (r2, t2), (None, t3)]
                        )
                        tmp_zones["zone_weight"] = tmp_zones.geometry.area
                        st.session_state["zones_gdf"] = tmp_zones
                        zones_gdf = tmp_zones

                        # 显示成功信息
                        st.success(f"✅ 成功生成 {len(zones_gdf)} 个 zones")
                        st.info(
                            f"📍 中心点坐标: 经度={input_lon:.6f}°, 纬度={input_lat:.6f}° (WGS84)\n\n转换为 {selected_target_crs}: X={center_x:,.2f}, Y={center_y:,.2f}")

                        # 显示area_type统计
                        area_type_counts = zones_gdf['area_type'].value_counts()
                        st.markdown("#### 区域类型分布")
                        st.dataframe(area_type_counts)
                    else:
                        st.error("❌ 生成zones失败，请检查参数")

        else:
            # ============================================================
            # 多中心点模式（支持上传shp、不同颜色显示）
            # ============================================================
            center_points = render_center_points_manager(study_gdf)

            if st.button("🗺️ 生成 Zones（多中心点模式）", type="primary"):
                with st.spinner("正在生成方格 zones 并应用多中心点配置..."):
                    tmp_zones = generate_grid_zones(study_gdf, cell_size, min_overlap_ratio)
                    if tmp_zones is not None and not tmp_zones.empty:
                        tmp_zones = assign_area_type_multi_centers(
                            tmp_zones,
                            center_points,
                            default_area_type="rural"
                        )
                        tmp_zones["zone_weight"] = tmp_zones.geometry.area
                        st.session_state["zones_gdf"] = tmp_zones
                        zones_gdf = tmp_zones
                        st.success(f"✅ 成功生成 {len(zones_gdf)} 个 zones（多中心点模式）")

                        # 显示详细统计
                        area_type_counts = zones_gdf['area_type'].value_counts()
                        st.markdown("#### 区域类型分布")
                        st.dataframe(area_type_counts)

                        if 'assigned_center' in zones_gdf.columns:
                            center_stats = zones_gdf.groupby('assigned_center')['area_type'].value_counts().unstack(
                                fill_value=0)
                            st.markdown("#### 各中心点分配统计")
                            st.dataframe(center_stats)
                    else:
                        st.error("❌ 生成zones失败，请检查参数")

    else:
        # ============================================================
        # 从文件导入zones
        # ============================================================
        st.markdown("**上传已有 zones Shapefile ZIP**")
        zones_file = st.file_uploader("上传 zones Shapefile ZIP", type=["zip"], key="zones_zip")
        if zones_file is not None:
            zgdf_raw = read_zipped_shapefile(zones_file)
            if zgdf_raw is not None and not zgdf_raw.empty:
                zgdf_raw = ensure_projected(zgdf_raw, study_gdf.crs.to_string())

                st.write("原始 zones 字段:", list(zgdf_raw.columns))

                col_field1, col_field2, col_field3 = st.columns(3)

                with col_field1:
                    id_field = st.selectbox("选择作为 zone_id 的字段", options=list(zgdf_raw.columns))
                with col_field2:
                    area_type_field = st.selectbox(
                        "选择作为 area_type 的字段",
                        options=["<无>"] + list(zgdf_raw.columns)
                    )
                with col_field3:
                    weight_field = st.selectbox(
                        "选择作为 zone_weight 的字段",
                        options=["<无>"] + list(zgdf_raw.columns)
                    )

                if st.button("✓ 确认 zones 字段映射", type="primary"):
                    tmp = zgdf_raw.copy()
                    tmp["zone_id"] = tmp[id_field]
                    tmp["centroid"] = tmp.geometry.centroid
                    tmp["centroid_x"] = tmp["centroid"].x
                    tmp["centroid_y"] = tmp["centroid"].y

                    if area_type_field != "<无>":
                        tmp["area_type"] = tmp[area_type_field]
                    else:
                        tmp["area_type"] = "default"

                    if weight_field != "<无>":
                        tmp["zone_weight"] = tmp[weight_field].astype(float)
                    else:
                        tmp["zone_weight"] = tmp.geometry.area

                    tmp = tmp[["zone_id", "centroid_x", "centroid_y", "area_type", "zone_weight", "geometry"]]
                    st.session_state["zones_gdf"] = tmp
                    zones_gdf = tmp
                    st.success(f"✅ 加载 {len(zones_gdf)} 个 zones")

    # ============================================================
    # 显示生成的zones
    # ============================================================
    zones_gdf = st.session_state["zones_gdf"]

    if zones_gdf is None or zones_gdf.empty:
        st.warning("⚠️ 请先生成或导入 zones。")
        return

    # 显示zones预览地图（根据assigned_center或area_type着色）
    if 'assigned_center' in zones_gdf.columns:
        show_polygon_map(
            zones_gdf,
            fill_color=(255, 0, 0, 128),
            label="### 🗺️ Zones 预览（按中心点着色）",
            color_by='center',
            color_column='assigned_center'
        )
    elif 'area_type' in zones_gdf.columns:
        show_polygon_map(
            zones_gdf,
            fill_color=(255, 0, 0, 128),
            label="### 🗺️ Zones 预览（按区域类型着色）",
            color_by='area_type',
            color_column='area_type'
        )
    else:
        show_polygon_map(
            zones_gdf,
            fill_color=(255, 0, 0, 128),
            label="### 🗺️ Zones 预览"
        )

    # 获取所有area_types（用于后续配置）
    if 'area_type' in zones_gdf.columns:
        all_area_types = sorted(zones_gdf['area_type'].unique().tolist())
    else:
        all_area_types = ['default']

    st.info(f"📊 当前共有 {len(zones_gdf)} 个zones，包含 {len(all_area_types)} 种区域类型：{', '.join(all_area_types)}")
    # ============================================================
    # 【续main函数】1.5️⃣ 按区域类型配置参数（可选）
    # ============================================================
    st.markdown("---")

    # 渲染按area_type配置的UI
    area_type_configs = render_area_type_config_ui(all_area_types)

    use_area_type_mode = st.session_state.get('use_area_type_config', False)

    # ============================================================
    # 2️⃣ 人口生成模型参数（统一参数模式）
    # ============================================================
    st.markdown("---")
    st.subheader("2️⃣ 人口生成模型参数")

    if use_area_type_mode:
        st.info("✅ 当前使用按区域类型差异化配置模式，此处统一参数仅用于全局设置（收入分段）")
    else:
        st.info("💡 当前使用统一参数模式（原有功能）")

    # 家庭规模分布
    with st.expander("2.1 家庭规模分布", expanded=False):
        col_h1, col_h2, col_h3, col_h4, col_h5 = st.columns(5)
        p_h1 = col_h1.number_input("1人户", 0.0, 1.0, 0.30, 0.01, key="global_hh1")
        p_h2 = col_h2.number_input("2人户", 0.0, 1.0, 0.40, 0.01, key="global_hh2")
        p_h3 = col_h3.number_input("3人户", 0.0, 1.0, 0.20, 0.01, key="global_hh3")
        p_h4 = col_h4.number_input("4人户", 0.0, 1.0, 0.10, 0.01, key="global_hh4")
        p_h5p = col_h5.number_input("5人+", 0.0, 1.0, 0.00, 0.01, key="global_hh5")

    hhsize_dist = {"1": p_h1, "2": p_h2, "3": p_h3, "4": p_h4, "5+": p_h5p}

    # 收入分段
    with st.expander("2.2 收入分段", expanded=False):
        col_l1, col_l2 = st.columns(2)
        low_min = col_l1.number_input("低收入最小值", 0.0, 1e9, 0.0, 1000.0, key="global_low_min")
        low_max = col_l2.number_input("低收入最大值", 0.0, 1e9, 300000.0, 1000.0, key="global_low_max")

        col_m1, col_m2 = st.columns(2)
        mid_min = col_m1.number_input("中收入最小值", 0.0, 1e9, 300000.0, 1000.0, key="global_mid_min")
        mid_max = col_m2.number_input("中收入最大值", 0.0, 1e9, 600000.0, 1000.0, key="global_mid_max")

        col_hh1, col_hh2 = st.columns(2)
        high_min = col_hh1.number_input("高收入最小值", 0.0, 1e9, 600000.0, 1000.0, key="global_high_min")
        high_max = col_hh2.number_input("高收入最大值", 0.0, 1e9, 2000000.0, 1000.0, key="global_high_max")

        st.markdown("#### 收入段权重")
        col_w1, col_w2, col_w3 = st.columns(3)
        w_low = col_w1.number_input("低收入占比", 0.0, 1.0, 0.3, 0.01, key="global_w_low")
        w_mid = col_w2.number_input("中收入占比", 0.0, 1.0, 0.5, 0.01, key="global_w_mid")
        w_high = col_w3.number_input("高收入占比", 0.0, 1.0, 0.2, 0.01, key="global_w_high")

    income_segments = {"low": (low_min, low_max), "mid": (mid_min, mid_max), "high": (high_min, high_max)}
    income_segment_weights = {"low": w_low, "mid": w_mid, "high": w_high}

    # 汽车拥有量分布
    with st.expander("2.3 汽车拥有量分布", expanded=False):
        autos_by_income_and_hhsize: Dict[str, Dict[str, List[float]]] = {}

        for seg in ["low", "mid", "high"]:
            st.markdown(f"#### {seg}")
            autos_by_income_and_hhsize[seg] = {}
            for hh_cat in ["1", "2", "3+"]:
                col_a0, col_a1 = st.columns(2)
                label_prefix = f"{seg}-{hh_cat}人户"

                if seg == "low":
                    default0, default1 = (0.8, 0.2) if hh_cat == "1" else (0.6, 0.4) if hh_cat == "2" else (0.4, 0.4)
                elif seg == "mid":
                    default0, default1 = (0.5, 0.5) if hh_cat == "1" else (0.3, 0.6) if hh_cat == "2" else (0.2, 0.5)
                else:
                    default0, default1 = (0.3, 0.4) if hh_cat == "1" else (0.2, 0.4) if hh_cat == "2" else (0.1, 0.4)

                p0 = col_a0.number_input(f"{label_prefix}:无车", 0.0, 1.0, default0, 0.05,
                                         key=f"global_auto_{seg}_{hh_cat}_0")
                p1 = col_a1.number_input(f"{label_prefix}:1车", 0.0, 1.0, default1, 0.05,
                                         key=f"global_auto_{seg}_{hh_cat}_1")
                s = p0 + p1
                if s > 1.0:
                    p0, p1, p2 = p0 / s, p1 / s, 0.0
                else:
                    p2 = 1.0 - s
                autos_by_income_and_hhsize[seg][hh_cat] = [p0, p1, p2]

    # 年龄结构与劳动/在学/驾照率
    with st.expander("2.4 年龄结构与劳动/在学/驾照率", expanded=False):
        st.markdown("#### 年龄结构")
        col_a1, col_a2, col_a3, col_a4, col_a5 = st.columns(5)
        s_0_5 = col_a1.number_input("0-5岁", 0.0, 1.0, 0.05, 0.01, key="global_age_0_5")
        s_6_17 = col_a2.number_input("6-17岁", 0.0, 1.0, 0.15, 0.01, key="global_age_6_17")
        s_18_22 = col_a3.number_input("18-22岁", 0.0, 1.0, 0.10, 0.01, key="global_age_18_22")
        s_23_64 = col_a4.number_input("23-64岁", 0.0, 1.0, 0.55, 0.01, key="global_age_23_64")
        s_65p = col_a5.number_input("65+岁", 0.0, 1.0, 0.15, 0.01, key="global_age_65")

        total_age_share = s_0_5 + s_6_17 + s_18_22 + s_23_64 + s_65p
        if total_age_share <= 0:
            age_shares = {"0-5": 0.05, "6-17": 0.15, "18-22": 0.10, "23-64": 0.55, "65+": 0.15}
        else:
            age_shares = {
                "0-5": s_0_5 / total_age_share,
                "6-17": s_6_17 / total_age_share,
                "18-22": s_18_22 / total_age_share,
                "23-64": s_23_64 / total_age_share,
                "65+": s_65p / total_age_share,
            }

        st.markdown("#### 就业率")
        col_w0, col_w1, col_w2, col_w3, col_w4 = st.columns(5)
        wr_16_17 = col_w0.number_input("16-17岁", 0.0, 1.0, 0.05, 0.05, key="global_wr_16_17")
        wr_18_22 = col_w1.number_input("18-22岁", 0.0, 1.0, 0.30, 0.05, key="global_wr_18_22")
        wr_23_59 = col_w2.number_input("23-59岁", 0.0, 1.0, 0.80, 0.05, key="global_wr_23_59")
        wr_60_64 = col_w3.number_input("60-64岁", 0.0, 1.0, 0.40, 0.05, key="global_wr_60_64")
        wr_65p = col_w4.number_input("65+岁就业", 0.0, 1.0, 0.10, 0.05, key="global_wr_65")

        worker_rate_by_age = {
            "16-17": wr_16_17, "18-22": wr_18_22, "23-59": wr_23_59,
            "60-64": wr_60_64, "65+": wr_65p,
        }

        st.markdown("#### 在学率")
        col_s1, col_s2 = st.columns(2)
        sr_6_17 = col_s1.number_input("6-17岁在学率", 0.0, 1.0, 0.95, 0.05, key="global_sr_6_17")
        sr_18_22 = col_s2.number_input("18-22岁在学率", 0.0, 1.0, 0.70, 0.05, key="global_sr_18_22")

        student_rate_by_age = {"6-17": sr_6_17, "18-22": sr_18_22}

        st.markdown("#### 驾照率")
        col_lc1, col_lc2, col_lc3, col_lc4 = st.columns(4)
        lr_18_22 = col_lc1.number_input("18-22岁驾照", 0.0, 1.0, 0.50, 0.05, key="global_lr_18_22")
        lr_23_59 = col_lc2.number_input("23-59岁驾照", 0.0, 1.0, 0.90, 0.05, key="global_lr_23_59")
        lr_60_69 = col_lc3.number_input("60-69岁驾照", 0.0, 1.0, 0.70, 0.05, key="global_lr_60_69")
        lr_70p = col_lc4.number_input("70+岁驾照", 0.0, 1.0, 0.40, 0.05, key="global_lr_70")

        license_rate_by_age = {
            "18-22": lr_18_22, "23-59": lr_23_59,
            "60-69": lr_60_69, "70+": lr_70p,
        }

    # 创建全局配置对象
    cfg = PopulationConfig(
        total_households=int(total_households),
        max_persons_per_household=int(max_persons_per_household),
        hhsize_dist=hhsize_dist,
        income_segments=income_segments,
        income_segment_weights=income_segment_weights,
        autos_by_income_and_hhsize=autos_by_income_and_hhsize,
        age_shares=age_shares,
        worker_rate_by_age=worker_rate_by_age,
        student_rate_by_age=student_rate_by_age,
        license_rate_by_age=license_rate_by_age,
    )

    # ============================================================
    # 3️⃣ 生成人口数据 (Households & Persons)
    # ============================================================
    st.markdown("---")
    st.subheader("3️⃣ 生成人口数据 (Households & Persons)")

    if use_area_type_mode and area_type_configs:
        # 使用area_type配置模式
        st.info(f"✅ 将使用按区域类型差异化配置模式生成人口（{len(area_type_configs)}个区域类型）")

        if st.button("🏠 生成 Households & Persons（差异化模式）", type="primary"):
            with st.spinner("正在按区域类型差异化生成 households 和 persons ..."):
                try:
                    hh_df, persons_df = generate_households_and_persons_by_area_type(
                        zones_gdf,
                        int(total_households),
                        int(max_persons_per_household),
                        income_segments,
                        area_type_configs,
                        seed=int(seed)
                    )
                    st.session_state["hh_df"] = hh_df
                    st.session_state["persons_df"] = persons_df
                    st.success(f"✅ 成功生成 {len(hh_df)} 个家庭, {len(persons_df)} 个个人（差异化模式）")

                    # 显示按area_type的统计
                    st.markdown("#### 📊 按区域类型统计")
                    area_stats = hh_df.groupby('area_type').agg({
                        'household_id': 'count',
                        'hhsize': 'mean',
                        'autos': 'mean',
                        'income': 'mean'
                    }).round(2)
                    area_stats.columns = ['家庭数', '平均规模', '平均汽车数', '平均收入']
                    st.dataframe(area_stats, use_container_width=True)

                except Exception as e:
                    st.error(f"❌ 生成失败：{e}")
                    import traceback
                    st.code(traceback.format_exc())

    else:
        # 使用统一参数模式
        st.info("💡 将使用统一参数模式生成人口（原有功能）")

        if st.button("🏠 生成 Households & Persons（统一参数模式）", type="primary"):
            with st.spinner("正在生成 households 和 persons ..."):
                try:
                    hh_df, persons_df = generate_households_and_persons(zones_gdf, cfg, seed=int(seed))
                    st.session_state["hh_df"] = hh_df
                    st.session_state["persons_df"] = persons_df
                    st.success(f"✅ 成功生成 {len(hh_df)} 个家庭, {len(persons_df)} 个个人（统一参数模式）")
                except Exception as e:
                    st.error(f"❌ 生成失败：{e}")
                    import traceback
                    st.code(traceback.format_exc())

    # 显示人口数据
    if st.session_state["hh_df"] is not None and st.session_state["persons_df"] is not None:
        hh_df = st.session_state["hh_df"]
        persons_df = st.session_state["persons_df"]

        st.markdown("#### 👨‍👩‍👧‍👦 Households 预览")
        st.dataframe(hh_df.head(20), use_container_width=True)

        st.markdown("#### 👤 Persons 预览")
        st.dataframe(persons_df.head(20), use_container_width=True)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("家庭总数", len(hh_df))
        with col2:
            st.metric("个人总数", len(persons_df))
        with col3:
            avg_hhsize = len(persons_df) / len(hh_df) if len(hh_df) > 0 else 0
            st.metric("平均家庭规模", f"{avg_hhsize:.2f}")

        # 可视化
        st.markdown("---")
        st.subheader("📊 人口数据可视化")

        if st.button("🎨 生成人口可视化图表"):
            with st.spinner("正在生成图表..."):
                try:
                    figures = create_visualization_charts_complete(hh_df, persons_df)

                    st.success(f"✅ 成功生成 {len(figures)} 个图表")

                    # 显示图表
                    for name, fig in figures.items():
                        st.pyplot(fig)
                        plt.close(fig)

                    # 重新生成用于下载
                    figures_download = create_visualization_charts_complete(hh_df, persons_df)
                    zip_data = save_all_visualizations(figures_download, "population")
                    st.download_button(
                        "📥 下载所有人口图表（ZIP）",
                        data=zip_data,
                        file_name="population_visualizations.zip",
                        mime="application/zip"
                    )

                except Exception as e:
                    st.error(f"❌ 图表生成失败：{e}")
                    import traceback
                    st.code(traceback.format_exc())

        # 下载数据
        hh_csv = hh_df.to_csv(index=False).encode("utf-8-sig")
        persons_csv = persons_df.to_csv(index=False).encode("utf-8-sig")

        zones_export = zones_gdf.copy()
        if 'centroid' in zones_export.columns:
            zones_export = zones_export.drop(columns=['centroid'])
        zones_json = zones_export.to_crs(epsg=4326).to_json().encode("utf-8")

        st.markdown("#### 📥 下载人口数据")
        col_d1, col_d2, col_d3 = st.columns(3)

        with col_d1:
            st.download_button(
                "📥 下载 households.csv",
                data=hh_csv,
                file_name="households.csv",
                mime="text/csv",
                use_container_width=True
            )
        with col_d2:
            st.download_button(
                "📥 下载 persons.csv",
                data=persons_csv,
                file_name="persons.csv",
                mime="text/csv",
                use_container_width=True
            )
        with col_d3:
            st.download_button(
                "📥 下载 zones.geojson",
                data=zones_json,
                file_name="zones.geojson",
                mime="application/geo+json",
                use_container_width=True
            )

    # ============================================================
    # 4️⃣ Tour & Trip 生成
    # ============================================================
    st.markdown("---")
    st.subheader("4️⃣ Tour & Trip 生成")

    # Tour生成参数配置（仅在统一参数模式下显示详细配置）
    if not use_area_type_mode:
        with st.expander("Tour 生成参数（统一参数模式）", expanded=False):
            st.markdown("#### Tour Frequency")

            col_tf1, col_tf2 = st.columns(2)
            with col_tf1:
                st.markdown("**Full-time worker**")
                worker_0 = st.slider("0 tours", 0.0, 1.0, 0.05, 0.05, key="tf_worker_0")
                worker_1 = st.slider("1 tour", 0.0, 1.0, 0.60, 0.05, key="tf_worker_1")
                worker_2 = st.slider("2 tours", 0.0, 1.0, 0.30, 0.05, key="tf_worker_2")
                worker_3 = st.slider("3+ tours", 0.0, 1.0, 0.05, 0.05, key="tf_worker_3")

            with col_tf2:
                st.markdown("**University student**")
                student_0 = st.slider("0 tours", 0.0, 1.0, 0.10, 0.05, key="tf_student_0")
                student_1 = st.slider("1 tour", 0.0, 1.0, 0.70, 0.05, key="tf_student_1")
                student_2 = st.slider("2 tours", 0.0, 1.0, 0.20, 0.05, key="tf_student_2")

            col_tf3, col_tf4 = st.columns(2)
            with col_tf3:
                st.markdown("**Non-worker**")
                nonworker_0 = st.slider("0 tours", 0.0, 1.0, 0.30, 0.05, key="tf_nonworker_0")
                nonworker_1 = st.slider("1 tour", 0.0, 1.0, 0.50, 0.05, key="tf_nonworker_1")
                nonworker_2 = st.slider("2 tours", 0.0, 1.0, 0.20, 0.05, key="tf_nonworker_2")

            with col_tf4:
                st.markdown("**Child**")
                child_0 = st.slider("0 tours", 0.0, 1.0, 0.20, 0.05, key="tf_child_0")
                child_1 = st.slider("1 tour", 0.0, 1.0, 0.70, 0.05, key="tf_child_1")
                child_2 = st.slider("2 tours", 0.0, 1.0, 0.10, 0.05, key="tf_child_2")

            tour_frequency = {
                'full_time_worker': {0: worker_0, 1: worker_1, 2: worker_2, 3: worker_3},
                'university_student': {0: student_0, 1: student_1, 2: student_2},
                'non_worker': {0: nonworker_0, 1: nonworker_1, 2: nonworker_2},
                'child': {0: child_0, 1: child_1, 2: child_2},
                'worker_other': {0: 0.15, 1: 0.60, 2: 0.25}
            }

            st.markdown("#### Tour Type Distribution")
            col_tt1, col_tt2, col_tt3, col_tt4 = st.columns(4)
            tt_shop = col_tt1.number_input("Shopping", 0.0, 1.0, 0.30, 0.05, key="tt_shop")
            tt_social = col_tt2.number_input("Social", 0.0, 1.0, 0.25, 0.05, key="tt_social")
            tt_dining = col_tt3.number_input("Dining", 0.0, 1.0, 0.20, 0.05, key="tt_dining")
            tt_escort = col_tt4.number_input("Escort", 0.0, 1.0, 0.15, 0.05, key="tt_escort")
            tt_other = max(1.0 - (tt_shop + tt_social + tt_dining + tt_escort), 0.1)

            tour_type_base = {
                'shopping': tt_shop,
                'social': tt_social,
                'dining': tt_dining,
                'escort': tt_escort,
                'other': tt_other
            }

            tour_type_dist = {
                'full_time_worker': {'work': 1.0, **tour_type_base},
                'university_student': {'school': 1.0, **tour_type_base},
                'non_worker': tour_type_base,
                'child': {'school': 0.8, **tour_type_base},
                'worker_other': {'work': 0.8, **tour_type_base}
            }

            st.markdown("#### Time Windows & Duration")
            st.info("💡 使用默认时间窗口和持续时间参数")

            time_windows = {
                'work': (420, 540), 'school': (390, 480), 'shopping': (540, 1140),
                'social': (600, 1200), 'dining': (660, 1260), 'escort': (420, 540), 'other': (480, 1200),
            }

            duration_params = {
                'work': (420, 600), 'school': (360, 480), 'shopping': (60, 180),
                'social': (90, 240), 'dining': (60, 150), 'escort': (30, 60), 'other': (60, 240),
            }

            st.markdown("#### Destination & Stop")
            col_dest1, col_dest2, col_dest3 = st.columns(3)

            with col_dest1:
                max_distance = st.number_input("最大距离(米)", 1000.0, 100000.0, 30000.0, 1000.0, key="tour_maxdist")

            with col_dest2:
                distance_decay = st.number_input("距离衰减", 0.01, 2.0, 0.1, 0.01, key="tour_decay")

            with col_dest3:
                stop_prob_0 = st.slider("无停靠", 0.0, 1.0, 0.70, 0.05, key="stop_0")
                stop_prob_1 = st.slider("1停靠", 0.0, 1.0, 0.25, 0.05, key="stop_1")
                stop_prob_2 = max(1.0 - stop_prob_0 - stop_prob_1, 0.0)

            stop_frequency = {
                'work': {0: 0.80, 1: 0.15, 2: 0.05},
                'school': {0: 0.85, 1: 0.12, 2: 0.03},
                'shopping': {0: stop_prob_0, 1: stop_prob_1, 2: stop_prob_2},
                'social': {0: stop_prob_0, 1: stop_prob_1, 2: stop_prob_2},
                'dining': {0: 0.90, 1: 0.08, 2: 0.02},
                'escort': {0: 0.70, 1: 0.25, 2: 0.05},
                'other': {0: stop_prob_0, 1: stop_prob_1, 2: stop_prob_2},
            }

        tour_trip_config = TourTripConfig(
            tour_frequency=tour_frequency,
            tour_type_dist=tour_type_dist,
            time_windows=time_windows,
            duration_params=duration_params,
            max_distance=max_distance,
            distance_decay=distance_decay,
            stop_frequency=stop_frequency,
        )
    else:
        st.info("✅ 使用按区域类型配置的Tour参数")
        tour_trip_config = None

    # 生成Tours & Trips
    if st.session_state["hh_df"] is None or st.session_state["persons_df"] is None:
        st.warning("⚠️ 请先生成人口数据！")
    else:
        # 判断使用哪种模式
        if use_area_type_mode and area_type_configs:
            # 使用area_type配置模式
            st.info("✅ 将使用按区域类型差异化配置模式生成Tours & Trips")

            if st.button("🚗 生成 Tours & Trips（差异化模式）", type="primary"):
                with st.spinner("正在按区域类型差异化生成 tours 和 trips..."):
                    try:
                        tours_df, trips_df = generate_tours_and_trips_by_area_type(
                            st.session_state["persons_df"],
                            st.session_state["hh_df"],
                            zones_gdf,
                            area_type_configs,
                            seed=int(seed)
                        )

                        st.session_state["tours_df"] = tours_df
                        st.session_state["trips_df"] = trips_df

                        st.success(f"✅ 成功生成 {len(tours_df)} 个 tours, {len(trips_df)} 个 trips（差异化模式）")

                        # 显示按area_type的统计
                        if 'area_type' in tours_df.columns:
                            st.markdown("#### 📊 按区域类型统计")
                            tour_stats = tours_df.groupby('area_type').agg({
                                'tour_id': 'count',
                                'duration': 'mean'
                            }).round(2)
                            tour_stats.columns = ['Tours数量', '平均时长(分钟)']
                            st.dataframe(tour_stats, use_container_width=True)

                    except Exception as e:
                        st.error(f"❌ 生成失败：{e}")
                        import traceback
                        st.code(traceback.format_exc())

        else:
            # 使用统一参数模式
            st.info("💡 将使用统一参数模式生成Tours & Trips（原有功能）")

            if st.button("🚗 生成 Tours & Trips（统一参数模式）", type="primary"):
                with st.spinner("正在生成 tours 和 trips..."):
                    try:
                        tours_df, trips_df = generate_tours_and_trips(
                            st.session_state["persons_df"],
                            st.session_state["hh_df"],
                            zones_gdf,
                            tour_trip_config,
                            seed=int(seed)
                        )

                        st.session_state["tours_df"] = tours_df
                        st.session_state["trips_df"] = trips_df

                        st.success(f"✅ 成功生成 {len(tours_df)} 个 tours, {len(trips_df)} 个 trips（统一参数模式）")
                    except Exception as e:
                        st.error(f"❌ 生成失败：{e}")
                        import traceback
                        st.code(traceback.format_exc())

    # 显示Tour/Trip数据
    if "tours_df" in st.session_state and st.session_state["tours_df"] is not None:
        tours_df = st.session_state["tours_df"]
        trips_df = st.session_state["trips_df"]

        st.markdown("#### 🚌 Tours 预览")
        st.dataframe(tours_df.head(20), use_container_width=True)

        st.markdown("#### 🚗 Trips 预览")
        st.dataframe(trips_df.head(20), use_container_width=True)

        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
        with col_stat1:
            st.metric("总 Tours", len(tours_df))
        with col_stat2:
            st.metric("总 Trips", len(trips_df))
        with col_stat3:
            total_persons = len(st.session_state["persons_df"])
            avg_tours = len(tours_df) / total_persons if total_persons > 0 else 0
            st.metric("人均 Tours", f"{avg_tours:.2f}")
        with col_stat4:
            avg_trips = len(trips_df) / len(tours_df) if len(tours_df) > 0 else 0
            st.metric("Tour均 Trips", f"{avg_trips:.2f}")

        # 可视化
        st.markdown("---")
        st.subheader("📊 出行数据可视化")

        if st.button("🎨 生成出行图表"):
            with st.spinner("正在生成出行图表..."):
                try:
                    figures = create_visualization_charts_complete(
                        st.session_state["hh_df"],
                        st.session_state["persons_df"],
                        tours_df,
                        trips_df
                    )

                    st.success(f"✅ 成功生成 {len(figures)} 个图表")

                    # 显示图表
                    for name, fig in figures.items():
                        st.pyplot(fig)
                        plt.close(fig)

                    # 重新生成用于下载
                    figures_download = create_visualization_charts_complete(
                        st.session_state["hh_df"],
                        st.session_state["persons_df"],
                        tours_df,
                        trips_df
                    )
                    zip_data = save_all_visualizations(figures_download, "travel")
                    st.download_button(
                        "📥 下载所有出行图表（ZIP）",
                        data=zip_data,
                        file_name="travel_visualizations.zip",
                        mime="application/zip"
                    )

                except Exception as e:
                    st.error(f"❌ 图表生成失败：{e}")
                    import traceback
                    st.code(traceback.format_exc())

        # 下载Tour/Trip数据
        tours_csv = tours_df.to_csv(index=False).encode("utf-8-sig")
        trips_csv = trips_df.to_csv(index=False).encode("utf-8-sig")

        st.markdown("#### 📥 下载 Tour & Trip 数据")
        col_dl1, col_dl2 = st.columns(2)

        with col_dl1:
            st.download_button(
                "📥 下载 tours.csv",
                data=tours_csv,
                file_name="tours.csv",
                mime="text/csv",
                use_container_width=True
            )

        with col_dl2:
            st.download_button(
                "📥 下载 trips.csv",
                data=trips_csv,
                file_name="trips.csv",
                mime="text/csv",
                use_container_width=True
            )

    # ============================================================
    # 5️⃣ MATSim Population XML 生成
    # ============================================================
    st.markdown("---")
    st.subheader("5️⃣ MATSim Population XML 生成")

    if st.session_state["tours_df"] is not None and st.session_state["trips_df"] is not None:

        # 数据验证
        with st.expander("📋 数据验证", expanded=False):
            validation_result = validate_matsim_population(
                st.session_state["persons_df"],
                st.session_state["tours_df"],
                st.session_state["trips_df"]
            )

            if validation_result['valid']:
                st.success("✅ 数据验证通过，可以生成 MATSim population XML")
            else:
                st.warning("⚠️ 数据验证发现以下问题：")
                for issue in validation_result['issues']:
                    st.write(f"- {issue}")

            st.markdown("**统计信息：**")
            for key, value in validation_result['stats'].items():
                st.write(f"- {key}: {value}")

        # XML 生成选项
        st.markdown("### XML 生成选项")

        col_opt1, col_opt2 = st.columns(2)

        with col_opt1:
            include_persons_without_tours = st.checkbox(
                "包含没有 tours 的 persons",
                value=True,
                help="如果勾选，没有任何 tour 的 person 也会被包含在 XML 中（只有一个 home activity）"
            )

        with col_opt2:
            coordinate_precision = st.number_input(
                "坐标精度（小数位数）",
                min_value=0,
                max_value=6,
                value=2,
                help="控制 x, y 坐标的小数位数"
            )

        # 生成按钮
        if st.button("🚀 生成 MATSim Population XML", type="primary"):
            with st.spinner("正在生成 MATSim population XML..."):
                try:
                    persons_to_use = st.session_state["persons_df"].copy()

                    if not include_persons_without_tours:
                        persons_with_tours = st.session_state["tours_df"]['person_id'].unique()
                        persons_to_use = persons_to_use[
                            persons_to_use['person_id'].isin(persons_with_tours)
                        ]

                    xml_string = generate_matsim_population_xml(
                        persons_to_use,
                        st.session_state["hh_df"],
                        st.session_state["tours_df"],
                        st.session_state["trips_df"],
                        zones_gdf
                    )

                    st.session_state["matsim_xml"] = xml_string

                    st.success(f"✅ 成功生成包含 {len(persons_to_use)} 个 persons 的 MATSim population XML")

                except Exception as e:
                    st.error(f"❌ 生成失败：{e}")
                    import traceback
                    st.code(traceback.format_exc())

        # 显示和下载XML
        if "matsim_xml" in st.session_state and st.session_state["matsim_xml"] is not None:

            st.markdown("### 📄 XML 预览")

            xml_lines = st.session_state["matsim_xml"].split('\n')
            preview_lines = min(50, len(xml_lines))

            st.code('\n'.join(xml_lines[:preview_lines]), language='xml')

            if len(xml_lines) > preview_lines:
                st.info(f"显示前 {preview_lines} 行，共 {len(xml_lines)} 行")

            xml_bytes = st.session_state["matsim_xml"].encode('utf-8')
            file_size_mb = len(xml_bytes) / (1024 * 1024)

            st.metric("文件大小", f"{file_size_mb:.2f} MB")

            # DTD 验证
            st.markdown("### ✅ DTD 验证")

            col_v1, col_v2 = st.columns([1, 2])

            with col_v1:
                if st.button("🔍 验证 XML (DTD)"):
                    with st.spinner("正在验证..."):
                        try:
                            is_valid, errors = validate_matsim_xml_against_dtd(
                                st.session_state["matsim_xml"]
                            )

                            if is_valid:
                                st.success("✅ XML 符合 population_v6.dtd 规范")
                            else:
                                st.error("❌ XML 不符合 DTD 规范")
                                st.markdown("**错误列表：**")
                                for error in errors:
                                    st.write(f"- {error}")
                        except ImportError:
                            st.warning("⚠️ 需要安装 lxml 库才能进行 DTD 验证")
                            st.code("pip install lxml")
                        except Exception as e:
                            st.error(f"验证失败：{e}")

            with col_v2:
                with st.expander("📖 查看 population_v6.dtd"):
                    st.code(DTD_CONTENT, language='xml')

            # 下载按钮
            st.markdown("### 📥 下载 MATSim Files")

            col_dl1, col_dl2, col_dl3 = st.columns(3)

            with col_dl1:
                st.download_button(
                    label="📥 下载 population.xml",
                    data=xml_bytes,
                    file_name="population.xml",
                    mime="application/xml",
                    use_container_width=True
                )

            with col_dl2:
                xml_gz = gzip.compress(xml_bytes)
                st.download_button(
                    label="📥 下载 population.xml.gz",
                    data=xml_gz,
                    file_name="population.xml.gz",
                    mime="application/gzip",
                    use_container_width=True
                )
                st.caption(f"压缩后: {len(xml_gz) / (1024 * 1024):.2f} MB")

            with col_dl3:
                if st.button("📋 生成示例 config.xml", use_container_width=True):
                    config_xml = generate_sample_matsim_config(zones_gdf)
                    st.session_state["matsim_config"] = config_xml
                    st.success("✅ Config 已生成")

            if "matsim_config" in st.session_state and st.session_state["matsim_config"] is not None:
                st.markdown("### 📋 MATSim Config 预览")

                config_lines = st.session_state["matsim_config"].split('\n')
                st.code('\n'.join(config_lines[:30]), language='xml')

                st.download_button(
                    label="📥 下载 config.xml",
                    data=st.session_state["matsim_config"].encode('utf-8'),
                    file_name="config.xml",
                    mime="application/xml",
                )

    else:
        st.info("ℹ️ 请先生成 Tours 和 Trips 数据")

    # ============================================================
    # 页脚
    # ============================================================
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: gray; padding: 20px;'>
        <p><b>ActivitySim/MATSim 人口与出行生成工具 v5.0（完整版）</b></p>
        <p>🆕 新增功能：</p>
        <ul style='list-style: none; padding: 0;'>
            <li>✅ 多中心点管理（支持上传Shapefile计算中心）</li>
            <li>✅ 多坐标系支持（智能推荐中国常用坐标系）</li>
            <li>✅ 按区域类型完整参数配置（所有人口和出行参数）</li>
            <li>✅ 不同中心点zones用不同颜色显示</li>
            <li>✅ 15个完整可视化图表</li>
            <li>✅ 完整的DTD验证和数据质量检查</li>
        </ul>
        <p>💡 完全兼容原有功能，可自由选择使用模式</p>
        <p style='font-size: 12px; margin-top: 10px;'>Powered by Streamlit | 支持 ActivitySim & MATSim</p>
        </div>
        """,
        unsafe_allow_html=True
    )


# ============================================================
#  程序入口
# ============================================================

if __name__ == "__main__":
    main()

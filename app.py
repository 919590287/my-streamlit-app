import zipfile
from dataclasses import dataclass
from typing import Dict, List, Tuple, Set, Optional
import gzip
import re
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import box, Point

import streamlit as st
import pydeck as pdk

import matplotlib.pyplot as plt
import matplotlib
from matplotlib import font_manager
import seaborn as sns
import warnings

warnings.filterwarnings('ignore')


# ============================================================
#  字段定义模块 - 定义各表的必要字段
# ============================================================

@dataclass
class RequiredFields:
    """定义各数据表的必要字段"""

    # Households 必要字段
    HOUSEHOLDS_REQUIRED = {
        'household_id': 'int',
        'home_zone_id': 'int',
        'income': 'float',
        'autos': 'int',
        'hhsize': 'int',
    }

    # Persons 必要字段
    PERSONS_REQUIRED = {
        'person_id': 'int',
        'household_id': 'int',
        'age': 'int',
        'sex': 'str',
        'is_worker': 'int',
        'is_student': 'int',
        'license': 'int',
    }

    # Tours 必要字段
    TOURS_REQUIRED = {
        'tour_id': 'int',
        'person_id': 'int',
        'household_id': 'int',
        'tour_type': 'str',
        'origin_zone_id': 'int',
        'destination_zone_id': 'int',
        'start_time': 'int',
        'end_time': 'int',
    }

    # Trips 必要字段
    TRIPS_REQUIRED = {
        'trip_id': 'int',
        'tour_id': 'int',
        'person_id': 'int',
        'household_id': 'int',
        'origin_zone_id': 'int',
        'destination_zone_id': 'int',
        'purpose': 'str',
        'mode': 'str',
        'departure_time': 'int',
        'arrival_time': 'int',
    }

    # Zones 必要字段
    ZONES_REQUIRED = {
        'zone_id': 'int',
        'centroid_x': 'float',
        'centroid_y': 'float',
    }


def validate_dataframe_fields(
        df: pd.DataFrame,
        required_fields: Dict[str, str],
        data_name: str = "数据"
) -> Tuple[bool, List[str], List[str]]:
    """
    验证DataFrame是否包含必要字段

    Args:
        df: 要验证的DataFrame
        required_fields: 必要字段字典 {字段名: 类型}
        data_name: 数据名称（用于错误提示）

    Returns:
        (is_valid, missing_fields, extra_fields)
    """
    if df is None or df.empty:
        return False, list(required_fields.keys()), []

    df_columns = set(df.columns)
    required_columns = set(required_fields.keys())

    missing_fields = list(required_columns - df_columns)
    extra_fields = list(df_columns - required_columns)

    is_valid = len(missing_fields) == 0

    return is_valid, missing_fields, extra_fields


def try_convert_field_types(
        df: pd.DataFrame,
        required_fields: Dict[str, str]
) -> pd.DataFrame:
    """
    尝试将DataFrame字段转换为必要的类型

    Args:
        df: 输入DataFrame
        required_fields: 必要字段字典 {字段名: 类型}

    Returns:
        转换后的DataFrame
    """
    df = df.copy()

    type_mapping = {
        'int': 'int64',
        'float': 'float64',
        'str': 'str',
    }

    for field, field_type in required_fields.items():
        if field in df.columns:
            try:
                target_type = type_mapping.get(field_type, field_type)
                if target_type == 'int64':
                    df[field] = pd.to_numeric(df[field], errors='coerce').fillna(0).astype('int64')
                elif target_type == 'float64':
                    df[field] = pd.to_numeric(df[field], errors='coerce').fillna(0.0).astype('float64')
                elif target_type == 'str':
                    df[field] = df[field].astype(str)
            except Exception as e:
                st.warning(f"字段 {field} 类型转换失败: {e}")

    return df


def show_field_validation_ui(
        validation_result: Tuple[bool, List[str], List[str]],
        data_name: str
) -> None:
    """
    显示字段验证结果的UI

    Args:
        validation_result: validate_dataframe_fields 的返回值
        data_name: 数据名称
    """
    is_valid, missing_fields, extra_fields = validation_result

    if is_valid:
        st.success(f"✅ {data_name} 字段验证通过")
    else:
        st.error(f"❌ {data_name} 缺少必要字段")
        st.write("**缺少的字段：**")
        for field in missing_fields:
            st.write(f"  - `{field}`")

    if extra_fields:
        with st.expander(f"📋 {data_name} 包含额外字段（将被保留）"):
            for field in extra_fields:
                st.write(f"  - `{field}`")


# ============================================================
#  配置中文字体 - 强制使用微软雅黑或宋体
# ============================================================

def setup_chinese_font():
    """配置matplotlib中文字体 - 强制使用微软雅黑或宋体"""
    import platform

    # 清除matplotlib缓存
    try:
        import shutil
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


def show_polygon_map(
        gdf: gpd.GeoDataFrame,
        fill_color=(0, 0, 255, 128),
        height: int = 400,
        label: str = ""
) -> None:
    """使用 pydeck 在底图上叠加多边形图层"""
    if gdf is None or gdf.empty:
        st.info("没有几何数据可展示。")
        return

    gdf_ll = gdf.to_crs(epsg=4326).copy()
    data = []

    for geom in gdf_ll.geometry:
        if geom.is_empty:
            continue
        if geom.geom_type == "Polygon":
            coords = list(geom.exterior.coords)
            data.append({"polygon": coords})
        elif geom.geom_type == "MultiPolygon":
            for poly in geom.geoms:
                coords = list(poly.exterior.coords)
                data.append({"polygon": coords})

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
        get_fill_color=fill_color,
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
#  人口生成相关
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


@dataclass
class PopulationConfig:
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


def generate_households_and_persons(
        zones_gdf: gpd.GeoDataFrame,
        cfg: PopulationConfig,
        seed: int = 42
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """生成 households 和 persons"""
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
#  Tour & Trip 生成模块
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


def generate_tours_and_trips(
        persons_df: pd.DataFrame,
        households_df: pd.DataFrame,
        zones_gdf: gpd.GeoDataFrame,
        config: TourTripConfig,
        seed: int = 42
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """生成ActivitySim风格的tour和trip数据"""

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
#  MATSim Population XML 生成（支持扩展字段）
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


def infer_java_class(value) -> str:
    """推断值的Java类型"""
    if pd.isna(value):
        return 'java.lang.String'

    if isinstance(value, (bool, np.bool_)):
        return 'java.lang.Boolean'
    elif isinstance(value, (int, np.integer)):
        return 'java.lang.Integer'
    elif isinstance(value, (float, np.floating)):
        return 'java.lang.Double'
    else:
        return 'java.lang.String'


def value_to_string(value) -> str:
    """将值转换为XML字符串"""
    if pd.isna(value):
        return ''

    if isinstance(value, (bool, np.bool_)):
        return 'true' if value else 'false'
    elif isinstance(value, (int, np.integer)):
        return str(int(value))
    elif isinstance(value, (float, np.floating)):
        return f'{float(value):.6f}'
    else:
        return str(value)


def generate_matsim_population_xml(
        persons_df: pd.DataFrame,
        households_df: pd.DataFrame,
        tours_df: pd.DataFrame,
        trips_df: pd.DataFrame,
        zones_gdf: gpd.GeoDataFrame
) -> str:
    """生成符合 MATSim population_v6.dtd 的 XML 字符串（支持扩展字段）"""
    from xml.etree.ElementTree import Element, SubElement, tostring
    from xml.dom import minidom

    zone_coords = {}
    for _, zone in zones_gdf.iterrows():
        zone_coords[zone['zone_id']] = (zone['centroid_x'], zone['centroid_y'])

    # 识别标准字段和扩展字段
    standard_person_fields = set(RequiredFields.PERSONS_REQUIRED.keys())
    standard_person_fields.update(['person_type'])  # 添加常用字段

    all_person_fields = set(persons_df.columns)
    extra_person_fields = all_person_fields - standard_person_fields

    # Merge households信息
    persons_full = persons_df.merge(
        households_df[['household_id', 'home_zone_id', 'autos']],
        on='household_id',
        how='left'
    )

    # 识别household的扩展字段
    standard_hh_fields = set(RequiredFields.HOUSEHOLDS_REQUIRED.keys())
    standard_hh_fields.update(['income_segment', 'area_type', 'workers', 'children'])
    all_hh_fields = set(households_df.columns)
    extra_hh_fields = all_hh_fields - standard_hh_fields

    population = Element('population')

    for person_id in sorted(persons_full['person_id'].unique()):
        person_data = persons_full[persons_full['person_id'] == person_id].iloc[0]
        person_elem = SubElement(population, 'person', id=str(person_id))

        person_attrs = SubElement(person_elem, 'attributes')

        # 标准属性
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

        # 添加is_student
        student_attr = SubElement(person_attrs, 'attribute', name='isStudent', **{'class': 'java.lang.Boolean'})
        student_attr.text = 'true' if int(person_data['is_student']) == 1 else 'false'

        # 添加person_type
        if 'person_type' in person_data:
            ptype_attr = SubElement(person_attrs, 'attribute', name='personType', **{'class': 'java.lang.String'})
            ptype_attr.text = str(person_data['person_type'])

        # 添加person的扩展字段
        for field in extra_person_fields:
            if field in person_data and pd.notna(person_data[field]):
                value = person_data[field]
                java_class = infer_java_class(value)
                attr_elem = SubElement(person_attrs, 'attribute',
                                       name=field,
                                       **{'class': java_class})
                attr_elem.text = value_to_string(value)

        # 添加household的扩展字段（通过household_id关联）
        hh_id = int(person_data['household_id'])
        hh_data = households_df[households_df['household_id'] == hh_id]
        if not hh_data.empty:
            hh_data = hh_data.iloc[0]
            for field in extra_hh_fields:
                if field in hh_data and pd.notna(hh_data[field]):
                    value = hh_data[field]
                    java_class = infer_java_class(value)
                    attr_elem = SubElement(person_attrs, 'attribute',
                                           name=f'hh_{field}',  # 加前缀避免冲突
                                           **{'class': java_class})
                    attr_elem.text = value_to_string(value)

        # 生成plan
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
        <param name="coordinateSystem" value="EPSG:3857"/>
    </module>
</config>
"""
    return config


# ============================================================
#  可视化图表生成功能
# ============================================================

def create_visualization_charts(
        hh_df: pd.DataFrame,
        persons_df: pd.DataFrame,
        tours_df: pd.DataFrame = None,
        trips_df: pd.DataFrame = None
):
    """创建所有可视化图表"""

    setup_chinese_font()

    figures = {}

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
    if 'income_segment' in hh_df.columns:
        fig2, ax2 = plt.subplots(figsize=(12, 7))
        income_counts = hh_df['income_segment'].value_counts()
        colors = {'low': '#e74c3c', 'mid': '#3498db', 'high': '#2ecc71'}
        income_labels = {'low': '低收入', 'mid': '中收入', 'high': '高收入'}

        sorted_segments = ['low', 'mid', 'high']
        sorted_counts = [income_counts.get(seg, 0) for seg in sorted_segments]
        sorted_labels = [income_labels.get(seg, seg) for seg in sorted_segments]
        sorted_colors = [colors.get(seg, '#95a5a6') for seg in sorted_segments]

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
    if 'autos' in hh_df.columns:
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
    if 'sex' in persons_df.columns:
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
    if 'person_type' in persons_df.columns:
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
    if 'is_worker' in persons_df.columns and 'is_student' in persons_df.columns:
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
    if 'license' in persons_df.columns:
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
        if 'tour_type' in tours_df.columns:
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
        if 'start_time' in tours_df.columns and 'end_time' in tours_df.columns:
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
        if 'mode' in trips_df.columns:
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
        if 'travel_time' in trips_df.columns:
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

        # 13. 出行目的分布
        if 'purpose' in trips_df.columns:
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
        if 'departure_time' in trips_df.columns and 'arrival_time' in trips_df.columns:
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
#  Streamlit GUI 主程序（支持CSV上传）
# ============================================================

def main():
    st.set_page_config(page_title="人口与分区生成工具", layout="wide")

    # 初始化 session_state
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

    st.title("🚗 ActivitySim/MATSim 人口与出行生成工具")

    st.markdown(
        """
        **功能说明：**
        1. 📍 上传研究范围 Shapefile（ZIP）  
        2. 🗺️ 自动生成分区 zones（规则方格 / 导入现有分区）  
        3. 👥 生成或上传 households.csv 与 persons.csv（支持扩展字段）
        4. 🚌 生成或上传 tours.csv 和 trips.csv（支持扩展字段）
        5. 🔧 生成 MATSim population.xml 文件（包含所有扩展字段）
        6. ✅ DTD验证和数据质量检查
        7. 📊 生成可视化图表
        8. 📥 下载所有结果文件
        """
    )

    # --------------------------------------------------------
    # 侧边栏：全局参数
    # --------------------------------------------------------
    st.sidebar.header("⚙️ 全局设置")

    seed = st.sidebar.number_input("随机种子", value=42, step=1)
    total_households = st.sidebar.number_input("总家庭数", value=1000, min_value=1, step=100)
    max_persons_per_household = st.sidebar.number_input("单户最大人数", value=6, min_value=1, step=1)

    st.sidebar.markdown("---")
    st.sidebar.subheader("📍 研究范围")

    study_area_file = st.sidebar.file_uploader(
        "上传研究范围 Shapefile ZIP",
        type=["zip"],
        help="包含 .shp/.dbf/.shx/.prj 文件的 ZIP 压缩包"
    )

    if study_area_file is None:
        st.warning("⚠️ 请先在左侧上传研究范围 Shapefile ZIP。")
        return

    study_gdf = read_zipped_shapefile(study_area_file)
    if study_gdf is None or study_gdf.empty:
        st.error("❌ 研究范围读取失败或为空，请检查数据。")
        return

    study_gdf = ensure_projected(study_gdf)

    show_polygon_map(
        study_gdf,
        fill_color=(0, 0, 255, 128),
        label="### 📍 研究范围预览"
    )

    # --------------------------------------------------------
    # 1️⃣ 分区生成
    # --------------------------------------------------------
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

        cell_size = st.number_input("格网单元边长(米)", value=500.0, min_value=50.0, step=50.0)
        min_overlap_ratio = st.slider("格网与研究范围重叠比例阈值", 0.0, 1.0, 0.25, 0.05)

        st.markdown("**区域类型：按与中心点距离分环**")

        center_mode = st.radio(
            "中心点选择",
            options=["使用研究范围几何中心", "手动输入坐标"],
            index=0,
            horizontal=True,
        )

        if center_mode == "使用研究范围几何中心":
            center_geom = study_gdf.unary_union.centroid
            center_x, center_y = center_geom.x, center_geom.y
            st.info(f"✓ 中心点: (x={center_x:.1f}, y={center_y:.1f})")
        else:
            center_x = st.number_input("中心点 X", value=float(study_gdf.unary_union.centroid.x))
            center_y = st.number_input("中心点 Y", value=float(study_gdf.unary_union.centroid.y))

        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1:
            r1 = st.number_input("内圈半径(m)", value=3000.0, min_value=0.0, step=500.0)
            t1 = st.text_input("内圈 area_type", value="CBD")
        with col_r2:
            r2 = st.number_input("中圈半径(m)", value=10000.0, min_value=r1, step=1000.0)
            t2 = st.text_input("中圈 area_type", value="urban")
        with col_r3:
            t3 = st.text_input("外圈 area_type", value="suburban")

        if st.button("🗺️ 生成 Zones"):
            with st.spinner("正在生成方格 zones ..."):
                tmp_zones = generate_grid_zones(study_gdf, cell_size, min_overlap_ratio)
                if tmp_zones is not None and not tmp_zones.empty:
                    tmp_zones = assign_area_type_rings(
                        tmp_zones,
                        (center_x, center_y),
                        [(r1, t1), (r2, t2), (None, t3)]
                    )
                    tmp_zones["zone_weight"] = tmp_zones.geometry.area
                    st.session_state["zones_gdf"] = tmp_zones
                    zones_gdf = tmp_zones
                    st.success(f"✅ 成功生成 {len(zones_gdf)} 个 zones")

    else:
        st.markdown("**上传已有 zones Shapefile ZIP**")
        zones_file = st.file_uploader("上传 zones Shapefile ZIP", type=["zip"], key="zones_zip")
        if zones_file is not None:
            zgdf_raw = read_zipped_shapefile(zones_file)
            if zgdf_raw is not None and not zgdf_raw.empty:
                zgdf_raw = ensure_projected(zgdf_raw, study_gdf.crs.to_string())

                st.write("原始 zones 字段:", list(zgdf_raw.columns))
                id_field = st.selectbox("选择作为 zone_id 的字段", options=list(zgdf_raw.columns))
                area_type_field = st.selectbox(
                    "选择作为 area_type 的字段",
                    options=["<无>"] + list(zgdf_raw.columns)
                )
                weight_field = st.selectbox(
                    "选择作为 zone_weight 的字段",
                    options=["<无>"] + list(zgdf_raw.columns)
                )

                if st.button("✓ 确认 zones 字段映射"):
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

    zones_gdf = st.session_state["zones_gdf"]

    if zones_gdf is None or zones_gdf.empty:
        st.warning("⚠️ 请先生成或导入 zones。")
        return

    show_polygon_map(zones_gdf, fill_color=(255, 0, 0, 128), label="### 🗺️ Zones 预览")

    # --------------------------------------------------------
    # --------------------------------------------------------
    # 2️⃣ 人口数据：生成 或 上传CSV
    # --------------------------------------------------------
    st.markdown("---")
    st.subheader("2️⃣ 人口数据 (Households & Persons)")

    pop_data_mode = st.radio(
        "选择人口数据来源",
        options=["🎲 自动生成", "📤 上传CSV文件"],
        index=0,
        horizontal=True,
        key="pop_mode"
    )

    if pop_data_mode == "📤 上传CSV文件":
        st.markdown("### 📤 上传 Households 和 Persons CSV")

        col_upload1, col_upload2 = st.columns(2)

        with col_upload1:
            st.markdown("#### Households CSV")
            hh_uploaded = st.file_uploader("上传 households.csv", type=['csv'], key='hh_upload')

            if hh_uploaded is not None:
                try:
                    hh_df_uploaded = pd.read_csv(hh_uploaded)

                    # 验证字段
                    validation = validate_dataframe_fields(
                        hh_df_uploaded,
                        RequiredFields.HOUSEHOLDS_REQUIRED,
                        "Households"
                    )
                    show_field_validation_ui(validation, "Households")

                    is_valid, missing, extra = validation

                    if is_valid:
                        # 类型转换
                        hh_df_uploaded = try_convert_field_types(
                            hh_df_uploaded,
                            RequiredFields.HOUSEHOLDS_REQUIRED
                        )

                        st.session_state["hh_df"] = hh_df_uploaded
                        st.success(f"✅ 成功加载 {len(hh_df_uploaded)} 个 households")

                        with st.expander("预览数据"):
                            st.dataframe(hh_df_uploaded.head(10))
                    else:
                        st.error("❌ 请确保CSV包含所有必要字段后重新上传")

                except Exception as e:
                    st.error(f"读取CSV失败：{e}")

        with col_upload2:
            st.markdown("#### Persons CSV")
            persons_uploaded = st.file_uploader("上传 persons.csv", type=['csv'], key='persons_upload')

            if persons_uploaded is not None:
                try:
                    persons_df_uploaded = pd.read_csv(persons_uploaded)

                    # 验证字段
                    validation = validate_dataframe_fields(
                        persons_df_uploaded,
                        RequiredFields.PERSONS_REQUIRED,
                        "Persons"
                    )
                    show_field_validation_ui(validation, "Persons")

                    is_valid, missing, extra = validation

                    if is_valid:
                        # 类型转换
                        persons_df_uploaded = try_convert_field_types(
                            persons_df_uploaded,
                            RequiredFields.PERSONS_REQUIRED
                        )

                        st.session_state["persons_df"] = persons_df_uploaded
                        st.success(f"✅ 成功加载 {len(persons_df_uploaded)} 个 persons")

                        with st.expander("预览数据"):
                            st.dataframe(persons_df_uploaded.head(10))
                    else:
                        st.error("❌ 请确保CSV包含所有必要字段后重新上传")

                except Exception as e:
                    st.error(f"读取CSV失败：{e}")

    else:  # 自动生成模式
        st.markdown("### 🎲 人口生成模型参数配置")

        # 使用tabs代替嵌套expander
        param_tabs = st.tabs([
            "家庭规模",
            "收入分段",
            "汽车拥有量",
            "年龄与就业"
        ])

        # Tab 1: 家庭规模分布
        with param_tabs[0]:
            st.markdown("#### 家庭规模分布")
            col_h1, col_h2, col_h3, col_h4, col_h5 = st.columns(5)
            p_h1 = col_h1.number_input("1人户", 0.0, 1.0, 0.30, 0.01, key="h1")
            p_h2 = col_h2.number_input("2人户", 0.0, 1.0, 0.40, 0.01, key="h2")
            p_h3 = col_h3.number_input("3人户", 0.0, 1.0, 0.20, 0.01, key="h3")
            p_h4 = col_h4.number_input("4人户", 0.0, 1.0, 0.10, 0.01, key="h4")
            p_h5p = col_h5.number_input("5人+", 0.0, 1.0, 0.00, 0.01, key="h5")

            hhsize_dist = {"1": p_h1, "2": p_h2, "3": p_h3, "4": p_h4, "5+": p_h5p}

        # Tab 2: 收入分段
        with param_tabs[1]:
            st.markdown("#### 收入分段设置")

            col_l1, col_l2 = st.columns(2)
            low_min = col_l1.number_input("低收入最小值", 0.0, 1e9, 0.0, 1000.0, key="low_min")
            low_max = col_l2.number_input("低收入最大值", 0.0, 1e9, 300000.0, 1000.0, key="low_max")

            col_m1, col_m2 = st.columns(2)
            mid_min = col_m1.number_input("中收入最小值", 0.0, 1e9, 300000.0, 1000.0, key="mid_min")
            mid_max = col_m2.number_input("中收入最大值", 0.0, 1e9, 600000.0, 1000.0, key="mid_max")

            col_hh1, col_hh2 = st.columns(2)
            high_min = col_hh1.number_input("高收入最小值", 0.0, 1e9, 600000.0, 1000.0, key="high_min")
            high_max = col_hh2.number_input("高收入最大值", 0.0, 1e9, 2000000.0, 1000.0, key="high_max")

            st.markdown("#### 收入段权重")
            col_w1, col_w2, col_w3 = st.columns(3)
            w_low = col_w1.number_input("低收入占比", 0.0, 1.0, 0.3, 0.01, key="w_low")
            w_mid = col_w2.number_input("中收入占比", 0.0, 1.0, 0.5, 0.01, key="w_mid")
            w_high = col_w3.number_input("高收入占比", 0.0, 1.0, 0.2, 0.01, key="w_high")

            income_segments = {
                "low": (low_min, low_max),
                "mid": (mid_min, mid_max),
                "high": (high_min, high_max)
            }
            income_segment_weights = {"low": w_low, "mid": w_mid, "high": w_high}

        # Tab 3: 汽车拥有量分布
        with param_tabs[2]:
            st.markdown("#### 汽车拥有量分布（按收入和家庭规模）")

            autos_by_income_and_hhsize: Dict[str, Dict[str, List[float]]] = {}

            for seg in ["low", "mid", "high"]:
                st.markdown(f"**{seg.upper()} 收入段**")
                autos_by_income_and_hhsize[seg] = {}

                col_seg1, col_seg2, col_seg3 = st.columns(3)

                for idx, (col, hh_cat) in enumerate([(col_seg1, "1"), (col_seg2, "2"), (col_seg3, "3+")]):
                    with col:
                        st.caption(f"{hh_cat}人户")

                        if seg == "low":
                            default0, default1 = (0.8, 0.2) if hh_cat == "1" else (0.6, 0.4) if hh_cat == "2" else (
                            0.4, 0.4)
                        elif seg == "mid":
                            default0, default1 = (0.5, 0.5) if hh_cat == "1" else (0.3, 0.6) if hh_cat == "2" else (
                            0.2, 0.5)
                        else:
                            default0, default1 = (0.3, 0.4) if hh_cat == "1" else (0.2, 0.4) if hh_cat == "2" else (
                            0.1, 0.4)

                        p0 = st.number_input(
                            "无车", 0.0, 1.0, default0, 0.05,
                            key=f"auto_{seg}_{hh_cat}_0"
                        )
                        p1 = st.number_input(
                            "1车", 0.0, 1.0, default1, 0.05,
                            key=f"auto_{seg}_{hh_cat}_1"
                        )

                        s = p0 + p1
                        if s > 1.0:
                            p0, p1, p2 = p0 / s, p1 / s, 0.0
                        else:
                            p2 = 1.0 - s

                        st.caption(f"2+车: {p2:.2f}")
                        autos_by_income_and_hhsize[seg][hh_cat] = [p0, p1, p2]

                st.markdown("---")

        # Tab 4: 年龄结构与劳动/在学/驾照率
        with param_tabs[3]:
            st.markdown("#### 年龄结构")
            col_a1, col_a2, col_a3, col_a4, col_a5 = st.columns(5)
            s_0_5 = col_a1.number_input("0-5岁", 0.0, 1.0, 0.05, 0.01, key="age_0_5")
            s_6_17 = col_a2.number_input("6-17岁", 0.0, 1.0, 0.15, 0.01, key="age_6_17")
            s_18_22 = col_a3.number_input("18-22岁", 0.0, 1.0, 0.10, 0.01, key="age_18_22")
            s_23_64 = col_a4.number_input("23-64岁", 0.0, 1.0, 0.55, 0.01, key="age_23_64")
            s_65p = col_a5.number_input("65+岁", 0.0, 1.0, 0.15, 0.01, key="age_65p")

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
            wr_16_17 = col_w0.number_input("16-17岁", 0.0, 1.0, 0.05, 0.05, key="work_16_17")
            wr_18_22 = col_w1.number_input("18-22岁", 0.0, 1.0, 0.30, 0.05, key="work_18_22")
            wr_23_59 = col_w2.number_input("23-59岁", 0.0, 1.0, 0.80, 0.05, key="work_23_59")
            wr_60_64 = col_w3.number_input("60-64岁", 0.0, 1.0, 0.40, 0.05, key="work_60_64")
            wr_65p = col_w4.number_input("65+岁就业", 0.0, 1.0, 0.10, 0.05, key="work_65p")

            worker_rate_by_age = {
                "16-17": wr_16_17, "18-22": wr_18_22, "23-59": wr_23_59,
                "60-64": wr_60_64, "65+": wr_65p,
            }

            st.markdown("#### 在学率")
            col_s1, col_s2 = st.columns(2)
            sr_6_17 = col_s1.number_input("6-17岁在学率", 0.0, 1.0, 0.95, 0.05, key="student_6_17")
            sr_18_22 = col_s2.number_input("18-22岁在学率", 0.0, 1.0, 0.70, 0.05, key="student_18_22")

            student_rate_by_age = {"6-17": sr_6_17, "18-22": sr_18_22}

            st.markdown("#### 驾照率")
            col_lc1, col_lc2, col_lc3, col_lc4 = st.columns(4)
            lr_18_22 = col_lc1.number_input("18-22岁驾照", 0.0, 1.0, 0.50, 0.05, key="license_18_22")
            lr_23_59 = col_lc2.number_input("23-59岁驾照", 0.0, 1.0, 0.90, 0.05, key="license_23_59")
            lr_60_69 = col_lc3.number_input("60-69岁驾照", 0.0, 1.0, 0.70, 0.05, key="license_60_69")
            lr_70p = col_lc4.number_input("70+岁驾照", 0.0, 1.0, 0.40, 0.05, key="license_70p")

            license_rate_by_age = {
                "18-22": lr_18_22, "23-59": lr_23_59,
                "60-69": lr_60_69, "70+": lr_70p,
            }

        # 构建配置对象
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

        # 生成按钮
        st.markdown("---")
        if st.button("🏠 生成 Households & Persons", type="primary", use_container_width=True):
            with st.spinner("正在生成 households 和 persons ..."):
                try:
                    hh_df, persons_df = generate_households_and_persons(zones_gdf, cfg, seed=int(seed))
                    st.session_state["hh_df"] = hh_df
                    st.session_state["persons_df"] = persons_df
                    st.success(f"✅ 生成 {len(hh_df)} 个家庭, {len(persons_df)} 个个人")
                except Exception as e:
                    st.error(f"❌ 生成失败：{e}")
                    import traceback
                    st.code(traceback.format_exc())

    # 显示人口数据（无论是生成的还是上传的）
    if st.session_state["hh_df"] is not None and st.session_state["persons_df"] is not None:
        hh_df = st.session_state["hh_df"]
        persons_df = st.session_state["persons_df"]

        st.markdown("---")
        st.markdown("#### 📊 数据预览")

        tab1, tab2 = st.tabs(["Households", "Persons"])

        with tab1:
            st.dataframe(hh_df.head(20), use_container_width=True)
            st.caption(f"共 {len(hh_df)} 行 × {len(hh_df.columns)} 列")

        with tab2:
            st.dataframe(persons_df.head(20), use_container_width=True)
            st.caption(f"共 {len(persons_df)} 行 × {len(persons_df.columns)} 列")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("家庭总数", len(hh_df))
        with col2:
            st.metric("个人总数", len(persons_df))
        with col3:
            avg_hhsize = len(persons_df) / len(hh_df) if len(hh_df) > 0 else 0
            st.metric("平均家庭规模", f"{avg_hhsize:.2f}")

        # 生成可视化图表
        st.markdown("---")
        st.subheader("📊 人口数据可视化")

        if st.button("🎨 生成人口可视化图表", use_container_width=True):
            with st.spinner("正在生成图表..."):
                try:
                    figures = create_visualization_charts(hh_df, persons_df)

                    st.success(f"✅ 成功生成 {len(figures)} 个图表")

                    for name, fig in figures.items():
                        st.pyplot(fig)
                        plt.close(fig)

                    figures_download = create_visualization_charts(hh_df, persons_df)
                    zip_data = save_all_visualizations(figures_download, "population")
                    st.download_button(
                        "📥 下载所有人口图表（ZIP）",
                        data=zip_data,
                        file_name="population_visualizations.zip",
                        mime="application/zip",
                        use_container_width=True
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

        st.markdown("#### 📥 下载数据")
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
    # --------------------------------------------------------
    # 3️⃣ Tour & Trip：生成 或 上传CSV
    # --------------------------------------------------------
    st.markdown("---")
    st.subheader("3️⃣ Tour & Trip 数据")

    if st.session_state["hh_df"] is None or st.session_state["persons_df"] is None:
        st.info("ℹ️ 请先生成或上传人口数据")
    else:
        trip_data_mode = st.radio(
            "选择出行数据来源",
            options=["🎲 自动生成", "📤 上传CSV文件"],
            index=0,
            horizontal=True,
            key="trip_mode"
        )

        if trip_data_mode == "📤 上传CSV文件":
            st.markdown("### 📤 上传 Tours 和 Trips CSV")

            col_upload3, col_upload4 = st.columns(2)

            with col_upload3:
                st.markdown("#### Tours CSV")
                tours_uploaded = st.file_uploader("上传 tours.csv", type=['csv'], key='tours_upload')

                if tours_uploaded is not None:
                    try:
                        tours_df_uploaded = pd.read_csv(tours_uploaded)

                        validation = validate_dataframe_fields(
                            tours_df_uploaded,
                            RequiredFields.TOURS_REQUIRED,
                            "Tours"
                        )
                        show_field_validation_ui(validation, "Tours")

                        is_valid, missing, extra = validation

                        if is_valid:
                            tours_df_uploaded = try_convert_field_types(
                                tours_df_uploaded,
                                RequiredFields.TOURS_REQUIRED
                            )

                            st.session_state["tours_df"] = tours_df_uploaded
                            st.success(f"✅ 成功加载 {len(tours_df_uploaded)} 个 tours")

                            with st.expander("预览数据"):
                                st.dataframe(tours_df_uploaded.head(10))
                        else:
                            st.error("❌ 请确保CSV包含所有必要字段后重新上传")

                    except Exception as e:
                        st.error(f"读取CSV失败：{e}")

            with col_upload4:
                st.markdown("#### Trips CSV")
                trips_uploaded = st.file_uploader("上传 trips.csv", type=['csv'], key='trips_upload')

                if trips_uploaded is not None:
                    try:
                        trips_df_uploaded = pd.read_csv(trips_uploaded)

                        validation = validate_dataframe_fields(
                            trips_df_uploaded,
                            RequiredFields.TRIPS_REQUIRED,
                            "Trips"
                        )
                        show_field_validation_ui(validation, "Trips")

                        is_valid, missing, extra = validation

                        if is_valid:
                            trips_df_uploaded = try_convert_field_types(
                                trips_df_uploaded,
                                RequiredFields.TRIPS_REQUIRED
                            )

                            st.session_state["trips_df"] = trips_df_uploaded
                            st.success(f"✅ 成功加载 {len(trips_df_uploaded)} 个 trips")

                            with st.expander("预览数据"):
                                st.dataframe(trips_df_uploaded.head(10))
                        else:
                            st.error("❌ 请确保CSV包含所有必要字段后重新上传")

                    except Exception as e:
                        st.error(f"读取CSV失败：{e}")

        else:  # 自动生成模式
            # （保留原有的Tour/Trip生成参数配置...由于字数限制，这部分代码与原来相同）
            with st.expander("Tour 生成参数", expanded=True):
                st.markdown("#### Tour Frequency")

                col_tf1, col_tf2 = st.columns(2)
                with col_tf1:
                    st.markdown("**Full-time worker**")
                    worker_0 = st.slider("0 tours", 0.0, 1.0, 0.05, 0.05, key="worker_0")
                    worker_1 = st.slider("1 tour", 0.0, 1.0, 0.60, 0.05, key="worker_1")
                    worker_2 = st.slider("2 tours", 0.0, 1.0, 0.30, 0.05, key="worker_2")
                    worker_3 = st.slider("3+ tours", 0.0, 1.0, 0.05, 0.05, key="worker_3")

                with col_tf2:
                    st.markdown("**University student**")
                    student_0 = st.slider("0 tours", 0.0, 1.0, 0.10, 0.05, key="student_0")
                    student_1 = st.slider("1 tour", 0.0, 1.0, 0.70, 0.05, key="student_1")
                    student_2 = st.slider("2 tours", 0.0, 1.0, 0.20, 0.05, key="student_2")

                col_tf3, col_tf4 = st.columns(2)
                with col_tf3:
                    st.markdown("**Non-worker**")
                    nonworker_0 = st.slider("0 tours", 0.0, 1.0, 0.30, 0.05, key="nonworker_0")
                    nonworker_1 = st.slider("1 tour", 0.0, 1.0, 0.50, 0.05, key="nonworker_1")
                    nonworker_2 = st.slider("2 tours", 0.0, 1.0, 0.20, 0.05, key="nonworker_2")

                with col_tf4:
                    st.markdown("**Child**")
                    child_0 = st.slider("0 tours", 0.0, 1.0, 0.20, 0.05, key="child_0")
                    child_1 = st.slider("1 tour", 0.0, 1.0, 0.70, 0.05, key="child_1")
                    child_2 = st.slider("2 tours", 0.0, 1.0, 0.10, 0.05, key="child_2")

                tour_frequency = {
                    'full_time_worker': {0: worker_0, 1: worker_1, 2: worker_2, 3: worker_3},
                    'university_student': {0: student_0, 1: student_1, 2: student_2},
                    'non_worker': {0: nonworker_0, 1: nonworker_1, 2: nonworker_2},
                    'child': {0: child_0, 1: child_1, 2: child_2},
                }

                st.markdown("#### Tour Type Distribution")

                col_tt1, col_tt2, col_tt3, col_tt4 = st.columns(4)
                tt_shop = col_tt1.number_input("Shopping", 0.0, 1.0, 0.30, 0.05)
                tt_social = col_tt2.number_input("Social", 0.0, 1.0, 0.25, 0.05)
                tt_dining = col_tt3.number_input("Dining", 0.0, 1.0, 0.20, 0.05)
                tt_escort = col_tt4.number_input("Escort", 0.0, 1.0, 0.15, 0.05)
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
                }

                st.markdown("#### Time Windows (HH:MM:SS格式)")

                col_tw1, col_tw2 = st.columns(2)
                with col_tw1:
                    work_start_early = time_input_hms("Work-最早出发", 420, "work_early")
                    work_start_late = time_input_hms("Work-最晚出发", 540, "work_late")
                    school_start_early = time_input_hms("School-最早出发", 390, "school_early")
                    school_start_late = time_input_hms("School-最晚出发", 480, "school_late")

                with col_tw2:
                    shop_start_early = time_input_hms("Shop-最早出发", 540, "shop_early")
                    shop_start_late = time_input_hms("Shop-最晚出发", 1140, "shop_late")
                    social_start_early = time_input_hms("Social-最早出发", 600, "social_early")
                    social_start_late = time_input_hms("Social-最晚出发", 1200, "social_late")

                time_windows = {
                    'work': (work_start_early, work_start_late),
                    'school': (school_start_early, school_start_late),
                    'shopping': (shop_start_early, shop_start_late),
                    'social': (social_start_early, social_start_late),
                    'dining': (660, 1260),
                    'escort': (420, 540),
                    'other': (480, 1200),
                }

                st.markdown("#### Duration (分钟)")

                col_dur1, col_dur2 = st.columns(2)
                with col_dur1:
                    work_dur_min = st.number_input("Work-最短", 60, 720, 420, 30)
                    work_dur_max = st.number_input("Work-最长", 60, 720, 600, 30)
                    school_dur_min = st.number_input("School-最短", 60, 720, 360, 30)
                    school_dur_max = st.number_input("School-最长", 60, 720, 480, 30)

                with col_dur2:
                    shop_dur_min = st.number_input("Shop-最短", 30, 480, 60, 15)
                    shop_dur_max = st.number_input("Shop-最长", 30, 480, 180, 15)
                    social_dur_min = st.number_input("Social-最短", 30, 480, 90, 15)
                    social_dur_max = st.number_input("Social-最长", 30, 480, 240, 15)

                duration_params = {
                    'work': (work_dur_min, work_dur_max),
                    'school': (school_dur_min, school_dur_max),
                    'shopping': (shop_dur_min, shop_dur_max),
                    'social': (social_dur_min, social_dur_max),
                    'dining': (60, 150),
                    'escort': (30, 60),
                    'other': (60, 240),
                }

                st.markdown("#### Destination & Stop")

                col_dest1, col_dest2, col_dest3 = st.columns(3)

                with col_dest1:
                    max_distance = st.number_input("最大距离(米)", 1000.0, 100000.0, 30000.0, 1000.0)

                with col_dest2:
                    distance_decay = st.number_input("距离衰减", 0.01, 2.0, 0.1, 0.01)

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

            if st.button("🚗 生成 Tours & Trips"):
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

                        st.success(f"✅ 生成 {len(tours_df)} 个 tours, {len(trips_df)} 个 trips")
                    except Exception as e:
                        st.error(f"❌ 生成失败：{e}")
                        import traceback
                        st.code(traceback.format_exc())

        # 显示Tour/Trip数据
        if st.session_state["tours_df"] is not None and st.session_state["trips_df"] is not None:
            tours_df = st.session_state["tours_df"]
            trips_df = st.session_state["trips_df"]

            st.markdown("#### 📊 数据预览")

            tab3, tab4 = st.tabs(["Tours", "Trips"])

            with tab3:
                st.dataframe(tours_df.head(20))
                st.caption(f"共 {len(tours_df)} 行 × {len(tours_df.columns)} 列")

            with tab4:
                st.dataframe(trips_df.head(20))
                st.caption(f"共 {len(trips_df)} 行 × {len(trips_df.columns)} 列")

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
                        figures = create_visualization_charts(
                            st.session_state["hh_df"],
                            st.session_state["persons_df"],
                            tours_df,
                            trips_df
                        )

                        st.success(f"✅ 成功生成 {len(figures)} 个图表")

                        for name, fig in figures.items():
                            st.pyplot(fig)
                            plt.close(fig)

                        figures_download = create_visualization_charts(
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

            # 下载
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

    # --------------------------------------------------------
    # 4️⃣ MATSim XML 生成
    # --------------------------------------------------------
    st.markdown("---")
    st.subheader("4️⃣ MATSim Population XML 生成")

    if st.session_state["tours_df"] is not None and st.session_state["trips_df"] is not None:

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

        if st.button("🚀 生成 MATSim Population XML"):
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

                    st.success(
                        f"✅ 成功生成包含 {len(persons_to_use)} 个 persons 的 MATSim population XML (包含所有扩展字段)")

                except Exception as e:
                    st.error(f"❌ 生成失败：{e}")
                    import traceback
                    st.code(traceback.format_exc())

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
        st.info("ℹ️ 请先生成或上传 Tours 和 Trips 数据")

    # 页脚
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: gray; padding: 20px;'>
        <p>ActivitySim/MATSim 人口与出行生成工具 v3.0</p>
        <p>✅ 新增：CSV上传功能、字段验证、扩展字段支持</p>
        </div>
        """,
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()

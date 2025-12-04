"""
MATSim 2024 Config.xml 配置器 - 完整重构版
面向新手的傻瓜式配置生成系统
"""

# ============================================================
# 服务器配置（必须在 import streamlit 之前）
# ============================================================
import os
os.environ["STREAMLIT_SERVER_MAX_UPLOAD_SIZE"] = "1000"   # 上传限制 1000MB
os.environ["STREAMLIT_SERVER_MAX_MESSAGE_SIZE"] = "1000"  # 消息限制 1000MB

# ============================================================
# 导入模块
# ============================================================
import streamlit as st
import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Dict, List, Optional, Tuple, Set
from enum import Enum
import gzip

# ============================================================
# 页面配置 / Page Configuration
# ============================================================
st.set_page_config(
    page_title="MATSim Config Generator | MATSim配置生成器",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# 自定义CSS样式 / Custom CSS Styles
# ============================================================
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E88E5;
        text-align: center;
        padding: 1rem;
        border-bottom: 3px solid #1E88E5;
        margin-bottom: 2rem;
    }
    .module-header {
        font-size: 1.5rem;
        font-weight: bold;
        color: #424242;
        background-color: #E3F2FD;
        padding: 0.8rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    .section-header {
        font-size: 1.2rem;
        font-weight: bold;
        color: #1565C0;
        padding: 0.5rem 0;
        border-bottom: 2px solid #90CAF9;
        margin: 1rem 0 0.5rem 0;
    }
    .warning-box {
        background-color: #FFF3E0;
        border-left: 4px solid #FF9800;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 4px;
    }
    .error-box {
        background-color: #FFEBEE;
        border-left: 4px solid #F44336;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 4px;
    }
    .success-box {
        background-color: #E8F5E9;
        border-left: 4px solid #4CAF50;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 4px;
    }
    .info-box {
        background-color: #E3F2FD;
        border-left: 4px solid #2196F3;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 4px;
    }
    .tip-box {
        background-color: #F3E5F5;
        border-left: 4px solid #9C27B0;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 4px;
    }
    .required-tag {
        background-color: #FFEBEE;
        color: #C62828;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.8rem;
        margin-left: 8px;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# 枚举类型定义 / Enum Definitions
# ============================================================

class ModeCategory(Enum):
    """模式类别枚举"""
    NETWORK = "network"
    TELEPORTED = "teleported"
    TRANSIT = "transit"
    TRANSIT_SUBMODES = "transit_submodes"


class VehicleConstraint(Enum):
    """车辆约束类型"""
    CHAIN_BASED = "chain_based"
    FREE = "free"


# ============================================================
# 配置检测规则 / Configuration Check Rules
# ============================================================

from dataclasses import dataclass
from typing import List, Tuple, Callable, Any


@dataclass
class ConfigCheckRule:
    """配置检查规则"""
    id: str
    severity: str  # 'error', 'warning', 'info'
    category: str  # 分类
    check_func: Callable[[], bool]  # 检查函数，返回 True 表示存在问题
    message_cn: str
    message_en: str
    fix_suggestion_cn: str
    fix_suggestion_en: str
    source: str  # 来源（哪个 Java 检查器）


def run_config_consistency_checks() -> List[dict]:
    """
    运行所有配置一致性检查
    返回问题列表
    """
    issues = []

    # 获取当前配置
    controller_cfg = st.session_state.get('controller_config', {})
    qsim_cfg = st.session_state.get('qsim_config', {})
    global_cfg = st.session_state.get('global_config', {})
    scoring_cfg = st.session_state.get('scoring_config', {})
    scoring_params = st.session_state.get('scoring_parameters', {}).get(None, {})
    replanning_cfg = st.session_state.get('replanning_config', {})
    strategy_config = st.session_state.get('strategy_config', [])
    network_modes = st.session_state.get('network_modes', {})
    teleported_modes = st.session_state.get('teleported_modes', {})
    transit_enabled = st.session_state.get('transit_enabled', False)
    activity_params = st.session_state.get('activity_params', {})
    file_config = st.session_state.get('file_config', {})
    ttc_cfg = st.session_state.get('travel_time_calculator_config', {})
    routing_cfg = st.session_state.get('routing_config', {})
    plans_cfg = st.session_state.get('plans_config', {})
    tam_cfg = st.session_state.get('time_allocation_mutator_config', {})
    smc_cfg = st.session_state.get('subtour_mode_choice_config', {})
    raptor_cfg = st.session_state.get('swiss_rail_raptor_config', {})
    access_egress_cfg = st.session_state.get('access_egress_config', {})
    vsp_cfg = st.session_state.get('vsp_experimental_config', {})

    # ================================================================
    # 1. Scoring 模块检查 (ConfigConsistencyCheckerImpl.checkPlanCalcScore)
    # ================================================================

    # 1.1 检查各模式的 marginalUtilityOfTraveling
    for mode_name, mode_config in network_modes.items():
        scoring = mode_config.get('scoring', {})
        mut = scoring.get('marginalUtilityOfTraveling_util_hr', -6.0)
        if mut > 0:
            issues.append({
                'id': f'SCORING_MUT_POSITIVE_{mode_name.upper()}',
                'severity': 'warning',
                'category': 'Scoring',
                'message_cn': f"模式 '{mode_name}' 的 marginalUtilityOfTraveling ({mut}) > 0。"
                              f"这个值表示效用，通常应该是负值（表示时间的不效用）。",
                'message_en': f"Mode '{mode_name}' has marginalUtilityOfTraveling ({mut}) > 0. "
                              f"This value specifies a utility. Typically, it should be a disutility (negative value).",
                'fix_cn': f"将 scoring.modeParams.{mode_name}.marginalUtilityOfTraveling_util_hr 设置为负值，如 -6.0",
                'fix_en': f"Set scoring.modeParams.{mode_name}.marginalUtilityOfTraveling_util_hr to a negative value like -6.0",
                'source': 'ConfigConsistencyCheckerImpl'
            })

    for mode_name, mode_config in teleported_modes.items():
        scoring = mode_config.get('scoring', {})
        mut = scoring.get('marginalUtilityOfTraveling_util_hr', -6.0)
        if mut > 0:
            issues.append({
                'id': f'SCORING_MUT_POSITIVE_{mode_name.upper()}',
                'severity': 'warning',
                'category': 'Scoring',
                'message_cn': f"模式 '{mode_name}' 的 marginalUtilityOfTraveling ({mut}) > 0。"
                              f"这个值表示效用，通常应该是负值。",
                'message_en': f"Mode '{mode_name}' has marginalUtilityOfTraveling ({mut}) > 0. "
                              f"This value specifies a utility. Typically, it should be a disutility.",
                'fix_cn': f"将 scoring.modeParams.{mode_name}.marginalUtilityOfTraveling_util_hr 设置为负值",
                'fix_en': f"Set scoring.modeParams.{mode_name}.marginalUtilityOfTraveling_util_hr to a negative value",
                'source': 'ConfigConsistencyCheckerImpl'
            })

    # 1.2 检查 pt interaction 活动
    if transit_enabled and 'pt interaction' in activity_params:
        pt_interaction = activity_params['pt interaction']
        if pt_interaction.get('scoringThisActivityAtAll', True):
            if not vsp_cfg.get('isAbleToOverwritePtInteractionParams', False):
                issues.append({
                    'id': 'SCORING_PT_INTERACTION',
                    'severity': 'error',
                    'category': 'Scoring',
                    'message_cn': "对 'pt interaction' 活动进行评分是不允许的，因为这会破坏公交评分。",
                    'message_en': "Scoring 'pt interaction' activity is not allowed because it breaks pt scoring.",
                    'fix_cn': "将 'pt interaction' 活动的 scoringThisActivityAtAll 设置为 false，"
                              "或者在 VspExperimental 模块中启用 isAbleToOverwritePtInteractionParams",
                    'fix_en': "Set scoringThisActivityAtAll to false for 'pt interaction' activity, "
                              "or enable isAbleToOverwritePtInteractionParams in VspExperimental module",
                    'source': 'ConfigConsistencyCheckerImpl'
                })

    # ================================================================
    # 2. 路由和出行时间计算检查
    # ================================================================

    # 2.1 Link-to-Link 路由配置一致性
    if controller_cfg.get('enableLinkToLinkRouting', False):
        if not ttc_cfg.get('calculateLinkToLinkTravelTimes', False):
            issues.append({
                'id': 'ROUTING_L2L_TTCalculator',
                'severity': 'error',
                'category': 'Routing',
                'message_cn': "启用了 LinkToLinkRouting，但未启用 link-to-link 出行时间计算。",
                'message_en': "LinkToLinkRouting is activated but link-to-link travel time calculation is not enabled.",
                'fix_cn': "在 travelTimeCalculator 模块中设置 calculateLinkToLinkTravelTimes = true",
                'fix_en': "Set calculateLinkToLinkTravelTimes = true in travelTimeCalculator module",
                'source': 'ConfigConsistencyCheckerImpl'
            })

        if controller_cfg.get('routingAlgorithmType', 'SpeedyALT') != 'Dijkstra':
            issues.append({
                'id': 'ROUTING_L2L_ALGORITHM',
                'severity': 'warning',
                'category': 'Routing',
                'message_cn': f"启用了 LinkToLinkRouting，但路由算法是 '{controller_cfg.get('routingAlgorithmType')}'。"
                              f"我们不确定非 Dijkstra 路由是否与 LinkToLink 路由兼容。",
                'message_en': f"LinkToLinkRouting is enabled but routing algorithm is '{controller_cfg.get('routingAlgorithmType')}'. "
                              f"We don't know if non-Dijkstra routing works with LinkToLink routing.",
                'fix_cn': "将 controller.routingAlgorithmType 设置为 Dijkstra",
                'fix_en': "Set controller.routingAlgorithmType to Dijkstra",
                'source': 'ConfigConsistencyCheckerImpl'
            })

    # 2.2 出行时间计算优化警告
    if ttc_cfg.get('calculateLinkTravelTimes', True) and ttc_cfg.get('calculateLinkToLinkTravelTimes', False):
        if not controller_cfg.get('enableLinkToLinkRouting', False):
            issues.append({
                'id': 'ROUTING_MEMORY_WARNING',
                'severity': 'warning',
                'category': 'Routing',
                'message_cn': "同时启用了 link 和 link-to-link 出行时间计算，但未启用 link-to-link 路由。"
                              "这需要至少两倍的内存。",
                'message_en': "Both link and link-to-link travel time calculation are enabled, "
                              "but link-to-link routing is not enabled. This requires at least twice the memory.",
                'fix_cn': "如果不需要 link-to-link 路由，禁用 calculateLinkToLinkTravelTimes 以节省内存",
                'fix_en': "If link-to-link routing is not needed, disable calculateLinkToLinkTravelTimes to save memory",
                'source': 'ConfigConsistencyCheckerImpl'
            })

    # 2.3 removeStuckVehicles 与 link-to-link 冲突
    if ttc_cfg.get('calculateLinkToLinkTravelTimes', False) and qsim_cfg.get('removeStuckVehicles', False):
        issues.append({
            'id': 'QSIM_L2L_STUCK',
            'severity': 'error',
            'category': 'QSim',
            'message_cn': "启用了 link-to-link 出行时间计算，同时启用了 removeStuckVehicles。这是不兼容的。",
            'message_en': "Link-to-link travel time calculation is not available with remove stuck vehicles option.",
            'fix_cn': "禁用 qsim.removeStuckVehicles 或 travelTimeCalculator.calculateLinkToLinkTravelTimes",
            'fix_en': "Disable either qsim.removeStuckVehicles or travelTimeCalculator.calculateLinkToLinkTravelTimes",
            'source': 'ConfigConsistencyCheckerImpl'
        })

    # ================================================================
    # 3. Lanes 配置检查
    # ================================================================

    if qsim_cfg.get('useLanes', False):
        # 3.1 需要 xml events
        events_formats = controller_cfg.get('eventsFileFormat', ['xml'])
        if 'xml' not in events_formats:
            issues.append({
                'id': 'LANES_EVENTS_FORMAT',
                'severity': 'error',
                'category': 'Lanes',
                'message_cn': "启用了 lanes 但未启用 xml 事件格式。Lanes 事件只能写入 xml 格式。",
                'message_en': "Lanes are enabled but xml events are not enabled. Events from lanes will only be written to xml format.",
                'fix_cn': "在 controller.eventsFileFormat 中添加 'xml'",
                'fix_en': "Add 'xml' to controller.eventsFileFormat",
                'source': 'ConfigConsistencyCheckerImpl'
            })

        # 3.2 建议启用 link-to-link routing
        if not controller_cfg.get('enableLinkToLinkRouting', False):
            issues.append({
                'id': 'LANES_L2L_ROUTING',
                'severity': 'warning',
                'category': 'Lanes',
                'message_cn': "使用 lanes 但未启用 link-to-link 路由，可能不会产生预期的仿真结果。",
                'message_en': "Using lanes without enabling link-to-link routing might not lead to expected simulation results.",
                'fix_cn': "启用 controller.enableLinkToLinkRouting",
                'fix_en': "Enable controller.enableLinkToLinkRouting",
                'source': 'ConfigConsistencyCheckerImpl'
            })

    # ================================================================
    # 4. VSP 标准检查 (VspConfigConsistencyCheckerImpl)
    # ================================================================

    # 4.1 brainExpBeta 应该为 1
    if scoring_cfg.get('brainExpBeta', 1.0) != 1.0:
        issues.append({
            'id': 'VSP_BRAIN_EXP_BETA',
            'severity': 'warning',
            'category': 'VSP Standard',
            'message_cn': f"brainExpBeta = {scoring_cfg.get('brainExpBeta')}，VSP 默认值是 1.0。"
                          f"不同的值可能在论文撰写时造成概念问题。",
            'message_en': f"brainExpBeta = {scoring_cfg.get('brainExpBeta')}, VSP default is 1.0. "
                          f"Different values may cause conceptual problems during paper writing.",
            'fix_cn': "设置 scoring.brainExpBeta = 1.0",
            'fix_en': "Set scoring.brainExpBeta = 1.0",
            'source': 'VspConfigConsistencyCheckerImpl'
        })

    # 4.2 marginalUtlOfWaiting 应该为 0
    if scoring_params.get('waiting', 0.0) != 0.0:
        issues.append({
            'id': 'VSP_WAITING_UTILITY',
            'severity': 'warning',
            'category': 'VSP Standard',
            'message_cn': f"marginalUtilityOfWaiting = {scoring_params.get('waiting')}，VSP 默认值是 0。",
            'message_en': f"marginalUtilityOfWaiting = {scoring_params.get('waiting')}, VSP default is 0.",
            'fix_cn': "设置 scoring.waiting = 0.0",
            'fix_en': "Set scoring.waiting = 0.0",
            'source': 'VspConfigConsistencyCheckerImpl'
        })

    # 4.3 monetaryDistanceRate 检查
    for mode_name, mode_config in {**network_modes, **teleported_modes}.items():
        scoring = mode_config.get('scoring', {})
        mdr = scoring.get('monetaryDistanceRate', 0.0)
        if mdr > 0:
            issues.append({
                'id': f'VSP_MDR_POSITIVE_{mode_name.upper()}',
                'severity': 'error',
                'category': 'VSP Standard',
                'message_cn': f"模式 '{mode_name}' 的 monetaryDistanceRate = {mdr} > 0。"
                              f"这可能是错误的，通常需要负值（表示成本）。",
                'message_en': f"Mode '{mode_name}' has monetaryDistanceRate = {mdr} > 0. "
                              f"You probably want a value < 0 here.",
                'fix_cn': f"将 scoring.modeParams.{mode_name}.monetaryDistanceRate 设置为负值",
                'fix_en': f"Set scoring.modeParams.{mode_name}.monetaryDistanceRate to a negative value",
                'source': 'VspConfigConsistencyCheckerImpl'
            })
        if mdr < -0.01:
            issues.append({
                'id': f'VSP_MDR_TOO_NEGATIVE_{mode_name.upper()}',
                'severity': 'warning',
                'category': 'VSP Standard',
                'message_cn': f"模式 '{mode_name}' 的 monetaryDistanceRate = {mdr} < -0.01。"
                              f"-0.01/米 意味着 -10/公里。您可能需要将值除以 1000。",
                'message_en': f"Mode '{mode_name}' has monetaryDistanceRate = {mdr} < -0.01. "
                              f"-0.01 per meter means -10 per km. You probably want to divide your value by 1000.",
                'fix_cn': f"检查并调整 monetaryDistanceRate 值，通常应在 -0.0001 到 -0.001 之间",
                'fix_en': f"Check and adjust monetaryDistanceRate value, typically should be between -0.0001 and -0.001",
                'source': 'VspConfigConsistencyCheckerImpl'
            })

    # 4.4 marginalUtilityOfMoney 应该 > 0
    if scoring_params.get('marginalUtilityOfMoney', 1.0) < 0:
        issues.append({
            'id': 'VSP_UTILITY_OF_MONEY',
            'severity': 'error',
            'category': 'VSP Standard',
            'message_cn': f"marginalUtilityOfMoney = {scoring_params.get('marginalUtilityOfMoney')} < 0。"
                          f"您几乎肯定需要一个大于 0 的值。",
            'message_en': f"marginalUtilityOfMoney = {scoring_params.get('marginalUtilityOfMoney')} < 0. "
                          f"You almost certainly want a value > 0 here.",
            'fix_cn': "设置 scoring.marginalUtilityOfMoney 为正值，如 1.0",
            'fix_en': "Set scoring.marginalUtilityOfMoney to a positive value like 1.0",
            'source': 'VspConfigConsistencyCheckerImpl'
        })

    # 4.5 walk 模式的 constant 应该为 0
    if 'walk' in teleported_modes:
        walk_constant = teleported_modes['walk'].get('scoring', {}).get('constant', 0.0)
        if walk_constant != 0:
            issues.append({
                'id': 'VSP_WALK_CONSTANT',
                'severity': 'error',
                'category': 'VSP Standard',
                'message_cn': f"walk 模式的 constant = {walk_constant}。"
                              f"非零值会导致问题，因为 ASC 也用于接驳模式。",
                'message_en': f"Walk mode has constant = {walk_constant}. "
                              f"Values different from zero cause problems because the ASC is also used for access/egress modes.",
                'fix_cn': "设置 walk 模式的 constant = 0.0",
                'fix_en': "Set walk mode constant = 0.0",
                'source': 'VspConfigConsistencyCheckerImpl'
            })

    # 4.6 fractionOfIterationsToStartScoreMSA 检查
    msa_fraction = scoring_cfg.get('fractionOfIterationsToStartScoreMSA')
    if msa_fraction is None or msa_fraction >= 1.0:
        issues.append({
            'id': 'VSP_SCORE_MSA',
            'severity': 'warning',
            'category': 'VSP Standard',
            'message_cn': "未设置 fractionOfIterationsToStartScoreMSA 或值 >= 1.0。"
                          "VSP 默认建议设置为 0.8 左右。",
            'message_en': "fractionOfIterationsToStartScoreMSA is not set or >= 1.0. "
                          "VSP default is to set this to something like 0.8.",
            'fix_cn': "设置 scoring.fractionOfIterationsToStartScoreMSA = 0.8",
            'fix_en': "Set scoring.fractionOfIterationsToStartScoreMSA = 0.8",
            'source': 'VspConfigConsistencyCheckerImpl'
        })

    # 4.7 accessEgressType 检查
    if routing_cfg.get('accessEgressType', 'none') == 'none':
        issues.append({
            'id': 'VSP_ACCESS_EGRESS_TYPE',
            'severity': 'info',
            'category': 'VSP Standard',
            'message_cn': "accessEgressType = 'none'。VSP 建议使用 'accessEgressModeToLink' 或其他值。",
            'message_en': "accessEgressType = 'none'. VSP recommends using 'accessEgressModeToLink' or another value.",
            'fix_cn': "设置 routing.accessEgressType = 'accessEgressModeToLink'",
            'fix_en': "Set routing.accessEgressType = 'accessEgressModeToLink'",
            'source': 'VspConfigConsistencyCheckerImpl'
        })

    # ================================================================
    # 5. Plans 模块检查
    # ================================================================

    # 5.1 removingUnnecessaryPlanAttributes
    if not plans_cfg.get('removingUnnecessaryPlanAttributes', False):
        issues.append({
            'id': 'VSP_REMOVE_PLAN_ATTRS',
            'severity': 'warning',
            'category': 'VSP Standard',
            'message_cn': "未移除不必要的计划属性。VSP 默认是移除这些属性。",
            'message_en': "You are not removing unnecessary plan attributes. VSP default is to do that.",
            'fix_cn': "设置 plans.removingUnnecessaryPlanAttributes = true",
            'fix_en': "Set plans.removingUnnecessaryPlanAttributes = true",
            'source': 'VspConfigConsistencyCheckerImpl'
        })

    # 5.2 activityDurationInterpretation
    adi = plans_cfg.get('activityDurationInterpretation', 'tryEndTimeThenDuration')
    if adi == 'endTimeOnly':
        issues.append({
            'id': 'PLANS_ADI_DEPRECATED',
            'severity': 'error',
            'category': 'Plans',
            'message_cn': "使用了已废弃的 activityDurationInterpretation = 'endTimeOnly'。"
                          "请使用 'tryEndTimeThenDuration'。",
            'message_en': "activityDurationInterpretation = 'endTimeOnly' is deprecated. "
                          "Use 'tryEndTimeThenDuration' instead.",
            'fix_cn': "设置 plans.activityDurationInterpretation = 'tryEndTimeThenDuration'",
            'fix_en': "Set plans.activityDurationInterpretation = 'tryEndTimeThenDuration'",
            'source': 'VspConfigConsistencyCheckerImpl'
        })

        if transit_enabled:
            issues.append({
                'id': 'PLANS_ADI_TRANSIT',
                'severity': 'error',
                'category': 'Plans',
                'message_cn': "使用 'endTimeOnly' 与公交模块一起会导致问题。"
                              "公交交互活动没有结束时间，因此永远不会结束！",
                'message_en': "Using 'endTimeOnly' with transit module does not work. "
                              "PT interaction activities never have an end time and thus will never end!",
                'fix_cn': "设置 plans.activityDurationInterpretation = 'tryEndTimeThenDuration'",
                'fix_en': "Set plans.activityDurationInterpretation = 'tryEndTimeThenDuration'",
                'source': 'VspConfigConsistencyCheckerImpl'
            })
    elif adi != 'tryEndTimeThenDuration':
        issues.append({
            'id': 'VSP_ADI_RECOMMENDATION',
            'severity': 'warning',
            'category': 'VSP Standard',
            'message_cn': f"activityDurationInterpretation = '{adi}'。"
                          f"VSP 默认使用 'tryEndTimeThenDuration'。",
            'message_en': f"activityDurationInterpretation = '{adi}'. "
                          f"VSP default is 'tryEndTimeThenDuration'.",
            'fix_cn': "设置 plans.activityDurationInterpretation = 'tryEndTimeThenDuration'",
            'fix_en': "Set plans.activityDurationInterpretation = 'tryEndTimeThenDuration'",
            'source': 'VspConfigConsistencyCheckerImpl'
        })

    # ================================================================
    # 6. QSim 模块检查
    # ================================================================

    # 6.1 vehiclesSource
    if qsim_cfg.get('vehiclesSource', 'defaultVehicle') == 'defaultVehicle':
        issues.append({
            'id': 'VSP_VEHICLES_SOURCE',
            'severity': 'info',
            'category': 'VSP Standard',
            'message_cn': "qsim.vehiclesSource = 'defaultVehicle'。VSP 建议使用其他设置。",
            'message_en': "qsim.vehiclesSource = 'defaultVehicle'. VSP should use one of the other settings.",
            'fix_cn': "考虑设置 qsim.vehiclesSource = 'modeVehicleTypesFromVehiclesData' 或 'fromVehiclesData'",
            'fix_en': "Consider setting qsim.vehiclesSource = 'modeVehicleTypesFromVehiclesData' or 'fromVehiclesData'",
            'source': 'VspConfigConsistencyCheckerImpl'
        })

    # 6.2 linkDynamics 与 bike
    main_modes = list(network_modes.keys())
    if 'bike' in main_modes and qsim_cfg.get('linkDynamics', 'FIFO') != 'PassingQ':
        issues.append({
            'id': 'VSP_LINK_DYNAMICS_BIKE',
            'severity': 'info',
            'category': 'VSP Standard',
            'message_cn': f"bike 在网络模式中，但 linkDynamics = '{qsim_cfg.get('linkDynamics')}'。"
                          f"VSP 建议使用 'PassingQ' 以允许自行车超车。",
            'message_en': f"Bike is in main modes but linkDynamics = '{qsim_cfg.get('linkDynamics')}'. "
                          f"VSP should use 'PassingQ' to allow bikes to pass.",
            'fix_cn': "设置 qsim.linkDynamics = 'PassingQ'",
            'fix_en': "Set qsim.linkDynamics = 'PassingQ'",
            'source': 'VspConfigConsistencyCheckerImpl'
        })

    # 6.3 usePersonIdForMissingVehicleId
    if qsim_cfg.get('usePersonIdForMissingVehicleId', True):
        issues.append({
            'id': 'VSP_PERSON_ID_FOR_VEHICLE',
            'severity': 'info',
            'category': 'VSP Standard',
            'message_cn': "qsim.usePersonIdForMissingVehicleId = true。VSP 建议设置为 false。",
            'message_en': "qsim.usePersonIdForMissingVehicleId = true. VSP should set this to false.",
            'fix_cn': "设置 qsim.usePersonIdForMissingVehicleId = false",
            'fix_en': "Set qsim.usePersonIdForMissingVehicleId = false",
            'source': 'VspConfigConsistencyCheckerImpl'
        })

    # 6.4 trafficDynamics
    if qsim_cfg.get('trafficDynamics', 'queue') != 'kinematicWaves':
        issues.append({
            'id': 'VSP_TRAFFIC_DYNAMICS',
            'severity': 'info',
            'category': 'VSP Standard',
            'message_cn': f"qsim.trafficDynamics = '{qsim_cfg.get('trafficDynamics')}'。"
                          f"VSP 标准是 'kinematicWaves'。",
            'message_en': f"qsim.trafficDynamics = '{qsim_cfg.get('trafficDynamics')}'. "
                          f"VSP standard is 'kinematicWaves'.",
            'fix_cn': "设置 qsim.trafficDynamics = 'kinematicWaves'",
            'fix_en': "Set qsim.trafficDynamics = 'kinematicWaves'",
            'source': 'VspConfigConsistencyCheckerImpl'
        })

    # 6.5 removeStuckVehicles
    if qsim_cfg.get('removeStuckVehicles', False):
        issues.append({
            'id': 'VSP_REMOVE_STUCK',
            'severity': 'warning',
            'category': 'VSP Standard',
            'message_cn': "qsim 正在移除卡住的车辆。VSP 默认是不移除。",
            'message_en': "QSim is removing stuck vehicles. VSP default is to not remove them.",
            'fix_cn': "设置 qsim.removeStuckVehicles = false",
            'fix_en': "Set qsim.removeStuckVehicles = false",
            'source': 'VspConfigConsistencyCheckerImpl'
        })

    # ================================================================
    # 7. Strategy 模块检查
    # ================================================================

    # 7.1 检查是否有 ChangeExpBeta 策略
    has_change_exp_beta = any(s.get('name') == 'ChangeExpBeta' for s in strategy_config)
    if not has_change_exp_beta:
        issues.append({
            'id': 'VSP_CHANGE_EXP_BETA',
            'severity': 'warning',
            'category': 'VSP Standard',
            'message_cn': "没有配置 ChangeExpBeta 策略。VSP 默认至少在一个策略中使用 ChangeExpBeta。",
            'message_en': "No ChangeExpBeta strategy is configured. VSP default is to use ChangeExpBeta in at least one strategy.",
            'fix_cn': "添加 ChangeExpBeta 策略，或考虑用 ChangeExpBeta 替换 BestScore",
            'fix_en': "Add a ChangeExpBeta strategy, or consider replacing BestScore with ChangeExpBeta",
            'source': 'VspConfigConsistencyCheckerImpl'
        })

    # 7.2 fractionOfIterationsToDisableInnovation
    disable_frac = replanning_cfg.get('fractionOfIterationsToDisableInnovation', 0.8)
    if disable_frac is None or disable_frac >= 1.0:
        issues.append({
            'id': 'VSP_DISABLE_INNOVATION',
            'severity': 'warning',
            'category': 'VSP Standard',
            'message_cn': "未设置 fractionOfIterationsToDisableInnovation。"
                          "VSP 默认设置为 0.8 左右。",
            'message_en': "fractionOfIterationsToDisableInnovation is not set. "
                          "VSP default is to set this to 0.8 or similar.",
            'fix_cn': "设置 replanning.fractionOfIterationsToDisableInnovation = 0.8",
            'fix_en': "Set replanning.fractionOfIterationsToDisableInnovation = 0.8",
            'source': 'VspConfigConsistencyCheckerImpl'
        })

    # 7.3 TimeAllocationMutator 检查
    uses_time_mutator = any(s.get('name') == 'TimeAllocationMutator' for s in strategy_config)
    if uses_time_mutator:
        mutation_range = tam_cfg.get('mutationRange', 1800.0)
        if mutation_range < 7200:
            issues.append({
                'id': 'VSP_TAM_MUTATION_RANGE',
                'severity': 'warning',
                'category': 'VSP Standard',
                'message_cn': f"timeAllocationMutator.mutationRange = {mutation_range} < 7200。"
                              f"VSP 默认值是 7200。",
                'message_en': f"timeAllocationMutator.mutationRange = {mutation_range} < 7200. "
                              f"VSP default is 7200.",
                'fix_cn': "设置 timeAllocationMutator.mutationRange = 7200",
                'fix_en': "Set timeAllocationMutator.mutationRange = 7200",
                'source': 'VspConfigConsistencyCheckerImpl'
            })

        if tam_cfg.get('mutationAffectsDuration', True):
            issues.append({
                'id': 'VSP_TAM_AFFECTS_DURATION',
                'severity': 'info',
                'category': 'VSP Standard',
                'message_cn': "timeAllocationMutator 正在影响持续时间。VSP 默认是不影响。",
                'message_en': "timeAllocationMutator is affecting duration. VSP default is not to do that.",
                'fix_cn': "设置 timeAllocationMutator.mutationAffectsDuration = false",
                'fix_en': "Set timeAllocationMutator.mutationAffectsDuration = false",
                'source': 'VspConfigConsistencyCheckerImpl'
            })

    # 7.4 SubtourModeChoice 检查
    uses_smc = any(s.get('name') == 'SubtourModeChoice' for s in strategy_config)
    if uses_smc:
        proba = smc_cfg.get('probaForRandomSingleTripMode', 0.0)
        if proba < 0.2:
            issues.append({
                'id': 'VSP_SMC_PROBA',
                'severity': 'warning',
                'category': 'VSP Standard',
                'message_cn': f"SubtourModeChoice.probaForRandomSingleTripMode = {proba} < 0.2。"
                              f"建议设置为 0.5 左右。",
                'message_en': f"SubtourModeChoice.probaForRandomSingleTripMode = {proba} < 0.2. "
                              f"Recommendation is to set this to a value around 0.5.",
                'fix_cn': "设置 subtourModeChoice.probaForRandomSingleTripMode = 0.5",
                'fix_en': "Set subtourModeChoice.probaForRandomSingleTripMode = 0.5",
                'source': 'VspConfigConsistencyCheckerImpl'
            })

    # ================================================================
    # 8. Controller 模块检查
    # ================================================================

    # 8.1 events file format
    events_formats = controller_cfg.get('eventsFileFormat', ['xml'])
    if 'xml' not in events_formats:
        issues.append({
            'id': 'VSP_EVENTS_XML',
            'severity': 'warning',
            'category': 'VSP Standard',
            'message_cn': "events file format 不包含 'xml'。VSP 默认使用 xml events。",
            'message_en': "Events file format does not contain 'xml'. VSP default is using xml events.",
            'fix_cn': "在 controller.eventsFileFormat 中添加 'xml'",
            'fix_en': "Add 'xml' to controller.eventsFileFormat",
            'source': 'VspConfigConsistencyCheckerImpl'
        })

    # 8.2 路由算法
    routing_algo = controller_cfg.get('routingAlgorithmType', 'SpeedyALT')
    if routing_algo != 'SpeedyALT':
        issues.append({
            'id': 'VSP_ROUTING_ALGO',
            'severity': 'info',
            'category': 'VSP Standard',
            'message_cn': f"路由算法是 '{routing_algo}'。VSP 默认（自 2021 年 5 月起）使用 SpeedyALT。",
            'message_en': f"Routing algorithm is '{routing_algo}'. VSP default (since May 2021) is SpeedyALT.",
            'fix_cn': "设置 controller.routingAlgorithmType = 'SpeedyALT'",
            'fix_en': "Set controller.routingAlgorithmType = 'SpeedyALT'",
            'source': 'VspConfigConsistencyCheckerImpl'
        })

    # 8.3 writePlansInterval
    if controller_cfg.get('writePlansInterval', 50) <= 0:
        issues.append({
            'id': 'VSP_WRITE_PLANS',
            'severity': 'warning',
            'category': 'VSP Standard',
            'message_cn': "writePlansInterval <= 0。VSP 默认至少写一次（用于 SimWrapper）。",
            'message_en': "writePlansInterval <= 0. VSP default is to write plans at least once (for SimWrapper).",
            'fix_cn': "设置 controller.writePlansInterval 为正整数",
            'fix_en': "Set controller.writePlansInterval to a positive integer",
            'source': 'VspConfigConsistencyCheckerImpl'
        })

    # 8.4 writeTripsInterval
    if controller_cfg.get('writeTripsInterval', 50) <= 0:
        issues.append({
            'id': 'VSP_WRITE_TRIPS',
            'severity': 'warning',
            'category': 'VSP Standard',
            'message_cn': "writeTripsInterval <= 0。VSP 默认至少写一次（用于 SimWrapper）。",
            'message_en': "writeTripsInterval <= 0. VSP default is to write trips at least once (for SimWrapper).",
            'fix_cn': "设置 controller.writeTripsInterval 为正整数",
            'fix_en': "Set controller.writeTripsInterval to a positive integer",
            'source': 'VspConfigConsistencyCheckerImpl'
        })

    # ================================================================
    # 9. TravelTimeCalculator 模块检查
    # ================================================================

    if not ttc_cfg.get('separateModes', True):
        issues.append({
            'id': 'VSP_TTC_SEPARATE_MODES',
            'severity': 'info',
            'category': 'VSP Standard',
            'message_cn': "travelTimeCalculator 未按模式分别分析。VSP 默认是这样做的。"
                          "否则，您可能对 bike 和 car 使用相同的出行时间。",
            'message_en': "travelTimeCalculator is not analyzing different modes separately. VSP default is to do that. "
                          "Otherwise, you are using the same travel times for, say, bike and car.",
            'fix_cn': "设置 travelTimeCalculator.separateModes = true",
            'fix_en': "Set travelTimeCalculator.separateModes = true",
            'source': 'VspConfigConsistencyCheckerImpl'
        })

    # ================================================================
    # 10. SwissRailRaptor 检查
    # ================================================================

    if transit_enabled and raptor_cfg.get('useIntermodalAccessEgress', False):
        # 10.1 handlingOfPlansWithoutRoutingMode
        if plans_cfg.get('handlingOfPlansWithoutRoutingMode', 'reject') != 'reject':
            issues.append({
                'id': 'RAPTOR_ROUTING_MODE',
                'severity': 'error',
                'category': 'SwissRailRaptor',
                'message_cn': "使用多模式接驳时，plans.handlingOfPlansWithoutRoutingMode 必须设置为 'reject'。",
                'message_en': "Using intermodal access/egress requires plans.handlingOfPlansWithoutRoutingMode to be 'reject'.",
                'fix_cn': "设置 plans.handlingOfPlansWithoutRoutingMode = 'reject'",
                'fix_en': "Set plans.handlingOfPlansWithoutRoutingMode = 'reject'",
                'source': 'SwissRailRaptorConfigGroup'
            })

        # 10.2 检查接驳模式配置
        enabled_ae = [m for m, c in access_egress_cfg.items() if c.get('enabled', False)]
        if not enabled_ae:
            issues.append({
                'id': 'RAPTOR_NO_AE_MODES',
                'severity': 'error',
                'category': 'SwissRailRaptor',
                'message_cn': "启用了多模式接驳，但未定义任何接驳模式。",
                'message_en': "Intermodal routing is enabled, but no access/egress modes are defined.",
                'fix_cn': "在「出行模式配置 → 公共交通配置 → 接驳模式配置」中启用至少一种接驳模式",
                'fix_en': "Enable at least one access/egress mode in 'Travel Mode Configuration → Transit Configuration → Access/Egress Configuration'",
                'source': 'SwissRailRaptorConfigGroup'
            })

        # 10.3 检查每个接驳模式的参数
        for mode_name in enabled_ae:
            ae_cfg = access_egress_cfg.get(mode_name, {})
            max_radius = ae_cfg.get('max_radius', 1000.0)
            initial_radius = ae_cfg.get('initial_search_radius', 500.0)
            extension_radius = ae_cfg.get('search_extension_radius', 200.0)

            if max_radius <= 0:
                issues.append({
                    'id': f'RAPTOR_MAX_RADIUS_{mode_name.upper()}',
                    'severity': 'error',
                    'category': 'SwissRailRaptor',
                    'message_cn': f"接驳模式 '{mode_name}' 的 maxRadius = {max_radius} <= 0。请设置正值。",
                    'message_en': f"IntermodalAccessEgress mode '{mode_name}' has maxRadius = {max_radius} <= 0. Set a positive value.",
                    'fix_cn': f"设置 '{mode_name}' 的 maxRadius 为正值",
                    'fix_en': f"Set maxRadius for '{mode_name}' to a positive value",
                    'source': 'SwissRailRaptorConfigGroup'
                })

            if initial_radius <= 0:
                issues.append({
                    'id': f'RAPTOR_INITIAL_RADIUS_{mode_name.upper()}',
                    'severity': 'error',
                    'category': 'SwissRailRaptor',
                    'message_cn': f"接驳模式 '{mode_name}' 的 initialSearchRadius = {initial_radius} <= 0。请设置正值。",
                    'message_en': f"IntermodalAccessEgress mode '{mode_name}' has initialSearchRadius = {initial_radius} <= 0. Set a positive value.",
                    'fix_cn': f"设置 '{mode_name}' 的 initialSearchRadius 为正值",
                    'fix_en': f"Set initialSearchRadius for '{mode_name}' to a positive value",
                    'source': 'SwissRailRaptorConfigGroup'
                })

            if max_radius < initial_radius:
                issues.append({
                    'id': f'RAPTOR_RADIUS_INCONSISTENT_{mode_name.upper()}',
                    'severity': 'error',
                    'category': 'SwissRailRaptor',
                    'message_cn': f"接驳模式 '{mode_name}' 的 maxRadius ({max_radius}) < initialSearchRadius ({initial_radius})。"
                                  f"这是不一致的。",
                    'message_en': f"IntermodalAccessEgress mode '{mode_name}' has maxRadius ({max_radius}) < initialSearchRadius ({initial_radius}). "
                                  f"This is inconsistent.",
                    'fix_cn': f"确保 maxRadius >= initialSearchRadius",
                    'fix_en': f"Ensure maxRadius >= initialSearchRadius",
                    'source': 'SwissRailRaptorConfigGroup'
                })

    # ================================================================
    # 11. 模式冲突检查
    # ================================================================

    # 11.1 vehiclesSource 与 mode choice 冲突
    if (qsim_cfg.get('vehiclesSource', 'defaultVehicle') == 'fromVehiclesData'
            and qsim_cfg.get('usePersonIdForMissingVehicleId', True)):

        has_mode_choice = any('Mode' in s.get('name', '') for s in strategy_config)
        if has_mode_choice and len(main_modes) > 1:
            issues.append({
                'id': 'QSIM_VEHICLE_MODE_CONFLICT',
                'severity': 'error',
                'category': 'QSim',
                'message_cn': "不能在使用 Agent ID 作为缺失车辆 ID 的情况下使用多于一种主模式..."
                              "因为这样人只能有一辆车，无法切换到不同的车辆类型。",
                'message_en': "Cannot use more than one main (vehicular) mode while using agent ID for missing vehicle ID... "
                              "because in this case the person can only have one vehicle and cannot switch to a different vehicle type.",
                'fix_cn': "设置 qsim.usePersonIdForMissingVehicleId = false，或减少主模式数量，或禁用模式选择策略",
                'fix_en': "Set qsim.usePersonIdForMissingVehicleId = false, or reduce number of main modes, or disable mode choice strategies",
                'source': 'VspConfigConsistencyCheckerImpl'
            })

    # ================================================================
    # 12. jdeqsim 废弃检查 (UnmaterializedConfigGroupChecker)
    # ================================================================

    if controller_cfg.get('mobsim', 'qsim') == 'jdeqsim':
        issues.append({
            'id': 'JDEQSIM_DEPRECATED',
            'severity': 'warning',
            'category': 'Mobsim',
            'message_cn': "jdeqsim 已不再支持。请移除 jdeqsim 模块配置并使用 qsim。",
            'message_en': "jdeqsim is no longer supported. Please remove the jdeqsim module and use qsim.",
            'fix_cn': "设置 controller.mobsim = 'qsim'",
            'fix_en': "Set controller.mobsim = 'qsim'",
            'source': 'UnmaterializedConfigGroupChecker'
        })

    return issues

# ============================================================
# 重规划策略定义 / Replanning Strategy Definitions
# ============================================================

class StrategyType(Enum):
    """策略类型"""
    SELECTOR = "selector"  # 选择器：从现有计划中选择，不生成新计划
    MUTATOR = "mutator"  # 创新策略：修改计划生成新变体


class StrategyDefinition:
    """策略定义类"""

    def __init__(
            self,
            name: str,
            display_name_cn: str,
            display_name_en: str,
            strategy_type: StrategyType,
            description_cn: str = "",
            description_en: str = "",
            is_innovation: bool = False,  # 是否受 fractionOfIterationsToDisableInnovation 控制
            requires_module: Optional[str] = None,  # 需要的额外模块
            deprecated: bool = False
    ):
        self.name = name
        self.display_name_cn = display_name_cn
        self.display_name_en = display_name_en
        self.strategy_type = strategy_type
        self.description_cn = description_cn
        self.description_en = description_en
        self.is_innovation = is_innovation
        self.requires_module = requires_module
        self.deprecated = deprecated


# 预定义所有策略
AVAILABLE_STRATEGIES = {
    # ===== A. 选择器 (Selectors) =====
    "BestScore": StrategyDefinition(
        name="BestScore",
        display_name_cn="最佳得分",
        display_name_en="Best Score",
        strategy_type=StrategyType.SELECTOR,
        description_cn="选择得分最高的计划，不生成新计划",
        description_en="Selects the plan with the highest score, does not create new plans",
        is_innovation=False
    ),

    "SelectExpBeta": StrategyDefinition(
        name="SelectExpBeta",
        display_name_cn="指数概率选择",
        display_name_en="Select Exp Beta",
        strategy_type=StrategyType.SELECTOR,
        description_cn="按 exp(beta × score) 概率选择计划，不生成新计划",
        description_en="Selects plans with probability exp(beta × score), does not create new plans",
        is_innovation=False
    ),

    "KeepLastSelected": StrategyDefinition(
        name="KeepLastSelected",
        display_name_cn="保持上次选择",
        display_name_en="Keep Last Selected",
        strategy_type=StrategyType.SELECTOR,
        description_cn="保持上一轮选择的计划",
        description_en="Keeps the plan selected in the last iteration",
        is_innovation=False
    ),

    "SelectRandom": StrategyDefinition(
        name="SelectRandom",
        display_name_cn="随机选择",
        display_name_en="Select Random",
        strategy_type=StrategyType.SELECTOR,
        description_cn="随机选择一个计划",
        description_en="Randomly selects a plan",
        is_innovation=False
    ),

    "ChangeExpBeta": StrategyDefinition(
        name="ChangeExpBeta",
        display_name_cn="改变指数Beta",
        display_name_en="Change Exp Beta",
        strategy_type=StrategyType.SELECTOR,
        description_cn="与 SelectExpBeta 类似，但标记为创新策略",
        description_en="Similar to SelectExpBeta, but marked as innovation",
        is_innovation=True
    ),

    "SelectPathSizeLogit": StrategyDefinition(
        name="SelectPathSizeLogit",
        display_name_cn="路径大小Logit选择",
        display_name_en="Select Path Size Logit",
        strategy_type=StrategyType.SELECTOR,
        description_cn="使用路径大小Logit模型选择计划",
        description_en="Selects plans using path size logit model",
        is_innovation=False
    ),

    "KeepSelected": StrategyDefinition(
        name="KeepSelected",
        display_name_cn="保持已选",
        display_name_en="Keep Selected",
        strategy_type=StrategyType.SELECTOR,
        description_cn="保持当前选中的计划（废弃，使用 KeepLastSelected）",
        description_en="Keeps currently selected plan (deprecated, use KeepLastSelected)",
        is_innovation=False,
        deprecated=True
    ),

    # ===== B. 创新策略 (Mutators) =====
    "ReRoute": StrategyDefinition(
        name="ReRoute",
        display_name_cn="重新路由",
        display_name_en="ReRoute",
        strategy_type=StrategyType.MUTATOR,
        description_cn="重新计算路径，生成新的路由计划",
        description_en="Recalculates routes, generates new routed plan",
        is_innovation=True
    ),

    "TimeAllocationMutator": StrategyDefinition(
        name="TimeAllocationMutator",
        display_name_cn="时间分配变异",
        display_name_en="Time Allocation Mutator",
        strategy_type=StrategyType.MUTATOR,
        description_cn="随机调整活动时间，生成新的时间安排",
        description_en="Randomly adjusts activity times, generates new schedule",
        is_innovation=True,
        requires_module="timeAllocationMutator"
    ),

    "TimeAllocationMutator_ReRoute": StrategyDefinition(
        name="TimeAllocationMutator_ReRoute",
        display_name_cn="时间变异+重新路由",
        display_name_en="Time Mutator + ReRoute",
        strategy_type=StrategyType.MUTATOR,
        description_cn="先调整时间，再重新路由",
        description_en="Adjusts times then reroutes",
        is_innovation=True,
        requires_module="timeAllocationMutator"
    ),

    "SubtourModeChoice": StrategyDefinition(
        name="SubtourModeChoice",
        display_name_cn="子路程模式选择",
        display_name_en="Subtour Mode Choice",
        strategy_type=StrategyType.MUTATOR,
        description_cn="改变子路程的出行模式",
        description_en="Changes mode for subtours",
        is_innovation=True,
        requires_module="subtourModeChoice"
    ),

    "SubtourModeChoice_ReRoute": StrategyDefinition(
        name="SubtourModeChoice_ReRoute",
        display_name_cn="子路程模式+重新路由",
        display_name_en="Subtour Mode + ReRoute",
        strategy_type=StrategyType.MUTATOR,
        description_cn="改变模式后重新路由",
        description_en="Changes mode then reroutes",
        is_innovation=True,
        requires_module="subtourModeChoice"
    ),

    "ChangeTripMode": StrategyDefinition(
        name="ChangeTripMode",
        display_name_cn="改变出行模式",
        display_name_en="Change Trip Mode",
        strategy_type=StrategyType.MUTATOR,
        description_cn="改变整个出行的模式",
        description_en="Changes mode for entire trip",
        is_innovation=True,
        requires_module="changeMode"
    ),

    "ChangeSingleTripMode": StrategyDefinition(
        name="ChangeSingleTripMode",
        display_name_cn="改变单个出行模式",
        display_name_en="Change Single Trip Mode",
        strategy_type=StrategyType.MUTATOR,
        description_cn="改变单个出行段的模式",
        description_en="Changes mode for a single trip leg",
        is_innovation=True,
        requires_module="changeMode"
    ),

    "ChangeLegMode": StrategyDefinition(
        name="ChangeLegMode",
        display_name_cn="改变行程段模式",
        display_name_en="Change Leg Mode",
        strategy_type=StrategyType.MUTATOR,
        description_cn="改变单个行程段（leg）的模式",
        description_en="Changes mode for a single leg",
        is_innovation=True,
        requires_module="changeMode"
    ),

    "TripSubtourModeChoice": StrategyDefinition(
        name="TripSubtourModeChoice",
        display_name_cn="出行子路程模式",
        display_name_en="Trip Subtour Mode Choice",
        strategy_type=StrategyType.MUTATOR,
        description_cn="组合出行和子路程的模式选择",
        description_en="Combined trip and subtour mode choice",
        is_innovation=True,
        requires_module="subtourModeChoice"
    ),

    # ===== 废弃策略 =====
    "PlanSelector": StrategyDefinition(
        name="PlanSelector",
        display_name_cn="计划选择器（废弃）",
        display_name_en="Plan Selector (Deprecated)",
        strategy_type=StrategyType.SELECTOR,
        description_cn="废弃的策略，请使用其他选择器",
        description_en="Deprecated strategy, use other selectors",
        is_innovation=False,
        deprecated=True
    ),
}


def get_selector_strategies() -> Dict[str, StrategyDefinition]:
    """获取所有选择器策略"""
    return {k: v for k, v in AVAILABLE_STRATEGIES.items()
            if v.strategy_type == StrategyType.SELECTOR and not v.deprecated}


def get_mutator_strategies() -> Dict[str, StrategyDefinition]:
    """获取所有创新策略"""
    return {k: v for k, v in AVAILABLE_STRATEGIES.items()
            if v.strategy_type == StrategyType.MUTATOR and not v.deprecated}


def get_all_active_strategies() -> Dict[str, StrategyDefinition]:
    """获取所有活跃（非废弃）策略"""
    return {k: v for k, v in AVAILABLE_STRATEGIES.items() if not v.deprecated}

# ============================================================
# 模式定义类 / Mode Definition Class
# ============================================================

class ModeDefinition:
    """模式定义类"""

    def __init__(
            self,
            name: str,
            display_name_cn: str,
            display_name_en: str,
            category: ModeCategory,
            constraint: VehicleConstraint = VehicleConstraint.FREE,
            default_speed: float = 0.0,
            beeline_factor: float = 1.3,
            description_cn: str = "",
            description_en: str = "",
            is_access_egress: bool = False,
            scoring_defaults: Optional[Dict] = None
    ):
        self.name = name
        self.display_name_cn = display_name_cn
        self.display_name_en = display_name_en
        self.category = category
        self.constraint = constraint
        self.default_speed = default_speed
        self.beeline_factor = beeline_factor
        self.description_cn = description_cn
        self.description_en = description_en
        self.is_access_egress = is_access_egress
        self.scoring_defaults = scoring_defaults if scoring_defaults is not None else {}


# ============================================================
# 预定义模式 / Preset Modes
# ============================================================

def get_preset_modes() -> Dict[str, ModeDefinition]:
    """获取所有预设模式定义"""

    preset_modes = {
        # ===== 网络模式 =====
        "car": ModeDefinition(
            name="car",
            display_name_cn="小汽车",
            display_name_en="Car",
            category=ModeCategory.NETWORK,
            constraint=VehicleConstraint.CHAIN_BASED,
            description_cn="私人小汽车，在路网上模拟，有链约束",
            description_en="Private car, simulated on network, chain-based constraint",
            scoring_defaults={
                'constant': 0.0,
                'marginalUtilityOfTraveling_util_hr': -6.0,
                'monetaryDistanceRate': -0.0002,
                'dailyMonetaryConstant': -5.0
            }
        ),
        "truck": ModeDefinition(
            name="truck",
            display_name_cn="货车",
            display_name_en="Truck",
            category=ModeCategory.NETWORK,
            constraint=VehicleConstraint.CHAIN_BASED,
            description_cn="货运车辆，在路网上模拟",
            description_en="Freight truck, simulated on network",
            scoring_defaults={
                'constant': 0.0,
                'marginalUtilityOfTraveling_util_hr': -6.0,
                'monetaryDistanceRate': -0.0005,
                'dailyMonetaryConstant': -20.0
            }
        ),
        "motorcycle": ModeDefinition(
            name="motorcycle",
            display_name_cn="摩托车",
            display_name_en="Motorcycle",
            category=ModeCategory.NETWORK,
            constraint=VehicleConstraint.CHAIN_BASED,
            description_cn="摩托车，在路网上模拟",
            description_en="Motorcycle, simulated on network",
            scoring_defaults={
                'constant': -1.0,
                'marginalUtilityOfTraveling_util_hr': -6.0,
                'monetaryDistanceRate': -0.0001,
                'dailyMonetaryConstant': -2.0
            }
        ),

        # ===== 传送模式 =====
        "walk": ModeDefinition(
            name="walk",
            display_name_cn="步行",
            display_name_en="Walk",
            category=ModeCategory.TELEPORTED,
            default_speed=1.39,
            description_cn="步行出行，使用直线距离估算",
            description_en="Walking, estimated using beeline distance",
            scoring_defaults={
                'constant': 0.0,
                'marginalUtilityOfTraveling_util_hr': -12.0,
                'monetaryDistanceRate': 0.0,
                'dailyMonetaryConstant': 0.0
            }
        ),
        "bike": ModeDefinition(
            name="bike",
            display_name_cn="自行车",
            display_name_en="Bike",
            category=ModeCategory.TELEPORTED,
            constraint=VehicleConstraint.CHAIN_BASED,
            default_speed=4.17,
            description_cn="自行车，有链约束",
            description_en="Bicycle, chain-based constraint",
            scoring_defaults={
                'constant': -2.0,
                'marginalUtilityOfTraveling_util_hr': -6.0,
                'monetaryDistanceRate': 0.0,
                'dailyMonetaryConstant': 0.0
            }
        ),
        "e-bike": ModeDefinition(
            name="e-bike",
            display_name_cn="电动自行车",
            display_name_en="E-Bike",
            category=ModeCategory.TELEPORTED,
            constraint=VehicleConstraint.CHAIN_BASED,
            default_speed=6.94,
            description_cn="电动自行车，有链约束",
            description_en="Electric bicycle, chain-based constraint",
            scoring_defaults={
                'constant': -1.5,
                'marginalUtilityOfTraveling_util_hr': -5.0,
                'monetaryDistanceRate': -0.00005,
                'dailyMonetaryConstant': -1.0
            }
        ),
        "ride": ModeDefinition(
            name="ride",
            display_name_cn="搭车",
            display_name_en="Ride",
            category=ModeCategory.TELEPORTED,
            default_speed=8.33,
            description_cn="搭乘他人车辆，如顺风车",
            description_en="Ride with others, like carpooling",
            scoring_defaults={
                'constant': -1.0,
                'marginalUtilityOfTraveling_util_hr': -4.0,
                'monetaryDistanceRate': -0.0001,
                'dailyMonetaryConstant': 0.0
            }
        ),

        # ===== 公交接驳模式 =====
        "access_walk": ModeDefinition(
            name="access_walk",
            display_name_cn="接驳步行(去程)",
            display_name_en="Access Walk",
            category=ModeCategory.TELEPORTED,
            default_speed=1.39,
            description_cn="从起点步行到公交站",
            description_en="Walking from origin to transit stop",
            is_access_egress=True,
            scoring_defaults={
                'constant': 0.0,
                'marginalUtilityOfTraveling_util_hr': -12.0,
                'monetaryDistanceRate': 0.0,
                'dailyMonetaryConstant': 0.0
            }
        ),
        "egress_walk": ModeDefinition(
            name="egress_walk",
            display_name_cn="接驳步行(回程)",
            display_name_en="Egress Walk",
            category=ModeCategory.TELEPORTED,
            default_speed=1.39,
            description_cn="从公交站步行到终点",
            description_en="Walking from transit stop to destination",
            is_access_egress=True,
            scoring_defaults={
                'constant': 0.0,
                'marginalUtilityOfTraveling_util_hr': -12.0,
                'monetaryDistanceRate': 0.0,
                'dailyMonetaryConstant': 0.0
            }
        ),
        "transit_walk": ModeDefinition(
            name="transit_walk",
            display_name_cn="换乘步行",
            display_name_en="Transit Walk",
            category=ModeCategory.TELEPORTED,
            default_speed=1.39,
            description_cn="公交站间换乘步行",
            description_en="Walking between transit stops for transfer",
            is_access_egress=True,
            scoring_defaults={
                'constant': 0.0,
                'marginalUtilityOfTraveling_util_hr': -12.0,
                'monetaryDistanceRate': 0.0,
                'dailyMonetaryConstant': 0.0
            }
        ),

        # ===== 公交模式(Agent选择层面) =====
        "pt": ModeDefinition(
            name="pt",
            display_name_cn="公共交通",
            display_name_en="Public Transport",
            category=ModeCategory.TRANSIT,
            description_cn="公共交通统称，Agent选择坐公交时使用",
            description_en="Generic public transport mode",
            scoring_defaults={
                'constant': -1.0,
                'marginalUtilityOfTraveling_util_hr': -3.0,
                'monetaryDistanceRate': 0.0,
                'dailyMonetaryConstant': -2.5
            }
        ),

        # ===== 公交子模式(transitSchedule层面) =====
        "bus": ModeDefinition(
            name="bus",
            display_name_cn="公交车",
            display_name_en="Bus",
            category=ModeCategory.TRANSIT_SUBMODES,
            description_cn="公交车，在路网上运行，可能受拥堵影响",
            description_en="Bus, runs on road network, may be affected by congestion",
            scoring_defaults={
                'constant': -1.0,
                'marginalUtilityOfTraveling_util_hr': -5.0,
                'monetaryDistanceRate': 0.0,
                'dailyMonetaryConstant': -2.0
            }
        ),
        "tram": ModeDefinition(
            name="tram",
            display_name_cn="有轨电车",
            display_name_en="Tram",
            category=ModeCategory.TRANSIT_SUBMODES,
            description_cn="有轨电车",
            description_en="Tram",
            scoring_defaults={
                'constant': -0.5,
                'marginalUtilityOfTraveling_util_hr': -3.0,
                'monetaryDistanceRate': 0.0,
                'dailyMonetaryConstant': -2.0
            }
        ),
        "subway": ModeDefinition(
            name="subway",
            display_name_cn="地铁",
            display_name_en="Subway/Metro",
            category=ModeCategory.TRANSIT_SUBMODES,
            description_cn="地铁，独立路网运行，不受道路拥堵影响",
            description_en="Subway/Metro, runs on separate network",
            scoring_defaults={
                'constant': -0.5,
                'marginalUtilityOfTraveling_util_hr': -2.0,
                'monetaryDistanceRate': 0.0,
                'dailyMonetaryConstant': -3.0
            }
        ),
        "train": ModeDefinition(
            name="train",
            display_name_cn="火车/城铁",
            display_name_en="Train",
            category=ModeCategory.TRANSIT_SUBMODES,
            description_cn="城市铁路/城际列车，独立路网运行",
            description_en="Urban rail/Intercity train",
            scoring_defaults={
                'constant': -1.0,
                'marginalUtilityOfTraveling_util_hr': -1.0,
                'monetaryDistanceRate': 0.0,
                'dailyMonetaryConstant': -5.0
            }
        ),
        "ferry": ModeDefinition(
            name="ferry",
            display_name_cn="轮渡",
            display_name_en="Ferry",
            category=ModeCategory.TRANSIT_SUBMODES,
            description_cn="水上公共交通",
            description_en="Water-based public transport",
            scoring_defaults={
                'constant': -2.0,
                'marginalUtilityOfTraveling_util_hr': -2.0,
                'monetaryDistanceRate': 0.0,
                'dailyMonetaryConstant': -3.0
            }
        ),
        "light_rail": ModeDefinition(
            name="light_rail",
            display_name_cn="轻轨",
            display_name_en="Light Rail",
            category=ModeCategory.TRANSIT_SUBMODES,
            description_cn="轻轨系统",
            description_en="Light rail system",
            scoring_defaults={
                'constant': -0.5,
                'marginalUtilityOfTraveling_util_hr': -2.5,
                'monetaryDistanceRate': 0.0,
                'dailyMonetaryConstant': -2.5
            }
        ),
    }

    return preset_modes


# 全局预设模式字典
PRESET_MODES = get_preset_modes()


# ============================================================
# 预设活动类型 / Preset Activity Types
# ============================================================

def get_preset_activities() -> Dict[str, Dict]:
    """获取预设活动类型"""

    return {
        "home": {
            "display_cn": "居家",
            "display_en": "Home",
            "typicalDuration": "12:00:00",
            "minimalDuration": "",
            "openingTime": "",
            "closingTime": "",
            "description": "居住活动"
        },
        "work": {
            "display_cn": "工作",
            "display_en": "Work",
            "typicalDuration": "08:00:00",
            "minimalDuration": "06:00:00",
            "openingTime": "07:00:00",
            "closingTime": "19:00:00",
            "description": "工作活动"
        },
        "education": {
            "display_cn": "教育",
            "display_en": "Education",
            "typicalDuration": "06:00:00",
            "minimalDuration": "04:00:00",
            "openingTime": "08:00:00",
            "closingTime": "18:00:00",
            "description": "上学/培训活动"
        },
        "shopping": {
            "display_cn": "购物",
            "display_en": "Shopping",
            "typicalDuration": "01:00:00",
            "minimalDuration": "00:30:00",
            "openingTime": "09:00:00",
            "closingTime": "22:00:00",
            "description": "购物活动"
        },
        "leisure": {
            "display_cn": "休闲",
            "display_en": "Leisure",
            "typicalDuration": "02:00:00",
            "minimalDuration": "00:30:00",
            "openingTime": "",
            "closingTime": "",
            "description": "休闲娱乐活动"
        },
        "other": {
            "display_cn": "其他",
            "display_en": "Other",
            "typicalDuration": "01:00:00",
            "minimalDuration": "",
            "openingTime": "",
            "closingTime": "",
            "description": "其他类型活动"
        },
    }


PRESET_ACTIVITIES = get_preset_activities()

# ============================================================
# 其他选项定义 / Other Options
# ============================================================

MOBSIM_OPTIONS = {
    "qsim": "QSim (推荐，多线程队列仿真)",
    "hermes": "Hermes (超大规模专用)",
}


ROUTING_ALGORITHMS = {
    "Dijkstra": "标准Dijkstra (精确)",
    "AStarLandmarks": "A*地标算法 (快速精确)",
    "SpeedyALT": "SpeedyALT (最新最快)",
}

OVERWRITE_OPTIONS = {
    "deleteDirectoryIfExists": "删除已有目录 (推荐)",
    "overwriteExistingFiles": "覆盖已有文件",
    "failIfDirectoryExists": "目录存在则报错",
}
# ============================================================
# TravelTimeCalculator 模块枚举选项 / TravelTimeCalculator Enum Options
# ============================================================

TRAVEL_TIME_AGGREGATOR_OPTIONS = {
    "optimistic": (
        "乐观估计 / optimistic",
        "假设自由流速度（可能过于乐观），适用于无拥堵时间桶"
    ),
    "experimental_LastMile": (
        "实验性最后一里 / experimental_LastMile",
        "实验性功能，可能过于悲观"
    )
}

TRAVEL_TIME_GETTER_OPTIONS = {
    "average": (
        "平均值 / average",
        "返回时间桶内的平均出行时间"
    ),
    "linearinterpolation": (
        "线性插值 / linearinterpolation",
        "在相邻时间桶之间进行线性插值"
    )
}

# ============================================================
# VspExperimental 模块枚举选项 / VspExperimental Enum Options
# ============================================================

VSP_DEFAULTS_CHECKING_LEVEL_OPTIONS = {
    "ignore": (
        "忽略 / ignore",
        "不检查VSP默认值，适用于非VSP成员"
    ),
    "info": (
        "信息 / info",
        "违反VSP默认值时记录信息日志"
    ),
    "warn": (
        "警告 / warn",
        "违反VSP默认值时记录警告日志"
    ),
    "abort": (
        "中止 / abort",
        "违反VSP默认值时中止仿真（VSP成员应使用此选项）"
    )
}
# ===== Controller 相关枚举取值 / Controller Enum Options =====

CONTROLLER_EVENTS_FORMAT_OPTIONS = {
    "xml": "XML 事件文件 / XML events (人类可读，标准格式)",
    "pb": "Protocol Buffers / .pb (高效二进制，体积小，读写快)",
    "json": "JSON 事件文件 / JSON events (易于与其他系统集成)"
}

CONTROLLER_SNAPSHOT_FORMAT_OPTIONS = {
    "transims": "TRANSIMS快照 / TRANSIMS-style snapshots (按链接聚合流量)",
    "googleearth": "Google Earth 可视化 / Google Earth snapshots (KML/KMZ)",
    "otfvis": "OTFVis 在线可视化 / OTFVis snapshots (用于交互式动画)",
    "positionevents": "位置事件 / Position events (每个 Agent 的位置事件)"
}

CONTROLLER_COMPRESSION_OPTIONS = {
    "none": "不压缩 / no compression (文件最大，I/O最快)",
    "gzip": "GZip 压缩 / gzip compression (默认，兼容性好)",
    "lz4": "LZ4 压缩 / lz4 compression (更快，体积中等)",
    "zst": "Zstandard 压缩 / zst compression (高压缩率)"
}

CONTROLLER_CLEAN_ITERS_OPTIONS = {
    "keep": "保留所有 ITERS / keep all iterations (便于后分析，磁盘占用大)",
    "delete": "删除所有 ITERS / delete iterations (只保留最终结果)"
}

CONTROLLER_CREATE_SCORING_OPTIONS = {
    "IterationStarts": "在每轮开始时创建评分函数 / create at iteration start",
    "BeforeMobsim": "在每轮仿真前创建评分函数 / create before mobsim"
}

# ===== changeMode 模块枚举 / changeMode Enum Options =====

CHANGEMODE_BEHAVIOR_OPTIONS = {
    "fromSpecifiedModesToSpecifiedModes": (
        "仅从指定模式切换到指定模式 / "
        "from specified modes to specified modes"
    ),
    "fromAllModesToSpecifiedModes": (
        "从所有模式切换到指定模式 / "
        "from all modes to specified modes"
    )
}

# ============================================================
# SwissRailRaptor 模块枚举选项 / SwissRailRaptor Enum Options
# ============================================================

RAPTOR_INTERMODAL_MODE_SELECTION_OPTIONS = {
    "CalcLeastCostModePerStop": (
        "按站点计算最低成本模式 / CalcLeastCostModePerStop",
        "为每个站点计算成本最低的接驳模式"
    ),
    "RandomSelectOneModePerRoutingRequestAndDirection": (
        "随机选择模式 / RandomSelectOneModePerRoutingRequestAndDirection",
        "每次路由请求随机选择一种接驳模式"
    )
}

RAPTOR_INTERMODAL_LEG_HANDLING_OPTIONS = {
    "allow": (
        "允许 / allow",
        "允许仅由接驳行程组成的公交路线（如果成本最低）"
    ),
    "avoid": (
        "避免 / avoid",
        "尽量避免仅接驳路线，除非找不到包含PT的路线"
    ),
    "forbid": (
        "禁止 / forbid",
        "明确禁止仅接驳路线，找不到PT路线则返回空"
    )
}

RAPTOR_TRANSFER_CALCULATION_OPTIONS = {
    "Initial": (
        "预计算 / Initial",
        "仿真开始时预计算所有可能的换乘（启动慢，路由快）"
    ),
    "Adaptive": (
        "按需计算 / Adaptive",
        "按需构建换乘（启动快，路由可能较慢）"
    )
}

RAPTOR_SCORING_PARAMETERS_OPTIONS = {
    "Default": "默认评分参数 / Default scoring parameters",
    "Individual": "个性化评分参数 / Individual scoring parameters"
}

# ============================================================
# Transit 模块枚举选项 / Transit Enum Options
# ============================================================

TRANSIT_ROUTING_ALGORITHM_OPTIONS = {
    "SwissRailRaptor": (
        "SwissRailRaptor (推荐)",
        "高效的公交路由算法，支持多模式接驳"
    ),
    "DijkstraBased": (
        "DijkstraBased (已废弃)",
        "基于Dijkstra的传统算法，不推荐使用"
    )
}

TRANSIT_BOARDING_ACCEPTANCE_OPTIONS = {
    "checkLineAndStop": (
        "检查线路和站点 / checkLineAndStop",
        "Agent必须在正确的线路和站点才能上车"
    ),
    "checkStopOnly": (
        "仅检查站点 / checkStopOnly",
        "Agent只需在正确站点即可上车任何线路"
    )
}

# ============================================================
# Routing 模块枚举选项 / Routing Module Enum Options
# ============================================================

ROUTING_ACCESS_EGRESS_TYPE_OPTIONS = {
    "none": (
        "无接驳仿真 / none",
        "不模拟接驳行程，传统模式"
    ),
    "accessEgressModeToLink": (
        "接驳到Link / accessEgressModeToLink",
        "从设施欧氏距离步行到Link最近点"
    ),
    "walkConstantTimeToLink": (
        "固定时间到Link / walkConstantTimeToLink",
        "步行时间从Link属性读取，所有Agent相同"
    ),
    "accessEgressModeToLinkPlusTimeConstant": (
        "欧氏距离+固定时间 / accessEgressModeToLinkPlusTimeConstant",
        "欧氏距离步行加上Link属性时间"
    )
}

ROUTING_NETWORK_CONSISTENCY_CHECK_OPTIONS = {
    "disable": "禁用检查 / Disable consistency check",
    "abortOnInconsistency": "不一致时中止 / Abort on inconsistency (推荐)"
}

# ============================================================
# Scoring 模块枚举选项 / Scoring Module Enum Options
# ============================================================

SCORING_TYPICAL_DURATION_COMPUTATION_OPTIONS = {
    "relative": (
        "相对计算 / relative (推荐)",
        "根据活动类型调整评分，短活动不会被过度惩罚"
    ),
    "uniform": (
        "统一计算 / uniform",
        "向后兼容模式，所有活动统一评分"
    )
}

# ============================================================
# SubtourModeChoice 模块枚举选项 / SubtourModeChoice Enum Options
# ============================================================

SUBTOUR_MODE_BEHAVIOR_OPTIONS = {
    "fromSpecifiedModesToSpecifiedModes": (
        "指定模式间切换 / fromSpecifiedModesToSpecifiedModes",
        "仅当当前模式在modes中时才切换，目标也在modes中"
    ),
    "fromAllModesToSpecifiedModes": (
        "从所有模式切换到指定模式 / fromAllModesToSpecifiedModes",
        "任何当前模式都可切换到modes中的目标模式"
    )
}

# ============================================================
# 模式管理器类 / Mode Manager Class
# ============================================================

class ModeManager:
    """统一模式管理器"""

    @staticmethod
    def get_network_modes() -> Dict[str, Dict]:
        """获取所有网络模式"""
        return st.session_state.get('network_modes', {})

    @staticmethod
    def get_teleported_modes() -> Dict[str, Dict]:
        """获取所有传送模式"""
        return st.session_state.get('teleported_modes', {})

    @staticmethod
    def get_transit_submodes() -> Dict[str, Dict]:
        """获取所有公交子模式"""
        return st.session_state.get('transit_submodes', {})

    @staticmethod
    def get_access_egress_config() -> Dict[str, Dict]:
        """获取接驳配置"""
        return st.session_state.get('access_egress_config', {})

    @staticmethod
    def get_enabled_access_egress_modes() -> List[str]:
        """获取已启用的接驳模式"""
        config = st.session_state.get('access_egress_config', {})
        return [mode for mode, cfg in config.items() if cfg.get('enabled', False)]

    @staticmethod
    def get_chain_based_modes() -> List[str]:
        """获取所有链约束模式"""
        result = []

        for name, config in st.session_state.get('network_modes', {}).items():
            if config.get('is_chain_based', False):
                result.append(name)

        for name, config in st.session_state.get('teleported_modes', {}).items():
            if config.get('is_chain_based', False):
                result.append(name)

        return result

    @staticmethod
    def get_choosable_modes() -> List[str]:
        """
        获取Agent可选择的模式 (subtourModeChoice.modes)
        包括：标记为choosable的网络模式 + 传送模式 + pt(如果启用公交)
        """
        modes = []

        # 网络模式
        for name, config in st.session_state.get('network_modes', {}).items():
            if config.get('is_choosable', True):
                modes.append(name)

        # 传送模式
        for name, config in st.session_state.get('teleported_modes', {}).items():
            if config.get('is_choosable', True):
                modes.append(name)

        # 公交
        if st.session_state.get('transit_enabled', False):
            modes.append('pt')

        return modes

    @staticmethod
    def get_enabled_modes() -> Dict[str, List[str]]:
        """获取当前启用的各类模式（兼容接口）"""
        network = list(st.session_state.get('network_modes', {}).keys())
        teleported = list(st.session_state.get('teleported_modes', {}).keys())
        transit = ['pt'] if st.session_state.get('transit_enabled', False) else []
        transit_submodes = list(st.session_state.get('transit_submodes', {}).keys())

        return {
            'network': network,
            'teleported': teleported,
            'transit': transit,
            'transit_submodes': transit_submodes
        }

    @staticmethod
    def get_all_mode_names() -> Set[str]:
        """获取所有已使用的模式名称"""
        names = set()
        names.update(st.session_state.get('network_modes', {}).keys())
        names.update(st.session_state.get('teleported_modes', {}).keys())
        names.update(st.session_state.get('transit_submodes', {}).keys())
        return names

    @staticmethod
    def check_mode_name_conflict(new_name: str, exclude_category: str = None) -> Tuple[bool, str]:
        """
        检查模式名称是否冲突
        返回: (是否冲突, 冲突描述)
        """
        new_name = new_name.lower().strip()

        # 检查网络模式
        if exclude_category != 'network' and new_name in st.session_state.get('network_modes', {}):
            return True, f"'{new_name}' 已存在于网络模式中"

        # 检查传送模式
        if exclude_category != 'teleported' and new_name in st.session_state.get('teleported_modes', {}):
            return True, f"'{new_name}' 已存在于传送模式中"

        # 检查公交子模式
        if exclude_category != 'transit' and new_name in st.session_state.get('transit_submodes', {}):
            return True, f"'{new_name}' 已存在于公交子模式中（从时刻表解析）"

        # 检查保留名称
        reserved = ['pt']
        if new_name in reserved:
            return True, f"'{new_name}' 是系统保留名称"

        return False, ""

    @staticmethod
    def validate_configuration() -> Tuple[List[str], List[str]]:
        """验证配置"""
        errors = []
        warnings = []

        network_modes = st.session_state.get('network_modes', {})
        teleported_modes = st.session_state.get('teleported_modes', {})
        transit_enabled = st.session_state.get('transit_enabled', False)
        transit_submodes = st.session_state.get('transit_submodes', {})

        # 1. 至少需要一种出行模式
        if not network_modes and not teleported_modes and not transit_enabled:
            errors.append("❌ 至少需要配置一种出行模式")

        # 2. 公交检查
        if transit_enabled:
            if not transit_submodes:
                warnings.append("⚠️ 启用了公交但未检测到公交子模式，请上传并解析时刻表文件")

            # 检查接驳模式
            enabled_ae = ModeManager.get_enabled_access_egress_modes()
            if not enabled_ae:
                warnings.append("⚠️ 启用公交但未配置任何接驳模式，建议启用walk作为接驳")

            # 检查接驳模式是否在传送模式中
            for mode in enabled_ae:
                if mode not in teleported_modes:
                    errors.append(f"❌ 接驳模式 '{mode}' 不在传送模式中")
            # ========== 新增：检查 pt interaction 活动 ==========
            activity_params = st.session_state.get('activity_params', {})
            if 'pt interaction' not in activity_params:
                errors.append("❌ 启用公交但未配置 'pt interaction' 活动，请在【活动类型配置】中解析文件或手动添加")

        # 3. 公交子模式冲突检查
        transit_submode_names = set(transit_submodes.keys())
        network_names = set(network_modes.keys())
        teleported_names = set(teleported_modes.keys())

        conflict_with_network = transit_submode_names & network_names
        if conflict_with_network:
            errors.append(f"❌ 公交子模式与网络模式冲突: {conflict_with_network}")

        conflict_with_teleported = transit_submode_names & teleported_names
        if conflict_with_teleported:
            errors.append(f"❌ 公交子模式与传送模式冲突: {conflict_with_teleported}")

        # 4. 链约束检查
        chain_modes = ModeManager.get_chain_based_modes()
        choosable = set(ModeManager.get_choosable_modes())
        for mode in chain_modes:
            if mode not in choosable:
                warnings.append(f"⚠️ 链约束模式 '{mode}' 未标记为可选择")

        return errors, warnings

    @staticmethod
    def sync_access_egress_config():
        """同步接驳配置，移除不存在的传送模式"""
        teleported = st.session_state.get('teleported_modes', {})
        access_egress = st.session_state.get('access_egress_config', {})

        # 移除不再存在的模式
        modes_to_remove = [m for m in access_egress if m not in teleported]
        for mode in modes_to_remove:
            del access_egress[mode]

        st.session_state.access_egress_config = access_egress

    @staticmethod
    def auto_fix_configuration():
        """自动修复配置问题"""
        teleported = st.session_state.get('teleported_modes', {})
        access_egress = st.session_state.get('access_egress_config', {})

        # 1. 如果没有任何接驳模式且存在walk，自动启用walk作为接驳
        if st.session_state.get('transit_enabled', False):
            enabled_ae = [m for m, c in access_egress.items() if c.get('enabled', False)]
            if not enabled_ae and 'walk' in teleported:
                if 'walk' not in access_egress:
                    access_egress['walk'] = {
                        'enabled': True,
                        'max_radius': 1000.0,
                        'initial_search_radius': 500.0
                    }
                else:
                    access_egress['walk']['enabled'] = True
                st.session_state.access_egress_config = access_egress

        # 2. 同步接驳配置
        ModeManager.sync_access_egress_config()

        # 3. 确保所有模式都有评分参数
        for mode_name, mode_config in st.session_state.get('network_modes', {}).items():
            if 'scoring' not in mode_config:
                mode_config['scoring'] = {
                    'constant': 0.0,
                    'marginalUtilityOfTraveling_util_hr': -6.0,
                    'monetaryDistanceRate': 0.0,
                    'dailyMonetaryConstant': 0.0
                }

        for mode_name, mode_config in st.session_state.get('teleported_modes', {}).items():
            if 'scoring' not in mode_config:
                mode_config['scoring'] = {
                    'constant': 0.0,
                    'marginalUtilityOfTraveling_util_hr': -6.0,
                    'monetaryDistanceRate': 0.0,
                    'dailyMonetaryConstant': 0.0
                }


def validate_full_configuration() -> Tuple[List[str], List[str]]:
    """
    汇总全局配置校验，覆盖 MATSim 核心模块规则（基于 Config.java 及各 ConfigGroup）
    返回: (errors, warnings)
    """
    # 先执行模式级别的基础检查，避免递归
    errors, warnings = ModeManager.validate_configuration()

    file_config = st.session_state.get('file_config', {})
    controller = st.session_state.get('controller_config', {})
    qsim = st.session_state.get('qsim_config', {})
    gc = st.session_state.get('global_config', {})
    network_modes = st.session_state.get('network_modes', {})
    teleported_modes = st.session_state.get('teleported_modes', {})
    transit_enabled = st.session_state.get('transit_enabled', False)

    # ---------- 文件必填 ----------
    if not file_config.get('networkFile'):
        errors.append("❌ 未配置路网文件 (network.inputNetworkFile)")
    if not file_config.get('plansFile'):
        errors.append("❌ 未配置人口计划文件 (plans.inputPlansFile)")
    if transit_enabled:
        if not file_config.get('transitScheduleFile'):
            errors.append("❌ 启用公交但未配置时刻表文件 (transit.transitScheduleFile)")
        if not file_config.get('transitVehiclesFile'):
            errors.append("❌ 启用公交但未配置车辆文件 (transit.vehiclesFile)")

    # ---------- GlobalConfigGroup ----------
    if gc.get('numberOfThreads', 0) < 1:
        errors.append("❌ global.numberOfThreads 必须 >= 1")
    if gc.get('randomSeed', -1) < 0:
        warnings.append("⚠️ global.randomSeed 建议为非负整数")
    delimiter = gc.get('defaultDelimiter', '')
    if not delimiter or not str(delimiter).strip():
        errors.append("❌ global.defaultDelimiter 不能为空")
    if not gc.get('coordinateSystem'):
        warnings.append("⚠️ global.coordinateSystem 为空，需与路网坐标系一致")

    # ---------- ControllerConfigGroup ----------
    first_iter = controller.get('firstIteration', 0)
    last_iter = controller.get('lastIteration', 0)
    if last_iter < first_iter:
        errors.append("❌ controller.lastIteration 必须 >= firstIteration")

    if controller.get('writeEventsInterval', 0) < 0:
        errors.append("❌ controller.writeEventsInterval 不能为负")
    if controller.get('writePlansInterval', 0) < 0:
        errors.append("❌ controller.writePlansInterval 不能为负")
    if controller.get('writeTripsInterval', 0) < 0:
        errors.append("❌ controller.writeTripsInterval 不能为负")
    if controller.get('writeSnapshotsInterval', 0) < 0:
        errors.append("❌ controller.writeSnapshotsInterval 不能为负")
    if controller.get('createGraphsInterval', 0) < 0:
        errors.append("❌ controller.createGraphsInterval 不能为负")
    if controller.get('memoryObserverInterval', 0) <= 0:
        errors.append("❌ controller.memoryObserverInterval 必须 > 0")

    if not controller.get('outputDirectory'):
        errors.append("❌ controller.outputDirectory 不能为空")
    if not controller.get('runId'):
        errors.append("❌ controller.runId 不能为空")

    # 路由/引擎相关一致性
    if controller.get('enableLinkToLinkRouting', False) and controller.get('routingAlgorithmType') != 'Dijkstra':
        errors.append("❌ enableLinkToLinkRouting=true 时必须使用 routingAlgorithmType=Dijkstra")

    # eventsFileFormat / snapshotFormat 枚举检查
    for fmt in controller.get('eventsFileFormat', ['xml']):
        if fmt not in CONTROLLER_EVENTS_FORMAT_OPTIONS:
            errors.append(f"❌ controller.eventsFileFormat 包含未知格式 '{fmt}'")

    for fmt in controller.get('snapshotFormat', []):
        if fmt not in CONTROLLER_SNAPSHOT_FORMAT_OPTIONS:
            errors.append(f"❌ controller.snapshotFormat 包含未知格式 '{fmt}'")

    if controller.get('compressionType', 'gzip') not in CONTROLLER_COMPRESSION_OPTIONS:
        errors.append(f"❌ controller.compressionType='{controller.get('compressionType')}' 非法")

    if controller.get('cleanItersAtEnd', 'keep') not in CONTROLLER_CLEAN_ITERS_OPTIONS:
        errors.append(f"❌ controller.cleanItersAtEnd='{controller.get('cleanItersAtEnd')}' 非法")

    if controller.get('createScoringFunctionType', 'IterationStarts') not in CONTROLLER_CREATE_SCORING_OPTIONS:
        errors.append(f"❌ controller.createScoringFunctionType='{controller.get('createScoringFunctionType')}' 非法")


    # ---------- QSimConfigGroup ----------
    if controller.get('mobsim', 'qsim') == 'qsim':
        if not network_modes:
            errors.append("❌ qsim.mainMode 至少需要一个网络模式（当前网络模式为空）")
        start_sec = parse_time_to_seconds(qsim.get('startTime', ''))
        end_sec = parse_time_to_seconds(qsim.get('endTime', ''))
        if start_sec is None:
            warnings.append("⚠️ qsim.startTime 格式应为 HH:MM:SS")
        if end_sec is None:
            warnings.append("⚠️ qsim.endTime 格式应为 HH:MM:SS")
        if start_sec is not None and end_sec is not None and start_sec >= end_sec:
            errors.append("❌ qsim.startTime 必须早于 endTime")
        if qsim.get('flowCapacityFactor', 0) <= 0:
            errors.append("❌ qsim.flowCapacityFactor 必须 > 0")
        if qsim.get('storageCapacityFactor', 0) <= 0:
            errors.append("❌ qsim.storageCapacityFactor 必须 > 0")
        if qsim.get('numberOfThreads', 0) < 1:
            errors.append("❌ qsim.numberOfThreads 必须 >= 1")
        if qsim.get('stuckTime', -1) < 0:
            errors.append("❌ qsim.stuckTime 必须 >= 0")

    # ---------- RoutingConfigGroup / modes ----------
    choosable_modes = ModeManager.get_choosable_modes()
    if not choosable_modes:
        warnings.append("⚠️ subtourModeChoice.modes 为空，Agent 将没有可选出行方式")

    # ---------- TransitConfigGroup ----------
    if transit_enabled:
        if not st.session_state.get('transit_submodes', {}):
            warnings.append("⚠️ 启用公交但未检测到 transit 子模式，请确认时刻表文件")

    # ---------- ScoringConfigGroup ----------
    def ensure_scoring(mode_name: str, scoring: Dict, defaults: Dict):
        missing = [k for k in defaults if k not in scoring]
        for k, v in defaults.items():
            scoring.setdefault(k, v)
        if missing:
            warnings.append(f"⚠️ scoring.modeParams.{mode_name} 缺少字段 {missing}，已回填默认值")

    default_score = {
        'constant': 0.0,
        'marginalUtilityOfTraveling_util_hr': -6.0,
        'monetaryDistanceRate': 0.0,
        'dailyMonetaryConstant': 0.0
    }
    for mode_name, mode_cfg in network_modes.items():
        scoring_ref = mode_cfg.setdefault('scoring', {})
        ensure_scoring(mode_name, scoring_ref, default_score)
    for mode_name, mode_cfg in teleported_modes.items():
        scoring_ref = mode_cfg.setdefault('scoring', {})
        ensure_scoring(mode_name, scoring_ref, default_score)
    if transit_enabled:
        pt_scoring = st.session_state.setdefault('pt_scoring', {})
        ensure_scoring('pt', pt_scoring, {
            'constant': -1.0,
            'marginalUtilityOfTraveling_util_hr': -3.0,
            'monetaryDistanceRate': 0.0,
            'dailyMonetaryConstant': -2.5
        })

    # ---------- ReplanningConfigGroup ----------
    replanning = st.session_state.get('replanning_config', {})
    if replanning.get('maxAgentPlanMemorySize', 0) < 1:
        errors.append("❌ replanning.maxAgentPlanMemorySize 必须 >= 1")
    frac = replanning.get('fractionOfIterationsToDisableInnovation', 0.0)
    if frac < 0 or frac > 1:
        errors.append("❌ replanning.fractionOfIterationsToDisableInnovation 必须在 0~1 之间")

    # strategy settings 权重检查
    strategies = st.session_state.get('strategy_config', [])
    total_weight = 0.0
    for s in strategies:
        if s.get('weight', 0) < 0:
            errors.append(f"❌ replanning.strategy {s.get('name')} 的 weight 不能为负")
        total_weight += s.get('weight', 0)
    if total_weight <= 0:
        errors.append("❌ replanning.strategysettings 总权重必须 > 0")

    # ---------- TimeAllocationMutatorConfigGroup ----------
    tam = st.session_state.get('time_mutator_config', {})
    if tam.get('mutationRange', -1) < 0:
        errors.append("❌ timeAllocationMutator.mutationRange 必须 >= 0")
    # ---------- TimeAllocationMutatorConfigGroup ----------
    tam = st.session_state.get('time_mutator_config', {})
    if tam.get('mutationRange', -1) < 0:
        errors.append("❌ timeAllocationMutator.mutationRange 必须 >= 0")

    # ---------- CountsConfigGroup ----------
    counts_cfg = st.session_state.get('counts_config', {})
    counts_file = file_config.get('countsFile', '')
    counts_enabled = bool(counts_file)
    if counts_enabled:
        if counts_cfg.get('countsScaleFactor', 0.0) <= 0:
            errors.append("❌ counts.countsScaleFactor 必须 > 0（建议为人口采样率的倒数，例如 10%% 采样 → 10.0）")
        if counts_cfg.get('writeCountsInterval', 0) < 0:
            errors.append("❌ counts.writeCountsInterval 不能为负")
        if counts_cfg.get('averageCountsOverIterations', 0) < 1:
            errors.append("❌ counts.averageCountsOverIterations 必须 >= 1")
        if counts_cfg.get('filterModes', False) and not counts_cfg.get('analyzedModes', '').strip():
            errors.append("❌ counts.filterModes=true 时，counts.analyzedModes 不能为空")
        if counts_cfg.get('distanceFilter') is not None and counts_cfg.get('distanceFilter', 0.0) < 0:
            errors.append("❌ counts.distanceFilter 若设置，则必须 >= 0")

    # ---------- EventsManagerConfigGroup ----------
    em_cfg = st.session_state.get('events_manager_config', {})
    if em_cfg.get('numberOfThreads', 0) < 0:
        errors.append("❌ eventsManager.numberOfThreads 不能为负（0 表示由系统自动决定）")
    if em_cfg.get('eventsQueueSize', 0) <= 0:
        errors.append("❌ eventsManager.eventsQueueSize 必须 > 0")
    if not em_cfg.get('synchronizeOnSimSteps', True):
        warnings.append("⚠️ eventsManager.synchronizeOnSimSteps=false 可能与 within-day replanning 等在线重规划不兼容，请谨慎使用")

    # ---------- ChangeModeConfigGroup ----------
    cm = st.session_state.get('changemode_config', {})
    cm_behavior = cm.get('modeSwitchBehavior', 'fromSpecifiedModesToSpecifiedModes')
    if cm_behavior not in CHANGEMODE_BEHAVIOR_OPTIONS:
        errors.append(f"❌ changeMode.modeSwitchBehavior='{cm_behavior}' 非法")

    if not cm.get('use_subtour_modes', True):
        # 使用自定义列表时，检查是否为空以及模式是否存在
        custom_modes = cm.get('custom_modes', [])
        if not custom_modes:
            warnings.append("⚠️ changeMode.modes 使用自定义模式但列表为空，模块将不起作用")
        else:
            available = set(ModeManager.get_choosable_modes())
            for m in custom_modes:
                if m not in available:
                    warnings.append(f"⚠️ changeMode.modes 包含当前不可选择的模式 '{m}'")

    return errors, warnings


def parse_transit_schedule_file() -> Dict:
    """
    解析上传的transitSchedule文件，提取transportMode
    支持两种格式：
    1. <transitRoute transportMode="bus">  (属性形式)
    2. <transitRoute><transportMode>bus</transportMode>  (子元素形式)

    返回: {'success': bool, 'modes': list, 'error': str, 'stats': dict}
    """
    result = {
        'success': False,
        'modes': [],
        'error': None,
        'stats': {
            'lines': 0,
            'routes': 0,
            'stops': 0
        }
    }

    file_key = 'transitScheduleFile'

    if file_key not in st.session_state.uploaded_files:
        result['error'] = "请先上传公交时刻表文件"
        return result

    try:
        content = st.session_state.uploaded_files[file_key]['content']
        filename = st.session_state.uploaded_files[file_key]['name']

        # 处理gzip压缩
        if filename.endswith('.gz'):
            content = gzip.decompress(content)

        # 解析XML
        if isinstance(content, bytes):
            content = content.decode('utf-8')

        root = ET.fromstring(content)

        modes_found = set()
        lines_count = 0
        routes_count = 0
        stops_count = 0

        # 遍历所有元素
        for elem in root.iter():
            # 处理命名空间
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag

            if tag == 'transitLine':
                lines_count += 1

            elif tag == 'transitRoute':
                routes_count += 1

                # 方式1: 检查属性 <transitRoute transportMode="bus">
                mode = elem.get('transportMode')
                if mode:
                    modes_found.add(mode)
                else:
                    # 方式2: 检查子元素 <transportMode>bus</transportMode>
                    for child in elem:
                        child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                        if child_tag == 'transportMode':
                            mode_text = child.text
                            if mode_text:
                                modes_found.add(mode_text.strip())
                            break

            elif tag == 'stopFacility':
                stops_count += 1

        result['success'] = True
        result['modes'] = sorted(list(modes_found))
        result['stats'] = {
            'lines': lines_count,
            'routes': routes_count,
            'stops': stops_count
        }

        # 保存解析结果
        st.session_state.transit_submodes_detected = result['modes']

        # 初始化公交子模式配置
        current_submodes = st.session_state.get('transit_submodes', {})
        for mode in result['modes']:
            if mode not in current_submodes:
                # 根据模式名称设置默认显示名
                display_names = {
                    'train': '火车 / Train',
                    'bus': '公交车 / Bus',
                    'subway': '地铁 / Subway',
                    'tram': '有轨电车 / Tram',
                    'ferry': '轮渡 / Ferry',
                    'light_rail': '轻轨 / Light Rail',
                    'metro': '地铁 / Metro',
                    'rail': '铁路 / Rail',
                }
                current_submodes[mode] = {
                    'display_name': display_names.get(mode, mode),
                    'enabled': True,
                    'scoring': {
                        'constant': -1.0,
                        'marginalUtilityOfTraveling_util_hr': -3.0,
                        'monetaryDistanceRate': 0.0,
                        'dailyMonetaryConstant': -2.0
                    }
                }

        # 移除不再存在的子模式
        modes_to_remove = [m for m in current_submodes if m not in result['modes']]
        for m in modes_to_remove:
            del current_submodes[m]

        st.session_state.transit_submodes = current_submodes

        # ========== 新增：自动添加 pt interaction 活动 ==========
        activity_params = st.session_state.get('activity_params', {})
        if 'pt interaction' not in activity_params:
            activity_params['pt interaction'] = {
                'typicalDuration': '00:00:00',  # 瞬时活动
                'minimalDuration': '',
                'openingTime': '',
                'closingTime': '',
                'performing': 0.0,  # 无效用
                'lateArrival': 0.0,  # 无惩罚
                'earlyDeparture': 0.0,  # 无惩罚
            }
            st.session_state.activity_params = activity_params

    except ET.ParseError as e:
        result['error'] = f"XML解析错误: {str(e)}"
    except Exception as e:
        result['error'] = f"解析异常: {str(e)}"

    return result


def parse_plans_file() -> Dict:
    """
    解析上传的 plans 文件，提取所有活动类型
    返回: {'success': bool, 'activities': list, 'error': str, 'stats': dict}
    """
    result = {
        'success': False,
        'activities': [],
        'error': None,
        'stats': {
            'persons': 0,
            'plans': 0,
            'activities': 0
        }
    }

    file_key = 'plansFile'

    if file_key not in st.session_state.uploaded_files:
        result['error'] = "请先上传人口计划文件"
        return result

    try:
        content = st.session_state.uploaded_files[file_key]['content']
        filename = st.session_state.uploaded_files[file_key]['name']

        # 处理gzip压缩
        if filename.endswith('.gz'):
            content = gzip.decompress(content)

        # 解析XML
        if isinstance(content, bytes):
            content = content.decode('utf-8')

        root = ET.fromstring(content)

        activities_found = set()
        persons_count = 0
        plans_count = 0
        activities_count = 0

        # 遍历所有元素
        for elem in root.iter():
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag

            if tag == 'person':
                persons_count += 1
            elif tag == 'plan':
                plans_count += 1
            elif tag in ['activity', 'act']:
                activities_count += 1
                act_type = elem.get('type')
                if act_type:
                    activities_found.add(act_type)

        result['success'] = True
        result['activities'] = sorted(list(activities_found))
        result['stats'] = {
            'persons': persons_count,
            'plans': plans_count,
            'activities': activities_count
        }

        # 保存解析结果
        st.session_state.detected_activity_types = result['activities']

        # 初始化活动参数
        current_activities = st.session_state.get('activity_params', {})

        for act_type in result['activities']:
            if act_type not in current_activities:
                # 默认配置
                defaults = {
                    'home': ('12:00:00', '', '', ''),
                    'work': ('08:00:00', '06:00:00', '07:00:00', '19:00:00'),
                    'education': ('06:00:00', '04:00:00', '08:00:00', '18:00:00'),
                    'shopping': ('01:00:00', '00:30:00', '09:00:00', '22:00:00'),
                    'leisure': ('02:00:00', '00:30:00', '', ''),
                    'other': ('02:00:00', '', '', ''),
                }

                typical, minimal, opening, closing = defaults.get(act_type, ('01:00:00', '', '', ''))

                current_activities[act_type] = {
                    'typicalDuration': typical,
                    'minimalDuration': minimal,
                    'openingTime': opening,
                    'closingTime': closing,
                    'performing': 6.0,
                    'lateArrival': -18.0,
                    'earlyDeparture': -0.0,
                }

        st.session_state.activity_params = current_activities

        # 如果启用了公交，自动添加 pt interaction
        if st.session_state.get('transit_enabled', False):
            if 'pt interaction' not in current_activities:
                current_activities['pt interaction'] = {
                    'typicalDuration': '00:00:00',
                    'minimalDuration': '',
                    'openingTime': '',
                    'closingTime': '',
                    'performing': 0.0,
                    'lateArrival': 0.0,
                    'earlyDeparture': 0.0,
                }
                st.session_state.activity_params = current_activities

    except ET.ParseError as e:
        result['error'] = f"XML解析错误: {str(e)}"
    except Exception as e:
        result['error'] = f"解析异常: {str(e)}"

    return result

def format_seconds_to_hms(seconds: float) -> str:
    """将秒转换为 HH:MM:SS 格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
# ============================================================
# Session State 初始化 / Session State Initialization
# ============================================================

def init_session_state():
    """初始化所有session state变量"""

    # ========== 1. 网络模式 ==========
    if 'network_modes' not in st.session_state:
        st.session_state.network_modes = {
            'car': {
                'display_name': '小汽车 / Car',
                'is_chain_based': True,
                'is_choosable': True,
                'scoring': {
                    'constant': 0.0,
                    'marginalUtilityOfTraveling_util_hr': -6.0,
                    'monetaryDistanceRate': -0.0002,
                    'dailyMonetaryConstant': -5.0
                }
            }
        }

    # ========== 2. 传送模式 ==========
    if 'teleported_modes' not in st.session_state:
        st.session_state.teleported_modes = {
            'walk': {
                'display_name': '步行 / Walk',
                'speed_kmh': 5.0,
                'beeline_factor': 1.3,
                'is_chain_based': False,
                'is_choosable': True,
                'scoring': {
                    'constant': 0.0,
                    'marginalUtilityOfTraveling_util_hr': -12.0,
                    'monetaryDistanceRate': 0.0,
                    'dailyMonetaryConstant': 0.0
                }
            },
            'bike': {
                'display_name': '自行车 / Bike',
                'speed_kmh': 15.0,
                'beeline_factor': 1.3,
                'is_chain_based': True,
                'is_choosable': True,
                'scoring': {
                    'constant': -2.0,
                    'marginalUtilityOfTraveling_util_hr': -6.0,
                    'monetaryDistanceRate': 0.0,
                    'dailyMonetaryConstant': 0.0
                }
            }
        }

    # ========== 3. 公交总开关 ==========
    if 'transit_enabled' not in st.session_state:
        st.session_state.transit_enabled = False

    # ========== 4. 公交子模式（从文件解析） ==========
    if 'transit_submodes_detected' not in st.session_state:
        st.session_state.transit_submodes_detected = []  # 解析结果

    if 'transit_submodes' not in st.session_state:
        st.session_state.transit_submodes = {}  # 配置详情

    if 'transit_separate_scoring' not in st.session_state:
        st.session_state.transit_separate_scoring = False

    # ========== 5. 接驳配置（引用传送模式） ==========
    if 'access_egress_config' not in st.session_state:
        st.session_state.access_egress_config = {
            'walk': {
                'enabled': True,
                'max_radius': 1000.0,
                'initial_search_radius': 500.0
            }
        }

    # ========== 6. PT 统一评分参数 ==========
    if 'pt_scoring' not in st.session_state:
        st.session_state.pt_scoring = {
            'constant': -1.0,
            'marginalUtilityOfTraveling_util_hr': -3.0,
            'monetaryDistanceRate': 0.0,
            'dailyMonetaryConstant': -2.5
        }

    # ========== 7. 公交扩展搜索半径 ==========
    if 'transit_extension_radius' not in st.session_state:
        st.session_state.transit_extension_radius = 200.0

    # ========== 8. 全局配置 ==========
    if 'global_config' not in st.session_state:
        st.session_state.global_config = {
            'randomSeed': 4711,
            'numberOfThreads': 4,
            'coordinateSystem': 'EPSG:4326',
            # 对应 GlobalConfigGroup.defaultDelimiter，MATSim 默认是分号
            'defaultDelimiter': ';',
        }

    # ========== 9. 网络模块配置（NetworkConfigGroup） ==========
    if 'network_config' not in st.session_state:
        st.session_state.network_config = {
            # 对应 network.timeVariantNetwork，默认 false
            'timeVariantNetwork': False,
            # 对应 network.inputChangeEventsFile
            'inputChangeEventsFile': '',
            # 对应 network.laneDefinitionsFile
            'laneDefinitionsFile': '',
            # 对应 network.inputCRS（Deprecated）
            'inputCRS': '',
        }
    # ========== TravelTimeCalculator 模块配置 ==========
    if 'travel_time_calculator_config' not in st.session_state:
        st.session_state.travel_time_calculator_config = {
            'travelTimeBinSize': 900.0,  # 15分钟 = 15*60秒
            'maxTime': 108000,  # 30小时 = 30*3600秒
            'travelTimeAggregator': 'optimistic',
            'travelTimeGetter': 'average',
            'calculateLinkTravelTimes': True,
            'calculateLinkToLinkTravelTimes': False,
            'analyzedModes': 'car',
            'filterModes': False,
            'separateModes': True,
        }

    # ========== Vehicles 模块配置 ==========
    # 注意：vehiclesFile 已在 file_config 中，此处仅作为模块级配置的占位
    if 'vehicles_config' not in st.session_state:
        st.session_state.vehicles_config = {
            # vehiclesFile 从 file_config 同步
        }

    # ========== VspExperimental 模块配置 ==========
    if 'vsp_experimental_config' not in st.session_state:
        st.session_state.vsp_experimental_config = {
            'vspDefaultsCheckingLevel': 'ignore',
            'logitScaleParamForPlansRemoval': 1.0,
            'isGeneratingBoardingDeniedEvent': False,
            'isAbleToOverwritePtInteractionParams': False,
            'isUsingOpportunityCostOfTimeForLocationChoice': True,
            'writingOutputEvents': True,
        }
    # ========== 10. LinkStats 配置（LinkStatsConfigGroup） ==========
    if 'linkstats_config' not in st.session_state:
        st.session_state.linkstats_config = {
            # 源码默认 50，为避免默认就输出体量较大，这里默认填 0 = 关闭
            'writeLinkStatsInterval': 0,
            # 源码默认 5
            'averageLinkStatsOverIterations': 5,
        }

    # ========== 11. 文件配置 ==========
    if 'file_config' not in st.session_state:
        st.session_state.file_config = {
            'networkFile': '',
            'plansFile': '',
            'transitScheduleFile': '',
            'transitVehiclesFile': '',
            'vehiclesFile': '',
            'facilitiesFile': '',
            'countsFile': '',
            'networkChangeEventsFile': '',
            'laneDefinitionsFile': '',
        }

    # ========== 12. 上传的文件内容 ==========
    if 'uploaded_files' not in st.session_state:
        st.session_state.uploaded_files = {}



    # ========== 13. 控制器配置 ==========
    if 'controller_config' not in st.session_state:
        st.session_state.controller_config = {
            # 基本
            'outputDirectory': './output',
            'runId': 'run001',
            'firstIteration': 0,
            'lastIteration': 100,

            # 仿真引擎 / 路由
            'mobsim': 'qsim',                          # qsim / jdeqsim / hermes
            'routingAlgorithmType': 'SpeedyALT',       # Dijkstra / AStarLandmarks / SpeedyALT
            'enableLinkToLinkRouting': False,          # 是否启用 link-to-link 路由

            # 输出频率
            'writeEventsInterval': 50,                 # 写 events 间隔
            'writePlansInterval': 50,                  # 写 plans 间隔
            'writeTripsInterval': 50,                  # 写 trips 间隔
            'writeSnapshotsInterval': 1,               # 写 snapshot 间隔

            # 文件格式与压缩
            'eventsFileFormat': ['xml'],               # 多选：xml, pb, json
            'snapshotFormat': [],                      # 多选：transims, googleearth, otfvis, positionevents
            'overwriteFiles': 'deleteDirectoryIfExists',  # 输出目录策略
            'compressionType': 'gzip',                 # none / gzip / lz4 / zst

            # 图表与数据清理
            'createGraphsInterval': 1,                 # 生成图表间隔 (0=不生成)
            'dumpDataAtEnd': True,                     # 结束时是否 dump 完整数据
            'cleanItersAtEnd': 'keep',                 # keep / delete

            # 评分函数与监控
            'createScoringFunctionType': 'IterationStarts',  # IterationStarts / BeforeMobsim
            'memoryObserverInterval': 60,              # 内存监控打印间隔（秒）
        }



    # ========== 12. QSim配置 ==========
    if 'qsim_config' not in st.session_state:
        st.session_state.qsim_config = {
            # 时间设置
            'startTime': '00:00:00',   # 仿真开始时间
            'endTime': '30:00:00',     # 仿真结束时间（默认30小时）

            # 流量与容量
            'timeStepSize': 1.0,       # timeStepSize
            'snapshotPeriod': 0.0,     # snapshotperiod，0=不输出中间快照
            'flowCapacityFactor': 1.0,
            'storageCapacityFactor': 1.0,

            # 卡住与线程
            'stuckTime': 10.0,
            'removeStuckVehicles': False,
            'notifyAboutStuckVehicles': False,
            'numberOfThreads': 4,

            # 动力学与时间解释
            'trafficDynamics': 'queue',   # queue / withHoles / kinematicWaves
            'simStarttimeInterpretation': 'maxOfStarttimeAndEarliestActivityEnd',
            'simEndtimeInterpretation': 'minOfEndtimeAndMobsimFinished',
            'usePersonIdForMissingVehicleId': True,

            # 快照与 link 动力学
            'filterSnapshots': 'no',        # no / withLinkAttributes
            'linkDynamics': 'FIFO',         # FIFO / PassingQ / SeepageQ
            'nodeOffset': 0.0,

            # 渗流与车辆行为
            'isSeepModeStorageFree': True,
            'vehicleBehavior': 'teleport',  # teleport / wait / exception
            'snapshotStyle': 'queue',       # equiDist / queue / withHoles / ...
            'vehiclesSource': 'defaultVehicle',  # defaultVehicle / modeVehicleTypesFromVehiclesData / fromVehiclesData
            'insertingWaitingVehiclesBeforeDrivingVehicles': True,

            # 车道与渗流模式
            'useLanes': False,
            'seepMode': 'bike',          # 渗流模式，默认 bike
            'isRestrictingSeepage': True,
        }

    # ========== 13. Hermes配置 ==========
    if 'hermes_config' not in st.session_state:
        st.session_state.hermes_config = {
            # 对应 HermesConfigGroup
            'endTime': '30:00:00',          # 仿真结束时间（同 SIM_STEPS）
            'flowCapacityFactor': 1.0,      # 流量容量因子
            'storageCapacityFactor': 1.0,   # 存储容量因子
            'stuckTime': 10,                # 卡住时间（秒）
            'useDeterministicPt': False,    # 是否采用确定性PT
        }

    # ========== 14. 评分基础配置 ==========
    if 'scoring_base_config' not in st.session_state:
        st.session_state.scoring_base_config = {
            'learningRate': 1.0,
            'brainExpBeta': 1.0,
            'lateArrival': -18.0,
            'performing': 6.0,
            'waitingPt': -2.0,
        }

    # ========== 16. 活动参数 ==========
    # ========== 16. 活动参数 ==========
    if 'activity_params' not in st.session_state:
        st.session_state.activity_params = {
            'home': {
                'typicalDuration': '12:00:00',
                'minimalDuration': '',
                'openingTime': '',
                'closingTime': '',
                'performing': 6.0,  # 新增：每个活动独立
                'lateArrival': -18.0,  # 新增：每个活动独立
                'earlyDeparture': -0.0,  # 新增：每个活动独立
            },
            'work': {
                'typicalDuration': '08:00:00',
                'minimalDuration': '06:00:00',
                'openingTime': '07:00:00',
                'closingTime': '19:00:00',
                'performing': 6.0,
                'lateArrival': -18.0,
                'earlyDeparture': -0.0,
            },
        }

    # 检测到的活动类型（从 plans 文件解析）
    if 'detected_activity_types' not in st.session_state:
        st.session_state.detected_activity_types = []
    # 检测到的活动持续时间统计
    if 'detected_activity_durations' not in st.session_state:
        st.session_state.detected_activity_durations = {}
    # ========== 新增：如果启用公交，确保 pt interaction 存在 ==========
    if st.session_state.get('transit_enabled', False):
        if 'pt interaction' not in st.session_state.activity_params:
            st.session_state.activity_params['pt interaction'] = {
                'typicalDuration': '00:00:00',
                'minimalDuration': '',
                'openingTime': '',
                'closingTime': '',
                'performing': 0.0,
                'lateArrival': 0.0,
                'earlyDeparture': 0.0,
            }
    # ========== 17. 重规划配置 ==========
    # 在现有 replanning_config 基础上添加：
    if 'replanning_config' not in st.session_state:
        st.session_state.replanning_config = {
            'maxAgentPlanMemorySize': 5,
            'fractionOfIterationsToDisableInnovation': 0.8,
            # 新增以下参数
            'planSelectorForRemoval': 'WorstPlanSelector',
            'externalExeConfigTemplate': '',
            'externalExeTmpFileRootDir': '',
            'externalExeTimeOut': 3600
        }
    else:
        # 如果已存在，确保新参数也被初始化
        st.session_state.replanning_config.setdefault('planSelectorForRemoval', 'WorstPlanSelector')
        st.session_state.replanning_config.setdefault('externalExeConfigTemplate', '')
        st.session_state.replanning_config.setdefault('externalExeTmpFileRootDir', '')
        st.session_state.replanning_config.setdefault('externalExeTimeOut', 3600)

    # ========== 18. 策略配置 ==========
    if 'strategy_config' not in st.session_state:
        st.session_state.strategy_config = [
            {'name': 'BestScore', 'weight': 0.6},
            {'name': 'ReRoute', 'weight': 0.2},
            {'name': 'TimeAllocationMutator', 'weight': 0.1},
            {'name': 'SubtourModeChoice', 'weight': 0.1},
        ]

    # ========== 19. 时间变异配置 ==========
    if 'time_mutator_config' not in st.session_state:
        st.session_state.time_mutator_config = {
            'mutationRange': 7200.0,
        }

    # ========== 20. changeMode 配置 ==========
    if 'changemode_config' not in st.session_state:
        st.session_state.changemode_config = {
            # modes 的来源：True=跟随 subtourModeChoice.modes，False=自定义
            'use_subtour_modes': True,
            # 若 use_subtour_modes=False，则使用此列表
            'custom_modes': [],
            # 是否忽略小汽车可用性（与 Config 中 ignoreCarAvailability 含义一致）
            'ignoreCarAvailability': True,
            # 切换行为枚举
            'modeSwitchBehavior': 'fromSpecifiedModesToSpecifiedModes',
        }
    # ========== 21. Counts 配置 ==========
    if 'counts_config' not in st.session_state:
        st.session_state.counts_config = {
            # 是否启用 counts 由是否配置了 countsFile 决定（见 file_config）
            'outputFormat': 'txt',              # txt / html / all
            'distanceFilter': None,             # 浮点数或 None
            'distanceFilterCenterNode': '',     # 节点ID
            'countsScaleFactor': 1.0,           # 采样修正因子
            'writeCountsInterval': 10,          # 写出间隔
            'averageCountsOverIterations': 5,   # 跨轮平均窗口
            'analyzedModes': 'car',             # 参与分析的mode列表，逗号分隔
            'filterModes': False,               # 是否按模式过滤
            'inputCRS': '',                     # 已废弃，保留兼容
        }

    # ========== 22. EventsManager 配置 ==========
    if 'events_manager_config' not in st.session_state:
        st.session_state.events_manager_config = {
            # 0 表示 UI 里的“自动决定”，生成 XML 时不会写出该参数
            'numberOfThreads': 0,
            'estimatedNumberOfEvents': 0,
            'synchronizeOnSimSteps': True,
            'oneThreadPerHandler': False,
            'eventsQueueSize': 131072,  # 65536*2, 与源码默认保持一致
        }

    # ========== 23. 生成的XML ==========
    if 'generated_xml' not in st.session_state:
        st.session_state.generated_xml = None

    # ========== 新增：planInheritance 模块配置 ==========
    if 'planinheritance_config' not in st.session_state:
        st.session_state.planinheritance_config = {
            'enabled': False
        }
    # ========== 扩展：plans 模块配置（除了文件路径） ==========
    if 'plans_config' not in st.session_state:
        st.session_state.plans_config = {
            'networkRouteType': 'LinkNetworkRoute',
            'activityDurationInterpretation': 'tryEndTimeThenDuration',
            'tripDurationHandling': 'ignoreDelays',
            'removingUnnecessaryPlanAttributes': False,
            'inputCRS': '',
            'inputPersonAttributesFile': '',
            'insistingOnUsingDeprecatedPersonAttributeFile': False,
            'handlingOfPlansWithoutRoutingMode': 'reject'
        }

    # ========== 新增：ptCounts 模块配置 ==========
    if 'ptcounts_config' not in st.session_state:
        st.session_state.ptcounts_config = {
            'outputformat': 'txt',
            'distanceFilter': None,
            'distanceFilterCenterNode': '',
            'inputOccupancyCountsFile': '',
            'inputBoardCountsFile': '',
            'inputAlightCountsFile': '',
            'countsScaleFactor': 1.0,
            'ptCountsInterval': 10
        }
    # ========== 新增/更新：Routing 模块完整配置 ==========
    if 'routing_config' not in st.session_state:
        st.session_state.routing_config = {
            'routingRandomness': 3.0,
            'clearDefaultTeleportedModeParams': False,
            'accessEgressType': 'none',
            'networkRouteConsistencyCheck': 'abortOnInconsistency',
        }

    # ========== 新增/更新：Scoring 模块完整配置 ==========
    if 'scoring_config' not in st.session_state:
        st.session_state.scoring_config = {
            # 顶层参数 (ReflectiveDelegate)
            'learningRate': 1.0,
            'brainExpBeta': 1.0,
            'pathSizeLogitBeta': 1.0,
            'writeExperiencedPlans': False,
            'fractionOfIterationsToStartScoreMSA': None,  # None = 不设置
            'usingOldScoringBelowZeroUtilityDuration': False,
            'writeScoreExplanations': False,
        }

    # ========== 新增：Scoring Parameters (per subpopulation) ==========
    if 'scoring_parameters' not in st.session_state:
        st.session_state.scoring_parameters = {
            # 默认子人口 (subpopulation = None)
            None: {
                'subpopulation': None,
                'lateArrival': -18.0,
                'earlyDeparture': 0.0,
                'performing': 6.0,
                'waiting': 0.0,
                'marginalUtilityOfMoney': 1.0,
                'utilityOfLineSwitch': -1.0,
                'waitingPt': None,  # None = 使用 pt 的 marginalUtilityOfTraveling
            }
        }

    # ========== 更新：Activity Params 添加新字段 ==========
    # 确保现有 activity_params 有完整字段
    for act_type, act_params in st.session_state.get('activity_params', {}).items():
        act_params.setdefault('priority', 1.0)
        act_params.setdefault('latestStartTime', '')
        act_params.setdefault('earliestEndTime', '')
        act_params.setdefault('scoringThisActivityAtAll', True)
        act_params.setdefault('typicalDurationScoreComputation', 'relative')

    # ========== 更新：Mode Params 添加新字段 ==========
    # 确保 network_modes 和 teleported_modes 有完整的评分字段
    for mode_name, mode_config in st.session_state.get('network_modes', {}).items():
        scoring = mode_config.setdefault('scoring', {})
        scoring.setdefault('marginalUtilityOfDistance_util_m', 0.0)
        scoring.setdefault('dailyUtilityConstant', 0.0)

    for mode_name, mode_config in st.session_state.get('teleported_modes', {}).items():
        scoring = mode_config.setdefault('scoring', {})
        scoring.setdefault('marginalUtilityOfDistance_util_m', 0.0)
        scoring.setdefault('dailyUtilityConstant', 0.0)

    # ========== 新增/更新：SubtourModeChoice 模块完整配置 ==========
    if 'subtour_mode_choice_config' not in st.session_state:
        st.session_state.subtour_mode_choice_config = {
            'modes': [],
            'chainBasedModes': [],
            'considerCarAvailability': False,
            'probaForRandomSingleTripMode': 0.0,
            'coordDistance': 0.0,
            'behavior': 'fromSpecifiedModesToSpecifiedModes',
            'modes_override': False,
            'chainBasedModes_override': False,
        }
    # ========== SwissRailRaptor 模块配置 ==========
    if 'swiss_rail_raptor_config' not in st.session_state:
        st.session_state.swiss_rail_raptor_config = {
            # 顶层参数
            'useRangeQuery': False,
            'useIntermodalAccessEgress': True,  # 启用公交时通常需要
            'intermodalAccessEgressModeSelection': 'CalcLeastCostModePerStop',
            'useModeMappingForPassengers': False,
            'useCapacityConstraints': False,
            'scoringParameters': 'Default',
            'transferPenaltyBaseCost': 0.0,
            'transferPenaltyMinCost': None,  # None = -Infinity
            'transferPenaltyMaxCost': None,  # None = +Infinity
            'transferPenaltyCostPerTravelTimeHour': 0.0,
            'transferWalkMargin': 5.0,
            'intermodalLegOnlyHandling': 'forbid',
            'transferCalculation': 'Initial',
        }

    # SwissRailRaptor 接驳模式配置 (从 access_egress_config 同步)
    if 'raptor_intermodal_access_egress' not in st.session_state:
        st.session_state.raptor_intermodal_access_egress = []

    # ========== TimeAllocationMutator 模块配置 ==========
    if 'time_allocation_mutator_config' not in st.session_state:
        st.session_state.time_allocation_mutator_config = {
            'mutationRange': 1800.0,
            'mutationAffectsDuration': True,
            'latestActivityEndTime': '24:00:00',
            'mutationRangeStep': 1.0,
            'mutateAroundInitialEndTimeOnly': False,
        }

    # ========== Transit 模块配置 ==========
    if 'transit_config' not in st.session_state:
        st.session_state.transit_config = {
            'useTransit': False,  # 与 transit_enabled 同步
            'transitModes': 'pt',
            'routingAlgorithmType': 'SwissRailRaptor',
            'inputScheduleCRS': '',
            'usingTransitInMobsim': True,
            'boardingAcceptance': 'checkLineAndStop',
            # 废弃参数
            'transitLinesAttributesFile': '',
            'transitStopsAttributesFile': '',
            'insistingOnUsingDeprecatedAttributeFiles': False,
        }

    # ========== TransitRouter 模块配置 ==========
    if 'transit_router_config' not in st.session_state:
        st.session_state.transit_router_config = {
            'searchRadius': 1000.0,
            'extensionRadius': 200.0,
            'maxBeelineWalkConnectionDistance': 100.0,
            'additionalTransferTime': 0.0,
            'directWalkFactor': 1.0,
        }
    # ========== 24. 当前步骤 ==========
    if 'current_step' not in st.session_state:
        st.session_state.current_step = 'modes'
    # 导航目标（按钮触发后使用，避免直接修改radio绑定的key）
    if 'nav_target' not in st.session_state:
        st.session_state.nav_target = None


# 执行初始化
init_session_state()


# ============================================================
# 辅助函数 / Helper Functions
# ============================================================

def create_param_label(cn: str, en: str) -> str:
    """创建双语参数标签"""
    return f"**{cn}** / {en}"


def create_help_text(cn: str, en: str) -> str:
    """创建双语帮助文本"""
    return f"{cn}\n\n{en}"


def parse_time_to_seconds(time_str: str) -> Optional[int]:
    """将 HH:MM[:SS] 文本安全转换为秒；失败时返回 None"""
    if not time_str:
        return None
    try:
        parts = time_str.split(":")
        if len(parts) == 2:
            h, m = parts
            s = 0
        elif len(parts) == 3:
            h, m, s = parts
        else:
            return None
        return int(h) * 3600 + int(m) * 60 + int(s)
    except Exception:
        return None


def format_time_display(seconds: float) -> str:
    """将秒转换为易读格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours > 0:
        return f"{hours}小时{minutes}分钟" if minutes > 0 else f"{hours}小时"
    return f"{minutes}分钟"


def speed_ms_to_kmh(speed_ms: float) -> float:
    """m/s 转 km/h"""
    return speed_ms * 3.6


def speed_kmh_to_ms(speed_kmh: float) -> float:
    """km/h 转 m/s"""
    return speed_kmh / 3.6


def render_config_check_dialog():
    """渲染配置检测对话框"""

    st.markdown("### 🔍 配置一致性检测 / Configuration Consistency Check")

    st.markdown("""
    <div class="info-box">
    <b>说明 / Description</b><br>
    此检测基于 MATSim 官方配置一致性检查器，包括：<br>
    • <code>ConfigConsistencyCheckerImpl</code> - 基础配置检查<br>
    • <code>VspConfigConsistencyCheckerImpl</code> - VSP 标准检查<br>
    • <code>SwissRailRaptorConfigGroup</code> - 公交路由检查<br>
    • <code>UnmaterializedConfigGroupChecker</code> - 废弃模块检查<br><br>
    点击「开始检测」分析当前配置是否存在问题。
    </div>
    """, unsafe_allow_html=True)

    if st.button("🔍 开始检测", type="primary", use_container_width=True):
        with st.spinner("正在检测配置..."):
            issues = run_config_consistency_checks()

        st.session_state['config_check_issues'] = issues

    # 显示检测结果
    if 'config_check_issues' in st.session_state:
        issues = st.session_state['config_check_issues']

        if not issues:
            st.markdown("""
            <div class="success-box">
            ✅ <b>恭喜！未发现配置问题。</b><br>
            ✅ <b>Congratulations! No configuration issues found.</b>
            </div>
            """, unsafe_allow_html=True)
        else:
            # 统计
            errors = [i for i in issues if i['severity'] == 'error']
            warnings = [i for i in issues if i['severity'] == 'warning']
            infos = [i for i in issues if i['severity'] == 'info']

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("总计问题", len(issues))
            with col2:
                st.metric("❌ 错误", len(errors), delta=None, delta_color="inverse")
            with col3:
                st.metric("⚠️ 警告", len(warnings))
            with col4:
                st.metric("ℹ️ 信息", len(infos))

            # 按类别分组
            categories = {}
            for issue in issues:
                cat = issue['category']
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(issue)

            # 显示问题
            st.markdown("---")

            # 先显示错误
            if errors:
                st.markdown("### ❌ 错误 / Errors")
                for issue in errors:
                    render_issue_card(issue)

            # 再显示警告
            if warnings:
                st.markdown("### ⚠️ 警告 / Warnings")
                for issue in warnings:
                    render_issue_card(issue)

            # 最后显示信息
            if infos:
                st.markdown("### ℹ️ 建议 / Suggestions")
                for issue in infos:
                    render_issue_card(issue)

            # 按类别查看
            with st.expander("📂 按类别查看 / View by Category", expanded=False):
                for cat, cat_issues in sorted(categories.items()):
                    st.markdown(f"**{cat}** ({len(cat_issues)} issues)")
                    for issue in cat_issues:
                        severity_icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}[issue['severity']]
                        st.markdown(f"- {severity_icon} {issue['message_cn'][:50]}...")


def render_issue_card(issue: dict):
    """渲染单个问题卡片"""

    severity_styles = {
        'error': ('error-box', '❌'),
        'warning': ('warning-box', '⚠️'),
        'info': ('info-box', 'ℹ️')
    }

    box_class, icon = severity_styles.get(issue['severity'], ('info-box', 'ℹ️'))

    with st.expander(f"{icon} [{issue['category']}] {issue['message_cn'][:60]}...", expanded=False):
        # 中文部分
        st.markdown(f"""
        **🇨🇳 问题描述：**

        {issue['message_cn']}

        **修复建议：**

        {issue['fix_cn']}
        """)

        st.markdown("---")

        # 英文部分
        st.markdown(f"""
        **🇬🇧 Issue Description:**

        {issue['message_en']}

        **Fix Suggestion:**

        {issue['fix_en']}
        """)

        st.caption(f"来源 / Source: `{issue['source']}`")
        st.caption(f"ID: `{issue['id']}`")
# ============================================================
# 文件上传组件 / File Upload Components
# ============================================================

def render_file_upload(
        label_cn: str,
        label_en: str,
        file_key: str,
        required: bool = False,
        file_types: Optional[List[str]] = None,
        help_text: str = ""
) -> Optional[str]:
    """
    渲染文件上传组件
    返回文件名（如果已上传或已配置路径）
    """
    if file_types is None:
        file_types = ['xml', 'gz']

    # 标签和状态
    status_html = '<span class="required-tag">必需</span>' if required else ''
    st.markdown(f"**{label_cn}** / {label_en} {status_html}", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        # 文件上传
        uploaded = st.file_uploader(
            "上传文件",
            type=file_types,
            key=f"upload_{file_key}",
            label_visibility="collapsed",
            help=help_text
        )

        if uploaded is not None:
            # 保存上传的文件到本地并记录路径（用于生成 config.xml）
            content = uploaded.read()
            uploads_dir = os.path.join(".", "uploaded_inputs")
            os.makedirs(uploads_dir, exist_ok=True)
            save_path = os.path.join(uploads_dir, uploaded.name)
            with open(save_path, "wb") as f:
                f.write(content)

            st.session_state.uploaded_files[file_key] = {
                'name': uploaded.name,
                'content': content,
                'saved_path': save_path
            }
            st.session_state.file_config[file_key] = save_path
            uploaded.seek(0)
            st.success(f"✅ 已保存到 {save_path}")

    with col2:
        # 手动输入路径（直接显示，不用expander）
        manual_path = st.text_input(
            "或输入路径",
            value=st.session_state.file_config.get(file_key, ''),
            key=f"path_{file_key}",
            placeholder="例如: ./input/file.xml.gz",
            label_visibility="collapsed"
        )
        if manual_path:
            st.session_state.file_config[file_key] = manual_path

    with col3:
        # 状态显示
        current_file = st.session_state.file_config.get(file_key, '')
        if file_key in st.session_state.uploaded_files:
            saved = st.session_state.uploaded_files[file_key].get('saved_path')
            if saved:
                st.success(f"✅ 已保存\n{saved}")
            else:
                st.success("✅ 已上传")
        elif current_file:
            st.info("📁 已配置")
        elif required:
            st.error("❌ 未配置")
        else:
            st.caption("可选")

    return st.session_state.file_config.get(file_key, '')


def parse_transit_schedule(file_key: str = 'transitScheduleFile') -> Dict:
    """
    解析上传的transitSchedule文件，提取模式信息
    """
    result = {
        'modes': set(),
        'lines': [],
        'stops': 0,
        'success': False,
        'error': None
    }

    if file_key not in st.session_state.uploaded_files:
        return result

    try:
        content = st.session_state.uploaded_files[file_key]['content']
        filename = st.session_state.uploaded_files[file_key]['name']

        # 处理gzip压缩
        if filename.endswith('.gz'):
            content = gzip.decompress(content)

        # 解析XML
        root = ET.fromstring(content)

        # 查找所有transitRoute的transportMode
        for route in root.iter():
            if route.tag.endswith('transitRoute') or route.tag == 'transitRoute':
                mode = route.get('transportMode')
                if mode:
                    result['modes'].add(mode)

        # 统计线路
        for line in root.iter():
            if line.tag.endswith('transitLine') or line.tag == 'transitLine':
                line_id = line.get('id')
                if line_id:
                    result['lines'].append(line_id)

        # 统计站点
        for stop in root.iter():
            if stop.tag.endswith('stopFacility') or stop.tag == 'stopFacility':
                result['stops'] += 1

        result['success'] = True
        result['modes'] = list(result['modes'])

        # 保存到session state
        st.session_state.parsed_transit_info = {
            'modes_in_schedule': result['modes'],
            'lines_count': len(result['lines']),
            'stops_count': result['stops'],
            'is_parsed': True
        }

    except Exception as e:
        result['error'] = str(e)

    return result


def parse_transit_vehicles(file_key: str = 'transitVehiclesFile') -> Dict:
    """
    解析上传的transitVehicles文件，提取车辆类型信息
    """
    result = {
        'vehicle_types': [],
        'success': False,
        'error': None
    }

    if file_key not in st.session_state.uploaded_files:
        return result

    try:
        content = st.session_state.uploaded_files[file_key]['content']
        filename = st.session_state.uploaded_files[file_key]['name']

        if filename.endswith('.gz'):
            content = gzip.decompress(content)

        root = ET.fromstring(content)

        for vtype in root.iter():
            if vtype.tag.endswith('vehicleType') or vtype.tag == 'vehicleType':
                type_id = vtype.get('id')
                if type_id:
                    result['vehicle_types'].append(type_id)

        result['success'] = True
        st.session_state.parsed_transit_info['vehicle_types'] = result['vehicle_types']

    except Exception as e:
        result['error'] = str(e)

    return result


def render_travel_time_calculator_configuration():
    """渲染 TravelTimeCalculator 模块配置"""

    st.markdown('<div class="module-header">⏱️ 出行时间计算器配置 / TravelTimeCalculator Settings</div>',
                unsafe_allow_html=True)

    ttc = st.session_state.travel_time_calculator_config

    st.markdown("""
    <div class="info-box">
    <b>模块说明 / Description</b><br>
    • 控制如何收集、聚合和提供路网上的出行时间数据。<br>
    • 出行时间被分割到时间桶（time bins）中，用于路由器计算最短路径。<br>
    • 这些数据在每轮迭代中更新，反映当前的拥堵状况。<br><br>
    <b>使用建议 / Tips</b><br>
    • travelTimeBinSize 越小，时间精度越高，但内存消耗越大。<br>
    • 通常 15 分钟（900秒）是一个合理的默认值。<br>
    • 若启用 link-to-link 出行时间，需在 controller 中设置相应的路由算法。<br>
    </div>
    """, unsafe_allow_html=True)

    # ===== 时间桶参数 =====
    st.markdown("#### ⏱️ 时间桶参数 / Time Bin Parameters")

    col1, col2 = st.columns(2)

    with col1:
        ttc['travelTimeBinSize'] = st.number_input(
            create_param_label("时间桶大小 / travelTimeBinSize (秒)",
                               "Travel Time Bin Size (config.travelTimeCalculator.travelTimeBinSize)"),
            min_value=60.0,
            max_value=3600.0,
            value=float(ttc.get('travelTimeBinSize', 900.0)),
            step=60.0,
            help=create_help_text(
                "将出行时间聚合到路由器使用的时间窗口大小（秒）。"
                "较小的值提高精度但增加内存消耗。默认 900 秒（15分钟）。",
                "Size of the time-window (in seconds) for aggregating travel times for the router. "
                "Smaller values increase precision but also memory consumption. Default 900s (15min)."
            )
        )
        # 显示人性化时间
        st.caption(f"= {ttc['travelTimeBinSize'] / 60:.0f} 分钟 / {ttc['travelTimeBinSize'] / 60:.0f} minutes")

    with col2:
        ttc['maxTime'] = st.number_input(
            create_param_label("最大时间 / maxTime (秒)",
                               "Max Time (config.travelTimeCalculator.maxTime)"),
            min_value=3600,
            max_value=172800,  # 48小时
            value=int(ttc.get('maxTime', 108000)),
            step=3600,
            help=create_help_text(
                "分割成时间桶的总时间长度（秒）。超过此时间后的出行时间被聚合到最后一个桶。"
                "默认 108000 秒（30小时）。",
                "Total time period split into time bins. Travel times after maxTime are aggregated "
                "into an additional bin. Default 108000s (30 hours)."
            )
        )
        st.caption(f"= {ttc['maxTime'] / 3600:.0f} 小时 / {ttc['maxTime'] / 3600:.0f} hours")

    # ===== 聚合与获取方式 =====
    st.markdown("---")
    st.markdown("#### 📊 聚合与获取方式 / Aggregation & Getter")

    col1, col2 = st.columns(2)

    with col1:
        aggregator_options = list(TRAVEL_TIME_AGGREGATOR_OPTIONS.keys())
        current_aggregator = ttc.get('travelTimeAggregator', 'optimistic')

        ttc['travelTimeAggregator'] = st.selectbox(
            create_param_label("出行时间聚合方式 / travelTimeAggregator",
                               "Travel Time Aggregator"),
            options=aggregator_options,
            index=aggregator_options.index(current_aggregator) if current_aggregator in aggregator_options else 0,
            format_func=lambda x: TRAVEL_TIME_AGGREGATOR_OPTIONS[x][0],
            help=create_help_text(
                "处理拥堵时间桶中无进入事件的方式。"
                "optimistic 假设自由流速度（可能过于乐观）。",
                "How to deal with congested time bins with no link entry events. "
                "'optimistic' assumes free speed (may be too optimistic)."
            )
        )
        st.caption(TRAVEL_TIME_AGGREGATOR_OPTIONS[ttc['travelTimeAggregator']][1])

    with col2:
        getter_options = list(TRAVEL_TIME_GETTER_OPTIONS.keys())
        current_getter = ttc.get('travelTimeGetter', 'average')

        ttc['travelTimeGetter'] = st.selectbox(
            create_param_label("出行时间获取方式 / travelTimeGetter",
                               "Travel Time Getter"),
            options=getter_options,
            index=getter_options.index(current_getter) if current_getter in getter_options else 0,
            format_func=lambda x: TRAVEL_TIME_GETTER_OPTIONS[x][0],
            help=create_help_text(
                "处理时间桶内不同进入时间位置的方式。"
                "average 返回平均值；linearinterpolation 在时间桶间进行插值。",
                "How to deal with link entry times at different positions during the time bin. "
                "'average' returns the average; 'linearinterpolation' interpolates between bins."
            )
        )
        st.caption(TRAVEL_TIME_GETTER_OPTIONS[ttc['travelTimeGetter']][1])

    # ===== 计算选项 =====
    st.markdown("---")
    st.markdown("#### ⚙️ 计算选项 / Calculation Options")

    col1, col2 = st.columns(2)

    with col1:
        ttc['calculateLinkTravelTimes'] = st.checkbox(
            create_param_label("计算Link出行时间 / calculateLinkTravelTimes",
                               "Calculate Link Travel Times"),
            value=bool(ttc.get('calculateLinkTravelTimes', True)),
            help=create_help_text(
                "是否计算每条Link的出行时间。这是标准路由所需的。",
                "Whether to calculate travel times for each link. Required for standard routing."
            )
        )

        ttc['calculateLinkToLinkTravelTimes'] = st.checkbox(
            create_param_label("计算Link-to-Link出行时间 / calculateLinkToLinkTravelTimes",
                               "Calculate Link-to-Link Travel Times"),
            value=bool(ttc.get('calculateLinkToLinkTravelTimes', False)),
            help=create_help_text(
                "是否计算Link间（包含转向）的出行时间。"
                "若启用，需在 controller 中设置 enableLinkToLinkRouting=true 且使用 Dijkstra 算法。",
                "Whether to calculate link-to-link travel times (including turn times). "
                "Requires enableLinkToLinkRouting=true and Dijkstra routing algorithm."
            )
        )

    with col2:
        ttc['separateModes'] = st.checkbox(
            create_param_label("分离模式统计 / separateModes",
                               "Separate Modes"),
            value=bool(ttc.get('separateModes', True)),
            help=create_help_text(
                "若启用，每种模式分别测量和聚合Link出行时间。"
                "若禁用，所有使用Link的车辆一起统计（向后兼容）。",
                "If true, link travel times are measured and aggregated separately per mode. "
                "If false, all vehicles using the link are aggregated together (backward compatibility)."
            )
        )

        # 仅在 separateModes=False 时显示过滤选项
        if not ttc['separateModes']:
            ttc['filterModes'] = st.checkbox(
                create_param_label("按模式过滤 / filterModes",
                                   "Filter Modes"),
                value=bool(ttc.get('filterModes', False)),
                help=create_help_text(
                    "（仅当 separateModes=false 时生效）"
                    "若启用，仅统计 analyzedModes 中指定的模式。",
                    "(Only when separateModes=false) "
                    "If true, only modes in analyzedModes are included."
                )
            )
        else:
            ttc['filterModes'] = False

    # ===== 分析模式 =====
    st.markdown("---")
    st.markdown("#### 🚗 分析模式 / Analyzed Modes")

    # 获取可用模式
    network_modes = list(st.session_state.get('network_modes', {}).keys())
    teleported_modes = list(st.session_state.get('teleported_modes', {}).keys())
    all_available_modes = network_modes + teleported_modes
    if st.session_state.get('transit_enabled', False):
        all_available_modes.append('pt')

    # 解析当前值
    current_modes_str = ttc.get('analyzedModes', 'car')
    current_modes = [m.strip() for m in current_modes_str.split(',') if m.strip()]
    # 确保只选择可用的模式
    current_modes = [m for m in current_modes if m in all_available_modes] or (
        ['car'] if 'car' in all_available_modes else [])

    if all_available_modes:
        selected_modes = st.multiselect(
            create_param_label("分析的模式 / analyzedModes",
                               "Analyzed Modes (config.travelTimeCalculator.analyzedModes)"),
            options=all_available_modes,
            default=current_modes,
            help=create_help_text(
                "（向后兼容；仅当 separateModes=false && filterModes=true 时使用）"
                "被出行时间收集器统计的模式。默认 car（也包含PT模块中的公交车）。",
                "(Backward compatibility; only used when separateModes=false && filterModes=true) "
                "Transport modes respected by the travel time collector. Default 'car' (includes buses from PT)."
            )
        )
        ttc['analyzedModes'] = ','.join(selected_modes) if selected_modes else 'car'
    else:
        st.warning("请先在「出行模式配置」中添加模式")
        ttc['analyzedModes'] = 'car'

    st.session_state.travel_time_calculator_config = ttc


def render_vehicles_configuration():
    """渲染 Vehicles 模块配置"""

    st.markdown('<div class="module-header">🚗 车辆配置 / Vehicles Settings</div>',
                unsafe_allow_html=True)

    st.markdown("""
    <div class="info-box">
    <b>模块说明 / Description</b><br>
    • 控制 MATSim 车辆类型的定义和输入。<br>
    • 车辆文件定义了不同类型车辆的物理特性（长度、最大速度、PCU等）。<br>
    • 此文件用于网络模式的车辆，与公交车辆文件（transit.vehiclesFile）分开。<br><br>
    <b>使用建议 / Tips</b><br>
    • 车辆文件在「输入文件配置」中上传，此处显示配置状态。<br>
    • 若使用 qsim.vehiclesSource=fromVehiclesData，则需要此文件。<br>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### 📁 车辆文件 / Vehicles File")

    # 显示当前配置状态
    vehicles_file = st.session_state.file_config.get('vehiclesFile', '')

    if vehicles_file:
        st.success(f"✅ 已配置车辆文件: `{vehicles_file}`")
    else:
        st.info("⚪ 未配置车辆文件（可选）")

    st.caption("车辆文件在「输入文件配置」步骤中上传。")

    # 显示相关 QSim 设置
    st.markdown("---")
    st.markdown("#### 🔗 相关 QSim 设置 / Related QSim Settings")

    qsim_cfg = st.session_state.get('qsim_config', {})
    vehicles_source = qsim_cfg.get('vehiclesSource', 'defaultVehicle')

    vehicles_source_info = {
        'defaultVehicle': '使用默认车辆（不需要车辆文件）',
        'modeVehicleTypesFromVehiclesData': '从车辆文件按模式映射车辆类型',
        'fromVehiclesData': '直接从车辆文件读取车辆'
    }

    st.info(f"当前 QSim 车辆来源: **{vehicles_source}**\n\n{vehicles_source_info.get(vehicles_source, '')}")

    if vehicles_source in ['modeVehicleTypesFromVehiclesData', 'fromVehiclesData'] and not vehicles_file:
        st.warning("⚠️ 当前 QSim 设置需要车辆文件，但未配置。请在「输入文件配置」中上传。")


def render_vsp_experimental_configuration():
    """渲染 VspExperimental 模块配置"""

    st.markdown('<div class="module-header">🧪 VSP 实验性配置 / VspExperimental Settings</div>',
                unsafe_allow_html=True)

    vsp = st.session_state.vsp_experimental_config

    st.markdown("""
    <div class="warning-box">
    <b>⚠️ 警告 / Warning</b><br>
    此模块包含 VSP（Transport Systems Planning, TU Berlin）内部使用的实验性参数。<br>
    非 VSP 成员通常不需要修改这些参数，保持默认值即可。<br><br>
    <b>This module contains experimental parameters used internally by VSP. 
    Non-VSP members usually do not need to modify these; keep defaults.</b>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### 🔍 检查级别 / Checking Level")

    checking_options = list(VSP_DEFAULTS_CHECKING_LEVEL_OPTIONS.keys())
    current_level = vsp.get('vspDefaultsCheckingLevel', 'ignore')

    vsp['vspDefaultsCheckingLevel'] = st.selectbox(
        create_param_label("VSP默认值检查级别 / vspDefaultsCheckingLevel",
                           "VSP Defaults Checking Level"),
        options=checking_options,
        index=checking_options.index(current_level) if current_level in checking_options else 0,
        format_func=lambda x: VSP_DEFAULTS_CHECKING_LEVEL_OPTIONS[x][0],
        help=create_help_text(
            "违反VSP默认值时的行为：忽略/记录信息/记录警告/中止仿真。"
            "VSP成员应使用 abort 或与 Kai 讨论。",
            "Behavior when violating VSP defaults: ignore/log info/log warning/abort. "
            "VSP members should use 'abort' or talk to Kai."
        )
    )
    st.caption(VSP_DEFAULTS_CHECKING_LEVEL_OPTIONS[vsp['vspDefaultsCheckingLevel']][1])

    st.markdown("---")
    st.markdown("#### ⚙️ 实验性参数 / Experimental Parameters")

    col1, col2 = st.columns(2)

    with col1:
        vsp['writingOutputEvents'] = st.checkbox(
            create_param_label("写入输出事件 / writingOutputEvents",
                               "Write Output Events"),
            value=bool(vsp.get('writingOutputEvents', True)),
            help=create_help_text(
                "若启用，在输出目录写入 output_events 文件。"
                "仅当 lastIteration 是事件写入间隔的倍数时有效。",
                "If true, writes output_events in output directory. "
                "Only works when lastIteration is multiple of events writing interval."
            )
        )

        vsp['isGeneratingBoardingDeniedEvent'] = st.checkbox(
            create_param_label("生成上车拒绝事件 / isGeneratingBoardingDeniedEvent",
                               "Generate Boarding Denied Events"),
            value=bool(vsp.get('isGeneratingBoardingDeniedEvent', False)),
            help=create_help_text(
                "是否生成上车被拒绝事件（当公交车满载时）。"
                "默认不生成。",
                "Whether to generate boarding denied events (when transit vehicle is full). "
                "Default is not to generate."
            )
        )

        vsp['isAbleToOverwritePtInteractionParams'] = st.checkbox(
            create_param_label("允许覆盖PT交互参数 / isAbleToOverwritePtInteractionParams",
                               "Allow Overwriting PT Interaction Params"),
            value=bool(vsp.get('isAbleToOverwritePtInteractionParams', False)),
            help=create_help_text(
                "（除非必须，否则不要使用）"
                "之前有人通过覆盖 pt interaction 活动类型参数来解决问题。"
                "现在这样做会抛出异常，除非启用此选项。",
                "(Do not use unless you have to) "
                "There was a problem with pt interaction scoring. Some solved it by overwriting params. "
                "Now this throws an exception unless you enable this option."
            )
        )

    with col2:
        vsp['isUsingOpportunityCostOfTimeForLocationChoice'] = st.checkbox(
            create_param_label("位置选择使用时间机会成本 / isUsingOpportunityCostOfTimeForLocationChoice",
                               "Use Opportunity Cost of Time for Location Choice"),
            value=bool(vsp.get('isUsingOpportunityCostOfTimeForLocationChoice', True)),
            help=create_help_text(
                "在位置选择的半径计算中是否包含时间机会成本的近似值。"
                "true 更快但是近似值。默认 true；false 用于向后兼容。",
                "Whether to include an approximation of opportunity cost of time "
                "in the radius calculation for location choice. "
                "'true' is faster but approximate. Default true; false for backward compatibility."
            )
        )

        vsp['logitScaleParamForPlansRemoval'] = st.number_input(
            create_param_label("计划移除Logit规模参数 / logitScaleParamForPlansRemoval",
                               "Logit Scale Param for Plans Removal"),
            min_value=0.1,
            max_value=10.0,
            value=float(vsp.get('logitScaleParamForPlansRemoval', 1.0)),
            step=0.1,
            help=create_help_text(
                "用于计划移除的Logit模型规模参数。",
                "Logit model scale parameter used for plans removal."
            )
        )

    st.session_state.vsp_experimental_config = vsp
# ============================================================
# 统一模式配置面板 / Unified Mode Configuration Panel
# ============================================================

def render_mode_configuration():
    """渲染统一模式配置面板"""

    st.markdown('<div class="module-header">🎛️ 出行模式配置 / Travel Mode Configuration</div>',
                unsafe_allow_html=True)

    # 顶部说明
    with st.expander("📖 模式配置说明（新手必读）", expanded=False):
        st.markdown("""
        ### 🎯 模式类别说明

        | 类别 | 说明 | 示例 | Agent可选? |
        |-----|------|------|-----------|
        | **网络模式** | 在路网上物理模拟 | car, truck | ✅ 可选 |
        | **传送模式** | 直线距离估算时间 | walk, bike | ✅ 可选 |
        | **pt** | 公交统一入口 | pt | ✅ 可选 |
        | **公交子模式** | 时刻表中的具体类型 | bus, subway | ❌ 路由分配 |

        ### ⚠️ 重要规则

        1. **模式名称**：英文小写，无空格（用下划线）
        2. **公交子模式**：从时刻表文件解析，不可自定义名称
        3. **接驳模式**：只能从传送模式中选择
        4. **可选择**：勾选后Agent可主动选择此模式
        5. **链约束**：使用此模式出发必须用同一模式返回
        """)

    # 配置标签页
    tab1, tab2, tab3 = st.tabs([
        "🚗 基本出行模式",
        "🚌 公共交通配置",
        "✅ 配置检查"
    ])

    with tab1:
        render_basic_modes_tab()

    with tab2:
        render_transit_config_tab()

    with tab3:
        render_config_check_tab()


def render_basic_modes_tab():
    """渲染基本出行模式标签页"""

    # ========== 网络模式 ==========
    st.markdown("### 🚗 网络模式 / networkModes")
    st.caption("说明：在路网上物理模拟的模式，将写入 routing.networkModes 和 qsim.mainMode")

    st.markdown("""
    <div class="info-box">
    网络模式的车辆在路网上物理移动，使用路由算法计算路径，受道路容量限制。
    </div>
    """, unsafe_allow_html=True)

    network_modes = st.session_state.get('network_modes', {})

    # 显示已配置的网络模式
    if network_modes:
        # 表头
        cols = st.columns([2, 2, 1.2, 1.2, 1, 0.5])
        cols[0].markdown("**名称 (mode)**")
        cols[1].markdown("**显示名**")
        cols[2].markdown("**链约束 / chainBasedModes**")
        cols[3].markdown("**可选主模式 / modes**")
        cols[4].markdown("**评分**")
        cols[5].markdown("")

        for mode_name, mode_config in list(network_modes.items()):
            cols = st.columns([2, 2, 1, 1, 1, 0.5])

            with cols[0]:
                st.text(mode_name)

            with cols[1]:
                new_display = st.text_input(
                    "显示名",
                    value=mode_config.get('display_name', mode_name),
                    key=f"net_display_{mode_name}",
                    label_visibility="collapsed"
                )
                network_modes[mode_name]['display_name'] = new_display

            with cols[2]:
                is_chain = st.checkbox(
                    "链约束：需往返同一模式",
                    value=mode_config.get('is_chain_based', True),
                    key=f"net_chain_{mode_name}",
                    label_visibility="collapsed"
                )
                network_modes[mode_name]['is_chain_based'] = is_chain

            with cols[3]:
                is_choosable = st.checkbox(
                    "可选主模式：可作为出行全过程主模式",
                    value=mode_config.get('is_choosable', True),
                    key=f"net_choosable_{mode_name}",
                    label_visibility="collapsed"
                )
                network_modes[mode_name]['is_choosable'] = is_choosable

            with cols[4]:
                if st.button("📝", key=f"net_edit_{mode_name}", help="编辑评分参数"):
                    st.session_state['editing_mode'] = ('network', mode_name)
                    st.session_state['open_scoring_mode'] = mode_name
                    st.session_state['open_scoring_type'] = 'network'
                    st.session_state['nav_target'] = 'scoring'
                    st.rerun()

            with cols[5]:
                if st.button("🗑️", key=f"net_del_{mode_name}", help="删除"):
                    del network_modes[mode_name]
                    st.session_state.network_modes = network_modes
                    st.rerun()
    else:
        st.info("暂无网络模式")

    # 添加网络模式
    st.markdown("**➕ 添加网络模式：**")

    cols = st.columns([2, 2, 1, 1, 1])

    with cols[0]:
        new_net_name = st.text_input(
            "名称(英文，mode)",
            key="new_net_name",
            placeholder="如: car"
        )

    with cols[1]:
        new_net_display = st.text_input(
            "显示名",
            key="new_net_display",
            placeholder="如: 小汽车"
        )

    with cols[2]:
        new_net_chain = st.checkbox("链约束（chainBasedModes）", value=True, key="new_net_chain")

    with cols[3]:
        new_net_choosable = st.checkbox("可选主模式（modes）", value=True, key="new_net_choosable")

    with cols[4]:
        if st.button("➕ 添加", key="add_net_btn"):
            if new_net_name:
                name = new_net_name.strip().lower().replace(' ', '_')
                conflict, msg = ModeManager.check_mode_name_conflict(name, 'network')

                if conflict:
                    st.error(f"❌ {msg}")
                elif name in network_modes:
                    st.error(f"❌ '{name}' 已存在")
                else:
                    network_modes[name] = {
                        'display_name': new_net_display or name,
                        'is_chain_based': new_net_chain,
                        'is_choosable': new_net_choosable,
                        'scoring': {
                            'constant': 0.0,
                            'marginalUtilityOfTraveling_util_hr': -6.0,
                            'monetaryDistanceRate': 0.0,
                            'dailyMonetaryConstant': 0.0
                        }
                    }
                    st.session_state.network_modes = network_modes
                    st.success(f"✅ 已添加: {name}")
                    st.rerun()
            else:
                st.error("请输入模式名称")

    # 快速添加
    st.markdown("**快速添加：**")
    quick_net = {'car': '小汽车', 'truck': '货车', 'motorcycle': '摩托车'}
    cols = st.columns(len(quick_net))
    for i, (mode, display) in enumerate(quick_net.items()):
        with cols[i]:
            if mode not in network_modes:
                if st.button(f"+ {mode}", key=f"quick_net_{mode}"):
                    network_modes[mode] = {
                        'display_name': display,
                        'is_chain_based': True,
                        'is_choosable': True,
                        'scoring': {
                            'constant': 0.0,
                            'marginalUtilityOfTraveling_util_hr': -6.0,
                            'monetaryDistanceRate': -0.0002 if mode == 'car' else 0.0,
                            'dailyMonetaryConstant': -5.0 if mode == 'car' else 0.0
                        }
                    }
                    st.session_state.network_modes = network_modes
                    st.rerun()
            else:
                st.caption(f"✓ {mode}")

    # ========== 传送模式 ==========
    st.markdown("---")
    st.markdown("### 🚶 传送模式 / teleportedModeParameters")
    st.caption("说明：不走路网，按直线距离 × 直线系数 ÷ 速度进行“瞬移”，写入 routing.teleportedModeParameters")

    st.markdown("""
    <div class="info-box">
    传送模式使用公式估算：时间 = 直线距离 × 直线系数 ÷ 速度。可用于步行、自行车等，也可作为公交接驳。
    </div>
    """, unsafe_allow_html=True)

    teleported_modes = st.session_state.get('teleported_modes', {})

    if teleported_modes:
        cols = st.columns([1.5, 1.5, 1, 1, 1.2, 1, 1, 0.5])
        cols[0].markdown("**名称 (mode)**")
        cols[1].markdown("**显示名**")
        cols[2].markdown("**速度 km/h (teleportedModeSpeed)**")
        cols[3].markdown("**直线系数 / beelineDistanceFactor**")
        cols[4].markdown("**链约束 / chainBasedModes**")
        cols[5].markdown("**可选主模式 / modes**")
        cols[6].markdown("**评分**")
        cols[7].markdown("")

        for mode_name, mode_config in list(teleported_modes.items()):
            cols = st.columns([1.5, 1.5, 1, 1, 1.2, 1, 1, 0.5])

            with cols[0]:
                st.text(mode_name)

            with cols[1]:
                new_display = st.text_input(
                    "显示",
                    value=mode_config.get('display_name', mode_name),
                    key=f"tele_display_{mode_name}",
                    label_visibility="collapsed"
                )
                teleported_modes[mode_name]['display_name'] = new_display

            with cols[2]:
                new_speed = st.number_input(
                    "km/h",
                    min_value=1.0,
                    max_value=100.0,
                    value=mode_config.get('speed_kmh', 5.0),
                    step=1.0,
                    key=f"tele_speed_{mode_name}",
                    label_visibility="collapsed"
                )
                teleported_modes[mode_name]['speed_kmh'] = new_speed

            with cols[3]:
                new_beeline = st.number_input(
                    "直线系数",
                    min_value=0.5,
                    max_value=5.0,
                    value=mode_config.get('beeline_factor', 1.3),
                    step=0.1,
                    key=f"tele_beeline_{mode_name}",
                    label_visibility="collapsed"
                )
                teleported_modes[mode_name]['beeline_factor'] = new_beeline

            with cols[4]:
                is_chain = st.checkbox(
                    "链约束：需往返同一模式",
                    value=mode_config.get('is_chain_based', False),
                    key=f"tele_chain_{mode_name}",
                    label_visibility="collapsed"
                )
                teleported_modes[mode_name]['is_chain_based'] = is_chain

            with cols[5]:
                is_choosable = st.checkbox(
                    "可选主模式：可作为出行全过程主模式",
                    value=mode_config.get('is_choosable', True),
                    key=f"tele_choosable_{mode_name}",
                    label_visibility="collapsed"
                )
                teleported_modes[mode_name]['is_choosable'] = is_choosable

            with cols[6]:
                if st.button("📝", key=f"tele_edit_{mode_name}"):
                    st.session_state['editing_mode'] = ('teleported', mode_name)
                    st.session_state['open_scoring_mode'] = mode_name
                    st.session_state['open_scoring_type'] = 'teleported'
                    st.session_state['nav_target'] = 'scoring'
                    st.rerun()

            with cols[7]:
                if st.button("🗑️", key=f"tele_del_{mode_name}"):
                    del teleported_modes[mode_name]
                    st.session_state.teleported_modes = teleported_modes
                    # 同步接驳配置
                    ModeManager.sync_access_egress_config()
                    st.rerun()
    else:
        st.info("暂无传送模式")

    # 添加传送模式
    st.markdown("**➕ 添加传送模式：**")

    cols = st.columns([1.5, 1.5, 1, 1, 1, 1, 1])

    with cols[0]:
        new_tele_name = st.text_input("名称", key="new_tele_name", placeholder="如: walk")

    with cols[1]:
        new_tele_display = st.text_input("显示名", key="new_tele_display", placeholder="如: 步行")

    with cols[2]:
        new_tele_speed = st.number_input("km/h", min_value=1.0, value=5.0, key="new_tele_speed")

    with cols[3]:
        new_tele_beeline = st.number_input("直线系数", min_value=0.5, max_value=5.0, value=1.3, step=0.1,
                                           key="new_tele_beeline")

    with cols[4]:
        new_tele_chain = st.checkbox("链约束（chainBasedModes）", value=False, key="new_tele_chain")

    with cols[5]:
        new_tele_choosable = st.checkbox("可选主模式（modes）", value=True, key="new_tele_choosable")

    with cols[6]:
        if st.button("➕ 添加", key="add_tele_btn"):
            if new_tele_name:
                name = new_tele_name.strip().lower().replace(' ', '_')
                conflict, msg = ModeManager.check_mode_name_conflict(name, 'teleported')

                if conflict:
                    st.error(f"❌ {msg}")
                elif name in teleported_modes:
                    st.error(f"❌ '{name}' 已存在")
                else:
                    teleported_modes[name] = {
                        'display_name': new_tele_display or name,
                        'speed_kmh': new_tele_speed,
                        'beeline_factor': new_tele_beeline,
                        'is_chain_based': new_tele_chain,
                        'is_choosable': new_tele_choosable,
                        'scoring': {
                            'constant': 0.0,
                            'marginalUtilityOfTraveling_util_hr': -6.0,
                            'monetaryDistanceRate': 0.0,
                            'dailyMonetaryConstant': 0.0
                        }
                    }
                    st.session_state.teleported_modes = teleported_modes
                    st.success(f"✅ 已添加: {name}")
                    st.rerun()
            else:
                st.error("请输入模式名称")

    # 快速添加
    st.markdown("**快速添加：**")
    quick_tele = {
        'walk': ('步行', 5.0, False),
        'bike': ('自行车', 15.0, True),
        'e-bike': ('电动自行车', 25.0, True),
        'e-scooter': ('电动滑板车', 18.0, False)
    }
    cols = st.columns(len(quick_tele))
    for i, (mode, (display, speed, chain)) in enumerate(quick_tele.items()):
        with cols[i]:
            if mode not in teleported_modes:
                if st.button(f"+ {mode}", key=f"quick_tele_{mode}"):
                    teleported_modes[mode] = {
                        'display_name': display,
                        'speed_kmh': speed,
                        'beeline_factor': 1.3,
                        'is_chain_based': chain,
                        'is_choosable': True,
                        'scoring': {
                            'constant': 0.0 if mode == 'walk' else -1.0,
                            'marginalUtilityOfTraveling_util_hr': -12.0 if mode == 'walk' else -6.0,
                            'monetaryDistanceRate': 0.0,
                            'dailyMonetaryConstant': 0.0
                        }
                    }
                    st.session_state.teleported_modes = teleported_modes
                    st.rerun()
            else:
                st.caption(f"✓ {mode}")


def render_transit_config_tab():
    """渲染公共交通配置标签页"""

    st.markdown("### 🚌 公共交通配置")

    # 主开关
    transit_enabled = st.checkbox(
        "**启用公共交通系统**",
        value=st.session_state.get('transit_enabled', False),
        help="启用后，Agent可以选择乘坐公交出行"
    )
    st.session_state.transit_enabled = transit_enabled

    if not transit_enabled:
        st.markdown("""
        <div class="info-box">
        ℹ️ 公共交通已禁用。如需模拟公交、地铁等，请勾选上方开关。
        </div>
        """, unsafe_allow_html=True)
        return

    st.markdown("""
    <div class="success-box">
    ✅ 公共交通已启用！
    </div>
    """, unsafe_allow_html=True)

    # ========== Step 1: 上传文件 ==========
    st.markdown("---")
    st.markdown("#### 📁 Step 1: 上传公交文件")

    col1, col2 = st.columns(2)

    with col1:
        render_file_upload(
            "公交时刻表", "Transit Schedule",
            'transitScheduleFile',
            required=True,
            help_text="包含线路、站点、发车时刻的XML文件"
        )

    with col2:
        render_file_upload(
            "公交车辆", "Transit Vehicles",
            'transitVehiclesFile',
            required=True,
            help_text="包含车辆类型和容量的XML文件"
        )

    # 调试信息：显示文件上传状态
    uploaded_files = st.session_state.get('uploaded_files', {})
    has_schedule_file = 'transitScheduleFile' in uploaded_files

    # 解析按钮和状态
    st.markdown("---")

    if has_schedule_file:
        file_info = uploaded_files['transitScheduleFile']
        st.info(f"📄 已上传文件: {file_info['name']} ({len(file_info['content'])} 字节)")

        col1, col2 = st.columns([1, 3])
        with col1:
            parse_clicked = st.button("🔍 解析时刻表", type="primary", use_container_width=True)

        if parse_clicked:
            with st.spinner("正在解析..."):
                result = parse_transit_schedule_file()

            # 显示解析结果（不立即刷新，让用户看到结果）
            if result['success']:
                st.success(f"✅ 解析成功！")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("线路", result['stats']['lines'])
                with col2:
                    st.metric("路线", result['stats']['routes'])
                with col3:
                    st.metric("站点", result['stats']['stops'])

                if result['modes']:
                    st.write(f"**发现的交通模式:** `{', '.join(result['modes'])}`")
                else:
                    st.warning("⚠️ 未在时刻表中找到 transportMode，请检查文件格式")

                # 提示用户刷新
                if st.button("🔄 应用解析结果"):
                    st.rerun()
            else:
                st.error(f"❌ 解析失败: {result['error']}")
    else:
        st.warning("⚠️ 请先上传公交时刻表文件（支持 .xml 或 .xml.gz 格式）")

    # ========== Step 2: 公交子模式 ==========
    st.markdown("---")
    st.markdown("#### 📋 Step 2: 公交子模式（从时刻表解析）")

    transit_submodes = st.session_state.get('transit_submodes', {})
    detected = st.session_state.get('transit_submodes_detected', [])

    # 调试信息
    with st.expander("🔧 调试信息", expanded=False):
        st.write(f"detected modes: {detected}")
        st.write(f"transit_submodes: {list(transit_submodes.keys())}")
        st.write(f"uploaded_files keys: {list(uploaded_files.keys())}")

    if not detected:
        st.warning("⚠️ 请先上传并解析时刻表文件，系统将自动识别公交子模式")
    else:
        st.markdown(f"**检测到的 transportMode:** `{', '.join(detected)}`")

        # 显示子模式配置
        for mode_name in detected:
            if mode_name not in transit_submodes:
                transit_submodes[mode_name] = {
                    'display_name': mode_name,
                    'enabled': True,
                    'scoring': {
                        'constant': -1.0,
                        'marginalUtilityOfTraveling_util_hr': -3.0,
                        'monetaryDistanceRate': 0.0,
                        'dailyMonetaryConstant': -2.0
                    }
                }

            config = transit_submodes[mode_name]

            cols = st.columns([0.5, 1.5, 2, 1])

            with cols[0]:
                enabled = st.checkbox(
                    "启用",
                    value=config.get('enabled', True),
                    key=f"transit_enable_{mode_name}",
                    label_visibility="collapsed"
                )
                transit_submodes[mode_name]['enabled'] = enabled

            with cols[1]:
                st.text(mode_name)

            with cols[2]:
                display_name = st.text_input(
                    "显示名称",
                    value=config.get('display_name', mode_name),
                    key=f"transit_display_{mode_name}",
                    label_visibility="collapsed",
                    placeholder=f"如: {mode_name.title()}"
                )
                transit_submodes[mode_name]['display_name'] = display_name

            with cols[3]:
                # 检查冲突
                conflict, msg = ModeManager.check_mode_name_conflict(mode_name, 'transit')
                if conflict:
                    st.error("⚠️ 冲突")
                    st.caption(msg)

        st.session_state.transit_submodes = transit_submodes

        # 评分策略
        st.markdown("---")
        st.markdown("**⭐ 评分策略：**")

        scoring_strategy = st.radio(
            "选择公交评分策略",
            options=['unified', 'separate'],
            format_func=lambda x: "统一评分（所有公交使用pt参数）" if x == 'unified' else "分别评分（每种公交单独配置）",
            horizontal=True,
            index=0 if not st.session_state.get('transit_separate_scoring', False) else 1,
            key="transit_scoring_radio"
        )
        st.session_state.transit_separate_scoring = (scoring_strategy == 'separate')

    # ========== Step 3: 接驳配置 ==========
    st.markdown("---")
    st.markdown("#### 🚶 Step 3: 接驳模式配置")

    st.markdown("""
    <div class="info-box">
    从已配置的<b>传送模式</b>中选择用于公交接驳的模式。每种接驳模式可以设置不同的最大距离。
    </div>
    """, unsafe_allow_html=True)

    teleported_modes = st.session_state.get('teleported_modes', {})
    access_egress_config = st.session_state.get('access_egress_config', {})

    if not teleported_modes:
        st.warning("⚠️ 请先在【基本出行模式】中添加传送模式（如walk、bike）")
    else:
        # 表头
        cols = st.columns([0.5, 1.5, 1.5, 1.5, 1.5])
        cols[0].markdown("**启用**")
        cols[1].markdown("**模式**")
        cols[2].markdown("**最大接驳距离(米)**")
        cols[3].markdown("**初始搜索半径(米)**")
        cols[4].markdown("**速度(km/h)**")

        for mode_name, mode_config in teleported_modes.items():
            # 确保配置存在
            if mode_name not in access_egress_config:
                access_egress_config[mode_name] = {
                    'enabled': mode_name == 'walk',  # 默认只启用walk
                    'max_radius': 1000.0,
                    'initial_search_radius': 500.0
                }

            ae_config = access_egress_config[mode_name]

            cols = st.columns([0.5, 1.5, 1.5, 1.5, 1.5])

            with cols[0]:
                enabled = st.checkbox(
                    "启用",
                    value=ae_config.get('enabled', False),
                    key=f"ae_enable_{mode_name}",
                    label_visibility="collapsed"
                )
                access_egress_config[mode_name]['enabled'] = enabled

            with cols[1]:
                st.text(f"{mode_name}")
                st.caption(mode_config.get('display_name', ''))

            with cols[2]:
                if enabled:
                    max_r = st.number_input(
                        "最大距离",
                        min_value=100.0,
                        max_value=10000000.0,
                        value=float(ae_config.get('max_radius', 1000.0)),
                        step=100.0,
                        key=f"ae_max_{mode_name}",
                        label_visibility="collapsed"
                    )
                    access_egress_config[mode_name]['max_radius'] = max_r
                else:
                    st.caption("-")

            with cols[3]:
                if enabled:
                    init_r = st.number_input(
                        "初始半径",
                        min_value=50.0,
                        max_value=10000.0,
                        value=float(ae_config.get('initial_search_radius', 500.0)),
                        step=50.0,
                        key=f"ae_init_{mode_name}",
                        label_visibility="collapsed"
                    )
                    access_egress_config[mode_name]['initial_search_radius'] = init_r
                else:
                    st.caption("-")

            with cols[4]:
                st.caption(f"{mode_config.get('speed_kmh', 5.0)} km/h")

        st.session_state.access_egress_config = access_egress_config

        # 提示
        enabled_ae = [m for m, c in access_egress_config.items() if c.get('enabled', False)]
        if not enabled_ae:
            st.warning("⚠️ 请至少启用一种接驳模式（建议启用walk）")
        else:
            st.caption(f"✅ 已启用的接驳模式: {', '.join(enabled_ae)}")

    # ========== 扩展搜索半径 ==========
    st.markdown("---")
    st.markdown("#### 📊 其他参数")

    st.session_state.transit_extension_radius = st.number_input(
        "扩展搜索半径 (米)",
        min_value=50.0,
        max_value=2000.0,
        value=float(st.session_state.get('transit_extension_radius', 200.0)),
        step=50.0,
        help="当初始搜索找不到路线时，扩大搜索的半径"
    )


def render_config_check_tab():
    """渲染配置检查标签页"""

    st.markdown("### ✅ 配置检查")

    errors, warnings = validate_full_configuration()

    # 显示错误和警告
    if errors:
        st.markdown('<div class="error-box"><b>❌ 错误：</b></div>', unsafe_allow_html=True)
        for error in errors:
            st.error(error)

    if warnings:
        st.markdown('<div class="warning-box"><b>⚠️ 警告：</b></div>', unsafe_allow_html=True)
        for warning in warnings:
            st.warning(warning)

    if not errors and not warnings:
        st.markdown("""
        <div class="success-box">
        ✅ 配置检查通过！
        </div>
        """, unsafe_allow_html=True)

    # 配置摘要
    st.markdown("---")
    st.markdown("#### 📋 配置摘要")

    network_modes = list(st.session_state.get('network_modes', {}).keys())
    teleported_modes = list(st.session_state.get('teleported_modes', {}).keys())
    transit_submodes = list(st.session_state.get('transit_submodes', {}).keys())
    choosable_modes = ModeManager.get_choosable_modes()
    chain_modes = ModeManager.get_chain_based_modes()
    enabled_ae = ModeManager.get_enabled_access_egress_modes()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**routing 模块：**")
        st.code(f"networkModes = {', '.join(network_modes) if network_modes else '(无)'}")

        st.markdown("**qsim 模块：**")
        st.code(f"mainMode = {', '.join(network_modes) if network_modes else '(无)'}")

        st.markdown("**teleportedModeParameters：**")
        for mode in teleported_modes:
            speed = st.session_state.teleported_modes[mode].get('speed_kmh', 5.0)
            st.code(f"{mode}: {speed} km/h")

    with col2:
        st.markdown("**subtourModeChoice：**")
        st.code(f"modes = {', '.join(choosable_modes) if choosable_modes else '(无)'}")
        st.code(f"chainBasedModes = {', '.join(chain_modes) if chain_modes else '(无)'}")

        if st.session_state.get('transit_enabled', False):
            st.markdown("**transit 模块：**")
            st.code("transitModes = pt")
            st.code(f"子模式: {', '.join(transit_submodes) if transit_submodes else '(未配置)'}")

            st.markdown("**swissRailRaptor.intermodalAccessEgress：**")
            for mode in enabled_ae:
                ae_config = st.session_state.access_egress_config.get(mode, {})
                max_r = ae_config.get('max_radius', 1000)
                st.code(f"{mode}: maxRadius={max_r}m")

    # 评分模式列表
    st.markdown("---")
    st.markdown("**需要评分参数的模式：**")

    scoring_modes = []
    scoring_modes.extend(network_modes)
    scoring_modes.extend(teleported_modes)
    if st.session_state.get('transit_enabled', False):
        scoring_modes.append('pt')
        if st.session_state.get('transit_separate_scoring', False):
            scoring_modes.extend(transit_submodes)

    st.code(', '.join(scoring_modes) if scoring_modes else '(无)')




# ============================================================
# 评分参数配置 / Scoring Parameters Configuration
# ============================================================
def render_mode_scoring_editor(mode_name: str, scoring: dict, mode_type: str):
    """渲染单个模式的评分参数编辑器"""

    col1, col2 = st.columns(2)

    with col1:
        scoring['constant'] = st.number_input(
            "常数 / Constant",
            value=float(scoring.get('constant', 0.0)),
            step=0.5,
            key=f"score_const_{mode_type}_{mode_name}",
            help="模式固有效用"
        )

        scoring['marginalUtilityOfTraveling_util_hr'] = st.number_input(
            "时间效用 (utils/hr)",
            value=float(scoring.get('marginalUtilityOfTraveling_util_hr', -6.0)),
            step=0.5,
            key=f"score_time_{mode_type}_{mode_name}",
            help="出行时间的边际效用（通常为负）"
        )

    with col2:
        scoring['monetaryDistanceRate'] = st.number_input(
            "距离费率 (货币/m)",
            value=float(scoring.get('monetaryDistanceRate', 0.0)),
            step=0.0001,
            format="%.4f",
            key=f"score_dist_{mode_type}_{mode_name}",
            help="每米的货币成本（如油费）"
        )

        scoring['dailyMonetaryConstant'] = st.number_input(
            "日固定成本",
            value=float(scoring.get('dailyMonetaryConstant', 0.0)),
            step=0.5,
            key=f"score_daily_{mode_type}_{mode_name}",
            help="每日使用该模式的固定成本（如停车费）"
        )


def render_scoring_configuration():
    """渲染完整的 Scoring 模块配置（ScoringConfigGroup）"""

    st.markdown('<div class="module-header">⭐ 效用评分配置 / Scoring Configuration</div>',
                unsafe_allow_html=True)

    with st.expander("📖 评分模块完整说明", expanded=False):
        st.markdown("""
        ### 评分模块层次结构

        ```
        scoring (模块)
        ├── 顶层参数 (learningRate, brainExpBeta, ...)
        └── scoringParameters (子参数集，按子人口分组)
            ├── 全局效用参数 (performing, lateArrival, ...)
            ├── activityParams (活动参数，嵌套)
            │   └── 每种活动类型的参数
            └── modeParams (模式参数，嵌套)
                └── 每种模式的参数
        ```

        ### 效用函数简介

        MATSim 使用效用函数评估每个 Agent 的计划。Agent 会学习选择效用更高的计划。

        **关键公式：**
        ```
        V_plan = Σ V_activity + Σ V_leg
        V_activity = performing × duration + lateArrival × late_time + ...
        V_leg = constant + marginalUtilityOfTraveling × time + ...
        ```
        """)

    # ===== Tab 布局 =====
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎯 顶层参数",
        "📊 全局效用参数",
        "📍 活动参数",
        "🚗 模式参数"
    ])

    # ===== Tab 1: 顶层参数 =====
    with tab1:
        render_scoring_toplevel_params()

    # ===== Tab 2: 全局效用参数 =====
    with tab2:
        render_scoring_global_params()

    # ===== Tab 3: 活动参数 =====
    with tab3:
        render_scoring_activity_params()

    # ===== Tab 4: 模式参数 =====
    with tab4:
        render_scoring_mode_params()


def render_subtour_mode_choice_configuration():
    """渲染 SubtourModeChoice 模块完整配置"""

    st.markdown('<div class="module-header">🔄 子路程模式选择配置 / SubtourModeChoice Settings</div>',
                unsafe_allow_html=True)

    smc = st.session_state.subtour_mode_choice_config

    st.markdown("""
    <div class="info-box">
    <b>模块说明 / Description</b><br>
    • 控制 Agent 在重规划时如何改变子路程（subtour）的出行模式。<br>
    • 子路程是从某个活动出发并最终返回该活动的一系列行程。<br>
    • 链约束模式（如 car, bike）要求出发和返回使用同一模式（因为车在原地）。<br><br>
    <b>使用建议 / Tips</b><br>
    • modes 和 chainBasedModes 会自动从「出行模式配置」同步。<br>
    • 若需要禁用某些模式的选择，可在此处手动调整。<br>
    </div>
    """, unsafe_allow_html=True)

    # ===== 1. 模式列表 (显示自动同步状态) =====
    st.markdown("#### 🚗 模式列表 / Mode Lists")

    choosable_modes = ModeManager.get_choosable_modes()
    chain_modes = ModeManager.get_chain_based_modes()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**可选模式 / modes**")
        if choosable_modes:
            st.success(f"`{', '.join(choosable_modes)}`")
        else:
            st.warning("无可选模式")
        st.caption("自动从「出行模式配置」中标记为可选主模式的模式同步")

        # 允许手动覆盖
        override_modes = st.checkbox("手动覆盖 modes", value=False, key="smc_override_modes")
        if override_modes:
            custom_modes_str = st.text_input(
                "自定义 modes（逗号分隔）",
                value=','.join(smc.get('modes', choosable_modes)),
                key="smc_custom_modes"
            )
            smc['modes'] = [m.strip() for m in custom_modes_str.split(',') if m.strip()]
            smc['modes_override'] = True
        else:
            smc['modes'] = choosable_modes
            smc['modes_override'] = False

    with col2:
        st.markdown("**链约束模式 / chainBasedModes**")
        if chain_modes:
            st.success(f"`{', '.join(chain_modes)}`")
        else:
            st.info("无链约束模式")
        st.caption("自动从「出行模式配置」中标记为链约束的模式同步")

        # 允许手动覆盖
        override_chain = st.checkbox("手动覆盖 chainBasedModes", value=False, key="smc_override_chain")
        if override_chain:
            custom_chain_str = st.text_input(
                "自定义 chainBasedModes（逗号分隔）",
                value=','.join(smc.get('chainBasedModes', chain_modes)),
                key="smc_custom_chain"
            )
            smc['chainBasedModes'] = [m.strip() for m in custom_chain_str.split(',') if m.strip()]
            smc['chainBasedModes_override'] = True
        else:
            smc['chainBasedModes'] = chain_modes
            smc['chainBasedModes_override'] = False

    # ===== 2. 行为参数 =====
    st.markdown("---")
    st.markdown("#### ⚙️ 行为参数 / Behavior Parameters")

    col1, col2 = st.columns(2)

    with col1:
        smc['considerCarAvailability'] = st.checkbox(
            create_param_label("考虑小汽车可用性 / considerCarAvailability",
                               "Consider Car Availability"),
            value=bool(smc.get('considerCarAvailability', False)),
            help=create_help_text(
                "若勾选，仅当Agent有驾照且有车时才能选择car模式。"
                "Agent没有车的条件是：没有驾照 或 从不使用小汽车。",
                "If checked, car mode is only available if the agent has a license and car access. "
                "An agent has no car only if they have no license or never have car access."
            )
        )

        current_behavior = smc.get('behavior', 'fromSpecifiedModesToSpecifiedModes')
        behavior_options = list(SUBTOUR_MODE_BEHAVIOR_OPTIONS.keys())

        smc['behavior'] = st.selectbox(
            create_param_label("模式切换行为 / behavior",
                               "Mode Switch Behavior"),
            options=behavior_options,
            index=behavior_options.index(current_behavior) if current_behavior in behavior_options else 0,
            format_func=lambda x: SUBTOUR_MODE_BEHAVIOR_OPTIONS[x][0],
            help=create_help_text(
                "fromSpecifiedModesToSpecifiedModes: 仅当当前模式在modes中才切换，目标也在modes中。"
                "fromAllModesToSpecifiedModes: 任何当前模式都可切换到modes中的模式。",
                SUBTOUR_MODE_BEHAVIOR_OPTIONS[current_behavior][1]
            )
        )

    with col2:
        smc['probaForRandomSingleTripMode'] = st.number_input(
            create_param_label("随机单程模式概率 / probaForRandomSingleTripMode",
                               "Probability for Random Single Trip Mode"),
            min_value=0.0,
            max_value=1.0,
            value=float(smc.get('probaForRandomSingleTripMode', 0.0)),
            step=0.05,
            help=create_help_text(
                "改变单个行程为非链模式（而不是整个子路程）的概率。"
                "0 = 总是改变整个子路程。向后兼容设置，通常保持 0。",
                "Probability of changing a single trip to an unchained mode instead of the whole subtour. "
                "0 = always change whole subtour. For backward compatibility, usually keep at 0."
            )
        )

        smc['coordDistance'] = st.number_input(
            create_param_label("坐标距离阈值 / coordDistance (m)",
                               "Coordinate Distance Threshold"),
            min_value=0.0,
            value=float(smc.get('coordDistance', 0.0)),
            step=100.0,
            help=create_help_text(
                "若大于0，距离小于此值的活动将被视为同一子路程的一部分。"
                "即两个接近的活动可以使用同一链约束车辆服务两个子路程。",
                "If > 0, activities closer than this distance are considered part of the same subtour. "
                "Allows chain-based vehicles to serve two subtours if activities are close."
            )
        )

    st.session_state.subtour_mode_choice_config = smc

def render_scoring_toplevel_params():
    """渲染 Scoring 顶层参数"""

    st.markdown("### 🎯 顶层参数 / Top-level Parameters")

    scoring_cfg = st.session_state.scoring_config

    col1, col2 = st.columns(2)

    with col1:
        scoring_cfg['learningRate'] = st.number_input(
            create_param_label("学习率 / learningRate",
                               "Learning Rate (config.scoring.learningRate)"),
            min_value=0.0,
            max_value=1.0,
            value=float(scoring_cfg.get('learningRate', 1.0)),
            step=0.1,
            help=create_help_text(
                "new_score = (1-learningRate) × old_score + learningRate × score_from_mobsim。"
                "接近0的值模拟评分平均，但减慢初始收敛。推荐值：1.0。",
                "new_score = (1-learningRate) × old_score + learningRate × score_from_mobsim. "
                "Values close to 0 emulate score averaging but slow initial convergence. Recommended: 1.0."
            )
        )

        scoring_cfg['brainExpBeta'] = st.number_input(
            create_param_label("选择敏感度 / brainExpBeta",
                               "Brain Exp Beta (config.scoring.brainExpBeta)"),
            min_value=0.1,
            max_value=10.0,
            value=float(scoring_cfg.get('brainExpBeta', 1.0)),
            step=0.5,
            help=create_help_text(
                "Logit模型的规模参数。较大值使Agent更倾向选择高分计划。"
                "历史原因默认为1.0。",
                "Logit model scale parameter. Higher values make agents prefer higher-scoring plans more strongly. "
                "Default 1.0 for historical reasons."
            )
        )

        scoring_cfg['pathSizeLogitBeta'] = st.number_input(
            create_param_label("路径大小Logit参数 / pathSizeLogitBeta",
                               "Path Size Logit Beta (config.scoring.pathSizeLogitBeta)"),
            min_value=0.0,
            max_value=5.0,
            value=float(scoring_cfg.get('pathSizeLogitBeta', 1.0)),
            step=0.5,
            help=create_help_text(
                "路径大小Logit模型参数。设置非零值为实验性功能。",
                "Path size logit parameter. Setting non-zero is experimental."
            )
        )

    with col2:
        scoring_cfg['writeExperiencedPlans'] = st.checkbox(
            create_param_label("写出体验计划 / writeExperiencedPlans",
                               "Write Experienced Plans"),
            value=bool(scoring_cfg.get('writeExperiencedPlans', False)),
            help=create_help_text(
                "每轮迭代写出每个Agent实际执行的计划及获得的评分。",
                "Write each agent's actually executed plan and received score per iteration."
            )
        )

        scoring_cfg['writeScoreExplanations'] = st.checkbox(
            create_param_label("写出评分解释 / writeScoreExplanations",
                               "Write Score Explanations"),
            value=bool(scoring_cfg.get('writeScoreExplanations', False)),
            help=create_help_text(
                "在计划属性中写出详细的评分组成。用于调试评分问题。",
                "Write detailed score composition into plan attributes. Useful for debugging scoring issues."
            )
        )

        scoring_cfg['usingOldScoringBelowZeroUtilityDuration'] = st.checkbox(
            create_param_label("使用旧版零效用评分 / usingOldScoringBelowZeroUtilityDuration",
                               "Use old scoring below zero utility duration"),
            value=bool(scoring_cfg.get('usingOldScoringBelowZeroUtilityDuration', False)),
            help=create_help_text(
                "仅用于向后兼容旧结果。通常保持关闭。",
                "Only for backward compatibility with old results. Usually keep disabled."
            )
        )

        # MSA 评分开始比例
        # ✅ 先安全获取当前值
        current_msa_value = scoring_cfg.get('fractionOfIterationsToStartScoreMSA')

        msa_enabled = st.checkbox(
            "启用 MSA 评分",
            value=current_msa_value is not None,
            key="enable_msa_scoring",  # ✅ 添加唯一 key
            help="启用后，在指定比例的迭代后开始使用 MSA 评分平均"
        )

        if msa_enabled:
            # ✅ 安全处理 None 值
            default_msa_value = current_msa_value if current_msa_value is not None else 0.8

            scoring_cfg['fractionOfIterationsToStartScoreMSA'] = st.number_input(
                create_param_label("MSA评分开始比例 / fractionOfIterationsToStartScoreMSA",
                                   "Fraction to start MSA scoring"),
                min_value=0.0,
                max_value=1.0,
                value=float(default_msa_value),  # ✅ 现在一定不是 None
                step=0.05,
                key="msa_fraction_input",  # ✅ 添加唯一 key
                help=create_help_text(
                    "在此比例迭代后开始MSA评分平均。例如 0.8 表示在最后 20% 迭代中使用 MSA。",
                    "Start MSA score averaging after this fraction of iterations. "
                    "E.g., 0.8 means start MSA in the last 20% of iterations."
                )
            )

            # ✅ 添加友好的计算提示
            last_iter = st.session_state.controller_config.get('lastIteration', 100)
            msa_start_iter = int(last_iter * scoring_cfg['fractionOfIterationsToStartScoreMSA'])
            st.caption(f"ℹ️ MSA 评分将从第 {msa_start_iter} 轮开始（共 {last_iter} 轮）")
        else:
            scoring_cfg['fractionOfIterationsToStartScoreMSA'] = None

    st.session_state.scoring_config = scoring_cfg


def render_scoring_global_params():
    """渲染 Scoring 全局效用参数（ScoringParameterSet）"""

    st.markdown("### 📊 全局效用参数 / Global Utility Parameters")

    # 获取默认子人口的参数
    scoring_params = st.session_state.scoring_parameters.get(None, {})

    st.markdown("""
    <div class="info-box">
    这些参数对默认子人口的所有Agent生效。如需按子人口差异化配置，请使用高级配置。
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**活动执行效用**")

        scoring_params['performing'] = st.number_input(
            create_param_label("执行活动 / performing (utils/hr)",
                               "Performing utility"),
            value=float(scoring_params.get('performing', 6.0)),
            step=0.5,
            help=create_help_text(
                "执行活动的边际效用。通常为正值。也是时间的机会成本。"
                "MATSim将时间资源价值与出行时间的直接效用分开。",
                "Marginal utility of performing an activity. Usually positive. "
                "Also the opportunity cost of time. MATSim separates time resource value from travel time disutility."
            )
        )

        scoring_params['waiting'] = st.number_input(
            create_param_label("等待 / waiting (utils/hr)",
                               "Waiting utility"),
            value=float(scoring_params.get('waiting', 0.0)),
            step=0.5,
            help=create_help_text(
                "等待的额外边际效用（在时间机会成本之上）。通常为负或零。",
                "Additional marginal utility for waiting (on top of opportunity cost of time). Usually negative or zero."
            )
        )

    with col2:
        st.markdown("**时间惩罚**")

        scoring_params['lateArrival'] = st.number_input(
            create_param_label("迟到惩罚 / lateArrival (utils/hr)",
                               "Late arrival penalty"),
            value=float(scoring_params.get('lateArrival', -18.0)),
            step=1.0,
            help=create_help_text(
                "迟到的效用惩罚（在最晚开始时间之后到达）。通常为负值。",
                "Utility penalty for arriving late (after latest start time). Usually negative."
            )
        )

        scoring_params['earlyDeparture'] = st.number_input(
            create_param_label("早退惩罚 / earlyDeparture (utils/hr)",
                               "Early departure penalty"),
            value=float(scoring_params.get('earlyDeparture', 0.0)),
            step=1.0,
            help=create_help_text(
                "早退的效用惩罚（在最早结束时间之前离开）。通常为负值。",
                "Utility penalty for departing early (before earliest end time). Usually negative."
            )
        )

    with col3:
        st.markdown("**金钱与公交**")

        scoring_params['marginalUtilityOfMoney'] = st.number_input(
            create_param_label("金钱边际效用 / marginalUtilityOfMoney",
                               "Marginal utility of money"),
            value=float(scoring_params.get('marginalUtilityOfMoney', 1.0)),
            step=0.1,
            help=create_help_text(
                "金钱到效用的转换系数。通常为正值（收费/成本作为负金额处理）。",
                "Conversion of money to utility. Usually positive (tolls/costs are negative money amounts)."
            )
        )

        scoring_params['utilityOfLineSwitch'] = st.number_input(
            create_param_label("换乘效用 / utilityOfLineSwitch",
                               "Utility of line switch"),
            value=float(scoring_params.get('utilityOfLineSwitch', -1.0)),
            step=0.5,
            help=create_help_text(
                "换乘的效用（换乘惩罚）。通常为负值。",
                "Utility of switching transit lines (transfer penalty). Usually negative."
            )
        )

        # ===== 修复：waitingPt 复选框和输入框 =====
        # 检查当前值是否为 None
        current_waiting_pt = scoring_params.get('waitingPt')
        use_custom_waiting_pt = st.checkbox(
            "自定义公交等待效用",
            value=current_waiting_pt is not None,
            key="use_custom_waiting_pt",
            help="若不勾选，将使用 pt 模式的 marginalUtilityOfTraveling"
        )

        if use_custom_waiting_pt:
            # 如果勾选，显示输入框
            # 如果之前是 None，使用默认值 -2.0
            default_value = current_waiting_pt if current_waiting_pt is not None else -2.0

            scoring_params['waitingPt'] = st.number_input(
                create_param_label("公交等待 / waitingPt (utils/hr)",
                                   "PT waiting utility"),
                value=float(default_value),
                step=0.5,
                key="waiting_pt_input",
                help="等待公交的额外边际效用（在时间机会成本之上）"
            )
        else:
            # 如果不勾选，设置为 None
            scoring_params['waitingPt'] = None

    st.session_state.scoring_parameters[None] = scoring_params


def render_scoring_activity_params():
    """渲染 Scoring 活动参数（ActivityParams）"""

    st.markdown("### 📍 活动参数 / Activity Parameters")

    st.markdown("""
    <div class="info-box">
    每种活动类型需要单独配置评分参数。这些参数已从「活动类型配置」同步，此处可进行高级调整。
    </div>
    """, unsafe_allow_html=True)

    activity_params = st.session_state.get('activity_params', {})

    if not activity_params:
        st.warning("⚠️ 尚未配置活动类型。请先在「活动类型配置」中添加。")
        return

    for act_type, params in activity_params.items():
        with st.expander(f"📍 **{act_type}**", expanded=False):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**时间参数**")

                params['typicalDuration'] = st.text_input(
                    "典型持续时间 / typicalDuration",
                    value=params.get('typicalDuration', '01:00:00'),
                    key=f"act_typical_{act_type}",
                    help="典型持续时间，用于计算效用。格式: HH:MM:SS"
                )

                params['minimalDuration'] = st.text_input(
                    "最小持续时间 / minimalDuration",
                    value=params.get('minimalDuration', ''),
                    key=f"act_minimal_{act_type}",
                    help="最小持续时间（可选）"
                )

                params['openingTime'] = st.text_input(
                    "开门时间 / openingTime",
                    value=params.get('openingTime', ''),
                    key=f"act_opening_{act_type}",
                    help="设施开门时间（可选）"
                )

                params['closingTime'] = st.text_input(
                    "关门时间 / closingTime",
                    value=params.get('closingTime', ''),
                    key=f"act_closing_{act_type}",
                    help="设施关门时间（可选）"
                )

            with col2:
                st.markdown("**高级时间参数**")

                params['latestStartTime'] = st.text_input(
                    "最晚开始时间 / latestStartTime",
                    value=params.get('latestStartTime', ''),
                    key=f"act_latest_{act_type}",
                    help="活动最晚开始时间（可选）。晚于此时间开始将受迟到惩罚。"
                )

                params['earliestEndTime'] = st.text_input(
                    "最早结束时间 / earliestEndTime",
                    value=params.get('earliestEndTime', ''),
                    key=f"act_earliest_{act_type}",
                    help="活动最早结束时间（可选）。早于此时间离开将受早退惩罚。"
                )

                params['priority'] = st.number_input(
                    "优先级 / priority",
                    min_value=0.0,
                    value=float(params.get('priority', 1.0)),
                    step=0.1,
                    key=f"act_priority_{act_type}",
                    help="活动优先级。默认为1.0。"
                )

            st.markdown("**评分控制**")
            col1, col2 = st.columns(2)

            with col1:
                # pt interaction 强制禁止评分
                if act_type == 'pt interaction':
                    params['scoringThisActivityAtAll'] = False
                    st.checkbox(
                        "对此活动评分 / scoringThisActivityAtAll",
                        value=False,
                        key=f"act_scoring_{act_type}",
                        disabled=True,
                        help="⚠️ pt interaction 活动禁止评分，否则会破坏公交评分系统。"
                    )
                    st.caption("🔒 此活动类型禁止评分")
                else:
                    params['scoringThisActivityAtAll'] = st.checkbox(
                        "对此活动评分 / scoringThisActivityAtAll",
                        value=params.get('scoringThisActivityAtAll', True),
                        key=f"act_scoring_{act_type}",
                        help="是否对此活动进行评分。"
                    )

            with col2:
                computation_options = list(SCORING_TYPICAL_DURATION_COMPUTATION_OPTIONS.keys())
                current_computation = params.get('typicalDurationScoreComputation', 'relative')

                params['typicalDurationScoreComputation'] = st.selectbox(
                    "评分计算方式 / typicalDurationScoreComputation",
                    options=computation_options,
                    index=computation_options.index(current_computation),
                    format_func=lambda x: SCORING_TYPICAL_DURATION_COMPUTATION_OPTIONS[x][0],
                    key=f"act_computation_{act_type}",
                    help=SCORING_TYPICAL_DURATION_COMPUTATION_OPTIONS[current_computation][1]
                )

    st.session_state.activity_params = activity_params


def render_scoring_mode_params():
    """渲染 Scoring 模式参数（ModeParams）"""

    st.markdown("### 🚗 模式参数 / Mode Parameters")

    st.markdown("""
    <div class="info-box">
    每种出行模式需要配置评分参数。参数从「出行模式配置」同步，此处可进行详细调整。
    </div>
    """, unsafe_allow_html=True)

    # 收集所有需要评分的模式
    network_modes = st.session_state.get('network_modes', {})
    teleported_modes = st.session_state.get('teleported_modes', {})
    transit_enabled = st.session_state.get('transit_enabled', False)
    transit_submodes = st.session_state.get('transit_submodes', {})

    # ===== 网络模式 =====
    if network_modes:
        st.markdown("#### 🚗 网络模式")
        for mode_name, mode_config in network_modes.items():
            render_single_mode_params(mode_name, mode_config, 'network')

    # ===== 传送模式 =====
    if teleported_modes:
        st.markdown("#### 🚶 传送模式")
        for mode_name, mode_config in teleported_modes.items():
            render_single_mode_params(mode_name, mode_config, 'teleported')

    # ===== 公交模式 =====
    if transit_enabled:
        st.markdown("#### 🚌 公交模式")

        # PT 统一评分
        pt_scoring = st.session_state.get('pt_scoring', {})
        with st.expander("📊 **pt** (公共交通统一入口)", expanded=True):
            render_mode_params_form('pt', pt_scoring, 'pt')
        st.session_state.pt_scoring = pt_scoring

        # 公交子模式
        if st.session_state.get('transit_separate_scoring', False):
            st.markdown("**公交子模式（分别评分）：**")
            for mode_name, mode_config in transit_submodes.items():
                if mode_config.get('enabled', True):
                    render_single_mode_params(mode_name, mode_config, 'transit_sub')


def render_single_mode_params(mode_name: str, mode_config: dict, mode_type: str):
    """渲染单个模式的评分参数"""

    if 'scoring' not in mode_config:
        mode_config['scoring'] = {
            'constant': 0.0,
            'marginalUtilityOfTraveling_util_hr': -6.0,
            'marginalUtilityOfDistance_util_m': 0.0,
            'monetaryDistanceRate': 0.0,
            'dailyMonetaryConstant': 0.0,
            'dailyUtilityConstant': 0.0,
        }

    display_name = mode_config.get('display_name', mode_name)

    with st.expander(f"📊 **{display_name}** ({mode_name})", expanded=False):
        render_mode_params_form(mode_name, mode_config['scoring'], mode_type)


def render_mode_params_form(mode_name: str, scoring: dict, mode_type: str):
    """渲染模式参数表单"""

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**固定效用**")

        scoring['constant'] = st.number_input(
            "常数 / constant",
            value=float(scoring.get('constant', 0.0)),
            step=0.5,
            key=f"mode_const_{mode_type}_{mode_name}",
            help="模式固有效用。正值表示偏好，负值表示不偏好。"
        )

        scoring['dailyUtilityConstant'] = st.number_input(
            "日固定效用 / dailyUtilityConstant",
            value=float(scoring.get('dailyUtilityConstant', 0.0)),
            step=0.5,
            key=f"mode_daily_util_{mode_type}_{mode_name}",
            help="每日使用该模式的固定效用（与金钱无关）"
        )

    with col2:
        st.markdown("**边际效用**")

        scoring['marginalUtilityOfTraveling_util_hr'] = st.number_input(
            "时间效用 / marginalUtilityOfTraveling (utils/hr)",
            value=float(scoring.get('marginalUtilityOfTraveling_util_hr', -6.0)),
            step=0.5,
            key=f"mode_travel_{mode_type}_{mode_name}",
            help="出行时间的额外边际效用（在时间机会成本之上）。通常为负值。"
        )

        scoring['marginalUtilityOfDistance_util_m'] = st.number_input(
            "距离效用 / marginalUtilityOfDistance (utils/m)",
            value=float(scoring.get('marginalUtilityOfDistance_util_m', 0.0)),
            step=0.0001,
            format="%.4f",
            key=f"mode_dist_util_{mode_type}_{mode_name}",
            help="每米出行的效用（在时间效用之上）。通常为负或零。"
        )

    with col3:
        st.markdown("**货币成本**")

        scoring['monetaryDistanceRate'] = st.number_input(
            "距离费率 / monetaryDistanceRate (货币/m)",
            value=float(scoring.get('monetaryDistanceRate', 0.0)),
            step=0.0001,
            format="%.4f",
            key=f"mode_money_dist_{mode_type}_{mode_name}",
            help="每米的货币成本（如油费、公交费）。通常为负值。"
        )

        scoring['dailyMonetaryConstant'] = st.number_input(
            "日固定成本 / dailyMonetaryConstant",
            value=float(scoring.get('dailyMonetaryConstant', 0.0)),
            step=0.5,
            key=f"mode_daily_money_{mode_type}_{mode_name}",
            help="每日使用该模式的固定货币成本（如停车费）。"
        )




def render_mode_scoring_params(modes: List[str]):
    """渲染一组模式的评分参数"""

    for mode in modes:
        if mode not in st.session_state.scoring_params:
            continue

        params = st.session_state.scoring_params[mode]
        preset = PRESET_MODES.get(mode)
        display_name = f"{preset.display_name_cn}/{preset.display_name_en}" if preset else mode

        with st.expander(f"📊 {display_name} ({mode})", expanded=False):
            col1, col2 = st.columns(2)

            with col1:
                params['constant'] = st.number_input(
                    "常数 / Constant",
                    value=params.get('constant', 0.0),
                    step=0.5,
                    key=f"score_const_{mode}",
                    help="模式固有效用"
                )

                params['marginalUtilityOfTraveling_util_hr'] = st.number_input(
                    "时间效用 (utils/hr)",
                    value=params.get('marginalUtilityOfTraveling_util_hr', -6.0),
                    step=0.5,
                    key=f"score_time_{mode}",
                    help="出行时间的边际效用"
                )

            with col2:
                params['monetaryDistanceRate'] = st.number_input(
                    "距离费率 (货币/m)",
                    value=params.get('monetaryDistanceRate', 0.0),
                    step=0.0001,
                    format="%.4f",
                    key=f"score_dist_{mode}",
                    help="每米的货币成本"
                )

                params['dailyMonetaryConstant'] = st.number_input(
                    "日固定成本",
                    value=params.get('dailyMonetaryConstant', 0.0),
                    step=0.5,
                    key=f"score_daily_{mode}",
                    help="每日使用该模式的固定成本"
                )


# ============================================================
# 活动参数配置 / Activity Parameters Configuration
# ============================================================

def render_activity_configuration():
    """渲染活动参数配置"""

    st.markdown('<div class="module-header">📍 活动类型配置 / Activity Configuration</div>',
                unsafe_allow_html=True)

    with st.expander("📖 活动参数说明", expanded=False):
        st.markdown("""
        **活动类型**定义了Agent在各个地点进行的活动及其时间特征。

        | 参数 | 说明 |
        |-----|------|
        | **时间参数** | |
        | typicalDuration | 典型持续时间，用于计算效用 |
        | minimalDuration | 最小持续时间（可选） |
        | openingTime | 设施开门时间（可选） |
        | closingTime | 设施关门时间（可选） |
        | **效用参数** | |
        | performing | 执行此活动的边际效用（utils/hr） |
        | lateArrival | 迟到惩罚（utils/hr，负值） |
        | earlyDeparture | 早退惩罚（utils/hr，负值） |
        """)

    # ========== Step 1: 从 plans 文件解析 ==========
    st.markdown("#### 📁 Step 1: 从 Plans 文件提取活动类型")

    plans_file_uploaded = 'plansFile' in st.session_state.uploaded_files
    detected_activities = st.session_state.get('detected_activity_types', [])

    if plans_file_uploaded:
        file_info = st.session_state.uploaded_files['plansFile']
        st.info(f"📄 已上传文件: {file_info['name']}")

        col1, col2 = st.columns([1, 3])

        with col1:
            parse_clicked = st.button("🔍 解析活动类型", type="primary", use_container_width=True)

        if parse_clicked:
            with st.spinner("正在解析..."):
                result = parse_plans_file()

            if result['success']:
                st.success(f"✅ 解析成功！")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Agent", result['stats']['persons'])
                with col2:
                    st.metric("计划", result['stats']['plans'])
                with col3:
                    st.metric("活动", result['stats']['activities'])

                if result['activities']:
                    st.write(f"**发现的活动类型:** `{', '.join(result['activities'])}`")
                else:
                    st.warning("⚠️ 未找到活动类型")

                if st.button("🔄 应用结果"):
                    st.rerun()
            else:
                st.error(f"❌ 解析失败: {result['error']}")
    else:
        st.warning("⚠️ 请先在【输入文件配置】中上传 Plans 文件")

    # ========== Step 2: 配置活动参数 ==========
    st.markdown("---")
    st.markdown("#### 📋 Step 2: 配置活动参数")

    activity_params = st.session_state.get('activity_params', {})

    if detected_activities:
        st.success(f"✅ 从 Plans 文件检测到 {len(detected_activities)} 种活动")

    if activity_params:
        for act_type, act_params in list(activity_params.items()):
            is_detected = act_type in detected_activities
            badge = "🔍" if is_detected else "✏️"

            with st.expander(f"{badge} **{act_type}**", expanded=False):
                # 时间参数
                st.markdown("**⏰ 时间参数**")
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    act_params['typicalDuration'] = st.text_input(
                        "典型持续时间",
                        value=act_params.get('typicalDuration', '01:00:00'),
                        key=f"act_dur_{act_type}",
                        placeholder="HH:MM:SS"
                    )

                with col2:
                    act_params['minimalDuration'] = st.text_input(
                        "最小持续时间",
                        value=act_params.get('minimalDuration', ''),
                        key=f"act_min_{act_type}",
                        placeholder="可选"
                    )

                with col3:
                    act_params['openingTime'] = st.text_input(
                        "开门时间",
                        value=act_params.get('openingTime', ''),
                        key=f"act_open_{act_type}",
                        placeholder="可选"
                    )

                with col4:
                    act_params['closingTime'] = st.text_input(
                        "关门时间",
                        value=act_params.get('closingTime', ''),
                        key=f"act_close_{act_type}",
                        placeholder="可选"
                    )

                # 效用参数
                st.markdown("---")
                st.markdown("**⭐ 效用参数**")
                col1, col2, col3 = st.columns(3)

                with col1:
                    act_params['performing'] = st.number_input(
                        "活动效用 (utils/hr)",
                        value=float(act_params.get('performing', 6.0)),
                        step=0.5,
                        key=f"act_perf_{act_type}"
                    )

                with col2:
                    act_params['lateArrival'] = st.number_input(
                        "迟到惩罚 (utils/hr)",
                        value=float(act_params.get('lateArrival', -18.0)),
                        step=1.0,
                        key=f"act_late_{act_type}"
                    )

                with col3:
                    act_params['earlyDeparture'] = st.number_input(
                        "早退惩罚 (utils/hr)",
                        value=float(act_params.get('earlyDeparture', 0.0)),
                        step=1.0,
                        key=f"act_early_{act_type}"
                    )

                # 删除按钮
                st.markdown("---")
                if act_type not in ['home', 'pt interaction']:
                    if st.button(f"🗑️ 删除", key=f"del_act_{act_type}"):
                        del activity_params[act_type]
                        st.session_state.activity_params = activity_params
                        st.rerun()
                else:
                    st.caption(f"💡 '{act_type}' 不可删除")

        st.session_state.activity_params = activity_params
    else:
        st.info("暂无活动类型，请解析文件或手动添加")

    # ========== Step 3: 手动添加 ==========
    st.markdown("---")
    st.markdown("#### ➕ Step 3: 手动添加活动类型")

    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        presets = {'home': '居家', 'work': '工作', 'education': '教育',
                   'shopping': '购物', 'leisure': '休闲', 'other': '其他'}
        available = {k: v for k, v in presets.items() if k not in activity_params}

        new_preset = st.selectbox(
            "选择预设",
            options=[''] + list(available.keys()),
            format_func=lambda x: available.get(x, x) if x else "选择...",
            key="new_act_preset"
        )

    with col2:
        new_custom = st.text_input("或自定义名称", key="new_act_custom", placeholder="如: medical")

    with col3:
        st.write("")
        st.write("")
        if st.button("➕ 添加", key="add_act"):
            new_act = new_preset or new_custom.strip().lower()
            if new_act and new_act not in activity_params:
                activity_params[new_act] = {
                    'typicalDuration': '01:00:00',
                    'minimalDuration': '',
                    'openingTime': '',
                    'closingTime': '',
                    'performing': 6.0,
                    'lateArrival': -18.0,
                    'earlyDeparture': 0.0,
                }
                st.session_state.activity_params = activity_params
                st.rerun()
            elif new_act in activity_params:
                st.error(f"'{new_act}' 已存在")

    # ========== 公交活动 ==========
    if st.session_state.get('transit_enabled', False):
        st.markdown("---")
        st.markdown("#### 🚌 公交活动")

        if 'pt interaction' not in activity_params:
            activity_params['pt interaction'] = {
                'typicalDuration': '00:00:00',
                'minimalDuration': '',
                'openingTime': '',
                'closingTime': '',
                'performing': 0.0,
                'lateArrival': 0.0,
                'earlyDeparture': 0.0,
                'scoringThisActivityAtAll': False,  # 强制禁止评分
            }
            st.session_state.activity_params = activity_params
            st.rerun()
        else:
            st.success("✅ 'pt interaction' 已配置")

# ============================================================
# 其他配置模块 / Other Configuration Modules
# ============================================================

def render_global_configuration():
    """渲染全局配置"""

    st.markdown('<div class="module-header">🌍 全局设置 / Global Settings</div>',
                unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.session_state.global_config['randomSeed'] = st.number_input(
            create_param_label("随机种子 / randomSeed", "Random Seed (config.global.randomSeed)"),
            min_value=0,
            value=st.session_state.global_config['randomSeed'],
            help="相同种子产生相同结果，便于重复实验"
        )

    with col2:
        st.session_state.global_config['numberOfThreads'] = st.number_input(
            create_param_label("全局线程数 / numberOfThreads", "Number of Threads (config.global.numberOfThreads)"),
            min_value=1,
            max_value=64,
            value=st.session_state.global_config['numberOfThreads'],
            help="并行计算线程数，建议为CPU核心数的50-75%"
        )

    with col3:
        coord_systems = {
            'EPSG:4326': 'WGS84 经纬度 (全球通用)',
            'EPSG:32650': 'UTM 50N (中国东部)',
            'EPSG:32649': 'UTM 49N (中国中部)',
            'EPSG:32651': 'UTM 51N (中国东北)',
            'EPSG:3857': 'Web墨卡托 (网页地图)',
            'Atlantis': 'MATSim虚拟坐标 (教学用)',
        }

        current_crs = st.session_state.global_config['coordinateSystem']

        selected_crs = st.selectbox(
            create_param_label("坐标系统 / coordinateSystem", "Coordinate System (config.global.coordinateSystem)"),
            options=list(coord_systems.keys()),
            index=list(coord_systems.keys()).index(current_crs) if current_crs in coord_systems else 0,
            format_func=lambda x: f"{x} - {coord_systems[x]}",
            help="必须与路网文件使用的坐标系一致"
        )
        st.session_state.global_config['coordinateSystem'] = selected_crs

    with col4:
        # defaultDelimiter 不能为空，对应 GlobalConfigGroup.@NotBlank
        delimiter = st.text_input(
            create_param_label("默认CSV分隔符 / defaultDelimiter", "Default CSV Delimiter (config.global.defaultDelimiter)"),
            value=st.session_state.global_config.get('defaultDelimiter', ';'),
            help="用于读取/写入CSV文件的默认分隔符，MATSim默认为分号 ;"
        )
        if not delimiter.strip():
            st.error("⚠️ 默认CSV分隔符不能为空，将回退为 ';'")
            delimiter = ';'
        st.session_state.global_config['defaultDelimiter'] = delimiter
    # 兼容旧 config 版本
    st.markdown("#### ⚠️ 兼容旧版配置 / Deprecated Config Version")

    st.session_state.global_config['insistingOnDeprecatedConfigVersion'] = st.checkbox(
        create_param_label(
            "允许继续使用已废弃的 config 版本 / insistingOnDeprecatedConfigVersion",
            "Insist on using deprecated config version (config.global.insistingOnDeprecatedConfigVersion)"
        ),
        value=st.session_state.global_config.get('insistingOnDeprecatedConfigVersion', True),
        help=create_help_text(
            "一般保持勾选即可，表示即使 config.xml 中使用的是旧版本 DTD/结构，仍然强制按当前 MATSim 版本解析。"
            " 若你希望在发现旧版本配置时立即报错，则取消该选项。",
            "In most cases keep this checked so that MATSim still accepts older config versions. "
            "Uncheck it if you want MATSim to fail fast when encountering deprecated config versions."
        )
    )



def render_files_configuration():
    """渲染文件配置"""

    st.markdown('<div class="module-header">📁 输入文件配置 / Input Files</div>',
                unsafe_allow_html=True)

    st.markdown("""
    <div class="info-box">
    上传或指定仿真所需的输入文件。支持 .xml 和 .xml.gz 格式。
    </div>
    """, unsafe_allow_html=True)

    # ========== 必需文件 ==========
    st.markdown("#### 📌 必需文件")

    col1, col2 = st.columns(2)

    with col1:
        render_file_upload(
            "路网文件 / network.inputNetworkFile", "Network File (config.network.inputNetworkFile)",
            'networkFile',
            required=True,
            help_text="定义道路网络的拓扑结构"
        )

    with col2:
        render_file_upload(
            "人口计划文件 / plans.inputPlansFile", "Plans File (config.plans.inputPlansFile)",
            'plansFile',
            required=True,
            help_text="定义Agent的活动计划"
        )

        # 上传后提示解析
        if 'plansFile' in st.session_state.uploaded_files:
            detected = st.session_state.get('detected_activity_types', [])
            if not detected:
                st.info("💡 上传成功！请前往【活动类型配置】解析此文件以提取活动类型。")
            else:
                st.success(f"✅ 已解析，发现 {len(detected)} 种活动类型")

    # ========== 公交文件（如果启用） ==========
    if st.session_state.get('transit_enabled', False):
        st.markdown("---")
        st.markdown("#### 🚌 公交文件")

        col1, col2 = st.columns(2)

        with col1:
            render_file_upload(
                "公交时刻表 / transit.transitScheduleFile", "Transit Schedule (config.transit.transitScheduleFile)",
                'transitScheduleFile',
                required=True,
                help_text="包含线路、站点、发车时刻的XML文件"
            )

            # 提示解析
            if 'transitScheduleFile' in st.session_state.uploaded_files:
                detected_submodes = st.session_state.get('transit_submodes_detected', [])
                if not detected_submodes:
                    st.info("💡 请前往【公共交通配置】解析此文件")
                else:
                    st.success(f"✅ 已解析，发现模式: {', '.join(detected_submodes)}")

        with col2:
            render_file_upload(
                "公交车辆 / transit.vehiclesFile", "Transit Vehicles (config.transit.vehiclesFile)",
                'transitVehiclesFile',
                required=True,
                help_text="包含车辆类型和容量的XML文件"
            )
    else:
        st.markdown("---")
        st.caption("💡 公交文件配置：请先在【出行模式配置 → 公共交通配置】中启用公交")

    # ========== 可选文件 ==========
    st.markdown("---")
    st.markdown("#### 📎 可选文件")

    with st.expander("车辆与设施文件", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            render_file_upload(
                "车辆类型文件 / vehicles.vehicleTypesFile", "Vehicles File (config.vehicles.vehicleTypesFile)",
                'vehiclesFile',
                required=False,
                help_text="定义不同车辆类型的属性（网络模式车辆）"
            )

        with col2:
            render_file_upload(
                "设施文件 / facilities.inputFacilitiesFile", "Facilities File (config.facilities.inputFacilitiesFile)",
                'facilitiesFile',
                required=False,
                help_text="定义活动设施的详细信息"
            )
    with st.expander("家庭文件", expanded=False):
        render_file_upload(
            "家庭文件 / households.inputFile", "Households File (config.households.inputFile)",
            'householdsFile',
            required=False,
            help_text="家庭结构数据（如收入、车辆拥有量等），用于增强人口建模和出行行为建模。"
        )

    with st.expander("验证数据文件", expanded=False):
        render_file_upload(
            "流量计数文件 / counts.inputCountsFile", "Counts File (config.counts.inputCountsFile)",
            'countsFile',
            required=False,
            help_text="实测交通流量数据，用于模型验证"
        )

    # ========== 文件状态汇总 ==========
    st.markdown("---")
    st.markdown("#### 📊 文件状态汇总")

    uploaded_files = st.session_state.get('uploaded_files', {})
    file_config = st.session_state.get('file_config', {})

    # 必需文件检查
    required_files = {
        'networkFile': '路网文件',
        'plansFile': '人口计划文件',
    }

    if st.session_state.get('transit_enabled', False):
        required_files['transitScheduleFile'] = '公交时刻表'
        required_files['transitVehiclesFile'] = '公交车辆'

    # 可选文件
    optional_files = {
        'vehiclesFile': '车辆类型文件',
        'facilitiesFile': '设施文件',
        'countsFile': '流量计数文件',
    }

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**必需文件：**")
        for key, name in required_files.items():
            if key in uploaded_files or file_config.get(key):
                st.markdown(f"✅ {name}")
            else:
                st.markdown(f"❌ {name}")

    with col2:
        st.markdown("**可选文件：**")
        for key, name in optional_files.items():
            if key in uploaded_files or file_config.get(key):
                st.markdown(f"✅ {name}")
            else:
                st.markdown(f"⚪ {name}")

    # 总体状态
    all_required_ok = all(
        key in uploaded_files or file_config.get(key)
        for key in required_files.keys()
    )

    st.markdown("---")
    if all_required_ok:
        st.success("✅ 所有必需文件已配置")
    else:
        missing = [name for key, name in required_files.items()
                   if key not in uploaded_files and not file_config.get(key)]
        st.error(f"❌ 缺少必需文件: {', '.join(missing)}")

def render_network_configuration():
    """渲染 network 模块配置（NetworkConfigGroup），文件全部通过上传自动识别路径"""

    st.markdown('<div class="module-header">🕸️ 路网配置 / Network Settings</div>',
                unsafe_allow_html=True)

    net_cfg = st.session_state.network_config
    file_cfg = st.session_state.file_config

    st.markdown("""
    <div class="info-box">
    <b>模块说明 / Description</b><br>
    • 控制 <code>config.network</code> 路网模块，包括主路网文件、时变路网和车道定义。<br>
    • 本页面只负责“配置含义”，真正的文件选择全部通过上传完成，并自动记录路径。<br><br>
    <b>使用建议 / Tips</b><br>
    • 路网主文件在「输入文件配置 / Input Files」中作为必需文件上传，只需上传一次。<br>
    • 路网变更事件文件和车道定义文件，可在本页面直接上传，无需手动填写路径。<br>
    </div>
    """, unsafe_allow_html=True)

    # ===== 路网输入文件（只读展示） =====
    st.markdown("#### 📁 路网输入文件 / Input Network File")

    network_path = file_cfg.get('networkFile', '').strip()
    if network_path:
        st.success(f"已选择路网文件：{network_path}")
        st.caption("该路径来自「输入文件配置」步骤的上传结果，无需在此重复上传或手动填写。")
    else:
        st.error("尚未配置路网文件。请先前往「输入文件配置 / Input Files」步骤上传 config.network.inputNetworkFile 对应的文件。")

    # ===== 其他网络参数 =====
    st.markdown("#### ⚙️ 其他网络参数 / Other Network Parameters")

    col1, col2 = st.columns(2)

    # 左侧：时变开关 + CRS
    with col1:
        net_cfg['timeVariantNetwork'] = st.checkbox(
            create_param_label("启用时变路网 / timeVariantNetwork",
                               "Use time-variant network (config.network.timeVariantNetwork)"),
            value=bool(net_cfg.get('timeVariantNetwork', False)),
            help=create_help_text(
                "勾选后，仿真会根据 change events 文件（如封路/限速等）动态修改路网。",
                "If checked, the simulation will apply network change events "
                "to model time-varying network conditions."
            )
        )

        net_cfg['inputCRS'] = st.text_input(
            create_param_label("输入坐标系（已废弃） / inputCRS",
                               "Input CRS (deprecated) (config.network.inputCRS)"),
            value=net_cfg.get('inputCRS', ''),
            help=create_help_text(
                "已标记为废弃。仅在需要保持与旧场景完全兼容时才填写，"
                "一般建议通过 config.global.coordinateSystem 或外部工具处理坐标系。",
                "Deprecated. Only use this to keep full backward compatibility with older scenarios; "
                "prefer handling CRS via config.global.coordinateSystem or external tools."
            )
        )

    # 右侧：变更事件文件 + 车道文件，通过上传自动设置路径
    with col2:
        # 路网变更事件文件：通过上传设置 network.inputChangeEventsFile
        change_events_path = render_file_upload(
            "路网变更事件文件 / network.inputChangeEventsFile",
            "Network change events file (config.network.inputChangeEventsFile)",
            'networkChangeEventsFile',
            required=False,
            help_text="可选。包含封路、限速等时变路网事件的 XML / XML.gz 文件。"
        )
        # 将上传得到的路径同步到 network_config
        net_cfg['inputChangeEventsFile'] = change_events_path or ""

        # 车道定义文件：通过上传设置 network.laneDefinitionsFile
        lane_defs_path = render_file_upload(
            "车道定义文件 / network.laneDefinitionsFile",
            "Lane definitions file (config.network.laneDefinitionsFile)",
            'laneDefinitionsFile',
            required=False,
            help_text="可选。若使用车道级建模，则上传 lanes.xml / lanes.xml.gz。"
        )
        net_cfg['laneDefinitionsFile'] = lane_defs_path or ""


def render_routing_configuration():
    """渲染 Routing 模块完整配置（RoutingConfigGroup）"""

    st.markdown('<div class="module-header">🗺️ 路由配置 / Routing Settings</div>',
                unsafe_allow_html=True)

    routing_cfg = st.session_state.routing_config

    st.markdown("""
    <div class="info-box">
    <b>模块说明 / Description</b><br>
    • 控制 <code>config.routing</code> 模块，定义如何计算各模式的出行路径和时间。<br>
    • 网络模式使用路由算法在路网上计算路径；传送模式使用直线距离估算。<br><br>
    <b>使用建议 / Tips</b><br>
    • networkModes 和 teleportedModeParameters 会自动从「出行模式配置」同步。<br>
    • 此处仅配置路由算法相关的全局参数。<br>
    </div>
    """, unsafe_allow_html=True)

    # ===== 1. 网络模式 (只读展示) =====
    st.markdown("#### 🚗 网络模式 / Network Modes")

    network_modes = list(st.session_state.get('network_modes', {}).keys())
    if network_modes:
        st.success(f"当前网络模式: `{', '.join(network_modes)}`")
    else:
        st.warning("尚未配置网络模式。请在「出行模式配置」中添加。")
    st.caption("此参数从「出行模式配置」自动同步，无需手动设置。")

    # ===== 2. 传送模式 (只读展示) =====
    st.markdown("---")
    st.markdown("#### 🚶 传送模式参数 / Teleported Mode Parameters")

    teleported_modes = st.session_state.get('teleported_modes', {})

    if teleported_modes:
        # 表头
        cols = st.columns([2, 1.5, 1.5, 2])
        cols[0].markdown("**模式 / Mode**")
        cols[1].markdown("**速度 (km/h)**")
        cols[2].markdown("**直线系数**")
        cols[3].markdown("**计算公式**")

        for mode_name, mode_config in teleported_modes.items():
            cols = st.columns([2, 1.5, 1.5, 2])

            with cols[0]:
                display_name = mode_config.get('display_name', mode_name)
                st.text(f"{mode_name}")
                st.caption(display_name)

            with cols[1]:
                speed_kmh = mode_config.get('speed_kmh', 5.0)
                st.text(f"{speed_kmh:.1f}")

            with cols[2]:
                beeline = mode_config.get('beeline_factor', 1.3)
                st.text(f"{beeline:.2f}")

            with cols[3]:
                speed_ms = speed_kmh / 3.6
                st.caption(f"时间 = 距离 × {beeline:.1f} ÷ {speed_ms:.2f} m/s")

        st.caption("这些参数从「出行模式配置」自动同步。如需修改，请前往「出行模式配置」页面。")
    else:
        st.info("暂无传送模式。请在「出行模式配置」中添加。")

    # ===== 3. 路由参数 =====
    st.markdown("---")
    st.markdown("#### ⚙️ 路由参数 / Routing Parameters")

    col1, col2 = st.columns(2)

    with col1:
        routing_cfg['routingRandomness'] = st.number_input(
            create_param_label("路由随机性 / routingRandomness",
                               "Routing Randomness (config.routing.routingRandomness)"),
            min_value=0.0,
            max_value=10.0,
            value=float(routing_cfg.get('routingRandomness', 3.0)),
            step=0.5,
            help=create_help_text(
                "收费路由中金钱效用的随机性强度。较大值产生更多样化的路径选择。"
                "技术上是对数正态分布的宽度参数，3.0 是推荐值。",
                "Strength of randomness for utility of money in toll routing. "
                "Higher values produce more diverse route choices. "
                "Technically the width parameter of a log-normal distribution; 3.0 is recommended."
            )
        )

        routing_cfg['clearDefaultTeleportedModeParams'] = st.checkbox(
            create_param_label("清除默认传送模式 / clearDefaultTeleportedModeParams",
                               "Clear default teleported modes"),
            value=bool(routing_cfg.get('clearDefaultTeleportedModeParams', False)),
            help=create_help_text(
                "勾选后清除 MATSim 内置的默认传送模式（walk, bike, pt, ride 等）。"
                "然后只使用您在配置中明确定义的模式。",
                "If checked, clears MATSim built-in default teleported modes (walk, bike, pt, ride, etc.). "
                "Only modes explicitly defined in your config will be used."
            )
        )

    with col2:
        current_access_egress = routing_cfg.get('accessEgressType', 'none')
        access_egress_options = list(ROUTING_ACCESS_EGRESS_TYPE_OPTIONS.keys())

        routing_cfg['accessEgressType'] = st.selectbox(
            create_param_label("接驳类型 / accessEgressType",
                               "Access/Egress Type (config.routing.accessEgressType)"),
            options=access_egress_options,
            index=access_egress_options.index(
                current_access_egress) if current_access_egress in access_egress_options else 0,
            format_func=lambda x: ROUTING_ACCESS_EGRESS_TYPE_OPTIONS[x][0],
            help=create_help_text(
                "定义如何模拟接驳行程（从起点到主模式、从主模式到终点）。"
                "none = 不模拟接驳；accessEgressModeToLink = 欧氏距离步行到Link。",
                "Defines how access and egress trips are simulated. "
                "none = no access/egress; accessEgressModeToLink = walk Euclidean distance to link."
            )
        )

        # 显示选项说明
        st.caption(ROUTING_ACCESS_EGRESS_TYPE_OPTIONS[routing_cfg['accessEgressType']][1])

        current_consistency = routing_cfg.get('networkRouteConsistencyCheck', 'abortOnInconsistency')
        consistency_options = list(ROUTING_NETWORK_CONSISTENCY_CHECK_OPTIONS.keys())

        routing_cfg['networkRouteConsistencyCheck'] = st.selectbox(
            create_param_label("路网一致性检查 / networkRouteConsistencyCheck",
                               "Network Route Consistency Check"),
            options=consistency_options,
            index=consistency_options.index(current_consistency) if current_consistency in consistency_options else 1,
            format_func=lambda x: ROUTING_NETWORK_CONSISTENCY_CHECK_OPTIONS[x],
            help=create_help_text(
                "是否检查路网路由的一致性。推荐保持 abortOnInconsistency 以便及早发现问题。",
                "Whether to check network route consistency. Recommended to keep abortOnInconsistency "
                "to catch problems early."
            )
        )

    st.session_state.routing_config = routing_cfg

def render_linkstats_configuration():
    """渲染 linkStats 模块配置（LinkStatsConfigGroup）"""

    st.markdown('<div class="module-header">🧮 LinkStats 配置 / LinkStats Settings</div>',
                unsafe_allow_html=True)

    ls_cfg = st.session_state.linkstats_config

    st.markdown("""
    <div class="info-box">
    <b>模块说明 / Description</b><br>
    • 控制 <code>config.linkStats</code> 模块，输出每条 link 在各迭代的统计指标。<br>
    • 指标通常包括流量、速度、密度等，用于诊断和可视化路网运行状态。<br><br>
    <b>使用建议 / Tips</b><br>
    • 大网络 + 多迭代时，LinkStats 文件可能非常大，占用内存与磁盘，请谨慎开启。<br>
    • 建议仅在调试或诊断阶段开启，正式大规模跑批时可以关闭（writeLinkStatsInterval=0）。<br>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        ls_cfg['writeLinkStatsInterval'] = st.number_input(
            create_param_label("输出间隔迭代数 / writeLinkStatsInterval",
                               "Write interval (config.linkStats.writeLinkStatsInterval)"),
            min_value=0,
            value=int(ls_cfg.get('writeLinkStatsInterval', 0)),
            help=create_help_text(
                "每隔多少个迭代输出一次 LinkStats。0 表示不输出。",
                "Number of iterations between writing linkStats files; 0 means disabled."
            )
        )

    with col2:
        ls_cfg['averageLinkStatsOverIterations'] = st.number_input(
            create_param_label("平均统计的迭代数 / averageLinkStatsOverIterations",
                               "Average over iterations (config.linkStats.averageLinkStatsOverIterations)"),
            min_value=1,
            value=int(ls_cfg.get('averageLinkStatsOverIterations', 5)),
            help=create_help_text(
                "写出 LinkStats 时，将最近 N 个迭代的统计做平均平滑。通常取 3~10。",
                "When writing linkStats, average statistics over the last N iterations. "
                "Typical values are between 3 and 10."
            )
        )


def render_households_configuration():
    """渲染 households 模块配置（HouseholdsConfigGroup）"""

    st.markdown('<div class="module-header">👪 家庭配置 / Households Settings</div>',
                unsafe_allow_html=True)

    households_cfg = st.session_state.households_config
    file_config = st.session_state.file_config

    st.markdown("""
    <div class="info-box">
    <b>模块说明 / Description</b><br>
    • 控制家庭数据 (<code>households.xml</code>) 的读取。<br>
    • 可选读取单独的 households 属性文件（已不推荐）。<br><br>
    <b>使用建议 / Tips</b><br>
    • 若你的场景没有家庭结构，可以不配置该模块。<br>
    • 若需要家庭收入、车拥有量等信息，一般需要启用 households 模块并提供相应输入文件。<br>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### 📁 家庭输入文件 / Input Households File")

    current_hh_file = file_config.get('householdsFile', '')
    new_hh_file = st.text_input(
        create_param_label("家庭文件路径 / inputFile", "Households file path (config.households.inputFile)"),
        value=current_hh_file,
        help=create_help_text(
            "通常为 <code>households.xml</code> 或 <code>households.xml.gz</code>。",
            "Typically <code>households.xml</code> or <code>households.xml.gz</code>."
        )
    )
    file_config['householdsFile'] = new_hh_file

    st.markdown("#### ⚙️ Households 模块参数 / Households Parameters")

    col1, col2 = st.columns(2)

    with col1:
        households_cfg['inputHouseholdAttributesFile'] = st.text_input(
            create_param_label("家庭属性文件 / inputHouseholdAttributesFile",
                               "Deprecated households attributes file (config.households.inputHouseholdAttributesFile)"),
            value=households_cfg.get('inputHouseholdAttributesFile', ''),
            help=create_help_text(
                "可选。指定诸如 <code>householdAttributes.xml</code> 的旧式家庭属性文件。",
                "Optional. Path to deprecated external households attributes file, "
                "such as <code>householdAttributes.xml</code>."
            )
        )

    with col2:
        households_cfg['insistingOnUsingDeprecatedHouseholdsAttributeFile'] = st.checkbox(
            create_param_label(
                "仍然读取已废弃的家庭属性文件 / insistingOnUsingDeprecatedHouseholdsAttributeFile",
                "Insist on using deprecated households attribute file"
            ),
            value=households_cfg.get('insistingOnUsingDeprecatedHouseholdsAttributeFile', False),
            help=create_help_text(
                "仅当你确实仍在使用独立的家庭属性文件并清楚风险时才勾选。"
                " 官方建议将这些属性迁移到 households 内嵌 <code>&lt;attributes&gt;</code>。",
                "Check only if you still rely on a separate households attributes file and understand the risks. "
                "The official recommendation is to migrate attributes into the households objects."
            )
        )

def render_facilities_configuration():
    """渲染 facilities 模块配置（FacilitiesConfigGroup）"""

    st.markdown('<div class="module-header">🏢 设施配置 / Facilities Settings</div>',
                unsafe_allow_html=True)

    facilities_cfg = st.session_state.facilities_config
    file_config = st.session_state.file_config

    st.markdown("""
    <div class="info-box">
    <b>模块说明 / Description</b><br>
    • 控制 MATSim 读取或生成活动设施 (<code>facilities.xml</code>) 的方式。<br>
    • 支持从文件读取、在场景中手工构造，或根据出行计划自动生成设施。<br><br>
    <b>使用建议 / Tips</b><br>
    • 如果已经有完善的设施数据，推荐选择 <code>fromFile</code> 并指定设施文件。<br>
    • 如果只在 plans 中有坐标但没有设施文件，可选择自动生成选项。<br>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### 📁 设施输入文件 / Input Facilities File")

    current_fac_file = file_config.get('facilitiesFile', '')
    new_fac_file = st.text_input(
        create_param_label("设施文件路径 / inputFacilitiesFile", "Facilities file path (config.facilities.inputFacilitiesFile)"),
        value=current_fac_file,
        help=create_help_text(
            "通常为 <code>facilities.xml</code> 或 <code>facilities.xml.gz</code>。"
            " 若通过上一步“输入文件”已经上传，这里会自动带出路径。",
            "Typically <code>facilities.xml</code> or <code>facilities.xml.gz</code>. "
            "If you uploaded it in the previous 'Input Files' step, the path is pre-filled here."
        )
    )
    file_config['facilitiesFile'] = new_fac_file

    st.markdown("#### ⚙️ 设施模块参数 / Facilities Parameters")

    col1, col2 = st.columns(2)

    with col1:
        facilities_cfg['inputFacilityAttributesFile'] = st.text_input(
            create_param_label("设施属性文件 / inputFacilityAttributesFile",
                               "Deprecated facilities attributes file (config.facilities.inputFacilityAttributesFile)"),
            value=facilities_cfg.get('inputFacilityAttributesFile', ''),
            help=create_help_text(
                "可选。用于指定 <code>facilitiesAttributes.xml</code> 等外部属性文件。"
                " 官方已不推荐使用，建议将属性写入每个 facility 的 <code>&lt;attributes&gt;</code> 中。",
                "Optional. Path to a deprecated external facilities attributes file such as "
                "<code>facilitiesAttributes.xml</code>. It is deprecated; prefer using attributes inside each facility."
            )
        )

        facilities_cfg['inputCRS'] = st.text_input(
            create_param_label("输入坐标系 / inputCRS", "Input CRS for facilities (config.facilities.inputCRS)"),
            value=facilities_cfg.get('inputCRS', ''),
            help=create_help_text(
                "可选。若设施文件使用的坐标系与全局 <code>config.global.coordinateSystem</code> 不同，可以在此单独指定。",
                "Optional. If the facilities file uses a different CRS than "
                "<code>config.global.coordinateSystem</code>, specify it here."
            )
        )

    with col2:
        facilities_source_options = {
            "none": "none - 不使用 facilities 模块",
            "fromFile": "fromFile - 直接从 inputFacilitiesFile 读取",
            "setInScenario": "setInScenario - 在场景代码中手工设置",
            "onePerActivityLinkInPlansFile": "onePerActivityLinkInPlansFile - 每条活动链路自动生成一个 facility",
            "onePerActivityLinkInPlansFileExceptWhenCoordinatesAreGiven": (
                "onePerActivityLinkInPlansFileExceptWhenCoordinatesAreGiven - "
                "按 link 生成，若活动已有坐标则复用坐标"
            ),
            "onePerActivityLocationInPlansFile": "onePerActivityLocationInPlansFile - 按活动坐标生成 facility"
        }
        current_source = facilities_cfg.get('facilitiesSource', 'none')
        if current_source not in facilities_source_options:
            current_source = 'none'

        facilities_cfg['facilitiesSource'] = st.selectbox(
            create_param_label("设施来源方式 / facilitiesSource",
                               "Facilities source (config.facilities.facilitiesSource)"),
            options=list(facilities_source_options.keys()),
            index=list(facilities_source_options.keys()).index(current_source),
            format_func=lambda x: facilities_source_options[x],
            help=create_help_text(
                "决定 MATSim 如何获得设施：从文件读取、在场景中设置，或根据计划自动生成。",
                "Controls how MATSim obtains facilities: from file, set in scenario, or auto-generated from plans."
            )
        )

        facilities_cfg['idPrefix'] = st.text_input(
            create_param_label("自动生成设施ID前缀 / idPrefix", "ID prefix for auto-generated facilities (config.facilities.idPrefix)"),
            value=facilities_cfg.get('idPrefix', 'f_auto_'),
            help=create_help_text(
                "用于自动生成的设施 ID 前缀。仅在 facilitiesSource 选择自动生成方式时生效。",
                "Prefix for IDs of auto-generated facilities; only relevant when using auto-generation facilitiesSource."
            )
        )

    st.markdown("#### ⚠️ 兼容旧属性文件 / Deprecated Attributes File")

    facilities_cfg['insistingOnUsingDeprecatedFacilitiesAttributeFile'] = st.checkbox(
        create_param_label(
            "仍然读取已废弃的设施属性文件 / insistingOnUsingDeprecatedFacilitiesAttributeFile",
            "Insist on using deprecated facilities attribute file"
        ),
        value=facilities_cfg.get('insistingOnUsingDeprecatedFacilitiesAttributeFile', False),
        help=create_help_text(
            "仅当你必须继续使用旧的 <code>facilitiesAttributes.xml</code> 时才勾选。"
            " 官方建议迁移到 facility 内嵌属性，否则可能在未来版本中不再支持。",
            "Check this only if you really must keep using the deprecated facilitiesAttributes.xml. "
            "The official recommendation is to migrate to attributes inside each facility."
        )
    )


def render_controller_configuration():
    """渲染控制器配置（包含 ControllerConfigGroup 全部参数）"""

    st.markdown('<div class="module-header">🎮 仿真控制配置 / Controller Settings</div>',
                unsafe_allow_html=True)

    ctrl = st.session_state.controller_config

    # ========== 1. 基本设置 / Basic ==========
    st.markdown("#### 📋 基本设置 / Basic Settings")

    col1, col2 = st.columns(2)

    with col1:
        ctrl['outputDirectory'] = st.text_input(
            create_param_label("输出目录 / outputDirectory", "Output Directory (controller.outputDirectory)"),
            value=ctrl.get('outputDirectory', './output'),
            help=create_help_text(
                "所有结果文件的根目录。",
                "Root directory for all output files."
            )
        )

        ctrl['firstIteration'] = st.number_input(
            create_param_label("起始迭代 / firstIteration", "First Iteration (controller.firstIteration)"),
            min_value=0,
            value=int(ctrl.get('firstIteration', 0)),
            help=create_help_text(
                "从第几轮开始仿真（包含）。",
                "Iteration index to start the simulation (inclusive)."
            )
        )

    with col2:
        ctrl['runId'] = st.text_input(
            create_param_label("运行标识 / runId", "Run ID (controller.runId)"),
            value=ctrl.get('runId', 'run001'),
            help=create_help_text(
                "用于区分不同运行，会作为输出文件名前缀写入。",
                "Identifier for this run; used as prefix for output files."
            )
        )

        ctrl['lastIteration'] = st.number_input(
            create_param_label("结束迭代 / lastIteration", "Last Iteration (controller.lastIteration)"),
            min_value=1,
            max_value=100000,
            value=int(ctrl.get('lastIteration', 100)),
            help=create_help_text(
                "仿真结束的迭代号（包含），必须 ≥ firstIteration。",
                "Iteration index to end the simulation (inclusive); must be ≥ firstIteration."
            )
        )

    # ========== 2. 仿真引擎与路由 / Mobsim & Routing ==========
    st.markdown("#### ⚙️ 仿真引擎与路由 / Mobsim & Routing")

    col1, col2 = st.columns(2)

    with col1:
        ctrl['mobsim'] = st.selectbox(
            create_param_label("仿真引擎 / mobsim", "Simulation Engine (controller.mobsim)"),
            options=list(MOBSIM_OPTIONS.keys()),
            format_func=lambda x: f"{x} - {MOBSIM_OPTIONS[x]}",
            index=list(MOBSIM_OPTIONS.keys()).index(ctrl.get('mobsim', 'qsim')),
            help=create_help_text(
                "选择用于执行交通仿真的引擎类型。",
                "Choose the mobility simulation engine to run the traffic model."
            )
        )

        ctrl['enableLinkToLinkRouting'] = st.checkbox(
            create_param_label("启用 link-to-link 路由 / enableLinkToLinkRouting",
                               "Enable link-to-link routing"),
            value=bool(ctrl.get('enableLinkToLinkRouting', False)),
            help=create_help_text(
                "若启用，路由将基于『link→link』转向时间计算（仅支持 Dijkstra，且不能与按模式分离的 travel time 同时使用）。",
                "If enabled, routing is done link-to-link including turning times "
                "(only supported with Dijkstra and incompatible with per-mode travel times)."
            )
        )

    with col2:
        ctrl['routingAlgorithmType'] = st.selectbox(
            create_param_label("物理路网车辆路由算法（除公交） / routingAlgorithmType",
                               "Routing Algorithm (controller.routingAlgorithmType)"),
            options=list(ROUTING_ALGORITHMS.keys()),
            format_func=lambda x: f"{x} - {ROUTING_ALGORITHMS[x]}",
            index=list(ROUTING_ALGORITHMS.keys()).index(ctrl.get('routingAlgorithmType', 'SpeedyALT')),
            help=create_help_text(
                "选择最短广义成本路径算法。",
                "Choose the shortest (generalized) cost path algorithm."
            )
        )

        ctrl['createScoringFunctionType'] = st.selectbox(
            create_param_label("评分函数创建时机 / createScoringFunctionType",
                               "When to create scoring functions"),
            options=list(CONTROLLER_CREATE_SCORING_OPTIONS.keys()),
            format_func=lambda x: CONTROLLER_CREATE_SCORING_OPTIONS[x],
            index=list(CONTROLLER_CREATE_SCORING_OPTIONS.keys()).index(
                ctrl.get('createScoringFunctionType', 'IterationStarts')
            ),
            help=create_help_text(
                "控制在仿真流程中的哪一步创建 scoring function（每轮开始 / 每次仿真前）。",
                "Controls at which point in the iteration scoring functions are created "
                "(at iteration start / before mobsim)."
            )
        )

    # ========== 3. 输出设置 / Output Settings ==========
    st.markdown("#### 💾 输出频率与格式 / Output Frequency & Formats")

    col1, col2, col3 = st.columns(3)

    with col1:
        ctrl['writeEventsInterval'] = st.number_input(
            create_param_label("事件写入间隔 / writeEventsInterval",
                               "Events Write Interval"),
            min_value=0,
            value=int(ctrl.get('writeEventsInterval', 50)),
            help=create_help_text(
                "每多少轮写一次 events 文件；0 表示完全不写。",
                "Write events every N iterations; 0 means never write."
            )
        )

        ctrl['writeTripsInterval'] = st.number_input(
            create_param_label("出行(trips)写入间隔 / writeTripsInterval",
                               "Trips Write Interval"),
            min_value=0,
            value=int(ctrl.get('writeTripsInterval', 50)),
            help=create_help_text(
                "每多少轮导出 trips（出行）统计；0 表示不导出。",
                "Export trips statistics every N iterations; 0 means do not export."
            )
        )

    with col2:
        ctrl['writePlansInterval'] = st.number_input(
            create_param_label("计划写入间隔 / writePlansInterval",
                               "Plans Write Interval"),
            min_value=0,
            value=int(ctrl.get('writePlansInterval', 50)),
            help=create_help_text(
                "每多少轮写一次 plans 文件；0 表示不写（但某些关键迭代仍会写出）。",
                "Write plans every N iterations; 0 means no regular writes "
                "(some key iterations may still be written)."
            )
        )

        ctrl['writeSnapshotsInterval'] = st.number_input(
            create_param_label("快照写入间隔 / writeSnapshotsInterval",
                               "Snapshots Write Interval"),
            min_value=0,
            value=int(ctrl.get('writeSnapshotsInterval', 1)),
            help=create_help_text(
                "每多少轮输出快照（由 snapshotFormat 控制格式）；0 表示不输出快照。",
                "Write snapshots every N iterations (formats controlled by snapshotFormat); "
                "0 means no snapshots."
            )
        )

    with col3:
        ctrl['overwriteFiles'] = st.selectbox(
            create_param_label("文件覆盖策略 / overwriteFiles",
                               "Overwrite Behavior (controller.overwriteFiles)"),
            options=list(OVERWRITE_OPTIONS.keys()),
            format_func=lambda x: OVERWRITE_OPTIONS[x],
            index=list(OVERWRITE_OPTIONS.keys()).index(
                ctrl.get('overwriteFiles', 'deleteDirectoryIfExists')
            ),
            help=create_help_text(
                "当输出目录已存在且非空时采取的行为。",
                "What to do if the output directory already exists and is non-empty."
            )
        )

        ctrl['compressionType'] = st.selectbox(
            create_param_label("压缩方式 / compressionType", "Compression Type"),
            options=list(CONTROLLER_COMPRESSION_OPTIONS.keys()),
            format_func=lambda x: CONTROLLER_COMPRESSION_OPTIONS[x],
            index=list(CONTROLLER_COMPRESSION_OPTIONS.keys()).index(
                ctrl.get('compressionType', 'gzip')
            ),
            help=create_help_text(
                "控制大多数输出文件使用的压缩格式。",
                "Controls the compression format used for most output files."
            )
        )

    # 事件文件格式 / snapshots 格式
    st.markdown("##### 📂 文件格式 / File Formats")

    col1, col2 = st.columns(2)

    with col1:
        current_events = ctrl.get('eventsFileFormat', ['xml'])
        ctrl['eventsFileFormat'] = st.multiselect(
            create_param_label("事件文件格式 / eventsFileFormat", "Events File Format"),
            options=list(CONTROLLER_EVENTS_FORMAT_OPTIONS.keys()),
            default=current_events if current_events else ['xml'],
            format_func=lambda x: CONTROLLER_EVENTS_FORMAT_OPTIONS[x],
            help=create_help_text(
                "可同时输出多种事件格式（如 XML + PB）。",
                "You can write multiple event formats in parallel (e.g. XML + PB)."
            )
        )

    with col2:
        current_snapshots = ctrl.get('snapshotFormat', [])
        ctrl['snapshotFormat'] = st.multiselect(
            create_param_label("快照格式 / snapshotFormat", "Snapshot Formats"),
            options=list(CONTROLLER_SNAPSHOT_FORMAT_OPTIONS.keys()),
            default=current_snapshots,
            format_func=lambda x: CONTROLLER_SNAPSHOT_FORMAT_OPTIONS[x],
            help=create_help_text(
                "选择要生成的网络快照格式（用于可视化或后续分析）。",
                "Select which snapshot formats to generate for visualization or analysis."
            )
        )

    # ========== 4. 图表与数据清理 / Graphs & Cleanup ==========
    st.markdown("#### 📊 图表与数据清理 / Graphs & Cleanup")

    col1, col2 = st.columns(2)

    with col1:
        ctrl['createGraphsInterval'] = st.number_input(
            create_param_label("图表输出间隔 / createGraphsInterval",
                               "Create Graphs Interval"),
            min_value=0,
            value=int(ctrl.get('createGraphsInterval', 1)),
            help=create_help_text(
                "每多少轮生成统计图表（scorestats 等）；0 表示不生成。",
                "Create analysis graphs every N iterations; 0 means no graphs."
            )
        )

        ctrl['dumpDataAtEnd'] = st.checkbox(
            create_param_label("结束时导出完整数据 / dumpDataAtEnd",
                               "Dump full data at end"),
            value=bool(ctrl.get('dumpDataAtEnd', True)),
            help=create_help_text(
                "若勾选，在仿真结束时额外导出一份完整的 plans/network/config 等结果。",
                "If checked, an extra full dump of plans/network/config is written at the end."
            )
        )

    with col2:
        ctrl['cleanItersAtEnd'] = st.selectbox(
            create_param_label("结束时处理 ITERS / cleanItersAtEnd",
                               "Clean iterations at end"),
            options=list(CONTROLLER_CLEAN_ITERS_OPTIONS.keys()),
            format_func=lambda x: CONTROLLER_CLEAN_ITERS_OPTIONS[x],
            index=list(CONTROLLER_CLEAN_ITERS_OPTIONS.keys()).index(
                ctrl.get('cleanItersAtEnd', 'keep')
            ),
            help=create_help_text(
                "仿真成功结束后对 ITERS 目录的处理方式。",
                "How to handle the ITERS directory after a successful run."
            )
        )

        ctrl['memoryObserverInterval'] = st.number_input(
            create_param_label("内存监控间隔(秒) / memoryObserverInterval",
                               "Memory observer interval (seconds)"),
            min_value=1,
            value=int(ctrl.get('memoryObserverInterval', 60)),
            help=create_help_text(
                "每隔多少秒在日志中打印一次当前 Java 内存使用情况。",
                "How often (in seconds) to log current JVM memory usage."
            )
        )

    # 写回 session
    st.session_state.controller_config = ctrl


def render_qsim_configuration():
    """渲染 QSim 配置（仅当 mobsim = qsim 时显示）"""

    if st.session_state.controller_config['mobsim'] != 'qsim':
        st.info(f"当前仿真内核为 {st.session_state.controller_config['mobsim']}，此处显示的是 Hermes/QSim 以外的配置说明。"
                " 如需配置 QSim，请到“仿真控制”中将内核切换为 qsim。")
        return

    qsim = st.session_state.qsim_config

    st.markdown('<div class="module-header">🚦 QSim 队列仿真配置 / QSim Settings</div>',
                unsafe_allow_html=True)

    st.markdown("""
    <div class="info-box">
    <b>模块说明 / Description</b><br>
    • QSim 是 MATSim 默认的多线程队列仿真内核。<br>
    • 控制时间步长、流量容量、快照输出、渗流行为等细节。<br><br>
    <b>使用建议 / Tips</b><br>
    • 一般仅需设置时间窗口、流量/容量采样率，其它保持默认即可。<br>
    • 对于空间可视化、渗流建模、PT 等高级用法，可展开“高级设置”。<br>
    </div>
    """, unsafe_allow_html=True)

    # ===== 时间设置 =====
    st.markdown("#### ⏰ 时间设置 / Time Settings")

    col1, col2, col3 = st.columns(3)

    with col1:
        qsim['startTime'] = st.text_input(
            "开始时间 / startTime",
            value=qsim.get('startTime', '00:00:00'),
            help="仿真开始时间，例如 00:00:00；为空则由系统自动决定 / "
                 "Simulation start time, e.g. 00:00:00; leave empty for default behaviour."
        )

    with col2:
        qsim['endTime'] = st.text_input(
            "结束时间 / endTime",
            value=qsim.get('endTime', '30:00:00'),
            help="仿真结束时间，建议覆盖到全日（例如 30:00:00）。/ "
                 "Simulation end time, e.g. 30:00:00 to cover full day."
        )

    with col3:
        qsim['timeStepSize'] = st.number_input(
            "时间步长 / timeStepSize (秒)",
            min_value=0.01,
            value=float(qsim.get('timeStepSize', 1.0)),
            help="队列仿真的内部时间步长；数值越小越精细，但计算量越大。/ "
                 "Internal QSim time step in seconds; smaller values give more detail but higher CPU cost."
        )

    # ===== 流量与容量设置 =====
    st.markdown("#### 🚗 流量与容量采样 / Flow & Storage Capacity")

    col1, col2 = st.columns(2)

    with col1:
        qsim['flowCapacityFactor'] = st.number_input(
            "流量容量因子 / flowCapacityFactor",
            min_value=0.0001,
            value=float(qsim.get('flowCapacityFactor', 1.0)),
            help="缩放所有 link 的流量容量。0.1 表示 10%% 抽样交通流。/ "
                 "Scales link flow capacities globally. 0.1 means 10% sampled traffic."
        )

    with col2:
        qsim['storageCapacityFactor'] = st.number_input(
            "存储容量因子 / storageCapacityFactor",
            min_value=0.0001,
            value=float(qsim.get('storageCapacityFactor', 1.0)),
            help="缩放队列长度上限。通常与 flowCapacityFactor 一致。/ "
                 "Scales queue storage capacity; typically same as flowCapacityFactor."
        )

    st.markdown("**快速设置采样率 / Quick presets:**")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("100% 全量"):
            qsim['flowCapacityFactor'] = 1.0
            qsim['storageCapacityFactor'] = 1.0
            st.rerun()
    with col2:
        if st.button("25% 采样"):
            qsim['flowCapacityFactor'] = 0.25
            qsim['storageCapacityFactor'] = 0.25
            st.rerun()
    with col3:
        if st.button("10% 采样"):
            qsim['flowCapacityFactor'] = 0.1
            qsim['storageCapacityFactor'] = 0.1
            st.rerun()
    with col4:
        if st.button("3% 采样"):
            qsim['flowCapacityFactor'] = 0.03
            qsim['storageCapacityFactor'] = 0.03
            st.rerun()

    # ===== 卡住行为与线程数 =====
    st.markdown("#### 🧱 卡住行为与线程数 / Stuck Behaviour & Threads")

    col1, col2, col3 = st.columns(3)

    with col1:
        qsim['stuckTime'] = st.number_input(
            "卡住时间阈值 / stuckTime (秒)",
            min_value=1.0,
            value=float(qsim.get('stuckTime', 10.0)),
            help="前车超过该等待时间仍不移动则视为 `stuck`。/ "
                 "Front-most vehicle not moving for this many seconds is considered stuck."
        )

    with col2:
        qsim['removeStuckVehicles'] = st.checkbox(
            "移除卡住车辆 / removeStuckVehicles",
            value=bool(qsim.get('removeStuckVehicles', False)),
            help="若勾选，卡住车辆将被移出仿真，避免死锁。/ "
                 "If checked, stuck vehicles are removed from simulation to avoid deadlocks."
        )

    with col3:
        qsim['notifyAboutStuckVehicles'] = st.checkbox(
            "输出卡住事件 / notifyAboutStuckVehicles",
            value=bool(qsim.get('notifyAboutStuckVehicles', False)),
            help="若勾选，当车辆卡住时会输出 PersonStuck 事件，便于诊断。/ "
                 "If checked, PersonStuck events are emitted for diagnostics."
        )

    qsim['numberOfThreads'] = st.number_input(
        "QSim 线程数 / numberOfThreads",
        min_value=1,
        value=int(qsim.get('numberOfThreads', 4)),
        help="队列仿真内部使用的线程数，通常与CPU核心数接近。/ "
             "Number of QSim worker threads, usually close to CPU core count."
    )

    # ===== 高级设置 =====
    with st.expander("⚙️ 高级 QSim 设置 / Advanced QSim Settings", expanded=False):

        st.markdown("##### ⛓️ 交通动力学 / Traffic Dynamics")

        col1, col2, col3 = st.columns(3)
        with col1:
            qsim['trafficDynamics'] = st.selectbox(
                "trafficDynamics",
                options=["queue", "withHoles", "kinematicWaves"],
                index=["queue", "withHoles", "kinematicWaves"].index(
                    qsim.get('trafficDynamics', 'queue')),
                help="选择交通动力学模型：queue（经典队列）、withHoles（已废弃）、kinematicWaves（波动模型）。/ "
                     "Select traffic dynamics model: queue, withHoles (deprecated), or kinematicWaves."
            )

        with col2:
            qsim['linkDynamics'] = st.selectbox(
                "linkDynamics",
                options=["FIFO", "PassingQ", "SeepageQ"],
                index=["FIFO", "PassingQ", "SeepageQ"].index(
                    qsim.get('linkDynamics', 'FIFO')),
                help="link 上的车辆出入顺序逻辑，决定是否允许超车以及渗流行为。/ "
                     "Controls vehicle ordering on links (FIFO vs. passing vs. seepage)."
            )

        with col3:
            qsim['vehicleBehavior'] = st.selectbox(
                "vehicleBehavior",
                options=["teleport", "wait", "exception"],
                index=["teleport", "wait", "exception"].index(
                    qsim.get('vehicleBehavior', 'teleport')),
                help="当车辆无法继续行驶时的处理方式：传送、等待或抛异常。/ "
                     "Behaviour when vehicles get blocked: teleport, wait, or throw exception."
            )

        st.markdown("##### 🖼 快照输出 / Snapshots")

        col1, col2, col3 = st.columns(3)
        with col1:
            qsim['snapshotPeriod'] = st.number_input(
                "snapshotperiod (秒)",
                min_value=0.0,
                value=float(qsim.get('snapshotPeriod', 0.0)),
                help="快照输出时间步间隔；0 表示不输出中间快照。/ "
                     "Snapshot interval in seconds; 0 disables intermediate snapshots."
            )
        with col2:
            qsim['snapshotStyle'] = st.selectbox(
                "snapshotStyle",
                options=["equiDist", "queue", "withHoles", "withHolesAndShowHoles", "kinematicWaves"],
                index=["equiDist", "queue", "withHoles", "withHolesAndShowHoles", "kinematicWaves"].index(
                    qsim.get('snapshotStyle', 'queue')),
                help="快照中车辆的显示风格。/ "
                     "Style of snapshots for visualization."
            )
        with col3:
            qsim['filterSnapshots'] = st.selectbox(
                "filterSnapshots",
                options=["no", "withLinkAttributes"],
                index=["no", "withLinkAttributes"].index(
                    qsim.get('filterSnapshots', 'no')),
                help="是否对 snapshot 按 link 属性过滤。/ "
                     "Whether to filter snapshots by link attributes."
            )

        qsim['nodeOffset'] = st.number_input(
            "nodeOffset",
            value=float(qsim.get('nodeOffset', 0.0)),
            help="控制可视化中节点位置偏移。/ "
                 "Controls node offset in visualizations."
        )

        st.markdown("##### ⏱ 时间解释与 ID 设置 / Time Interpretation & IDs")

        col1, col2, col3 = st.columns(3)
        with col1:
            qsim['simStarttimeInterpretation'] = st.selectbox(
                "simStarttimeInterpretation",
                options=["maxOfStarttimeAndEarliestActivityEnd", "onlyUseStarttime"],
                index=["maxOfStarttimeAndEarliestActivityEnd", "onlyUseStarttime"].index(
                    qsim.get('simStarttimeInterpretation', 'maxOfStarttimeAndEarliestActivityEnd')),
                help="如何解释 startTime：与活动结束时间取最大，或仅用 startTime。/ "
                     "Interpretation of startTime: max with earliest activity end or only use startTime."
            )
        with col2:
            qsim['simEndtimeInterpretation'] = st.selectbox(
                "simEndtimeInterpretation",
                options=["minOfEndtimeAndMobsimFinished", "onlyUseEndtime"],
                index=["minOfEndtimeAndMobsimFinished", "onlyUseEndtime"].index(
                    qsim.get('simEndtimeInterpretation', 'minOfEndtimeAndMobsimFinished')),
                help="如何解释 endTime：与 mobsim 完成时刻取最小，或仅用 endTime。/ "
                     "Interpretation of endTime: min with mobsim finish or only use endTime."
            )
        with col3:
            qsim['usePersonIdForMissingVehicleId'] = st.checkbox(
                "usePersonIdForMissingVehicleId",
                value=bool(qsim.get('usePersonIdForMissingVehicleId', True)),
                help="车辆缺少ID时是否用 personId 替代。/ "
                     "Use personId as fallback if vehicleId is missing."
            )

        st.markdown("##### 🚲 渗流与车道 / Seepage & Lanes")

        col1, col2, col3 = st.columns(3)
        with col1:
            qsim['seepMode'] = st.text_input(
                "seepMode",
                value=qsim.get('seepMode', 'bike'),
                help="渗流模式名称，默认 bike。可扩展为 bike,ebike 等。/ "
                     "Name of seepage mode(s), default bike."
            )
        with col2:
            qsim['isSeepModeStorageFree'] = st.checkbox(
                "isSeepModeStorageFree",
                value=bool(qsim.get('isSeepModeStorageFree', True)),
                help="渗流模式车辆是否不占用存储容量。/ "
                     "Whether seepage-mode vehicles consume storage capacity."
            )
        with col3:
            qsim['isRestrictingSeepage'] = st.checkbox(
                "isRestrictingSeepage",
                value=bool(qsim.get('isRestrictingSeepage', True)),
                help="是否对渗流行为施加约束。/ "
                     "Whether to restrict seepage behaviour."
            )

        st.markdown("##### 🚗 车辆来源与车道 / Vehicles & Lanes")

        col1, col2, col3 = st.columns(3)
        with col1:
            qsim['vehiclesSource'] = st.selectbox(
                "vehiclesSource",
                options=["defaultVehicle", "modeVehicleTypesFromVehiclesData", "fromVehiclesData"],
                index=["defaultVehicle", "modeVehicleTypesFromVehiclesData", "fromVehiclesData"].index(
                    qsim.get('vehiclesSource', 'defaultVehicle')),
                help="车辆类型来源：默认、按mode映射、或直接使用 vehicles.xml。/ "
                     "Source of vehicle types: default, mode-based, or explicit vehicles data."
            )
        with col2:
            qsim['useLanes'] = st.checkbox(
                "useLanes",
                value=bool(qsim.get('useLanes', False)),
                help="是否启用车道级仿真（需要提供 laneDefinitionsFile）。/ "
                     "Enable lane-based simulation (requires laneDefinitionsFile)."
            )
        with col3:
            qsim['insertingWaitingVehiclesBeforeDrivingVehicles'] = st.checkbox(
                "insertingWaitingVehiclesBeforeDrivingVehicles",
                value=bool(qsim.get('insertingWaitingVehiclesBeforeDrivingVehicles', True)),
                help="等待进入网络的车辆是否在已行驶车辆之前插入。/ "
                     "Insert waiting vehicles before already driving ones."
            )

    st.session_state.qsim_config = qsim

def render_hermes_configuration():
    """渲染 Hermes 配置（仅当 mobsim = hermes 时显示）"""

    if st.session_state.controller_config['mobsim'] != 'hermes':
        st.info(f"当前仿真内核为 {st.session_state.controller_config['mobsim']}，仅在选择 Hermes 时显示此页面。")
        return

    hermes = st.session_state.hermes_config

    st.markdown('<div class="module-header">🧬 Hermes 超大规模仿真配置 / Hermes Settings</div>',
                unsafe_allow_html=True)

    st.markdown("""
    <div class="info-box">
    <b>模块说明 / Description</b><br>
    • Hermes 是为超大规模场景设计的仿真内核。<br>
    • 参数与 QSim 类似，但内部实现不同，更适合大规模并行。<br><br>
    <b>使用建议 / Tips</b><br>
    • 一般仅需设置 endTime 与容量采样率，其它保持默认。<br>
    • Hermes 推荐搭配 EventsManager.oneThreadPerHandler = true 使用。<br>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### ⏰ 时间与容量 / Time & Capacity")

    col1, col2, col3 = st.columns(3)

    with col1:
        hermes['endTime'] = st.text_input(
            "结束时间 / endTime",
            value=hermes.get('endTime', '30:00:00'),
            help="Hermes 仿真结束时间，控制 SIM_STEPS。/ "
                 "Hermes simulation end time, controlling SIM_STEPS."
        )

    with col2:
        hermes['flowCapacityFactor'] = st.number_input(
            "流量容量因子 / flowCapacityFactor",
            min_value=0.0001,
            value=float(hermes.get('flowCapacityFactor', 1.0)),
            help="缩放流量容量；与 QSim 的 flowCapacityFactor 含义一致。/ "
                 "Scales flow capacity; same meaning as in QSim."
        )

    with col3:
        hermes['storageCapacityFactor'] = st.number_input(
            "存储容量因子 / storageCapacityFactor",
            min_value=0.0001,
            value=float(hermes.get('storageCapacityFactor', 1.0)),
            help="缩放排队存储容量；与 QSim 的 storageCapacityFactor 含义一致。/ "
                 "Scales storage capacity; same meaning as in QSim."
        )

    st.markdown("#### 🧱 卡住行为 / Stuck Behaviour")

    hermes['stuckTime'] = st.number_input(
        "卡住时间阈值 / stuckTime (秒)",
        min_value=1,
        value=int(hermes.get('stuckTime', 10)),
        help="前车在 link 上等待超过该时间仍不移动则视为 stuck。/ "
             "Front-most vehicle not moving for this many seconds is considered stuck."
    )

    st.markdown("#### 🚌 公交仿真模式 / Public Transport Mode")

    hermes['useDeterministicPt'] = st.checkbox(
        "使用确定性 PT / useDeterministicPt",
        value=bool(hermes.get('useDeterministicPt', False)),
        help="若勾选，PT 车辆将以更稳定的方式运行，尤其适用于多层网络。/ "
             "If checked, PT vehicles will run in a more deterministic, stable fashion."
    )

    st.markdown("""
    <small>
    mainMode 参数将自动根据“出行模式”中勾选的网络模式生成，通常不需要单独修改。<br>
    / The <b>mainMode</b> parameter is automatically set from the network modes defined in the modes step.
    </small>
    """, unsafe_allow_html=True)

    st.session_state.hermes_config = hermes


def render_replanning_configuration():
    """渲染重规划配置"""

    st.markdown('<div class="module-header">🔄 重规划策略配置 / Replanning Settings</div>',
                unsafe_allow_html=True)

    with st.expander("📖 重规划策略说明", expanded=False):
        st.markdown("""
        **策略类型：**
        - **选择策略**（BestScore等）：从现有计划中选择，不生成新计划
        - **创新策略**（ReRoute等）：生成新的计划变体

        **重要提示：**
        - 创新策略应在后期迭代中禁用以确保收敛
        - 权重会被自动归一化
        """)

    # 基本参数
    st.markdown("#### 📋 基本参数")

    col1, col2 = st.columns(2)

    with col1:
        st.session_state.replanning_config['maxAgentPlanMemorySize'] = st.number_input(
            "最大计划记忆数",
            min_value=1,
            max_value=10,
            value=st.session_state.replanning_config['maxAgentPlanMemorySize'],
            help="每个Agent保留的最大计划数量"
        )

    with col2:
        st.session_state.replanning_config['fractionOfIterationsToDisableInnovation'] = st.number_input(
            "禁用创新比例",
            min_value=0.0,
            max_value=1.0,
            value=st.session_state.replanning_config['fractionOfIterationsToDisableInnovation'],
            step=0.05,
            help="在此比例迭代后禁用创新策略"
        )

    # 计算禁用迭代
    last_iter = st.session_state.controller_config['lastIteration']
    disable_fraction = st.session_state.replanning_config['fractionOfIterationsToDisableInnovation']
    disable_iter = int(last_iter * disable_fraction)

    st.info(f"ℹ️ 创新策略将在第 {disable_iter} 轮后禁用（共 {last_iter} 轮）")

    # 策略配置
    st.markdown("#### 🎯 策略配置")

    # 可用策略
    available_strategies = {
        'BestScore': ('选择最佳', '选择', '选择得分最高的计划'),
        'SelectExpBeta': ('指数选择', '选择', '按概率选择计划'),
        'ReRoute': ('重新路由', '创新', '重新计算最优路径'),
        'TimeAllocationMutator': ('时间变异', '创新', '随机调整活动时间'),
        'SubtourModeChoice': ('子路程模式', '创新', '改变子路程出行方式'),
    }

    # 显示当前策略
    total_weight = sum(s['weight'] for s in st.session_state.strategy_config)

    for i, strategy in enumerate(st.session_state.strategy_config):
        info = available_strategies.get(strategy['name'], (strategy['name'], '未知', ''))
        type_badge = "🎯" if info[1] == '选择' else "💡"

        col1, col2, col3 = st.columns([3, 2, 1])

        with col1:
            st.markdown(f"{type_badge} **{info[0]}** ({strategy['name']})")
            st.caption(info[2])

        with col2:
            strategy['weight'] = st.number_input(
                "权重",
                min_value=0.0,
                max_value=1.0,
                value=strategy['weight'],
                step=0.05,
                key=f"strat_weight_{i}",
                label_visibility="collapsed"
            )

        with col3:
            pct = (strategy['weight'] / total_weight * 100) if total_weight > 0 else 0
            st.metric("占比", f"{pct:.0f}%")

    # 快速预设
    st.markdown("---")
    st.markdown("**快速预设：**")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📋 标准配置"):
            st.session_state.strategy_config = [
                {'name': 'BestScore', 'weight': 0.6},
                {'name': 'ReRoute', 'weight': 0.2},
                {'name': 'TimeAllocationMutator', 'weight': 0.1},
                {'name': 'SubtourModeChoice', 'weight': 0.1},
            ]
            st.rerun()

    with col2:
        if st.button("🔍 充分探索"):
            st.session_state.strategy_config = [
                {'name': 'SelectExpBeta', 'weight': 0.4},
                {'name': 'ReRoute', 'weight': 0.25},
                {'name': 'TimeAllocationMutator', 'weight': 0.15},
                {'name': 'SubtourModeChoice', 'weight': 0.2},
            ]
            st.rerun()

    with col3:
        if st.button("⚡ 快速收敛"):
            st.session_state.strategy_config = [
                {'name': 'BestScore', 'weight': 0.8},
                {'name': 'ReRoute', 'weight': 0.1},
                {'name': 'SubtourModeChoice', 'weight': 0.1},
            ]
            st.rerun()
    # ========== changeMode 模块配置 ==========
    st.markdown("---")
    st.markdown("#### 🔁 出行方式变更模块 / changeMode Module")

    cm = st.session_state.changemode_config
    all_modes_for_change = ModeManager.get_choosable_modes()

    st.markdown("""
    changeMode 模块用于在重规划时**更改出行方式**，与策略 `ChangeExpBeta` 等一起使用时生效。

    - `modes`：允许参与 mode change 的出行方式集合
    - `ignoreCarAvailability`：是否忽略小汽车可用性（无车也可以被改成 car）
    - `modeSwitchBehavior`：模式切换的来源/目标范围
    """)

    # 1) modes 来源选择
    cm['use_subtour_modes'] = st.radio(
        "模式来源 / Modes source",
        options=[True, False],
        index=0 if cm.get('use_subtour_modes', True) else 1,
        format_func=lambda x: "跟随 subtourModeChoice.modes / follow subtourModeChoice.modes"
        if x else "自定义模式列表 / use custom mode list",
        horizontal=False
    )

    if cm['use_subtour_modes']:
        st.info(
            "当前将使用 **subtourModeChoice.modes** 作为 changeMode 的 `modes` 参数：\n\n"
            f"`{', '.join(all_modes_for_change) if all_modes_for_change else '(当前为空)'}`"
        )
    else:
        # 允许自定义模式列表，从所有可选模式中选择
        available_modes = sorted(list(set(all_modes_for_change)))
        cm['custom_modes'] = st.multiselect(
            "自定义可切换模式 / Custom changeable modes (changeMode.modes)",
            options=available_modes,
            default=cm.get('custom_modes', available_modes),
            help="选择哪些出行方式可以被改变 / which travel modes can be changed"
        )

    # 2) ignoreCarAvailability
    cm['ignoreCarAvailability'] = st.checkbox(
        "忽略小汽车可用性 / ignoreCarAvailability",
        value=cm.get('ignoreCarAvailability', True),
        help=create_help_text(
            "若勾选，即使 Agent 没有车/驾照也可以被改成 car 模式。",
            "If checked, agents can be switched to 'car' even if they have no car/license."
        )
    )

    # 3) modeSwitchBehavior
    cm['modeSwitchBehavior'] = st.selectbox(
        "模式切换行为 / modeSwitchBehavior",
        options=list(CHANGEMODE_BEHAVIOR_OPTIONS.keys()),
        format_func=lambda x: CHANGEMODE_BEHAVIOR_OPTIONS[x],
        index=list(CHANGEMODE_BEHAVIOR_OPTIONS.keys()).index(
            cm.get('modeSwitchBehavior', 'fromSpecifiedModesToSpecifiedModes')
        ),
        help=create_help_text(
            "fromSpecifiedModesToSpecifiedModes：仅当当前模式在 modes 中时才参与切换，目标模式也在 modes 中。\n"
            "fromAllModesToSpecifiedModes：所有当前模式都可以切换到 modes 中任一目标模式。",
            "fromSpecifiedModesToSpecifiedModes: only legs whose current mode is in 'modes' are changed, "
            "and target modes are also restricted to 'modes'.\n"
            "fromAllModesToSpecifiedModes: legs of all current modes may be changed to any of the modes in 'modes'."
        )
    )

    st.session_state.changemode_config = cm


# ============================================================
# planInheritance 模块配置 / PlanInheritance Configuration
# ============================================================
def render_planinheritance_configuration():
    """渲染 planInheritance 模块配置（PlanInheritanceConfigGroup）"""

    st.markdown('<div class="module-header">🧬 计划继承配置 / PlanInheritance Settings</div>',
                unsafe_allow_html=True)

    pi_cfg = st.session_state.planinheritance_config

    st.markdown("""
    <div class="info-box">
    <b>模块说明 / Description</b><br>
    • 控制是否跟踪和记录计划的继承信息（哪个计划是从哪个计划变异而来）。<br>
    • 主要用于分析和调试重规划过程。<br><br>
    <b>使用建议 / Tips</b><br>
    • 一般情况下保持关闭，仅在需要分析计划演化时启用。<br>
    • 启用后会增加内存占用和输出文件大小。<br>
    </div>
    """, unsafe_allow_html=True)

    pi_cfg['enabled'] = st.checkbox(
        create_param_label("启用计划继承跟踪 / enabled",
                           "Enable plan inheritance tracking (config.planInheritance.enabled)"),
        value=bool(pi_cfg.get('enabled', False)),
        help=create_help_text(
            "勾选后，MATSim 会记录每个计划是通过哪个策略从哪个父计划生成的。",
            "If checked, MATSim tracks which plan was generated from which parent plan using which strategy."
        )
    )

    st.session_state.planinheritance_config = pi_cfg


# ============================================================
# plans 模块配置（独立配置页） / Plans Configuration
# ============================================================
def render_plans_configuration():
    """渲染 plans 模块配置（PlansConfigGroup 的高级参数）"""

    st.markdown('<div class="module-header">📋 Plans 模块配置 / Plans Module Settings</div>',
                unsafe_allow_html=True)

    plans_cfg = st.session_state.plans_config

    st.markdown("""
    <div class="info-box">
    <b>模块说明 / Description</b><br>
    • 控制人口计划的读取、存储和处理方式。<br>
    • 输入文件路径在「输入文件配置」步骤中配置，此处配置行为参数。<br><br>
    <b>使用建议 / Tips</b><br>
    • 大部分参数保持默认即可。<br>
    • 路由压缩类型影响内存占用，大规模场景建议使用压缩路由。<br>
    </div>
    """, unsafe_allow_html=True)

    # ===== 1. 路由存储类型 =====
    st.markdown("#### 🗺️ 路由存储类型 / Network Route Type")

    route_type_options = {
        'LinkNetworkRoute': 'LinkNetworkRoute - 完整链路列表（无压缩，内存占用大）',
        'MediumCompressedNetworkRoute': 'MediumCompressedNetworkRoute - 中度压缩（平衡性能与内存）',
        'HeavyCompressedNetworkRoute': 'HeavyCompressedNetworkRoute - 高度压缩（节省内存，稍慢）'
    }

    plans_cfg['networkRouteType'] = st.selectbox(
        create_param_label("networkRouteType", "Network Route Type (config.plans.networkRouteType)"),
        options=list(route_type_options.keys()),
        index=list(route_type_options.keys()).index(plans_cfg.get('networkRouteType', 'LinkNetworkRoute')),
        format_func=lambda x: route_type_options[x],
        help=create_help_text(
            "定义路由在内存中的存储方式。LinkNetworkRoute 存储完整链路序列；压缩路由只存储关键节点，可节省内存。",
            "Defines how routes are stored in memory. LinkNetworkRoute stores full link sequences; "
            "compressed routes store only key nodes to save memory."
        )
    )

    # ===== 2. 活动与出行时间处理 =====
    st.markdown("---")
    st.markdown("#### ⏱️ 活动与出行时间处理 / Activity & Trip Duration Handling")

    col1, col2 = st.columns(2)

    with col1:
        activity_duration_options = {
            'minOfDurationAndEndTime': 'minOfDurationAndEndTime - 取最小值（推荐）',
            'tryEndTimeThenDuration': 'tryEndTimeThenDuration - 优先结束时间',
        }

        plans_cfg['activityDurationInterpretation'] = st.selectbox(
            create_param_label("活动时长解释 / activityDurationInterpretation",
                               "Activity Duration Interpretation (config.plans.activityDurationInterpretation)"),
            options=list(activity_duration_options.keys()),
            index=list(activity_duration_options.keys()).index(
                plans_cfg.get('activityDurationInterpretation', 'tryEndTimeThenDuration')
            ),
            format_func=lambda x: activity_duration_options[x],
            help=create_help_text(
                "当活动同时设置了 typicalDuration 和 endTime 时如何解释。"
                "minOfDurationAndEndTime 对应完整的 TimeAllocationMutator；"
                "tryEndTimeThenDuration 使用简化版本。",
                "How to interpret activities when both typicalDuration and endTime are set. "
                "minOfDurationAndEndTime uses the full TimeAllocationMutator; "
                "tryEndTimeThenDuration uses a simplified version."
            )
        )

    with col2:
        trip_duration_options = {
            'ignoreDelays': 'ignoreDelays - 忽略延迟（经典行为）',
            'shiftActivityEndTimes': 'shiftActivityEndTimes - 累积旅行时间并移动活动'
        }

        plans_cfg['tripDurationHandling'] = st.selectbox(
            create_param_label("出行时长处理 / tripDurationHandling",
                               "Trip Duration Handling (config.plans.tripDurationHandling)"),
            options=list(trip_duration_options.keys()),
            index=list(trip_duration_options.keys()).index(
                plans_cfg.get('tripDurationHandling', 'ignoreDelays')
            ),
            format_func=lambda x: trip_duration_options[x],
            help=create_help_text(
                "定义在沿计划路由时如何解释出发时间。"
                "ignoreDelays：始终使用活动的名义结束时间作为出发时间；"
                "shiftActivityEndTimes：累积旅行时间，必要时推迟后续活动。",
                "Defines how departure times are interpreted when routing along a plan. "
                "ignoreDelays: always use nominal activity end time; "
                "shiftActivityEndTimes: accumulate travel times and shift activities if necessary."
            )
        )

    # ===== 3. 坐标系与属性 =====
    st.markdown("---")
    st.markdown("#### 🌐 坐标系与属性处理 / CRS & Attributes")

    col1, col2 = st.columns(2)

    with col1:
        plans_cfg['inputCRS'] = st.text_input(
            create_param_label("输入坐标系 / inputCRS",
                               "Input CRS (config.plans.inputCRS)"),
            value=plans_cfg.get('inputCRS', ''),
            help=create_help_text(
                "Plans 文件中坐标的坐标系。导入时会转换到 global.coordinateSystem，导出时转回。"
                "留空表示不进行转换。",
                "The CRS in which coordinates are expressed in the input plans file. "
                "At import, coordinates are converted to global.coordinateSystem. "
                "Leave empty for no conversion."
            )
        )

        plans_cfg['removingUnnecessaryPlanAttributes'] = st.checkbox(
            create_param_label("移除不必要的计划属性 / removingUnnecessaryPlanAttributes",
                               "Remove Unnecessary Plan Attributes (config.plans.removingUnnecessaryPlanAttributes)"),
            value=bool(plans_cfg.get('removingUnnecessaryPlanAttributes', False)),
            help=create_help_text(
                "（未充分测试）是否移除可能不使用的计划属性，如 activityStartTime。谨慎使用！",
                "(Not tested) Remove plan attributes that are presumably not used. Use with caution!"
            )
        )

    with col2:
        routing_mode_options = {
            'reject': 'reject - 拒绝没有路由模式的计划',
            'useMainModeIdentifier': 'useMainModeIdentifier - 使用主模式标识符'
        }

        plans_cfg['handlingOfPlansWithoutRoutingMode'] = st.selectbox(
            create_param_label("处理无路由模式的计划 / handlingOfPlansWithoutRoutingMode",
                               "Handling of Plans Without Routing Mode"),
            options=list(routing_mode_options.keys()),
            index=list(routing_mode_options.keys()).index(
                plans_cfg.get('handlingOfPlansWithoutRoutingMode', 'reject')
            ),
            format_func=lambda x: routing_mode_options[x],
            help=create_help_text(
                "当计划中的出行没有 routingMode 时如何处理。",
                "How to handle trips without routingMode attribute in plans."
            )
        )

    # ===== 4. 已废弃的人口属性文件 =====
    st.markdown("---")
    st.markdown("#### ⚠️ 已废弃的人口属性文件 / Deprecated Person Attributes File")

    st.markdown("""
    <div class="warning-box">
    <b>废弃警告 / Deprecation Warning</b><br>
    使用独立的人口属性文件已被废弃。推荐将属性直接添加到每个 Person 对象的 Attributable 中。
    如果必须使用旧文件，请勾选下方选项并指定文件路径（文件将被读取，但值会被转换为 Attributable 形式）。
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        plans_cfg['insistingOnUsingDeprecatedPersonAttributeFile'] = st.checkbox(
            create_param_label(
                "坚持使用已废弃的属性文件 / insistingOnUsingDeprecatedPersonAttributeFile",
                "Insist on Using Deprecated Person Attribute File"
            ),
            value=bool(plans_cfg.get('insistingOnUsingDeprecatedPersonAttributeFile', False)),
            help=create_help_text(
                "仅当必须继续使用独立的 personAttributes.xml 文件时才勾选。",
                "Check only if you must continue using a separate personAttributes.xml file."
            )
        )

    with col2:
        if plans_cfg['insistingOnUsingDeprecatedPersonAttributeFile']:
            plans_cfg['inputPersonAttributesFile'] = st.text_input(
                create_param_label("人口属性文件路径 / inputPersonAttributesFile",
                                   "Person Attributes File Path (deprecated)"),
                value=plans_cfg.get('inputPersonAttributesFile', ''),
                help="独立的人口属性文件路径（ObjectAttributes 格式）"
            )
        else:
            plans_cfg['inputPersonAttributesFile'] = ''
            st.caption("💡 未启用废弃属性文件")

    st.session_state.plans_config = plans_cfg


# ============================================================
# ptCounts 模块配置 / PtCounts Configuration
# ============================================================
def render_ptcounts_configuration():
    """渲染 ptCounts 模块配置（PtCountsConfigGroup）"""

    st.markdown('<div class="module-header">🚌📊 公交计数评估配置 / PT Counts Settings</div>',
                unsafe_allow_html=True)

    ptc_cfg = st.session_state.ptcounts_config

    st.markdown("""
    <div class="info-box">
    <b>模块说明 / Description</b><br>
    • 用于将仿真的公交客流与实测计数数据进行对比验证。<br>
    • 支持三种计数类型：占用计数（occupancy）、上车计数（board）、下车计数（alight）。<br><br>
    <b>使用建议 / Tips</b><br>
    • 至少需要配置一种计数文件才能启用此模块。<br>
    • countsScaleFactor 应设置为人口采样率的倒数（如 10% 采样 → 10.0）。<br>
    </div>
    """, unsafe_allow_html=True)

    # ===== 1. 输入文件 =====
    st.markdown("#### 📁 PT 计数输入文件 / PT Counts Input Files")

    st.markdown("上传或指定至少一种 PT 计数文件：")

    col1, col2, col3 = st.columns(3)

    with col1:
        occupancy_file = render_file_upload(
            "占用计数文件 / Occupancy Counts",
            "Occupancy Counts File (config.ptCounts.inputOccupancyCountsFile)",
            'ptOccupancyCountsFile',
            required=False,
            help_text="车辆占用人数的实测数据"
        )
        ptc_cfg['inputOccupancyCountsFile'] = occupancy_file or ''

    with col2:
        board_file = render_file_upload(
            "上车计数文件 / Board Counts",
            "Board Counts File (config.ptCounts.inputBoardCountsFile)",
            'ptBoardCountsFile',
            required=False,
            help_text="乘客上车人数的实测数据"
        )
        ptc_cfg['inputBoardCountsFile'] = board_file or ''

    with col3:
        alight_file = render_file_upload(
            "下车计数文件 / Alight Counts",
            "Alight Counts File (config.ptCounts.inputAlightCountsFile)",
            'ptAlightCountsFile',
            required=False,
            help_text="乘客下车人数的实测数据"
        )
        ptc_cfg['inputAlightCountsFile'] = alight_file or ''

    has_any_file = bool(occupancy_file or board_file or alight_file)

    if not has_any_file:
        st.warning("⚠️ 未配置任何 PT 计数文件，此模块将不会生效。")
    else:
        st.success(f"✅ 已配置 PT 计数文件")

    # ===== 2. 输出与采样设置 =====
    st.markdown("---")
    st.markdown("#### 📤 输出与采样设置 / Output & Sampling Settings")

    col1, col2, col3 = st.columns(3)

    with col1:
        output_format_options = {
            'txt': 'txt - 纯文本报告',
            'html': 'html - HTML 图文报告',
            'all': 'all - 同时输出 txt 和 html'
        }

        ptc_cfg['outputformat'] = st.selectbox(
            create_param_label("输出格式 / outputformat",
                               "Output Format (config.ptCounts.outputformat)"),
            options=list(output_format_options.keys()),
            index=list(output_format_options.keys()).index(ptc_cfg.get('outputformat', 'txt')),
            format_func=lambda x: output_format_options[x],
            help="PT 计数对比报告的输出格式"
        )

    with col2:
        ptc_cfg['countsScaleFactor'] = st.number_input(
            create_param_label("计数缩放因子 / countsScaleFactor",
                               "Counts Scale Factor (config.ptCounts.countsScaleFactor)"),
            min_value=0.0,
            value=float(ptc_cfg.get('countsScaleFactor', 1.0)),
            step=0.1,
            help=create_help_text(
                "用于按人口采样率缩放仿真流量，例如 10% 采样 → 10.0。",
                "Scale simulated flows according to population sampling rate, e.g. 10% sample → 10.0."
            )
        )

        st.caption("示例：100%→1.0，10%→10.0，5%→20.0")

    with col3:
        ptc_cfg['ptCountsInterval'] = st.number_input(
            create_param_label("PT 计数间隔 / ptCountsInterval",
                               "PT Counts Interval (config.ptCounts.ptCountsInterval)"),
            min_value=1,
            value=int(ptc_cfg.get('ptCountsInterval', 10)),
            help=create_help_text(
                "每隔多少个迭代输出一次 PT 计数对比结果（从迭代 0 开始）。",
                "Generate PT counts comparisons every N iterations (starting with iteration 0)."
            )
        )

    # ===== 3. 距离过滤 =====
    st.markdown("---")
    st.markdown("#### 📍 距离过滤 / Distance Filter")

    distance_enabled_default = ptc_cfg.get('distanceFilter') is not None \
                               or bool(ptc_cfg.get('distanceFilterCenterNode'))

    distance_enabled = st.checkbox(
        create_param_label("启用距离过滤", "Enable Distance Filter"),
        value=distance_enabled_default,
        help=create_help_text(
            "只保留距某个中心节点一定半径内的 PT 计数站点。",
            "Keep only PT count stations within a radius around a specified center node."
        )
    )

    if distance_enabled:
        col1, col2 = st.columns(2)

        with col1:
            ptc_cfg['distanceFilter'] = st.number_input(
                create_param_label("过滤半径 (米) / distanceFilter",
                                   "Radius in meters (config.ptCounts.distanceFilter)"),
                min_value=0.0,
                value=float(ptc_cfg.get('distanceFilter') or 20000.0),
                step=1000.0,
                help="以路网坐标系单位（通常为米）表示的过滤半径"
            )

        with col2:
            ptc_cfg['distanceFilterCenterNode'] = st.text_input(
                create_param_label("中心节点 ID / distanceFilterCenterNode",
                                   "Center Node ID (config.ptCounts.distanceFilterCenterNode)"),
                value=ptc_cfg.get('distanceFilterCenterNode', ''),
                help="作为过滤中心的路网节点 ID，必须存在于 network 中"
            )
    else:
        ptc_cfg['distanceFilter'] = None
        ptc_cfg['distanceFilterCenterNode'] = ''

    st.session_state.ptcounts_config = ptc_cfg


# ============================================================
# 扩展 replanning 配置（补充缺失参数）
# ============================================================
def render_replanning_configuration_extended():
    """
    扩展版的 replanning 配置渲染函数
    完全基于 MATSim 源码，支持所有策略的自定义配置
    """

    st.markdown('<div class="module-header">🔄 重规划策略配置 / Replanning Settings</div>',
                unsafe_allow_html=True)

    with st.expander("📖 重规划策略说明", expanded=False):
        st.markdown("""
        ### 策略类型

        **A. 选择器 (Selectors)**
        - 从现有计划中选择一个
        - **不生成新计划**
        - 不受创新禁用设置影响
        - 示例：BestScore, SelectExpBeta

        **B. 创新策略 (Mutators)**
        - 修改现有计划生成新变体
        - **生成新计划**
        - 可在后期迭代中禁用
        - 示例：ReRoute, TimeAllocationMutator, SubtourModeChoice

        ### 重要规则

        1. **权重总和必须等于 1.0**（不会自动归一化）
        2. 至少需要一个选择器策略
        3. 创新策略在达到 `fractionOfIterationsToDisableInnovation` 后自动禁用
        4. 某些策略需要配置相应模块（如 TimeAllocationMutator 需要配置 timeAllocationMutator 模块）
        """)

    # ===== 初始化策略配置 =====
    # 确保策略配置存在且有效
    if 'strategy_config' not in st.session_state:
        st.session_state.strategy_config = []

    # 确保是列表类型
    if not isinstance(st.session_state.strategy_config, list):
        st.session_state.strategy_config = []

    # 如果为空，提供默认配置选项
    if len(st.session_state.strategy_config) == 0:
        st.info("ℹ️ 当前没有配置任何策略。请添加策略或使用快速预设。")

    # ===== 基本参数 =====
    st.markdown("#### 📋 基本参数 / Basic Parameters")

    col1, col2 = st.columns(2)

    with col1:
        st.session_state.replanning_config['maxAgentPlanMemorySize'] = st.number_input(
            create_param_label("最大计划记忆数 / maxAgentPlanMemorySize",
                               "Max Agent Plan Memory Size (config.replanning.maxAgentPlanMemorySize)"),
            min_value=1,
            max_value=10,
            value=st.session_state.replanning_config.get('maxAgentPlanMemorySize', 5),
            help=create_help_text(
                "每个 Agent 保留的最大计划数量。0 表示无限制。通常 5 是一个好的值。",
                "Maximum number of plans per agent. 0 means infinity. Currently, 5 is a good number."
            )
        )

    with col2:
        st.session_state.replanning_config['fractionOfIterationsToDisableInnovation'] = st.number_input(
            create_param_label("禁用创新比例 / fractionOfIterationsToDisableInnovation",
                               "Fraction of Iterations to Disable Innovation"),
            min_value=0.0,
            max_value=1.0,
            value=st.session_state.replanning_config.get('fractionOfIterationsToDisableInnovation', 0.8),
            step=0.05,
            help=create_help_text(
                "在此比例迭代后禁用创新策略。例如 0.8 表示在最后 20% 迭代中禁用创新。",
                "Fraction of iterations where innovative strategies are switched off. E.g., 0.8 means "
                "innovation is disabled in the last 20% of iterations."
            )
        )

    # 计算禁用迭代
    last_iter = st.session_state.controller_config.get('lastIteration', 100)
    disable_fraction = st.session_state.replanning_config['fractionOfIterationsToDisableInnovation']
    disable_iter = int(last_iter * disable_fraction)

    st.info(f"ℹ️ 创新策略将在第 {disable_iter} 轮后禁用（共 {last_iter} 轮）")

    # ===== 计划移除选择器 =====
    st.markdown("---")
    st.markdown("#### 🗑️ 计划移除策略 / Plan Selector for Removal")

    plan_removal_options = {
        'WorstPlanSelector': 'WorstPlanSelector - 移除得分最低的计划（默认）',
        'WorstPlanForRemovalSelector': 'WorstPlanForRemovalSelector - 改进的最差计划选择器',
        'SelectExpBetaForRemoval': 'SelectExpBetaForRemoval - 指数概率移除',
        'ChangeExpBetaForRemoval': 'ChangeExpBetaForRemoval - 变更指数概率移除',
        'PathSizeLogitSelectorForRemoval': 'PathSizeLogitSelectorForRemoval - 路径大小 Logit 移除'
    }

    st.session_state.replanning_config['planSelectorForRemoval'] = st.selectbox(
        create_param_label("计划移除选择器 / planSelectorForRemoval",
                           "Plan Selector for Removal (config.replanning.planSelectorForRemoval)"),
        options=list(plan_removal_options.keys()),
        index=list(plan_removal_options.keys()).index(
            st.session_state.replanning_config.get('planSelectorForRemoval', 'WorstPlanSelector')
        ),
        format_func=lambda x: plan_removal_options[x],
        help=create_help_text(
            "当计划数量超过 maxAgentPlanMemorySize 时，使用哪种策略移除计划。",
            "Strategy to select which plan to remove when exceeding maxAgentPlanMemorySize."
        )
    )

    # ===== 快速预设（移到前面，方便快速初始化） =====
    st.markdown("---")
    st.markdown("#### ⚡ 快速预设配置 / Quick Presets")

    st.caption("点击快速应用预设配置，然后可以进一步调整")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("📋 标准配置", use_container_width=True,
                     help="BestScore 60% + ReRoute 20% + TimeAllocationMutator 10% + SubtourModeChoice 10%"):
            st.session_state.strategy_config = [
                {'name': 'BestScore', 'weight': 0.6},
                {'name': 'ReRoute', 'weight': 0.2},
                {'name': 'TimeAllocationMutator', 'weight': 0.1},
                {'name': 'SubtourModeChoice', 'weight': 0.1},
            ]
            st.rerun()

    with col2:
        if st.button("🔍 充分探索", use_container_width=True,
                     help="SelectExpBeta 40% + ReRoute 25% + TimeAllocationMutator 15% + SubtourModeChoice 20%"):
            st.session_state.strategy_config = [
                {'name': 'SelectExpBeta', 'weight': 0.4},
                {'name': 'ReRoute', 'weight': 0.25},
                {'name': 'TimeAllocationMutator', 'weight': 0.15},
                {'name': 'SubtourModeChoice', 'weight': 0.2},
            ]
            st.rerun()

    with col3:
        if st.button("⚡ 快速收敛", use_container_width=True,
                     help="BestScore 80% + ReRoute 15% + TimeAllocationMutator 5%"):
            st.session_state.strategy_config = [
                {'name': 'BestScore', 'weight': 0.8},
                {'name': 'ReRoute', 'weight': 0.15},
                {'name': 'TimeAllocationMutator', 'weight': 0.05},
            ]
            st.rerun()

    with col4:
        if st.button("🔄 仅重路由", use_container_width=True, help="BestScore 70% + ReRoute 30%"):
            st.session_state.strategy_config = [
                {'name': 'BestScore', 'weight': 0.7},
                {'name': 'ReRoute', 'weight': 0.3},
            ]
            st.rerun()

    # ===== 策略配置 =====
    st.markdown("---")
    st.markdown("#### 🎯 策略配置 / Strategy Settings")

    # 获取当前策略列表
    current_strategies = st.session_state.strategy_config

    # ===== 修复：只计算已添加策略的总权重 =====
    total_weight = sum(s.get('weight', 0.0) for s in current_strategies)

    # 权重验证
    weight_valid = abs(total_weight - 1.0) < 0.001  # 允许浮点误差

    # 显示权重状态
    col1, col2, col3 = st.columns(3)

    with col1:
        if weight_valid:
            st.success(f"✅ 权重总和: {total_weight:.4f}")
        else:
            st.error(f"❌ 权重总和: {total_weight:.4f}")

    with col2:
        remaining = 1.0 - total_weight
        if abs(remaining) < 0.001:
            st.info(f"✅ 剩余权重: {remaining:.4f}")
        elif remaining > 0:
            st.warning(f"⚠️ 剩余权重: {remaining:.4f}")
        else:
            st.error(f"❌ 超出权重: {abs(remaining):.4f}")

    with col3:
        strategy_count = len(current_strategies)
        st.metric("策略数量", strategy_count)

    # 显示当前策略
    if current_strategies:
        st.markdown("**当前策略配置：**")

        # 按类型分组显示
        selectors_in_config = []
        mutators_in_config = []

        for i, strategy in enumerate(current_strategies):
            strategy_def = AVAILABLE_STRATEGIES.get(strategy['name'])
            if strategy_def:
                if strategy_def.strategy_type == StrategyType.SELECTOR:
                    selectors_in_config.append((i, strategy))
                else:
                    mutators_in_config.append((i, strategy))

        # 选择器
        if selectors_in_config:
            st.markdown("**🎯 选择器 (Selectors):**")
            for i, strategy in selectors_in_config:
                render_strategy_row(strategy, i, current_strategies)

        # 创新策略
        if mutators_in_config:
            st.markdown("**💡 创新策略 (Mutators):**")
            for i, strategy in mutators_in_config:
                render_strategy_row(strategy, i, current_strategies)
    else:
        st.warning("⚠️ 尚未配置任何策略。请添加策略或使用快速预设。")

    # 添加新策略
    st.markdown("---")
    st.markdown("**➕ 添加新策略：**")

    # 获取可用策略（排除已添加的）
    current_strategy_names = {s['name'] for s in current_strategies}
    available_to_add = {k: v for k, v in get_all_active_strategies().items()
                        if k not in current_strategy_names}

    if not available_to_add:
        st.info("✅ 所有可用策略都已添加")
    else:
        col1, col2, col3, col4 = st.columns([2.5, 1, 1, 0.8])

        with col1:
            # 按类型分组
            selectors = {k: v for k, v in available_to_add.items()
                         if v.strategy_type == StrategyType.SELECTOR}
            mutators = {k: v for k, v in available_to_add.items()
                        if v.strategy_type == StrategyType.MUTATOR}

            # 创建选项列表（不包含分组标题）
            selector_options = [(f"🎯 {v.display_name_cn} / {v.display_name_en}", k)
                                for k, v in selectors.items()]
            mutator_options = [(f"💡 {v.display_name_cn} / {v.display_name_en}", k)
                               for k, v in mutators.items()]

            all_options = []
            if selector_options:
                all_options.append(("─── 选择器 (Selectors) ───", "__selector_header__"))
                all_options.extend(selector_options)
            if mutator_options:
                all_options.append(("─── 创新策略 (Mutators) ───", "__mutator_header__"))
                all_options.extend(mutator_options)

            selected_strategy = st.selectbox(
                "选择策略",
                options=[opt[1] for opt in all_options],
                format_func=lambda x: next((opt[0] for opt in all_options if opt[1] == x), x),
                label_visibility="collapsed",
                key="new_strategy_select"
            )

            # 过滤掉标题选项
            if selected_strategy in ["__selector_header__", "__mutator_header__"]:
                selected_strategy = None

        with col2:
            # ===== 修复：建议权重基于剩余权重 =====
            remaining_weight = max(0.0, 1.0 - total_weight)
            suggested_weight = min(0.1, remaining_weight) if remaining_weight > 0 else 0.0

            new_weight = st.number_input(
                "权重",
                min_value=0.0,
                max_value=1.0,
                value=suggested_weight,
                step=0.05,
                key="new_strategy_weight",
                label_visibility="collapsed",
                help=f"建议值: {suggested_weight:.3f} (基于剩余权重)"
            )

        with col3:
            # 显示剩余权重
            remaining_after = 1.0 - total_weight - new_weight
            if remaining_after >= 0:
                st.metric("添加后剩余", f"{remaining_after:.3f}",
                          delta=f"-{new_weight:.3f}", delta_color="normal")
            else:
                st.metric("添加后超出", f"{abs(remaining_after):.3f}",
                          delta=f"-{new_weight:.3f}", delta_color="inverse")

        with col4:
            can_add = selected_strategy and selected_strategy not in ["__selector_header__", "__mutator_header__"]

            if st.button("➕ 添加", key="add_strategy_btn",
                         disabled=not can_add,
                         use_container_width=True,
                         type="primary" if can_add else "secondary"):
                if selected_strategy:
                    current_strategies.append({
                        'name': selected_strategy,
                        'weight': new_weight
                    })
                    st.session_state.strategy_config = current_strategies
                    st.rerun()

        # 显示选中策略的详细信息
        if selected_strategy and selected_strategy in AVAILABLE_STRATEGIES:
            strategy_def = AVAILABLE_STRATEGIES[selected_strategy]

            type_icon = "🎯 选择器" if strategy_def.strategy_type == StrategyType.SELECTOR else "💡 创新策略"
            innovation_text = "是（受禁用创新设置影响）" if strategy_def.is_innovation else "否"

            info_parts = [
                f"<b>{strategy_def.display_name_cn} / {strategy_def.display_name_en}</b>",
                f"类型: {type_icon}",
                f"说明: {strategy_def.description_cn}",
                f"创新策略: {innovation_text}"
            ]

            if strategy_def.requires_module:
                info_parts.append(f"需要模块: <code>{strategy_def.requires_module}</code>")

            st.markdown(f"""
            <div class="info-box">
            {'<br>'.join(info_parts)}
            </div>
            """, unsafe_allow_html=True)

    # 配置验证
    st.markdown("---")
    st.markdown("#### ✅ 配置验证 / Configuration Validation")

    validation_errors = []
    validation_warnings = []

    # 验证1: 权重总和
    if not weight_valid and len(current_strategies) > 0:
        validation_errors.append(f"权重总和为 {total_weight:.4f}，必须等于 1.0")

    # 验证2: 至少一个策略
    if len(current_strategies) == 0:
        validation_errors.append("必须至少配置一个策略")

    # 验证3: 至少一个选择器
    has_selector = any(
        AVAILABLE_STRATEGIES.get(s['name'], StrategyDefinition('', '', '',
                                                               StrategyType.MUTATOR)).strategy_type == StrategyType.SELECTOR
        for s in current_strategies
    )
    if len(current_strategies) > 0 and not has_selector:
        validation_warnings.append("建议至少配置一个选择器策略（如 BestScore）")

    # 验证4: 检查必需模块
    for strategy in current_strategies:
        strategy_def = AVAILABLE_STRATEGIES.get(strategy['name'])
        if strategy_def and strategy_def.requires_module:
            # 检查相关模块是否配置
            if strategy_def.requires_module == 'timeAllocationMutator':
                tam_config = st.session_state.get('time_allocation_mutator_config', {})
                if not tam_config or tam_config.get('mutationRange', 0) <= 0:
                    validation_warnings.append(
                        f"策略 {strategy_def.display_name_cn} 需要配置 TimeAllocationMutator 模块"
                    )
            elif strategy_def.requires_module == 'subtourModeChoice':
                smc_config = st.session_state.get('subtour_mode_choice_config', {})
                if not smc_config or not smc_config.get('modes'):
                    validation_warnings.append(
                        f"策略 {strategy_def.display_name_cn} 需要配置 SubtourModeChoice 模块"
                    )
            elif strategy_def.requires_module == 'changeMode':
                cm_config = st.session_state.get('changemode_config', {})
                if not cm_config:
                    validation_warnings.append(
                        f"策略 {strategy_def.display_name_cn} 需要配置 ChangeMode 模块"
                    )

    # 验证5: 权重为0的策略
    zero_weight_strategies = [s['name'] for s in current_strategies if s.get('weight', 0) == 0]
    if zero_weight_strategies:
        validation_warnings.append(
            f"以下策略权重为0，将不起作用: {', '.join(zero_weight_strategies)}"
        )

    # 验证6: 创新策略占比过低
    innovation_weight = sum(
        s.get('weight', 0) for s in current_strategies
        if AVAILABLE_STRATEGIES.get(s['name'], StrategyDefinition('', '', '', StrategyType.SELECTOR,
                                                                  is_innovation=False)).is_innovation
    )
    if len(current_strategies) > 0 and innovation_weight < 0.1:
        validation_warnings.append(
            f"创新策略总权重仅 {innovation_weight:.2%}，可能导致探索不足"
        )

    # 显示验证结果
    if validation_errors:
        for error in validation_errors:
            st.error(f"❌ {error}")

    if validation_warnings:
        for warning in validation_warnings:
            st.warning(f"⚠️ {warning}")

    if not validation_errors and not validation_warnings and len(current_strategies) > 0:
        st.success("✅ 配置有效！")

    # ===== 外部可执行文件设置（高级） =====
    st.markdown("---")
    with st.expander("⚙️ 外部可执行文件设置 / External Executable Settings (Advanced)", expanded=False):
        st.markdown("""
        <div class="info-box">
        用于与外部策略程序集成。一般用户无需配置。
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        with col1:
            st.session_state.replanning_config['externalExeConfigTemplate'] = st.text_input(
                create_param_label("配置模板路径 / externalExeConfigTemplate",
                                   "External Exe Config Template"),
                value=st.session_state.replanning_config.get('externalExeConfigTemplate', ''),
                help=create_help_text(
                    "外部可执行文件将使用的配置文件模板路径。可为空。",
                    "Path to skeleton config file for external executable. Can be null."
                )
            )

            st.session_state.replanning_config['externalExeTmpFileRootDir'] = st.text_input(
                create_param_label("临时文件根目录 / externalExeTmpFileRootDir",
                                   "External Exe Tmp File Root Dir"),
                value=st.session_state.replanning_config.get('externalExeTmpFileRootDir', ''),
                help=create_help_text(
                    "外部可执行文件生成临时文件的根目录。",
                    "Root directory for temporary files generated by external executable."
                )
            )

        with col2:
            st.session_state.replanning_config['externalExeTimeOut'] = st.number_input(
                create_param_label("超时时间(秒) / externalExeTimeOut",
                                   "External Exe Time Out (seconds)"),
                min_value=1,
                value=int(st.session_state.replanning_config.get('externalExeTimeOut', 3600)),
                help=create_help_text(
                    "超过该时间后，MATSim 将认为外部策略失败。",
                    "Time out value (in seconds) after which MATSim will consider the external strategy as failed."
                )
            )

    # ===== changeMode 模块配置 =====
    st.markdown("---")
    st.markdown("#### 🔁 出行方式变更模块 / changeMode Module")

    cm = st.session_state.changemode_config
    all_modes_for_change = ModeManager.get_choosable_modes()

    st.markdown("""
    changeMode 模块用于在重规划时**更改出行方式**，与策略 `ChangeTripMode`、`ChangeSingleTripMode`、`ChangeLegMode` 等一起使用时生效。
    """)

    # 检查是否有相关策略
    has_change_mode_strategy = any(
        s['name'] in ['ChangeTripMode', 'ChangeSingleTripMode', 'ChangeLegMode']
        for s in current_strategies
    )

    if not has_change_mode_strategy:
        st.info("ℹ️ 当前未使用任何需要 changeMode 模块的策略")

    # modes 来源选择
    cm['use_subtour_modes'] = st.radio(
        "模式来源 / Modes source",
        options=[True, False],
        index=0 if cm.get('use_subtour_modes', True) else 1,
        format_func=lambda x: "跟随 subtourModeChoice.modes / follow subtourModeChoice.modes"
        if x else "自定义模式列表 / use custom mode list",
        horizontal=False
    )

    if cm['use_subtour_modes']:
        st.info(
            "当前将使用 **subtourModeChoice.modes** 作为 changeMode 的 `modes` 参数：\n\n"
            f"`{', '.join(all_modes_for_change) if all_modes_for_change else '(当前为空)'}`"
        )
    else:
        available_modes = sorted(list(set(all_modes_for_change)))
        cm['custom_modes'] = st.multiselect(
            "自定义可切换模式 / Custom changeable modes (changeMode.modes)",
            options=available_modes,
            default=cm.get('custom_modes', available_modes),
            help="选择哪些出行方式可以被改变"
        )

    # ignoreCarAvailability
    cm['ignoreCarAvailability'] = st.checkbox(
        "忽略小汽车可用性 / ignoreCarAvailability",
        value=cm.get('ignoreCarAvailability', True),
        help=create_help_text(
            "若勾选，即使 Agent 没有车/驾照也可以被改成 car 模式。",
            "If checked, agents can be switched to 'car' even if they have no car/license."
        )
    )

    # modeSwitchBehavior
    cm['modeSwitchBehavior'] = st.selectbox(
        "模式切换行为 / modeSwitchBehavior",
        options=list(CHANGEMODE_BEHAVIOR_OPTIONS.keys()),
        format_func=lambda x: CHANGEMODE_BEHAVIOR_OPTIONS[x],
        index=list(CHANGEMODE_BEHAVIOR_OPTIONS.keys()).index(
            cm.get('modeSwitchBehavior', 'fromSpecifiedModesToSpecifiedModes')
        ),
        help=create_help_text(
            "fromSpecifiedModesToSpecifiedModes：仅当当前模式在 modes 中时才参与切换，目标模式也在 modes 中。\n"
            "fromAllModesToSpecifiedModes：所有当前模式都可以切换到 modes 中任一目标模式。",
            "fromSpecifiedModesToSpecifiedModes: only legs whose current mode is in 'modes' are changed.\n"
            "fromAllModesToSpecifiedModes: legs of all current modes may be changed to any mode in 'modes'."
        )
    )

    st.session_state.changemode_config = cm


def render_strategy_row(strategy: dict, index: int, strategies_list: list):
    """渲染单个策略行"""
    strategy_def = AVAILABLE_STRATEGIES.get(strategy['name'])
    if not strategy_def:
        return

    # 计算当前总权重（用于显示百分比）
    total = sum(s.get('weight', 0.0) for s in strategies_list)

    cols = st.columns([0.5, 2.5, 1.5, 1, 0.8, 0.5])

    with cols[0]:
        # 类型图标
        icon = "🎯" if strategy_def.strategy_type == StrategyType.SELECTOR else "💡"
        st.markdown(f"<div style='font-size: 1.5rem; text-align: center;'>{icon}</div>",
                    unsafe_allow_html=True)

    with cols[1]:
        # 策略名称和描述
        st.markdown(f"**{strategy_def.display_name_cn}**")
        st.caption(f"{strategy['name']}")

    with cols[2]:
        # 描述
        st.caption(strategy_def.description_cn)

    with cols[3]:
        # 权重输入
        current_weight = strategy.get('weight', 0.0)
        new_weight = st.number_input(
            "权重",
            min_value=0.0,
            max_value=1.0,
            value=float(current_weight),
            step=0.05,
            key=f"weight_{index}_{strategy['name']}",
            label_visibility="collapsed",
            format="%.3f"
        )

        # 只有当权重真正改变时才更新
        if abs(new_weight - current_weight) > 0.0001:
            strategies_list[index]['weight'] = new_weight
            st.session_state.strategy_config = strategies_list
            st.rerun()

    with cols[4]:
        # 百分比显示
        pct = (current_weight / total * 100) if total > 0 else 0
        st.metric("", f"{pct:.1f}%", label_visibility="collapsed")

    with cols[5]:
        # 删除按钮
        if st.button("🗑️", key=f"del_{index}_{strategy['name']}", help="删除此策略"):
            strategies_list.pop(index)
            st.session_state.strategy_config = strategies_list
            st.rerun()




def render_counts_configuration():
    """渲染 counts 模块配置（CountsConfigGroup）"""

    st.markdown('<div class="module-header">📈 流量计数评估配置 / Counts Settings</div>',
                unsafe_allow_html=True)

    counts_cfg = st.session_state.counts_config
    file_config = st.session_state.file_config

    st.markdown("""
    <div class="info-box">
    <b>模块说明 / Description</b><br>
    • 将仿真得到的链路流量与 <code>counts.xml</code> 实测计数进行对比。<br>
    • 可以按采样率缩放流量、按距离过滤计数站、按出行方式过滤事件。<br><br>
    <b>使用建议 / Tips</b><br>
    • 若未配置计数文件，本模块不会写出任何 counts 对比结果。<br>
    • 若使用人口采样（如10%），请将 <code>countsScaleFactor</code> 设置为采样率的倒数（例如10.0）。
    </div>
    """, unsafe_allow_html=True)

    # -------- 1. 输入文件（可复用 Input Files 的 countsFile） --------
    st.markdown("#### 📁 计数文件 / Counts File")

    render_file_upload(
        "流量计数文件 / counts.inputCountsFile",
        "Counts File (config.counts.inputCountsFile)",
        'countsFile',
        required=False,
        help_text="包含实测链路流量的 counts 文件，用于与仿真结果对比 / "
                  "Counts file with observed link volumes."
    )

    has_counts_file = bool(file_config.get('countsFile'))
    if not has_counts_file:
        st.warning("未配置计数文件时，将不会输出 counts 评估结果。 / "
                   "Without a counts file, no counts comparison will be written.")

    # -------- 2. 输出格式 --------
    st.markdown("#### 📤 输出设置 / Output Settings")

    col1, col2 = st.columns(2)

    with col1:
        output_format = st.selectbox(
            create_param_label("输出格式 / outputformat",
                               "Output Format (config.counts.outputformat)"),
            options=["txt", "html", "all"],
            index=["txt", "html", "all"].index(counts_cfg.get('outputFormat', 'txt')),
            format_func=lambda x: {
                "txt": "txt - 纯文本报告 / plain text",
                "html": "html - 图文报告 / HTML report",
                "all": "all - 同时输出两种 / both txt and html"
            }[x],
            help=create_help_text(
                "选择 counts 对比报告的输出格式。",
                "Select the output format for counts comparison reports."
            )
        )
        counts_cfg['outputFormat'] = output_format

    with col2:
        counts_cfg['writeCountsInterval'] = st.number_input(
            create_param_label("写出间隔 / writeCountsInterval",
                               "Write Interval (config.counts.writeCountsInterval)"),
            min_value=0,
            value=int(counts_cfg.get('writeCountsInterval', 10)),
            help=create_help_text(
                "每隔多少轮迭代写出一次 counts 对比结果，0 表示不自动写出。",
                "Write counts comparison every N iterations; 0 usually means no periodic output."
            )
        )

    # -------- 3. 采样 & 平滑 --------
    st.markdown("#### 🔧 采样与跨轮平均 / Sampling & Averaging")

    col1, col2 = st.columns(2)

    with col1:
        counts_cfg['countsScaleFactor'] = st.number_input(
            create_param_label("计数缩放因子 / countsScaleFactor",
                               "Counts Scale Factor (config.counts.countsScaleFactor)"),
            min_value=0.0,
            value=float(counts_cfg.get('countsScaleFactor', 1.0)),
            step=0.1,
            help=create_help_text(
                "用于按人口采样率缩放仿真流量，例如 10% 采样 → 10.0。",
                "Scale simulated flows according to population sampling rate, e.g. 10% sample → 10.0."
            )
        )

        st.caption(
            "示例：100%→1.0，10%→10.0，5%→20.0 / "
            "Examples: 100%→1.0, 10%→10.0, 5%→20.0"
        )

    with col2:
        counts_cfg['averageCountsOverIterations'] = st.number_input(
            create_param_label("跨轮平均窗口 / averageCountsOverIterations",
                               "Averaging Window (config.counts.averageCountsOverIterations)"),
            min_value=1,
            value=int(counts_cfg.get('averageCountsOverIterations', 5)),
            help=create_help_text(
                "对最近 N 轮迭代的流量取平均后再与 counts 对比，以平滑随机波动。",
                "Average flows over the last N iterations before comparing to counts."
            )
        )

    # -------- 4. 距离过滤 --------
    st.markdown("#### 📍 距离过滤 / Distance Filter")

    distance_enabled_default = counts_cfg.get('distanceFilter') is not None \
        or bool(counts_cfg.get('distanceFilterCenterNode'))
    distance_enabled = st.checkbox(
        create_param_label("启用距离过滤", "Enable Distance Filter"),
        value=distance_enabled_default,
        help=create_help_text(
            "只保留距某个中心节点一定半径内的计数站。",
            "Keep only counts located within a radius around a specified center node."
        )
    )

    if distance_enabled:
        col1, col2 = st.columns(2)
        with col1:
            counts_cfg['distanceFilter'] = st.number_input(
                create_param_label("过滤半径 (米) / distanceFilter",
                                   "Radius in meters (config.counts.distanceFilter)"),
                min_value=0.0,
                value=float(counts_cfg.get('distanceFilter') or 20000.0),
                step=1000.0,
                help=create_help_text(
                    "以路网坐标系单位（通常为米）表示的过滤半径。",
                    "Filter radius in network coordinate units (usually meters)."
                )
            )
        with col2:
            counts_cfg['distanceFilterCenterNode'] = st.text_input(
                create_param_label("中心节点 ID / distanceFilterCenterNode",
                                   "Center Node ID (config.counts.distanceFilterCenterNode)"),
                value=counts_cfg.get('distanceFilterCenterNode', ''),
                help=create_help_text(
                    "作为过滤中心的路网节点 ID，必须存在于 network 中。",
                    "Network node ID used as center for distance-based filtering."
                )
            )
    else:
        counts_cfg['distanceFilter'] = None
        counts_cfg['distanceFilterCenterNode'] = ''

    # -------- 5. 分析模式设置 --------
    st.markdown("#### 🚗 分析的出行方式 / Analyzed Modes")

    # 可用模式：网络 + 传送 + (pt) 等
    available_modes: set[str] = set()
    available_modes.update(st.session_state.get('network_modes', {}).keys())
    available_modes.update(st.session_state.get('teleported_modes', {}).keys())
    if st.session_state.get('transit_enabled', False):
        available_modes.add('pt')

    available_modes = sorted(available_modes)

    current_modes_str = counts_cfg.get('analyzedModes', 'car')
    current_modes = [m.strip() for m in current_modes_str.split(',') if m.strip()]
    # 和当前可用模式求交集
    current_modes = [m for m in current_modes if m in available_modes] or (
        ['car'] if 'car' in available_modes else []
    )

    selected_modes = st.multiselect(
        create_param_label("参与分析的模式 / analyzedModes",
                           "Modes to Analyze (config.counts.analyzedModes)"),
        options=available_modes,
        default=current_modes,
        help=create_help_text(
            "只统计这些出行方式产生的流量。",
            "Only flows of these travel modes are considered in counts comparison."
        )
    )
    if selected_modes:
        counts_cfg['analyzedModes'] = ','.join(selected_modes)
    else:
        # 保底：不选则清空，后续校验会给出警告
        counts_cfg['analyzedModes'] = ''

    counts_cfg['filterModes'] = st.checkbox(
        create_param_label("按模式过滤事件 / filterModes",
                           "Filter Events by Modes (config.counts.filterModes)"),
        value=bool(counts_cfg.get('filterModes', False)),
        help=create_help_text(
            "若为 true，则只统计 analyzedModes 中的出行方式；否则不按模式过滤。",
            "If true, only events with modes listed in analyzedModes are used."
        )
    )

    # -------- 6. inputCRS（已废弃） --------
    st.markdown("#### 🧭 坐标系（已废弃） / CRS (Deprecated)")

    counts_cfg['inputCRS'] = st.text_input(
        create_param_label("计数文件坐标系 / inputCRS",
                           "Counts CRS (config.counts.inputCRS, deprecated)"),
        value=counts_cfg.get('inputCRS', ''),
        help=create_help_text(
            "已废弃字段。新项目中建议直接让 counts 文件使用与路网相同的坐标系。",
            "Deprecated. For new projects, use the same CRS in the counts file as in the network."
        )
    )

    st.session_state.counts_config = counts_cfg

def render_events_manager_configuration():
    """渲染 eventsManager 模块配置（EventsManagerConfigGroup）"""

    st.markdown('<div class="module-header">📊 事件管理配置 / EventsManager Settings</div>',
                unsafe_allow_html=True)

    em_cfg = st.session_state.events_manager_config

    st.markdown("""
    <div class="info-box">
    <b>模块说明 / Description</b><br>
    • 控制仿真事件（events）的队列大小和处理线程数。<br>
    • 一般情况下保持默认即可，仅在超大规模场景或性能调优时修改。<br><br>
    <b>重要提示 / Important</b><br>
    • 若使用 <i>within-day replanning</i> 等在线重规划，<code>synchronizeOnSimSteps</code> 必须保持为 <code>true</code>。
    </div>
    """, unsafe_allow_html=True)

    # -------- 1. 线程与队列 --------
    st.markdown("#### ⚙️ 线程与队列 / Threads & Queue")

    col1, col2 = st.columns(2)

    with col1:
        em_cfg['numberOfThreads'] = st.number_input(
            create_param_label("事件线程数 / numberOfThreads",
                               "Event Threads (config.eventsManager.numberOfThreads)"),
            min_value=0,
            value=int(em_cfg.get('numberOfThreads', 0)),
            help=create_help_text(
                "0 表示由 MATSim 自动决定线程数；>0 时为显式指定线程数（0 在内部是不合法值，因此不会写入 XML）。",
                "0 lets MATSim decide automatically; >0 explicitly sets the number of threads "
                "(0 is not a valid config value and will not be written)."
            )
        )

    with col2:
        em_cfg['eventsQueueSize'] = st.number_input(
            create_param_label("事件队列大小 / eventsQueueSize",
                               "Events Queue Size (config.eventsManager.eventsQueueSize)"),
            min_value=1024,
            value=int(em_cfg.get('eventsQueueSize', 131072)),
            step=1024,
            help=create_help_text(
                "事件队列容量，场景极大且事件非常密集时可以适当增大，默认约为 13 万。",
                "Capacity of the events queue. Increase for very large scenarios; default is ~131k."
            )
        )

    # -------- 2. 事件规模预估 --------
    st.markdown("#### 🔢 预估事件数量 / Estimated Number of Events")

    em_cfg['estimatedNumberOfEvents'] = st.number_input(
        create_param_label("预估事件总数 / estimatedNumberOfEvents",
                           "Estimated Number of Events (config.eventsManager.estimatedNumberOfEvents)"),
        min_value=0,
        value=int(em_cfg.get('estimatedNumberOfEvents', 0)),
        help=create_help_text(
            "可选的性能优化提示。0 表示不设置；若已知事件量级（如 5000 万），可显式填入。",
            "Optional performance hint. 0 means not set; if you know the expected order of magnitude "
            "(e.g., 50,000,000), you may specify it here."
        )
    )

    # -------- 3. 同步策略 --------
    st.markdown("#### ⏱ 同步策略 / Synchronization")

    col1, col2 = st.columns(2)

    with col1:
        em_cfg['synchronizeOnSimSteps'] = st.checkbox(
            create_param_label("按时间步同步 / synchronizeOnSimSteps",
                               "Synchronize on Sim Steps (config.eventsManager.synchronizeOnSimSteps)"),
            value=bool(em_cfg.get('synchronizeOnSimSteps', True)),
            help=create_help_text(
                "若为 true，则确保某一仿真时间步产生的事件在进入下一时间步前全部处理完；"
                "使用 within-day replanning 时必须为 true。",
                "If true, all events within a simulation time step are processed before advancing "
                "to the next step; must be true when using within-day replanning."
            )
        )

    with col2:
        em_cfg['oneThreadPerHandler'] = st.checkbox(
            create_param_label("每个处理器独立线程 / oneThreadPerHandler",
                               "One Thread per Handler (config.eventsManager.oneThreadPerHandler)"),
            value=bool(em_cfg.get('oneThreadPerHandler', False)),
            help=create_help_text(
                "实验功能：为每个事件处理器分配独立线程，同时忽略 numberOfThreads 设置。"
                "一般不建议开启，除非非常清楚 handler 数量和线程安全性。",
                "Experimental feature: assign a dedicated thread to each event handler and ignore "
                "numberOfThreads. Not recommended unless you fully understand handler count and "
                "thread-safety implications."
            )
        )

    st.session_state.events_manager_config = em_cfg


def render_time_allocation_mutator_configuration():
    """渲染 TimeAllocationMutator 模块配置"""

    st.markdown('<div class="module-header">⏱️ 时间分配变异器配置 / TimeAllocationMutator Settings</div>',
                unsafe_allow_html=True)

    tam = st.session_state.time_allocation_mutator_config

    st.markdown("""
    <div class="info-box">
    <b>模块说明 / Description</b><br>
    • 控制 Agent 活动时间的随机变异，是重规划策略 TimeAllocationMutator 的核心参数。<br>
    • 通过调整活动开始/结束时间，帮助 Agent 探索不同的时间安排。<br><br>
    <b>使用建议 / Tips</b><br>
    • mutationRange 越大，时间调整幅度越大，探索性越强。<br>
    • 通常设置为 1800 秒（30分钟），可根据场景调整。<br>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### ⚙️ 变异参数 / Mutation Parameters")

    col1, col2 = st.columns(2)

    with col1:
        tam['mutationRange'] = st.number_input(
            create_param_label("变异范围 / mutationRange (秒)",
                               "Mutation Range (config.timeAllocationMutator.mutationRange)"),
            min_value=0.0,
            max_value=7200.0,
            value=float(tam.get('mutationRange', 1800.0)),
            step=60.0,
            help=create_help_text(
                "时间变异的最大偏移量（秒）。默认1800秒=30分钟。"
                "较大值允许更大的时间调整，较小值使调整更精细。",
                "Maximum time shift in seconds. Default 1800s = 30min. "
                "Larger values allow bigger adjustments, smaller values are more fine-grained."
            )
        )

        # 显示人性化时间
        st.caption(f"= {tam['mutationRange'] / 60:.0f} 分钟 / {tam['mutationRange'] / 60:.0f} minutes")

        tam['mutationRangeStep'] = st.number_input(
            create_param_label("变异步长 / mutationRangeStep (秒)",
                               "Mutation Range Step"),
            min_value=1.0,
            max_value=60.0,
            value=float(tam.get('mutationRangeStep', 1.0)),
            step=1.0,
            help=create_help_text(
                "时间变异的最小步长（秒）。默认1秒。",
                "Minimum step size for time mutation in seconds. Default 1 second."
            )
        )

    with col2:
        tam['mutationAffectsDuration'] = st.checkbox(
            create_param_label("变异影响持续时间 / mutationAffectsDuration",
                               "Mutation Affects Duration"),
            value=bool(tam.get('mutationAffectsDuration', True)),
            help=create_help_text(
                "若勾选，时间变异会改变活动的持续时间。"
                "若不勾选，仅移动活动的开始/结束时间窗口。",
                "If checked, time mutation changes activity duration. "
                "If unchecked, only shifts the activity time window."
            )
        )

        tam['mutateAroundInitialEndTimeOnly'] = st.checkbox(
            create_param_label("仅围绕初始结束时间变异 / mutateAroundInitialEndTimeOnly",
                               "Mutate Around Initial End Time Only"),
            value=bool(tam.get('mutateAroundInitialEndTimeOnly', False)),
            help=create_help_text(
                "若勾选，仅围绕计划中初始定义的结束时间进行变异。"
                "有助于保持活动时间的稳定性。",
                "If checked, mutates times only around initially defined end times. "
                "Helps maintain activity timing stability."
            )
        )

    st.markdown("---")
    st.markdown("#### ⏰ 时间约束 / Time Constraints")

    tam['latestActivityEndTime'] = st.text_input(
        create_param_label("最晚活动结束时间 / latestActivityEndTime",
                           "Latest Activity End Time"),
        value=tam.get('latestActivityEndTime', '24:00:00'),
        help=create_help_text(
            "活动可以结束的最晚时间。默认24:00:00。"
            "超过此时间的活动将被截断。",
            "Latest time an activity can end. Default 24:00:00. "
            "Activities ending later will be truncated."
        )
    )

    st.session_state.time_allocation_mutator_config = tam


def render_transit_configuration():
    """渲染 Transit 模块配置"""

    st.markdown('<div class="module-header">🚌 公共交通配置 / Transit Settings</div>',
                unsafe_allow_html=True)

    transit_cfg = st.session_state.transit_config

    # 同步 transit_enabled 状态
    transit_cfg['useTransit'] = st.session_state.get('transit_enabled', False)

    st.markdown("""
    <div class="info-box">
    <b>模块说明 / Description</b><br>
    • 控制 MATSim 公共交通系统的核心配置。<br>
    • 文件路径在「输入文件配置」中设置，此处配置运行参数。<br><br>
    <b>使用建议 / Tips</b><br>
    • 路由算法推荐使用 SwissRailRaptor（高效且支持多模式接驳）。<br>
    • 若使用多模式接驳，请同时配置 swissRailRaptor 模块。<br>
    </div>
    """, unsafe_allow_html=True)

    # 主开关状态显示
    if transit_cfg['useTransit']:
        st.success("✅ 公共交通已启用")
    else:
        st.warning("⚠️ 公共交通未启用。请在「出行模式配置 → 公共交通配置」中启用。")
        st.caption("以下配置将在启用公交后生效。")

    st.markdown("---")
    st.markdown("#### 🚌 基本参数 / Basic Parameters")

    col1, col2 = st.columns(2)

    with col1:
        transit_cfg['transitModes'] = st.text_input(
            create_param_label("公交模式 / transitModes",
                               "Transit Modes (config.transit.transitModes)"),
            value=transit_cfg.get('transitModes', 'pt'),
            help=create_help_text(
                "作为公交处理的出行模式（逗号分隔）。默认为 pt。",
                "Transportation modes handled as transit (comma-separated). Default is pt."
            )
        )

        routing_algo_options = list(TRANSIT_ROUTING_ALGORITHM_OPTIONS.keys())
        current_algo = transit_cfg.get('routingAlgorithmType', 'SwissRailRaptor')

        transit_cfg['routingAlgorithmType'] = st.selectbox(
            create_param_label("公共交通路由算法 / routingAlgorithmType",
                               "Routing Algorithm Type"),
            options=routing_algo_options,
            index=routing_algo_options.index(current_algo) if current_algo in routing_algo_options else 0,
            format_func=lambda x: TRANSIT_ROUTING_ALGORITHM_OPTIONS[x][0],
            help=create_help_text(
                "公交路由算法类型。强烈推荐 SwissRailRaptor。",
                "Transit routing algorithm type. SwissRailRaptor is strongly recommended."
            )
        )
        st.caption(TRANSIT_ROUTING_ALGORITHM_OPTIONS[transit_cfg['routingAlgorithmType']][1])

    with col2:
        transit_cfg['usingTransitInMobsim'] = st.checkbox(
            create_param_label("在Mobsim中使用公交 / usingTransitInMobsim",
                               "Use Transit in Mobsim"),
            value=bool(transit_cfg.get('usingTransitInMobsim', True)),
            help=create_help_text(
                "是否在交通仿真中模拟公交车辆。通常保持启用。",
                "Whether to simulate transit vehicles in mobsim. Usually keep enabled."
            )
        )

        boarding_options = list(TRANSIT_BOARDING_ACCEPTANCE_OPTIONS.keys())
        current_boarding = transit_cfg.get('boardingAcceptance', 'checkLineAndStop')

        transit_cfg['boardingAcceptance'] = st.selectbox(
            create_param_label("上车条件 / boardingAcceptance",
                               "Boarding Acceptance"),
            options=boarding_options,
            index=boarding_options.index(current_boarding) if current_boarding in boarding_options else 0,
            format_func=lambda x: TRANSIT_BOARDING_ACCEPTANCE_OPTIONS[x][0],
            help=create_help_text(
                "Agent上车时的检查条件。",
                "Conditions checked when agent boards a transit vehicle."
            )
        )

    st.markdown("---")
    st.markdown("#### 🌐 坐标系 / Coordinate System")

    transit_cfg['inputScheduleCRS'] = st.text_input(
        create_param_label("时刻表坐标系 / inputScheduleCRS",
                           "Input Schedule CRS"),
        value=transit_cfg.get('inputScheduleCRS', ''),
        placeholder="如: EPSG:4326",
        help=create_help_text(
            "时刻表文件中坐标的坐标系。导入时会转换到 global.coordinateSystem。"
            "留空表示不进行转换。",
            "CRS of coordinates in the schedule file. Converted to global.coordinateSystem at import. "
            "Leave empty for no conversion."
        )
    )

    # 废弃参数（折叠）
    with st.expander("⚠️ 废弃参数（仅向后兼容）", expanded=False):
        st.warning("以下参数已废弃。推荐将属性直接添加到站点/线路对象中。")

        transit_cfg['insistingOnUsingDeprecatedAttributeFiles'] = st.checkbox(
            "坚持使用废弃属性文件",
            value=bool(transit_cfg.get('insistingOnUsingDeprecatedAttributeFiles', False)),
            help="仅当必须使用旧的属性文件时才勾选"
        )

        if transit_cfg['insistingOnUsingDeprecatedAttributeFiles']:
            transit_cfg['transitLinesAttributesFile'] = st.text_input(
                "线路属性文件",
                value=transit_cfg.get('transitLinesAttributesFile', '')
            )
            transit_cfg['transitStopsAttributesFile'] = st.text_input(
                "站点属性文件",
                value=transit_cfg.get('transitStopsAttributesFile', '')
            )

    st.session_state.transit_config = transit_cfg


def render_transit_router_configuration():
    """渲染 TransitRouter 模块配置"""

    st.markdown('<div class="module-header">🔍 公交路由器配置 / TransitRouter Settings</div>',
                unsafe_allow_html=True)

    tr = st.session_state.transit_router_config

    st.markdown("""
    <div class="info-box">
    <b>模块说明 / Description</b><br>
    • 控制公交路由器的搜索参数，影响 Agent 如何找到公交站点和换乘。<br>
    • 主要用于传统的 Dijkstra 路由器；使用 SwissRailRaptor 时部分参数由该模块覆盖。<br><br>
    <b>使用建议 / Tips</b><br>
    • searchRadius 决定了 Agent 愿意步行到站点的最大距离。<br>
    • 若使用 SwissRailRaptor，建议主要配置 swissRailRaptor 模块。<br>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### 📍 搜索参数 / Search Parameters")

    col1, col2 = st.columns(2)

    with col1:
        tr['searchRadius'] = st.number_input(
            create_param_label("搜索半径 / searchRadius (米)",
                               "Search Radius (config.transitRouter.searchRadius)"),
            min_value=100.0,
            max_value=5000.0,
            value=float(tr.get('searchRadius', 1000.0)),
            step=100.0,
            help=create_help_text(
                "给定起点/终点坐标时，搜索公交站点的半径（米）。",
                "Radius in which stop locations are searched given a start or target coordinate."
            )
        )

        tr['extensionRadius'] = st.number_input(
            create_param_label("扩展半径 / extensionRadius (米)",
                               "Extension Radius"),
            min_value=50.0,
            max_value=1000.0,
            value=float(tr.get('extensionRadius', 200.0)),
            step=50.0,
            help=create_help_text(
                "若初始搜索未找到站点，增加搜索半径的步长。",
                "Step size to increase searchRadius if no stops are found."
            )
        )

    with col2:
        tr['maxBeelineWalkConnectionDistance'] = st.number_input(
            create_param_label("最大步行换乘距离 / maxBeelineWalkConnectionDistance (米)",
                               "Max Beeline Walk Connection Distance"),
            min_value=50.0,
            max_value=500.0,
            value=float(tr.get('maxBeelineWalkConnectionDistance', 100.0)),
            step=10.0,
            help=create_help_text(
                "Agent步行换乘时站点间的最大直线距离。",
                "Maximum beeline distance between stops that agents could transfer to by walking."
            )
        )

        tr['additionalTransferTime'] = st.number_input(
            create_param_label("额外换乘时间 / additionalTransferTime (秒)",
                               "Additional Transfer Time"),
            min_value=0.0,
            max_value=600.0,
            value=float(tr.get('additionalTransferTime', 0.0)),
            step=10.0,
            help=create_help_text(
                "换乘时额外分配的安全时间（秒），用于确保 Agent 能安全换乘。",
                "Additional safety time allocated when a line switch happens."
            )
        )

    st.markdown("---")
    st.markdown("#### ⚖️ 直接步行因子 / Direct Walk Factor")

    tr['directWalkFactor'] = st.number_input(
        create_param_label("直接步行因子 / directWalkFactor",
                           "Direct Walk Factor"),
        min_value=0.1,
        max_value=100.0,
        value=float(tr.get('directWalkFactor', 1.0)),
        step=0.5,
        help=create_help_text(
            "直接步行的广义成本乘数。设置较高值可减少直接步行结果，鼓励使用公交。"
            "例如：设为10.0意味着直接步行成本被放大10倍。",
            "Multiplier for direct walk generalized cost. Set high to reduce direct walk results. "
            "E.g., 10.0 means direct walk cost is multiplied by 10."
        )
    )

    st.session_state.transit_router_config = tr


def render_swiss_rail_raptor_configuration():
    """渲染 SwissRailRaptor 模块配置"""

    st.markdown('<div class="module-header">🚄 SwissRailRaptor 高级公交路由配置 / SwissRailRaptor Settings</div>',
                unsafe_allow_html=True)

    raptor = st.session_state.swiss_rail_raptor_config

    st.markdown("""
    <div class="info-box">
    <b>模块说明 / Description</b><br>
    • SwissRailRaptor 是 MATSim 推荐的高效公交路由算法。<br>
    • 支持多模式接驳（如步行、自行车到公交站）和容量约束。<br>
    • 接驳模式配置从「出行模式配置 → 公共交通配置」同步。<br><br>
    <b>使用建议 / Tips</b><br>
    • 若启用多模式接驳，请确保已在「出行模式配置」中配置接驳模式。<br>
    • 换乘惩罚参数可用于调整 Agent 对换乘的敏感度。<br>
    </div>
    """, unsafe_allow_html=True)

    # 检查公交是否启用
    transit_enabled = st.session_state.get('transit_enabled', False)
    if not transit_enabled:
        st.warning("⚠️ 公共交通未启用。请先在「出行模式配置」中启用公交。")
        return

    # ===== Tab 布局 =====
    tab1, tab2, tab3 = st.tabs([
        "🎯 基本参数",
        "🔄 换乘参数",
        "🚶 接驳配置"
    ])

    # ===== Tab 1: 基本参数 =====
    with tab1:
        st.markdown("#### 🎯 基本参数 / Basic Parameters")

        col1, col2 = st.columns(2)

        with col1:
            raptor['useIntermodalAccessEgress'] = st.checkbox(
                create_param_label("启用多模式接驳 / useIntermodalAccessEgress",
                                   "Use Intermodal Access/Egress"),
                value=bool(raptor.get('useIntermodalAccessEgress', True)),
                help=create_help_text(
                    "启用多模式接驳，允许 Agent 使用步行、自行车等方式到达公交站。",
                    "Enable intermodal access/egress, allowing agents to use walk, bike, etc. to reach transit stops."
                )
            )

            raptor['useCapacityConstraints'] = st.checkbox(
                create_param_label("启用容量约束 / useCapacityConstraints",
                                   "Use Capacity Constraints"),
                value=bool(raptor.get('useCapacityConstraints', False)),
                help=create_help_text(
                    "若启用，SwissRailRaptor 会检测上一轮因车辆满载而无法上车的情况，并尝试寻找替代路线。",
                    "If enabled, detects when agents cannot board due to full vehicles and tries to find alternatives."
                )
            )

            raptor['useRangeQuery'] = st.checkbox(
                create_param_label("启用范围查询 / useRangeQuery",
                                   "Use Range Query"),
                value=bool(raptor.get('useRangeQuery', False)),
                help=create_help_text(
                    "启用范围查询，允许在一定时间范围内搜索出发时间。",
                    "Enable range query to search departure times within a time range."
                )
            )

        with col2:
            mode_selection_options = list(RAPTOR_INTERMODAL_MODE_SELECTION_OPTIONS.keys())
            current_selection = raptor.get('intermodalAccessEgressModeSelection', 'CalcLeastCostModePerStop')

            raptor['intermodalAccessEgressModeSelection'] = st.selectbox(
                create_param_label("接驳模式选择方式 / intermodalAccessEgressModeSelection",
                                   "Intermodal Mode Selection"),
                options=mode_selection_options,
                index=mode_selection_options.index(
                    current_selection) if current_selection in mode_selection_options else 0,
                format_func=lambda x: RAPTOR_INTERMODAL_MODE_SELECTION_OPTIONS[x][0],
                help=create_help_text(
                    "选择接驳模式的策略：按成本计算或随机选择。",
                    "Strategy for selecting access/egress modes: by cost or randomly."
                )
            )

            leg_handling_options = list(RAPTOR_INTERMODAL_LEG_HANDLING_OPTIONS.keys())
            current_handling = raptor.get('intermodalLegOnlyHandling', 'forbid')

            raptor['intermodalLegOnlyHandling'] = st.selectbox(
                create_param_label("仅接驳行程处理 / intermodalLegOnlyHandling",
                                   "Intermodal Leg Only Handling"),
                options=leg_handling_options,
                index=leg_handling_options.index(current_handling) if current_handling in leg_handling_options else 2,
                format_func=lambda x: RAPTOR_INTERMODAL_LEG_HANDLING_OPTIONS[x][0],
                help=create_help_text(
                    "如何处理仅由接驳行程组成（无公交）的路线。",
                    "How to handle routes consisting only of intermodal legs (no actual PT)."
                )
            )

        # 评分和换乘计算参数
        st.markdown("---")
        col1, col2 = st.columns(2)

        with col1:
            scoring_options = list(RAPTOR_SCORING_PARAMETERS_OPTIONS.keys())
            current_scoring = raptor.get('scoringParameters', 'Default')

            raptor['scoringParameters'] = st.selectbox(
                create_param_label("评分参数类型 / scoringParameters",
                                   "Scoring Parameters"),
                options=scoring_options,
                index=scoring_options.index(current_scoring) if current_scoring in scoring_options else 0,
                format_func=lambda x: RAPTOR_SCORING_PARAMETERS_OPTIONS[x],
                help="选择使用默认评分参数还是个性化评分参数"
            )

        with col2:
            transfer_calc_options = list(RAPTOR_TRANSFER_CALCULATION_OPTIONS.keys())
            current_calc = raptor.get('transferCalculation', 'Initial')

            raptor['transferCalculation'] = st.selectbox(
                create_param_label("换乘计算方式 / transferCalculation",
                                   "Transfer Calculation"),
                options=transfer_calc_options,
                index=transfer_calc_options.index(current_calc) if current_calc in transfer_calc_options else 0,
                format_func=lambda x: RAPTOR_TRANSFER_CALCULATION_OPTIONS[x][0],
                help=RAPTOR_TRANSFER_CALCULATION_OPTIONS[current_calc][1]
            )

    #    # ===== Tab 2: 换乘参数 =====
    with tab2:
        st.markdown("#### 🔄 换乘惩罚参数 / Transfer Penalty Parameters")

        st.markdown("""
        <div class="info-box">
        换乘惩罚用于调整 Agent 对换乘次数的敏感度。<br>
        计算公式：<code>penalty = base + hourly × travelTimeHours</code>，受 min/max 约束。
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        with col1:
            raptor['transferPenaltyBaseCost'] = st.number_input(
                create_param_label("基础换乘惩罚 / transferPenaltyBaseCost",
                                   "Transfer Penalty Base Cost"),
                value=float(raptor.get('transferPenaltyBaseCost', 0.0)),
                step=0.5,
                help=create_help_text(
                    "每次换乘的基础成本（以效用单位计）。",
                    "Base cost per transfer in utility units."
                )
            )

            raptor['transferPenaltyCostPerTravelTimeHour'] = st.number_input(
                create_param_label("每小时换乘惩罚 / transferPenaltyCostPerTravelTimeHour",
                                   "Transfer Penalty Per Hour"),
                value=float(raptor.get('transferPenaltyCostPerTravelTimeHour', 0.0)),
                step=0.5,
                help=create_help_text(
                    "每小时出行时间的额外换乘成本。",
                    "Additional transfer cost per hour of travel time."
                )
            )

        with col2:
            # ===== 修复：最小换乘惩罚 =====
            current_min_cost = raptor.get('transferPenaltyMinCost')

            use_min = st.checkbox(
                "设置最小换乘惩罚",
                value=current_min_cost is not None,
                key="use_transfer_penalty_min",
                help="启用后，换乘惩罚将不会低于此值"
            )

            if use_min:
                # 如果启用，显示输入框
                # 如果之前是 None，使用默认值 0.0
                default_min_value = current_min_cost if current_min_cost is not None else 0.0

                raptor['transferPenaltyMinCost'] = st.number_input(
                    "最小换乘惩罚 / transferPenaltyMinCost",
                    value=float(default_min_value),
                    step=0.5,
                    key="transfer_penalty_min_input",
                    help=create_help_text(
                        "换乘惩罚的下限值。计算结果低于此值时使用此值。",
                        "Lower bound for transfer penalty. Use this value when calculated penalty is lower."
                    )
                )
            else:
                raptor['transferPenaltyMinCost'] = None

            # ===== 修复：最大换乘惩罚 =====
            current_max_cost = raptor.get('transferPenaltyMaxCost')

            use_max = st.checkbox(
                "设置最大换乘惩罚",
                value=current_max_cost is not None,
                key="use_transfer_penalty_max",
                help="启用后，换乘惩罚将不会高于此值"
            )

            if use_max:
                # 如果启用，显示输入框
                # 如果之前是 None，使用默认值 10.0
                default_max_value = current_max_cost if current_max_cost is not None else 10.0

                raptor['transferPenaltyMaxCost'] = st.number_input(
                    "最大换乘惩罚 / transferPenaltyMaxCost",
                    value=float(default_max_value),
                    step=0.5,
                    key="transfer_penalty_max_input",
                    help=create_help_text(
                        "换乘惩罚的上限值。计算结果高于此值时使用此值。",
                        "Upper bound for transfer penalty. Use this value when calculated penalty is higher."
                    )
                )
            else:
                raptor['transferPenaltyMaxCost'] = None

        # ===== 添加：换乘惩罚计算示例 =====
        st.markdown("---")
        st.markdown("#### 💡 换乘惩罚计算示例 / Transfer Penalty Calculation Example")

        with st.expander("查看计算示例", expanded=False):
            base = raptor.get('transferPenaltyBaseCost', 0.0)
            hourly = raptor.get('transferPenaltyCostPerTravelTimeHour', 0.0)
            min_cost = raptor.get('transferPenaltyMinCost')
            max_cost = raptor.get('transferPenaltyMaxCost')

            st.markdown(f"""
            **当前设置：**
            - 基础成本 (base): `{base}`
            - 每小时成本 (hourly): `{hourly}`
            - 最小惩罚 (min): `{min_cost if min_cost is not None else '未设置 (-∞)'}`
            - 最大惩罚 (max): `{max_cost if max_cost is not None else '未设置 (+∞)'}`
            
            **计算公式：**
            ```
            raw_penalty = base + hourly × travel_time_hours
            final_penalty = CLAMP(raw_penalty, min, max)
            ```
            
            **示例：**
            """)

            # 计算几个示例
            travel_times = [0.5, 1.0, 2.0, 3.0]  # 小时

            for travel_time in travel_times:
                raw_penalty = base + hourly * travel_time

                # 应用 min/max 约束
                final_penalty = raw_penalty
                if min_cost is not None and final_penalty < min_cost:
                    final_penalty = min_cost
                    constraint_note = f" → 受最小值约束 = {min_cost}"
                elif max_cost is not None and final_penalty > max_cost:
                    final_penalty = max_cost
                    constraint_note = f" → 受最大值约束 = {max_cost}"
                else:
                    constraint_note = ""

                travel_time_min = int(travel_time * 60)
                st.markdown(
                    f"- 出行时间 **{travel_time_min} 分钟**: "
                    f"原始惩罚 = {base} + {hourly} × {travel_time} = **{raw_penalty:.2f}**"
                    f"{constraint_note}"
                )

        st.markdown("---")
        st.markdown("#### ⏱️ 换乘时间参数 / Transfer Time Parameters")

        raptor['transferWalkMargin'] = st.number_input(
            create_param_label("换乘步行边际时间 / transferWalkMargin (秒)",
                               "Transfer Walk Margin"),
            min_value=0.0,
            max_value=60.0,
            value=float(raptor.get('transferWalkMargin', 5.0)),
            step=1.0,
            help=create_help_text(
                "从换乘步行时间中扣除的安全余量（秒），以避免因延误错过车辆。",
                "Time deducted from transfer walk time to avoid missing vehicles due to delays."
            )
        )
    # ===== Tab 3: 接驳配置 =====
    with tab3:
        st.markdown("#### 🚶 接驳模式配置 / Intermodal Access/Egress Configuration")

        # 从 access_egress_config 同步
        access_egress_config = st.session_state.get('access_egress_config', {})
        enabled_ae = [m for m, c in access_egress_config.items() if c.get('enabled', False)]

        if not enabled_ae:
            st.warning(
                "⚠️ 尚未配置接驳模式。请在「出行模式配置 → 公共交通配置 → Step 3: 接驳模式配置」中启用接驳模式。")

            # 提供快速跳转按钮
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("🔗 前往配置接驳模式", type="primary"):
                    st.session_state['nav_target'] = 'modes'
                    st.rerun()
            with col2:
                st.caption("跳转到「出行模式配置」页面")
        else:
            st.success(f"✅ 已启用的接驳模式: `{', '.join(enabled_ae)}`")

            st.markdown("""
            <div class="info-box">
            以下参数控制 SwissRailRaptor 如何使用接驳模式搜索公交站点。<br>
            这些参数会覆盖「出行模式配置」中的基础设置。
            </div>
            """, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("**接驳模式详细参数：**")

            # 为每个启用的接驳模式显示配置表单
            for mode in enabled_ae:
                ae_config = access_egress_config.get(mode, {})
                teleported_config = st.session_state.get('teleported_modes', {}).get(mode, {})

                with st.expander(f"📍 **{mode}** ({teleported_config.get('display_name', mode)})", expanded=False):

                    # 显示基础信息
                    speed_kmh = teleported_config.get('speed_kmh', 5.0)
                    beeline_factor = teleported_config.get('beeline_factor', 1.3)

                    st.markdown(f"""
                    **模式信息：**
                    - 速度: `{speed_kmh} km/h` ({speed_kmh / 3.6:.2f} m/s)
                    - 直线系数: `{beeline_factor}`
                    - 来源: 传送模式 / Teleported Mode
                    """)

                    st.markdown("---")

                    # 搜索半径参数
                    col1, col2 = st.columns(2)

                    with col1:
                        ae_config['max_radius'] = st.number_input(
                            create_param_label("最大搜索半径 / maxRadius (米)",
                                               "Max Search Radius (meters)"),
                            min_value=100.0,
                            max_value=50000.0,
                            value=float(ae_config.get('max_radius', 1000.0)),
                            step=100.0,
                            key=f"raptor_max_{mode}",
                            help=create_help_text(
                                f"使用 {mode} 模式可达站点的最大半径。",
                                f"Maximum radius for stops reachable by {mode} mode."
                            )
                        )

                        ae_config['initial_search_radius'] = st.number_input(
                            create_param_label("初始搜索半径 / initialSearchRadius (米)",
                                               "Initial Search Radius (meters)"),
                            min_value=50.0,
                            max_value=10000.0,
                            value=float(ae_config.get('initial_search_radius', 500.0)),
                            step=50.0,
                            key=f"raptor_init_{mode}",
                            help=create_help_text(
                                "开始搜索站点的初始半径。",
                                "Initial radius for searching stops."
                            )
                        )

                    with col2:
                        ae_config['search_extension_radius'] = st.number_input(
                            create_param_label("搜索扩展半径 / searchExtensionRadius (米)",
                                               "Search Extension Radius (meters)"),
                            min_value=50.0,
                            max_value=1000.0,
                            value=float(ae_config.get('search_extension_radius', 200.0)),
                            step=50.0,
                            key=f"raptor_ext_{mode}",
                            help=create_help_text(
                                "若找到的站点少于2个，扩展搜索的半径。",
                                "Radius to extend search if fewer than 2 stops are found."
                            )
                        )

                        # 计算最大出行时间
                        max_time_seconds = ae_config['max_radius'] / (speed_kmh / 3.6)
                        max_time_minutes = max_time_seconds / 60
                        st.metric(
                            "最大接驳时间",
                            f"{max_time_minutes:.1f} 分钟",
                            help=f"基于最大半径 {ae_config['max_radius']}m 和速度 {speed_kmh} km/h 计算"
                        )

                    # 可选过滤器
                    st.markdown("---")
                    st.markdown("**可选过滤器 (Optional Filters):**")

                    st.markdown("""
                    <div class="tip-box">
                    💡 <b>提示：</b>过滤器用于限制哪些站点可以使用此接驳模式，或哪些Agent可以使用。<br>
                    留空表示不过滤（所有站点/Agent都可用）。
                    </div>
                    """, unsafe_allow_html=True)

                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown("**站点过滤 / Stop Filter**")

                        ae_config['stop_filter_attribute'] = st.text_input(
                            "站点过滤属性 / stopFilterAttribute",
                            value=ae_config.get('stop_filter_attribute', ''),
                            key=f"raptor_stop_attr_{mode}",
                            placeholder="例如: accessMode",
                            help="站点必须具有此属性才能使用该接驳模式"
                        )

                        ae_config['stop_filter_value'] = st.text_input(
                            "站点过滤值 / stopFilterValue",
                            value=ae_config.get('stop_filter_value', ''),
                            key=f"raptor_stop_val_{mode}",
                            placeholder="例如: walk",
                            help="站点属性必须等于此值"
                        )

                        if ae_config.get('stop_filter_attribute'):
                            st.caption(
                                f"✅ 只有属性 `{ae_config['stop_filter_attribute']}` "
                                f"= `{ae_config.get('stop_filter_value', '(任意值)')}` 的站点可用"
                            )

                    with col2:
                        st.markdown("**人员过滤 / Person Filter**")

                        ae_config['person_filter_attribute'] = st.text_input(
                            "人员过滤属性 / personFilterAttribute",
                            value=ae_config.get('person_filter_attribute', ''),
                            key=f"raptor_person_attr_{mode}",
                            placeholder="例如: hasBike",
                            help="Agent 必须具有此属性才能使用该接驳模式"
                        )

                        ae_config['person_filter_value'] = st.text_input(
                            "人员过滤值 / personFilterValue",
                            value=ae_config.get('person_filter_value', ''),
                            key=f"raptor_person_val_{mode}",
                            placeholder="例如: true",
                            help="Agent 属性必须等于此值"
                        )

                        if ae_config.get('person_filter_attribute'):
                            st.caption(
                                f"✅ 只有属性 `{ae_config['person_filter_attribute']}` "
                                f"= `{ae_config.get('person_filter_value', '(任意值)')}` 的 Agent 可用"
                            )

                    # ===== 修复：使用 checkbox 代替嵌套 expander =====
                    st.markdown("---")
                    show_examples = st.checkbox(
                        "📚 显示过滤器使用示例",
                        value=False,
                        key=f"show_filter_examples_{mode}",
                        help="展开查看 XML 配置示例"
                    )

                    if show_examples:
                        st.markdown("""
                        <div class="info-box">
                        <b>站点过滤示例 / Stop Filter Example:</b>
                        </div>
                        """, unsafe_allow_html=True)

                        st.code("""
<!-- transitSchedule.xml 中的站点定义 -->
<stopFacility id="stop_001" x="..." y="...">
    <attributes>
        <attribute name="accessMode" class="java.lang.String">walk</attribute>
    </attributes>
</stopFacility>
                        """, language="xml")

                        st.markdown("""
                        **配置：** `stopFilterAttribute = "accessMode"`, `stopFilterValue = "walk"`

                        **结果：** 只有标记为可步行接驳的站点才能使用 walk 模式。
                        """)

                        st.markdown("---")

                        st.markdown("""
                        <div class="info-box">
                        <b>人员过滤示例 / Person Filter Example:</b>
                        </div>
                        """, unsafe_allow_html=True)

                        st.code("""
<!-- plans.xml 中的 person 定义 -->
<person id="person_001">
    <attributes>
        <attribute name="hasBike" class="java.lang.Boolean">true</attribute>
    </attributes>
</person>
                        """, language="xml")

                        st.markdown("""
                        **配置：** `personFilterAttribute = "hasBike"`, `personFilterValue = "true"`

                        **结果：** 只有拥有自行车的 Agent 才能使用 bike 接驳模式。
                        """)

                    access_egress_config[mode] = ae_config

            st.session_state.access_egress_config = access_egress_config

            # 全局参数总结
            st.markdown("---")
            st.markdown("#### 📊 接驳配置摘要 / Access/Egress Configuration Summary")

            summary_data = []
            for mode in enabled_ae:
                cfg = access_egress_config.get(mode, {})
                tele_cfg = st.session_state.get('teleported_modes', {}).get(mode, {})

                max_r = cfg.get('max_radius', 1000.0)
                speed = tele_cfg.get('speed_kmh', 5.0)
                max_time = (max_r / (speed / 3.6)) / 60  # 转换为分钟

                summary_data.append({
                    '模式': mode,
                    '显示名': tele_cfg.get('display_name', mode),
                    '速度 (km/h)': f"{speed:.1f}",
                    '最大半径 (m)': f"{max_r:.0f}",
                    '最大时间 (min)': f"{max_time:.1f}",
                    '初始半径 (m)': f"{cfg.get('initial_search_radius', 500.0):.0f}",
                    '扩展半径 (m)': f"{cfg.get('search_extension_radius', 200.0):.0f}",
                })

            # 使用 st.dataframe 显示表格
            import pandas as pd
            df = pd.DataFrame(summary_data)
            st.dataframe(df, use_container_width=True, hide_index=True)

    st.session_state.swiss_rail_raptor_config = raptor
    #st.session_state.swiss_rail_raptor_config = raptor
# ============================================================
# XML 生成函数 / XML Generation Functions
# ============================================================

def generate_config_xml() -> str:
    """生成完整的config.xml内容"""

    # 获取模式配置（使用新的数据结构）
    network_modes = st.session_state.get('network_modes', {})
    teleported_modes = st.session_state.get('teleported_modes', {})
    transit_enabled = st.session_state.get('transit_enabled', False)
    transit_submodes = st.session_state.get('transit_submodes', {})
    access_egress_config = st.session_state.get('access_egress_config', {})
    routing_cfg = st.session_state.get('routing_config', {})
    scoring_cfg = st.session_state.get('scoring_config', {})
    scoring_params = st.session_state.get('scoring_parameters', {}).get(None, {})
    smc = st.session_state.get('subtour_mode_choice_config', {})
    tam_cfg = st.session_state.get('time_allocation_mutator_config', {})
    transit_cfg = st.session_state.get('transit_config', {})
    tr_cfg = st.session_state.get('transit_router_config', {})
    raptor_cfg = st.session_state.get('swiss_rail_raptor_config', {})
    ttc_cfg = st.session_state.get('travel_time_calculator_config', {})
    vsp_cfg = st.session_state.get('vsp_experimental_config', {})

    # 计算模式列表
    network_mode_names = list(network_modes.keys())
    teleported_mode_names = list(teleported_modes.keys())
    choosable_modes = ModeManager.get_choosable_modes()
    chain_modes = ModeManager.get_chain_based_modes()
    enabled_access_egress = ModeManager.get_enabled_access_egress_modes()

    # 创建根元素
    root = ET.Element('config')

    # ===== TravelTimeCalculator Module =====
    ttc_module = ET.SubElement(root, 'module', name='travelTimeCalculator')

    ET.SubElement(ttc_module, 'param', name='travelTimeBinSize',
                  value=str(ttc_cfg.get('travelTimeBinSize', 900.0)))
    ET.SubElement(ttc_module, 'param', name='maxTime',
                  value=str(int(ttc_cfg.get('maxTime', 108000))))
    ET.SubElement(ttc_module, 'param', name='travelTimeAggregator',
                  value=ttc_cfg.get('travelTimeAggregator', 'optimistic'))
    ET.SubElement(ttc_module, 'param', name='travelTimeGetter',
                  value=ttc_cfg.get('travelTimeGetter', 'average'))
    ET.SubElement(ttc_module, 'param', name='calculateLinkTravelTimes',
                  value=str(ttc_cfg.get('calculateLinkTravelTimes', True)).lower())
    ET.SubElement(ttc_module, 'param', name='calculateLinkToLinkTravelTimes',
                  value=str(ttc_cfg.get('calculateLinkToLinkTravelTimes', False)).lower())
    ET.SubElement(ttc_module, 'param', name='analyzedModes',
                  value=ttc_cfg.get('analyzedModes', 'car'))
    ET.SubElement(ttc_module, 'param', name='filterModes',
                  value=str(ttc_cfg.get('filterModes', False)).lower())
    ET.SubElement(ttc_module, 'param', name='separateModes',
                  value=str(ttc_cfg.get('separateModes', True)).lower())

    # ===== Vehicles Module =====
    vehicles_file = st.session_state.file_config.get('vehiclesFile', '')
    if vehicles_file:
        vehicles_module = ET.SubElement(root, 'module', name='vehicles')
        ET.SubElement(vehicles_module, 'param', name='vehiclesFile', value=vehicles_file)

    # ===== VspExperimental Module =====
    vsp_module = ET.SubElement(root, 'module', name='vspExperimental')

    ET.SubElement(vsp_module, 'param', name='vspDefaultsCheckingLevel',
                  value=vsp_cfg.get('vspDefaultsCheckingLevel', 'ignore'))
    ET.SubElement(vsp_module, 'param', name='logitScaleParamForPlansRemoval',
                  value=str(vsp_cfg.get('logitScaleParamForPlansRemoval', 1.0)))
    ET.SubElement(vsp_module, 'param', name='isGeneratingBoardingDeniedEvent',
                  value=str(vsp_cfg.get('isGeneratingBoardingDeniedEvent', False)).lower())
    ET.SubElement(vsp_module, 'param', name='isAbleToOverwritePtInteractionParams',
                  value=str(vsp_cfg.get('isAbleToOverwritePtInteractionParams', False)).lower())
    ET.SubElement(vsp_module, 'param', name='isUsingOpportunityCostOfTimeForLocationChoice',
                  value=str(vsp_cfg.get('isUsingOpportunityCostOfTimeForLocationChoice', True)).lower())
    ET.SubElement(vsp_module, 'param', name='writingOutputEvents',
                  value=str(vsp_cfg.get('writingOutputEvents', True)).lower())

    # ===== 1. Global Module =====
    global_module = ET.SubElement(root, 'module', name='global')
    gc = st.session_state.global_config
    ET.SubElement(global_module, 'param', name='randomSeed', value=str(gc['randomSeed']))
    ET.SubElement(global_module, 'param', name='numberOfThreads', value=str(gc['numberOfThreads']))
    ET.SubElement(global_module, 'param', name='coordinateSystem', value=gc['coordinateSystem'])
    # GlobalConfigGroup.defaultDelimiter
    if gc.get('defaultDelimiter'):
        ET.SubElement(global_module, 'param', name='defaultDelimiter', value=gc['defaultDelimiter'])
    # GlobalConfigGroup.insistingOnDeprecatedConfigVersion
    ET.SubElement(
        global_module,
        'param',
        name='insistingOnDeprecatedConfigVersion',
        value=str(bool(gc.get('insistingOnDeprecatedConfigVersion', True))).lower()
    )


    # ===== 2. Network Module =====
    network_module = ET.SubElement(root, 'module', name='network')
    net_cfg = st.session_state.get('network_config', {})
    network_file = st.session_state.file_config.get('networkFile', 'network.xml.gz')

    # inputNetworkFile
    ET.SubElement(
        network_module,
        'param',
        name='inputNetworkFile',
        value=network_file if network_file else 'network.xml.gz'
    )

    # timeVariantNetwork
    ET.SubElement(
        network_module,
        'param',
        name='timeVariantNetwork',
        value=str(bool(net_cfg.get('timeVariantNetwork', False))).lower()
    )

    # inputChangeEventsFile
    if net_cfg.get('inputChangeEventsFile', '').strip():
        ET.SubElement(
            network_module,
            'param',
            name='inputChangeEventsFile',
            value=net_cfg['inputChangeEventsFile'].strip()
        )

    # laneDefinitionsFile
    if net_cfg.get('laneDefinitionsFile', '').strip():
        ET.SubElement(
            network_module,
            'param',
            name='laneDefinitionsFile',
            value=net_cfg['laneDefinitionsFile'].strip()
        )

    # inputCRS（Deprecated）
    if net_cfg.get('inputCRS', '').strip():
        ET.SubElement(
            network_module,
            'param',
            name='inputCRS',
            value=net_cfg['inputCRS'].strip()
        )

    # ===== TimeAllocationMutator Module =====
    tam_module = ET.SubElement(root, 'module', name='timeAllocationMutator')

    ET.SubElement(tam_module, 'param', name='mutationRange',
                  value=str(tam_cfg.get('mutationRange', 1800.0)))
    ET.SubElement(tam_module, 'param', name='mutationAffectsDuration',
                  value=str(tam_cfg.get('mutationAffectsDuration', True)).lower())
    ET.SubElement(tam_module, 'param', name='latestActivityEndTime',
                  value=tam_cfg.get('latestActivityEndTime', '24:00:00'))
    ET.SubElement(tam_module, 'param', name='mutationRangeStep',
                  value=str(tam_cfg.get('mutationRangeStep', 1.0)))
    ET.SubElement(tam_module, 'param', name='mutateAroundInitialEndTimeOnly',
                  value=str(tam_cfg.get('mutateAroundInitialEndTimeOnly', False)).lower())

    # ===== Transit Module =====
    if transit_enabled:
        transit_module = ET.SubElement(root, 'module', name='transit')

        ET.SubElement(transit_module, 'param', name='useTransit', value='true')
        ET.SubElement(transit_module, 'param', name='transitModes',
                      value=transit_cfg.get('transitModes', 'pt'))

        # 文件路径
        schedule_file = st.session_state.file_config.get('transitScheduleFile', '')
        vehicles_file = st.session_state.file_config.get('transitVehiclesFile', '')
        if schedule_file:
            ET.SubElement(transit_module, 'param', name='transitScheduleFile', value=schedule_file)
        if vehicles_file:
            ET.SubElement(transit_module, 'param', name='vehiclesFile', value=vehicles_file)

        ET.SubElement(transit_module, 'param', name='routingAlgorithmType',
                      value=transit_cfg.get('routingAlgorithmType', 'SwissRailRaptor'))
        ET.SubElement(transit_module, 'param', name='usingTransitInMobsim',
                      value=str(transit_cfg.get('usingTransitInMobsim', True)).lower())

        if transit_cfg.get('inputScheduleCRS'):
            ET.SubElement(transit_module, 'param', name='inputScheduleCRS',
                          value=transit_cfg['inputScheduleCRS'])

        # 废弃参数（如果启用）
        if transit_cfg.get('insistingOnUsingDeprecatedAttributeFiles', False):
            ET.SubElement(transit_module, 'param', name='insistingOnUsingDeprecatedAttributeFiles',
                          value='true')
            if transit_cfg.get('transitLinesAttributesFile'):
                ET.SubElement(transit_module, 'param', name='transitLinesAttributesFile',
                              value=transit_cfg['transitLinesAttributesFile'])
            if transit_cfg.get('transitStopsAttributesFile'):
                ET.SubElement(transit_module, 'param', name='transitStopsAttributesFile',
                              value=transit_cfg['transitStopsAttributesFile'])

    # ===== TransitRouter Module =====
    if transit_enabled:
        tr_module = ET.SubElement(root, 'module', name='transitRouter')

        ET.SubElement(tr_module, 'param', name='searchRadius',
                      value=str(tr_cfg.get('searchRadius', 1000.0)))
        ET.SubElement(tr_module, 'param', name='extensionRadius',
                      value=str(tr_cfg.get('extensionRadius', 200.0)))
        ET.SubElement(tr_module, 'param', name='maxBeelineWalkConnectionDistance',
                      value=str(tr_cfg.get('maxBeelineWalkConnectionDistance', 100.0)))
        ET.SubElement(tr_module, 'param', name='additionalTransferTime',
                      value=str(tr_cfg.get('additionalTransferTime', 0.0)))
        ET.SubElement(tr_module, 'param', name='directWalkFactor',
                      value=str(tr_cfg.get('directWalkFactor', 1.0)))

    # ===== SwissRailRaptor Module =====
    if transit_enabled and raptor_cfg.get('useIntermodalAccessEgress', False):
        raptor_module = ET.SubElement(root, 'module', name='swissRailRaptor')

        # 顶层参数
        ET.SubElement(raptor_module, 'param', name='useRangeQuery',
                      value=str(raptor_cfg.get('useRangeQuery', False)).lower())
        ET.SubElement(raptor_module, 'param', name='useIntermodalAccessEgress',
                      value=str(raptor_cfg.get('useIntermodalAccessEgress', True)).lower())
        ET.SubElement(raptor_module, 'param', name='intermodalAccessEgressModeSelection',
                      value=raptor_cfg.get('intermodalAccessEgressModeSelection', 'CalcLeastCostModePerStop'))
        ET.SubElement(raptor_module, 'param', name='useModeMappingForPassengers',
                      value=str(raptor_cfg.get('useModeMappingForPassengers', False)).lower())
        ET.SubElement(raptor_module, 'param', name='useCapacityConstraints',
                      value=str(raptor_cfg.get('useCapacityConstraints', False)).lower())
        ET.SubElement(raptor_module, 'param', name='scoringParameters',
                      value=raptor_cfg.get('scoringParameters', 'Default'))

        # 换乘惩罚参数
        ET.SubElement(raptor_module, 'param', name='transferPenaltyBaseCost',
                      value=str(raptor_cfg.get('transferPenaltyBaseCost', 0.0)))

        if raptor_cfg.get('transferPenaltyMinCost') is not None:
            ET.SubElement(raptor_module, 'param', name='transferPenaltyMinCost',
                          value=str(raptor_cfg['transferPenaltyMinCost']))

        if raptor_cfg.get('transferPenaltyMaxCost') is not None:
            ET.SubElement(raptor_module, 'param', name='transferPenaltyMaxCost',
                          value=str(raptor_cfg['transferPenaltyMaxCost']))

        ET.SubElement(raptor_module, 'param', name='transferPenaltyCostPerTravelTimeHour',
                      value=str(raptor_cfg.get('transferPenaltyCostPerTravelTimeHour', 0.0)))
        ET.SubElement(raptor_module, 'param', name='transferWalkMargin',
                      value=str(raptor_cfg.get('transferWalkMargin', 5.0)))
        ET.SubElement(raptor_module, 'param', name='intermodalLegOnlyHandling',
                      value=raptor_cfg.get('intermodalLegOnlyHandling', 'forbid'))
        ET.SubElement(raptor_module, 'param', name='transferCalculation',
                      value=raptor_cfg.get('transferCalculation', 'Initial'))

        # 接驳模式参数集
        access_egress_config = st.session_state.get('access_egress_config', {})
        teleported_modes = st.session_state.get('teleported_modes', {})
        extension_radius = st.session_state.get('transit_extension_radius', 200.0)

        for mode_name, ae_config in access_egress_config.items():
            if not ae_config.get('enabled', False):
                continue

            ae_ps = ET.SubElement(raptor_module, 'parameterset', type='intermodalAccessEgress')
            ET.SubElement(ae_ps, 'param', name='mode', value=mode_name)
            ET.SubElement(ae_ps, 'param', name='maxRadius',
                          value=str(ae_config.get('max_radius', 1000.0)))
            ET.SubElement(ae_ps, 'param', name='initialSearchRadius',
                          value=str(ae_config.get('initial_search_radius', 500.0)))
            ET.SubElement(ae_ps, 'param', name='searchExtensionRadius',
                          value=str(ae_config.get('search_extension_radius', extension_radius)))

            # 可选参数
            if ae_config.get('stop_filter_attribute'):
                ET.SubElement(ae_ps, 'param', name='stopFilterAttribute',
                              value=ae_config['stop_filter_attribute'])
            if ae_config.get('stop_filter_value'):
                ET.SubElement(ae_ps, 'param', name='stopFilterValue',
                              value=ae_config['stop_filter_value'])
            if ae_config.get('person_filter_attribute'):
                ET.SubElement(ae_ps, 'param', name='personFilterAttribute',
                              value=ae_config['person_filter_attribute'])
            if ae_config.get('person_filter_value'):
                ET.SubElement(ae_ps, 'param', name='personFilterValue',
                              value=ae_config['person_filter_value'])

    # ===== 3. Plans Module =====
    plans_module = ET.SubElement(root, 'module', name='plans')
    plans_file = st.session_state.file_config.get('plansFile', 'plans.xml.gz')
    ET.SubElement(plans_module, 'param', name='inputPlansFile', value=plans_file)

    # ===== 4. Controller Module =====
    controller_module = ET.SubElement(root, 'module', name='controller')
    ctrl = st.session_state.controller_config

    # 基本
    ET.SubElement(controller_module, 'param', name='outputDirectory', value=str(ctrl.get('outputDirectory', './output')))
    ET.SubElement(controller_module, 'param', name='runId', value=str(ctrl.get('runId', 'run001')))
    ET.SubElement(controller_module, 'param', name='firstIteration', value=str(ctrl.get('firstIteration', 0)))
    ET.SubElement(controller_module, 'param', name='lastIteration', value=str(ctrl.get('lastIteration', 100)))

    # 仿真引擎 / 路由
    ET.SubElement(controller_module, 'param', name='mobsim', value=str(ctrl.get('mobsim', 'qsim')))
    ET.SubElement(controller_module, 'param', name='routingAlgorithmType',
                  value=str(ctrl.get('routingAlgorithmType', 'SpeedyALT')))
    ET.SubElement(controller_module, 'param', name='enableLinkToLinkRouting',
                  value=str(bool(ctrl.get('enableLinkToLinkRouting', False))).lower())
    ET.SubElement(controller_module, 'param', name='createScoringFunctionType',
                  value=str(ctrl.get('createScoringFunctionType', 'IterationStarts')))

    # 输出频率
    ET.SubElement(controller_module, 'param', name='writeEventsInterval',
                  value=str(ctrl.get('writeEventsInterval', 50)))
    ET.SubElement(controller_module, 'param', name='writePlansInterval',
                  value=str(ctrl.get('writePlansInterval', 50)))
    ET.SubElement(controller_module, 'param', name='writeTripsInterval',
                  value=str(ctrl.get('writeTripsInterval', 50)))
    ET.SubElement(controller_module, 'param', name='writeSnapshotsInterval',
                  value=str(ctrl.get('writeSnapshotsInterval', 1)))

    # 文件格式与压缩
    events_formats = ctrl.get('eventsFileFormat', ['xml'])
    if events_formats:
        ET.SubElement(controller_module, 'param', name='eventsFileFormat',
                      value=",".join(events_formats))
    snapshot_formats = ctrl.get('snapshotFormat', [])
    if snapshot_formats:
        ET.SubElement(controller_module, 'param', name='snapshotFormat',
                      value=",".join(snapshot_formats))

    ET.SubElement(controller_module, 'param', name='overwriteFiles',
                  value=str(ctrl.get('overwriteFiles', 'deleteDirectoryIfExists')))
    ET.SubElement(controller_module, 'param', name='compressionType',
                  value=str(ctrl.get('compressionType', 'gzip')))

    # 图表与清理
    ET.SubElement(controller_module, 'param', name='createGraphsInterval',
                  value=str(ctrl.get('createGraphsInterval', 1)))
    ET.SubElement(controller_module, 'param', name='dumpDataAtEnd',
                  value=str(bool(ctrl.get('dumpDataAtEnd', True))).lower())
    ET.SubElement(controller_module, 'param', name='cleanItersAtEnd',
                  value=str(ctrl.get('cleanItersAtEnd', 'keep')))
    ET.SubElement(controller_module, 'param', name='memoryObserverInterval',
                  value=str(ctrl.get('memoryObserverInterval', 60)))


    # ===== 5. Mobsim-specific Modules =====
    if ctrl['mobsim'] == 'qsim':
        qsim_module = ET.SubElement(root, 'module', name='qsim')
        qsim = st.session_state.qsim_config

        # 时间相关
        if qsim.get('startTime'):
            ET.SubElement(qsim_module, 'param', name='startTime', value=qsim['startTime'])
        if qsim.get('endTime'):
            ET.SubElement(qsim_module, 'param', name='endTime', value=qsim['endTime'])
        ET.SubElement(qsim_module, 'param', name='timeStepSize', value=str(qsim.get('timeStepSize', 1.0)))

        # 流量与容量
        ET.SubElement(qsim_module, 'param', name='flowCapacityFactor',
                      value=str(qsim.get('flowCapacityFactor', 1.0)))
        ET.SubElement(qsim_module, 'param', name='storageCapacityFactor',
                      value=str(qsim.get('storageCapacityFactor', 1.0)))
        ET.SubElement(qsim_module, 'param', name='snapshotperiod',
                      value=str(qsim.get('snapshotPeriod', 0.0)))

        # 卡住与线程
        ET.SubElement(qsim_module, 'param', name='stuckTime', value=str(qsim.get('stuckTime', 10.0)))
        ET.SubElement(qsim_module, 'param', name='removeStuckVehicles',
                      value=str(bool(qsim.get('removeStuckVehicles', False))).lower())
        ET.SubElement(qsim_module, 'param', name='notifyAboutStuckVehicles',
                      value=str(bool(qsim.get('notifyAboutStuckVehicles', False))).lower())
        ET.SubElement(qsim_module, 'param', name='numberOfThreads',
                      value=str(int(qsim.get('numberOfThreads', 4))))

        # 动力学与时间解释
        ET.SubElement(qsim_module, 'param', name='trafficDynamics',
                      value=qsim.get('trafficDynamics', 'queue'))
        ET.SubElement(qsim_module, 'param', name='simStarttimeInterpretation',
                      value=qsim.get('simStarttimeInterpretation',
                                     'maxOfStarttimeAndEarliestActivityEnd'))
        ET.SubElement(qsim_module, 'param', name='simEndtimeInterpretation',
                      value=qsim.get('simEndtimeInterpretation',
                                     'minOfEndtimeAndMobsimFinished'))
        ET.SubElement(qsim_module, 'param', name='usePersonIdForMissingVehicleId',
                      value=str(bool(qsim.get('usePersonIdForMissingVehicleId', True))).lower())

        # 快照与 link 动力学
        ET.SubElement(qsim_module, 'param', name='filterSnapshots',
                      value=qsim.get('filterSnapshots', 'no'))
        ET.SubElement(qsim_module, 'param', name='linkDynamics',
                      value=qsim.get('linkDynamics', 'FIFO'))
        ET.SubElement(qsim_module, 'param', name='nodeOffset',
                      value=str(qsim.get('nodeOffset', 0.0)))

        # 渗流与车辆行为
        ET.SubElement(qsim_module, 'param', name='isSeepModeStorageFree',
                      value=str(bool(qsim.get('isSeepModeStorageFree', True))).lower())
        ET.SubElement(qsim_module, 'param', name='vehicleBehavior',
                      value=qsim.get('vehicleBehavior', 'teleport'))
        ET.SubElement(qsim_module, 'param', name='snapshotStyle',
                      value=qsim.get('snapshotStyle', 'queue'))
        ET.SubElement(qsim_module, 'param', name='vehiclesSource',
                      value=qsim.get('vehiclesSource', 'defaultVehicle'))
        ET.SubElement(qsim_module, 'param',
                      name='insertingWaitingVehiclesBeforeDrivingVehicles',
                      value=str(bool(qsim.get('insertingWaitingVehiclesBeforeDrivingVehicles', True))).lower())

        # 车道与渗流模式
        ET.SubElement(qsim_module, 'param', name='useLanes',
                      value=str(bool(qsim.get('useLanes', False))).lower())
        if qsim.get('seepMode'):
            ET.SubElement(qsim_module, 'param', name='seepMode', value=qsim['seepMode'])
        ET.SubElement(qsim_module, 'param', name='isRestrictingSeepage',
                      value=str(bool(qsim.get('isRestrictingSeepage', True))).lower())

        # mainMode = 网络模式集合（自动生成）
        if network_mode_names:
            ET.SubElement(qsim_module, 'param', name='mainMode', value=','.join(network_mode_names))

    elif ctrl['mobsim'] == 'hermes':
        hermes_module = ET.SubElement(root, 'module', name='hermes')
        hermes = st.session_state.hermes_config

        # Hermes 结束时间
        if hermes.get('endTime'):
            ET.SubElement(hermes_module, 'param', name='endTime', value=hermes['endTime'])

        # 容量控制
        ET.SubElement(hermes_module, 'param', name='flowCapacityFactor',
                      value=str(hermes.get('flowCapacityFactor', 1.0)))
        ET.SubElement(hermes_module, 'param', name='storageCapacityFactor',
                      value=str(hermes.get('storageCapacityFactor', 1.0)))

        # 卡住时间
        ET.SubElement(hermes_module, 'param', name='stuckTime',
                      value=str(int(hermes.get('stuckTime', 10))))

        # PT 仿真模式
        ET.SubElement(hermes_module, 'param', name='useDeterministicPt',
                      value=str(bool(hermes.get('useDeterministicPt', False))).lower())

        # mainMode 同样自动根据网络模式生成
        if network_mode_names:
            ET.SubElement(hermes_module, 'param', name='mainMode', value=','.join(network_mode_names))

    # ===== 更新：Routing Module =====
    routing_module = ET.SubElement(root, 'module', name='routing')

    # networkModes
    if network_mode_names:
        ET.SubElement(routing_module, 'param', name='networkModes', value=','.join(network_mode_names))

    # 顶层参数
    ET.SubElement(routing_module, 'param', name='routingRandomness',
                  value=str(routing_cfg.get('routingRandomness', 3.0)))
    ET.SubElement(routing_module, 'param', name='clearDefaultTeleportedModeParams',
                  value=str(routing_cfg.get('clearDefaultTeleportedModeParams', False)).lower())
    ET.SubElement(routing_module, 'param', name='accessEgressType',
                  value=routing_cfg.get('accessEgressType', 'none'))
    ET.SubElement(routing_module, 'param', name='networkRouteConsistencyCheck',
                  value=routing_cfg.get('networkRouteConsistencyCheck', 'abortOnInconsistency'))

    # 传送模式参数
    for mode_name, mode_config in teleported_modes.items():
        tele_params = ET.SubElement(routing_module, 'parameterset', type='teleportedModeParameters')
        ET.SubElement(tele_params, 'param', name='mode', value=mode_name)
        ET.SubElement(tele_params, 'param', name='beelineDistanceFactor',
                      value=str(mode_config.get('beeline_factor', 1.3)))

        # 使用速度或自由流因子
        freespeed_factor = mode_config.get('freespeed_factor')
        if freespeed_factor and freespeed_factor > 0:
            ET.SubElement(tele_params, 'param', name='teleportedModeFreespeedFactor',
                          value=str(freespeed_factor))
        else:
            speed_ms = mode_config.get('speed_kmh', 5.0) / 3.6
            ET.SubElement(tele_params, 'param', name='teleportedModeSpeed', value=f"{speed_ms:.4f}")

    # ===== 7. Transit Module =====
    if transit_enabled:
        transit_module = ET.SubElement(root, 'module', name='transit')
        ET.SubElement(transit_module, 'param', name='useTransit', value='true')
        ET.SubElement(transit_module, 'param', name='transitModes', value='pt')

        schedule_file = st.session_state.file_config.get('transitScheduleFile', 'transitSchedule.xml')
        vehicles_file = st.session_state.file_config.get('transitVehiclesFile', 'transitVehicles.xml')
        ET.SubElement(transit_module, 'param', name='transitScheduleFile', value=schedule_file)
        ET.SubElement(transit_module, 'param', name='vehiclesFile', value=vehicles_file)

        # ===== 8. SwissRailRaptor Module（多模式接驳配置） =====
        if enabled_access_egress:
            raptor_module = ET.SubElement(root, 'module', name='swissRailRaptor')
            ET.SubElement(raptor_module, 'param', name='useIntermodalAccessEgress', value='true')

            extension_radius = st.session_state.get('transit_extension_radius', 200.0)
            ET.SubElement(raptor_module, 'param', name='intermodalAccessEgressModeSelection',
                          value='CalcLeastCostModePerStop')

            # 每种启用的接驳模式单独配置
            for ae_mode in enabled_access_egress:
                ae_config = access_egress_config.get(ae_mode, {})
                tele_config = teleported_modes.get(ae_mode, {})

                ae_params = ET.SubElement(raptor_module, 'parameterset', type='intermodalAccessEgress')
                ET.SubElement(ae_params, 'param', name='mode', value=ae_mode)
                ET.SubElement(ae_params, 'param', name='maxRadius', value=str(ae_config.get('max_radius', 1000.0)))
                ET.SubElement(ae_params, 'param', name='initialSearchRadius',
                              value=str(ae_config.get('initial_search_radius', 500.0)))
                ET.SubElement(ae_params, 'param', name='searchExtensionRadius', value=str(extension_radius))
                # 使用传送模式的速度
                speed_ms = tele_config.get('speed_kmh', 5.0) / 3.6
                ET.SubElement(ae_params, 'param', name='linkIdAttribute', value='null')
                ET.SubElement(ae_params, 'param', name='personFilterAttribute', value='null')
                ET.SubElement(ae_params, 'param', name='stopFilterAttribute', value='null')

    # ===== 9. Scoring Module =====
    # ===== 9. Scoring Module =====
    scoring_module = ET.SubElement(root, 'module', name='scoring')

    # 顶层参数 (ReflectiveDelegate)
    ET.SubElement(scoring_module, 'param', name='learningRate',
                  value=str(scoring_cfg.get('learningRate', 1.0)))
    ET.SubElement(scoring_module, 'param', name='brainExpBeta',
                  value=str(scoring_cfg.get('brainExpBeta', 1.0)))
    ET.SubElement(scoring_module, 'param', name='pathSizeLogitBeta',
                  value=str(scoring_cfg.get('pathSizeLogitBeta', 1.0)))
    ET.SubElement(scoring_module, 'param', name='writeExperiencedPlans',
                  value=str(scoring_cfg.get('writeExperiencedPlans', False)).lower())

    if scoring_cfg.get('fractionOfIterationsToStartScoreMSA') is not None:
        ET.SubElement(scoring_module, 'param', name='fractionOfIterationsToStartScoreMSA',
                      value=str(scoring_cfg['fractionOfIterationsToStartScoreMSA']))

    ET.SubElement(scoring_module, 'param', name='usingOldScoringBelowZeroUtilityDuration',
                  value=str(scoring_cfg.get('usingOldScoringBelowZeroUtilityDuration', False)).lower())
    ET.SubElement(scoring_module, 'param', name='writeScoreExplanations',
                  value=str(scoring_cfg.get('writeScoreExplanations', False)).lower())

    # scoringParameters (默认子人口)
    scoring_ps = ET.SubElement(scoring_module, 'parameterset', type='scoringParameters')

    # 全局效用参数
    ET.SubElement(scoring_ps, 'param', name='lateArrival',
                  value=str(scoring_params.get('lateArrival', -18.0)))
    ET.SubElement(scoring_ps, 'param', name='earlyDeparture',
                  value=str(scoring_params.get('earlyDeparture', 0.0)))
    ET.SubElement(scoring_ps, 'param', name='performing',
                  value=str(scoring_params.get('performing', 6.0)))
    ET.SubElement(scoring_ps, 'param', name='waiting',
                  value=str(scoring_params.get('waiting', 0.0)))
    ET.SubElement(scoring_ps, 'param', name='marginalUtilityOfMoney',
                  value=str(scoring_params.get('marginalUtilityOfMoney', 1.0)))
    ET.SubElement(scoring_ps, 'param', name='utilityOfLineSwitch',
                  value=str(scoring_params.get('utilityOfLineSwitch', -1.0)))

    if scoring_params.get('waitingPt') is not None:
        ET.SubElement(scoring_ps, 'param', name='waitingPt',
                      value=str(scoring_params['waitingPt']))

    # activityParams (嵌套)
    for act_type, act_params in st.session_state.activity_params.items():
        act_ps = ET.SubElement(scoring_ps, 'parameterset', type='activityParams')
        ET.SubElement(act_ps, 'param', name='activityType', value=act_type)
        ET.SubElement(act_ps, 'param', name='typicalDuration',
                      value=act_params.get('typicalDuration', '01:00:00'))

        if act_params.get('priority', 1.0) != 1.0:
            ET.SubElement(act_ps, 'param', name='priority', value=str(act_params['priority']))
        if act_params.get('minimalDuration'):
            ET.SubElement(act_ps, 'param', name='minimalDuration', value=act_params['minimalDuration'])
        if act_params.get('openingTime'):
            ET.SubElement(act_ps, 'param', name='openingTime', value=act_params['openingTime'])
        if act_params.get('latestStartTime'):
            ET.SubElement(act_ps, 'param', name='latestStartTime', value=act_params['latestStartTime'])
        if act_params.get('earliestEndTime'):
            ET.SubElement(act_ps, 'param', name='earliestEndTime', value=act_params['earliestEndTime'])
        if act_params.get('closingTime'):
            ET.SubElement(act_ps, 'param', name='closingTime', value=act_params['closingTime'])

        ET.SubElement(act_ps, 'param', name='scoringThisActivityAtAll',
                      value=str(act_params.get('scoringThisActivityAtAll', True)).lower())
        ET.SubElement(act_ps, 'param', name='typicalDurationScoreComputation',
                      value=act_params.get('typicalDurationScoreComputation', 'relative'))

    # modeParams (嵌套) - 网络模式
    for mode_name, mode_config in network_modes.items():
        scoring = mode_config.get('scoring', {})
        mode_ps = ET.SubElement(scoring_ps, 'parameterset', type='modeParams')
        ET.SubElement(mode_ps, 'param', name='mode', value=mode_name)
        ET.SubElement(mode_ps, 'param', name='constant', value=str(scoring.get('constant', 0.0)))
        ET.SubElement(mode_ps, 'param', name='marginalUtilityOfTraveling_util_hr',
                      value=str(scoring.get('marginalUtilityOfTraveling_util_hr', -6.0)))
        ET.SubElement(mode_ps, 'param', name='marginalUtilityOfDistance_util_m',
                      value=str(scoring.get('marginalUtilityOfDistance_util_m', 0.0)))
        ET.SubElement(mode_ps, 'param', name='monetaryDistanceRate',
                      value=str(scoring.get('monetaryDistanceRate', 0.0)))
        ET.SubElement(mode_ps, 'param', name='dailyMonetaryConstant',
                      value=str(scoring.get('dailyMonetaryConstant', 0.0)))
        ET.SubElement(mode_ps, 'param', name='dailyUtilityConstant',
                      value=str(scoring.get('dailyUtilityConstant', 0.0)))

    # modeParams (嵌套) - 传送模式
    for mode_name, mode_config in teleported_modes.items():
        scoring = mode_config.get('scoring', {})
        mode_ps = ET.SubElement(scoring_ps, 'parameterset', type='modeParams')
        ET.SubElement(mode_ps, 'param', name='mode', value=mode_name)
        ET.SubElement(mode_ps, 'param', name='constant', value=str(scoring.get('constant', 0.0)))
        ET.SubElement(mode_ps, 'param', name='marginalUtilityOfTraveling_util_hr',
                      value=str(scoring.get('marginalUtilityOfTraveling_util_hr', -6.0)))
        ET.SubElement(mode_ps, 'param', name='marginalUtilityOfDistance_util_m',
                      value=str(scoring.get('marginalUtilityOfDistance_util_m', 0.0)))
        ET.SubElement(mode_ps, 'param', name='monetaryDistanceRate',
                      value=str(scoring.get('monetaryDistanceRate', 0.0)))
        ET.SubElement(mode_ps, 'param', name='dailyMonetaryConstant',
                      value=str(scoring.get('dailyMonetaryConstant', 0.0)))
        ET.SubElement(mode_ps, 'param', name='dailyUtilityConstant',
                      value=str(scoring.get('dailyUtilityConstant', 0.0)))

    # modeParams - pt
    if transit_enabled:
        pt_scoring = st.session_state.get('pt_scoring', {})
        mode_ps = ET.SubElement(scoring_ps, 'parameterset', type='modeParams')
        ET.SubElement(mode_ps, 'param', name='mode', value='pt')
        ET.SubElement(mode_ps, 'param', name='constant', value=str(pt_scoring.get('constant', -1.0)))
        ET.SubElement(mode_ps, 'param', name='marginalUtilityOfTraveling_util_hr',
                      value=str(pt_scoring.get('marginalUtilityOfTraveling_util_hr', -3.0)))
        ET.SubElement(mode_ps, 'param', name='marginalUtilityOfDistance_util_m',
                      value=str(pt_scoring.get('marginalUtilityOfDistance_util_m', 0.0)))
        ET.SubElement(mode_ps, 'param', name='monetaryDistanceRate',
                      value=str(pt_scoring.get('monetaryDistanceRate', 0.0)))
        ET.SubElement(mode_ps, 'param', name='dailyMonetaryConstant',
                      value=str(pt_scoring.get('dailyMonetaryConstant', -2.5)))
        ET.SubElement(mode_ps, 'param', name='dailyUtilityConstant',
                      value=str(pt_scoring.get('dailyUtilityConstant', 0.0)))

        # 公交子模式评分（如果启用分别评分）
        if st.session_state.get('transit_separate_scoring', False):
            for mode_name, mode_config in transit_submodes.items():
                if not mode_config.get('enabled', True):
                    continue
                scoring = mode_config.get('scoring', {})
                mode_ps = ET.SubElement(scoring_ps, 'parameterset', type='modeParams')
                ET.SubElement(mode_ps, 'param', name='mode', value=mode_name)
                ET.SubElement(mode_ps, 'param', name='constant', value=str(scoring.get('constant', -1.0)))
                ET.SubElement(mode_ps, 'param', name='marginalUtilityOfTraveling_util_hr',
                              value=str(scoring.get('marginalUtilityOfTraveling_util_hr', -3.0)))
                ET.SubElement(mode_ps, 'param', name='marginalUtilityOfDistance_util_m',
                              value=str(scoring.get('marginalUtilityOfDistance_util_m', 0.0)))
                ET.SubElement(mode_ps, 'param', name='monetaryDistanceRate',
                              value=str(scoring.get('monetaryDistanceRate', 0.0)))
                ET.SubElement(mode_ps, 'param', name='dailyMonetaryConstant',
                              value=str(scoring.get('dailyMonetaryConstant', -2.0)))
                ET.SubElement(mode_ps, 'param', name='dailyUtilityConstant',
                              value=str(scoring.get('dailyUtilityConstant', 0.0)))

    # ===== 10. Replanning Module =====
    replanning_module = ET.SubElement(root, 'module', name='replanning')
    rp = st.session_state.replanning_config
    ET.SubElement(replanning_module, 'param', name='maxAgentPlanMemorySize',
                  value=str(rp['maxAgentPlanMemorySize']))
    ET.SubElement(replanning_module, 'param', name='fractionOfIterationsToDisableInnovation',
                  value=str(rp['fractionOfIterationsToDisableInnovation']))

    for strategy in st.session_state.strategy_config:
        if strategy['weight'] > 0:
            strat_ps = ET.SubElement(replanning_module, 'parameterset', type='strategysettings')
            ET.SubElement(strat_ps, 'param', name='strategyName', value=strategy['name'])
            ET.SubElement(strat_ps, 'param', name='weight', value=str(strategy['weight']))

    # ===== 11. SubtourModeChoice Module =====
    # ===== 更新：SubtourModeChoice Module =====
    subtour_module = ET.SubElement(root, 'module', name='subtourModeChoice')

    # 模式列表
    modes = smc.get('modes', choosable_modes)
    if modes:
        ET.SubElement(subtour_module, 'param', name='modes', value=','.join(modes))

    chain_modes_list = smc.get('chainBasedModes', chain_modes)
    if chain_modes_list:
        ET.SubElement(subtour_module, 'param', name='chainBasedModes', value=','.join(chain_modes_list))

    # 行为参数
    ET.SubElement(subtour_module, 'param', name='considerCarAvailability',
                  value=str(smc.get('considerCarAvailability', False)).lower())
    ET.SubElement(subtour_module, 'param', name='behavior',
                  value=smc.get('behavior', 'fromSpecifiedModesToSpecifiedModes'))
    ET.SubElement(subtour_module, 'param', name='probaForRandomSingleTripMode',
                  value=str(smc.get('probaForRandomSingleTripMode', 0.0)))
    ET.SubElement(subtour_module, 'param', name='coordDistance',
                  value=str(smc.get('coordDistance', 0.0)))

    # ===== 12. TimeAllocationMutator =====
    time_module = ET.SubElement(root, 'module', name='timeAllocationMutator')
    ET.SubElement(time_module, 'param', name='mutationRange',
                  value=str(st.session_state.time_mutator_config['mutationRange']))

    # ===== 13. ChangeMode Module =====
    change_mode_module = ET.SubElement(root, 'module', name='changeMode')
    if choosable_modes:
        ET.SubElement(change_mode_module, 'param', name='modes', value=','.join(choosable_modes))

    # ===== 14. Counts Module =====
    counts_cfg = st.session_state.get('counts_config', {})
    counts_file = st.session_state.file_config.get('countsFile', '')
    if counts_file:
        counts_module = ET.SubElement(root, 'module', name='counts')
        # inputCountsFile 从 file_config 映射
        ET.SubElement(counts_module, 'param', name='inputCountsFile', value=counts_file)

        # outputformat
        ET.SubElement(counts_module, 'param', name='outputformat',
                      value=str(counts_cfg.get('outputFormat', 'txt')))

        # distanceFilter & distanceFilterCenterNode
        if counts_cfg.get('distanceFilter') is not None:
            ET.SubElement(counts_module, 'param', name='distanceFilter',
                          value=str(counts_cfg['distanceFilter']))
        if counts_cfg.get('distanceFilterCenterNode', '').strip():
            ET.SubElement(counts_module, 'param', name='distanceFilterCenterNode',
                          value=counts_cfg['distanceFilterCenterNode'].strip())

        # countsScaleFactor
        ET.SubElement(counts_module, 'param', name='countsScaleFactor',
                      value=str(counts_cfg.get('countsScaleFactor', 1.0)))

        # writeCountsInterval
        ET.SubElement(counts_module, 'param', name='writeCountsInterval',
                      value=str(counts_cfg.get('writeCountsInterval', 10)))

        # averageCountsOverIterations
        ET.SubElement(counts_module, 'param', name='averageCountsOverIterations',
                      value=str(counts_cfg.get('averageCountsOverIterations', 5)))

        # analyzedModes & filterModes
        if counts_cfg.get('analyzedModes', '').strip():
            ET.SubElement(counts_module, 'param', name='analyzedModes',
                          value=counts_cfg['analyzedModes'].strip())
        ET.SubElement(counts_module, 'param', name='filterModes',
                      value=str(counts_cfg.get('filterModes', False)).lower())

        # inputCRS（兼容老配置，可为空）
        if counts_cfg.get('inputCRS', '').strip():
            ET.SubElement(counts_module, 'param', name='inputCRS',
                          value=counts_cfg['inputCRS'].strip())

    # ===== 15. Facilities Module =====
    fac_cfg = st.session_state.get('facilities_config', {})
    fac_file = st.session_state.file_config.get('facilitiesFile', '').strip()

    # 如果提供了文件或启用了非 none 的来源或其他参数，则写出 facilities 模块
    if fac_file or fac_cfg.get('facilitiesSource', 'none') != 'none' \
            or fac_cfg.get('inputFacilityAttributesFile') or fac_cfg.get('inputCRS'):
        facilities_module = ET.SubElement(root, 'module', name='facilities')

        # inputFacilitiesFile
        if fac_file:
            ET.SubElement(
                facilities_module,
                'param',
                name='inputFacilitiesFile',
                value=fac_file
            )

        # inputFacilityAttributesFile
        if fac_cfg.get('inputFacilityAttributesFile', '').strip():
            ET.SubElement(
                facilities_module,
                'param',
                name='inputFacilityAttributesFile',
                value=fac_cfg['inputFacilityAttributesFile'].strip()
            )

        # inputCRS
        if fac_cfg.get('inputCRS', '').strip():
            ET.SubElement(
                facilities_module,
                'param',
                name='inputCRS',
                value=fac_cfg['inputCRS'].strip()
            )

        # facilitiesSource（总是写出，默认 none）
        if fac_cfg.get('facilitiesSource', 'none'):
            ET.SubElement(
                facilities_module,
                'param',
                name='facilitiesSource',
                value=fac_cfg.get('facilitiesSource', 'none')
            )

        # idPrefix（有值时写出）
        if fac_cfg.get('idPrefix', '').strip():
            ET.SubElement(
                facilities_module,
                'param',
                name='idPrefix',
                value=fac_cfg.get('idPrefix', 'f_auto_').strip()
            )

        # insistingOnUsingDeprecatedFacilitiesAttributeFile
        ET.SubElement(
            facilities_module,
            'param',
            name='insistingOnUsingDeprecatedFacilitiesAttributeFile',
            value=str(bool(fac_cfg.get('insistingOnUsingDeprecatedFacilitiesAttributeFile', False))).lower()
        )

    # ===== 16. Households Module =====
    hh_cfg = st.session_state.get('households_config', {})
    hh_file = st.session_state.file_config.get('householdsFile', '').strip()

    if hh_file or hh_cfg.get('inputHouseholdAttributesFile') \
            or hh_cfg.get('insistingOnUsingDeprecatedHouseholdsAttributeFile'):
        households_module = ET.SubElement(root, 'module', name='households')

        # inputFile
        if hh_file:
            ET.SubElement(
                households_module,
                'param',
                name='inputFile',
                value=hh_file
            )

        # inputHouseholdAttributesFile
        if hh_cfg.get('inputHouseholdAttributesFile', '').strip():
            ET.SubElement(
                households_module,
                'param',
                name='inputHouseholdAttributesFile',
                value=hh_cfg['inputHouseholdAttributesFile'].strip()
            )

        # insistingOnUsingDeprecatedHouseholdsAttributeFile
        ET.SubElement(
            households_module,
            'param',
            name='insistingOnUsingDeprecatedHouseholdsAttributeFile',
            value=str(bool(hh_cfg.get('insistingOnUsingDeprecatedHouseholdsAttributeFile', False))).lower()
        )


    # ===== 15. EventsManager Module =====
    em_cfg = st.session_state.get('events_manager_config', {})
    events_module = ET.SubElement(root, 'module', name='eventsManager')

    # numberOfThreads: 0 表示 UI 中“自动决定”，不写出
    if em_cfg.get('numberOfThreads', 0) > 0:
        ET.SubElement(events_module, 'param', name='numberOfThreads',
                      value=str(int(em_cfg['numberOfThreads'])))

    # estimatedNumberOfEvents: 0 表示不设置
    if em_cfg.get('estimatedNumberOfEvents', 0) > 0:
        ET.SubElement(events_module, 'param', name='estimatedNumberOfEvents',
                      value=str(int(em_cfg['estimatedNumberOfEvents'])))

    # synchronizeOnSimSteps & oneThreadPerHandler & eventsQueueSize
    ET.SubElement(events_module, 'param', name='synchronizeOnSimSteps',
                  value=str(em_cfg.get('synchronizeOnSimSteps', True)).lower())
    ET.SubElement(events_module, 'param', name='oneThreadPerHandler',
                  value=str(em_cfg.get('oneThreadPerHandler', False)).lower())
    ET.SubElement(events_module, 'param', name='eventsQueueSize',
                  value=str(int(em_cfg.get('eventsQueueSize', 131072))))

    # ===== 16. LinkStats Module =====
    ls_cfg = st.session_state.get('linkstats_config', {})
    linkstats_module = ET.SubElement(root, 'module', name='linkStats')

    ET.SubElement(
        linkstats_module,
        'param',
        name='writeLinkStatsInterval',
        value=str(int(ls_cfg.get('writeLinkStatsInterval', 0)))
    )

    ET.SubElement(
        linkstats_module,
        'param',
        name='averageLinkStatsOverIterations',
        value=str(int(ls_cfg.get('averageLinkStatsOverIterations', 5)))
    )
    # 在 generate_config_xml() 函数中，最后的 linkStats 模块之后添加：

    # ===== 新增：PlanInheritance Module =====
    pi_cfg = st.session_state.get('planinheritance_config', {})
    if pi_cfg.get('enabled', False):
        planinheritance_module = ET.SubElement(root, 'module', name='planInheritance')
        ET.SubElement(
            planinheritance_module,
            'param',
            name='enabled',
            value=str(pi_cfg['enabled']).lower()
        )

    # ===== 扩展：Plans Module =====
    # 在现有 plans_module 之后添加其他参数
    plans_cfg = st.session_state.get('plans_config', {})

    # networkRouteType
    ET.SubElement(
        plans_module,
        'param',
        name='networkRouteType',
        value=plans_cfg.get('networkRouteType', 'LinkNetworkRoute')
    )

    # activityDurationInterpretation
    ET.SubElement(
        plans_module,
        'param',
        name='activityDurationInterpretation',
        value=plans_cfg.get('activityDurationInterpretation', 'tryEndTimeThenDuration')
    )

    # tripDurationHandling
    ET.SubElement(
        plans_module,
        'param',
        name='tripDurationHandling',
        value=plans_cfg.get('tripDurationHandling', 'ignoreDelays')
    )

    # removingUnnecessaryPlanAttributes
    ET.SubElement(
        plans_module,
        'param',
        name='removingUnnecessaryPlanAttributes',
        value=str(plans_cfg.get('removingUnnecessaryPlanAttributes', False)).lower()
    )

    # inputCRS
    if plans_cfg.get('inputCRS', '').strip():
        ET.SubElement(
            plans_module,
            'param',
            name='inputCRS',
            value=plans_cfg['inputCRS'].strip()
        )

    # handlingOfPlansWithoutRoutingMode
    ET.SubElement(
        plans_module,
        'param',
        name='handlingOfPlansWithoutRoutingMode',
        value=plans_cfg.get('handlingOfPlansWithoutRoutingMode', 'reject')
    )

    # inputPersonAttributesFile (deprecated)
    if plans_cfg.get('insistingOnUsingDeprecatedPersonAttributeFile', False):
        if plans_cfg.get('inputPersonAttributesFile', '').strip():
            ET.SubElement(
                plans_module,
                'param',
                name='inputPersonAttributesFile',
                value=plans_cfg['inputPersonAttributesFile'].strip()
            )
        ET.SubElement(
            plans_module,
            'param',
            name='insistingOnUsingDeprecatedPersonAttributeFile',
            value='true'
        )

    # ===== 新增：PtCounts Module =====
    ptc_cfg = st.session_state.get('ptcounts_config', {})
    has_ptcounts_file = bool(
        ptc_cfg.get('inputOccupancyCountsFile')
        or ptc_cfg.get('inputBoardCountsFile')
        or ptc_cfg.get('inputAlightCountsFile')
    )

    if has_ptcounts_file:
        ptcounts_module = ET.SubElement(root, 'module', name='ptCounts')

        # outputformat
        ET.SubElement(
            ptcounts_module,
            'param',
            name='outputformat',
            value=ptc_cfg.get('outputformat', 'txt')
        )

        # distanceFilter & distanceFilterCenterNode
        if ptc_cfg.get('distanceFilter') is not None:
            ET.SubElement(
                ptcounts_module,
                'param',
                name='distanceFilter',
                value=str(ptc_cfg['distanceFilter'])
            )
        if ptc_cfg.get('distanceFilterCenterNode', '').strip():
            ET.SubElement(
                ptcounts_module,
                'param',
                name='distanceFilterCenterNode',
                value=ptc_cfg['distanceFilterCenterNode'].strip()
            )

        # input files
        if ptc_cfg.get('inputOccupancyCountsFile', '').strip():
            ET.SubElement(
                ptcounts_module,
                'param',
                name='inputOccupancyCountsFile',
                value=ptc_cfg['inputOccupancyCountsFile'].strip()
            )
        if ptc_cfg.get('inputBoardCountsFile', '').strip():
            ET.SubElement(
                ptcounts_module,
                'param',
                name='inputBoardCountsFile',
                value=ptc_cfg['inputBoardCountsFile'].strip()
            )
        if ptc_cfg.get('inputAlightCountsFile', '').strip():
            ET.SubElement(
                ptcounts_module,
                'param',
                name='inputAlightCountsFile',
                value=ptc_cfg['inputAlightCountsFile'].strip()
            )

        # countsScaleFactor
        ET.SubElement(
            ptcounts_module,
            'param',
            name='countsScaleFactor',
            value=str(ptc_cfg.get('countsScaleFactor', 1.0))
        )

        # ptCountsInterval
        ET.SubElement(
            ptcounts_module,
            'param',
            name='ptCountsInterval',
            value=str(ptc_cfg.get('ptCountsInterval', 10))
        )

    # ===== 扩展：Replanning Module（补充缺失参数） =====
    # 在已有 replanning_module 中添加：

    # planSelectorForRemoval
    ET.SubElement(
        replanning_module,
        'param',
        name='planSelectorForRemoval',
        value=st.session_state.replanning_config.get('planSelectorForRemoval', 'WorstPlanSelector')
    )

    # externalExeConfigTemplate
    if st.session_state.replanning_config.get('externalExeConfigTemplate', '').strip():
        ET.SubElement(
            replanning_module,
            'param',
            name='externalExeConfigTemplate',
            value=st.session_state.replanning_config['externalExeConfigTemplate'].strip()
        )

    # externalExeTmpFileRootDir
    if st.session_state.replanning_config.get('externalExeTmpFileRootDir', '').strip():
        ET.SubElement(
            replanning_module,
            'param',
            name='externalExeTmpFileRootDir',
            value=st.session_state.replanning_config['externalExeTmpFileRootDir'].strip()
        )

    # externalExeTimeOut
    ET.SubElement(
        replanning_module,
        'param',
        name='externalExeTimeOut',
        value=str(st.session_state.replanning_config.get('externalExeTimeOut', 3600))
    )


    # ===== 美化输出 =====
    xml_str = ET.tostring(root, encoding='unicode')
    dom = minidom.parseString(xml_str)
    pretty_xml = dom.toprettyxml(indent='    ')

    lines = pretty_xml.split('\n')
    lines[0] = '<?xml version="1.0" encoding="UTF-8"?>'
    lines.insert(1, '<!DOCTYPE config SYSTEM "http://www.matsim.org/files/dtd/config_v2.dtd">')

    result_lines = [line for line in lines if line.strip()]

    return '\n'.join(result_lines)


def render_generate_section():
    """渲染生成配置部分"""

    st.markdown('<div class="module-header">✅ 生成配置文件 / Generate Configuration</div>',
                unsafe_allow_html=True)

    # 验证配置
    st.markdown("#### 🔍 配置验证")

    errors, warnings = validate_full_configuration()

    # 显示结果
    if errors:
        st.markdown('<div class="error-box"><b>❌ 发现错误：</b></div>', unsafe_allow_html=True)
        for error in errors:
            st.error(error)

    if warnings:
        for warning in warnings:
            st.warning(warning)

    if not errors and not warnings:
        st.markdown("""
        <div class="success-box">
        ✅ <b>配置验证通过！</b>
        </div>
        """, unsafe_allow_html=True)

    # 配置摘要
    st.markdown("---")
    st.markdown("#### 📋 配置摘要")

    network_modes = list(st.session_state.get('network_modes', {}).keys())
    teleported_modes = list(st.session_state.get('teleported_modes', {}).keys())
    transit_submodes = list(st.session_state.get('transit_submodes', {}).keys())
    choosable_modes = ModeManager.get_choosable_modes()
    chain_modes = ModeManager.get_chain_based_modes()
    enabled_ae = ModeManager.get_enabled_access_egress_modes()
    transit_enabled = st.session_state.get('transit_enabled', False)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**基本信息：**")
        st.write(f"- 运行ID: {st.session_state.controller_config['runId']}")
        st.write(
            f"- 迭代: {st.session_state.controller_config['firstIteration']}-{st.session_state.controller_config['lastIteration']}")
        st.write(f"- 采样率: {st.session_state.qsim_config['flowCapacityFactor'] * 100:.0f}%")

    with col2:
        st.markdown("**出行模式：**")
        st.write(f"- 网络模式: {', '.join(network_modes) or '无'}")
        st.write(f"- 传送模式: {', '.join(teleported_modes) or '无'}")
        st.write(f"- 公交: {'启用' if transit_enabled else '禁用'}")
        if transit_enabled and transit_submodes:
            st.write(f"- 公交子模式: {', '.join(transit_submodes)}")

    with col3:
        st.markdown("**关键配置：**")
        st.write(f"- Agent可选: {', '.join(choosable_modes) or '无'}")
        st.write(f"- 链约束模式: {', '.join(chain_modes) or '无'}")
        if transit_enabled:
            st.write(f"- 接驳模式: {', '.join(enabled_ae) or '无'}")

    # XML配置预览
    st.markdown("---")
    st.markdown("#### 📝 将生成的模块配置")

    with st.expander("查看配置详情", expanded=False):
        st.code(f"""
# routing 模块
networkModes = {','.join(network_modes) if network_modes else '(无)'}
teleportedModeParameters = {', '.join(teleported_modes) if teleported_modes else '(无)'}

# qsim 模块
mainMode = {','.join(network_modes) if network_modes else '(无)'}

# subtourModeChoice 模块
modes = {','.join(choosable_modes) if choosable_modes else '(无)'}
chainBasedModes = {','.join(chain_modes) if chain_modes else '(无)'}

# transit 模块
useTransit = {str(transit_enabled).lower()}
transitModes = {'pt' if transit_enabled else '(未启用)'}

# swissRailRaptor 模块
intermodalAccessEgress = {', '.join(enabled_ae) if enabled_ae else '(未配置)'}

# scoring 模块 - modeParams
{', '.join(network_modes + teleported_modes + (['pt'] if transit_enabled else []))}
        """, language='ini')

    # 生成按钮
    st.markdown("---")
    st.markdown("#### 📥 生成并下载")

    if errors:
        st.error("⚠️ 请先修复上述错误！")
        st.button("生成配置文件", disabled=True)
    else:
        if st.button("🔧 生成配置文件", type="primary"):
            with st.spinner("正在生成配置文件..."):
                try:
                    xml_content = generate_config_xml()
                    st.session_state.generated_xml = xml_content
                    st.success("✅ 配置文件生成成功！")
                except Exception as e:
                    st.error(f"❌ 生成失败: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())

    # 显示预览和下载
    if st.session_state.get('generated_xml'):
        st.markdown("---")

        # 下载按钮
        col1, col2 = st.columns(2)

        with col1:
            st.download_button(
                label="📥 下载 config.xml",
                data=st.session_state.generated_xml,
                file_name="config.xml",
                mime="application/xml",
                type="primary"
            )

        with col2:
            run_id = st.session_state.controller_config['runId']
            st.download_button(
                label=f"📥 下载 config_{run_id}.xml",
                data=st.session_state.generated_xml,
                file_name=f"config_{run_id}.xml",
                mime="application/xml"
            )

        # XML预览
        with st.expander("👁️ 查看生成的XML", expanded=False):
            st.code(st.session_state.generated_xml, language='xml')

        # 使用说明
        st.markdown("---")
        st.markdown("#### 📖 使用说明")

        st.markdown(f"""
        **运行MATSim：**
        ```bash
        java -Xmx8g -jar matsim.jar config.xml
        ```

        **输出目录：** `{st.session_state.controller_config['outputDirectory']}`

        **关键输出文件：**
        - `output_plans.xml.gz` - 最终计划
        - `output_events.xml.gz` - 事件日志
        - `scorestats.png` - 收敛曲线
        """)


# ============================================================
# 主函数 / Main Function
# ============================================================

def main():
    """主应用入口"""

    # 初始化
    init_session_state()

    # 页面标题
    st.markdown(
        '<div class="main-header">🚗 MATSim 配置生成器<br>'
        '<span style="font-size: 1rem; color: #666;">傻瓜式新手引导系统</span></div>',
        unsafe_allow_html=True
    )

    # 侧边栏导航
    st.sidebar.title("📑 配置向导")

    # 定义步骤
    # 定义步骤
    # 在 main() 函数中，将 steps 列表替换为：

    steps = [
        ("1️⃣ 出行模式", "modes", "🎛️"),
        ("2️⃣ 输入文件", "files", "📁"),
        ("3️⃣ 路网设置", "network", "🕸️"),
        ("4️⃣ 路由配置", "routing", "🗺️"),
        ("5️⃣ 全局设置", "global", "🌍"),
        ("6️⃣ Plans模块", "plans", "📋"),
        ("7️⃣ 仿真控制", "controller", "🎮"),
        ("8️⃣ 仿真内核", "mobsim", "🚦"),
        ("9️⃣ 出行时间", "travelTimeCalculator", "⏱️"),  # 新增
        ("🔟 车辆配置", "vehicles", "🚗"),  # 新增
        ("⓫ 活动类型", "activities", "📍"),
        ("⓬ 效用评分", "scoring", "⭐"),
        ("⓭ 子路程模式", "subtourModeChoice", "🔄"),
        ("⓮ 时间变异器", "timeAllocationMutator", "⏰"),
        ("⓯ 公交基础", "transit", "🚌"),
        ("⓰ 公交路由器", "transitRouter", "🔍"),
        ("⓱ SwissRailRaptor", "swissRailRaptor", "🚄"),
        ("⓲ 重规划策略", "replanning", "🔁"),
        ("⓳ 计数评估", "counts", "📈"),
        ("⓴ 公交计数", "ptCounts", "🚌📊"),
        ("㉑ LinkStats", "linkStats", "🧮"),
        ("㉒ 事件管理", "eventsManager", "📊"),
        ("㉓ 计划继承", "planInheritance", "🧬"),
        ("㉔ VSP实验", "vspExperimental", "🧪"),  # 新增
        ("㉕ 生成配置", "generate", "✅"),
    ]






    # 显示进度
    current_step_default = st.session_state.pop('nav_target', st.session_state.get('current_step', 'modes'))
    step_keys = [s[1] for s in steps]
    if current_step_default not in step_keys:
        current_step_default = 'modes'
    current_step = st.sidebar.radio(
        "配置步骤",
        options=step_keys,
        format_func=lambda x: next((s[0] for s in steps if s[1] == x), x),
        label_visibility="collapsed",
        index=step_keys.index(current_step_default),
        key="current_step"
    )

    # 快速操作
    st.sidebar.markdown("---")
    st.sidebar.markdown("**⚡ 快速操作**")

    col1, col2 = st.sidebar.columns(2)

    with col1:
        if st.button("🔍 检测配置", key="sidebar_check", use_container_width=True):
            st.session_state['show_config_check_dialog'] = True

    with col2:
        if st.button("🔄 重置配置", key="sidebar_reset", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    # 第二行按钮
    if st.sidebar.button("🔧 自动修复基础问题", key="sidebar_fix", use_container_width=True):
        ModeManager.auto_fix_configuration()
        st.sidebar.success("✅ 已修复基础问题")
        st.rerun()

    # 配置状态
    # 配置状态（侧边栏）
    st.sidebar.markdown("---")
    st.sidebar.markdown("**📊 配置状态**")

    errors, warnings = validate_full_configuration()

    if errors:
        summary = errors[0] if errors else ""
        st.sidebar.error(f"❌ {len(errors)} 个错误：{summary}")
    elif warnings:
        summary = warnings[0] if warnings else ""
        st.sidebar.warning(f"⚠️ {len(warnings)} 个警告：{summary}")
    else:
        st.sidebar.success("✅ 配置正常")

    # 模式统计
    enabled = ModeManager.get_enabled_modes()
    total_modes = len(enabled['network']) + len(enabled['teleported'])
    if enabled['transit']:
        total_modes += 1

    st.sidebar.caption(f"出行模式: {total_modes} 个")
    st.sidebar.caption(f"活动类型: {len(st.session_state.get('activity_params', {}))} 个")
    st.sidebar.caption(f"迭代次数: {st.session_state.controller_config.get('lastIteration', 100)}")

    # 显示配置检测对话框
    if st.session_state.get('show_config_check_dialog', False):
        with st.container():
            st.markdown("---")
            render_config_check_dialog()

            if st.button("✖️ 关闭检测面板", use_container_width=True):
                st.session_state['show_config_check_dialog'] = False
                st.rerun()

            st.markdown("---")
    # 主内容区

    st.markdown("---")

    if current_step == "modes":
        render_mode_configuration()
    elif current_step == "files":
        render_files_configuration()
    elif current_step == "network":
        render_network_configuration()
    elif current_step == "routing":
        render_routing_configuration()
    elif current_step == "global":
        render_global_configuration()
    elif current_step == "plans":
        render_plans_configuration()
    elif current_step == "controller":
        render_controller_configuration()
    elif current_step == "mobsim":
        mobsim_type = st.session_state.controller_config.get('mobsim', 'qsim')
        if mobsim_type == 'qsim':
            render_qsim_configuration()
        elif mobsim_type == 'hermes':
            render_hermes_configuration()
        else:
            st.warning(f"当前 mobsim = {mobsim_type} 尚未提供专门配置界面。")
    elif current_step == "travelTimeCalculator":  # 新增
        render_travel_time_calculator_configuration()
    elif current_step == "vehicles":  # 新增
        render_vehicles_configuration()
    elif current_step == "activities":
        render_activity_configuration()
    elif current_step == "scoring":
        render_scoring_configuration()
    elif current_step == "subtourModeChoice":
        render_subtour_mode_choice_configuration()
    elif current_step == "timeAllocationMutator":
        render_time_allocation_mutator_configuration()
    elif current_step == "transit":
        render_transit_configuration()
    elif current_step == "transitRouter":
        render_transit_router_configuration()
    elif current_step == "swissRailRaptor":
        render_swiss_rail_raptor_configuration()
    elif current_step == "replanning":
        render_replanning_configuration_extended()
    elif current_step == "counts":
        render_counts_configuration()
    elif current_step == "ptCounts":
        render_ptcounts_configuration()
    elif current_step == "linkStats":
        render_linkstats_configuration()
    elif current_step == "eventsManager":
        render_events_manager_configuration()
    elif current_step == "planInheritance":
        render_planinheritance_configuration()
    elif current_step == "vspExperimental":  # 新增
        render_vsp_experimental_configuration()
    elif current_step == "generate":
        render_generate_section()
    elif current_step == "plans":
        render_plans_configuration()
    elif current_step == "ptCounts":
        render_ptcounts_configuration()
    elif current_step == "planInheritance":
        render_planinheritance_configuration()
    elif current_step == "replanning":
        render_replanning_configuration_extended()  # 使用扩展版本


    # 底部导航
    st.markdown("---")

    step_idx = [s[1] for s in steps].index(current_step)

    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if step_idx > 0:
            prev_step = steps[step_idx - 1]
            if st.button(f"⬅️ {prev_step[0]}", use_container_width=True):
                st.session_state['nav_target'] = prev_step[1]
                st.rerun()

    with col2:
        st.markdown(f"<center>步骤 {step_idx + 1} / {len(steps)}</center>", unsafe_allow_html=True)

    with col3:
        if step_idx < len(steps) - 1:
            next_step = steps[step_idx + 1]
            if st.button(f"{next_step[0]} ➡️", use_container_width=True):
                st.session_state['nav_target'] = next_step[1]
                st.rerun()


# ============================================================
# 应用入口 / Application Entry Point
# ============================================================

if __name__ == "__main__":
    main()

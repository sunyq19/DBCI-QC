"""Presentation plugins consume saved evidence; they never execute QC algorithms."""
from copy import deepcopy

VERSION = 'qc-visualizations/1.0'
LEI = 'https://github.com/Jlei61/BrainElecQC'
GNOSIS = 'https://github.com/Gnosis-Neurodynamics/GnosisNeuroDynamicSE'
PROJECT = 'https://github.com/sunyq19/DBCI-QC'
_ROWS = [
 ('waveform','波形与候选标记','查看原始波形，定位需要复核的时间段。',['M02','M06','M09'],[LEI,PROJECT],'已有波形快照可查看；原文件可读时，报告支持前后拖动与最多6道同步对照。'),
 ('channel_metrics','通道指标','逐道查看 PREP 指标和线长；不同单位分开绘制。',['M05'],[LEI,GNOSIS],'对应通道指标已计算；候选标记沿用检测结果。'),
 ('psd','功率谱密度','查看各通道频谱；两条路线分图展示。',['M04'],[LEI,GNOSIS],'需要 PSD 与频率轴；统一显示 dB re μV²/Hz，不把处理前后变化当改善。'),
 ('interference','工频命中比例','展示逐通道工频命中窗占比。',['M04'],[LEI],'需要工频窗口观测；占比是通道窗命中率，不是受污染时长。'),
 ('artifact_burden','异常时间占比','横向条形图展示伪差、低频和高频候选时间占比。',['M06'],[GNOSIS],'需要对应灵犀云方法结果；缺测显示未评，不补零。'),
 ('timeline','异常时间轴','按通道标出候选区间，沿用原始记录时间。',['M06'],[LEI,GNOSIS],'需要原始时间坐标下的候选区间；拼接频谱不用于时间定位。'),
 ('band_power','相对频带功率','通道×五频带热图，颜色固定为 0–100%。',['M04'],[GNOSIS],'需要灵犀云相对功率结果；比例不代表质量分。'),
 ('band_amplitude','频带平均幅值','通道×五频带热图，标注 μV 与当前色标。',['M04'],[GNOSIS],'需要灵犀云幅值结果；不跨不同色标直接比较颜色。'),
 ('psd_distance','PSD 通道差异','显示各通道频谱距离及候选通道。',['M05'],[GNOSIS],'需要灵犀云 PSD 差异结果；频谱离群不自动等于坏道。'),
 ('reference_ranges','参考范围对照','用区间与落点展示参考范围，替代堆叠雷达图。',['M04'],[GNOSIS],'需要参考上下界及实测值；参考库适用性仍需确认。'),
 ('topography','头皮地形图','按电极位置展示通道指标。',['M02','M04','M05'],[GNOSIS],'待接入可信坐标或用户确认的标准 montage；不凭通道名静默猜位置。'),
 ('radar','多指标雷达图','比较多维特征轮廓。',['M04','M05','M06'],[GNOSIS],'待确认尺度、方向和归一化；暂不将不同量纲拼成总分。'),
]


def visualization_specs():
    return [dict(can_output_score=False, scoring_role='presentation', id='viz_'+key,key=key,name=name,description=description,dependencies=deps,
                 sources=urls,conditions=conditions,status='planned' if key in {'topography','radar'} else 'available',
                 implementation='DBCI-QC统一展示；读取来源算法结果，不复用Notebook样式',scope=['eeg'],version=VERSION)
            for key,name,description,deps,urls,conditions in deepcopy(_ROWS)]

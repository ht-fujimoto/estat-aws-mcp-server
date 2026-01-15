#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
北海道人口データ分析スクリプト（最終版）
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

# 日本語フォント設定
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'Hiragino Sans', 'Yu Gothic', 'Meirio', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# CSVファイル読み込み（文字列として読み込む）
df = pd.read_csv('hokkaido_population_2005.csv', dtype={'@cat01': str, '@cat02': str, '@cat03': str, '@cat04': str, '@area': str})

print("=" * 80)
print("北海道人口データ分析レポート（2005年国勢調査）")
print("=" * 80)
print()

# 基本統計
print("【1. データ概要】")
print(f"総レコード数: {len(df):,}件")
print()

# 総人口（cat01='00700', cat02='000', cat03='T01', cat04='000'が総数）
total_pop_row = df[(df['@cat01'] == '00700') & (df['@cat02'] == '000') & (df['@cat03'] == 'T01') & (df['@cat04'] == '000')]
if len(total_pop_row) > 0:
    total_pop = int(total_pop_row['$'].iloc[0])
    print(f"北海道総人口（2005年）: {total_pop:,}人")
print()

# 性別データの抽出（cat04='001'=男性, '002'=女性）
print("【2. 性別人口】")
male_pop = df[(df['@cat01'] == '00700') & (df['@cat02'] == '000') & (df['@cat03'] == 'T01') & (df['@cat04'] == '001')]
female_pop = df[(df['@cat01'] == '00700') & (df['@cat02'] == '000') & (df['@cat03'] == 'T01') & (df['@cat04'] == '002')]
if len(male_pop) > 0 and len(female_pop) > 0:
    male = int(male_pop['$'].iloc[0])
    female = int(female_pop['$'].iloc[0])
    print(f"男性: {male:,}人 ({male/total_pop*100:.1f}%)")
    print(f"女性: {female:,}人 ({female/total_pop*100:.1f}%)")
print()

# 年齢階級別データ（0-10歳）
print("【3. 年齢階級別人口（0-10歳）】")
age_data = df[(df['@cat01'] == '00700') & (df['@cat02'] == '000') & (df['@cat04'] == '000') & (df['@cat03'].str.isdigit())].copy()
age_data['age'] = age_data['@cat03'].astype(int)
age_data['population'] = age_data['$'].astype(int)
age_data = age_data.sort_values('age')
print(age_data[['age', 'population']].head(11).to_string(index=False))
print()

# 年齢階級別データ（全年齢の統計）
print("【4. 年齢階級別統計】")
all_ages = age_data.copy()
print(f"最年少: {all_ages['age'].min()}歳")
print(f"最高齢: {all_ages['age'].max()}歳")
print(f"平均人口/年齢: {all_ages['population'].mean():,.0f}人")
print(f"最多人口年齢: {all_ages.loc[all_ages['population'].idxmax(), 'age']}歳 ({all_ages['population'].max():,}人)")
print()

# グラフ作成
fig, axes = plt.subplots(2, 2, figsize=(16, 12))

# 1. 年齢別人口（0-20歳）
age_0_20 = age_data[age_data['age'] <= 20]
axes[0, 0].bar(age_0_20['age'], age_0_20['population'])
axes[0, 0].set_xlabel('年齢')
axes[0, 0].set_ylabel('人口')
axes[0, 0].set_title('年齢別人口（0-20歳）')
axes[0, 0].grid(True, alpha=0.3)

# 2. 年齢別人口（全年齢）
axes[0, 1].plot(all_ages['age'], all_ages['population'], linewidth=2)
axes[0, 1].set_xlabel('年齢')
axes[0, 1].set_ylabel('人口')
axes[0, 1].set_title('年齢別人口分布（全年齢）')
axes[0, 1].grid(True, alpha=0.3)

# 3. 性別分布
if len(male_pop) > 0 and len(female_pop) > 0:
    male_val = int(male_pop['$'].iloc[0])
    female_val = int(female_pop['$'].iloc[0])
    axes[1, 0].pie([male_val, female_val], labels=['男性', '女性'], autopct='%1.1f%%', startangle=90, colors=['#4A90E2', '#E24A90'])
    axes[1, 0].set_title('性別分布')

# 4. データサマリー
axes[1, 1].text(0.1, 0.9, f"総人口: {total_pop:,}人", fontsize=16, weight='bold', transform=axes[1, 1].transAxes)
axes[1, 1].text(0.1, 0.8, f"男性: {male:,}人 ({male/total_pop*100:.1f}%)", fontsize=12, transform=axes[1, 1].transAxes)
axes[1, 1].text(0.1, 0.7, f"女性: {female:,}人 ({female/total_pop*100:.1f}%)", fontsize=12, transform=axes[1, 1].transAxes)
axes[1, 1].text(0.1, 0.6, f"調査年: 2005年", fontsize=12, transform=axes[1, 1].transAxes)
axes[1, 1].text(0.1, 0.5, f"データソース: e-Stat", fontsize=12, transform=axes[1, 1].transAxes)
axes[1, 1].text(0.1, 0.4, f"データセットID: 0000033783", fontsize=10, transform=axes[1, 1].transAxes)
axes[1, 1].axis('off')
axes[1, 1].set_title('データサマリー')

plt.tight_layout()
plt.savefig('hokkaido_population_analysis_final.png', dpi=150, bbox_inches='tight')
print("グラフを保存しました: hokkaido_population_analysis_final.png")
print()

print("=" * 80)
print("分析完了")
print("=" * 80)

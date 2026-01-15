#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
北海道人口データ分析スクリプト
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # GUIなし環境用

# 日本語フォント設定
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'Hiragino Sans', 'Yu Gothic', 'Meirio', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# CSVファイル読み込み
df = pd.read_csv('hokkaido_population_2005.csv')

print("=" * 80)
print("北海道人口データ分析レポート（2005年国勢調査）")
print("=" * 80)
print()

# 基本統計
print("【1. データ概要】")
print(f"総レコード数: {len(df):,}件")
print(f"カラム: {', '.join(df.columns)}")
print()

# 総人口（cat03='T01', cat04=0が総数）
total_pop_row = df[(df['@cat03'] == 'T01') & (df['@cat04'] == 0) & (df['@area'] == 1000)]
if len(total_pop_row) > 0:
    total_pop = int(total_pop_row['$'].iloc[0])
    print(f"北海道総人口（2005年）: {total_pop:,}人")
print()

# 性別データの抽出（cat03='T01', cat04=1=男性, 2=女性）
print("【2. 性別人口】")
male_pop = df[(df['@cat03'] == 'T01') & (df['@cat04'] == 1) & (df['@area'] == 1000)]
female_pop = df[(df['@cat03'] == 'T01') & (df['@cat04'] == 2) & (df['@area'] == 1000)]
if len(male_pop) > 0 and len(female_pop) > 0:
    male = int(male_pop['$'].iloc[0])
    female = int(female_pop['$'].iloc[0])
    print(f"男性: {male:,}人 ({male/total_pop*100:.1f}%)")
    print(f"女性: {female:,}人 ({female/total_pop*100:.1f}%)")
print()

# 年齢階級別データ（cat04=0が総数、cat03が年齢）
print("【3. 年齢階級別人口（0-10歳）】")
age_data = df[(df['@cat04'] == 0) & (df['@area'] == 1000) & (df['@cat03'] != 'T01')].copy()
age_data['population'] = age_data['$'].astype(int)
age_data = age_data.sort_values('@cat03')
print(age_data[['@cat03', 'population']].head(11).to_string(index=False))
print()

# 地域別データ（area別）
print("【4. 地域別人口（上位10）】")
area_data = df[(df['@cat03'] == 'T01') & (df['@cat04'] == 0)].copy()
area_data['population'] = area_data['$'].astype(int)
area_data = area_data.sort_values('population', ascending=False)
print(area_data[['@area', 'population']].head(10).to_string(index=False))
print()

# グラフ作成
fig, axes = plt.subplots(2, 2, figsize=(16, 12))

# 1. 年齢階級別人口（0-20歳）
age_plot_data = df[(df['@cat04'] == 0) & (df['@area'] == 1000) & (df['@cat03'] != 'T01')].copy()
age_plot_data['population'] = age_plot_data['$'].astype(int)
age_plot_data = age_plot_data.sort_values('@cat03').head(21)
if len(age_plot_data) > 0:
    axes[0, 0].barh(range(len(age_plot_data)), age_plot_data['population'].values)
    axes[0, 0].set_yticks(range(len(age_plot_data)))
    axes[0, 0].set_yticklabels([f"{x}歳" for x in age_plot_data['@cat03'].values])
    axes[0, 0].set_xlabel('人口')
    axes[0, 0].set_title('年齢別人口（0-20歳）')
    axes[0, 0].invert_yaxis()

# 2. 地域別人口（上位10）
area_plot_data = df[(df['@cat03'] == 'T01') & (df['@cat04'] == 0)].copy()
area_plot_data['population'] = area_plot_data['$'].astype(int)
area_plot_data = area_plot_data.sort_values('population', ascending=False).head(10)
if len(area_plot_data) > 0:
    axes[0, 1].barh(range(len(area_plot_data)), area_plot_data['population'].values)
    axes[0, 1].set_yticks(range(len(area_plot_data)))
    axes[0, 1].set_yticklabels(area_plot_data['@area'].values)
    axes[0, 1].set_xlabel('人口')
    axes[0, 1].set_title('地域別人口（上位10）')
    axes[0, 1].invert_yaxis()

# 3. 性別分布
male_pop_val = df[(df['@cat03'] == 'T01') & (df['@cat04'] == 1) & (df['@area'] == 1000)]
female_pop_val = df[(df['@cat03'] == 'T01') & (df['@cat04'] == 2) & (df['@area'] == 1000)]
if len(male_pop_val) > 0 and len(female_pop_val) > 0:
    male_val = int(male_pop_val['$'].iloc[0])
    female_val = int(female_pop_val['$'].iloc[0])
    axes[1, 0].pie([male_val, female_val], labels=['男性', '女性'], autopct='%1.1f%%', startangle=90)
    axes[1, 0].set_title('性別分布')

# 4. データ分布の統計
total_pop_val = df[(df['@cat03'] == 'T01') & (df['@cat04'] == 0) & (df['@area'] == 1000)]
if len(total_pop_val) > 0:
    total = int(total_pop_val['$'].iloc[0])
    axes[1, 1].text(0.1, 0.9, f"総人口: {total:,}人", fontsize=14, transform=axes[1, 1].transAxes)
    axes[1, 1].text(0.1, 0.8, f"総レコード数: {len(df):,}件", fontsize=12, transform=axes[1, 1].transAxes)
    axes[1, 1].text(0.1, 0.7, f"地域数: {df['@area'].nunique()}地域", fontsize=12, transform=axes[1, 1].transAxes)
    axes[1, 1].text(0.1, 0.6, f"年齢区分数: {df['@cat03'].nunique()}区分", fontsize=12, transform=axes[1, 1].transAxes)
    axes[1, 1].text(0.1, 0.5, f"調査年: 2005年", fontsize=12, transform=axes[1, 1].transAxes)
    axes[1, 1].axis('off')
    axes[1, 1].set_title('データサマリー')

plt.tight_layout()
plt.savefig('hokkaido_population_analysis.png', dpi=150, bbox_inches='tight')
print("グラフを保存しました: hokkaido_population_analysis.png")
print()

print("=" * 80)
print("分析完了")
print("=" * 80)
